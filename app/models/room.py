from sqlalchemy import Column, Integer, String, Boolean, Date, Time, ForeignKey
from datetime import datetime

from app.database.base import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class RoomReservation(Base):
    __tablename__ = "room_reservations"

    id = Column(Integer, primary_key=True, index=True)

    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    weekday = Column(Integer, nullable=True)
    # Pazartesi=0, Salı=1, Çarşamba=2 ...

    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)