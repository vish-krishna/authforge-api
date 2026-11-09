import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from src.models.account_lock import AccountLock
    from src.models.audit_log import AuthAuditLog
    from src.models.password_history import PasswordHistory
    from src.models.password_reset_request import PasswordResetRequest
    from src.models.sent_email import SentEmail
    from src.models.user_session import UserSession


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Active password stored directly on User
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    algorithm_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Status: PENDING_VERIFICATION, ACTIVE, LOCKED, SUSPENDED, DEACTIVATED
    status: Mapped[str] = mapped_column(
        String(30), default="PENDING_VERIFICATION", index=True, nullable=False
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    password_histories: Mapped[List["PasswordHistory"]] = relationship(
        "PasswordHistory", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    account_locks: Mapped[List["AccountLock"]] = relationship(
        "AccountLock",
        back_populates="user",
        foreign_keys="AccountLock.user_id",
        cascade="all, delete-orphan",
    )
    reset_requests: Mapped[List["PasswordResetRequest"]] = relationship(
        "PasswordResetRequest", back_populates="user", cascade="all, delete-orphan"
    )
    sent_emails: Mapped[List["SentEmail"]] = relationship(
        "SentEmail", back_populates="user"
    )
    audit_logs: Mapped[List["AuthAuditLog"]] = relationship(
        "AuthAuditLog", back_populates="user"
    )

    __table_args__ = (
        # Partial index: Enforces case-insensitive uniqueness across non-deleted rows
        Index(
            "uq_users_active_email",
            "email",
            unique=True,
            postgresql_where=(TimestampMixin.deleted_at.is_(None)),
        ),
    )