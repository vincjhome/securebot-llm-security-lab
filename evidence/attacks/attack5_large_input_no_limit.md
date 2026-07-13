# Attack 5 — No Input Length Limit / Large Prompt Accepted

**Vulnerability name:** No Input Length Limit / Large Prompt Accepted
**OWASP category:** LLM04 Model Denial of Service / Unbounded Resource Consumption
**Severity:** Medium

## Exact command/input used

```bash
python3 - <<'PY'
import json

payload = {
    "message": "Please summarize this customer note: " + ("filler text " * 500),
    "history": []
}

with open("/tmp/securebot_attack_large_input.json", "w") as f:
    json.dump(payload, f)

print("Payload size:")
import os
print(os.path.getsize("/tmp/securebot_attack_large_input.json"), "bytes")
PY

curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
  -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  --data @/tmp/securebot_attack_large_input.json
```

## Observed behavior

The app accepted a moderately large prompt (~6KB) and returned `HTTP_STATUS:200` with a normal model response. The request was not rejected with a `400` validation error, `413 Payload Too Large`, or any application-level input length error.

## Screenshot evidence

- `screenshots/attack5_large_input_no_limit.png`

## Why this works

The `/api/chat` endpoint accepts user-controlled prompt text without enforcing a maximum input length before passing the request into the LLM workflow. This allows a caller to send oversized prompts that consume model context, CPU/GPU time, memory, and backend processing resources.

## Fix idea

Add server-side request validation for maximum message length and maximum history length before calling Ollama. Return a clear `400` or `413` error when user input exceeds safe limits. Consider rate limiting and request timeouts for production.

## Verification

Re-send the same moderately large prompt after the patch and confirm the app rejects it with a controlled error such as `400 Bad Request` or `413 Payload Too Large` instead of forwarding it to the model.

## Status

Documented finding — not remediated in this lab. Remains open as an example of missing input validation in LLM-integrated API endpoints.
