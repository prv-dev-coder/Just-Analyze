"""Read-only financial calculations for Just Analyze (stdlib only).

Conventions:
- Revenue excludes GST: it is the sum of invoices.total_taxable.
- COGS = sum of invoice_items.qty * invoice_items.cost_rate. The cost rate was
  copied onto each invoice line at sale time, so later purchase price changes
  do not alter past COGS.
- Available cash is all-time: opening balance + all inflows - all outflows.
  All other figures (sales, revenue, COGS, expenses, cash flow, profit) are
  per period.
- A credit sale is not a cash inflow; it only becomes cash when a payment is
  recorded. An unpaid (pending) expense is not a cash outflow until it is paid.
- Dates are ISO strings (yyyy-mm-dd), so string comparison orders them.
- Money values are rounded to 2 decimals.
"""

import datetime
from contextlib import closing

try:
    from .db import get_conn
except ImportError:  # imported as a top-level module from backend/
    from db import get_conn


OVERDUE_DAYS = 30
LOW_STOCK_LEVEL = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_date(value):
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    return value


def _money(value):
    return round(float(value or 0.0), 2)


def _scalar(sql, params=()):
    with closing(get_conn()) as conn:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row is not None else None


def _rows(sql, params=()):
    with closing(get_conn()) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _range(column, period, today):
    """Return (sql_fragment, params) restricting `column` to the period bounds."""
    start, end = period_bounds(period, today)
    if start is None:
        return "", []
    return f" AND {column} >= ? AND {column} <= ?", [start, end]


# ---------------------------------------------------------------------------
# Period handling
# ---------------------------------------------------------------------------

def period_bounds(period, today):
    """Return (start, end) ISO date strings for a period, or (None, None) for all time."""
    t = _to_date(today)
    iso = t.isoformat()
    if period == "today":
        return (iso, iso)
    if period == "month":
        return (t.replace(day=1).isoformat(), iso)
    return (None, None)


# ---------------------------------------------------------------------------
# Period figures
# ---------------------------------------------------------------------------

def revenue(period, today):
    clause, params = _range("invoice_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(total_taxable), 0) FROM invoices WHERE 1=1" + clause,
        params,
    ))


def cogs(period, today):
    clause, params = _range("i.invoice_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(ii.qty * ii.cost_rate), 0) "
        "FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_pk "
        "WHERE 1=1" + clause,
        params,
    ))


def paid_expenses(period, today):
    clause, params = _range("expense_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE status = 'paid'" + clause,
        params,
    ))


def total_expenses(period, today):
    clause, params = _range("expense_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE 1=1" + clause,
        params,
    ))


def operating_profit(period, today):
    return _money(revenue(period, today) - cogs(period, today) - paid_expenses(period, today))


def cash_inflows(period, today):
    clause, params = _range("payment_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE 1=1" + clause,
        params,
    ))


def purchase_cash_out(period, today):
    clause, params = _range("purchase_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(amount_paid), 0) FROM purchases WHERE 1=1" + clause,
        params,
    ))


def cash_outflows(period, today):
    return _money(purchase_cash_out(period, today) + paid_expenses(period, today))


def net_cash_flow(period, today):
    return _money(cash_inflows(period, today) - cash_outflows(period, today))


def credit_sales(period, today):
    clause, params = _range("invoice_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
        "WHERE payment_type = 'credit'" + clause,
        params,
    ))


def sales_total(period, today):
    clause, params = _range("invoice_date", period, today)
    return _money(_scalar(
        "SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE 1=1" + clause,
        params,
    ))


# ---------------------------------------------------------------------------
# All-time balances
# ---------------------------------------------------------------------------

def opening_balance():
    value = _scalar("SELECT value FROM settings WHERE key = 'opening_balance'")
    try:
        return _money(float(value)) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def available_cash(today):
    """All-time: opening balance + all payments - all purchase payments - all paid expenses."""
    all_payments = _scalar("SELECT COALESCE(SUM(amount), 0) FROM payments")
    all_purchase_paid = _scalar("SELECT COALESCE(SUM(amount_paid), 0) FROM purchases")
    all_paid_expenses = _scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE status = 'paid'"
    )
    return _money(
        opening_balance()
        + float(all_payments or 0)
        - float(all_purchase_paid or 0)
        - float(all_paid_expenses or 0)
    )


def receivables():
    return _money(_scalar("SELECT COALESCE(SUM(outstanding), 0) FROM invoices"))


def payables():
    pending_purchases = _scalar("SELECT COALESCE(SUM(pending), 0) FROM purchases")
    pending_expenses = _scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE status = 'pending'"
    )
    return _money(float(pending_purchases or 0) + float(pending_expenses or 0))


