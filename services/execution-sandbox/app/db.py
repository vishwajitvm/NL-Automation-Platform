import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import psycopg2

logger = logging.getLogger("execution-sandbox")


def get_connection():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    return psycopg2.connect(db_url)


def check_and_record_idempotency(automation_id: str, trigger_window_start: datetime, status: str = "running") -> Tuple[bool, Optional[str]]:
    """
    Checks if an execution with (automation_id, trigger_window_start) already exists.
    Returns (is_duplicate: bool, existing_status: Optional[str]).
    If not duplicate, inserts a new row and returns (False, None).
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check existing
        cur.execute(
            """
            SELECT status FROM execution_log
            WHERE automation_id = %s AND trigger_window_start = %s;
            """,
            (automation_id, trigger_window_start)
        )
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            return (True, row[0])

        # Insert new execution record
        cur.execute(
            """
            INSERT INTO execution_log (automation_id, trigger_window_start, status)
            VALUES (%s, %s, %s);
            """,
            (automation_id, trigger_window_start, status)
        )
        conn.commit()
        cur.close()
        conn.close()
        return (False, None)
    except Exception as e:
        logger.error(f"Error checking execution idempotency: {e}")
        # In case of DB collision race condition
        return (True, "conflict")


def update_execution_status(automation_id: str, trigger_window_start: datetime, status: str) -> None:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE execution_log
            SET status = %s
            WHERE automation_id = %s AND trigger_window_start = %s;
            """,
            (status, automation_id, trigger_window_start)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating execution status: {e}")


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
        logger.error(f"Error logging audit event: {e}")


def get_online_host_agent() -> Optional[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, os_family, distro_id, status, last_seen_at
            FROM host_agents
            WHERE status = 'online'
            ORDER BY last_seen_at DESC
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "id": str(row[0]),
                "user_id": str(row[1]) if row[1] else None,
                "os_family": row[2],
                "distro_id": row[3],
                "status": row[4],
                "last_seen_at": str(row[5]) if row[5] else None,
            }
        return None
    except Exception as e:
        logger.error(f"Error getting online host agent: {e}")
        return None


def create_host_agent_job(host_agent_id: str, action_name: str, params: Dict[str, Any], automation_id: Optional[str] = None) -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO host_agent_jobs (host_agent_id, automation_id, action_name, params, status)
        VALUES (%s, %s, %s, %s, 'pending')
        RETURNING id;
        """,
        (host_agent_id, automation_id, action_name, json.dumps(params))
    )
    job_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    conn.close()
    return job_id

