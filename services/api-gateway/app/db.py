import json
import logging
import os
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("api-gateway")


def get_connection():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    return psycopg2.connect(db_url)


def list_automations(status: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if status:
            cur.execute(
                """
                SELECT id, user_id, raw_text, structured_plan, status, trigger_type, cooldown_seconds, last_fired_at, created_at, updated_at
                FROM automations
                WHERE status = %s::automation_status
                ORDER BY created_at DESC;
                """,
                (status,)
            )
        else:
            cur.execute(
                """
                SELECT id, user_id, raw_text, structured_plan, status, trigger_type, cooldown_seconds, last_fired_at, created_at, updated_at
                FROM automations
                ORDER BY created_at DESC;
                """
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listing automations: {e}")
        return []


def get_automation_by_id(auto_id: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, user_id, raw_text, structured_plan, status, trigger_type, cooldown_seconds, last_fired_at, created_at, updated_at
            FROM automations
            WHERE id = %s;
            """,
            (auto_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error fetching automation {auto_id}: {e}")
        return None


def archive_automation(auto_id: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE automations
            SET status = 'archived', updated_at = now()
            WHERE id = %s;
            """,
            (auto_id,)
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error archiving automation {auto_id}: {e}")
        return False


def get_audit_logs(automation_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if automation_id:
            cur.execute(
                """
                SELECT id, automation_id, event_type, payload, created_at
                FROM audit_log
                WHERE automation_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (automation_id, limit)
            )
        else:
            cur.execute(
                """
                SELECT id, automation_id, event_type, payload, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (limit,)
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return []
