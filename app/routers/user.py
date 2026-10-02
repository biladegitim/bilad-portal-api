import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.user import (
    UserCreate,
    UserRegister,
    UserRoleUpdate,
    UserOrganizationUpdate,
    UserWorkHoursUpdate,
    UserAnnualLeaveUpdate,
)
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.models.device_conflict import DeviceConflict
from app.models.event import Event
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.permission import UserPermission
from app.models.push_subscription import PushSubscription
from app.models.room import RoomReservation
from app.database.connection import get_db
from app.core.security import hash_password
from app.core.dependencies import get_current_user, super_admin_required
from app.core.timezone import utc_to_turkey
from app.core.rbac import (
    VALID_ROLES,
    get_db_user_from_token,
    normalize_role,
    require_can_manage_user,
    scoped_users_query,
)
from app.core.work_schedule import parse_time, serialize_weekly_schedule


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
    db.query(DeviceConflict).filter(DeviceConflict.attempted_user_id == user_id).update(
        {DeviceConflict.attempted_user_id: None},
        synchronize_session=False,
    )
    db.query(DeviceConflict).filter(DeviceConflict.matched_user_id == user_id).update(
        {DeviceConflict.matched_user_id: None},
        synchronize_session=False,
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
        "work_type": user.work_type or "full_time",
        "weekly_work_schedule": serialize_weekly_schedule(user),
        "annual_leave_days": user.annual_leave_days or 0,
        "device_id": user.device_id,
        "device_name": user.device_name,
    }


def normalize_weekly_work_schedule(data: UserWorkHoursUpdate) -> list[dict]:
    if data.work_type != "part_time":
        return []

    if not data.weekly_work_schedule:
        raise HTTPException(
            status_code=400,
            detail="Yarı zamanlı çalışma için haftalık gün ve saat bilgisi gerekli",
        )

    schedule = []
    working_days = 0

    for item in data.weekly_work_schedule:
        if item.weekday < 0 or item.weekday > 6:
            raise HTTPException(status_code=400, detail="Geçersiz çalışma günü")

        if not item.is_working:
            schedule.append({
                "weekday": item.weekday,
                "is_working": False,
                "start_time": None,
                "end_time": None,
            })
            continue

        if not item.start_time or not item.end_time:
            raise HTTPException(
                status_code=400,
                detail="Çalışılan günlerde başlangıç ve bitiş saati gerekli",
            )

        if item.end_time <= item.start_time:
            raise HTTPException(
                status_code=400,
                detail="Çalışma bitiş saati başlangıçtan sonra olmalıdır",
            )

        working_days += 1
        schedule.append({
            "weekday": item.weekday,
            "is_working": True,
            "start_time": item.start_time.strftime("%H:%M"),
            "end_time": item.end_time.strftime("%H:%M"),
        })

    if working_days == 0:
        raise HTTPException(
            status_code=400,
            detail="Yarı zamanlı çalışma için en az bir çalışma günü seçilmelidir",
        )

    return sorted(schedule, key=lambda item: item["weekday"])


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

    if data.work_type not in ["full_time", "part_time"]:
        raise HTTPException(status_code=400, detail="Geçersiz çalışma şekli")

    if data.work_type == "full_time":
        has_start_time = data.work_start_time is not None
        has_end_time = data.work_end_time is not None

        if has_start_time != has_end_time:
            raise HTTPException(
                status_code=400,
                detail="Tam zamanlı çalışma için başlangıç ve bitiş saati birlikte girilmelidir",
            )

        if has_start_time and has_end_time and data.work_end_time <= data.work_start_time:
            raise HTTPException(
                status_code=400,
                detail="Mesai bitiş saati başlangıçtan sonra olmalıdır",
            )

        user.work_type = "full_time"
        user.work_start_time = data.work_start_time
        user.work_end_time = data.work_end_time
        user.weekly_work_schedule = None
    else:
        schedule = normalize_weekly_work_schedule(data)
        first_working_day = next(item for item in schedule if item["is_working"])

        user.work_type = "part_time"
        user.work_start_time = parse_time(first_working_day["start_time"])
        user.work_end_time = parse_time(first_working_day["end_time"])
        user.weekly_work_schedule = json.dumps(schedule, ensure_ascii=False)

    db.commit()
    db.refresh(user)

    return {
        "message": "Mesai saatleri güncellendi",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "work_start_time": str(user.work_start_time) if user.work_start_time else None,
            "work_end_time": str(user.work_end_time) if user.work_end_time else None,
            "work_type": user.work_type,
            "weekly_work_schedule": serialize_weekly_schedule(user),
        },
    }


@router.patch("/users/{user_id}/annual-leave")
def update_user_annual_leave(
    user_id: int,
    data: UserAnnualLeaveUpdate,
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
            detail="Yıllık izin hakkı yönetme yetkiniz yok",
        )

    require_can_manage_user(
        actor,
        user,
        "Bu kullanıcının yıllık izin hakkını yönetemezsiniz",
    )

    if data.annual_leave_days < 0:
        raise HTTPException(
            status_code=400,
            detail="Yıllık izin gün sayısı negatif olamaz",
        )

    user.annual_leave_days = data.annual_leave_days

    db.commit()
    db.refresh(user)

    return {
        "message": "Yıllık izin hakkı güncellendi",
        "user": serialize_user(user),
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


@router.get("/users/device-conflicts")
def get_device_conflicts(
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    conflicts = db.query(DeviceConflict).order_by(
        DeviceConflict.created_at.desc()
    ).limit(50).all()

    user_ids = {
        user_id
        for conflict in conflicts
        for user_id in (conflict.attempted_user_id, conflict.matched_user_id)
        if user_id
    }
    users_by_id = {
        user.id: user
        for user in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    return {
        "conflicts": [
            {
                "id": conflict.id,
                "attempted_user_id": conflict.attempted_user_id,
                "matched_user_id": conflict.matched_user_id,
                "attempted_user_name": users_by_id.get(conflict.attempted_user_id).full_name
                if conflict.attempted_user_id in users_by_id
                else "Silinmiş kullanıcı",
                "matched_user_name": users_by_id.get(conflict.matched_user_id).full_name
                if conflict.matched_user_id in users_by_id
                else None,
                "attempted_device_name": conflict.attempted_device_name,
                "expected_device_name": conflict.expected_device_name,
                "attempted_device_id": conflict.attempted_device_id,
                "expected_device_id": conflict.expected_device_id,
                "created_at": utc_to_turkey(conflict.created_at),
            }
            for conflict in conflicts
        ]
    }


@router.delete("/users/{user_id}/device-binding")
def reset_user_device_binding(
    user_id: int,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    user.device_id = None
    user.device_name = None

    db.commit()
    db.refresh(user)

    return {
        "message": "Cihaz eşleşmesi sıfırlandı",
        "user": serialize_user(user),
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
