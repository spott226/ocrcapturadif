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
    birth_date: Mapped[str] = mapped_column(String(20), default="")
    sex_or_gender: Mapped[str] = mapped_column(String(20), default="")
    state_code: Mapped[str] = mapped_column(String(20), default="")
    municipality_code: Mapped[str] = mapped_column(String(20), default="")
    section: Mapped[str] = mapped_column(String(10), default="")
    locality_code: Mapped[str] = mapped_column(String(20), default="")
    registration_year: Mapped[str] = mapped_column(String(20), default="")
    issue_year: Mapped[str] = mapped_column(String(10), default="")
    cic: Mapped[str] = mapped_column(String(20), default="", index=True)
    ocr_code: Mapped[str] = mapped_column(String(20), default="", index=True)
    valid_until: Mapped[str] = mapped_column(String(20), default="")
    created_by: Mapped[str] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
