from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import utcnow


class Resolution(Base):
    __tablename__ = "resolutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    actual_outcome: Mapped[bool] = mapped_column(Boolean)
    probability: Mapped[float] = mapped_column(Float)
    brier_score: Mapped[float] = mapped_column(Float)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    event: Mapped["Event"] = relationship(back_populates="resolutions")

    def __repr__(self) -> str:
        return f"<Resolution {self.id}: brier={self.brier_score}>"
