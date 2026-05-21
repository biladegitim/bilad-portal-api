from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.leave import LeaveRequest
from app.models.user import User
from app.models.notification import Notification
from app.schemas.leave import LeaveCreate
from app.core.dependencies import get_current_user
from app.core.rbac import (
    can_manage_user,
    get_db_user_from_token,
    normalize_role,
    scoped_user_ids,
)


router = APIRouter()


def serialize_leave(db: Session, leave: LeaveRequest):
    leave_user = db.query(User).filter(User.id == leave.user_id).first()

    return {
        "id": leave.id,
        "user_id": leave.user_id,
        "user_name": leave_user.full_name if leave_user else "Bilinmiyor",
        "start_time": leave.start_time,
        "end_time": leave.end_time,
        "reason": leave.reason,
        "status": leave.status,
        "approved_by": leave.approved_by,
    }


def add_notification(db: Session, user_id: int, title: str, message: str, link: str):
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link,
    ))


def require_leave_manager(db: Session, actor: User, leave: LeaveRequest) -> User:
    leave_user = db.query(User).filter(User.id == leave.user_id).first()

    if not leave_user:
        raise HTTPException(status_code=404, detail="İzin sahibi kullanıcı bulunamadı")

    if not can_manage_user(actor, leave_user) or actor.id == leave_user.id:
        raise HTTPException(
            status_code=403,
            detail="Bu kullanıcının iznini yönetemezsiniz",
        )

    return leave_user


@router.post("/leave-requests")
def create_leave_request(
    data: LeaveCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)

    leave_request = LeaveRequest(
        user_id=current_db_user.id,
        start_time=data.start_time,
        end_time=data.end_time,
        reason=data.reason,
        status="pending",
    )

    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)

    notify_users = []

    if current_db_user.supervisor_id:
        supervisor = db.query(User).filter(
            User.id == current_db_user.supervisor_id
        ).first()

        if supervisor:
            notify_users.append(supervisor)

    super_admins = db.query(User).filter(User.role == "super_admin").all()
    existing_ids = [user.id for user in notify_users]

    for super_admin in super_admins:
        if super_admin.id not in existing_ids:
            notify_users.append(super_admin)

    for notify_user in notify_users:
        add_notification(
            db,
            notify_user.id,
            "Yeni İzin Talebi",
            f"{current_db_user.full_name} yeni bir izin talebi oluşturdu.",
            "/leaves",
        )

    db.commit()

    return {
        "message": "İzin talebi oluşturuldu",
        "leave_request_id": leave_request.id,
    }


@router.get("/my-leaves")
def get_my_leaves(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    leaves = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user.id
    ).order_by(
        LeaveRequest.start_time.desc()
    ).all()

    return {
        "leaves": [
            {
                "id": leave.id,
                "start_time": leave.start_time,
                "end_time": leave.end_time,
                "reason": leave.reason,
                "status": leave.status,
                "approved_by": leave.approved_by,
            }
            for leave in leaves
        ]
    }


@router.get("/team-leaves")
def get_team_leaves(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)

    if normalize_role(current_db_user.role) == "employee":
        raise HTTPException(status_code=403, detail="İzinleri görüntüleme yetkiniz yok")

    user_ids = scoped_user_ids(db, current_db_user)

    leaves = db.query(LeaveRequest).filter(
        LeaveRequest.user_id.in_(user_ids or [-1])
    ).order_by(
        LeaveRequest.start_time.desc()
    ).all()

    return {
        "leaves": [
            serialize_leave(db, leave)
            for leave in leaves
        ]
    }


@router.patch("/leave-requests/{leave_id}/approve")
def approve_leave_request(
    leave_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()

    if not leave:
        raise HTTPException(status_code=404, detail="İzin talebi bulunamadı")

    leave_user = require_leave_manager(db, current_db_user, leave)
    leave.status = "approved"
    leave.approved_by = current_db_user.id

    add_notification(
        db,
        leave_user.id,
        "İzin Talebi Onaylandı",
        "İzin talebiniz onaylandı.",
        "/my-leaves",
    )

    db.commit()
    db.refresh(leave)

    return {
        "message": "İzin onaylandı",
        "leave_id": leave.id,
        "status": leave.status,
    }


@router.patch("/leave-requests/{leave_id}/reject")
def reject_leave_request(
    leave_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()

    if not leave:
        raise HTTPException(status_code=404, detail="İzin talebi bulunamadı")

    leave_user = require_leave_manager(db, current_db_user, leave)
    leave.status = "rejected"
    leave.approved_by = current_db_user.id

    add_notification(
        db,
        leave_user.id,
        "İzin Talebi Reddedildi",
        "İzin talebiniz reddedildi.",
        "/my-leaves",
    )

    db.commit()
    db.refresh(leave)

    return {
        "message": "İzin reddedildi",
        "leave_id": leave.id,
        "status": leave.status,
    }


@router.delete("/leave-requests/{leave_id}")
def delete_leave_request(
    leave_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()

    if not leave:
        raise HTTPException(status_code=404, detail="İzin talebi bulunamadı")

    require_leave_manager(db, current_db_user, leave)

    db.delete(leave)
    db.commit()

    return {
        "message": "İzin talebi silindi",
        "leave_id": leave_id,
    }


@router.get("/leaves/today-approved")
def get_today_approved_leaves(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    leaves = db.query(LeaveRequest).filter(
        LeaveRequest.status == "approved",
        LeaveRequest.start_time <= today_end,
        LeaveRequest.end_time >= today_start,
    ).order_by(
        LeaveRequest.start_time.asc()
    ).all()

    result = []

    for leave in leaves:
        user = db.query(User).filter(User.id == leave.user_id).first()
        result.append({
            "leave_id": leave.id,
            "user_id": leave.user_id,
            "full_name": user.full_name if user else "Bilinmiyor",
            "start_time": leave.start_time,
            "end_time": leave.end_time,
            "reason": leave.reason,
        })

    return {
        "date": str(today),
        "approved_leaves": result,
    }
