"""Initial schema setup

Revision ID: 0001
Revises:
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create custom enum types
    op.execute("CREATE TYPE automation_status AS ENUM ('draft', 'active', 'blocked', 'archived');")
    op.execute("CREATE TYPE trigger_type AS ENUM ('time', 'threshold', 'event');")
    op.execute("""
        CREATE TYPE audit_event_type AS ENUM (
            'parsed', 'guardrail_blocked', 'guardrail_approved',
            'ambiguity_asked', 'ambiguity_resolved',
            'trigger_fired', 'action_executed', 'action_failed', 'provider_failover'
        );
    """)

    # 2. Create users table
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 3. Create automations table
    op.execute("""
        CREATE TABLE automations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            raw_text TEXT NOT NULL,
            structured_plan JSONB NOT NULL,
            status automation_status NOT NULL DEFAULT 'draft',
            trigger_type trigger_type NOT NULL,
            cooldown_seconds INT NOT NULL DEFAULT 300,
            last_fired_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 4. Create audit_log table
    op.execute("""
        CREATE TABLE audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            automation_id UUID REFERENCES automations(id),
            event_type audit_event_type NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 5. Create execution_log table
    op.execute("""
        CREATE TABLE execution_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            automation_id UUID NOT NULL REFERENCES automations(id),
            trigger_window_start TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (automation_id, trigger_window_start)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS execution_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS automations CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TYPE IF EXISTS audit_event_type;")
    op.execute("DROP TYPE IF EXISTS trigger_type;")
    op.execute("DROP TYPE IF EXISTS automation_status;")
