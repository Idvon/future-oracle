from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import utcnow


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game: Mapped[str] = mapped_column(String(200), index=True)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(50), default="release")
    status: Mapped[str] = mapped_column(String(20), default="active")
    outcome: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["Metric"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    raw_records: Mapped[list["RawRecord"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    resolutions: Mapped[list["Resolution"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Event {self.id}: {self.game}>"
