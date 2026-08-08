from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.timezone import local_day_bounds, turkey_now, turkey_today
from app.models.event import Event
from app.models.menu import Menu
from app.models.leave import LeaveRequest
from app.models.user import User

router = APIRouter()


@router.get("/home")
def get_home_data(db: Session = Depends(get_db)):
    today = turkey_today()
    today_start, today_end = local_day_bounds(today)

    upcoming_events = db.query(Event).filter(
        Event.start_time >= turkey_now()
    ).order_by(
        Event.start_time.asc()
    ).limit(5).all()

    today_menu = db.query(Menu).filter(
        Menu.menu_date == today
    ).first()

    approved_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.status == "approved",
        LeaveRequest.start_time <= today_end,
        LeaveRequest.end_time >= today_start
    ).order_by(
        LeaveRequest.start_time.asc()
    ).all()

    leave_list = []

    for leave in approved_leaves:
        user = db.query(User).filter(
            User.id == leave.user_id
        ).first()

        leave_list.append({
            "leave_id": leave.id,
            "full_name": user.full_name if user else "Bilinmiyor",
            "start_time": leave.start_time,
            "end_time": leave.end_time,
            "reason": leave.reason,
            "leave_type": "excuse" if leave.leave_type == "standard" else leave.leave_type,
        })

    return {
        "upcoming_events": [
            {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "location": event.location,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "category": event.category,
                "icon": event.icon
            }
            for event in upcoming_events
        ],
        "today_menu": {
            "menu_date": today_menu.menu_date,
            "content": today_menu.content
        } if today_menu else None,
        "today_approved_leaves": leave_list
    }
