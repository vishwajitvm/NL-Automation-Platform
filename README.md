# ⚡ NL-Automation Platform

> **Turn plain English sentences into safe, dependable computer automations — with zero coding and zero guesswork.**

[![Docker Powered](https://img.shields.io/badge/docker-ready-blue?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests Passing](https://img.shields.io/badge/tests-76%2F76%20passing-brightgreen)](file:///c:/python/NL-Automation%20Platform/docs/build-log.md)
[![Free Tier Only](https://img.shields.io/badge/cost-$0%20free--tier-purple)]()
[![Security Shield](https://img.shields.io/badge/guardrails-Llama%20Guard%204-red)]()
[![TraceNest Observability](https://img.shields.io/badge/TraceNest-v0.1.18%20enabled-blueviolet)](http://localhost:8080/tracenest)

---

## 🌟 What is this, and why does it exist? (The Simple Story)

Have you ever wished you could just tell your computer:
* *"Hey, clean out my Recycle Bin whenever it reaches 80% full."*
* *"Email me a weekly summary every Friday at 5:00 PM."*
* *"Check if my company website is online every 10 minutes, and alert me if it goes down."*

In the past, setting up routines like that meant you had to be a software developer. You had to write Python scripts, configure confusing cron jobs, mess with API keys, and constantly worry: **"What if my script has a bug and accidentally deletes the wrong files?"**

The **NL-Automation Platform** solves this problem completely. 

Think of it as having **a smart translator**, **a strict security guard**, and **a dependable assistant** all working together on your computer:
1. **You speak everyday English:** You type what you want in plain words.
2. **The system understands:** It figures out *when* to do it (the trigger) and *what* to do (the action).
3. **The security guard inspects it:** It checks whether the request is completely safe before touching anything. If someone types *"Format my hard drive"*, it slams the brakes on immediately.
4. **It asks if you are vague:** If you say *"Clean it when it's full"*, it politely stops and asks: *"What percentage do you consider full?"*
5. **It works reliably in the background:** It schedules the job and executes it safely 24 hours a day, 7 days a week.

---

## 🚀 What Can It Do?

### 1. Smart Cleanups & Threshold Triggers
* **You type:** `"Clean my recycle bin when it reaches 80%"`
* **What happens:** The system sets up a background watcher that checks storage levels. When disk usage crosses 80%, it triggers a safe cleanup action — and enforces a 5-minute cooldown so it won't repeatedly fire if the number bounces around.

### 2. Time-Based Routines
* **You type:** `"Email me a summary every Friday at 5pm"`
* **What happens:** The system detects your local timezone, translates "Friday at 5pm" into universal scheduling time (UTC), and schedules an automated email dispatch right on time every week.

### 3. Webhook Alerts & Uptime Checks
* **You type:** `"Check if website https://example.com is healthy every 10 minutes"`
* **What happens:** The platform monitors the web address and logs the status to an audit log.

### 4. Interactive Clarification (When You Are Vague)
* **You type:** `"Clean the recycle bin when it is full"`
* **What happens:** The AI notices that *"full"* is ambiguous. It doesn't guess! It saves your request as a **draft** and pops up an alert asking: *"At what percentage of fullness would you like the recycle bin emptied?"* Once you reply *"80%"*, it activates the rule.

### 5. Military-Grade Safety Shield (Blocking Dangerous Actions)
* **You type:** `"Format C: drive every night"` or `"Delete all system files"`
* **What happens:** **BLOCKED.** The multi-stage security classifier immediately flags the request as a destructive file system operation (`destructive_fs_op`), writes a permanent security violation record into the flight recorder, and suggests a safe alternative like monitoring disk usage instead.

### 6. Rejecting Confusing Double Commands
* **You type:** `"Clean bin at 80% and email me weekly"`
* **What happens:** It rejects the sentence with an explanation: *"Please describe one automation at a time."* This ensures every rule has its own clear trigger, condition, and safety check.

---

## 🧠 How It Works: The 5-Step Journey of Your Sentence

```
    [Your Sentence] 
           │
           ▼
 1. The Translator       ──► Converts everyday words into an Action Blueprint
           │
           ▼
 2. The Security Guard   ──► Inspects the blueprint for hacking or dangerous commands
           │
           ▼
 3. The Clarifier        ──► Asks you a question if you left out important details
           │
           ▼
 4. The 24/7 Watchman    ──► Watches the clock or monitors your disk usage
           │
           ▼
 5. The Safe Hands       ──► Executes only pre-approved, safe actions
```

1. **The Translator (Intent Parser):** Powered by Google Gemini 2.5 Flash (with Groq as automatic backup). It takes your sentence and figures out:
   - What should start it? (e.g. A specific time, or a percentage threshold).
   - What should it do? (e.g. Send an email, empty the bin, call a webhook).
2. **The Security Guard (Guardrails):** Powered by Meta's Llama Guard 4 and Prompt Guard 2. It checks against malware, data theft, and destructive commands. **If the guardrail is ever down or offline, the platform fails closed — nothing dangerous ever slips through.**
3. **The Clarifier (Decision Agent):** Powered by LangGraph state machines. If your request is missing key parameters (like an exact percentage or time), it pauses safely and waits for your answer.
4. **The 24/7 Watchman (Trigger Engine):** Runs in the background using APScheduler and Redis. It checks conditions smoothly without slowing down your computer.
5. **The Safe Hands (Execution Sandbox):** The actual runner. Crucially, **it can only run actions from a locked list of pre-approved tasks.** It cannot run arbitrary computer terminal commands or unknown scripts.

---

## 🗺️ Visual Architecture & Data Flow

### 1. High-Level System Architecture

Here is how all the pieces connect together inside the system:

```mermaid
flowchart TD
    User([You / User]):::client -->|Types: 'Clean my recycle bin at 80%'| UI[Web Interface]:::client
    UI -->|Sends to| Gateway[API Gateway - The Front Desk]:::gateway
    
    subgraph Brain ['The AI Brain: Understanding & Safety']
        Gateway -->|1. Translates English| Parser[Intent Parser: Breaks sentence into Trigger & Action]:::brain
        Parser -->|2. Safety Inspection| Guard[Security Guard: Blocks dangerous or hacking commands]:::security
        Guard -->|3. Clarification Check| Agent[Decision Agent: Asks clarifying questions if vague]:::brain
    end
    
    subgraph Runtime ['The Automation Runtime: Watching & Doing']
        Agent -->|Registers Rule| Engine[Trigger Engine: Watches time & system metrics 24/7]:::runtime
        Engine -->|Condition Met!| Queue[Job Queue: Orders tasks safely]:::runtime
        Queue -->|Executes Action| Sandbox[Execution Sandbox: Runs safe, pre-approved actions only]:::runtime
    end
    
    subgraph History ['Memory & Flight Recorder']
        Sandbox -->|Records outcome| Database[(PostgreSQL Database: Stores automations & audit logs)]:::data
        Sandbox -->|Agent reasoning traces| Tracing[LangSmith Tracing]:::data
    end

    classDef client fill:#3b82f6,stroke:#1d4ed8,color:#ffffff,stroke-width:2px;
    classDef gateway fill:#6366f1,stroke:#4338ca,color:#ffffff,stroke-width:2px;
    classDef brain fill:#8b5cf6,stroke:#6d28d9,color:#ffffff,stroke-width:2px;
    classDef security fill:#ef4444,stroke:#b91c1c,color:#ffffff,stroke-width:2px;
    classDef runtime fill:#10b981,stroke:#047857,color:#ffffff,stroke-width:2px;
    classDef data fill:#f59e0b,stroke:#b45309,color:#ffffff,stroke-width:2px;
```

<div align="center">
  <img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBVc2VyKFtZb3UgLyBVc2VyXSk6OjpjbGllbnQgLS0+fFR5cGVzOiAnQ2xlYW4gbXkgcmVjeWNsZSBiaW4gYXQgODAlJ3wgVUlbV2ViIEludGVyZmFjZV06OjpjbGllbnQKICAgIFVJIC0tPnxTZW5kcyB0b3wgR2F0ZXdheVtBUEkgR2F0ZXdheSAtIFRoZSBGcm9udCBEZXNrXTo6OmdhdGV3YXkKICAgIAogICAgc3ViZ3JhcGggQnJhaW4gWydUaGUgQUkgQnJhaW46IFVuZGVyc3RhbmRpbmcgJiBTYWZldHknXQogICAgICAgIEdhdGV3YXkgLS0+fDEuIFRyYW5zbGF0ZXMgRW5nbGlzaHwgUGFyc2VyW0ludGVudCBQYXJzZXI6IEJyZWFrcyBzZW50ZW5jZSBpbnRvIFRyaWdnZXIgJiBBY3Rpb25dOjo6YnJhaW4KICAgICAgICBQYXJzZXIgLS0+fDIuIFNhZmV0eSBJbnNwZWN0aW9ufCBHdWFyZFtTZWN1cml0eSBHdWFyZDogQmxvY2tzIGRhbmdlcm91cyBvciBoYWNraW5nIGNvbW1hbmRzXTo6OnNlY3VyaXR5CiAgICAgICAgR3VhcmQgLS0+fDMuIENsYXJpZmljYXRpb24gQ2hlY2t8IEFnZW50W0RlY2lzaW9uIEFnZW50OiBBc2tzIGNsYXJpZnlpbmcgcXVlc3Rpb25zIGlmIHZhZ3VlXTo6OmJyYWluCiAgICBlbmQKICAgIAogICAgc3ViZ3JhcGggUnVudGltZSBbJ1RoZSBBdXRvbWF0aW9uIFJ1bnRpbWU6IFdhdGNoaW5nICYgRG9pbmcnXQogICAgICAgIEFnZW50IC0tPnxSZWdpc3RlcnMgUnVsZXwgRW5naW5lW1RyaWdnZXIgRW5naW5lOiBXYXRjaGVzIHRpbWUgJiBzeXN0ZW0gbWV0cmljcyAyNC83XTo6OnJ1bnRpbWUKICAgICAgICBFbmdpbmUgLS0+fENvbmRpdGlvbiBNZXQhfCBRdWV1ZVtKb2Job3B0cyBPcmRlcnMgdGFza3Mgc2FmZWx5XTo6OnJ1bnRpbWUKICAgICAgICBRdWV1ZSAtLT58RXhlY3V0ZXMgQWN0aW9ufCBTYW5kYm94W0V4ZWN1dGlvbiBTYW5kYm94OiBSdW5zIHNhZmUsIHByZS1hcHByb3ZlZCBhY3Rpb25zIG9ubHldOjo6cnVudGltZQogICAgZW5kCiAgICAKICAgIHN1YmdyYXBoIEhpc3RvcnkgWydNZW1vcnkgJiBGbGlnaHQgUmVjb3JkZXInXQogICAgICAgIFNhbmRib3ggLS0+fFJlY29yZHMgb3V0Y29tZXwgRGF0YWJhc2VbKFBvc3RncmVTUUwgRGF0YWJhc2U6IFN0b3JlcyBhdXRvbWF0aW9ucyAmIGF1ZGl0IGxvZ3MpXTo6OmRhdGEKICAgICAgICBTYW5kYm94IC0tPnxBZ2VudCByZWFzb25pbmcgdHJhY2VzfCBUcmFjaW5nW0xhbmdTbWl0aCBUcmFjaW5nKTo6OmRhdGEKICAgIGVuZAoKICAgIGNsYXNzRGVmIGNsaWVudCBmaWxsOiMzYjgyZjYsc3Ryb2tlOiMxZDRlZDgsY29sb3I6I2ZmZmZmZixzdHJva2Utd2lkdGg6MnB4OwogICAgY2xhc3NEZWYgZ2F0ZXdheSBmaWxsOiM2MzY2ZjEsc3Ryb2tlOiM0MzM4Y2EsY29sb3I6I2ZmZmZmZixzdHJva2Utd2lkdGg6MnB4OwogICAgY2xhc3NEZWYgYnJhaW4gZmlsbDojOGI1Y2Y2LHN0cm9rZTojNmQyOGQ5LGNvbG9yOiNmZmZmZmYsc3Ryb2tlLXdpZHRoOjJweDsKICAgIGNsYXNzRGVmIHNlY3VyaXR5IGZpbGw6I2VmNDQ0NCxzdHJva2U6I2I5MWMxYyxjb2xvcjojZmZmZmZmLHN0cm9rZS13aWR0aDoycHg7CiAgICBjbGFzc0RlZiBydW50aW1lIGZpbGw6IzEwYjk4MSxzdHJva2U6IzA0Nzg1Nyxjb2xvcjojZmZmZmZmLHN0cm9rZS13aWR0aDoycHg7CiAgICBjbGFzc0RlZiBkYXRhIGZpbGw6I2Y1OWUwYixzdHJva2U6I2I0NTMwOSxjb2xvcjojZmZmZmZmLHN0cm9rZS13aWR0aDoycHg7" alt="System Architecture Overview" width="850"/>
  <p><em>Figure 1: Bird's-Eye View of the Platform Architecture</em></p>
</div>

---

### 2. Conversation Flow: Creating an Automation & Resolving Ambiguity

Here is what happens when you type an automation that needs clarification:

```mermaid
sequenceDiagram
    autonumber
    actor User as You (The User)
    participant UI as Web Dashboard
    participant API as API Gateway
    participant AI as AI Translator (Gemini)
    participant Guard as Safety Guard (Llama Guard)
    participant Agent as Decision Agent (LangGraph)
    participant DB as System Database

    User->>UI: Type: 'Clean recycle bin when it is full'
    UI->>API: Send text
    API->>AI: What does the user want to do?
    AI-->>API: Wants to empty recycle bin, but percentage is vague!
    API->>Guard: Is this safe to run?
    Guard-->>API: Safe! No dangerous commands found.
    API->>Agent: Resolve details
    Agent-->>UI: Ask user: 'What percentage do you consider full?'
    User->>UI: Types: '80%'
    UI->>Agent: Resumes with answer: '80%'
    Agent->>DB: Save active rule: Trigger at 80%, Action: Empty bin
    UI-->>User: Success! Automation is now live and watching.
```

<div align="center">
  <img src="https://mermaid.ink/img/c2VxdWVuY2VEaWFncmFtCiAgICBhdXRvbnVtYmVyCiAgICBhY3RvciBVc2VyIGFzIFlvdSAoVGhlIFVzZXIpCiAgICBwYXJ0aWNpcGFudCBVSSBhcyBXZWIgRGFzaGJvYXJkCiAgICBwYXJ0aWNpcGFudCBBUEkgYXMgQVBJIEdhdGV3YXkKICAgIHBhcnRpY2lwYW50IEFJIGFzIEFJIFRyYW5zbGF0b3IgKEdlbWluaSkKICAgIHBhcnRpY2lwYW50IEd1YXJkIGFzIFNhZmV0eSBHdWFyZCAoTGxhbWEgR3VhcmQpCiAgICBwYXJ0aWNpcGFudCBBR0VOVCBhcyBEZWNpc2lvbiBBZ2VudCAoTGFuZ0dyYXBoKQogICAgcGFydGljaXBhbnQgREIgYXMgU3lzdGVtIERhdGFiYXNlCgogICAgVXNlci0+PlVJOiBUeXBlOiAnQ2xlYW4gcmVjeWNsZSBiaW4gd2hlbiBpdCBpcyBmdWxsJwogICAgVUktPj5BUEk6IFNlbmQgdGV4dAogICAgQVBJLT4+QUk6IFdoYXQgZG9lcyB0aGUgdXNlciB3YW50IHRvIGRvPwogICAgQUktLT4+QVBJOiBXYW50cyB0byBlbXB0eSByZWN5Y2xlIGJpbiwgYnV0IHBlcmNlbnRhZ2UgaXMgdmFndWUhCiAgICBBUEktPj5HdWFyZDogSXMgdGhpcyBzYWZlIHRvIHJ1bj8KICAgIEd1YXJkLS0+PkFQSTogU2FmZSEgTm8gZGFuZ2Vyb3VzIGNvbW1hbmRzIGZvdW5kLgogICAgQVBJLT4+QUdFTlQ6IFJlc29sdmUgZGV0YWlscwogICAgQUdFTlQtLT4+VUk6IEFzayB1c2VyOiAnV2hhdCBwZXJjZW50YWdlIGRvIHlvdSBjb25zaWRlciBmdWxsPycKICAgIFVzZXItPj5VSTogVHlwZXM6ICc4MCUnCiAgICBVSS0+PkFHRU5UOiBSZXN1bWVzIHdpdGggYW5zd2VyOiAnODAlJwogICAgQUdFTlQtPj5EQjogU2F2ZSBhY3RpdmUgcnVsZTogVHJpZ2dlciBhdCA4MCUsIEFjdGlvbjogRW1wdHkgYmluCiAgICBVSS0tPj5Vc2VyOiBTdWNjZXNzISBBdXRvbWF0aW9uIGlzIG5vdyBsaXZlIGFuZCB3YXRjaGluZy4K" alt="Creation and Ambiguity Sequence" width="850"/>
  <p><em>Figure 2: Clarification and Approval Sequence Flow</em></p>
</div>

---

### 3. Execution Flow: How It Fires in the Background

Here is what happens behind the scenes while you are away:

```mermaid
sequenceDiagram
    autonumber
    participant Watcher as Trigger Engine (The Watchman)
    participant Metric as System Metric (Disk Usage)
    participant Queue as Redis Queue (Task Line)
    participant Worker as Execution Worker (The Doer)
    participant Log as Flight Recorder (Audit Log)

    loop Every 5 seconds
        Watcher->>Metric: Is recycle bin >= 80% full?
    end
    Metric-->>Watcher: Yes! It just hit 85%!
    Watcher->>Queue: Put 'Empty Bin' task in queue
    Queue->>Worker: Dispatch task to execution worker
    Worker->>Worker: Check safety & run pre-approved action
    Worker->>Log: Record success: 'Recycle bin cleaned at 85% full'
    Worker->>Watcher: Start 5-minute cooldown (prevent spamming)
```

<div align="center">
  <img src="https://mermaid.ink/img/c2VxdWVuY2VEaWFncmFtCiAgICBhdXRvbnVtYmVyCiAgICBwYXJ0aWNpcGFudCBXYXRjaGVyIGFzIFRyaWdnZXIgRW5naW5lIChUaGUgV2F0Y2htYW4pCiAgICBwYXJ0aWNpcGFudCBNZXRyaWMgYXMgU3lzdGVtIE1ldHJpYyAoRGlzayBVc2FnZSkKICAgIHBhcnRpY2lwYW50IFF1ZXVlIGFzIFJlZGlzIFF1ZXVlIChUYXNrIExpbmUpCiAgICBwYXJ0aWNpcGFudCBXb3JrZXIgYXMgRXhlY3V0aW9uIFdvcmtlciAoVGhlIERvZXIpCiAgICBwYXJ0aWNpcGFudCBMb2cgYXMgRmxpZ2h0IFJlY29yZGVyIChBdWRpdCBMb2cpCgogICAgbG9vcCBFdmVyeSA1IHNlY29uZHMKICAgICAgICBXYXRjaGVyLT4+TWV0cmljOiBJcyByZWN5Y2xlIGJpbiA+PSA4MCUgZnVsbD8KICAgIGVuZAogICAgTWV0cmljLS0+PldhdGNoZXI6IFllcyEgSXQganVzdCBoaXQgODUlIQogICAgV2F0Y2hlci0+PlF1ZXVlOiBQdXQgJ0VtcHR5IEJpbicgdGFzayBpbiBxdWV1ZQogICAgUXVldWUtPj5Xb3JrZXI6IERpc3BhdGNoIHRhc2sgdG8gZXhlY3V0aW9uIHdvcmtlcgogICAgV29ya2VyLT4+V29ya2VyOiBDaGVjayBzYWZldHkgJiBydW4gcHJlLWFwcHJvdmVkIGFjdGlvbgogICAgV29ya2VyLT4+TG9nOiBSZWNvcmQgc3VjY2VzczogJ1JlY3ljbGUgYmluIGNsZWFuZWQgYXQgODUlIGZ1bGwnCiAgICBXb3JrZXItPj5XYXRjaGVyOiBTdGFydCA1LW1pbnV0ZSBjb29sZG93biAocHJldmVudCBzcGFtbWluZykK" alt="Background Trigger Flow" width="850"/>
  <p><em>Figure 3: Background Trigger, Queue, and Execution Sequence</em></p>
</div>

---

## 💻 How to Use It (Step-by-Step)

You do **not** need to install Python, Node.js, databases, or Redis on your computer. Everything runs completely isolated inside Docker!

### Step 1: Requirements
* Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, Mac, or Linux).

### Step 2: Configure Environment Keys
Copy the example environment file:
```bash
cp .env.example .env
```
Open `.env` in any text editor and paste your free API keys (like `GEMINI_API_KEY`, `GROQ_API_KEY`, and `MISTRAL_API_KEY`). All models use genuine $0 free tiers.

### Step 3: Start the Platform
In your terminal, navigate to the folder and run:
```bash
docker compose up -d
```
Docker will start all containers:
* 🌐 `nl-frontend` — The web dashboard
* 🚪 `nl-api-gateway` — The central API router
* 🤖 `nl-intent-parser` — The Gemini language translator
* 🛡️ `nl-guardrail` — The Llama Guard safety inspector
* 🧭 `nl-decision-agent` — The LangGraph decision agent
* ⏱️ `nl-trigger-engine` — The time and metric watcher
* 📦 `nl-execution-sandbox` — The isolated action worker
* 🗄️ `nl-postgres` & `nl-redis` — Storage and task queue

### Step 4: Open Your Browser
Open your browser and visit:
👉 **[http://localhost:3001](http://localhost:3001)**

---

## 🖥️ A Tour of the Web Interface

When you open **[http://localhost:3001](http://localhost:3001)**, you will see three main tabs:

### 1. ⌨️ The Composer Tab
* **Natural Language Textbox:** Type your automation in English.
* **Specification Test Chips:** Single-click preset buttons to try real scenarios:
  - *Recycle Bin Threshold (Happy Path)*
  - *Weekly Email (Time-Based)*
  - *Ambiguous Request (Requires Clarification)*
  - *Destructive Request (Guardrail Blocked)*
  - *Compound Automation (422 Rejection)*
* **Visual Pipeline Cards:** Watch your prompt get parsed into a trigger and an action, see the green **"Guardrail Approved"** shield, or see the red **"Guardrail Blocked"** badge explaining why a request was rejected.
* **Clarification Dialog:** If your prompt is ambiguous, an interactive yellow card lets you type the answer and resume the automation with one click!

### 2. 📋 The Automations Tab
* See all your live, draft, and archived automations.
* Shows when each automation was created, what triggered it, and what action it runs.
* Click **Archive** anytime to cleanly stop and deactivate a rule.

### 3. 📜 The Audit Trail Tab
* **The Flight Recorder:** Every single thing that happens in the system is immutably recorded in PostgreSQL.
* View timestamps and raw details for every event: `guardrail_approved`, `trigger_registered`, `trigger_fired`, `action_executed`, `provider_failover`, and `ambiguity_resolved`.
* Turn on **Live Poll (3s)** to watch events stream into the UI in real time!

### 4. 🔍 TraceNest Live Observability Dashboard
* **Instant Log Inspection (`http://localhost:8080/tracenest`):**
  - Live, color-coded stream of all microservice operations (`TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - Dropdown selector allows instant switching between all 6 backend services (`api-gateway`, `intent-parser`, `guardrail`, `decision-agent`, `trigger-engine`, `execution-sandbox`).
  - Detailed metadata on every event: service name, function, line number, duration (`duration_ms`), and execution context.
  - Automatic secret redaction scrubs passwords, tokens, and API keys before they hit the disk.
  - Direct 1-click access via the **"TraceNest Logs"** button in the Web UI navigation bar.

---

## 🔒 Security: How We Keep Your Computer Safe

1. **Zero Arbitrary Code Execution:** The system **never** generates Python code or shell commands on the fly. It can only call tools from a strict, hard-coded registry:
   - **Sandbox Actions**: `send_email`, `send_webhook`, `write_log_notification`, `run_http_healthcheck`.
   - **Host Agent Actions**: `check_disk_usage`, `list_drives`, `clean_temp_and_cache`, `empty_trash`, `preview_delete_path`, `delete_path`.
   - **Isolated Browser Actions**: `browser_open_url`, `browser_click_element`, `browser_fill_input`, `browser_extract_text`, `browser_close`.
2. **Hard Filesystem Denylist:** Any attempt to target drive roots (`C:\`, `/`), Windows directories (`C:\Windows`), or system folders triggers an immediate refusal without even prompting.
3. **Multi-Step SweetAlert2 Confirmation:** Destructive operations (like `delete_path`) require passing three separate human confirmations:
   - *Step 1:* Dry-run summary of total files and bytes to be deleted.
   - *Step 2:* Explicitly typing the target folder path to prevent accidental clicks.
   - *Step 3:* A mandatory 3-second disabled countdown with a vivid red warning banner before the confirm button enables.
4. **Isolated Sandboxed Browser Profile:** Managed browser automation operates strictly in a dedicated Playwright Chromium profile (`~/.nl-automation/browser-profile`). It never touches your personal Chrome/Firefox profiles, bookmarks, or banking cookies.
5. **Fail-Closed Policy:** If Groq, OpenAI Safeguard, or any safety API is unreachable, the platform **blocks the request**. It never fails open.
6. **Idempotency Guarantee:** If a trigger fires twice accidentally within the same minute, the database checks the execution log and skips the duplicate so side effects never happen twice.
7. **Cooldown Windows:** Threshold automations have a default 5-minute cooldown to prevent notification storms or trigger flapping.

---

## 💰 100% Free-Tier Architecture

This platform was purposely built to use **only free-tier tools and models**, with automatic failover so you never face unexpected costs:

| Role | Technology | Cost / Quota |
|---|---|---|
| **Natural Language Parsing** | Google Gemini 2.5 Flash | Free (500 requests/day via Google AI Studio) |
| **Parsing Fallback** | Groq Llama 3.3 70B & OpenRouter | Free tiers |
| **Safety Classification** | Meta Llama Guard 4 (12B) on Groq | Free tier |
| **Prompt Injection Defense** | Meta Prompt Guard 2 (86M) on Groq | Free tier |
| **Decision & Clarification** | Mistral AI & LangGraph | Free tier |
| **Observability & Tracing** | LangSmith & TraceNest | Free tier |
| **Database & Queue** | PostgreSQL 16 & Redis 7 | Open Source (Self-Hosted in Docker) |
| **Frontend & API** | Next.js 14 & FastAPI | Open Source (Self-Hosted in Docker) |

---

## ❓ Frequently Asked Questions (FAQ)

#### Can this platform accidentally format my hard drive or delete my files?
**No.** The execution engine has no code or commands capable of formatting drives or deleting arbitrary directories. In addition, any mention of destructive disk formatting is blocked by the security pre-gate and the Llama Guard 4 classifier before anything is ever created.

#### What happens if I type something that makes no sense (like gibberish)?
The intent parser will politely respond: *"I couldn't understand that."* It will not guess or execute random tasks.

#### What if Gemini or Groq is slow or temporarily down?
The system features an automatic failover chain:
`Gemini 2.5 Flash ──► Groq Llama 3.3 ──► OpenRouter ──► Deterministic Rules`
If an upstream provider returns a 429 (rate limit) or 5xx error, it switches providers automatically and records a `provider_failover` event in your audit trail.

#### Can I shut it down anytime?
Yes! Simply run:
```bash
docker compose down
```
All your automations and audit logs will be safely stored in the Docker volumes and will be waiting for you the next time you turn it on.

---

## 📚 Technical Documentation Directory

For deep-dive technical specifications and architectural logs, see the [`docs/`](file:///c:/python/NL-Automation%20Platform/docs/) folder:
* [Architecture Blueprint & Layers (`docs/architecture.md`)](file:///c:/python/NL-Automation%20Platform/docs/architecture.md)
* [Full API Reference & Schemas (`docs/api-spec.md`)](file:///c:/python/NL-Automation%20Platform/docs/api-spec.md)
* [Security & Guardrail Taxonomy (`docs/security-guardrails.md`)](file:///c:/python/NL-Automation%20Platform/docs/security-guardrails.md)
* [Roadmap & Phase Tracker (`docs/roadmap.md`)](file:///c:/python/NL-Automation%20Platform/docs/roadmap.md)
* [Step-by-Step Engineering Build Log (`docs/build-log.md`)](file:///c:/python/NL-Automation%20Platform/docs/build-log.md)

---

<div align="center">
  <sub>Built with ❤️ using Antigravity, Docker, FastAPI, Next.js, and Modern Open AI Models.</sub>
</div>