def overdue_invoices(today):
    """Invoices with outstanding > 0 dated more than OVERDUE_DAYS before today."""
    cutoff = (_to_date(today) - datetime.timedelta(days=OVERDUE_DAYS)).isoformat()
    rows = _rows(
        "SELECT i.invoice_no, i.invoice_date, i.outstanding, "
        "       c.customer_id, c.name AS customer_name "
        "FROM invoices i JOIN customers c ON c.id = i.customer_pk "
        "WHERE i.outstanding > 0 AND i.invoice_date < ? "
        "ORDER BY i.invoice_date, i.invoice_no",
        (cutoff,),
    )
    for r in rows:
        r["outstanding"] = _money(r["outstanding"])
    return rows


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def health(period, today):
    reds = []
    yellows = []

    cash = available_cash(today)
    pay = payables()
    if cash < pay:
        reds.append(f"Available cash ({cash:.2f}) is below pending payables ({pay:.2f}).")

    overdue_count = len(overdue_invoices(today))
    if overdue_count >= 2:
        reds.append(f"{overdue_count} invoices are more than 30 days overdue.")
    elif overdue_count == 1:
        yellows.append("1 invoice is more than 30 days overdue.")

    if net_cash_flow(period, today) < 0:
        yellows.append("Net cash flow for this period is negative.")

    if credit_sales(period, today) > cash_inflows(period, today):
        yellows.append("Credit sales are growing faster than collections.")

    if reds:
        status = "RED"
        reasons = reds + yellows
    elif yellows:
        status = "YELLOW"
        reasons = yellows
    else:
        status = "GREEN"
        reasons = ["Cash covers pending obligations and collections are on time."]
    return {"status": status, "reasons": reasons}


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def dashboard(period, today):
    overdue = overdue_invoices(today)
    low_stock = _rows(
        "SELECT product_id, name, stock_qty FROM products "
        "WHERE stock_qty <= ? ORDER BY stock_qty, name",
        (LOW_STOCK_LEVEL,),
    )
    customers_outstanding = _scalar(
        "SELECT COUNT(DISTINCT customer_pk) FROM invoices WHERE outstanding > 0"
    )
    return {
        "period": period,
        "sales_total": sales_total(period, today),
        "revenue": revenue(period, today),
        "cogs": cogs(period, today),
        "paid_expenses": paid_expenses(period, today),
        "operating_profit": operating_profit(period, today),
        "operating_profit_label": "Estimated profit",
        "total_expenses": total_expenses(period, today),
        "cash_inflows": cash_inflows(period, today),
        "cash_outflows": cash_outflows(period, today),
        "net_cash_flow": net_cash_flow(period, today),
        "available_cash": available_cash(today),
        "receivables": receivables(),
        "payables": payables(),
        "customers_with_outstanding": int(customers_outstanding or 0),
        "overdue_count": len(overdue),
        "low_stock": low_stock,
        "health": health(period, today),
    }


def cashflow_breakdown(period, today):
    pay_clause, pay_params = _range("payment_date", period, today)
    inflow_rows = _rows(
        "SELECT COALESCE(NULLIF(TRIM(note), ''), 'payment') AS label, "
        "       COALESCE(SUM(amount), 0) AS total "
        "FROM payments WHERE 1=1" + pay_clause + " GROUP BY label ORDER BY label",
        pay_params,
    )
    inflows = {r["label"]: _money(r["total"]) for r in inflow_rows}

    exp_clause, exp_params = _range("expense_date", period, today)
    expense_rows = _rows(
        "SELECT kind, COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE status = 'paid'" + exp_clause + " GROUP BY kind",
        exp_params,
    )
    by_kind = {"fixed": 0.0, "variable": 0.0, "other": 0.0}
    for r in expense_rows:
        by_kind[r["kind"]] = _money(r["total"])

    outflows = {
        "purchases": purchase_cash_out(period, today),
        "fixed": by_kind["fixed"],
        "variable": by_kind["variable"],
        "other": by_kind["other"],
    }
    return {
        "period": period,
        "inflows": inflows,
        "outflows": outflows,
        "totals": {
            "inflows": cash_inflows(period, today),
            "outflows": cash_outflows(period, today),
        },
        "available_cash": available_cash(today),
        "receivables": receivables(),
        "payables": payables(),
        "net_cash_flow": net_cash_flow(period, today),
    }


def receivables_report(today):
    customers = _rows(
        "SELECT c.customer_id, c.name, "
        "       COALESCE(SUM(i.outstanding), 0) AS outstanding, "
        "       COUNT(i.id) AS open_invoices "
        "FROM invoices i JOIN customers c ON c.id = i.customer_pk "
        "WHERE i.outstanding > 0 "
        "GROUP BY c.id ORDER BY outstanding DESC, c.name"
    )
    for r in customers:
        r["outstanding"] = _money(r["outstanding"])
    return {
        "customers": customers,
        "overdue": overdue_invoices(today),
        "total_outstanding": receivables(),
    }


def payments_report_rows():
    rows = _rows(
        "SELECT c.name AS customer_name, c.customer_id, i.invoice_no, i.invoice_date, "
        "       i.total_amount, i.amount_paid, i.outstanding, i.status, "
        "       GROUP_CONCAT(DISTINCT p.payment_date) AS payment_dates_raw "
        "FROM invoices i "
        "JOIN customers c ON c.id = i.customer_pk "
        "LEFT JOIN payments p ON p.invoice_pk = i.id "
        "GROUP BY i.id "
        "ORDER BY i.invoice_date, i.invoice_no"
    )
    total_amount = 0.0
    amount_paid = 0.0
    outstanding = 0.0
    for r in rows:
        raw = r.pop("payment_dates_raw") or ""
        dates = sorted({d.strip() for d in raw.split(",") if d.strip()})
        r["payment_dates"] = ", ".join(dates)
        r["total_amount"] = _money(r["total_amount"])
        r["amount_paid"] = _money(r["amount_paid"])
        r["outstanding"] = _money(r["outstanding"])
        total_amount += r["total_amount"]
        amount_paid += r["amount_paid"]
        outstanding += r["outstanding"]
    return {
        "rows": rows,
        "total_amount": _money(total_amount),
        "amount_paid": _money(amount_paid),
        "outstanding": _money(outstanding),
    }
