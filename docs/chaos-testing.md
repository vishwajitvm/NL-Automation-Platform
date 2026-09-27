# Chaos Testing Plan

## Scenarios

- [ ] Redis killed mid-job: Job resumes from queue once Redis restarts.
- [ ] Guardrail killed mid-request: Fails closed, request blocked.
- [ ] Host-agent killed mid-job: Job times out server-side, dead-letters.
- [ ] Postgres killed mid-write: Gateway returns 503.
- [ ] Ethics agent's model provider down: Falls back through provider chain, then fails closed.
