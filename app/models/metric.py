from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import utcnow


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_records.id"), nullable=True
    )
    signal_type: Mapped[str] = mapped_column(String(50), index=True)
    value: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=0.5)
    source_reliability: Mapped[float] = mapped_column(Float, default=0.5)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    event: Mapped["Event"] = relationship(back_populates="metrics")
    raw_record: Mapped["RawRecord"] = relationship(back_populates="metrics")

    def __repr__(self) -> str:
        return f"<Metric {self.id}: {self.signal_type}={self.value}>"
