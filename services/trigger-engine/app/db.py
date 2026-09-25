import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("trigger-engine")


def get_connection():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    return psycopg2.connect(db_url)


def get_active_automations(trigger_type: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if trigger_type:
            cur.execute(
                """
                SELECT id, raw_text, structured_plan, status, trigger_type, cooldown_seconds, last_fired_at
                FROM automations
                WHERE status = 'active' AND trigger_type = %s::trigger_type;
                """,
                (trigger_type,)
            )
        else:
            cur.execute(
                """
                SELECT id, raw_text, structured_plan, status, trigger_type, cooldown_seconds, last_fired_at
                FROM automations
                WHERE status = 'active';
                """
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching active automations: {e}")
        return []


def update_last_fired(automation_id: str, fired_at: datetime) -> None:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE automations
            SET last_fired_at = %s, updated_at = now()
            WHERE id = %s;
            """,
            (fired_at, automation_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating last_fired: {e}")


def log_audit_event(event_type: str, payload: Dict[str, Any], automation_id: Optional[str] = None) -> None:
    try:
        conn = get_connection()
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
    except Exception as e:
        logger.error(f"Error recording audit log: {e}")


def get_recent_host_agent_metric(metric_name: str, max_age_seconds: int = 60) -> Optional[float]:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT value
            FROM host_agent_metrics
            WHERE (metric_name = %s OR (%s IN ('recycle_bin_percentage', 'trash_usage_pct') AND metric_name IN ('recycle_bin_percentage', 'trash_usage_pct')))
              AND reported_at >= (now() - (%s || ' seconds')::interval)
            ORDER BY reported_at DESC
            LIMIT 1;
            """,
            (metric_name, metric_name, max_age_seconds)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row is not None:
            return float(row[0])
        return None
    except Exception as e:
        logger.error(f"Error checking recent host agent metric: {e}")
        return None

