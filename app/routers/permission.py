from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.permission import Permission, UserPermission
from app.models.user import User
from app.schemas.permission import PermissionCreate, UserPermissionCreate
from app.core.dependencies import super_admin_required


router = APIRouter()


@router.post("/permissions")
def create_permission(
    data: PermissionCreate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    existing = db.query(Permission).filter(Permission.code == data.code).first()

    if existing:
        raise HTTPException(status_code=400, detail="Bu permission zaten var")

    permission = Permission(
        code=data.code,
        description=data.description,
    )

    db.add(permission)
    db.commit()
    db.refresh(permission)

    return {
        "message": "Permission oluşturuldu",
        "permission_id": permission.id,
        "code": permission.code,
    }


@router.post("/users/{user_id}/permissions")
def assign_permission_to_user(
    user_id: int,
    data: UserPermissionCreate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    permission = db.query(Permission).filter(
        Permission.code == data.permission_code
    ).first()

    if not permission:
        raise HTTPException(status_code=404, detail="Permission bulunamadı")

    existing = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.permission_id == permission.id,
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Bu permission kullanıcıda zaten var")

    user_permission = UserPermission(
        user_id=user.id,
        permission_id=permission.id,
    )

    db.add(user_permission)
    db.commit()

    return {
        "message": "Permission kullanıcıya atandı",
        "user_id": user.id,
        "permission": permission.code,
    }


@router.get("/users/{user_id}/permissions")
def get_user_permissions(
    user_id: int,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    user_permissions = db.query(UserPermission).filter(
        UserPermission.user_id == user.id
    ).all()

    permissions = []

    for user_permission in user_permissions:
        permission = db.query(Permission).filter(
            Permission.id == user_permission.permission_id
        ).first()

        if permission:
            permissions.append(permission.code)

    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "permissions": permissions,
    }


@router.delete("/users/{user_id}/permissions/{permission_code}")
def remove_permission_from_user(
    user_id: int,
    permission_code: str,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    permission = db.query(Permission).filter(
        Permission.code == permission_code
    ).first()

    if not permission:
        raise HTTPException(status_code=404, detail="Permission bulunamadı")

    user_permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.permission_id == permission.id,
    ).first()

    if not user_permission:
        raise HTTPException(status_code=404, detail="Bu permission kullanıcıda yok")

    db.delete(user_permission)
    db.commit()

    return {
        "message": "Permission kullanıcıdan kaldırıldı",
        "user_id": user_id,
        "permission": permission_code,
    }
