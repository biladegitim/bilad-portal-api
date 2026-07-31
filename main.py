import os

import asyncio
import contextlib

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

load_dotenv()

from app.database.connection import SessionLocal, engine
from app.database.base import Base

from app.models.user import User
from app.models.leave import LeaveRequest
from app.models.qr import QRToken
from app.models.attendance import AttendanceRecord
from app.models.menu import Menu
from app.models.event import Event
from app.models.room import Room, RoomReservation
from app.models.permission import Permission, UserPermission
from app.models.push_subscription import PushSubscription

from app.routers.event import router as event_router, send_due_event_reminders
from app.routers.attendance import router as attendance_router
from app.routers.user import router as user_router
from app.routers.auth import router as auth_router
from app.routers.leave import router as leave_router
from app.routers.menu import router as menu_router
from app.routers.room import router as room_router
from app.routers.permission import router as permission_router
from app.routers.home import router as home_router
from app.routers.profile import router as profile_router
from app.routers.notification import router as notification_router

Base.metadata.create_all(bind=engine)

with engine.begin() as connection:
    connection.execute(text(
        "ALTER TABLE room_reservations "
        "ADD COLUMN IF NOT EXISTS status VARCHAR NOT NULL DEFAULT 'approved'"
    ))
    connection.execute(text(
        "ALTER TABLE room_reservations "
        "ADD COLUMN IF NOT EXISTS approved_by INTEGER"
    ))
    connection.execute(text(
        "ALTER TABLE room_reservations "
        "ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP"
    ))
    connection.execute(text(
        "ALTER TABLE rooms "
        "ADD COLUMN IF NOT EXISTS floor VARCHAR"
    ))
    connection.execute(text(
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS annual_leave_days INTEGER NOT NULL DEFAULT 0"
    ))
    connection.execute(text(
        "ALTER TABLE leave_requests "
        "ADD COLUMN IF NOT EXISTS leave_type VARCHAR NOT NULL DEFAULT 'standard'"
    ))
    connection.execute(text(
        "ALTER TABLE events "
        "ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMP"
    ))

app = FastAPI(title="Bilad Portal API")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://192.168.1.116:3000",
    ).split(",")
    if origin.strip()
]

upload_root = os.getenv("UPLOAD_ROOT", "uploads")
os.makedirs(upload_root, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=upload_root),
    name="uploads",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(auth_router)
app.include_router(leave_router)
app.include_router(attendance_router)
app.include_router(menu_router)
app.include_router(event_router)
app.include_router(room_router)
app.include_router(permission_router)
app.include_router(home_router)
app.include_router(profile_router)
app.include_router(notification_router)


async def event_reminder_loop():
    while True:
        db = SessionLocal()

        try:
            send_due_event_reminders(db)
        except Exception:
            db.rollback()
        finally:
            db.close()

        await asyncio.sleep(60)


@app.on_event("startup")
async def start_event_reminder_loop():
    app.state.event_reminder_task = asyncio.create_task(event_reminder_loop())


@app.on_event("shutdown")
async def stop_event_reminder_loop():
    task = getattr(app.state, "event_reminder_task", None)

    if task:
        task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/")
def home():
    return {
        "message": "Bilad Portal API çalışıyor"
    }


@app.get("/db-test")
def db_test():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database();")
        )

        database_name = result.scalar()

    return {
        "database": database_name,
        "status": "connected"
    }
