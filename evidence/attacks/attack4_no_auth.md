# Attack 4 — Missing Authentication on /api/chat

**Vulnerability name:** Missing Authentication on `/api/chat`
**OWASP / access-control category:** Access Control / Authentication weakness; also an enabler for OWASP LLM01 Prompt Injection and LLM06 Excessive Agency
**Severity:** Medium

## Exact command used

```bash
curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
  -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what products do you sell?", "history": []}'
```

## Observed behavior

The app returned `HTTP_STATUS:200` and responded to a direct unauthenticated POST request to `/api/chat`. No login, session cookie, bearer token, API key, CSRF token, or user identity was required.

## Screenshot evidence

- `screenshots/attack4_no_auth.png`

## Why this works

The `/api/chat` endpoint accepts requests from any caller without authentication or authorization checks. Because the endpoint directly exposes the LLM workflow, any unauthenticated caller can send prompts, attempt prompt injection, consume backend model resources, and potentially trigger unsafe action flows.

## Fix idea

Require authentication and authorization before allowing access to `/api/chat`. Add a simple API key or session-style authorization check before processing chat requests. In a production app, this should be tied to real user identity, rate limiting, audit logging, and authorization checks for any business action.

## Verification

Re-send the same unauthenticated request after the patch and confirm it returns `401 Unauthorized` or `403 Forbidden` instead of HTTP 200 and a model response.

## Status

Documented finding — not remediated in this lab. Remains open as an example of a common trust-boundary gap in LLM-integrated applications.
