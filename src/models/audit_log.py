import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, CreatedAtMixin, uuid_pk

if TYPE_CHECKING:
    from src.models.user import User


class AuthAuditLog(Base, CreatedAtMixin):
    """Append-only immutable forensic log for authentication and authorization events."""

    __tablename__ = "auth_audit_logs"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    email_attempted: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_event_created", "event_type", "created_at"),
        Index("ix_audit_email_attempted", "email_attempted", "created_at"),
    )