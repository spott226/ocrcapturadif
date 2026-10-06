from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SupportType(Base):
    __tablename__ = "support_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Unicode(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(Unicode(180))
    active: Mapped[bool] = mapped_column("is_active", Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Unicode(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Unicode(512))
    role: Mapped[str] = mapped_column(Unicode(32), default="capturista", index=True)
    active: Mapped[bool] = mapped_column("is_active", Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(Unicode(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Legacy fields remain in place so existing records and previous exports do
    # not become unreadable. New records dual-write ``name`` from the parts and
    # leave ``address`` empty by design.
    name: Mapped[str] = mapped_column(Unicode(180), index=True)
    address: Mapped[str] = mapped_column(Unicode, default="")

    given_names: Mapped[str] = mapped_column(Unicode(120), default="")
    paternal_surname: Mapped[str] = mapped_column(Unicode(80), default="")
    maternal_surname: Mapped[str] = mapped_column(Unicode(80), default="")
    municipality: Mapped[str] = mapped_column(Unicode(120), default="", index=True)
    support_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("support_types.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    support_type: Mapped[SupportType | None] = relationship(lazy="joined")

    curp: Mapped[str] = mapped_column(Unicode(18), default="", index=True)
    phone: Mapped[str] = mapped_column(Unicode(15), default="", index=True)
    leader: Mapped[str] = mapped_column(Unicode(180), default="")
    voter_key: Mapped[str] = mapped_column(Unicode(24), default="", index=True)
    birth_date: Mapped[str] = mapped_column(Unicode(20), default="")
    sex_or_gender: Mapped[str] = mapped_column(Unicode(20), default="")
    state_code: Mapped[str] = mapped_column(Unicode(20), default="")
    municipality_code: Mapped[str] = mapped_column(Unicode(20), default="")
    section: Mapped[str] = mapped_column(Unicode(10), default="")
    locality_code: Mapped[str] = mapped_column(Unicode(20), default="")
    registration_year: Mapped[str] = mapped_column(Unicode(20), default="")
    issue_year: Mapped[str] = mapped_column(Unicode(10), default="")
    cic: Mapped[str] = mapped_column(Unicode(20), default="", index=True)
    ocr_code: Mapped[str] = mapped_column(Unicode(20), default="", index=True)
    valid_until: Mapped[str] = mapped_column(Unicode(20), default="")
    created_by: Mapped[str] = mapped_column(Unicode(254))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def display_name(self) -> str:
        parts = (self.given_names, self.paternal_surname, self.maternal_surname)
        separated = " ".join(part.strip() for part in parts if part and part.strip())
        return separated or self.name

    @property
    def display_municipality(self) -> str:
        # Legacy rows have no municipality. Preserve access to their previous
        # address rather than attempting a destructive automatic conversion.
        return self.municipality or self.address
