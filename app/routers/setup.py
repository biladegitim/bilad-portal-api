import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.security import hash_password
from app.database.connection import SessionLocal
from app.models.user import User


router = APIRouter(prefix="/setup", tags=["setup"])


class SuperAdminSeed(BaseModel):
    email: str
    password: str
    full_name: str = "Bilad Yönetici"


@router.post("/create-super-admin")
def create_super_admin(
    data: SuperAdminSeed,
    x_seed_secret: str | None = Header(default=None),
):
    seed_secret = os.getenv("SEED_SECRET")

    if not seed_secret or x_seed_secret != seed_secret:
        raise HTTPException(status_code=403, detail="Setup secret invalid")

    db = SessionLocal()

    try:
        existing_user = db.query(User).filter(User.email == data.email).first()

        if existing_user:
            existing_user.full_name = data.full_name
            existing_user.hashed_password = hash_password(data.password)
            existing_user.role = "super_admin"
            existing_user.position = existing_user.position or "Yönetici"
            existing_user.is_active = True
            db.commit()

            return {
                "message": "super_admin updated",
                "email": data.email,
            }

        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            role="super_admin",
            position="Yönetici",
            is_active=True,
        )
        db.add(user)
        db.commit()

        return {
            "message": "super_admin created",
            "email": data.email,
        }
    finally:
        db.close()