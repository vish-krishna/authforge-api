import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, CreatedAtMixin, uuid_pk

if TYPE_CHECKING:
    from src.models.user import User


class SentEmail(Base, CreatedAtMixin):
    """Tracks outbox delivery status for security emails (OTPs, lock notices, verifications)."""

    __tablename__ = "sent_emails"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Types: EMAIL_VERIFICATION, PASSWORD_RESET_OTP, ACCOUNT_LOCKED_NOTICE, PASSWORD_CHANGED_NOTICE, NEW_LOGIN_LOCATION
    email_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_variables: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Status: QUEUED, SENT, DELIVERED, BOUNCED, FAILED
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User | None"] = relationship("User", back_populates="sent_emails")

    __table_args__ = (
        Index("ix_sent_emails_recipient", "recipient_email", "created_at"),
        Index("ix_sent_emails_status", "status"),
        Index("ix_sent_emails_user", "user_id", "created_at"),
    )