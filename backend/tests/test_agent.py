"""Tests for the AI agent flow, run with a fake LLM and the FastAPI TestClient.

Each test gets its own temporary SQLite database: an autouse fixture points
backend.db.DB_PATH at a file inside pytest's tmp_path and creates the schema.
"""

import datetime
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from backend import db as db_module  # noqa: E402
from backend.agent import flow, llm as llm_module  # noqa: E402
from backend.main import app  # noqa: E402


TODAY = datetime.date.today().isoformat()


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    path = str(tmp_path / "test_agent.db")
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    yield path


def fake_llm(intent_obj):
    def post_json(url, payload, timeout):
        return {"message": {"content": json.dumps(intent_obj)}}

    return post_json


def setup_data(client):
    """Create product PRD-1 (stock 50 after purchase), and customer Ravi. Returns customer_id."""
    r = client.post("/api/products", json={
        "product_id": "PRD-1",
        "name": "Rice",
        "purchase_rate": 600,
        "selling_rate": 800,
        "gst_percent": 5,
        "barcodes": [],
    })
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/purchases", json={
        "items": [{"product_id": "PRD-1", "qty": 50, "rate": 600}],
        "amount_paid": 30000,
    })
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/customers", json={"name": "Ravi", "credit_limit": 50000})
    assert r.status_code in (200, 201), r.text
    return r.json()["customer_id"]


def make_credit_invoice(client, customer_id):
    r = client.post("/api/invoices", json={
        "customer_id": customer_id,
        "items": [{"product_id": "PRD-1", "qty": 2, "rate": 800}],
        "payment_type": "credit",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["invoice_no"]


def stock_of(client, product_id="PRD-1"):
    r = client.get(f"/api/products/{product_id}")
    assert r.status_code == 200, r.text
    return r.json()["stock_qty"]


def purchase_intent(qty=10, rate=650):
    return {
        "intent": "record_purchase",
        "args": {"product_id": "PRD-1", "qty": qty, "rate": rate},
        "missing": [],
        "question": "",
    }


def test_unreachable_model_returns_error():
    def down(url, payload, timeout):
        raise llm_module.LLMUnavailable("down")

    result = flow.handle_message("buy 10 rice", TODAY, post_json=down)
    assert result["status"] == "error"
    assert "not reachable" in result["message"]


def test_unknown_intent_asks_to_rephrase():
    intent = {"intent": "unknown", "args": {}, "missing": [], "question": ""}
    result = flow.handle_message("asdf qwerty", TODAY, post_json=fake_llm(intent))
    assert result["status"] == "clarify"


def test_missing_fields_are_asked_not_guessed():
    intent = {
        "intent": "record_purchase",
        "args": {"product_id": "PRD-1"},
        "missing": ["qty", "rate"],
        "question": "",
    }
    result = flow.handle_message("bought some rice", TODAY, post_json=fake_llm(intent))
    assert result["status"] == "clarify"
    assert "qty" in result["message"]
    assert len(flow.list_pending_actions()) == 0


def test_write_intent_is_proposed_not_executed():
    with TestClient(app) as client:
        setup_data(client)
        assert stock_of(client) == 50

        result = flow.handle_message("buy 10 rice at 650", TODAY,
                                     post_json=fake_llm(purchase_intent(10, 650)))
        assert result["status"] == "confirm"
        assert result.get("action_id")

        assert stock_of(client) == 50


def test_confirm_executes_and_updates_stock():
    with TestClient(app) as client:
        setup_data(client)

        result = flow.handle_message("buy 10 rice at 650", TODAY,
                                     post_json=fake_llm(purchase_intent(10, 650)))
        assert result["status"] == "confirm"

        done = flow.confirm_action(result["action_id"], TODAY)
        assert done["status"] == "done"
        assert stock_of(client) == 60


def test_duplicate_request_is_blocked():
    with TestClient(app) as client:
        setup_data(client)
        fake = fake_llm(purchase_intent(10, 650))

        first = flow.handle_message("buy 10 rice at 650", TODAY, post_json=fake)
        second = flow.handle_message("buy 10 rice at 650", TODAY, post_json=fake)
        assert second["status"] == "duplicate"
        assert second["action_id"] == first["action_id"]


def test_cancel_does_not_execute():
    with TestClient(app) as client:
        setup_data(client)

        result = flow.handle_message("buy 10 rice at 650", TODAY,
                                     post_json=fake_llm(purchase_intent(10, 650)))
        assert result["status"] == "confirm"

        cancelled = flow.cancel_action(result["action_id"])
        assert cancelled["status"] == "cancelled"
        assert stock_of(client) == 50

        after = flow.confirm_action(result["action_id"], TODAY)
        assert after["status"] == "error"
        assert "already cancelled" in json.dumps(after).lower()


def test_payment_without_invoice_is_not_auto_assigned():
    with TestClient(app) as client:
        customer_id = setup_data(client)
        make_credit_invoice(client, customer_id)

        intent = {
            "intent": "record_payment",
            "args": {"customer_id": customer_id, "amount": 500, "invoice_no": ""},
            "missing": [],
            "question": "",
        }
        result = flow.handle_message("Ravi paid 500", TODAY, post_json=fake_llm(intent))
        assert result["status"] == "clarify"
        assert "Which invoice" in result["message"]
        assert len(flow.list_pending_actions()) == 0


def test_payment_with_invoice_proposed_then_confirmed():
    with TestClient(app) as client:
        customer_id = setup_data(client)
        invoice_no = make_credit_invoice(client, customer_id)

        before = client.get(f"/api/customers/{customer_id}").json()["total_outstanding"]

        intent = {
            "intent": "record_payment",
            "args": {"customer_id": customer_id, "amount": 500, "invoice_no": invoice_no},
            "missing": [],
            "question": "",
        }
        result = flow.handle_message("Ravi paid 500 on " + invoice_no, TODAY,
                                     post_json=fake_llm(intent))
        assert result["status"] == "confirm"

        done = flow.confirm_action(result["action_id"], TODAY)
        assert done["status"] == "done"

        after = client.get(f"/api/customers/{customer_id}").json()["total_outstanding"]
        assert after == pytest.approx(before - 500)


def test_read_intent_executes_immediately():
    intent = {
        "intent": "financial_summary",
        "args": {"period": "month"},
        "missing": [],
        "question": "",
    }
    with TestClient(app) as client:
        setup_data(client)
        result = flow.handle_message("how did we do this month", TODAY,
                                     post_json=fake_llm(intent))
    assert result["status"] == "answer"
    assert "data" in result
    assert "sales_total" in result["data"]


def test_business_rule_enforced_on_confirm():
    intent = {
        "intent": "create_invoice",
        "args": {
            "customer_id": None,
            "items": [{"product_id": "PRD-1", "qty": 9999, "rate": 800}],
            "payment_type": "cash",
        },
        "missing": [],
        "question": "",
    }
    with TestClient(app) as client:
        customer_id = setup_data(client)
        intent["args"]["customer_id"] = customer_id

        result = flow.handle_message("sell 9999 rice to Ravi", TODAY,
                                     post_json=fake_llm(intent))
        assert result["status"] == "confirm"

        done = flow.confirm_action(result["action_id"], TODAY)
        assert done["status"] == "error"
        assert "stock" in json.dumps(done).lower()

        assert stock_of(client) == 50
