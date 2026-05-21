from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime

from app.database.base import Base


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    reason = Column(String, nullable=True)

    status = Column(String, default="pending")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)