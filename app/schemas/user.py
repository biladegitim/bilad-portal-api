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
    
class UserWorkDaySchedule(BaseModel):
    weekday: int
    is_working: bool = False
    start_time: Optional[time] = None
    end_time: Optional[time] = None


class UserWorkHoursUpdate(BaseModel):
    work_type: str = "full_time"
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    weekly_work_schedule: Optional[list[UserWorkDaySchedule]] = None


class UserAnnualLeaveUpdate(BaseModel):
    annual_leave_days: int
    
