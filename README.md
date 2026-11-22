# 📊 Inventory Management & Cash Flow Intelligence System

[![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github)](https://github.com/suri9946/just_analyze)
[![Database](https://img.shields.io/badge/Database-Local_SQLite_%2F_PostgreSQL-003B57?style=for-the-badge&logo=sqlite)](https://sqlite.org/)
[![AI-Engine](https://img.shields.io/badge/AI_Agent-Local_Llama_3.2B-FF6F00?style=for-the-badge&logo=meta)](https://ollama.ai)
[![Design](https://img.shields.io/badge/Figma-Light_Theme_Clean_UX-F24E1E?style=for-the-badge&logo=figma)](https://figma.com)
[![License](https://img.shields.io/badge/License-Proprietary-blue.svg?style=for-the-badge)](#license)

---

## 🎯 Executive Overview & Product Vision

Most small and medium enterprise (SME) business owners struggle not because they lack sales, but because they **lack cash flow visibility**. High revenue often masks delayed receivables, mounting supplier payables, unmonitored fixed costs, and excessive capital tied up in inventory.

The **Inventory Management & Cash Flow Intelligence System** is an all-in-one business management and financial intelligence platform designed from first principles for retail and wholesale business owners.

### 💡 Core Mission
> **"Know where the money comes from, where it goes, where it gets stuck, and whether the business is financially healthy."**

The platform connects inventory purchasing, barcode-powered point-of-sale (POS) billing, customer credit control, manual payment reconciliations, granular business expenses, and local AI natural-language assistance into a single unified local database engine. It calculates **Revenue**, **Operating Profit**, and **Net Operating Cash Flow** independently to deliver real-time financial health monitoring without requiring accounting expertise.

---

## 🏗️ System Architecture & Technology Stack

The platform is designed with an **offline-first, local-first architecture**, ensuring complete data privacy, zero recurring cloud LLM costs, and lightning-fast POS response times.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                              │
│       Figma-Driven Light Theme UI (Tailwind CSS, Shadcn UI / React)    │
│  ┌───────────────┬────────────────┬────────────────┬────────────────┐  │
│  │ POS & Billing │ Inventory Hub  │ Customer Credit│ Cash Flow Intel│  │
│  └───────────────┴────────────────┴────────────────┴────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ IPC / REST API
┌───────────────────────────────────┴────────────────────────────────────┐
│                         APPLICATION CORE                               │
│  ┌────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Transaction Engine     │  │ Cash Flow Intelligence Engine        │  │
│  │ • Atomic Multi-Table   │  │ • Cash vs. Accrual Separator         │  │
│  │ • Strict No-Return Rule│  │ • 3-Tier Health Algorithm            │  │
│  │ • Credit Limit Guard   │  │ • Dynamic Working Capital Analyzer   │  │
│  └────────────────────────┘  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Local AI Agent Subsystem (Ollama / Llama 3.2B)                   │  │
│  │ • Intent Classification      • Controlled Tool Invocation Layer  │  │
│  │ • Parameter Extraction       • Mandatory Owner Confirmation Gate │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Local Driver (Prisma / Drizzle ORM)
┌───────────────────────────────────┴────────────────────────────────────┐
│                           LOCAL STORAGE                                │
│       Local Embedded Database (SQLite / Local Embedded PostgreSQL)      │
│  ┌───────────────┬────────────────┬────────────────┬────────────────┐  │
│  │ Products & Bar│ Customers & Rec│ Invoices & Cash│ Expenses & EMI │  │
│  └───────────────┴────────────────┴────────────────┴────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Tech Stack Recommendation
| Component | Technology | Rationale |
|---|---|---|
| **Frontend** | React / Next.js / Vite + Tailwind CSS | Ultra-fast reactivity, zero lag in POS barcode input. |
| **Design System** | Figma Light Theme + Radix / Shadcn UI | Clean high-contrast typography, ergonomic layouts for long desk hours. |
| **Local Database** | Local SQLite (WAL Mode) or Local PostgreSQL | Zero cloud latency, ACID transactional integrity, single-file backup simplicity. |
| **Local AI Engine** | Meta Llama 3.2B running via Ollama / llama.cpp | On-premise execution, zero cloud API fees, 100% offline data privacy. |
| **Messaging** | WhatsApp Business Cloud API / Webhook Integration | Direct dispatch of digital invoice links and payment reminder alerts. |
| **Reporting Engine** | jsPDF / SheetJS (XLSX) | Client-side export of auditable financial summaries and statement PDFs. |

---

## 🎨 Figma-Driven Light Theme UI/UX Design

The application features a **Figma-crafted clean light theme** engineered specifically for high-stress retail counters and business offices:

* **Surface Palette:** Crisp white backgrounds (`#FFFFFF`) with soft neutral canvas containers (`#F8FAFC`, `#F1F5F9`) and distinct slate borders (`#E2E8F0`).
* **Visual Hierarchy:** High-contrast charcoal text (`#0F172A`) ensures legibility under bright store lighting and varied display angles.
* **Semantic Status Accents:**
  * 🟢 **Emerald Green (`#10B981`):** Positive cash flow, completed payments, healthy financial status.
  * 🟡 **Amber Amber (`#F59E0B`):** Warning states, approaching credit thresholds, caution financial status.
  * 🔴 **Rose Red (`#EF4444`):** Overdue bills, hard credit limit breach, financial risk status.
* **Ergonomics & Keyboard Mastery:**
  * Global Hotkeys for instant billing (`F2` New Bill, `F3` Customer Search, `F4` Add Barcode, `F9` Settle).
  * Auto-focusing barcode scanner fields with instant audio-visual confirmation chimes.
  * Modal-less in-line new customer creation to prevent counter bottlenecks.

---

## 📦 Core Functional Modules

### 1. Inventory & Barcode Management
* **Unique Internal Product ID:** Independent SKU/Product IDs ensuring unambiguous stock tracking.
* **Multiple Barcode Aliasing:** Map multiple manufacturer barcodes (EAN-13, UPC, Code 128) and internal retail tags to a single product record.
* **Stock Tracking:** Automatic stock increments on supplier purchase and automatic decrement upon bill finalization.
* **Tax & HSN Compliance:** Configurable GST rates (0%, 5%, 12%, 18%, 28%) and HSN classifications per item.
* **Strict No-Return Business Rule:** The system strictly prohibits sales returns or product return workflows.

### 2. Customer Management & Credit Guard
* **Customer Profile:** Name, Phone Number, GSTIN, Address, Credit Limit, and Complete Ledger.
* **Credit Limit Verification:**
  $$\text{Available Credit} = \text{Credit Limit} - \text{Current Outstanding Balance}$$
* **Hard Enforcement:** Blocks unauthorized credit billing if an invoice exceeds available credit, displaying overdue invoice warnings and requiring owner intervention.
* **Auto-Discovery & In-line Creation:** Seamlessly create new customer profiles directly within the billing modal without aborting the billing transaction.

### 3. Point-of-Sale (POS) Billing
* **Multi-Modal Input:** Hardware barcode scan, manual barcode entry, or Product ID lookup.
* **Real-time Tax Calculations:** Automated subtotal, CGST/SGST/IGST splitting, and final round-off calculation.
* **Payment Modalities:**
  * **Cash Bill:** Immediate full settlement, recorded as instant cash collection.
  * **Credit Bill:** Validates credit limits and assigns unpaid invoice balance to customer ledger.
* **Atomic Settlement:** In a single ACID transaction, creates invoice items, deducts physical stock, logs ledger adjustments, and updates cash flow metrics.

### 4. Customer Payments & WhatsApp Automation
* **Manual Payment Reconciliation:** No third-party payment gateway fees. Payments received via cash, UPI, or NEFT outside the system are manually entered by the owner.
* **Partial Settlement Engine:** Distributes partial payments against specific invoices or allocates them to the oldest outstanding bill.
* **WhatsApp Notification Dispatch:**
  * Instant Invoice Delivery with line items, tax breakdown, and payment status.
  * Outstanding balance summaries with bank UPI/account details.
  * Automated polite payment reminder templates for overdue invoices.
  * *Safety Rule: Sending WhatsApp messages never marks an invoice as settled.*

### 5. Expense & Loan (EMI) Management
* **Fixed Expenses:** Rent, electricity, municipal water, staff salaries, internet, recurring subscriptions.
* **Variable Expenses:** Freight/transportation, packaging materials, maintenance, emergency repairs.
* **Inventory Purchase Outlays:** Direct linkage between supplier purchase invoices, quantities received, and cash outflows.
* **EMI & Loan Amortization Tracker:**
  * Separates **Principal Repayment** (Balance Sheet balance deduction) from **Interest Expense** (Operating Expense).
  * Tracks next EMI due dates, remaining tenures, and outstanding liabilities.

### 6. Owner Dashboard & Business Intelligence
* Centralized live dashboard displaying daily and monthly sales, gross revenue, net profit, total cash on hand, customer receivables, and supplier payables.
* One-click downloadable **Audited Payment & Outstanding Balance Reports (PDF/Excel)** with customer ledgers, payment timelines, and aging analyses.

---

## 📈 Cash Flow Intelligence Engine

Traditional accounting tools confuse **Sales** with **Cash**. Our system eliminates this dangerous blind spot through three isolated metrics:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FINANCIAL TRIAD FORMULAS                        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. REVENUE (Net Sales)                                                 │
│    Revenue = Gross Invoiced Sales - Applicable GST                     │
│                                                                        │
│ 2. OPERATING PROFIT                                                    │
│    Operating Profit = Revenue - Cost of Goods Sold (COGS) - OpEx       │
│                                                                        │
│ 3. NET OPERATING CASH FLOW                                             │
│    Net Cash Flow = Actual Cash Inflows - Actual Cash Outflows          │
│    where Inflows  = Cash Sales + Actual Customer Collections           │
│    where Outflows = Paid Inventory Purchases + Paid Expenses + EMI     │
└────────────────────────────────────────────────────────────────────────┘
```

### 🚦 Three-Tier Financial Health Indicator

The system dynamically classifies overall business solvency into three actionable states:

| Status | Condition & Triggers | System Diagnostic |
|---|---|---|
| 🟢 **GREEN (Healthy)** | Cash on hand covers upcoming 30-day obligations; customer collections $\ge 85\%$; projected 14-day cash flow $> 0$. | *Business is self-sustaining. Working capital is healthy.* |
| 🟡 **YELLOW (Caution)** | Collections dropping below $70\%$; receivables aging $> 30$ days; cash on hand tight against upcoming rent/EMI. | *Warning: Cash conversion cycle is lagging behind sales volume.* |
| 🔴 **RED (Financial Risk)** | Negative net cash flow; cash on hand insufficient for upcoming EMI/rent; high proportion of overdue credit sales. | *Urgent: Cash freeze risk. Halt credit billing and trigger collection alerts.* |

---

## 🤖 Local AI Agent Integration (Llama 3.2B)

A fully integrated, local AI agent powered by **Meta Llama 3.2B** (via Ollama) allows business owners to manage operations through natural-language conversation without touching complex forms.

```
                  ┌─────────────────────────────────────────┐
                  │      Owner Natural Language Input       │
                  │ "Purchased 50 rice bags at 800 from ABC"│
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │       Local Llama 3.2B LLM Core         │
                  │   Intent Extraction & Entity Parsing    │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │         Controlled Tool Gateway         │
                  │   • Schema & Type Validation            │
                  │   • Missing Information Interrogation   │
                  └────────────────────┬────────────────────┘
                                       │
                         [Is Information Complete?]
                        /                          \
                     YES                            NO
                      │                              │
                      ▼                              ▼
      ┌──────────────────────────────┐ ┌──────────────────────────────┐
      │ Confirmation Preview Card    │ │ Interactive Prompt to Owner: │
      │ [Approve & Execute] / [Edit] │ │ "What was the purchase rate?"│
      └──────────────┬───────────────┘ └──────────────────────────────┘
                     │ (Owner Confirms)
                     ▼
      ┌──────────────────────────────┐
      │ Atomic Local Database Write  │
      │ Stock +50 | Cash Flow Update │
      └──────────────────────────────┘
```

### Controlled Application Tools
The LLM is strictly sandboxed. It has **no arbitrary SQL execution privileges** and operates through validated APIs:
- `create_product(name, category, hsn, gst, purchase_rate, selling_rate, barcodes, stock)`
- `find_product(search_query)` / `find_by_barcode(barcode)`
- `record_inventory_purchase(product_id, quantity, rate, supplier, payment_status)`
- `find_customer(query)` / `create_customer(name, phone, address, credit_limit)`
- `get_customer_outstanding(customer_id)`
- `record_customer_payment(customer_id, invoice_id, amount, payment_mode)`
- `create_expense(category, amount, description, payment_status, due_date)`
- `get_financial_summary(time_range)`

---

## 🔄 End-to-End System Workflows

```
Workflow A: Add Product ───► Register SKU & Barcodes ───► Stock Ready for POS
Workflow B: Purchase Stock ──► Select Supplier ──► Increase Qty ──► Update Outflows/Payables
Workflow C: POS Cash/Credit ─► Barcode Scan ──► Credit Check ──► Deduct Stock ──► Create Invoice
Workflow D: New Buyer POS ──► In-line Customer Form ──► Link Invoice ──► Save to Directory
Workflow E: Debt Collection ─► Manual Payment Input ──► Reduce Debt ──► Inflow Recorded
Workflow F: WhatsApp Alerts ─► Query Aging Receivables ──► Send Reminder Link
Workflow G: Record Expenses ─► Categorize Fixed/Var/EMI ──► Cash Flow Updated
Workflow H: Owner Intel ─────► Aggregate Inflows/Outflows ──► Traffic Light Health State
Workflow I: AI Copilot ──────► NLP Input ──► Tool Call ──► Confirmation ──► Atomic DB Write
```

---

## 🗄️ Relational Database Schema Design (Local DB)

The system relies on a local relational schema with foreign key constraints and transactional rollback protection.

```sql
-- 1. PRODUCTS MASTER
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    item_category TEXT NOT NULL,
    hsn_code TEXT,
    gst_rate REAL NOT NULL DEFAULT 0.0,
    purchase_rate REAL NOT NULL,
    selling_rate REAL NOT NULL,
    preorder_quantity INTEGER DEFAULT 0,
    current_stock INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. PRODUCT BARCODES (1-to-Many mapping)
CREATE TABLE product_barcodes (
    barcode_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    barcode_value TEXT UNIQUE NOT NULL,
    barcode_type TEXT DEFAULT 'CUSTOM', -- 'MANUFACTURER' or 'CUSTOM'
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- 3. CUSTOMERS
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    address TEXT,
    gst_number TEXT,
    credit_limit REAL NOT NULL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. INVOICES
CREATE TABLE invoices (
    invoice_number TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    bill_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    billing_type TEXT CHECK(billing_type IN ('CASH', 'CREDIT')),
    subtotal REAL NOT NULL,
    gst_total REAL NOT NULL,
    grand_total REAL NOT NULL,
    amount_paid REAL NOT NULL DEFAULT 0.0,
    outstanding_amount REAL NOT NULL,
    payment_status TEXT CHECK(payment_status IN ('PAID', 'PARTIALLY_PAID', 'UNPAID')),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- 5. INVOICE ITEMS (Strict No-Return Rule Enforced)
CREATE TABLE invoice_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    gst_rate REAL NOT NULL,
    gst_amount REAL NOT NULL,
    total_amount REAL NOT NULL,
    FOREIGN KEY (invoice_number) REFERENCES invoices(invoice_number),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 6. CUSTOMER PAYMENTS (Manual Record)
CREATE TABLE customer_payments (
    payment_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    invoice_number TEXT,
    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    amount_received REAL NOT NULL,
    payment_mode TEXT NOT NULL, -- 'CASH', 'UPI', 'BANK_TRANSFER'
    notes TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (invoice_number) REFERENCES invoices(invoice_number)
);

-- 7. EXPENSES & EMIs
CREATE TABLE expenses (
    expense_id TEXT PRIMARY KEY,
    category TEXT NOT NULL, -- 'RENT', 'ELECTRICITY', 'SALARY', 'VARIABLE', 'EMI_INTEREST', 'EMI_PRINCIPAL'
    amount REAL NOT NULL,
    expense_date DATE NOT NULL,
    payment_status TEXT CHECK(payment_status IN ('PAID', 'PENDING')),
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE emi_loans (
    loan_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    total_principal REAL NOT NULL,
    monthly_emi REAL NOT NULL,
    principal_component REAL NOT NULL,
    interest_component REAL NOT NULL,
    next_due_date DATE NOT NULL,
    remaining_installments INTEGER NOT NULL,
    outstanding_balance REAL NOT NULL
);

-- 8. INVENTORY PURCHASES
CREATE TABLE inventory_purchases (
    purchase_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    supplier_name TEXT,
    quantity INTEGER NOT NULL,
    purchase_rate REAL NOT NULL,
    total_cost REAL NOT NULL,
    amount_paid REAL NOT NULL,
    amount_pending REAL NOT NULL,
    purchase_date DATE NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
```

---

## ⚡ Quick Start & Installation

### Prerequisites
1. **Node.js** (v18.0.0 or higher) or **Python 3.10+** (depending on frontend/backend runtime preference)
2. **Local Database:** SQLite3 (pre-installed on most OS) or PostgreSQL running locally
3. **Ollama:** Installed locally from [ollama.ai](https://ollama.ai) with the Llama 3.2B model pulled:
   ```bash
   ollama run llama3.2:3b
   ```

### Setup Steps
```bash
# 1. Clone the repository
git clone https://github.com/suri9946/just_analyze.git
cd just_analyze

# 2. Install dependencies
npm install
# or for python backend:
pip install -r requirements.txt

# 3. Configure environment variables (.env)
cp .env.example .env

# Configure your .env:
# DATABASE_URL="file:./data/inventory.db"
# OLLAMA_HOST="http://localhost:11434"
# OLLAMA_MODEL="llama3.2:3b"
# WHATSAPP_API_TOKEN="your_token_if_configured"

# 4. Initialize Local Database
npm run db:push
# or python manage.py migrate

# 5. Start Development Application
npm run dev
```

Visit `http://localhost:3000` to access the Light-Themed Owner Dashboard & POS Billing Terminal.

---

## 📋 Comprehensive System Business Rules Summary

1. **Unique Identity:** Every product must have an immutable, unique internal `Product ID`.
2. **Multi-Barcode Support:** A product may possess arbitrary manufacturer and custom internal barcodes; all resolve to the same product record.
3. **Zero Sales Returns:** The application does not accept product returns. No return or credit-note workflow exists.
4. **Fluid Customer Creation:** Unregistered customers can be created on-the-fly directly inside the billing interface.
5. **Credit Guard:** Credit billing is strictly constrained by `Credit Limit - Existing Outstanding`. Violations trigger warnings and require explicit authorization.
6. **No Auto-Settlement:** WhatsApp alerts, invoices, or reminders never update financial balances or settle bills automatically.
7. **Manual Reconciliation:** All payments received outside the software must be explicitly recorded by the owner with exact dates and modes.
8. **Three Independent Financial Dimensions:**
   - **Sales $\neq$ Collections:** Credit sales do not increase cash on hand.
   - **Expense $\neq$ Outflow:** Unpaid expenses do not reduce cash balances.
   - **Debt $\neq$ Expense:** EMI principal payments reduce loan liabilities, whereas interest is an operating expense.
9. **Controlled AI Execution:** The Llama 3.2B AI agent only operates through strictly typed application tools and mandatory owner confirmation.

---

## 📄 License
This project is proprietary software developed for high-precision inventory tracking and cash flow intelligence. All rights reserved. Built with ❤️ for business owners.

