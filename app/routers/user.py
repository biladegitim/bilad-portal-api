from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.user import (
    UserCreate,
    UserRegister,
    UserRoleUpdate,
    UserOrganizationUpdate,
    UserWorkHoursUpdate,
)
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.models.event import Event
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.permission import UserPermission
from app.models.push_subscription import PushSubscription
from app.models.room import RoomReservation
from app.database.connection import get_db
from app.core.security import hash_password
from app.core.dependencies import get_current_user, super_admin_required
from app.core.rbac import (
    VALID_ROLES,
    get_db_user_from_token,
    normalize_role,
    require_can_manage_user,
    scoped_users_query,
)


router = APIRouter()


def delete_user_completely(db: Session, user: User) -> None:
    user_id = user.id

    db.query(User).filter(User.supervisor_id == user_id).update(
        {User.supervisor_id: None},
        synchronize_session=False,
    )
    db.query(LeaveRequest).filter(LeaveRequest.approved_by == user_id).update(
        {LeaveRequest.approved_by: None},
        synchronize_session=False,
    )

    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(PushSubscription).filter(PushSubscription.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Notification).filter(Notification.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(AttendanceRecord).filter(AttendanceRecord.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(LeaveRequest).filter(LeaveRequest.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Event).filter(Event.created_by == user_id).delete(
        synchronize_session=False
    )
    db.query(RoomReservation).filter(RoomReservation.created_by == user_id).delete(
        synchronize_session=False
    )

    db.delete(user)


def purge_inactive_users(db: Session) -> int:
    inactive_users = db.query(User).filter(User.is_active == False).all()

    for user in inactive_users:
        delete_user_completely(db, user)

    return len(inactive_users)


def serialize_user(user: User):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": normalize_role(user.role),
        "position": user.position,
        "supervisor_id": user.supervisor_id,
        "is_active": user.is_active,
        "work_start_time": str(user.work_start_time) if user.work_start_time else None,
        "work_end_time": str(user.work_end_time) if user.work_end_time else None,
    }


@router.post("/users")
def create_user(
    user: UserCreate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    role = normalize_role(user.role)

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Geçersiz rol")

    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hash_password(user.password),
        role=role,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Kullanıcı oluşturuldu",
        "user_id": new_user.id,
    }


@router.post("/register")
def register_user(
    user: UserRegister,
    db: Session = Depends(get_db),
):
    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hash_password(user.password),
        role="employee",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Kayıt başarılı",
        "user_id": new_user.id,
        "role": new_user.role,
    }


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    role = normalize_role(data.role)

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Geçersiz rol")

    user.role = role

    db.commit()
    db.refresh(user)

    return {
        "message": "Kullanıcı rolü güncellendi",
        "user_id": user.id,
        "email": user.email,
        "new_role": user.role,
    }


@router.patch("/users/{user_id}/organization")
def update_user_organization(
    user_id: int,
    data: UserOrganizationUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor = get_db_user_from_token(db, current_user)
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if normalize_role(actor.role) == "employee":
        raise HTTPException(
            status_code=403,
            detail="Organizasyon bilgisi yönetme yetkiniz yok",
        )

    require_can_manage_user(
        actor,
        user,
        "Bu kullanıcının organizasyon bilgisini yönetemezsiniz",
    )

    if data.supervisor_id:
        supervisor = db.query(User).filter(User.id == data.supervisor_id).first()

        if not supervisor:
            raise HTTPException(status_code=404, detail="Yönetici kullanıcı bulunamadı")

    user.position = data.position
    user.supervisor_id = data.supervisor_id

    db.commit()
    db.refresh(user)

    return {
        "message": "Organizasyon bilgisi güncellendi",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "position": user.position,
            "supervisor_id": user.supervisor_id,
        },
    }


@router.patch("/users/{user_id}/work-hours")
def update_user_work_hours(
    user_id: int,
    data: UserWorkHoursUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor = get_db_user_from_token(db, current_user)
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if normalize_role(actor.role) == "employee":
        raise HTTPException(
            status_code=403,
            detail="Mesai saatleri yönetme yetkiniz yok",
        )

    require_can_manage_user(
        actor,
        user,
        "Bu kullanıcının mesai saatlerini yönetemezsiniz",
    )

    user.work_start_time = data.work_start_time
    user.work_end_time = data.work_end_time

    db.commit()
    db.refresh(user)

    return {
        "message": "Mesai saatleri güncellendi",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "work_start_time": str(user.work_start_time),
            "work_end_time": str(user.work_end_time),
        },
    }


@router.get("/users")
def get_users(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor = get_db_user_from_token(db, current_user)
    users = scoped_users_query(db, actor).order_by(User.id.asc()).all()

    return {
        "users": [
            serialize_user(user)
            for user in users
        ]
    }


@router.delete("/users/inactive")
def delete_inactive_users(
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    deleted_count = purge_inactive_users(db)
    db.commit()

    return {
        "message": "Pasif kullanÄ±cÄ±lar silindi",
        "deleted_count": deleted_count,
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)

    if current_db_user.id == user_id:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    delete_user_completely(db, user)
    db.commit()

    return {
        "message": "Kullanıcı silindi",
        "user_id": user_id,
    }
