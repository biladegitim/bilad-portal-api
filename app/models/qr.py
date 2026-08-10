from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import timedelta
import uuid

from app.database.base import Base
from app.core.timezone import utc_now


class QRToken(Base):
    __tablename__ = "qr_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    expires_at = Column(DateTime, default=lambda: utc_now() + timedelta(seconds=15))
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
