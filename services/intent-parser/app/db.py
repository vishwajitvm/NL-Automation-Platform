import json
import logging
import os
from typing import Any, Dict, Optional
import psycopg2

logger = logging.getLogger("intent-parser")

def log_audit_event(event_type: str, payload: Dict[str, Any], automation_id: Optional[str] = None) -> None:
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_log (automation_id, event_type, payload)
            VALUES (%s, %s::audit_event_type, %s);
            """,
            (automation_id, event_type, json.dumps(payload))
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Audit log recorded: event_type={event_type}")
    except Exception as e:
        logger.warning(f"Failed to record audit log: {e}")


def increment_provider_usage(provider: str) -> None:
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO provider_usage (provider, date, request_count)
            VALUES (%s, CURRENT_DATE, 1)
            ON CONFLICT (provider, date)
            DO UPDATE SET request_count = provider_usage.request_count + 1, updated_at = now();
            """,
            (provider,)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to increment provider usage for {provider}: {e}")

def get_provider_usage_today(provider: str) -> int:
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT request_count FROM provider_usage WHERE provider = %s AND date = CURRENT_DATE;
            """,
            (provider,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Failed to get provider usage for {provider}: {e}")
        return 0
