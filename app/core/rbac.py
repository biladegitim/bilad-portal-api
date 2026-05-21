from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User


VALID_ROLES = {"super_admin", "admin", "employee"}
ROLE_ALIASES = {
    "çalışan": "employee",
    "calisan": "employee",
    "employee": "employee",
    "admin": "admin",
    "super_admin": "super_admin",
}


def normalize_role(role: str | None) -> str:
    return ROLE_ALIASES.get(role or "", "employee")


def normalize_user_role(db: Session, user: User) -> User:
    normalized_role = normalize_role(user.role)

    if user.role != normalized_role:
        user.role = normalized_role
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def get_db_user_from_token(db: Session, current_user: dict) -> User:
    user = db.query(User).filter(
        User.email == current_user["sub"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    return normalize_user_role(db, user)


def can_manage_user(actor: User, target: User) -> bool:
    actor_role = normalize_role(actor.role)

    if actor_role == "super_admin":
        return True

    if actor_role == "admin":
        return target.supervisor_id == actor.id

    return actor.id == target.id


def require_can_manage_user(actor: User, target: User, detail: str) -> None:
    if not can_manage_user(actor, target):
        raise HTTPException(status_code=403, detail=detail)


def scoped_users_query(db: Session, actor: User):
    actor_role = normalize_role(actor.role)

    if actor_role == "super_admin":
        return db.query(User)

    if actor_role == "admin":
        return db.query(User).filter(User.supervisor_id == actor.id)

    return db.query(User).filter(User.id == actor.id)


def scoped_user_ids(db: Session, actor: User) -> list[int]:
    return [
        user.id
        for user in scoped_users_query(db, actor).all()
    ]
