from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.notification import Notification
from app.core.dependencies import get_current_user
from app.core.rbac import get_db_user_from_token


router = APIRouter()


@router.get("/notifications")
def get_notifications(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    notifications = db.query(Notification).filter(
        Notification.user_id == user.id
    ).order_by(
        Notification.created_at.desc()
    ).limit(20).all()

    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).count()

    return {
        "unread_count": unread_count,
        "notifications": [
            {
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "link": item.link,
                "is_read": item.is_read,
                "created_at": item.created_at,
            }
            for item in notifications
        ],
    }


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı")

    notification.is_read = True
    db.commit()

    return {"message": "Bildirim okundu"}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    notifications = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).all()

    for notification in notifications:
        notification.is_read = True

    db.commit()

    return {"message": "Tüm bildirimler okundu"}


@router.patch("/notifications/read-leaves")
def mark_leave_notifications_read(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    notifications = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
        Notification.link == "/leaves",
    ).all()

    for notification in notifications:
        notification.is_read = True

    db.commit()

    return {"message": "İzin bildirimleri okundu"}
