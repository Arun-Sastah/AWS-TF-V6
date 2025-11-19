# worker.py
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fix import path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Job imports
from app.jobs.jobs import create_server_job_sync, destroy_server_job_sync

from redis import Redis
from rq import Worker, Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(REDIS_URL)

queue = Queue("default", connection=redis_conn)

if __name__ == "__main__":
    print("🚀 RQ Worker Started and Listening on Queue: default")
    worker = Worker([queue], connection=redis_conn)
    worker.work()
