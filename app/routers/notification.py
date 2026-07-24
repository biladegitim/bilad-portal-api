import json
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pywebpush import WebPushException, webpush

from app.database.connection import get_db
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.schemas.push_subscription import PushSubscriptionCreate
from app.core.dependencies import get_current_user
from app.core.rbac import get_db_user_from_token


router = APIRouter()
LEAVE_NOTIFICATION_LINKS = ["/leaves", "/my-leaves"]


def get_vapid_public_key():
    return os.getenv("VAPID_PUBLIC_KEY", "")


def get_vapid_private_key():
    return os.getenv("VAPID_PRIVATE_KEY", "")


def notification_payload(title: str, message: str, link: str, badge_count: int):
    return {
        "title": title,
        "body": message,
        "url": link or "/",
        "badgeCount": badge_count,
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
    }


def send_push_to_user(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    link: str,
):
    private_key = get_vapid_private_key()
    public_key = get_vapid_public_key()

    if not private_key or not public_key:
        return

    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()
    payload = notification_payload(title, message, link, unread_count)
    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.user_id == user_id
    ).all()

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims={
                    "sub": os.getenv("VAPID_SUBJECT", "mailto:admin@bilad.local")
                },
            )
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in [404, 410]:
                db.delete(subscription)


@router.get("/push/public-key")
def get_push_public_key():
    public_key = get_vapid_public_key()

    return {
        "enabled": bool(public_key and get_vapid_private_key()),
        "public_key": public_key,
    }


@router.post("/push/subscriptions")
def save_push_subscription(
    data: PushSubscriptionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)
    subscription = db.query(PushSubscription).filter(
        PushSubscription.endpoint == data.endpoint
    ).first()

    if subscription:
        subscription.user_id = user.id
        subscription.p256dh = data.keys.p256dh
        subscription.auth = data.keys.auth
    else:
        subscription = PushSubscription(
            user_id=user.id,
            endpoint=data.endpoint,
            p256dh=data.keys.p256dh,
            auth=data.keys.auth,
        )
        db.add(subscription)

    db.commit()

    return {"message": "Push aboneliği kaydedildi"}


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


@router.get("/notifications/leaves/unread-count")
def get_unread_leave_notification_count(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
        Notification.link.in_(LEAVE_NOTIFICATION_LINKS),
    ).count()

    return {"unread_count": unread_count}


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
        Notification.link.in_(LEAVE_NOTIFICATION_LINKS),
    ).all()

    for notification in notifications:
        notification.is_read = True

    db.commit()

    return {"message": "İzin bildirimleri okundu"}
