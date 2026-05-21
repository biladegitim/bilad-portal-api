from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class LeaveCreate(BaseModel):

    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None