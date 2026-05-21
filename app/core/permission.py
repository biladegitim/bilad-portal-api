from sqlalchemy.orm import Session

from app.models.permission import Permission, UserPermission


def has_permission(
    db: Session,
    user_id: int,
    permission_code: str
):

    permission = db.query(Permission).filter(
        Permission.code == permission_code
    ).first()

    if not permission:
        return False

    user_permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.permission_id == permission.id
    ).first()

    return user_permission is not None