from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.room import Room, RoomReservation
from app.schemas.room import (
    RoomCreate,
    RoomUpdate,
    RoomReservationCreate,
    RoomReservationUpdate,
)
from app.core.dependencies import get_current_user, super_admin_required
from app.core.rbac import get_db_user_from_token, normalize_role


router = APIRouter()


def serialize_reservation(db: Session, reservation: RoomReservation):
    room = db.query(Room).filter(Room.id == reservation.room_id).first()

    return {
        "reservation_id": reservation.id,
        "room_id": reservation.room_id,
        "room_name": room.name if room else "Bilinmiyor",
        "title": reservation.title,
        "description": reservation.description,
        "start_time": str(reservation.start_time),
        "end_time": str(reservation.end_time),
        "start_date": str(reservation.start_date),
        "end_date": str(reservation.end_date),
        "weekday": reservation.weekday,
        "created_by": reservation.created_by,
    }


def find_reservation_conflict(
    db: Session,
    room_id: int,
    weekday: int,
    start_date,
    end_date,
    start_time,
    end_time,
    exclude_id: int | None = None,
):
    query = db.query(RoomReservation).filter(
        RoomReservation.room_id == room_id,
        RoomReservation.weekday == weekday,
        RoomReservation.start_date <= end_date,
        RoomReservation.end_date >= start_date,
        RoomReservation.start_time < end_time,
        RoomReservation.end_time > start_time,
    )

    if exclude_id is not None:
        query = query.filter(RoomReservation.id != exclude_id)

    return query.first()


@router.post("/rooms")
def create_room(
    data: RoomCreate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    room = Room(
        name=data.name,
        description=data.description,
        is_active=True,
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return {
        "message": "Mekan oluşturuldu",
        "room_id": room.id,
    }


@router.get("/rooms")
def get_rooms(db: Session = Depends(get_db)):
    rooms = db.query(Room).filter(
        Room.is_active == True
    ).order_by(Room.name.asc()).all()

    return {
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "is_active": room.is_active,
            }
            for room in rooms
        ]
    }


@router.patch("/rooms/{room_id}")
def update_room(
    room_id: int,
    data: RoomUpdate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    room = db.query(Room).filter(Room.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Mekan bulunamadı")

    if data.name is not None:
        room.name = data.name

    if data.description is not None:
        room.description = data.description

    if data.is_active is not None:
        room.is_active = data.is_active

    db.commit()
    db.refresh(room)

    return {
        "message": "Mekan güncellendi",
        "room": {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "is_active": room.is_active,
        },
    }


@router.delete("/rooms/{room_id}")
def delete_room(
    room_id: int,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    room = db.query(Room).filter(Room.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Mekan bulunamadı")

    db.delete(room)
    db.commit()

    return {
        "message": "Mekan silindi",
        "room_id": room_id,
    }


@router.post("/room-reservations")
def create_room_reservation(
    data: RoomReservationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    room = db.query(Room).filter(
        Room.id == data.room_id,
        Room.is_active == True,
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="Mekan bulunamadı")

    conflict = find_reservation_conflict(
        db,
        data.room_id,
        data.weekday,
        data.start_date,
        data.end_date,
        data.start_time,
        data.end_time,
    )

    if conflict:
        raise HTTPException(status_code=400, detail="Bu mekan seçilen saat aralığında dolu")

    reservation = RoomReservation(
        room_id=data.room_id,
        title=data.title,
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        weekday=data.weekday,
        start_time=data.start_time,
        end_time=data.end_time,
        created_by=user.id,
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return {
        "message": "Rezervasyon oluşturuldu",
        "reservation_id": reservation.id,
    }


@router.patch("/room-reservations/{reservation_id}")
def update_room_reservation(
    reservation_id: int,
    data: RoomReservationUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)
    reservation = db.query(RoomReservation).filter(
        RoomReservation.id == reservation_id
    ).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")

    is_admin = normalize_role(current_db_user.role) in ["admin", "super_admin"]

    if not is_admin and reservation.created_by != current_db_user.id:
        raise HTTPException(status_code=403, detail="Bu rezervasyonu düzenleme yetkiniz yok")

    new_room_id = data.room_id if data.room_id is not None else reservation.room_id
    new_weekday = data.weekday if data.weekday is not None else reservation.weekday
    new_start_date = data.start_date if data.start_date is not None else reservation.start_date
    new_end_date = data.end_date if data.end_date is not None else reservation.end_date
    new_start_time = data.start_time if data.start_time is not None else reservation.start_time
    new_end_time = data.end_time if data.end_time is not None else reservation.end_time

    room = db.query(Room).filter(
        Room.id == new_room_id,
        Room.is_active == True,
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="Mekan bulunamadı")

    conflict = find_reservation_conflict(
        db,
        new_room_id,
        new_weekday,
        new_start_date,
        new_end_date,
        new_start_time,
        new_end_time,
        exclude_id=reservation_id,
    )

    if conflict:
        raise HTTPException(status_code=400, detail="Bu mekan seçilen saat aralığında dolu")

    reservation.room_id = new_room_id
    reservation.weekday = new_weekday
    reservation.start_date = new_start_date
    reservation.end_date = new_end_date
    reservation.start_time = new_start_time
    reservation.end_time = new_end_time

    if data.title is not None:
        reservation.title = data.title

    if data.description is not None:
        reservation.description = data.description

    db.commit()
    db.refresh(reservation)

    return {
        "message": "Rezervasyon güncellendi",
        "reservation_id": reservation.id,
    }


@router.delete("/room-reservations/{reservation_id}")
def delete_room_reservation(
    reservation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)
    reservation = db.query(RoomReservation).filter(
        RoomReservation.id == reservation_id
    ).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")

    is_admin = normalize_role(current_db_user.role) in ["admin", "super_admin"]

    if not is_admin and reservation.created_by != current_db_user.id:
        raise HTTPException(status_code=403, detail="Bu rezervasyonu silme yetkiniz yok")

    db.delete(reservation)
    db.commit()

    return {
        "message": "Rezervasyon silindi",
        "reservation_id": reservation_id,
    }


@router.get("/room-reservations/weekly")
def get_weekly_room_reservations(db: Session = Depends(get_db)):
    reservations = db.query(RoomReservation).order_by(
        RoomReservation.weekday.asc(),
        RoomReservation.start_time.asc(),
    ).all()

    weekday_names = {
        0: "Pazartesi",
        1: "Salı",
        2: "Çarşamba",
        3: "Perşembe",
        4: "Cuma",
        5: "Cumartesi",
        6: "Pazar",
    }

    weekly_schedule = {
        day_name: []
        for day_name in weekday_names.values()
    }

    for reservation in reservations:
        day_name = weekday_names.get(reservation.weekday, "Bilinmiyor")
        weekly_schedule.setdefault(day_name, []).append(
            serialize_reservation(db, reservation)
        )

    return {"weekly_schedule": weekly_schedule}


@router.get("/room-reservations/by-date")
def get_room_reservations_by_date(
    selected_date: date,
    db: Session = Depends(get_db),
):
    weekday = selected_date.weekday()

    reservations = db.query(RoomReservation).filter(
        RoomReservation.weekday == weekday,
        RoomReservation.start_date <= selected_date,
        RoomReservation.end_date >= selected_date,
    ).order_by(RoomReservation.start_time.asc()).all()

    if not reservations:
        return {
            "date": str(selected_date),
            "message": "Bu tarihte planlanmış mekan kullanımı yok",
            "reservations": [],
        }

    return {
        "date": str(selected_date),
        "reservations": [
            serialize_reservation(db, reservation)
            for reservation in reservations
        ],
    }
