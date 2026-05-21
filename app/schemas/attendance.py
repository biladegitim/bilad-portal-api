from pydantic import BaseModel


class AttendanceScan(BaseModel):
    token: str
    device_id: str