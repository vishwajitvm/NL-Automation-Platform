"""Host agent tables and metrics

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26 01:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create host_agents table
    op.execute("""
        CREATE TABLE host_agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            token_hash TEXT NOT NULL UNIQUE,
            os_family TEXT NOT NULL,
            distro_id TEXT,
            distro_name TEXT,
            distro_version TEXT,
            package_manager TEXT,
            init_system TEXT,
            trash_path TEXT,
            status TEXT NOT NULL DEFAULT 'offline',
            capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
            last_seen_at TIMESTAMPTZ DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 2. Create host_agent_metrics table
    op.execute("""
        CREATE TABLE host_agent_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            host_agent_id UUID NOT NULL REFERENCES host_agents(id) ON DELETE CASCADE,
            metric_name TEXT NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            reported_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_host_agent_metrics_lookup ON host_agent_metrics (metric_name, reported_at DESC);
    """)

    # 3. Create host_agent_jobs table
    op.execute("""
        CREATE TABLE host_agent_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            host_agent_id UUID REFERENCES host_agents(id) ON DELETE CASCADE,
            automation_id UUID REFERENCES automations(id) ON DELETE SET NULL,
            action_name TEXT NOT NULL,
            params JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'pending',
            result JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        );
        CREATE INDEX idx_host_agent_jobs_status ON host_agent_jobs (status, created_at);
    """)

    # 4. Add host_agent_id column to automations table
    op.execute("""
        ALTER TABLE automations ADD COLUMN host_agent_id UUID REFERENCES host_agents(id) ON DELETE SET NULL;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE automations DROP COLUMN IF EXISTS host_agent_id;")
    op.execute("DROP TABLE IF EXISTS host_agent_jobs CASCADE;")
    op.execute("DROP TABLE IF EXISTS host_agent_metrics CASCADE;")
    op.execute("DROP TABLE IF EXISTS host_agents CASCADE;")
