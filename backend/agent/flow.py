"""Conversation flow for the business assistant.

Safety rules:
- The model only proposes an intent and arguments. It never writes SQL.
- Every write is stored as a pending action and runs only after an explicit confirm.
- Duplicate write requests (same intent, arguments and day) are blocked.
- Ambiguous payments are never assigned to an invoice automatically.
- Business rules are enforced by the services layer, not here.
"""
import datetime, hashlib, json, sqlite3
try:
    from ..db import get_conn
    from ..services import BusinessError, get_customer
    from . import llm as llm_module
    from .tools import validate, describe, execute, UnknownIntent, WRITE_INTENTS
except ImportError:
    from db import get_conn
    from services import BusinessError, get_customer
    from agent import llm as llm_module
    from agent.tools import validate, describe, execute, UnknownIntent, WRITE_INTENTS


UNKNOWN_MESSAGE = "I could not tell what you want to do. Please rephrase."
LLM_DOWN_MESSAGE = "The local AI model is not reachable. Start Ollama and try again."


def _now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _error_text(exc):
    detail = getattr(exc, "detail", None)
    return str(detail) if detail else str(exc)


def _money(value):
    try:
        return f"{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _as_list(result, key):
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        value = result.get(key)
        if isinstance(value, list):
            return value
        value = result.get("results")
        if isinstance(value, list):
            return value
    return []


def _render_read(intent, result):
    """Short plain-text rendering of a read-intent result."""
    if intent == "find_product":
        items = _as_list(result, "products")
        if not items:
            return "No products found"
        return "; ".join(f"{p.get('product_id')}: {p.get('name')}" for p in items)

    if intent == "find_customer":
        items = _as_list(result, "customers")
        if not items:
            return "No customers found"
        return ", ".join(f"{c.get('name')} (id {c.get('customer_id')})" for c in items)

    if intent == "customer_outstanding":
        if not isinstance(result, dict):
            return str(result)
        name = result.get("name", "Customer")
        total = result.get("total_outstanding", result.get("outstanding", 0))
        return f"{name} owes {_money(total)} in total."

    if intent == "financial_summary":
        if not isinstance(result, dict):
            return str(result)
        return (
            f"Sales total: {_money(result.get('sales_total'))}. "
            f"Available cash: {_money(result.get('available_cash'))}. "
            f"Receivables: {_money(result.get('receivables'))}. "
            f"Payables: {_money(result.get('payables'))}. "
            f"Health: {result.get('health_status', 'unknown')}."
        )

    return "Done."


