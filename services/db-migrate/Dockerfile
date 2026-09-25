FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/db-migrate/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/db-migrate .

CMD ["alembic", "upgrade", "head"]
