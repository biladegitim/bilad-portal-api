from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime

from app.database.base import Base


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    record_type = Column(String, nullable=False)
    # check_in veya check_out

    record_time = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="dynamic_qr")

    created_at = Column(DateTime, default=datetime.utcnow)