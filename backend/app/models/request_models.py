# request_models.py
from pydantic import BaseModel

# -----------------------------
# CREATE SERVER REQUEST
# -----------------------------
class DeployRequest(BaseModel):
    device_id: str
    instance_name: str
    user: str


# -----------------------------
# DESTROY SERVER REQUEST
# -----------------------------
class DestroyRequest(BaseModel):
    device_id: str
    instance_name: str   # still needed for folder path
    user: str
