# terraform_utils.py
import os
import asyncio
import logging
import textwrap
import shutil
from dotenv import load_dotenv
from datetime import datetime

# Load .env first
load_dotenv()

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------
# ENV variables
# --------------------------------------------------------------------
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
TF_STATE_BUCKET = os.getenv("TF_STATE_BUCKET")
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE")

# --------------------------------------------------------------------
# FIXED MODULE PATH FOR WORKER CONTAINER
# --------------------------------------------------------------------
# Dockerfile copies modules → /worker/app/modules
MODULE_PATH =  "/worker/modules/ec2"     # <--- FIXED


# --------------------------------------------------------------------
# Create Terraform files per-job
# --------------------------------------------------------------------
def generate_root_terraform_files(device_id: str, instance_name: str, path: str):
    """
    Creates a complete terraform working directory for this job.
    """

    # Clean old folder if exists
    if os.path.exists(path):
        shutil.rmtree(path)

    os.makedirs(path, exist_ok=True)

    logger.info(f"📁 Creating Terraform file set for job {device_id} at {path}")

    # ---------------------------------------------
    # main.tf
    # ---------------------------------------------
    main_tf = textwrap.dedent(f"""
    module "ec2" {{
      source        = "{MODULE_PATH}"
      ami           = "ami-0c02fb55956c7d316"
      instance_type = "t3.micro"
      instance_name = "{instance_name}"
      device_id     = "{device_id}"
    }}
    """)

    # ---------------------------------------------
    # variables.tf
    # ---------------------------------------------
    variables_tf = textwrap.dedent("""
    variable "device_id" {
      type        = string
      description = "Unique device ID"
    }

    variable "instance_name" {
      type        = string
      description = "EC2 instance name"
    }
    """)

    # ---------------------------------------------
    # outputs.tf
    # ---------------------------------------------
    outputs_tf = textwrap.dedent("""
    output "ec2_instance_id" {
      value = module.ec2.instance_id
    }

    output "ec2_public_ip" {
      value = module.ec2.public_ip
    }
    """)

    # ---------------------------------------------
    # provider.tf
    # ---------------------------------------------
    provider_tf = textwrap.dedent(f"""
    terraform {{
      required_version = ">= 1.1.0"

      backend "s3" {{
        bucket         = "{TF_STATE_BUCKET}"
        key            = "state/{device_id}.tfstate"
        region         = "{AWS_REGION}"
        dynamodb_table = "{DYNAMO_TABLE}"
        encrypt        = true
      }}
    }}

    provider "aws" {{
      region = "{AWS_REGION}"
    }}
    """)

    # Save all files
    files = {
        "main.tf": main_tf,
        "variables.tf": variables_tf,
        "outputs.tf": outputs_tf,
        "provider.tf": provider_tf,
    }

    for filename, content in files.items():
        with open(os.path.join(path, filename), "w") as f:
            f.write(content.strip() + "\n")

    logger.info(f"✅ Terraform files generated at: {path}")


# --------------------------------------------------------------------
# Run terraform commands
# --------------------------------------------------------------------
async def _run_cmd(cmd: list, cwd: str):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


async def run_terraform_commands(path: str, device_id: str, instance_name: str):
    start = datetime.utcnow()
    logs = []

    logger.info(f"🚀 Starting Terraform init+apply for device {device_id}")

    # terraform init
    ret, out, err = await _run_cmd(["terraform", "init", "-input=false"], cwd=path)
    logs += [out, err]

    if ret != 0:
        return False, "\n".join(logs), (datetime.utcnow() - start).total_seconds()

    # terraform apply
    ret, out, err = await _run_cmd([
        "terraform", "apply", "-auto-approve", "-input=false",
        "-var", f"device_id={device_id}",
        "-var", f"instance_name={instance_name}"
    ], cwd=path)

    logs += [out, err]
    duration = (datetime.utcnow() - start).total_seconds()

    if ret != 0:
        logger.error("❌ Terraform apply failed")
        return False, "\n".join(logs), duration

    # best-effort terraform output
    try:
        ret2, out2, err2 = await _run_cmd(["terraform", "output", "-json"], cwd=path)
        logs += [out2, err2]
    except:
        pass

    logger.info("✅ Terraform apply completed successfully")
    return True, "\n".join(logs), duration


# --------------------------------------------------------------------
# Terraform destroy
# --------------------------------------------------------------------
async def destroy_terraform_resources(path: str, device_id: str, instance_name: str):
    start = datetime.utcnow()
    logs = []

    logger.warning(f"⚠️ Destroying Terraform resources for {device_id}")

    ret, out, err = await _run_cmd([
        "terraform", "destroy", "-auto-approve", "-input=false",
        "-var", f"device_id={device_id}",
        "-var", f"instance_name={instance_name}"
    ], cwd=path)

    logs += [out, err]
    duration = (datetime.utcnow() - start).total_seconds()

    if ret != 0:
        logger.error("❌ Terraform destroy failed")

    return (ret == 0), "\n".join(logs), duration
