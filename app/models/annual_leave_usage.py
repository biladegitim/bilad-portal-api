from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint

from app.database.base import Base


class AnnualLeaveUsageAdjustment(Base):
    __tablename__ = "annual_leave_usage_adjustments"
    __table_args__ = (
        UniqueConstraint("user_id", "year", name="uq_annual_leave_usage_user_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    adjustment_days = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
