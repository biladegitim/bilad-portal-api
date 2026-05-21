import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.permission import Permission, UserPermission
from app.core.dependencies import get_current_user
from app.core.rbac import get_db_user_from_token, normalize_role
from app.core.security import verify_password, hash_password


router = APIRouter()


def get_upload_root() -> Path:
    return Path(os.getenv("UPLOAD_ROOT", "uploads"))


def profile_photo_public_path(file_name: str) -> str:
    return f"/uploads/profile_photos/{file_name}"


def profile_photo_file_path(public_path: str | None) -> Path | None:
    if not public_path or not public_path.startswith("/uploads/"):
        return None

    relative_path = public_path.removeprefix("/uploads/")
    return get_upload_root() / relative_path


def remove_profile_photo_file(public_path: str | None) -> None:
    file_path = profile_photo_file_path(public_path)

    if file_path and file_path.exists() and file_path.is_file():
        file_path.unlink()


@router.get("/profile")
def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "position": user.position,
        "profile_photo": user.profile_photo,
    }


@router.patch("/profile/change-password")
def change_password(
    data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Mevcut ve yeni şifre gerekli")

    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Mevcut şifre yanlış")

    user.hashed_password = hash_password(new_password)
    db.commit()

    return {"message": "Şifre başarıyla değiştirildi"}


@router.post("/profile/upload-photo")
def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)
    upload_dir = get_upload_root() / "profile_photos"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_extension = Path(file.filename or "profile.jpg").suffix.lower() or ".jpg"
    file_name = f"user_{user.id}{file_extension}"
    file_path = upload_dir / file_name

    remove_profile_photo_file(user.profile_photo)

    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())

    user.profile_photo = profile_photo_public_path(file_name)

    db.commit()
    db.refresh(user)

    return {
        "message": "Profil fotoğrafı yüklendi",
        "profile_photo": user.profile_photo,
    }


@router.delete("/profile/remove-photo")
def remove_profile_photo(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)
    remove_profile_photo_file(user.profile_photo)
    user.profile_photo = None

    db.commit()

    return {"message": "Profil fotoğrafı kaldırıldı"}


@router.get("/profile/access")
def get_profile_access(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    user_permissions = (
        db.query(Permission)
        .join(UserPermission, UserPermission.permission_id == Permission.id)
        .filter(UserPermission.user_id == user.id)
        .all()
    )

    role = normalize_role(user.role)

    return {
        "role": role,
        "is_admin": role in ["admin", "super_admin"],
        "permissions": [
            permission.code for permission in user_permissions
        ],
    }