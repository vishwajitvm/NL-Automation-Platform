import sys

with open('services/api-gateway/app/db.py', 'a') as f:
    f.write('''
def get_provider_usage_today() -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            \"\"\"
            SELECT provider, request_count
            FROM provider_usage
            WHERE date = CURRENT_DATE;
            \"\"\"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error getting provider usage: {e}")
        return []


def get_templates() -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            \"\"\"
            SELECT id, title, description, raw_text_template, category
            FROM automation_templates
            ORDER BY title ASC;
            \"\"\"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return []
''')
