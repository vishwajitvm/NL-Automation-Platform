import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("decision-agent")


def get_connection():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    return psycopg2.connect(db_url)


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


def get_or_create_default_user_id() -> str:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users LIMIT 1;")
        row = cur.fetchone()
        if row:
            uid = str(row[0])
            cur.close()
            conn.close()
            return uid
        
        uid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s);",
            (uid, "default_user@example.com", "default_hash")
        )
        conn.commit()
        cur.close()
        conn.close()
        return uid
    except Exception as e:
        logger.error(f"Error fetching/creating user: {e}")
        return str(uuid.uuid4())


def persist_automation_record(
    plan: Dict[str, Any],
    status: str,
    trigger_type: str,
    automation_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> str:
    conn = get_connection()
    cur = conn.cursor()
    
    uid = user_id or get_or_create_default_user_id()
    auto_id = automation_id or str(uuid.uuid4())
    raw_text = plan.get("raw_text", "")
    
    cur.execute(
        """
        INSERT INTO automations (id, user_id, raw_text, structured_plan, status, trigger_type, updated_at)
        VALUES (%s, %s, %s, %s, %s::automation_status, %s::trigger_type, now())
        ON CONFLICT (id) DO UPDATE
        SET structured_plan = EXCLUDED.structured_plan,
            status = EXCLUDED.status,
            trigger_type = EXCLUDED.trigger_type,
            updated_at = now();
        """,
        (auto_id, uid, raw_text, json.dumps(plan), status, trigger_type)
    )
    conn.commit()
    cur.close()
    conn.close()
    return auto_id


def sweep_expired_drafts(cutoff_delta: timedelta = timedelta(hours=24), custom_now: Optional[datetime] = None) -> List[str]:
    """
    Sweeps any automations row with status='draft' and created_at < cutoff
    Sets status -> 'archived' and records audit_log ambiguity_resolved with reason='expired_unanswered'.
    """
    now = custom_now or datetime.now(timezone.utc)
    cutoff = now - cutoff_delta
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute(
        """
        SELECT id FROM automations
        WHERE status = 'draft' AND created_at < %s;
        """,
        (cutoff,)
    )
    expired_rows = cur.fetchall()
    archived_ids = []
    
    for row in expired_rows:
        aid = str(row["id"])
        cur.execute(
            """
            UPDATE automations
            SET status = 'archived', updated_at = now()
            WHERE id = %s;
            """,
            (aid,)
        )
        cur.execute(
            """
            INSERT INTO audit_log (automation_id, event_type, payload)
            VALUES (%s, 'ambiguity_resolved', %s);
            """,
            (aid, json.dumps({"reason": "expired_unanswered"}))
        )
        archived_ids.append(aid)

    conn.commit()
    cur.close()
    conn.close()
    return archived_ids
