import os
import asyncio
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    Table, Column, Integer, String, Text, Float,
    TIMESTAMP, MetaData, ForeignKey, func, select
)

import redis.asyncio as aioredis

# -------------------------------------------------------------------
# Database Configuration
# -------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/appdb"
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
metadata = MetaData()

# -------------------------------------------------------------------
# Redis
# -------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

# -------------------------------------------------------------------
# SQLAlchemy Tables
# -------------------------------------------------------------------
request_status_logs = Table(
    "request_status_logs",
    metadata,
    Column("log_id", Integer, primary_key=True, autoincrement=True),
    Column("request_id", Integer, nullable=False),
    Column("user_id", String(100), nullable=False),
    Column("status", String(50), nullable=False),
    Column("duration_seconds", Float, nullable=True),
    Column("error_message", Text, nullable=True),
    Column("created_at", TIMESTAMP, server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
)

request_resources = Table(
    "request_resources",
    metadata,
    Column("resource_id", Integer, primary_key=True, autoincrement=True),
    Column("log_id", Integer, ForeignKey("request_status_logs.log_id", ondelete="CASCADE"), nullable=False),
    Column("resource_type", String(100)),
    Column("resource_name", String(255)),
    Column("resource_id_value", String(255)),
    Column("created_at", TIMESTAMP, server_default=func.now(), nullable=False)
)

# -------------------------------------------------------------------
# Redis cache
# -------------------------------------------------------------------
async def cache_job_status(job_id: str, status: str):
    try:
        await redis_client.set(f"job:{job_id}", status)
    except Exception:
        pass

async def get_cached_job_status(job_id: str) -> Optional[str]:
    try:
        return await redis_client.get(f"job:{job_id}")
    except Exception:
        return None

# -------------------------------------------------------------------
# Log request status
# -------------------------------------------------------------------
async def log_request(
    request_id: int,
    user_id: str,
    status: str,
    duration_seconds: float = None,
    error_message: str = None,
    created_at: datetime = None
) -> int:

    async with async_session() as session:
        async with session.begin():

            existing = await session.execute(
                select(request_status_logs.c.log_id)
                .where(request_status_logs.c.request_id == request_id)
            )
            log_id = existing.scalar()

            if log_id:
                await session.execute(
                    request_status_logs.update()
                    .where(request_status_logs.c.log_id == log_id)
                    .values(
                        status=status,
                        duration_seconds=duration_seconds,
                        error_message=error_message,
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                result = await session.execute(
                    request_status_logs.insert().values(
                        request_id=request_id,
                        user_id=user_id,
                        status=status,
                        duration_seconds=duration_seconds,
                        error_message=error_message,
                        created_at=created_at or datetime.utcnow()
                    ).returning(request_status_logs.c.log_id)
                )
                log_id = result.scalar()

    await cache_job_status(str(request_id), status)
    return log_id

# -------------------------------------------------------------------
# Log created AWS resources
# -------------------------------------------------------------------
async def log_resource(log_id: int, resource_type: str, resource_name: str, resource_id_value: str):

    async with async_session() as session:
        async with session.begin():

            await session.execute(
                request_resources.insert().values(
                    log_id=log_id,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    resource_id_value=resource_id_value
                )
            )

# -------------------------------------------------------------------
# DELETE all logs/resources for DESTROY 
# -------------------------------------------------------------------
async def delete_resources_by_request_id(request_id: int):
    async with async_session() as session:
        async with session.begin():

            # Delete child rows
            await session.execute(
                request_resources.delete().where(
                    request_resources.c.log_id.in_(
                        select(request_status_logs.c.log_id)
                        .where(request_status_logs.c.request_id == request_id)
                    )
                )
            )

            # Delete parent row
            await session.execute(
                request_status_logs.delete().where(
                    request_status_logs.c.request_id == request_id
                )
            )

# -------------------------------------------------------------------
# Initialize DB tables
# -------------------------------------------------------------------
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        print("✅ Database connected. Tables created.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
