from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, LargeBinary
from datetime import datetime
from sqlalchemy.orm import deferred

from app.database.base import Base


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    reason = Column(String, nullable=True)
    leave_type = Column(String, default="standard", nullable=False)
    leave_period = Column(String, nullable=True)

    report_document = deferred(Column(LargeBinary, nullable=True))
    report_filename = Column(String, nullable=True)
    report_content_type = Column(String, nullable=True)

    status = Column(String, default="pending")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
