with open('services/intent-parser/app/db.py', 'a') as f:
    f.write('''

def increment_provider_usage(provider: str) -> None:
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/nl_automation")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            \"\"\"
            INSERT INTO provider_usage (provider, date, request_count)
            VALUES (%s, CURRENT_DATE, 1)
            ON CONFLICT (provider, date)
            DO UPDATE SET request_count = provider_usage.request_count + 1, updated_at = now();
            \"\"\",
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
            \"\"\"
            SELECT request_count FROM provider_usage WHERE provider = %s AND date = CURRENT_DATE;
            \"\"\",
            (provider,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Failed to get provider usage for {provider}: {e}")
        return 0
''')
