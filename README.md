# SecureBot LLM Security Lab

A deliberately vulnerable AI-powered customer support chatbot used to demonstrate LLM application security review, exploit validation, and remediation practice. SecureBot is a hands-on lab target — not a production-ready app.

The project covers a full security review cycle: source code review, vulnerability identification, exploit execution against a running local instance, patch implementation, and re-verification. All attack evidence and fix verification are real, not fabricated.

---

## What It Demonstrates

SecureBot contains intentional implementations of six LLM application security issues drawn from the OWASP LLM Top 10:

| # | Vulnerability | OWASP Category | Status |
|---|---|---|---|
| V1 | Prompt injection / system prompt leakage | LLM01, LLM07 | **Fixed and verified** |
| V2 | Insecure output handling / DOM XSS | LLM02 | **Fixed and verified** |
| V3 | Excessive agency / unauthorized action execution | LLM06 | **Fixed and verified** |
| V4 | Missing authentication on `/api/chat` | Access control | Documented — not remediated |
| V5 | No input length limit / unbounded resource consumption | LLM04 | Documented — not remediated |
| V6 | Client-supplied conversation history trusted by server | LLM01 (trust boundary) | Documented — not remediated |

Full attack evidence, fix rationale, and re-verification results are in `evidence/` and `docs/security_assessment.md`.

---

## Tech Stack

- **Backend:** Python 3, FastAPI
- **Templates:** Jinja2
- **Frontend:** Vanilla JavaScript, HTML/CSS (single-page chat UI)
- **LLM:** [Ollama](https://ollama.com/) with `llama3.1:8b` running locally
- **LLM transport:** Ollama REST API (`http://host.docker.internal:11434/api/chat`)
- **HTTP client:** httpx (async)
- **Containerization:** Docker, Docker Compose

---

## Architecture

```
Browser (chat UI)
  │
  │ POST /api/chat {message, history}
  ▼
FastAPI (app.py)
  │
  ├── Pre-call check: looks_like_prompt_extraction() → safe refusal if matched
  │
  ├── Build messages: [system prompt, ...client history, user message]
  │
  │ POST Ollama /api/chat
  ▼
Ollama → llama3.1:8b
  │
  │ model response text
  ▼
FastAPI (output filters)
  ├── contains_leaked_content() → replace with safe refusal if matched
  ├── contains_action_command() → replace + mark blocked if matched
  │
  └── JSONResponse {response, actions_executed?}
       │
       ▼
Browser (index.html)
  └── addBubble() renders via textContent (patched — was innerHTML)
```

Key trust boundary issues (intentional in the vulnerable version):
- **No server-side session store** — conversation history is supplied by the client on every request and trusted verbatim (V6)
- **No authentication** on the `/api/chat` endpoint — any network-reachable caller can use it (V4)
- **No input size validation** before forwarding to the model (V5)

---

## How to Run

**Prerequisites:**
1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Compose (Linux)
2. [Ollama](https://ollama.com/) installed and running
3. The `llama3.1:8b` model pulled:
   ```bash
   ollama pull llama3.1:8b
   ```

**Start the app:**
```bash
docker compose up
```

Open [http://localhost:8080](http://localhost:8080) in your browser.

To stop: `Ctrl+C`, then `docker compose down`.

**Linux note:** If the container can't reach Ollama, ensure it's bound to `0.0.0.0`:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

---

## API Reference

**POST `/api/chat`**
```json
{
  "message": "your message",
  "history": [
    {"role": "user", "content": "previous message"},
    {"role": "assistant", "content": "previous reply"}
  ]
}
```

Response:
```json
{"response": "SecureBot's reply"}
```

**GET `/health`**
```json
{"status": "ok", "ollama": "connected"}
```

---

## Reviewing the Security Findings

**Security assessment report:** [`docs/security_assessment.md`](docs/security_assessment.md)

**Attack evidence** (exact inputs, observed behavior, screenshots):
- [`evidence/attacks/attack1_prompt_leakage.md`](evidence/attacks/attack1_prompt_leakage.md)
- [`evidence/attacks/attack2_xss.md`](evidence/attacks/attack2_xss.md)
- [`evidence/attacks/attack3_excessive_agency.md`](evidence/attacks/attack3_excessive_agency.md)
- [`evidence/attacks/attack4_no_auth.md`](evidence/attacks/attack4_no_auth.md)
- [`evidence/attacks/attack5_large_input_no_limit.md`](evidence/attacks/attack5_large_input_no_limit.md)
- [`evidence/attacks/attack6_forged_history.md`](evidence/attacks/attack6_forged_history.md)

**Fix verification** (before/after, re-test results):
- [`evidence/fixes/fix1_prompt_leakage_verified.md`](evidence/fixes/fix1_prompt_leakage_verified.md)
- [`evidence/fixes/fix2_xss_verified.md`](evidence/fixes/fix2_xss_verified.md)
- [`evidence/fixes/fix3_excessive_agency_verified.md`](evidence/fixes/fix3_excessive_agency_verified.md)

Screenshots are in [`screenshots/`](screenshots/).

**Demo walkthrough:** [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md)

---

## Limitations

- **Local lab only** — requires a local Ollama instance; does not call any external LLM API
- **No real business actions** — SecureBot cannot actually process refunds, apply discounts, send emails, or perform any real operation. It is purely a chat interface
- **Intentionally simplified** — the app has no database, no user system, no real order management
- **Not production-ready** — missing authentication, rate limiting, input validation, logging, and server-side session state (these are the documented open findings V4–V6)
- **LLM behavior is non-deterministic** — exact model responses may differ across runs; the security controls are applied server-side independently of the model's output

---

## Open Findings (Not Remediated)

V4, V5, and V6 were documented but not patched. They represent real gaps worth understanding:

- **V4:** Add an API key or session-based auth check before `chat()` is called
- **V5:** Add a `len(user_message) > MAX_LEN` check before forwarding to Ollama; return 400 on violation
- **V6:** Maintain server-side conversation state keyed to an authenticated session rather than trusting the client-supplied `history` array

These are left as exercises and serve as examples of the trust-boundary issues common in real LLM-integrated applications.

---

## License

MIT
