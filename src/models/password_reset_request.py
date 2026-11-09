import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, CreatedAtMixin, uuid_pk

if TYPE_CHECKING:
    from src.models.user import User


class PasswordResetRequest(Base, CreatedAtMixin):
    """Stores hashed 6-digit email OTPs and enforces max attempt thresholds."""

    __tablename__ = "password_reset_requests"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Status: PENDING, USED, EXPIRED, LOCKED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="reset_requests")

    __table_args__ = (
        Index("ix_password_reset_pending", "user_id", "status"),
    )