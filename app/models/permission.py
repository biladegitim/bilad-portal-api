from sqlalchemy import Column, Integer, String, ForeignKey

from app.database.base import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)