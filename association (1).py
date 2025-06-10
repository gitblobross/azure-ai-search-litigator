# app/models/association.py
from sqlalchemy import Column, ForeignKey, Integer, Table, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.db_models.db_base import Base

# ────────────────────────────────────────────────────────────────
#  Exhibits  ←→  Facts
# ────────────────────────────────────────────────────────────────
exhibit_fact_association = Table(
    "exhibit_fact_association",
    Base.metadata,
    Column(
        "exhibit_id",
        Integer,
        ForeignKey("exhibits.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("fact_id", Integer, ForeignKey("facts.id", ondelete="CASCADE"), primary_key=True),
)

# ────────────────────────────────────────────────────────────────
#  Evidence  ←→  Facts
# ────────────────────────────────────────────────────────────────
evidence_fact_association = Table(
    "evidence_fact_association",
    Base.metadata,
    Column(
        "evidence_id",
        Integer,
        ForeignKey("evidence.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("fact_id", Integer, ForeignKey("facts.id", ondelete="CASCADE"), primary_key=True),
)

# ────────────────────────────────────────────────────────────────
#  ComplaintSection links
# ────────────────────────────────────────────────────────────────
complaint_section_fact_link = Table(
    "complaint_section_fact_link",
    Base.metadata,
    Column(
        "complaint_section_id",
        Integer,
        ForeignKey("complaint_sections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "fact_id",
        Integer,
        ForeignKey("facts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

complaint_section_exhibit_link = Table(
    "complaint_section_exhibit_link",
    Base.metadata,
    Column(
        "complaint_section_id",
        Integer,
        ForeignKey("complaint_sections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "exhibit_id",
        Integer,
        ForeignKey("exhibits.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# ────────────────────────────────────────────────────────────────
#  Event  ←→  Facts
# ────────────────────────────────────────────────────────────────
event_fact = Table(
    "event_fact",
    Base.metadata,
    Column(
        "event_id",
        UUID(as_uuid=True),
        ForeignKey("event.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "fact_id",
        ForeignKey("facts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("role", Text, nullable=False),
)
