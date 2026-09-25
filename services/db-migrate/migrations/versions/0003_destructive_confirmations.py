"""Destructive action confirmations and content policy enums

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend enums
    op.execute("ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS 'content_policy_blocked';")
    op.execute("ALTER TYPE trigger_type ADD VALUE IF NOT EXISTS 'immediate';")

    # 2. Create destructive_action_confirmations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS destructive_action_confirmations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            automation_id UUID REFERENCES automations(id) ON DELETE SET NULL,
            command_id UUID,
            step TEXT NOT NULL,
            target_path TEXT,
            details JSONB DEFAULT '{}'::jsonb,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_destr_confirm_auto ON destructive_action_confirmations (automation_id);
        CREATE INDEX IF NOT EXISTS idx_destr_confirm_cmd ON destructive_action_confirmations (command_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS destructive_action_confirmations;")
