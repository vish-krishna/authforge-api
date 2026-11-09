import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, CreatedAtMixin, uuid_pk

if TYPE_CHECKING:
    from src.models.user import User


class PasswordHistory(Base, CreatedAtMixin):
    """Archival table storing past hashes to prevent password reuse (last 5)."""

    __tablename__ = "password_histories"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    algorithm_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="password_histories")

    __table_args__ = (
        Index("ix_password_histories_lookup", "user_id", "created_at"),
    )