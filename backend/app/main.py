# main.py
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fix Python path (so app.* works everywhere)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from rq import Queue
from rq.job import Job

from app.models.request_models import DeployRequest, DestroyRequest
from app.jobs.jobs import create_server_job_sync, destroy_server_job_sync
from app.services.db_utils import init_db


# -------------------------------------------------------------
# FastAPI App
# -------------------------------------------------------------
app = FastAPI(title="Terraform Provisioner")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Redis Queue
# -------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
task_queue = Queue(connection=redis_conn)

# -------------------------------------------------------------
# Startup → DB init with retry
# -------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    max_retries = 10
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}: Initializing DB...")
            await init_db()
            print("✅ Database initialized successfully.")
            break
        except Exception as e:
            print(f"❌ DB init failed: {e}")
            await asyncio.sleep(3)


# -------------------------------------------------------------
# CREATE SERVER
# -------------------------------------------------------------
@app.post("/create-server")
async def create_server(request: DeployRequest):

    job = task_queue.enqueue(
        create_server_job_sync,
        request.device_id,
        request.instance_name,
        request.user
    )
    return {"message": "Deployment started", "job_id": job.id}


# -------------------------------------------------------------
# DESTROY SERVER
# -------------------------------------------------------------
@app.post("/destroy-server")
async def destroy_server(request: DestroyRequest):

    job = task_queue.enqueue(
        destroy_server_job_sync,
        request.device_id,
        request.instance_name,
        request.user
    )
    return {"message": "Destroy started", "job_id": job.id}


# -------------------------------------------------------------
# JOB STATUS
# -------------------------------------------------------------
@app.get("/job/{job_id}")
async def job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        return {"status": "not_found", "result": None}

    return {
        "status": job.get_status(),
        "result": job.result
    }
