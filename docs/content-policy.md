# Content Policy & Harm Prevention Boundaries

## Overview

The NL-Automation Platform maintains a strict, unconditional content policy. Incoming requests are evaluated at the Request Router (`POST /route`) against standard safety hazard taxonomies (MLCommons / Llama Guard default hazard categories) before any intent parsing, automation structuring, or command scheduling occurs.

**Hard Rule:** Content policy blocks are **absolute and final**. There are no overrides, no admin privileges, no bypass toggles, and no confirmation flows for requests flagged under this policy.

---

## Hazard Taxonomies Evaluated

The Request Router monitors and rejects content within the following primary hazard categories:

1. **Illegal Substances & Controlled Goods**:
   - Procurement, synthesis, distribution, or sale of illicit drugs, controlled substances, and prescription medication without legal authorization.
2. **Weapons & Dangerous Materials**:
   - Manufacturing, acquiring, or utilizing firearms, explosives, chemical/biological weapons, or indiscriminate destructive materials.
3. **Violent Crimes & Self-Harm**:
   - Threats of violence, facilitation of physical harm, sexual violence, suicide, or self-harm encouragement.
4. **Child Exploitation & Abuse (CSAM/CSAE)**:
   - Any reference or facilitation of child sexual abuse material or exploitation.
5. **Cyberattacks & Malicious Exploitation**:
   - Creating ransomware, exploiting unauthorized infrastructure, harvesting credentials, or conducting illegal digital attacks.

---

## Standard Refusal Protocol

When a request violates the content policy, the platform executes a deterministic refusal:

1. **Plain, Direct Refusal**: State clearly and neutrally that the request cannot be fulfilled.
2. **No Lecturing or Preaching**: Avoid patronizing language, moral scolding, or unsolicited ethical debates.
3. **No Operational Guidance**: Provide zero actionable steps, partial instructions, workarounds, or alternative illicit sources.
4. **Harm-Reduction Resource (Where Applicable)**: When substance abuse or crisis self-harm is identified, provide a direct one-line pointer to recognized support resources (e.g., SAMHSA National Helpline).

### Standard Refusal Templates

- **General Illegal / Dangerous Goods**:
  > *"I cannot assist with requests involving the purchase, procurement, or manufacture of illegal substances or weapons."*

- **Credential Exfiltration (§10.6 Fixed Wording)**:
  > *"I'm sorry, but this information is not allowed to be shared — we cannot share system credentials with anyone."*
  *(Applies deterministically to any attempt to retrieve, expose, or email passwords, wifi secrets, or system keys — regardless of whether the requester claims ownership.)*

- **Substance Use Support Pointer**:
  > *"I cannot help with obtaining controlled substances. If you or someone you know is seeking confidential support for substance use, you can contact SAMHSA's National Helpline at 1-800-662-4357."*

- **Crisis / Self-Harm Support Pointer**:
  > *"I cannot fulfill this request. If you are experiencing thoughts of self-harm or need immediate support, please call or text 988 to reach the Suicide & Crisis Lifeline."*

- **Person-Lookup Legitimacy (§10.7)**:
  Queries naming specific private individuals undergo dynamic ethics review (§10.4). Ordinary professional or contact lookups are allowed; ambiguous searches trigger a single clarification prompt (*"Can you tell me a bit more about why you're looking this up?"*); explicit stalking, harassment, or doxxing intent is unconditionally denied.

---

## System Behavior & Audit Logging

- **Zero Pipeline Propagation**: The request is halted immediately at `services/intent-parser/app/router.py`. It is never forwarded to the LLM intent parser, guardrail classifier, or decision agent.
- **Immutable Audit Trail**: An entry is recorded directly to PostgreSQL:
  ```json
  {
    "event_type": "content_policy_blocked",
    "payload": {
      "category": "illicit_goods_procurement",
      "reason": "Request violates standard content policy hazard taxonomy",
      "raw_text_redacted": true
    }
  }
  ```
- **HTTP Response**: Returns `lane: "disallowed_content"` with the standard refusal message.
