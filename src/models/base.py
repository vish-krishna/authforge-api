import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Reusable mapped type shortcuts
uuid_pk = Annotated[
    uuid.UUID,
    mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    ),
]


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass



class TimestampMixin:
    """Reusable audit timestamp mixin providing creation, update, and soft-delete markers."""

    # 1. Populates on row creation (both via DB DDL default and ORM)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )

    # 2. Populates on initial creation via server_default, 
    #    and auto-updates on every ORM UPDATE statement via onupdate
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
        nullable=False,
    )

    # 3. Soft-delete flag (remains NULL until marked deleted)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class CreatedAtMixin:
    """Reusable creation timestamp for append-only forensic tables."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )


__all__ = ["Base", "TimestampMixin", "CreatedAtMixin", "uuid_pk"]