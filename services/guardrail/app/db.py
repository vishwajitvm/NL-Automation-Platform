import json
import logging
import os
from typing import Any, Dict, Optional
import psycopg2

logger = logging.getLogger("guardrail")

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
        logger.info(f"Guardrail audit log recorded: event_type={event_type}")
    except Exception as e:
        logger.warning(f"Failed to record guardrail audit log: {e}")
