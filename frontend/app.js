document.addEventListener('DOMContentLoaded', () => {
  // ---------- Helpers ----------
  const $ = (id) => document.getElementById(id);

  const esc = (s) => String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const money = (n) => Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(n) || 0);

  const api = async (method, path, body) => {
    const res = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      let msg = res.statusText || ('HTTP ' + res.status);
      const text = await res.text();
      try {
        const data = JSON.parse(text);
        const detail = data && data.detail;
        if (typeof detail === 'string') msg = detail;
        else if (detail) msg = JSON.stringify(detail);
      } catch (e) {
        if (text) msg = text;
      }
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  };

  let toastTimer = null;
  const toast = (msg, kind = 'info') => {
    const el = $('toast');
    el.textContent = msg;
    el.className = 'toast show ' + kind;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = 'toast'; }, 3500);
  };

  const showFormError = (msg) => {
    const el = $('form-error');
    if (el) el.textContent = msg || '';
  };

  const setBusy = (button, busy) => {
    if (button) button.disabled = !!busy;
  };

  // ---------- Router ----------
  const routes = ['dashboard', 'billing', 'products', 'customers', 'payments', 'expenses', 'purchases', 'cashflow', 'reports'];
  const loaders = {};

  const route = async () => {
    const raw = (location.hash || '').replace(/^#\//, '');
    const current = routes.includes(raw) ? raw : 'dashboard';

    routes.forEach((r) => {
      const sec = $('screen-' + r);
      if (sec) sec.classList.toggle('active', r === current);
    });
    document.querySelectorAll('a[data-route]').forEach((a) => {
      if (a.dataset.route === current) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });

    const loader = loaders[current];
    if (loader) {
      try {
        await loader();
      } catch (err) {
        toast(err.message, 'error');
      }
    }
  };

  // ---------- Dashboard ----------
  const card = (label, value) =>
    `<div class="card"><div class="card-label">${esc(label)}</div><div class="card-value">${esc(value)}</div></div>`;

  loaders.dashboard = async () => {
    const period = $('period-select').value || 'month';
    const d = await api('GET', '/api/dashboard?period=' + encodeURIComponent(period));

    $('dash-cards').innerHTML = [
      card('Sales', money(d.sales_total)),
      card('Revenue', money(d.revenue)),
      card('Estimated profit', money(d.operating_profit)),
      card('Total expenses', money(d.total_expenses)),
      card('Available cash', money(d.available_cash)),
      card('Receivables', money(d.receivables)),
      card('Payables', money(d.payables)),
      card('Cash inflows', money(d.cash_inflows)),
      card('Cash outflows', money(d.cash_outflows)),
      card('Net cash flow', money(d.net_cash_flow)),
      card('Customers with outstanding', d.customers_with_outstanding ?? 0),
      card('Overdue count', d.overdue_count ?? 0),
    ].join('');

    const health = d.health || {};
    const status = ['green', 'yellow', 'red'].includes(health.status) ? health.status : 'yellow';
    const reasons = Array.isArray(health.reasons) ? health.reasons : [];
    $('dash-health').innerHTML =
      `<span class="chip chip-${status}">${esc(health.status || 'unknown')}</span>` +
      `<ul>${reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>`;

    const low = Array.isArray(d.low_stock) ? d.low_stock : [];
    $('dash-lowstock').innerHTML = low.length
      ? `<ul>${low.map((p) => `<li>${esc(p.name)} (stock: ${esc(p.stock_qty)})</li>`).join('')}</ul>`
      : '<p class="empty">No low-stock items.</p>';
  };

  // ---------- Cash flow ----------
  loaders.cashflow = async () => {
    const period = $('cf-period').value || 'month';
    const [cf, settings] = await Promise.all([
      api('GET', '/api/cashflow?period=' + encodeURIComponent(period)),
      api('GET', '/api/settings'),
    ]);

    const rows = [
      ['Available cash', money(cf.available_cash)],
      ['Receivables', money(cf.receivables)],
      ['Payables', money(cf.payables)],
      ['Net cash flow', money(cf.net_cash_flow)],
    ];
    Object.entries(cf.inflows || {}).forEach(([k, v]) => rows.push(['Inflow: ' + k, money(v)]));
    Object.entries(cf.outflows || {}).forEach(([k, v]) => rows.push(['Outflow: ' + k, money(v)]));

    $('cf-table').innerHTML =
      '<table><thead><tr><th>Item</th><th>Amount</th></tr></thead><tbody>' +
      rows.map(([label, value]) => `<tr><td>${esc(label)}</td><td>${esc(value)}</td></tr>`).join('') +
      '</tbody></table>';

    const ob = settings ? settings.opening_balance : undefined;
    $('cf-opening').value = ob === undefined || ob === null ? '' : ob;
  };

  // ---------- Reports ----------
  loaders.reports = async () => {
    const d = await api('GET', '/api/receivables');
    $('report-summary').textContent = 'Total outstanding: ' + money(d.total_outstanding);
  };

  // ---------- Shared helpers for the remaining screens ----------
  const wired = {};
  const wireOnce = (key, fn) => {
    if (wired[key]) return;
    wired[key] = true;
    fn();
  };

  const reportError = (msg) => {
    showFormError(msg);
    toast(msg, 'error');
  };

  const arr = (v) => (Array.isArray(v) ? v : []);

  const numOrUndef = (s) => {
    const t = String(s ?? '').trim();
    if (t === '') return undefined;
    const n = Number(t);
    return Number.isFinite(n) ? n : undefined;
  };

  const intOrUndef = (s) => {
    const t = String(s ?? '').trim();
    if (t === '') return undefined;
    const n = parseInt(t, 10);
    return Number.isFinite(n) ? n : undefined;
  };

  const todayISO = () => {
    const d = new Date();
    const pad = (x) => String(x).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };

  const INVOICE_CHIP = { paid: 'chip-paid', partially_paid: 'chip-partial', unpaid: 'chip-unpaid' };
  const EXPENSE_CHIP = { paid: 'chip-paid', pending: 'chip-partial' };

  const chipFor = (status, map) => {
    const s = String(status ?? '');
    const cls = Object.prototype.hasOwnProperty.call(map, s) ? ' ' + map[s] : '';
    return `<span class="chip${cls}">${esc(s)}</span>`;
  };

  const table = (headers, rowsHtml) =>
    `<table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rowsHtml.join('')}</tbody></table>`;

  const emptyText = (text) => `<p class="empty">${esc(text)}</p>`;

  // ---------- Products ----------
  let productCache = [];

  const renderProducts = () => {
    const q = $('prod-search').value.trim().toLowerCase();
    const shown = productCache.filter((p) =>
      !q || [p.product_id, p.name, p.category].some((v) => String(v ?? '').toLowerCase().includes(q)));
    $('prod-list').innerHTML = shown.length
      ? table(['Product ID', 'Name', 'Category', 'Stock', 'Selling rate', 'Barcodes'], shown.map((p) => {
          const barcodes = arr(p.barcodes).map((b) => (b && typeof b === 'object' ? b.barcode : b)).join(', ');
          return `<tr><td>${esc(p.product_id)}</td><td>${esc(p.name)}</td><td>${esc(p.category)}</td>` +
            `<td>${esc(p.stock_qty)}</td><td>${money(p.selling_rate)}</td><td>${esc(barcodes)}</td></tr>`;
        }))
      : emptyText('No products found.');
  };

  const loadProducts = async () => {
    productCache = arr(await api('GET', '/api/products'));
    renderProducts();
  };

  loaders.products = async () => {
    wireOnce('products', () => {
      $('prod-search').addEventListener('input', renderProducts);

      $('prod-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const productId = $('p-product-id').value.trim();
        const name = $('p-name').value.trim();
        if (!productId) return reportError('Product ID is required.');
        if (!name) return reportError('Name is required.');

        const body = {
          product_id: productId,
          name,
          category: $('p-category').value.trim(),
          gst_percent: numOrUndef($('p-gst').value),
          hsn_code: $('p-hsn').value.trim(),
          billing_id: $('p-billing-id').value.trim(),
          purchase_rate: numOrUndef($('p-purchase-rate').value),
          selling_rate: numOrUndef($('p-selling-rate').value),
          pre_order_qty: intOrUndef($('p-pre-order').value),
          barcodes: $('p-barcodes').value.split(',').map((s) => s.trim()).filter(Boolean),
        };

        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          await api('POST', '/api/products', body);
          showFormError('');
          toast('Product saved', 'success');
          e.target.reset();
          await loadProducts();
        } catch (err) {
          reportError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });

      $('barcode-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const productId = $('bc-product-id').value.trim();
        const barcode = $('bc-barcode').value.trim();
        if (!productId || !barcode) return reportError('Product ID and barcode are required.');

        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          await api('POST', '/api/products/' + encodeURIComponent(productId) + '/barcodes', { barcode });
          showFormError('');
          toast('Barcode added', 'success');
          e.target.reset();
          await loadProducts();
        } catch (err) {
          reportError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });
    });

    await loadProducts();
  };

  // ---------- Customers ----------
  let custSearchTimer = null;

  const loadCustomers = async () => {
    const q = $('cust-list-search').value.trim();
    const data = await api('GET', q ? '/api/customers/search?q=' + encodeURIComponent(q) : '/api/customers');
    const rows = arr(data);
    $('cust-list').innerHTML = rows.length
      ? table(['Customer ID', 'Name', 'Phone', 'Credit limit'], rows.map((c) =>
          `<tr data-id="${esc(c.customer_id)}" class="clickable" tabindex="0">` +
          `<td>${esc(c.customer_id)}</td><td>${esc(c.name)}</td><td>${esc(c.phone)}</td><td>${money(c.credit_limit)}</td></tr>`))
      : emptyText('No customers found.');
  };

  const loadCustomerDetail = async (id) => {
    const c = await api('GET', '/api/customers/' + encodeURIComponent(id));
    const invoices = arr(c.invoices);
    const payments = arr(c.payments);
    const facts = [
      ['Name', c.name],
      ['Customer ID', c.customer_id],
      ['Phone', c.phone],
      ['Address', c.address],
      ['GSTIN', c.gstin],
      ['Credit limit', money(c.credit_limit)],
      ['Total outstanding', money(c.total_outstanding)],
      ['Available credit', money(c.available_credit)],
    ];
    $('cust-detail').innerHTML =
      `<h2>${esc(c.name)}</h2>` +
      '<dl>' + facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('') + '</dl>' +
      '<h3>Invoices</h3>' +
      (invoices.length
        ? table(['Invoice', 'Date', 'Total', 'Paid', 'Outstanding', 'Status'], invoices.map((i) =>
            `<tr><td>${esc(i.invoice_no)}</td><td>${esc(i.invoice_date)}</td><td>${money(i.total_amount)}</td>` +
            `<td>${money(i.amount_paid)}</td><td>${money(i.outstanding)}</td><td>${chipFor(i.status, INVOICE_CHIP)}</td></tr>`))
        : emptyText('No invoices.')) +
      '<h3>Payments</h3>' +
      (payments.length
        ? '<ul>' + payments.map((p) =>
            `<li>${esc(p.payment_date)} — ${money(p.amount)}` +
            (p.invoice_no ? ` (invoice ${esc(p.invoice_no)})` : '') + '</li>').join('') + '</ul>'
        : emptyText('No payments.'));
  };

  loaders.customers = async () => {
    wireOnce('customers', () => {
      $('cust-list-search').addEventListener('input', () => {
        clearTimeout(custSearchTimer);
        custSearchTimer = setTimeout(() => {
          loadCustomers().catch((err) => toast(err.message, 'error'));
        }, 250);
      });

      const openRow = (tr) => {
        if (tr && tr.dataset.id) {
          loadCustomerDetail(tr.dataset.id).catch((err) => toast(err.message, 'error'));
        }
      };
      $('cust-list').addEventListener('click', (e) => openRow(e.target.closest('tr[data-id]')));
      $('cust-list').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') openRow(e.target.closest('tr[data-id]'));
      });
    });

    await loadCustomers();
  };

  // ---------- Payments ----------
  const loadPayments = async () => {
    const rows = arr(await api('GET', '/api/payments'));
    $('pay-list').innerHTML = rows.length
      ? table(['Date', 'Customer', 'Invoice', 'Amount', 'Note'], rows.map((p) =>
          `<tr><td>${esc(p.payment_date)}</td><td>${esc(p.customer_pk ?? p.customer ?? '')}</td>` +
          `<td>${esc(p.invoice_pk ?? p.invoice_no ?? '')}</td><td>${money(p.amount)}</td><td>${esc(p.note ?? '')}</td></tr>`))
      : emptyText('No payments yet.');
  };

  const loadReceivables = async () => {
    const d = await api('GET', '/api/receivables');
    const customers = arr(d.customers);
    const overdue = arr(d.overdue);
    $('receivables').innerHTML =
      '<h3>By customer</h3>' +
      (customers.length
        ? table(['Customer ID', 'Name', 'Outstanding', 'Open invoices'], customers.map((c) =>
            `<tr><td>${esc(c.customer_id)}</td><td>${esc(c.name)}</td><td>${money(c.outstanding)}</td>` +
            `<td>${esc(c.open_invoices)}</td></tr>`))
        : emptyText('No outstanding balances.')) +
      '<h3>Overdue</h3>' +
      (overdue.length
        ? table(['Invoice', 'Customer ID', 'Outstanding'], overdue.map((i) =>
            `<tr><td>${esc(i.invoice_no)}</td><td>${esc(i.customer_id)}</td><td>${money(i.outstanding)}</td></tr>`))
        : emptyText('No overdue invoices.'));
  };

  loaders.payments = async () => {
    wireOnce('payments', () => {
      $('pay-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const customerId = $('pay-customer-id').value.trim();
        const invoiceNo = $('pay-invoice-no').value.trim();
        const amount = Number($('pay-amount').value);
        if (!customerId) return reportError('Customer ID is required.');
        if (!invoiceNo) return reportError('Invoice number is required.');
        if (!(amount > 0)) return reportError('Amount must be greater than 0.');

        const body = { customer_id: customerId, invoice_no: invoiceNo, amount };
        const payDate = $('pay-date').value;
        if (payDate) body.payment_date = payDate;

        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          await api('POST', '/api/payments', body);
          showFormError('');
          toast('Payment recorded', 'success');
          e.target.reset();
          await Promise.all([loadPayments(), loadReceivables()]);
        } catch (err) {
          reportError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });
    });

    await Promise.all([loadPayments(), loadReceivables()]);
  };

  // ---------- Expenses ----------
  const loadExpenses = async () => {
    const rows = arr(await api('GET', '/api/expenses'));
    $('exp-list').innerHTML = rows.length
      ? table(['Date', 'Name', 'Category', 'Kind', 'Amount', 'Status'], rows.map((x) =>
          `<tr><td>${esc(x.expense_date)}</td><td>${esc(x.name)}</td><td>${esc(x.category)}</td>` +
          `<td>${esc(x.kind)}</td><td>${money(x.amount)}</td><td>${chipFor(x.status, EXPENSE_CHIP)}</td></tr>`))
      : emptyText('No expenses yet.');
  };

  loaders.expenses = async () => {
    wireOnce('expenses', () => {
      $('exp-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = $('e-name').value.trim();
        const amountText = $('e-amount').value.trim();
        const amount = Number(amountText);
        if (!name) return reportError('Expense name is required.');
        if (amountText === '' || !Number.isFinite(amount) || amount < 0) {
          return reportError('Amount must be 0 or more.');
        }

        const body = {
          name,
          category: $('e-category').value.trim(),
          kind: $('e-kind').value,
          amount,
          description: $('e-description').value.trim(),
          status: $('e-status').value,
        };
        const expDate = $('e-date').value;
        if (expDate) body.expense_date = expDate;

        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          await api('POST', '/api/expenses', body);
          showFormError('');
          toast('Expense saved', 'success');
          e.target.reset();
          await loadExpenses();
        } catch (err) {
          reportError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });
    });

    await loadExpenses();
  };

  // ---------- Purchases ----------
  const addPurchaseLine = () => {
    const row = document.createElement('div');
    row.className = 'field-row pu-line';
    row.innerHTML =
      '<input type="text" class="pu-pid" placeholder="Product ID" aria-label="Product ID">' +
      '<input type="number" class="pu-qty" value="1" min="1" step="1" aria-label="Quantity">' +
      '<input type="number" class="pu-rate" min="0" step="0.01" placeholder="Rate" aria-label="Rate">' +
      '<button type="button" class="pu-remove">Remove</button>';
    row.querySelector('.pu-remove').addEventListener('click', () => row.remove());
    $('pu-lines').appendChild(row);
  };

  const loadSuppliers = async () => {
    const sups = arr(await api('GET', '/api/suppliers'));
    const sel = $('pu-supplier');
    const current = sel.value;
    sel.innerHTML = '<option value="">No supplier</option>' +
      sups.map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
    sel.value = current;
    $('sup-list').innerHTML = sups.length
      ? table(['Name', 'Phone', 'Address'], sups.map((s) =>
          `<tr><td>${esc(s.name)}</td><td>${esc(s.phone)}</td><td>${esc(s.address)}</td></tr>`))
      : emptyText('No suppliers yet.');
  };

  const loadPurchases = async () => {
    const rows = arr(await api('GET', '/api/purchases'));
    $('purch-list').innerHTML = rows.length
      ? table(['Date', 'Supplier', 'Total', 'Paid', 'Pending'], rows.map((p) => {
          const total = Number(p.total ?? p.total_amount) || 0;
          const paid = Number(p.amount_paid) || 0;
          const pending = p.pending ?? total - paid;
          return `<tr><td>${esc(p.purchase_date)}</td><td>${esc(p.supplier ?? p.supplier_name ?? '')}</td>` +
            `<td>${money(total)}</td><td>${money(paid)}</td><td>${money(pending)}</td></tr>`;
        }))
      : emptyText('No purchases yet.');
  };

  loaders.purchases = async () => {
    wireOnce('purchases', () => {
      $('pu-add-line').addEventListener('click', addPurchaseLine);

      $('sup-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = $('s-name').value.trim();
        if (!name) return reportError('Supplier name is required.');

        const body = { name, phone: $('s-phone').value.trim(), address: $('s-address').value.trim() };
        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          await api('POST', '/api/suppliers', body);
          showFormError('');
          toast('Supplier saved', 'success');
          e.target.reset();
          await loadSuppliers();
        } catch (err) {
          reportError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });

      // The supplier select may be blank ("No supplier"), so let the JS validate instead of the browser.
      $('purch-form').noValidate = true;
      $('purch-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const items = [];
        const lines = $('pu-lines').querySelectorAll('.pu-line');
        for (const row of lines) {
          const pid = row.querySelector('.pu-pid').value.trim();
          if (!pid) continue;
          const qty = Number(row.querySelector('.pu-qty').value);
          if (!Number.isInteger(qty) || qty <= 0) {
            return reportError('Quantity for ' + pid + ' must be a whole number above 0.');
          }
          items.push({ product_id: pid, qty, rate: Number(row.querySelector('.pu-rate').value) || 0 });
        }
        if (!items.length) return reportError('Add at least one line with a product ID.');

        const body = { items, amount_paid: Number($('pu-amount-paid').value) || 0 };
        const sid = $('pu-supplier').value;
        if (sid) body.supplier_id = Number(sid);
        const purchaseDate = $('pu-date').value;
        if (purchaseDate) body.purchase_date = purchaseDate;

        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          await api('POST', '/api/purchases', body);
          showFormError('');
          toast('Purchase saved', 'success');
          $('pu-lines').innerHTML = '';
          addPurchaseLine();
          $('pu-amount-paid').value = '';
          await loadPurchases();
        } catch (err) {
          reportError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });
    });

    if (!$('pu-date').value) $('pu-date').value = todayISO();
    if (!$('pu-lines').children.length) addPurchaseLine();
    await Promise.all([loadSuppliers(), loadPurchases()]);
  };

  // ---------- Billing ----------
  let billingWired = false;
  let billState = { customer: null, items: [] };
  let billCustResults = [];
  let billSearchTimer = null;

  const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;

  const billLineMath = (it) => {
    const taxable = round2(it.qty * it.selling_rate);
    const gst = round2(taxable * it.gst_percent / 100);
    const total = round2(taxable + gst);
    return { taxable, gst, total };
  };

  const renderCart = () => {
    if (!billState.items.length) {
      $('cart').innerHTML = '<tr><td colspan="7" class="empty">No items yet</td></tr>';
    } else {
      $('cart').innerHTML = billState.items.map((it, idx) => {
        const m = billLineMath(it);
        return `<tr><td>${esc(it.name)}</td><td>${esc(it.product_id)}</td>` +
          `<td><input type="number" class="bill-qty" data-idx="${idx}" min="1" step="1" value="${esc(it.qty)}" aria-label="Quantity"></td>` +
          `<td>${money(m.taxable)}</td><td>${money(m.gst)}</td><td>${money(m.total)}</td>` +
          `<td><button type="button" class="bill-remove" data-idx="${idx}">Remove</button></td></tr>`;
      }).join('');
    }

    const sums = billState.items.reduce((acc, it) => {
      const m = billLineMath(it);
      acc.taxable += m.taxable;
      acc.gst += m.gst;
      acc.total += m.total;
      return acc;
    }, { taxable: 0, gst: 0, total: 0 });

    $('cart-totals').innerHTML =
      `<p>Total taxable: ${money(round2(sums.taxable))}</p>` +
      `<p>Total GST: ${money(round2(sums.gst))}</p>` +
      `<p>Grand total: ${money(round2(sums.total))}</p>` +
      `<p>Items: ${esc(billState.items.length)}</p>`;
  };

  const refreshCredit = async () => {
    const box = $('credit-info');
    if (!billState.customer || $('pay-type').value !== 'credit') {
      box.innerHTML = '';
      return;
    }
    const id = billState.customer.customer_id;
    const c = (await api('GET', '/api/customers/' + encodeURIComponent(id))) || {};
    // Ignore a response that arrived after the selection changed.
    if (!billState.customer || billState.customer.customer_id !== id) return;
    box.innerHTML =
      '<dl>' +
      `<dt>Credit limit</dt><dd>${money(c.credit_limit)}</dd>` +
      `<dt>Total outstanding</dt><dd>${money(c.total_outstanding)}</dd>` +
      `<dt>Available credit</dt><dd>${money(c.available_credit)}</dd>` +
      '</dl>';
  };

  const selectCustomer = async (c) => {
    billState.customer = { customer_id: c.customer_id, name: c.name };
    $('cust-selected').textContent = `Selected: ${c.name} (${c.customer_id})`;
    $('cust-results').innerHTML = '';
    billCustResults = [];
    if ($('pay-type').value === 'credit') {
      await refreshCredit().catch((err) => toast(err.message, 'error'));
    }
  };

  const searchCustomers = async () => {
    const q = $('cust-search').value.trim();
    if (!q) {
      $('cust-results').innerHTML = '';
      billCustResults = [];
      return;
    }
    const rows = arr(await api('GET', '/api/customers/search?q=' + encodeURIComponent(q)));
    billCustResults = rows;
    $('cust-results').innerHTML = rows.map((c, idx) =>
      `<button type="button" class="cust-pick" data-idx="${idx}">${esc(c.name)} (${esc(c.customer_id)}) ${esc(c.phone)}</button>`
    ).join('');
  };

  const addItem = async () => {
    const addBtn = $('item-add');
    const term = $('item-input').value.trim();
    if (!term) return showFormError('Enter a product ID, name or barcode.');
    const qty = parseInt($('item-qty').value, 10);
    if (!Number.isInteger(qty) || qty < 1) return showFormError('Quantity must be a whole number of 1 or more.');

    showFormError('');
    setBusy(addBtn, true);
    try {
      const p = (await api('GET', '/api/products/lookup?q=' + encodeURIComponent(term))) || {};
      if (!p.product_id) throw new Error('Product not found.');
      const existing = billState.items.find((i) => i.product_id === p.product_id);
      if (existing) {
        existing.qty += qty;
      } else {
        billState.items.push({
          product_id: p.product_id,
          name: p.name ?? p.product_id,
          qty,
          selling_rate: Number(p.selling_rate) || 0,
          gst_percent: Number(p.gst_percent) || 0,
        });
      }
      $('item-input').value = '';
      $('item-qty').value = '1';
      $('item-input').focus();
      renderCart();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setBusy(addBtn, false);
    }
  };

  const billReset = () => {
    billState = { customer: null, items: [] };
    billCustResults = [];
    clearTimeout(billSearchTimer);
    $('cust-search').value = '';
    $('cust-results').innerHTML = '';
    $('cust-selected').textContent = '';
    $('credit-info').innerHTML = '';
    $('bill-result').innerHTML = '';
    $('item-input').value = '';
    $('item-qty').value = '1';
    showFormError('');
    renderCart();
  };

  loaders.billing = async () => {
    if (!billingWired) {
      billingWired = true;

      $('cust-search').addEventListener('input', () => {
        clearTimeout(billSearchTimer);
        billSearchTimer = setTimeout(() => {
          searchCustomers().catch((err) => toast(err.message, 'error'));
        }, 250);
      });

      $('cust-results').addEventListener('click', (e) => {
        const btn = e.target.closest('button.cust-pick');
        if (!btn) return;
        const c = billCustResults[Number(btn.dataset.idx)];
        if (c) selectCustomer(c).catch((err) => toast(err.message, 'error'));
      });

      $('new-cust-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = $('nc-name').value.trim();
        if (!name) return showFormError('Customer name is required.');

        const body = {
          name,
          phone: $('nc-phone').value.trim(),
          address: $('nc-address').value.trim(),
          gstin: $('nc-gstin').value.trim(),
          credit_limit: Number($('nc-credit-limit').value) || 0,
        };
        const btn = e.target.querySelector('button[type="submit"]');
        setBusy(btn, true);
        try {
          const c = (await api('POST', '/api/customers', body)) || {};
          showFormError('');
          await selectCustomer({ customer_id: c.customer_id, name: c.name });
          toast('Customer created', 'success');
          e.target.reset();
        } catch (err) {
          showFormError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });

      $('item-add').addEventListener('click', addItem);
      $('item-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          addItem();
        }
      });

      $('cart').addEventListener('change', (e) => {
        if (!e.target.classList.contains('bill-qty')) return;
        const item = billState.items[Number(e.target.dataset.idx)];
        if (!item) return;
        const q = Number(e.target.value);
        if (!Number.isInteger(q) || q < 1) {
          toast('Quantity must be a whole number of 1 or more.', 'error');
          e.target.value = item.qty;
          return;
        }
        item.qty = q;
        renderCart();
      });

      $('cart').addEventListener('click', (e) => {
        const btn = e.target.closest('.bill-remove');
        if (!btn) return;
        billState.items.splice(Number(btn.dataset.idx), 1);
        renderCart();
      });

      $('pay-type').addEventListener('change', () => {
        refreshCredit().catch((err) => toast(err.message, 'error'));
      });

      $('bill-submit').addEventListener('click', async () => {
        const btn = $('bill-submit');
        if (!billState.customer) return showFormError('Select a customer first.');
        if (!billState.items.length) return showFormError('Add at least one item.');

        showFormError('');
        setBusy(btn, true);
        try {
          const inv = (await api('POST', '/api/invoices', {
            customer_id: billState.customer.customer_id,
            payment_type: $('pay-type').value,
            items: billState.items.map((i) => ({ product_id: i.product_id, qty: i.qty })),
          })) || {};
          $('bill-result').innerHTML =
            `<p>Invoice <strong>${esc(inv.invoice_no)}</strong> created. ` +
            `Total: ${money(inv.total_amount)}. Status: ${esc(inv.status)}.</p>`;
          billState.items = [];
          renderCart();
          toast('Invoice ' + (inv.invoice_no ?? '') + ' created', 'success');
        } catch (err) {
          showFormError(err.message);
        } finally {
          setBusy(btn, false);
        }
      });

      $('bill-reset').addEventListener('click', billReset);
    }

    renderCart();
  };



  // ---------- Event wiring ----------
  $('period-select').addEventListener('change', () => {
    loaders.dashboard().catch((err) => toast(err.message, 'error'));
  });

  $('cf-period').addEventListener('change', () => {
    loaders.cashflow().catch((err) => toast(err.message, 'error'));
  });

  $('cf-opening-save').addEventListener('click', async () => {
    const btn = $('cf-opening-save');
    setBusy(btn, true);
    try {
      await api('PUT', '/api/settings/opening-balance', { value: Number($('cf-opening').value) });
      toast('Opening balance saved', 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setBusy(btn, false);
    }
  });

  // ---------- Initialise ----------
  window.addEventListener('hashchange', route);
  route();
});
