from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import utcnow


class RawRecord(Base):
    __tablename__ = "raw_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(500), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source: Mapped["Source"] = relationship(back_populates="raw_records")
    event: Mapped["Event"] = relationship(back_populates="raw_records")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="raw_record")

    def __repr__(self) -> str:
        return f"<RawRecord {self.id}: {self.title}>"
