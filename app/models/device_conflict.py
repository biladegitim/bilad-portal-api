from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database.base import Base


class DeviceConflict(Base):
    __tablename__ = "device_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    attempted_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    matched_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    attempted_device_id = Column(String, nullable=False)
    attempted_device_name = Column(String, nullable=True)
    expected_device_id = Column(String, nullable=True)
    expected_device_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
