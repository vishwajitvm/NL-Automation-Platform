# Setup and Quickstart Guide

## Prerequisites
- **Docker Desktop** (version 24.0+ with Docker Compose v2)
- Environment keys for free-tier providers (see `.env.example`)

---

## 1. Environment Configuration

Copy the template environment file:
```bash
cp .env.example .env
```

Populate the required keys in `.env`:
- `GEMINI_API_KEY`: Google AI Studio API key (free tier)
- `GROQ_API_KEY`: Groq API key for Llama Guard and fast inference
- `MISTRAL_API_KEY`: Mistral AI API key (free tier)
- `LANGSMITH_API_KEY`: LangSmith API key for tracing
- `LANGSMITH_TRACING`: `true`
- `LANGSMITH_PROJECT`: `nl-automation-platform`
- `OPENROUTER_API_KEY`: OpenRouter fallback (optional / free models)

---

## 2. Booting the Platform

Start all services with Docker Compose:
```bash
docker compose up -d --build
```

Check the status of running containers:
```bash
docker compose ps
```

Verify service logs:
```bash
docker compose logs -f api-gateway
```

---

## 3. Exposed Endpoints

| Service | Internal URL | Host Exposed URL |
|---|---|---|
| **Frontend** | `http://frontend:3000` | `http://localhost:3001` (or `$FRONTEND_PORT`) |
| **API Gateway** | `http://api-gateway:8000` | `http://localhost:8080` (or `$API_GATEWAY_PORT`) |
| **TraceNest Logs Dashboard** | `http://api-gateway:8000/tracenest/` | `http://localhost:8080/tracenest` |
| **PostgreSQL** | `postgres:5432` | Internal only |
| **Redis** | `redis:6379` | Internal only |
| **Intent Parser** | `intent-parser:8000` | Internal only |
| **Guardrail** | `guardrail:8000` | Internal only |
| **Decision Agent** | `decision-agent:8000` | Internal only |
| **Trigger Engine** | `trigger-engine:8000` | Internal only |
| **Execution Sandbox** | `execution-sandbox:8000` | Internal only |

---

## 4. TraceNest Observability Dashboard

Access the real-time logging and observability dashboard directly in your browser:
- **URL**: `http://localhost:8080/tracenest`
- **Features**:
  - Live inspection of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, and custom `TRACE` log records.
  - Multi-service dropdown to inspect logs from `api-gateway`, `intent-parser`, `guardrail`, `decision-agent`, `trigger-engine`, and `execution-sandbox`.
  - Secret redaction enabled by default (API keys and credentials are automatically scrubbed).
  - Also accessible via the **"TraceNest Logs"** button in the top navigation bar of the Web UI (`http://localhost:3001`).

---

## 5. Teardown

To stop and remove containers:
```bash
docker compose down
```
To remove persistent volumes:
```bash
docker compose down -v
```
