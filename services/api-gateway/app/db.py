import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
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


import hashlib
import uuid


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_host_agent_token() -> Tuple[str, str]:
    token = f"ha_{uuid.uuid4().hex}"
    thash = hash_token(token)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO host_agents (token_hash, os_family, status)
        VALUES (%s, 'pending', 'offline')
        RETURNING id;
        """,
        (thash,)
    )
    agent_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    conn.close()
    return token, agent_id


def register_host_agent(token: str, payload: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
    if payload is None:
        payload = {}
    payload = {**payload, **kwargs}
    thash = hash_token(token)
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        UPDATE host_agents
        SET os_family = %s,
            distro_id = %s,
            distro_name = %s,
            distro_version = %s,
            package_manager = %s,
            init_system = %s,
            trash_path = %s,
            capabilities = %s,
            status = 'online',
            last_seen_at = now()
        WHERE token_hash = %s
        RETURNING id, os_family, distro_id, status, last_seen_at;
        """,
        (
            payload.get("os_family", "unknown"),
            payload.get("distro_id"),
            payload.get("distro_name"),
            payload.get("distro_version"),
            payload.get("package_manager"),
            payload.get("init_system"),
            payload.get("trash_path"),
            json.dumps(payload.get("capabilities", [])),
            thash,
        )
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else None


def record_host_agent_metric(token: str, metric_name: str, value: float) -> bool:
    thash = hash_token(token)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM host_agents WHERE token_hash = %s;", (thash,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return False
    agent_id = row[0]
    cur.execute(
        """
        INSERT INTO host_agent_metrics (host_agent_id, metric_name, value, reported_at)
        VALUES (%s, %s, %s, now());
        """,
        (agent_id, metric_name, value)
    )
    cur.execute(
        """
        UPDATE host_agents
        SET status = 'online', last_seen_at = now()
        WHERE id = %s;
        """,
        (agent_id,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


def get_next_host_agent_job(token: str) -> Optional[Dict[str, Any]]:
    thash = hash_token(token)
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM host_agents WHERE token_hash = %s;", (thash,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    agent_id = row["id"]

    # Heartbeat
    cur.execute("UPDATE host_agents SET status = 'online', last_seen_at = now() WHERE id = %s;", (agent_id,))

    # Pick next pending job
    cur.execute(
        """
        SELECT id, host_agent_id, automation_id, action_name, params, status, created_at
        FROM host_agent_jobs
        WHERE (host_agent_id = %s OR host_agent_id IS NULL) AND status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED;
        """,
        (agent_id,)
    )
    job = cur.fetchone()
    if job:
        cur.execute(
            "UPDATE host_agent_jobs SET status = 'running', host_agent_id = %s WHERE id = %s;",
            (agent_id, job["id"])
        )
        conn.commit()
        cur.close()
        conn.close()
        return dict(job)
    conn.commit()
    cur.close()
    conn.close()
    return None


def complete_host_agent_job(job_id: str, status: str, result: Dict[str, Any]) -> bool:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        UPDATE host_agent_jobs
        SET status = %s, result = %s, completed_at = now()
        WHERE id = %s
        RETURNING automation_id, action_name;
        """,
        (status, json.dumps(result), job_id)
    )
    row = cur.fetchone()
    if row and row["automation_id"]:
        event_type = "action_executed" if status == "done" else "action_failed"
        cur.execute(
            """
            INSERT INTO audit_log (automation_id, event_type, payload)
            VALUES (%s, %s::audit_event_type, %s);
            """,
            (row["automation_id"], event_type, json.dumps({"action": row["action_name"], "result": result, "job_id": job_id, "metric_source": "host_agent"}))
        )
    conn.commit()
    cur.close()
    conn.close()
    return bool(row)


def list_host_agents() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT id, os_family, distro_id, distro_name, distro_version, package_manager, init_system, trash_path, status, capabilities, last_seen_at, created_at
        FROM host_agents
        ORDER BY created_at DESC;
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

