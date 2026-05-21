from sqlalchemy import Column, Integer, Date, Text
from datetime import date

from app.database.base import Base


class Menu(Base):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, index=True)
    menu_date = Column(Date, default=date.today)
    content = Column(Text, nullable=False)