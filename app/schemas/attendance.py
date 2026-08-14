from pydantic import BaseModel
from typing import Optional


class AttendanceScan(BaseModel):
    token: str
    device_id: str
    device_name: Optional[str] = None
