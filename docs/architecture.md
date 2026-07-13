# SecureBot — Architecture

SecureBot is a single-service FastAPI application that proxies chat messages to a local Ollama LLM instance and renders responses in a browser-based UI. This document describes the components, data flow, trust boundaries, and the security controls applied in the patched version.

---

## Components

| Component | Technology | Role |
|---|---|---|
| Browser UI | Vanilla JS + HTML | Chat input/display, client-side history state |
| Backend server | FastAPI (Python) | Prompt assembly, pre/post filters, Ollama relay |
| LLM runtime | Ollama (`llama3.1:8b`) | Text generation |
| Container | Docker Compose | Isolates the FastAPI server; connects to host Ollama |

---

## Request Data Flow

```
1. User types a message in the browser.

2. Browser JS sends POST /api/chat:
   {
     "message": "<user input>",
     "history": [ ...prior turns from JS-side array... ]
   }

3. FastAPI chat() handler:
   a. Parses body.
   b. [V1 control] Checks user_message against PROMPT_EXTRACTION_TRIGGERS.
      → If matched: returns SAFE_REFUSAL immediately, Ollama is never called.
   c. Builds messages array: [system_prompt, ...history, user_message]
   d. POSTs to Ollama /api/chat.

4. Ollama generates a response.

5. FastAPI post-call filters:
   a. [V1 control] contains_leaked_content() — if any LEAKED_CONTENT_MARKERS
      found in model reply, replace entire reply with SAFE_REFUSAL.
   b. [V3 control] contains_action_command() — if ACTION_COMMAND_PATTERN
      matches model reply, replace reply with SAFE_ACTION_MESSAGE and
      add a blocked-action entry (executed: false).

6. JSONResponse returned to browser.

7. Browser renders response:
   a. [V2 control] addBubble() uses textContent (not innerHTML) for model output.
   b. If actions_executed present: displays notice with action + status.
```

---

## Trust Boundaries

### Boundary 1: Browser ↔ FastAPI

- **User message** — fully attacker-controlled. Checked before reaching the model.
- **History array** — fully attacker-controlled. The server trusts this verbatim and includes it in the model context (V6, open finding).
- **No authentication** — `/api/chat` accepts any POST with no identity check (V4, open finding).

### Boundary 2: FastAPI ↔ Ollama

- FastAPI sends a JSON payload to the local Ollama REST API.
- The Ollama endpoint (`http://host.docker.internal:11434`) is host-local only — not externally exposed by default.
- The model response is text; it is checked by output filters before being forwarded to the browser.

### Boundary 3: FastAPI → Browser (output)

- Model output is returned as a JSON string.
- The browser renders it using `textContent`, preventing HTML/script interpretation (V2 fix).
- Any action-command-shaped output is blocked server-side before it reaches the browser (V3 fix).

---

## System Prompt Design

The patched `SYSTEM_PROMPT` is minimal and public-facing only:
- Bot identity and role
- Product catalog (non-sensitive, the same info shown on a product page)
- Return policy
- A note to direct discount-code questions to the website

**Deliberately excluded from the system prompt:**
- Secrets or internal-use-only values (moved server-side, never into LLM context)
- Action command grammar (`[ACTION:REFUND:...]`, etc.) — removed to prevent the model from learning or echoing these forms
- "CONFIDENTIAL" or "INTERNAL USE ONLY" framing — if these strings appear in model output, the output filter catches them as evidence of leakage

---

## Security Controls in the Patched Version

### V1 Fix — Two-layer prompt-leakage defense

```python
# Layer 1: Pre-call — block before the model is ever called
if looks_like_prompt_extraction(user_message):
    return JSONResponse({"response": SAFE_REFUSAL})

# Layer 2: Post-call — output-side defense-in-depth
if contains_leaked_content(assistant_message):
    assistant_message = SAFE_REFUSAL
```

### V2 Fix — Render bot output as text, not HTML

```javascript
// In addBubble() — applies to all bot message rendering paths
bubble.textContent = text;  // was: bubble.innerHTML = text
```

### V3 Fix — Block action-command-shaped output

```python
if contains_action_command(assistant_message):
    assistant_message = SAFE_ACTION_MESSAGE
    actions_executed.append({
        "action": "BLOCKED",
        "params": [],
        "executed": False,
        "status": "requires_server_side_validation",
    })
```

The pattern covers both the original bracket syntax and freeform keyword forms:
```python
ACTION_COMMAND_PATTERN = re.compile(
    r'\[ACTION:(?:REFUND|DISCOUNT)'
    r'|\b(?:REFUND_ORDER|DISCOUNT_CUSTOMER|PROCESS_REFUND|APPLY_DISCOUNT)\b',
    re.IGNORECASE,
)
```

---

## Open Issues (Documented, Not Patched)

| Finding | Root cause | Location |
|---|---|---|
| V4 — No auth | No authentication dependency on `/api/chat` route | `app.py:62-63` |
| V5 — No input limit | No `len(user_message)` check before forwarding to Ollama | `app.py:73` |
| V6 — Trusted client history | `messages.extend(history)` without server-side session store | `app.py:74,77` |

---

## Docker Networking

The container runs FastAPI on port 8080 (mapped to host 8080). The `extra_hosts: host.docker.internal:host-gateway` entry in `docker-compose.yml` allows the container to reach the host-local Ollama instance. On Linux, Ollama must be bound to `0.0.0.0` for this to work.
