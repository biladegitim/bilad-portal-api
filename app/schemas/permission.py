from pydantic import BaseModel


class PermissionCreate(BaseModel):
    code: str
    description: str | None = None


class UserPermissionCreate(BaseModel):
    permission_code: str