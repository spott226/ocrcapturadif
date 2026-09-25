from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Person(Base):
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    address: Mapped[str] = mapped_column(Text, default="")
    curp: Mapped[str] = mapped_column(String(18), default="", index=True)
    voter_key: Mapped[str] = mapped_column(String(24), default="", index=True)
    valid_until: Mapped[str] = mapped_column(String(20), default="")
    created_by: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

