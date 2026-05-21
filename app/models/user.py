from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Time
from datetime import datetime

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="employee")
    profile_photo = Column(String, nullable=True)

    position = Column(String, default="unassigned")
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    work_start_time = Column(Time, nullable=True)
    work_end_time = Column(Time, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    device_id = Column(String, nullable=True)
