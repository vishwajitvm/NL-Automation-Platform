"""Phase 10 & 11 additions: delay trigger and new audit event types

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26 04:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend trigger_type enum with 'delay'
    op.execute("ALTER TYPE trigger_type ADD VALUE IF NOT EXISTS 'delay';")

    # Extend audit_event_type enum with new event types
    op.execute("ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS 'ethics_review';")
    op.execute("ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS 'trigger_registered';")
    op.execute("ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS 'destructive_action_confirmation';")


def downgrade() -> None:
    pass
