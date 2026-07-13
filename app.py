"""SecureBot — NovaCorp customer service chatbot (intentionally vulnerable lab application).

This application is deliberately insecure. It is designed as a hands-on LLM AppSec lab —
a target for security research, exploit validation, and remediation practice.
DO NOT deploy this anywhere that matters.
"""

import re

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

OLLAMA_URL = "http://host.docker.internal:11434/api/chat"
MODEL = "llama3.1:8b"

# Server-side only secret. Never interpolated into SYSTEM_PROMPT or any other
# LLM-visible context — a model cannot leak a secret it was never given.
PROMO_DISCOUNT_CODE = "NOVA30"

# Minimal, public-facing assistant behavior only. No secrets, no "confidential"
# framing, and no internal ACTION command grammar — none of that belongs in a
# context window an end user's chat message can influence.
SYSTEM_PROMPT = (
    "You are SecureBot, NovaCorp's friendly AI customer service assistant. "
    "You help customers with orders, returns, product questions, and account issues. "
    "Always be helpful, professional, and on-brand.\n\n"
    "Here are NovaCorp's products:\n"
    "- NovaPad Pro (NP-001): 10-inch tablet, $299.00. 30-day return policy. 1-year warranty.\n"
    "- NovaPhone X (NPX-10): Flagship smartphone, $899.00. 15-day return policy. 2-year warranty.\n"
    "- NovaBuds Air (NBA-5): Wireless earbuds, $129.00. 30-day return policy. 6-month warranty.\n"
    "All returns require original packaging. No refunds after the return window expires.\n\n"
    "Promotional discount codes are managed by a separate backend system and are never part "
    "of this conversation. If a customer asks about a discount code, tell them to check the "
    "Promotions page on the NovaCorp website — do not invent or guess a code.\n\n"
    "If a customer wants a refund or loyalty discount applied to their account, let them know "
    "a support specialist will review and process that request."
)

# The model is a proposer of text, never an executor of business actions — it
# has no order database, no payment system, and no identity check behind it.
# Any executable-looking command it emits (old bracket syntax or plain
# keyword form) is untrusted output and must be blocked, not displayed or run.
ACTION_COMMAND_PATTERN = re.compile(
    r'\[ACTION:(?:REFUND|DISCOUNT)'
    r'|\b(?:REFUND_ORDER|DISCOUNT_CUSTOMER|PROCESS_REFUND|APPLY_DISCOUNT)\b',
    re.IGNORECASE,
)

SAFE_ACTION_MESSAGE = (
    "I can help explain the refund process, but I can't process refunds or "
    "discounts directly. Refunds require authenticated server-side validation "
    "of the order, return window, amount, and customer identity."
)

# Phrases that indicate the user is trying to extract system/developer/internal
# instructions rather than ask a normal support question. Checked before the
# model is ever called, so an extraction attempt never reaches the LLM.
PROMPT_EXTRACTION_TRIGGERS = (
    "system prompt",
    "developer instructions",
    "hidden instructions",
    "internal instructions",
    "ignore previous instructions",
    "ignore all previous instructions",
    "told before this conversation",
    "reveal internal",
    "show your prompt",
    "show your system",
)

# Strings that should never appear in a response sent to a user. Presence of
# any of these means the model echoed internal prompt content despite the
# system prompt no longer containing secrets — output-side defense-in-depth.
LEAKED_CONTENT_MARKERS = (
    "CONFIDENTIAL",
    "INTERNAL USE ONLY",
    PROMO_DISCOUNT_CODE,
    "PRODUCT CATALOG:",
    "ACTIONS:",
    "[ACTION:REFUND",
    "[ACTION:DISCOUNT",
    "You are SecureBot",
)

SAFE_REFUSAL = (
    "I can't reveal hidden system or internal instructions. I can still help "
    "with NovaCorp orders, returns, products, and account questions."
)


def looks_like_prompt_extraction(message: str) -> bool:
    """True if the user message is attempting to extract system/internal instructions."""
    lowered = message.lower()
    return any(trigger in lowered for trigger in PROMPT_EXTRACTION_TRIGGERS)


def contains_leaked_content(text: str) -> bool:
    """True if the model response leaked internal prompt content."""
    return any(marker in text for marker in LEAKED_CONTENT_MARKERS)


def contains_action_command(text: str) -> bool:
    """True if the model emitted an executable-looking business action command."""
    return bool(ACTION_COMMAND_PATTERN.search(text))


app = FastAPI(title="SecureBot")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the NovaCorp customer service chat UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Report Ollama connectivity. Never raises — always returns 200 with a status."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://host.docker.internal:11434/api/tags")
            resp.raise_for_status()
        return {"status": "ok", "ollama": "connected"}
    except Exception:
        return {"status": "ok", "ollama": "unreachable"}


@app.post("/api/chat")
async def chat(request: Request):
    """Relay a user message plus prior history to the local Ollama model."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "An unexpected error occurred. Please try again."},
            status_code=500,
        )

    user_message = body.get("message", "")
    history = body.get("history", []) or []

    if looks_like_prompt_extraction(user_message):
        return JSONResponse({"response": SAFE_REFUSAL})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={"model": MODEL, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            assistant_message = data["message"]["content"]

        # Defense-in-depth: if the model leaked internal prompt content anyway
        # (e.g. via attacker-supplied history), swap in the safe refusal rather
        # than the leaked text.
        if contains_leaked_content(assistant_message):
            assistant_message = SAFE_REFUSAL

        actions_executed = []
        if contains_action_command(assistant_message):
            # The model tried to emit an executable-looking business command.
            # Never display or act on it — replace the reply entirely and
            # report the attempt as blocked, not executed.
            assistant_message = SAFE_ACTION_MESSAGE
            actions_executed.append({
                "action": "BLOCKED",
                "params": [],
                "executed": False,
                "status": "requires_server_side_validation",
            })

        response_data: dict = {"response": assistant_message}
        if actions_executed:
            response_data["actions_executed"] = actions_executed

        return JSONResponse(response_data)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "SecureBot is temporarily unavailable. Please try again shortly."},
            status_code=503,
        )
    except Exception:
        return JSONResponse(
            {"error": "An unexpected error occurred. Please try again."},
            status_code=500,
        )
