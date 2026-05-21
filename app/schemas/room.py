from pydantic import BaseModel
from typing import Optional
from datetime import date, time


class RoomCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoomReservationCreate(BaseModel):
    room_id: int
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    weekday: int
    start_time: time
    end_time: time


class RoomReservationUpdate(BaseModel):
    room_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    weekday: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None