"""Phase 12 updates

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add provider_preemptive_skip to audit_event_type
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS 'provider_preemptive_skip'")

    # 2. Add provider_usage table
    op.create_table(
        'provider_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'date', name='uq_provider_date')
    )

    # 3. Add automation_templates table
    op.create_table(
        'automation_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('raw_text_template', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Seed templates
    op.execute("""
        INSERT INTO automation_templates (title, description, raw_text_template, category) VALUES
        ('Morning briefing', 'Weather and calendar for today', 'Send me a morning briefing every day at 7am', 'time'),
        ('Low disk alert', 'Notify when disk is full', 'Warn me when my C drive reaches 85%', 'threshold'),
        ('Weekly report email', 'Send report every Friday', 'Email me a weekly report every Friday at 5pm', 'time'),
        ('Website uptime check', 'Check website health', 'Check healthcheck for my website', 'time'),
        ('Daily standup reminder', 'Slack reminder for standup', 'Remind me on Slack for daily standup in 5 minutes', 'delay'),
        ('New row on form submit', 'Add to Google Sheets', 'Append a row to my spreadsheet when form submitted', 'event')
    """)


def downgrade() -> None:
    op.drop_table('automation_templates')
    op.drop_table('provider_usage')
    # Note: Cannot easily DROP an enum value in postgres, so we leave 'provider_preemptive_skip'
