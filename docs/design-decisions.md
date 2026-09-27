# Key Design Decisions

## 1. Why LangGraph over a hand-rolled state machine?
For the decision agent, we needed a robust state machine that could pause execution when ambiguity arose (e.g., asking the user for clarification) and resume precisely where it left off once the user responded. LangGraph's native checkpointer handles state persistence seamlessly using Postgres. This gave us the interrupt/resume capabilities for free rather than needing to build and maintain a custom persistent state machine.

## 2. Why fail-closed for safety checks?
In an automation platform with access to the host filesystem, any failure in a safety check must result in an immediate block, not an implicit approval. If the dynamic ethics agent or the Llama Guard 4 classifier is unreachable or times out, the system assumes the worst and halts the request. This ensures that no destructive or harmful action slips through just because a backend service hiccuped.

## 3. Why a separate Host-Agent?
Since every other service in this platform runs in isolated Docker containers, they fundamentally cannot see or interact with the user's host OS—its filesystem, its running processes, its mounted drives, or its Trash directory. A dedicated Host-Agent, running outside Docker directly on the OS, bridges this gap securely by pulling jobs from the API gateway rather than exposing an open port, keeping the boundary impenetrable.

## 4. Deterministic rules vs. Reasoning agent
We use deterministic rules (like the hard denylist for root directories and the fixed regex rejection for credentials) instead of leaving them entirely to the Dynamic Ethics Agent's judgment. While LLMs are excellent at reasoning about novel scenarios, they can occasionally be manipulated or hallucinate. By keeping the most critical boundaries (system credentials and drive-root wipe) as non-negotiable code-level constraints, we ensure they can never be bypassed, while the reasoning agent catches the vast long-tail of ambiguous requests.
