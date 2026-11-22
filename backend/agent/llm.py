"""Local model client for the agent.

The local model only proposes a JSON object describing an intent and its
arguments. It never executes anything: the caller validates the proposal and
performs any action itself.
"""

import json
import os
import urllib.error
import urllib.request

ALLOWED_INTENTS = [
    "create_product",
    "find_product",
    "record_purchase",
    "create_expense",
    "create_customer",
    "find_customer",
    "record_payment",
    "create_invoice",
    "customer_outstanding",
    "financial_summary",
]

UNKNOWN_INTENT = "unknown"


class LLMUnavailable(Exception):
    """Raised when the local model cannot be reached or returns an unreadable response."""


def _config():
    """Read agent LLM settings from the environment at call time."""
    url = os.environ.get("AGENT_LLM_URL", "http://127.0.0.1:11434/api/chat")
    model = os.environ.get("AGENT_LLM_MODEL", "llama3.2")
    raw_timeout = os.environ.get("AGENT_LLM_TIMEOUT", "60")
    try:
        timeout = float(raw_timeout)
    except ValueError:
        timeout = 60.0
    return url, model, timeout


def _default_post(url, payload, timeout):
    """POST a JSON payload to the local model and return the parsed JSON response."""
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("AGENT_LLM_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LLMUnavailable("local model unavailable: %s" % exc) from exc


SYSTEM_PROMPT = (
    "You convert a shop owner's typed request into a JSON intent. "
    "Reply with ONLY a JSON object of this exact shape:\n"
    '{"intent": <one of the intents below, or "unknown">, '
    '"args": {<argument name: value>}, '
    '"missing": [<names of mandatory fields the owner did not state>], '
    '"question": "<one short follow-up question for the owner, or empty string>"}\n'
    "\n"
    "Rules:\n"
    "- Never invent values. Only put in args what the owner actually stated.\n"
    "- Any mandatory field the owner did not state goes into \"missing\" and is left out of args.\n"
    "- Convert dates to YYYY-MM-DD relative to the TODAY value given in the user message "
    "(for example 'yesterday' is the day before TODAY).\n"
    "- If the request does not match any intent, use \"intent\": \"unknown\".\n"
    "\n"
    "Intents and their arguments:\n"
    "- create_product: product_id, name, purchase_rate, selling_rate, gst_percent, category, hsn_code, barcodes\n"
    "  mandatory: product_id, name, purchase_rate, selling_rate\n"
    "- find_product: query\n"
    "  mandatory: query\n"
    "- record_purchase: product_id, qty, rate, purchase_date, supplier_id, amount_paid\n"
    "  mandatory: product_id, qty, rate\n"
    "- create_expense: name, amount, category, kind (fixed|variable|other), status (paid|pending), "
    "expense_date, description\n"
    "  mandatory: name, amount\n"
    "- create_customer: name, phone, address, gstin, credit_limit\n"
    "  mandatory: name\n"
    "- find_customer: query\n"
    "  mandatory: query\n"
    "- record_payment: customer_id, invoice_no, amount, payment_date\n"
    "  mandatory: customer_id, amount, invoice_no\n"
    "- create_invoice: customer_id, payment_type (cash|credit), items (list of {product_id, qty})\n"
    "  mandatory: customer_id, payment_type, items\n"
    "- customer_outstanding: customer_id\n"
    "  mandatory: customer_id\n"
    "- financial_summary: period (today|month|all)\n"
    "  mandatory: none\n"
)


def _unknown_result():
    return {"intent": UNKNOWN_INTENT, "args": {}, "missing": [], "question": ""}


def parse_intent(text, today, post_json=None):
    """Ask the local model to classify a request and return a normalised intent dict.

    Connection problems raise LLMUnavailable. A malformed or off-list model
    reply returns the unknown result instead.
    """
    url, model, timeout = _config()
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "TODAY: " + str(today) + "\n" + text},
        ],
    }
    post = post_json or _default_post
    response = post(url, payload, timeout)

    try:
        content = response["message"]["content"]
    except (KeyError, TypeError):
        return _unknown_result()

    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return _unknown_result()

    if not isinstance(data, dict):
        return _unknown_result()

    intent = data.get("intent")
    if intent not in ALLOWED_INTENTS and intent != UNKNOWN_INTENT:
        return _unknown_result()

    args = data.get("args")
    if not isinstance(args, dict):
        args = {}

    missing = data.get("missing")
    if isinstance(missing, list):
        missing = [item for item in missing if isinstance(item, str)]
    else:
        missing = []

    question = data.get("question")
    if not isinstance(question, str):
        question = ""

    return {"intent": intent, "args": args, "missing": missing, "question": question}
