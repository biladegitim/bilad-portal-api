from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, super_admin_required
from app.core.permission import has_permission
from app.core.rbac import get_db_user_from_token, normalize_role
from app.database.connection import get_db
from app.models.notification import Notification
from app.models.permission import Permission, UserPermission
from app.models.room import Room, RoomReservation
from app.models.user import User
from app.routers.notification import send_push_to_user
from app.schemas.room import (
    RoomCreate,
    RoomReservationCreate,
    RoomReservationUpdate,
    RoomUpdate,
)


router = APIRouter()
ROOM_APPROVE_PERMISSION = "room.approve"


def can_approve_rooms(db: Session, user: User) -> bool:
    role = normalize_role(user.role)

    return (
        role in ["admin", "super_admin"]
        or has_permission(db, user.id, ROOM_APPROVE_PERMISSION)
    )


def add_notification(db: Session, user_id: int, title: str, message: str, link: str):
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link,
    ))
    db.flush()
    send_push_to_user(db, user_id, title, message, link)


def room_approvers(db: Session, creator_id: int) -> list[User]:
    permission = db.query(Permission).filter(
        Permission.code == ROOM_APPROVE_PERMISSION
    ).first()
    users_by_id: dict[int, User] = {}

    role_users = db.query(User).filter(
        User.is_active == True,
        User.role.in_(["admin", "super_admin"]),
        User.id != creator_id,
    ).all()

    for user in role_users:
        users_by_id[user.id] = user

    if permission:
        permission_users = (
            db.query(User)
            .join(UserPermission, UserPermission.user_id == User.id)
            .filter(
                UserPermission.permission_id == permission.id,
                User.is_active == True,
                User.id != creator_id,
            )
            .all()
        )

        for user in permission_users:
            users_by_id[user.id] = user

    return list(users_by_id.values())


def serialize_reservation(db: Session, reservation: RoomReservation):
    room = db.query(Room).filter(Room.id == reservation.room_id).first()
    creator = db.query(User).filter(User.id == reservation.created_by).first()

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
        "created_by_name": creator.full_name if creator else "Bilinmiyor",
        "status": reservation.status,
        "approved_by": reservation.approved_by,
        "approved_at": reservation.approved_at,
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
        RoomReservation.status == "approved",
        RoomReservation.start_date <= end_date,
        RoomReservation.end_date >= start_date,
        RoomReservation.start_time < end_time,
        RoomReservation.end_time > start_time,
    )

    if exclude_id is not None:
        query = query.filter(RoomReservation.id != exclude_id)

    return query.first()


def ensure_room_exists(db: Session, room_id: int):
    room = db.query(Room).filter(
        Room.id == room_id,
        Room.is_active == True,
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="Mekan bulunamadı")

    return room


def selected_weekdays_from_create(data: RoomReservationCreate):
    selected_weekdays = data.weekdays if data.weekdays is not None else [data.weekday]
    selected_weekdays = [weekday for weekday in selected_weekdays if weekday is not None]

    if not selected_weekdays:
        raise HTTPException(status_code=400, detail="En az bir gün seçmelisiniz")

    invalid_weekdays = [weekday for weekday in selected_weekdays if weekday < 0 or weekday > 6]

    if invalid_weekdays:
        raise HTTPException(status_code=400, detail="Geçersiz gün seçimi")

    return list(dict.fromkeys(selected_weekdays))


