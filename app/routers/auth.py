from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.core.rbac import normalize_user_role


router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")

    user = normalize_user_role(db, user)

    token = create_access_token(
        data={
            "sub": user.email,
            "role": user.role,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
        },
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "message": "Kullanıcı bilgisi",
        "user": current_user,
    }
