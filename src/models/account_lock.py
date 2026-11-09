import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from src.models.user import User


class AccountLock(Base):
    """Tracks temporary and indefinite account lockout occurrences."""

    __tablename__ = "account_locks"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Reason: MAX_FAILED_LOGINS, EXCESSIVE_OTP_FAILURES, SECURITY_INCIDENT, MANUAL_ADMIN_HOLD
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )
    unlock_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unlocked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="account_locks", foreign_keys=[user_id]
    )
    unlocker: Mapped["User | None"] = relationship("User", foreign_keys=[unlocked_by])

    __table_args__ = (
        Index("ix_account_locks_active", "user_id", postgresql_where=(unlocked_at.is_(None))),
    )