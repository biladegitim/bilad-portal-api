from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.rbac import normalize_role
from app.core.security import decode_access_token


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Gecersiz token",
        )

    return payload


def admin_required(current_user: dict = Depends(get_current_user)):
    if normalize_role(current_user.get("role")) not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Bu islem icin admin yetkisi gerekli",
        )

    return current_user


def qr_display_required(current_user: dict = Depends(get_current_user)):
    if normalize_role(current_user.get("role")) not in ["admin", "super_admin", "qr"]:
        raise HTTPException(
            status_code=403,
            detail="Bu islem icin QR ekran yetkisi gerekli",
        )

    return current_user


def super_admin_required(current_user: dict = Depends(get_current_user)):
    if normalize_role(current_user.get("role")) != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Bu islem icin kurucu yetkisi gerekli",
        )

    return current_user
