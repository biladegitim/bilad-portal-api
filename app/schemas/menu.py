from pydantic import BaseModel
from datetime import date
from typing import Optional


class MenuCreate(BaseModel):
    menu_date: date
    content: str


class MenuUpdate(BaseModel):
    menu_date: Optional[date] = None
    content: Optional[str] = None