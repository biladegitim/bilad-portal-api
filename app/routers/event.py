from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, date, time

from app.database.connection import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.core.dependencies import get_current_user

router = APIRouter()


@router.get("/events")
def get_events(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.start_time.asc()).all()

    return {
        "events": [
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
            for event in events
        ]
    }


@router.post("/events")
def create_event(
    data: EventCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == current_user["sub"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    event = Event(
        title=data.title,
        description=data.description,
        location=data.location,
        start_time=data.start_time,
        end_time=data.end_time,
        category=data.category,
        icon=data.icon,
        created_by=user.id
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "message": "Etkinlik oluşturuldu",
        "event_id": event.id
    }


@router.patch("/events/{event_id}")
def update_event(
    event_id: int,
    data: EventUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Etkinlik bulunamadı")

    if data.title is not None:
        event.title = data.title

    if data.description is not None:
        event.description = data.description

    if data.location is not None:
        event.location = data.location

    if data.start_time is not None:
        event.start_time = data.start_time

    if data.end_time is not None:
        event.end_time = data.end_time

    if data.category is not None:
        event.category = data.category

    if data.icon is not None:
        event.icon = data.icon

    db.commit()
    db.refresh(event)

    return {
        "message": "Etkinlik güncellendi",
        "event_id": event.id
    }


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Etkinlik bulunamadı")

    db.delete(event)
    db.commit()

    return {
        "message": "Etkinlik silindi",
        "event_id": event_id
    }


@router.get("/events/upcoming")
def get_upcoming_events(db: Session = Depends(get_db)):
    events = db.query(Event).filter(
        Event.start_time >= datetime.utcnow()
    ).order_by(Event.start_time.asc()).limit(10).all()

    return {
        "events": [
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
            for event in events
        ]
    }


@router.get("/events/by-date")
def get_events_by_date(
    selected_date: date = Query(...),
    db: Session = Depends(get_db),
):
    day_start = datetime.combine(selected_date, time.min)
    day_end = datetime.combine(selected_date, time.max)

    events = db.query(Event).filter(
        Event.start_time >= day_start,
        Event.start_time <= day_end
    ).order_by(Event.start_time.asc()).all()

    if not events:
        return {
            "date": str(selected_date),
            "message": "Planlanmış bir etkinlik yok",
            "events": []
        }

    return {
        "date": str(selected_date),
        "events": [
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
            for event in events
        ]
    }


@router.get("/events/month")
def get_events_by_month(
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    month_start = datetime(year, month, 1)

    if month == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month + 1, 1)

    events = db.query(Event).filter(
        Event.start_time >= month_start,
        Event.start_time < month_end
    ).order_by(Event.start_time.asc()).all()

    return {
        "year": year,
        "month": month,
        "days": [
            {
                "date": str(event.start_time.date()),
                "event_id": event.id,
                "title": event.title,
                "category": event.category,
                "icon": event.icon,
                "start_time": event.start_time
            }
            for event in events
        ]
    }