def handle_message(text, today, post_json=None):
    """Turn one owner message into a reply. Always returns a dict with status and message."""
    try:
        parsed = llm_module.parse_intent(text, today, post_json=post_json)
    except llm_module.LLMUnavailable:
        return {"status": "error", "message": LLM_DOWN_MESSAGE}

    intent = parsed.get("intent") or "unknown"
    args = parsed.get("args") or {}
    question = (parsed.get("question") or "").strip()

    if intent == "unknown":
        return {"status": "clarify", "message": UNKNOWN_MESSAGE}

    try:
        clean, missing = validate(intent, args)
    except UnknownIntent:
        return {"status": "clarify", "message": UNKNOWN_MESSAGE}
    except ValueError as error:
        return {"status": "clarify", "message": str(error)}

    if missing:
        customer_id = args.get("customer_id")
        if intent == "record_payment" and "invoice_no" in missing and customer_id:
            try:
                customer = get_customer(customer_id)
            except BusinessError:
                return {
                    "status": "clarify",
                    "message": "I could not find that customer. Which customer is this payment for?",
                }
            open_numbers = [
                inv.get("invoice_no") for inv in customer.get("invoices", [])
                if float(inv.get("outstanding") or 0) > 0
            ]
            if not open_numbers:
                return {"status": "error", "message": "This customer has no open invoices to pay."}
            return {
                "status": "clarify",
                "message": "Which invoice should this payment go to? Open invoices: "
                           + ", ".join(str(n) for n in open_numbers) + ".",
                "options": open_numbers,
                "missing": missing,
            }
        message = "I need: " + ", ".join(missing) + ". " + question
        return {"status": "clarify", "message": message.strip(), "missing": missing}

    if intent == "record_payment":
        customer_id = clean.get("customer_id")
        try:
            customer = get_customer(customer_id)
        except BusinessError as error:
            if getattr(error, "status_code", None) == 404:
                return {
                    "status": "clarify",
                    "message": f"I could not find customer {customer_id}. Which customer is this payment for?",
                }
            return {"status": "error", "message": _error_text(error)}

        open_invoices = [
            inv for inv in customer.get("invoices", [])
            if float(inv.get("outstanding") or 0) > 0
        ]
        if not open_invoices:
            return {"status": "error", "message": "This customer has no open invoices to pay."}

        open_numbers = [inv.get("invoice_no") for inv in open_invoices]
        if clean.get("invoice_no") not in open_numbers:
            return {
                "status": "clarify",
                "message": "Which invoice should this payment go to? Open invoices: "
                           + ", ".join(str(n) for n in open_numbers),
                "options": open_numbers,
            }

    if intent in WRITE_INTENTS:
        summary = describe(intent, clean)
        args_json = json.dumps(clean, default=str)
        request_key = hashlib.sha256(
            (intent + "|" + json.dumps(clean, sort_keys=True, default=str) + "|" + today).encode("utf-8")
        ).hexdigest()

        conn = get_conn()
        try:
            duplicate = conn.execute(
                "SELECT id FROM agent_actions WHERE request_key = ? AND status IN ('pending', 'confirmed')",
                (request_key,),
            ).fetchone()
            if duplicate:
                return {
                    "status": "duplicate",
                    "message": "This looks like a request that is already pending or done: " + summary,
                    "action_id": duplicate["id"],
                }

            created_at = today + "T" + datetime.datetime.now().strftime("%H:%M:%S")
            previous = conn.execute(
                "SELECT id FROM agent_actions WHERE request_key = ?", (request_key,)
            ).fetchone()
            if previous:
                # Reuse the cancelled or failed row, since request_key is UNIQUE.
                conn.execute(
                    "UPDATE agent_actions SET status = 'pending', args_json = ?, summary = ?, "
                    "created_at = ?, result_json = NULL, error = NULL, resolved_at = NULL WHERE id = ?",
                    (args_json, summary, created_at, previous["id"]),
                )
                action_id = previous["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO agent_actions (request_key, intent, args_json, summary, status, created_at) "
                    "VALUES (?, ?, ?, ?, 'pending', ?)",
                    (request_key, intent, args_json, summary, created_at),
                )
                action_id = cursor.lastrowid
        finally:
            conn.close()

        return {
            "status": "confirm",
            "action_id": action_id,
            "summary": summary,
            "message": "Please confirm: " + summary + ". Nothing is saved until you confirm.",
        }

    try:
        result = execute(intent, clean)
    except BusinessError as error:
        return {"status": "error", "message": _error_text(error)}

    return {"status": "answer", "message": _render_read(intent, result), "data": result}


def _write_status(conn, sql, params):
    """Run one status update inside its own transaction."""
    conn.execute("BEGIN")
    try:
        conn.execute(sql, params)
        conn.execute("COMMIT")
    except sqlite3.Error:
        conn.execute("ROLLBACK")
        raise


def confirm_action(action_id, today):
    """Run a pending action after the owner confirms it."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM agent_actions WHERE id = ?", (action_id,)).fetchone()
        if row is None:
            return {"status": "error", "message": "That action does not exist."}
        if row["status"] != "pending":
            return {"status": "error", "message": "That action is already " + row["status"] + "."}

        intent = row["intent"]
        summary = row["summary"]

        try:
            result = execute(intent, json.loads(row["args_json"]))
        except Exception as error:
            message = _error_text(error)
            _write_status(
                conn,
                "UPDATE agent_actions SET status = 'failed', error = ?, resolved_at = ? WHERE id = ?",
                (message, _now_iso(), action_id),
            )
            return {"status": "error", "message": message}

        _write_status(
            conn,
            "UPDATE agent_actions SET status = 'confirmed', result_json = ?, resolved_at = ? WHERE id = ?",
            (json.dumps(result, default=str), _now_iso(), action_id),
        )
        return {"status": "done", "message": "Done: " + summary, "result": result}
    finally:
        conn.close()


def cancel_action(action_id):
    """Cancel a pending action so it can never run."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM agent_actions WHERE id = ?", (action_id,)).fetchone()
        if row is None:
            return {"status": "error", "message": "That action does not exist."}
        if row["status"] != "pending":
            return {"status": "error", "message": "That action is already " + row["status"] + "."}

        _write_status(
            conn,
            "UPDATE agent_actions SET status = 'cancelled', resolved_at = ? WHERE id = ?",
            (_now_iso(), action_id),
        )
        return {"status": "cancelled", "message": "Cancelled: " + row["summary"]}
    finally:
        conn.close()


def list_pending_actions():
    """Return all actions still waiting for confirmation, oldest first."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, intent, summary, created_at FROM agent_actions WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
