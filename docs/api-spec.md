# NL-Automation Platform — Human-Readable API Specification

## 1. Overview
The platform exposes a primary user-facing REST gateway (`api-gateway`) on port 8080 and maintains dedicated internal microservice endpoints across the reasoning and execution runtime on `nl-network`.

---

## 2. API Gateway (Public Service)
**Base URL:** `http://localhost:8080` (or `http://localhost:8080/api/v1`)

### `GET /health`
Liveness and readiness check. Returns status `200 OK` with service identifier.
```json
{
  "status": "ok",
  "service": "api-gateway"
}
```

### `POST /api/v1/automations`
Submit a plain-English request to compile and register a new automation.

- **Request Body (`application/json`):**
  ```json
  {
    "text": "clean my recycle bin when it reaches 80%",
    "timezone": "UTC"
  }
  ```

- **Responses:**
  - `201 Created` (Unambiguous Happy Path):
    Automation successfully parsed, verified by guardrails, resolved, and registered.
    ```json
    {
      "id": "e4b17b12-98e2-4523-b1d2-069d80ef748b",
      "status": "active",
      "plan": {
        "trigger": {
          "type": "threshold",
          "params": {
            "metric": "recycle_bin_percentage",
            "operator": ">=",
            "threshold": 80,
            "cooldown_seconds": 300,
            "timezone": "UTC"
          }
        },
        "action": {
          "name": "empty_recycle_bin",
          "params": {}
        },
        "raw_text": "clean my recycle bin when it reaches 80%",
        "ambiguities": [],
        "parseable": true
      },
      "created_at": "2026-09-26T00:00:00Z"
    }
    ```

  - `201 Created` / `200 OK` (Ambiguity Clarification):
    Paused at LangGraph `ask_user` interrupt; stored as `draft`.
    ```json
    {
      "id": "e4b17b12-98e2-4523-b1d2-069d80ef748b",
      "status": "draft",
      "clarification_prompt": "At what percentage of fullness would you like the recycle bin emptied?",
      "expires_at": "2026-09-27T00:00:00Z",
      "plan": { ... }
    }
    ```

  - `400 Bad Request` (Guardrail Blocked):
    ```json
    {
      "detail": {
        "error": "GUARDRAIL_BLOCKED",
        "reason": "Violated security guardrails policy.",
        "categories": ["destructive_fs_op"],
        "suggested_alternative": "You can monitor disk usage with a webhook alert instead."
      }
    }
    ```

  - `400 Bad Request` (Unparseable / Gibberish):
    ```json
    {
      "detail": "I couldn't understand that."
    }
    ```

  - `422 Unprocessable Content` (Compound Intent Rejected):
    ```json
    {
      "detail": "Please describe one automation at a time."
    }
    ```

  - `503 Service Unavailable` (Fail-Closed / Upstream Down):
    ```json
    {
      "detail": "Security guardrail service unavailable (fail-closed)"
    }
    ```

---

### `POST /api/v1/automations/{id}/resume`
Provide user response to an ambiguity question, resuming LangGraph state graph.

- **Request Body (`application/json`):**
  ```json
  {
    "user_response": "clean it when it is 80% full"
  }
  ```

- **Response `200 OK`:**
  ```json
  {
    "id": "e4b17b12-98e2-4523-b1d2-069d80ef748b",
    "status": "active",
    "plan": { ... }
  }
  ```

---

### `GET /api/v1/automations`
List user automations with optional status filter.

- **Query Parameters:**
  - `status` (optional): `active`, `draft`, `archived`
- **Response `200 OK`:**
  ```json
  {
    "automations": [
      {
        "id": "e4b17b12-98e2-4523-b1d2-069d80ef748b",
        "raw_text": "clean my recycle bin when it reaches 80%",
        "status": "active",
        "trigger_type": "threshold",
        "structured_plan": { ... },
        "created_at": "2026-09-26T00:00:00Z"
      }
    ]
  }
  ```

---

### `GET /api/v1/automations/{id}`
Retrieve a single automation by its unique UUID.

---

### `DELETE /api/v1/automations/{id}`
Archive and deactivate an automation. Unregisters the trigger from the runtime engine.
- **Response `200 OK`:**
  ```json
  {
    "status": "archived",
    "id": "e4b17b12-98e2-4523-b1d2-069d80ef748b"
  }
  ```

---

### `GET /api/v1/audit` & `GET /api/v1/automations/{id}/audit`
Query the immutable PostgreSQL audit trail.

- **Query Parameters:**
  - `automation_id` (optional): Filter to a specific automation.
  - `limit` (default: 50): Number of records to return.
- **Response `200 OK`:**
  ```json
  {
    "audit_logs": [
      {
        "id": 104,
        "automation_id": "e4b17b12-98e2-4523-b1d2-069d80ef748b",
        "event_type": "trigger_fired",
        "payload": {
          "trigger_type": "threshold",
          "metric_value": 85
        },
        "timestamp": "2026-09-26T00:05:00Z"
      }
    ]
  }
  ```

---

## 3. Internal Microservice APIs (`nl-network`)

### Intent Parser (`http://intent-parser:8000`)
- `POST /parse`: Accepts `{"raw_text": string}`. Returns `AutomationPlan` via Gemini 2.5 Flash → Groq → OpenRouter failover chain. Returns 422 if multiple intents are detected.

### Guardrail Service (`http://guardrail:8000`)
- `POST /classify`: Accepts `AutomationPlan`. Performs Stage 0 registry pre-gate, Stage 1 Prompt Guard pre-filter, Stage 2 Llama Guard 4 custom taxonomy classifier. Fails closed.

### Decision Agent (`http://decision-agent:8000`)
- `POST /resolve`: Initiates LangGraph state machine. Pauses at `ask_user` on ambiguity; resumes via `POST /resume`. Traced via LangSmith.
- `POST /sweeper/run`: Sweeps and archives drafts older than 24 hours.

### Trigger Engine (`http://trigger-engine:8000`)
- `POST /triggers`: Registers a time-based (APScheduler) or threshold-based polling watcher.
- `DELETE /triggers/{id}`: Unregisters trigger.
- `GET /metrics/{metric_name}` & `POST /metrics/{metric_name}`: Stand-in threshold metric endpoint.

### Execution Sandbox (`http://execution-sandbox:8000`)
- `GET /mcp/tools`: Model Context Protocol schema discovery of allowlisted tools (`send_email`, `send_webhook`, `write_log_notification`, `run_http_healthcheck`, `empty_recycle_bin`).
- `POST /mcp/call`: Executes an MCP tool strictly through the closed action registry.
- `POST /execute`: Dispatches job with idempotency checking against `execution_log`.