@router.post("/rooms")
def create_room(
    data: RoomCreate,
    current_user: dict = Depends(super_admin_required),
    db: Session = Depends(get_db),
):
    room = Room(
        name=data.name,
        description=data.description,
        floor=data.floor,
        is_active=True,
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return {
        "message": "Mekan oluşturuldu",
        "room_id": room.id,
        "room": {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "floor": room.floor,
            "floor_name": room.floor,
            "is_active": room.is_active,
        },
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
                "floor": room.floor,
                "floor_name": room.floor,
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

    if data.floor is not None:
        room.floor = data.floor

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
            "floor": room.floor,
            "floor_name": room.floor,
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
    ensure_room_exists(db, data.room_id)
    selected_weekdays = selected_weekdays_from_create(data)

    for weekday in selected_weekdays:
        conflict = find_reservation_conflict(
            db,
            data.room_id,
            weekday,
            data.start_date,
            data.end_date,
            data.start_time,
            data.end_time,
        )

        if conflict:
            raise HTTPException(status_code=400, detail="Bu mekan seçilen saat aralığında dolu")

    reservations = []

    for weekday in selected_weekdays:
        reservation = RoomReservation(
            room_id=data.room_id,
            title=data.title,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
            weekday=weekday,
            start_time=data.start_time,
            end_time=data.end_time,
            created_by=user.id,
            status="pending",
        )
        db.add(reservation)
        reservations.append(reservation)

    db.flush()

    for approver in room_approvers(db, user.id):
        add_notification(
            db,
            approver.id,
            "Yeni Mekan Program Talebi",
            f"{user.full_name} yeni bir mekan program talebi oluşturdu.",
            "/rooms",
        )

    db.commit()

    for reservation in reservations:
        db.refresh(reservation)

    return {
        "message": "Program talebi oluşturuldu",
        "reservation_ids": [reservation.id for reservation in reservations],
        "status": "pending",
    }


@router.get("/room-reservations/pending")
def get_pending_room_reservations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user_from_token(db, current_user)

    if not can_approve_rooms(db, user):
        raise HTTPException(status_code=403, detail="Mekan taleplerini görüntüleme yetkiniz yok")

    reservations = db.query(RoomReservation).filter(
        RoomReservation.status == "pending"
    ).order_by(
        RoomReservation.start_date.asc(),
        RoomReservation.start_time.asc(),
    ).all()

    return {
        "reservations": [
            serialize_reservation(db, reservation)
            for reservation in reservations
        ]
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

    is_approver = can_approve_rooms(db, current_db_user)

    if not is_approver and reservation.created_by != current_db_user.id:
        raise HTTPException(status_code=403, detail="Bu rezervasyonu düzenleme yetkiniz yok")

    if not is_approver and reservation.status == "approved":
        raise HTTPException(status_code=403, detail="Onaylı programı düzenleme yetkiniz yok")

    new_room_id = data.room_id if data.room_id is not None else reservation.room_id
    new_weekday = data.weekday if data.weekday is not None else reservation.weekday
    new_start_date = data.start_date if data.start_date is not None else reservation.start_date
    new_end_date = data.end_date if data.end_date is not None else reservation.end_date
    new_start_time = data.start_time if data.start_time is not None else reservation.start_time
    new_end_time = data.end_time if data.end_time is not None else reservation.end_time

    ensure_room_exists(db, new_room_id)

    if reservation.status == "approved":
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

    if not is_approver:
        reservation.status = "pending"
        reservation.approved_by = None
        reservation.approved_at = None

    db.commit()
    db.refresh(reservation)

    return {
        "message": "Program talebi güncellendi",
        "reservation_id": reservation.id,
        "status": reservation.status,
    }


@router.patch("/room-reservations/{reservation_id}/approve")
def approve_room_reservation(
    reservation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)

    if not can_approve_rooms(db, current_db_user):
        raise HTTPException(status_code=403, detail="Mekan programı onaylama yetkiniz yok")

    reservation = db.query(RoomReservation).filter(
        RoomReservation.id == reservation_id
    ).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")

    conflict = find_reservation_conflict(
        db,
        reservation.room_id,
        reservation.weekday,
        reservation.start_date,
        reservation.end_date,
        reservation.start_time,
        reservation.end_time,
        exclude_id=reservation.id,
    )

    if conflict:
        raise HTTPException(status_code=400, detail="Bu mekan seçilen saat aralığında dolu")

    reservation.status = "approved"
    reservation.approved_by = current_db_user.id
    reservation.approved_at = datetime.utcnow()

    add_notification(
        db,
        reservation.created_by,
        "Mekan Programı Onaylandı",
        "Mekan program talebiniz onaylandı.",
        "/rooms",
    )

    db.commit()
    db.refresh(reservation)

    return {
        "message": "Program onaylandı",
        "reservation_id": reservation.id,
        "status": reservation.status,
    }


@router.patch("/room-reservations/{reservation_id}/reject")
def reject_room_reservation(
    reservation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_db_user = get_db_user_from_token(db, current_user)

    if not can_approve_rooms(db, current_db_user):
        raise HTTPException(status_code=403, detail="Mekan programı reddetme yetkiniz yok")

    reservation = db.query(RoomReservation).filter(
        RoomReservation.id == reservation_id
    ).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı")

    reservation.status = "rejected"
    reservation.approved_by = current_db_user.id
    reservation.approved_at = datetime.utcnow()

    add_notification(
        db,
        reservation.created_by,
        "Mekan Programı Reddedildi",
        "Mekan program talebiniz reddedildi.",
        "/rooms",
    )

    db.commit()
    db.refresh(reservation)

    return {
        "message": "Program reddedildi",
        "reservation_id": reservation.id,
        "status": reservation.status,
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

    is_approver = can_approve_rooms(db, current_db_user)

    if not is_approver and reservation.created_by != current_db_user.id:
        raise HTTPException(status_code=403, detail="Bu rezervasyonu silme yetkiniz yok")

    if not is_approver and reservation.status == "approved":
        raise HTTPException(status_code=403, detail="Onaylı programı silme yetkiniz yok")

    db.delete(reservation)
    db.commit()

    return {
        "message": "Rezervasyon silindi",
        "reservation_id": reservation_id,
    }


@router.get("/room-reservations/weekly")
def get_weekly_room_reservations(db: Session = Depends(get_db)):
    reservations = db.query(RoomReservation).filter(
        RoomReservation.status == "approved"
    ).order_by(
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
        RoomReservation.status == "approved",
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
