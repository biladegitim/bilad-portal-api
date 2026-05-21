from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from app.database.connection import get_db
from app.models.menu import Menu
from app.models.user import User
from app.schemas.menu import MenuCreate, MenuUpdate
from app.core.dependencies import get_current_user
from app.core.permission import has_permission
from app.core.rbac import normalize_role

router = APIRouter()


@router.post("/menus")
def create_menu(
    data: MenuCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == current_user["sub"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    is_admin = normalize_role(user.role) in ["admin", "super_admin"]

    if not is_admin and not has_permission(
        db,
        user.id,
        "menu.manage"
):
        raise HTTPException(
        status_code=403,
        detail="Menü ekleme yetkiniz yok"
    )

    existing_menu = db.query(Menu).filter(
        Menu.menu_date == data.menu_date
    ).first()

    if existing_menu:
        existing_menu.content = data.content
        db.commit()
        db.refresh(existing_menu)

        return {
            "message": "Menü güncellendi",
            "menu_id": existing_menu.id
        }

    menu = Menu(
        menu_date=data.menu_date,
        content=data.content
    )

    db.add(menu)
    db.commit()
    db.refresh(menu)

    return {
        "message": "Menü oluşturuldu",
        "menu_id": menu.id
    }


@router.get("/menus/today")
def get_today_menu(db: Session = Depends(get_db)):
    today_menu = db.query(Menu).filter(
        Menu.menu_date == date.today()
    ).first()

    if not today_menu:
        return {"message": "Bugün için menü bulunamadı"}

    return {
        "menu_date": today_menu.menu_date,
        "content": today_menu.content
    }


@router.get("/menus")
def get_all_menus(db: Session = Depends(get_db)):
    menus = db.query(Menu).order_by(
        Menu.menu_date.desc()
    ).all()

    return {
        "menus": [
            {
                "id": menu.id,
                "menu_date": menu.menu_date,
                "content": menu.content
            }
            for menu in menus
        ]
    }
from app.schemas.menu import MenuUpdate
@router.patch("/menus/{menu_id}")
def update_menu(
    menu_id: int,
    data: MenuUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == current_user["sub"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    is_admin = normalize_role(user.role) in ["admin", "super_admin"]

    if not is_admin and not has_permission(db, user.id, "menu.manage"):
        raise HTTPException(status_code=403, detail="Menü düzenleme yetkiniz yok")

    menu = db.query(Menu).filter(Menu.id == menu_id).first()

    if not menu:
        raise HTTPException(status_code=404, detail="Menü bulunamadı")

    if data.menu_date is not None:
        menu.menu_date = data.menu_date

    if data.content is not None:
        menu.content = data.content

    db.commit()
    db.refresh(menu)

    return {
        "message": "Menü güncellendi",
        "menu": {
            "id": menu.id,
            "menu_date": menu.menu_date,
            "content": menu.content
        }
    }


@router.delete("/menus/{menu_id}")
def delete_menu(
    menu_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == current_user["sub"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    is_admin = normalize_role(user.role) in ["admin", "super_admin"]

    if not is_admin and not has_permission(db, user.id, "menu.manage"):
        raise HTTPException(status_code=403, detail="Menü silme yetkiniz yok")

    menu = db.query(Menu).filter(Menu.id == menu_id).first()

    if not menu:
        raise HTTPException(status_code=404, detail="Menü bulunamadı")

    db.delete(menu)
    db.commit()

    return {
        "message": "Menü silindi",
        "menu_id": menu_id
    }
