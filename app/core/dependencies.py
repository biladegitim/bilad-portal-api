from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.core.rbac import normalize_role

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Geçersiz token"
        )

    return payload


def admin_required(current_user: dict = Depends(get_current_user)):
    if normalize_role(current_user.get("role")) not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Bu işlem için admin yetkisi gerekli"
        )

    return current_user
def super_admin_required(current_user: dict = Depends(get_current_user)):
    if normalize_role(current_user.get("role")) != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Bu işlem için kurucu yetkisi gerekli"
        )

    return current_user
