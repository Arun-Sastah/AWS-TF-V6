# jobs.py
import os
import asyncio
import logging
from datetime import datetime

from app.services.terraform_utils import (
    generate_root_terraform_files,
    run_terraform_commands,
    destroy_terraform_resources
)
from app.services.db_utils import log_request, log_resource

logger = logging.getLogger(__name__)

# Path where Terraform templates will be generated
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERRAFORM_ROOT = os.path.join(BACKEND_DIR, "terraform_templates")


# =====================================================================
# HELPER → Normalize request_id
# =====================================================================
def normalize_request_id(device_id: str) -> int:
    try:
        return int(device_id)
    except:
        # fallback if non-numeric ID
        return abs(hash(device_id)) % (10 ** 8)


# =====================================================================
# ----------------------  CREATE SERVER JOB  ---------------------------
# =====================================================================
async def create_server_job(device_id: str, instance_name: str, user: str) -> dict:

    request_id = normalize_request_id(device_id)
    device_path = os.path.join(TERRAFORM_ROOT, device_id)

    logger.info(f"🚀 CREATE started for device_id={device_id}, path={device_path}")

    # Initial DB log
    log_id = await log_request(
        request_id=request_id,
        user_id=user,
        status="create_started"
    )

    try:
        # Step 1: Generate Terraform files
        generate_root_terraform_files(
            device_id=device_id,
            instance_name=instance_name,
            path=device_path
        )

        # Step 2: Terraform apply
        success, output, duration = await run_terraform_commands(
            path=device_path,
            device_id=str(device_id),
            instance_name=instance_name
        )

        # Step 3: Final result logging
        await log_request(
            request_id=request_id,
            user_id=user,
            status="success" if success else "failed",
            duration_seconds=duration,
            error_message=None if success else output
        )

        # Step 4: Resource log
        if success:
            await log_resource(
                log_id=log_id,
                resource_type="EC2",
                resource_name=instance_name,
                resource_id_value=device_id
            )

        return {
            "success": success,
            "output": output,
            "duration": duration
        }

    except Exception as e:
        error_text = f"Unhandled error: {str(e)}"
        logger.error(error_text)

        await log_request(
            request_id=request_id,
            user_id=user,
            status="error",
            error_message=error_text
        )

        return {
            "success": False,
            "output": error_text,
            "duration": 0
        }


# =====================================================================
# ----------------------  DESTROY SERVER JOB  --------------------------
# =====================================================================
async def destroy_server_job(device_id: str, instance_name: str, user: str) -> dict:

    request_id = normalize_request_id(device_id)
    device_path = os.path.join(TERRAFORM_ROOT, device_id)

    logger.info(f"⚠️ DESTROY started for device_id={device_id}, path={device_path}")

    # Initial DB log
    await log_request(
        request_id=request_id,
        user_id=user,
        status="destroy_started"
    )

    try:
        # Terraform destroy
        success, output, duration = await destroy_terraform_resources(
            path=device_path,
            device_id=str(device_id),
            instance_name=instance_name
        )

        # Final DB log
        await log_request(
            request_id=request_id,
            user_id=user,
            status="destroyed" if success else "destroy_failed",
            duration_seconds=duration,
            error_message=None if success else output
        )

        return {
            "success": success,
            "output": output,
            "duration": duration
        }

    except Exception as e:
        error_text = f"Destroy crashed: {str(e)}"
        logger.error(error_text)

        await log_request(
            request_id=request_id,
            user_id=user,
            status="destroy_error",
            error_message=error_text
        )

        return {
            "success": False,
            "output": error_text,
            "duration": 0
        }


# =====================================================================
# -----------------------  SYNC WRAPPERS  ------------------------------
# =====================================================================
def create_server_job_sync(device_id: str, instance_name: str, user: str) -> dict:
    """
    Wrapper so RQ (sync worker) can run async job.
    """
    try:
        return asyncio.run(create_server_job(device_id, instance_name, user))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(create_server_job(device_id, instance_name, user))


def destroy_server_job_sync(device_id: str, instance_name: str, user: str) -> dict:
    """
    Wrapper for destroy job.
    """
    try:
        return asyncio.run(destroy_server_job(device_id, instance_name, user))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(destroy_server_job(device_id, instance_name, user))
