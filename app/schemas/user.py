from pydantic import BaseModel
from typing import Optional
from datetime import time


class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str
    role: Optional[str] = "employee"


class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str


class UserRoleUpdate(BaseModel):
    role: str
class UserOrganizationUpdate(BaseModel):

    position: str
    supervisor_id: Optional[int] = None
    
class UserWorkHoursUpdate(BaseModel):
    work_start_time: time
    work_end_time: time
    
