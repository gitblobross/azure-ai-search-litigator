# app/models/mixins.py
from sqlalchemy import Column, DateTime, func


class CreatedOnlyMixin:
    """Adds a created_at column (no updated_at).  For immutable records."""

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class TimestampMixin(CreatedOnlyMixin):
    """Adds created_at *and* updated_at.  For mutable records."""

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
