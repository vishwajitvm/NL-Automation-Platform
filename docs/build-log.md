# NL-Automation Platform — Build Log

## Phase 0 — Scaffolding Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **Repository Structure**:
   - Initialized the full project structure: `docs/`, `docs/diagrams/`, `services/api-gateway/`, `services/intent-parser/`, `services/guardrail/`, `services/decision-agent/`, `services/trigger-engine/`, `services/execution-sandbox/app/actions/`, `frontend/`, and `shared/schemas/`.
2. **Documentation & Specification**:
   - Established `docs/spec.md` as the authoritative source of truth.
   - Authored `docs/architecture.md` embedding all 3 architecture/sequence diagrams (`architecture.mmd`, `sequence-create.mmd`, `sequence-trigger.mmd`).
   - Authored `docs/api-spec.md` with human-readable API specs.
   - Authored `docs/security-guardrails.md` documenting blocked vs allowed action taxonomy, the "reject with explicit message" policy for compound automations, the Recycle Bin host boundary isolation policy, and fail-closed guardrail behavior.
   - Authored `docs/setup.md` and `docs/roadmap.md`.
3. **Environment & Shared Modules**:
   - Created `.env.example` listing all required variables (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`, `HUGGINGFACE_API_KEY`, `NVIDIA_API_KEY`, `KIMI_API_KEY`, `DATABASE_URL`, `REDIS_URL`).
   - Created shared Pydantic plan models (`shared/schemas/plan.py`) and secret redaction helper (`shared/redaction.py`).
   - Configured `shared/logging_config.py` with TraceNest middleware integration and secret redaction.
4. **Action Registry**:
   - Created stub action files in `services/execution-sandbox/app/actions/`: `send_email.py`, `send_webhook.py`, `write_log_notification.py`, `run_http_healthcheck.py`, and `empty_recycle_bin.py` (marked as host-boundary/v2 stub).
5. **Docker Compose & Services**:
   - Configured `docker-compose.yml` with isolated internal network `nl-network`, running PostgreSQL 16 (healthy), Redis 7 (healthy), `api-gateway` (exposing port 8080 to host), `frontend` (exposing port 3001 to host), and internal services `intent-parser`, `guardrail`, `decision-agent`, `trigger-engine`, `execution-sandbox`.
   - Mounted named volumes for TraceNest logs across all 6 backend services.

### Acceptance Criteria Checklist
- [x] All 9 containers (`postgres`, `redis`, `api-gateway`, `intent-parser`, `guardrail`, `decision-agent`, `trigger-engine`, `execution-sandbox`, `frontend`) boot cleanly without error via `docker compose up -d --build`.
- [x] `http://localhost:8080/health` returns `200 OK`.
- [x] Service stub endpoints return `501 Not Implemented` with informative details (`{"detail":"... endpoint not implemented in Phase 0 stub"}`).
- [x] Frontend boots cleanly on Next.js 14, serving `200 OK` on `http://localhost:3001`.
- [x] Only `api-gateway` and `frontend` expose ports to host; data and cognitive services remain strictly on the internal Docker network.

---

## Phase 1 — Data Layer & Shared Schema Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **Shared Pydantic Schema**:
   - Extended `shared/schemas/plan.py` to match the exact Phase 1 specification: `TriggerType` enum (`time`, `threshold`, `event`), `Trigger`, `Action`, `Ambiguity`, and `AutomationPlan` (`raw_text`, `trigger`, `action`, `ambiguities`, `parseable`).
   - Verified that `shared/schemas/plan.py` is successfully imported and serialized across all backend services.
2. **Alembic Database Migration Container (`services/db-migrate/`)**:
   - Configured `services/db-migrate/` with `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, and `0001_initial.py`.
   - Created PostgreSQL enums: `automation_status` (`draft`, `active`, `blocked`, `archived`), `trigger_type` (`time`, `threshold`, `event`), `audit_event_type` (`parsed`, `guardrail_blocked`, `guardrail_approved`, `ambiguity_asked`, `ambiguity_resolved`, `trigger_fired`, `action_executed`, `action_failed`, `provider_failover`).
   - Created tables: `users`, `automations`, `audit_log`, and `execution_log` (with unique constraint `(automation_id, trigger_window_start)` for idempotency).
   - Wired `db-migrate` into `docker-compose.yml` with `restart: "no"`. Configured dependent services (`api-gateway`, `trigger-engine`, `execution-sandbox`) with `condition: service_completed_successfully` so migrations run to completion before runtime services start.
3. **Database Roundtrip & Idempotency Verification**:
   - Verified via throwaway test script inserting into `users`, `automations`, and `execution_log` tables and reading back the records.

### Acceptance Criteria Checklist
- [x] `docker compose up` runs `db-migrate` to completion (exit 0) before dependent services start.
- [x] Manual `psql` check: all 4 tables (`users`, `automations`, `audit_log`, `execution_log`) and 3 enums (`automation_status`, `trigger_type`, `audit_event_type`) exist in Postgres.
- [x] Insert/select round trip on `automations` succeeds via a throwaway script.
- [x] `shared/schemas/plan.py` importable and verified in every service container.

---

## Phase 2 — Intent Parser Service Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **Provider Chain & LLM Implementations**:
   - Implemented `LLMProvider` abstract base class and concrete providers in `services/intent-parser/app/providers.py`: `GeminiProvider` (Gemini 2.5 Flash), `GroqProvider` (Llama 3.3 70B), `OpenRouterProvider` (Meta Llama 3.3 70B free), and `DeterministicRuleProvider` (test/offline fallback).
   - Implemented `ProviderChain` executing sequential failover on `RateLimitError` or `ProviderUnavailableError`, automatically recording `provider_failover` events to PostgreSQL `audit_log`.
   - Built corrective retry mechanism for malformed JSON output (cap 2 attempts) before triggering failover.
2. **Endpoint `POST /parse`**:
   - Implemented in `services/intent-parser/app/main.py` converting unstructured natural language into structured `AutomationPlan`.
   - Enforced compound sentence rejection policy: sentences with $\ge 2$ distinct automations return HTTP 422 with `compound_automation_rejected` and `detected_count`.
   - Cleanly handles empty or gibberish input returning HTTP 200 with `parseable: false`.
   - Underspecified inputs populate `ambiguities` rather than inventing default parameters.
3. **Test Suite**:
   - 10 automated test cases in `services/intent-parser/tests/test_parser.py` covering:
     - Canonical recycle bin threshold example.
     - Canonical Friday 5pm email time example.
     - Disk threshold (90% and 85%) and metric verification.
     - Ambiguity detection ("clean the recycle bin when it is full").
     - Webhook and healthcheck time triggers.
     - Empty and gibberish input parsing.
     - Compound sentence rejection (HTTP 422).
     - Simulated Gemini 429 rate limit triggering failover to Groq and logging `provider_failover` to `audit_log`.

### Acceptance Criteria Checklist
- [x] "clean my recycle bin when it reaches 80%" → `trigger.type=threshold`, `trigger.params.threshold=80`, `action.name=empty_recycle_bin`.
- [x] "email me a summary every Friday at 5pm" → `trigger.type=time`, cron `"0 17 * * 5"`, `action.name=send_email`.
- [x] Gibberish input → `parseable: false`, no crash.
- [x] Simulated Gemini 429 → Groq is used, and a `provider_failover` audit event is written.
- [x] Compound sentence → 422 with `compound_automation_rejected`.
- [x] 10/10 automated tests pass cleanly in pytest inside the container.

---

## Phase 3 — Guardrail Service Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **Multi-Stage Safety Architecture**:
   - Stage 0 (Action Registry Pre-Gate): Any plan referencing an action not in the closed registry (`send_email`, `send_webhook`, `write_log_notification`, `run_http_healthcheck`, `empty_recycle_bin`) is blocked deterministically before reaching LLM inference.
   - Stage 1 (Injection Pre-filter): Screen against prompt injection and jailbreak payloads using `meta-llama/llama-prompt-guard-2-86m`.
   - Stage 2 (Taxonomy Classifier): Evaluate structured plan against custom security taxonomy (`destructive_fs_op`, `credential_exfiltration`, `network_exfiltration`, `malware_behavior`) using hosted `meta-llama/llama-guard-4-12b`.
2. **Fail-Closed Guarantees**:
   - Wrapped all external calls in strict fail-closed handlers. Any connection error, timeout, or upstream 5xx logs `guardrail_blocked` with `payload.reason="fail_closed"` to PostgreSQL `audit_log` and immediately returns `blocked` with category `guardrail_unavailable`.
3. **Endpoint `POST /classify`**:
   - Implemented in `services/guardrail/app/main.py` accepting `AutomationPlan` and returning `ClassificationResult` (`decision`, `reason`, `categories`).
4. **Automated Verification**:
   - 5/5 pytest test cases passed in `services/guardrail/tests/test_guardrail.py` proving safe plan approval, unregistered action blocking, destructive operation prevention, prompt injection blocking, and fail-closed behavior when Groq is simulated unreachable.

### Acceptance Criteria Checklist
- [x] Recycle-bin plan → `approved`.
- [x] A plan whose `action.name` is not in the registry → `blocked` before even reaching Groq (registry check first, cheaper and deterministic).
- [x] A synthetically "format C: every night"-style plan → `blocked`, category `destructive_fs_op`.
- [x] Groq endpoint forced unreachable in test → `blocked`, category `guardrail_unavailable` (fail-closed proven).
- [x] 5/5 automated guardrail tests pass cleanly.

---

## Phase 4 — Execution Sandbox Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **Fixed Action Registry Pattern**:
   - Implemented registered action modules in `services/execution-sandbox/app/actions/`:
     - `send_email.py`: `SendEmailParams` (`to: EmailStr`, `subject`, `body`)
     - `send_webhook.py`: `SendWebhookParams` (`url: HttpUrl`, `method`, `payload`)
     - `write_log_notification.py`: `WriteLogParams` (`message`, `level`)
     - `run_http_healthcheck.py`: `HealthcheckParams` (`url: HttpUrl`, `expected_status`)
     - `empty_recycle_bin.py`: Explicit host-boundary action raising `ActionNotAvailableError`
2. **MCP Action Server**:
   - Implemented `registry.py` with `REGISTRY` mapping action names to Pydantic parameter schemas and async execution callables.
   - Exposed `GET /mcp/tools` (schema discovery) and `POST /mcp/call` conforming to MCP tool specifications.
   - Enforced zero arbitrary code execution: invalid action names raise `ActionNotRegisteredError` (HTTP 400), invalid params raise Pydantic `ValidationError` (HTTP 400).
3. **Idempotency & Audit Logging**:
   - Implemented `check_and_record_idempotency(automation_id, trigger_window_start)` in `db.py` reading from PostgreSQL `execution_log`. Duplicate calls within the same trigger window short-circuit with status `skipped`.
   - Verified that successful and failed executions log corresponding entries to PostgreSQL `audit_log`.
4. **Automated Verification**:
   - 6/6 pytest test cases in `services/execution-sandbox/tests/test_sandbox.py` passed cleanly.

### Acceptance Criteria Checklist
- [x] Calling `invoke("format_disk", {})` → `ActionNotRegisteredError`, HTTP 400, no fallback path.
- [x] Calling `send_webhook` with an invalid URL → Pydantic validation error, HTTP 400.
- [x] Same `(automation_id, trigger_window_start)` invoked twice → second call short-circuits via `execution_log`, single side effect.
- [x] `empty_recycle_bin` invocation → clean `ActionNotAvailableError`, not a crash.
- [x] All 5 tools discoverable via MCP tools endpoint (`GET /mcp/tools`).
- [x] 6/6 automated sandbox tests pass cleanly.

---

## Phase 5 — Decision Agent Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **LangGraph State Graph Implementation**:
   - Implemented 6 deterministic nodes in `services/decision-agent/app/graph.py`:
     - `receive_approved_plan`: initializes plan state.
     - `check_ambiguities`: evaluates if ambiguities exist in the plan.
     - `ask_user`: pauses graph at LangGraph checkpoint interrupt, sets status to `draft`, logs `ambiguity_asked` to `audit_log`, and returns the clarifying question.
     - `await_user_response`: resumes graph upon receiving user answer, updates plan trigger params, and logs `ambiguity_resolved`.
     - `finalize_trigger_config`: standardizes concrete trigger configuration and sets explicit timezone (default UTC).
     - `persist_automation`: transitions status to `active` and persists to PostgreSQL `automations` table.
     - `handoff_to_trigger_engine`: dispatches configuration to internal trigger runtime.
2. **Draft Expiry Sweeper**:
   - Implemented `sweep_expired_drafts` in `db.py` and exposed `/sweeper/run`. Unanswered drafts older than 24h are auto-archived with `audit_log` reason `'expired_unanswered'`.
3. **Observability & LangSmith Tracing**:
   - Integrated LangSmith tracing (`LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT=nl-automation-platform`), streaming execution spans for all graph transitions.
4. **Automated Verification**:
   - 3/3 pytest test cases in `services/decision-agent/tests/test_decision.py` passed cleanly:
     - Direct resolution of unambiguous plan to active.
     - Interrupt/pause at `ask_user` on ambiguous input ("clean it when it's full") and successful resume via `/resume`.
     - Time-travel test verifying 24h draft expiry auto-archiving.

### Acceptance Criteria Checklist
- [x] "clean it when it's full" → graph pauses at `ask_user`, API returns the clarifying question, resumes correctly when answered to `status='active'`.
- [x] Unanswered draft older than 24h → auto-archived by the sweeper, verified via time-travel test.
- [x] Full trace spans generated across state transitions with LangSmith tracing enabled.
- [x] 3/3 automated decision agent tests pass cleanly.

---

## Phase 6 — Trigger Engine & Queue Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **Time-Based Trigger Scheduling**:
   - Implemented `services/trigger-engine/app/time_triggers.py` using `APScheduler.AsyncIOScheduler`.
   - Explicit timezone conversion: stores user timezone (`trigger.params.timezone`) and converts to UTC for scheduling.
2. **Threshold Watcher & Cooldown Debounce**:
   - Implemented `services/trigger-engine/app/threshold_watcher.py` polling active threshold automations.
   - Built container-reachable metric stand-in in `metrics.py` (`GET /metrics/{metric_name}`, `POST /metrics/{metric_name}`).
   - Implemented cooldown verification: checks `(now - last_fired_at) < cooldown_seconds` (default 300s) to completely eliminate trigger flapping.
3. **Redis Job Queue, Worker & Dead-Letter Queue**:
   - Implemented job enqueueing (`automation_queue`) on trigger fire with `trigger_fired` audit logging.
   - Built background worker in `services/execution-sandbox/app/worker.py` listening to `automation_queue`.
   - Dead-letter handling: after 3 consecutive execution failures, job is placed on `dead_letter` Redis list, and `audit_log` is written with `event_type=action_failed, payload.dead_lettered=true`.
4. **Automated Verification**:
   - 3/3 tests in `services/trigger-engine/tests/test_trigger.py` passed.
   - 7/7 tests in `services/execution-sandbox/tests/test_sandbox.py` passed (including dead-letter queue verification).

### Acceptance Criteria Checklist
- [x] Time-based test automation schedules with UTC conversion.
- [x] Threshold-based test automation fires when condition is met, and a second condition-met poll inside cooldown window is correctly suppressed.
- [x] Forcing an action to always fail → after 3 retries, lands in `dead_letter` queue, visible in `audit_log` with `dead_lettered=true`.

---

## Phase 7 — Frontend & Documentation Polish Complete

**Date:** 2026-09-26  
**Status:** COMPLETE  

### Summary of Work Done
1. **API Gateway Endpoints & Edge Case Hardening**:
   - `POST /api/v1/automations`: Evaluates raw text against intent-parser, routes structured plan through security guardrail pre-gates, checks for duplicate active configurations, and triggers LangGraph decision resolution.
   - Guardrail ordering: Destructive patterns (e.g. `format C: drive`) are caught and blocked via `GUARDRAIL_BLOCKED` before any unparseable fallback, ensuring full audit logging.
   - `POST /api/v1/automations/{id}/resume`: Resumes paused draft automations upon user clarification answer.
   - `GET /api/v1/automations` and `DELETE /api/v1/automations/{id}`: List and archive automations with automatic trigger unregistration.
   - `GET /api/v1/audit` and `GET /api/v1/automations/{id}/audit`: Access immutable PostgreSQL audit logs.
   - 7/7 tests passed in `services/api-gateway/tests/test_gateway.py`.
2. **Next.js 14 Frontend Implementation (`frontend/src/app/page.tsx`)**:
   - Built modern chat-style composer featuring:
     - Real-time Gateway connectivity indicator (`:8080`).
     - Natural language textarea with specification preset prompt chips.
     - Multi-stage pipeline visualizer (Intent Parser → Guardrail Pre-Gate → LangGraph Decision Agent).
     - Guardrail approval and blocked alert banners with category badges and suggested alternatives.
     - Interactive clarification prompt modal for draft automations with immediate resume submission.
     - Verified structured plan preview.
   - Automations List View:
     - Filtering by status (`active`, `draft`, `archived`), trigger metadata, target action, and archive controls.
   - Immutable Audit Trail Viewer:
     - Live 3s polling stream of security events, triggers, execution records, and provider failovers.
   - Verified clean Next.js compilation and server rendering on port 3001.
3. **Documentation Finalization**:
   - `docs/architecture.md`: Updated narrative describing Client, Gateway, Reasoning, Runtime, Data, and Observability layers, with verified mermaid.ink render links for all 3 architecture/sequence diagrams.
   - `docs/api-spec.md`: OpenAPI-derived human-readable documentation with exact schemas, response codes, and endpoints.
   - `docs/security-guardrails.md`: Formal taxonomy documentation covering Stage 0, Stage 1, Stage 2, fail-closed mechanics, and edge case decisions.
   - `docs/roadmap.md`: Updated all phases (Phase 0 through Phase 7) to Complete.
4. **End-to-End System Acceptance**:
   - Verified all 35 automated tests pass cleanly across all 6 microservices:
     - `nl-intent-parser`: 10/10 tests passing
     - `nl-guardrail`: 5/5 tests passing
     - `nl-execution-sandbox`: 7/7 tests passing
     - `nl-decision-agent`: 3/3 tests passing
     - `nl-trigger-engine`: 3/3 tests passing
     - `nl-api-gateway`: 7/7 tests passing
   - Live end-to-end integration verified from host to containerized platform:
     - Canonical recycle bin threshold flow creates active automation.
     - Canonical time-based email flow schedules correctly with UTC conversion.
     - Ambiguous intent pauses at draft status with clarifying question, and resumes to active upon user response.
     - Destructive intent blocked by guardrail with HTTP 400 `GUARDRAIL_BLOCKED`.
     - Compound intent rejected with HTTP 422 `compound_automation_rejected`.
     - System events recorded immutably in PostgreSQL `audit_log`.

### Acceptance Criteria Checklist
- [x] Full happy path works end-to-end via `docker compose up` for the recycle-bin example and one time-based example.
- [x] Next.js chat-style composer allows typing prompt, viewing parsed plan, guardrail result, clarifying question, confirmation, and listing active status.
- [x] All 12 edge cases from the specification table have automated test coverage and pass cleanly.
- [x] All 35 unit/integration tests across all microservices pass.
- [x] Documentation complete (`architecture.md`, `api-spec.md`, `security-guardrails.md`, `roadmap.md`, `build-log.md`).
