# Customer 360 Suite — Wave 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new thin Apps module `invoice_customer_dashboard` (Invoice Customers kanban on `res.partner`) and join it to the CRM↔Sales share pool so AR slots appear on peer cards when Accounting is installed.

**Architecture:** Clone the `sales_customer_dashboard` / `crm_customer_dashboard` preset shape (manifest + seed XML + post_init). Blueprint key `invoice_customers`. Own AR KPIs/menus on this blueprint; reuse Wave 1 `style` / `style_mode` for overdue. Expand share hooks so CRM + Sales + Invoice form one connected component (dedupe by section+key; first wins).

**Tech Stack:** Odoo 19, `dashboard_engine`, `account`, optional soft-deps `account_followup` / `account_reports`, TransactionCase tests.

**Spec:** `docs/superpowers/specs/2026-07-29-customer-360-suite-design.md` (Wave 2)

## Global Constraints

- One dashboard = one Apps module: `invoice_customer_dashboard`
- Host: `res.partner` only; classic card stack (no Layout Studio requirement)
- Hard depends: `dashboard_engine`, `account`
- Soft-hide follow-up / aged report slots via `module_depends` + groups
- Do **not** build Customer 360 hub or Needs attention lens (Wave 3)
- Do **not** invent Category/UTM/Company packs (Wave 4)
- Share: update CRM + Sales + Invoice hooks so install order never drops a peer from the triangle
- Slot keys: prefer unique AR keys for new KPIs; same keys as Sales money boxes (`box_total_due`, `box_total_overdue`) allowed so Invoice-only install still has Due/Overdue (dedupe first-wins)
- Wave 1 health: overdue invoice KPIs / overdue money use `style=danger` + `style_mode=when_positive`
- Do **not** git commit unless the user explicitly asks
- After ship: install/upgrade on `dashboard_engine_v2.ee`, restart `:19016` (conf `http_port`), hard-refresh
- Engine version: bump only if engine code changes (prefer no engine change in Wave 2)

---

## File map

| Path | Responsibility |
|------|----------------|
| `invoice_customer_dashboard/__manifest__.py` | Thin pack: depends `dashboard_engine`, `account` |
| `invoice_customer_dashboard/__init__.py` | Export `post_init_hook` |
| `invoice_customer_dashboard/hooks.py` | Triangle share + publish sync |
| `invoice_customer_dashboard/data/seed_blueprints.xml` | Blueprint, scopes, core KPIs/bottoms |
| `invoice_customer_dashboard/data/seed_blueprint_headers.xml` | Header lines (clone Sales) |
| `invoice_customer_dashboard/data/seed_invoice_parity.xml` | Totals, menus, reports, soft-deps |
| `crm_customer_dashboard/hooks.py` | Union share with Sales + Invoice if present |
| `sales_customer_dashboard/hooks.py` | Union share with CRM + Invoice if present |
| `dashboard_engine/tests/test_dashboard_blueprint.py` | Seed + share-triangle tests (gated if module installed) |

---

### Task 1: Module skeleton + blueprint + headers

**Files:** create under `invoice_customer_dashboard/` as in file map (manifest, init, empty hooks stub, seed_blueprints, seed_headers)

**Interfaces:**
- Produces: xmlid `invoice_customer_dashboard.blueprint_invoice_customers`, key `invoice_customers`
- Menu: parent `account.menu_finance_receivables`, name `Customers Dashboard`, sequence `5`
- Graph: `account.invoice.report`, `graph_data_field=partner_id`, measure `price_total:sum` (or `price_subtotal:sum` if that field exists on report — verify on install), groupby `invoice_date:month`, caption `Invoices`
- Primary: label `Invoice Analysis`, action `account.action_account_invoice_report_all`
- Lenses: My Partners / With KPIs (same pattern as Sales)
- State: `published`, sequence `25` (after Sales `20`)

- [ ] **Step 1: Create package files** matching `sales_customer_dashboard` layout.

- [ ] **Step 2: Seed blueprint + 2–3 scopes** e.g. Posted invoices / Draft / Only mine (domains on `account.move` or report — scopes that filter host cards may use partner commercial fields; prefer invoice-related include scopes if the engine scopes host domain — **match Sales pattern**: Sales scopes filter graph/KPI context via blueprint scopes. Copy Sales scope shape but domains appropriate for invoice story, e.g. customers with invoices. If Sales scopes are on sale.order semantics via blueprint machinery, use partner domain scopes like `[('customer_rank', '>', 0)]` for “Customers” only — keep simple: one include scope “Customers” `[('customer_rank', '>', 0)]` default_on True, one restrict “Only mine” if a sensible partner field exists (skip if none — Sales uses sale order user_id on scopes; for Invoice use commercial partner filter only).

Check how scopes apply — if they inject into graph model domain, use `account.move` domains via graph model. Looking at Sales: scopes have sale order domains — they apply to graph/slots. For Invoice, scopes:

```xml
domain>[('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]</domain>
```

on graph model `account.move` if graph is move-based. **Prefer graph_model=`account.move`** with domain out invoices for simpler scopes:

Revised graph (simpler for Odoo 19):
- `graph_model`: `account.move`
- `graph_data_field`: `partner_id`
- `graph_measure`: `__count` or `amount_untaxed_signed:sum`
- `graph_groupby`: `invoice_date:month`
- `graph_domain`: `[('move_type', '=', 'out_invoice'), ('state', '!=', 'cancel')]`

Primary action can stay invoice report xmlid.

- [ ] **Step 3: Headers** — copy Sales header items (job, location, email, tags) with invoice xmlids.

---

### Task 2: AR slots (KPIs, totals, bottoms, menus)

**Files:** `seed_blueprints.xml` + `seed_invoice_parity.xml`

**Slot map (locked):**

| Section | key | Behavior |
|---------|-----|----------|
| kpi | `open_invoices` | count posted out_invoice not paid (`payment_state` in not_paid/partial/in_payment) |
| kpi | `overdue_invoices` | open + `invoice_date_due` &lt; today; `style=danger` `style_mode=when_positive` |
| kpi | `draft_invoices` | draft out_invoice |
| kpi | `credit_notes` | out_refund posted (or open) |
| button_box | `box_total_due` | host `total_due`; soft `account_followup,account_reports`; method `open_follow_up_report` |
| button_box | `box_total_overdue` | host `total_overdue`; danger + when_positive; soft same |
| bottom | `bottom_invoices` | count out invoices; action customer invoices |
| bottom | `bottom_payments` | optional soft if payments action easy — or skip if noisy; prefer invoices + credit notes bottoms |
| bottom | `bottom_credit_notes` | out_refunds |
| menu_views | `view_invoices`, `view_credit_notes`, `view_payments` (payments soft) |
| menu_new | `new_invoice`, `new_credit_note` |
| menu_reports | `report_invoices`, `report_aged_receivable` (soft enterprise/reports) |

Relate field: `partner_id` on `account.move`. Domains use `{{id}}` in action_domain.

`module_depends` on slots that need follow-up/reports. Groups: `account.group_account_invoice` where Sales used them.

- [ ] **Step 1: Implement KPI + bottom seeds** with compute_model `account.move`.

- [ ] **Step 2: Implement totals + menus** in parity XML.

- [ ] **Step 3: Write failing test** (module installed):

```python
def test_seeded_invoice_customers_slots_exist(self):
    if not self.env["ir.module.module"].search([
        ("name", "=", "invoice_customer_dashboard"), ("state", "=", "installed")
    ]):
        self.skipTest("invoice_customer_dashboard not installed")
    bp = self.env.ref("invoice_customer_dashboard.blueprint_invoice_customers")
    keys = set(bp.slot_ids.mapped("key"))
    for k in ("open_invoices", "overdue_invoices", "box_total_due", "view_invoices", "new_invoice"):
        self.assertIn(k, keys)
    overdue = bp.slot_ids.filtered(lambda s: s.key == "overdue_invoices")
    self.assertEqual(overdue.style, "danger")
    self.assertEqual(overdue.style_mode, "when_positive")
```

- [ ] **Step 4: Install module in test DB / run test green.**

---

### Task 3: Share triangle hooks

**Files:** `invoice_customer_dashboard/hooks.py`, update `crm_customer_dashboard/hooks.py`, `sales_customer_dashboard/hooks.py`

**Interfaces:**
- Produces: helper used by all three packs:

```python
PARTNER_CUSTOMER_BLUEPRINT_XMLIDS = (
    "crm_customer_dashboard.blueprint_crm_customers",
    "sales_customer_dashboard.blueprint_sales_customers",
    "invoice_customer_dashboard.blueprint_invoice_customers",
)

def link_partner_customer_share_pool(env):
    bps = []
    for xid in PARTNER_CUSTOMER_BLUEPRINT_XMLIDS:
        bp = env.ref(xid, raise_if_not_found=False)
        if bp:
            bps.append(bp)
    if len(bps) < 2:
        return
    for bp in bps:
        others = [o.id for o in bps if o.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})
```

Prefer putting the helper in `invoice_customer_dashboard/hooks.py` and duplicating a small copy in CRM/Sales **or** put shared helper in `dashboard_engine` — **YAGNI: duplicate thin 15-line helper in each hooks.py** to avoid engine bump (or one copy in invoice + CRM/Sales call via try import). Cleanest without engine change: **identical helper function text in all three hooks.py** calling the same xmlid tuple.

- [ ] **Step 1: Implement invoice post_init** — link pool + `_sync_generated_artifacts` if published.

- [ ] **Step 2: Replace CRM/Sales pairwise link with triangle helper.**

- [ ] **Step 3: Test**

```python
def test_invoice_customers_joins_share_triangle(self):
    # skip if any of three missing
    crm = self.env.ref("crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False)
    sale = self.env.ref("sales_customer_dashboard.blueprint_sales_customers", raise_if_not_found=False)
    inv = self.env.ref("invoice_customer_dashboard.blueprint_invoice_customers", raise_if_not_found=False)
    if not all((crm, sale, inv)):
        self.skipTest("partner customer packs incomplete")
    # re-run linker
    from odoo.addons.invoice_customer_dashboard.hooks import link_partner_customer_share_pool
    link_partner_customer_share_pool(self.env)
    self.assertIn(inv, crm.share_link_ids)
    self.assertIn(crm, inv.share_link_ids)
    # CRM effective slots include an invoice-only key
    eff_keys = set(crm._effective_slots().mapped("key"))
    self.assertIn("open_invoices", eff_keys)
```

---

### Task 4: Ship verify

- [ ] Mark plan checkboxes; update suite spec Wave 2 status line if present.
- [ ] Install: `-i invoice_customer_dashboard` or `-u` on `dashboard_engine_v2.ee`
- [ ] Restart `:19016`, login 200
- [ ] Manual: Accounting → Customers Dashboard; CRM/Sales cards show shared AR KPIs when account installed
- [ ] Commit only if user asks

---

## Spec coverage

| Spec Wave 2 item | Task |
|------------------|------|
| Invoice Customers app | 1–2 |
| Share into CRM/Sales | 3 |
| Soft-hide account extras | 2 (`module_depends`) |
| Classic stack / partner host | 1 |
| Not Wave 3/4 | Global |

## Out of scope

Vendor bills, Customer 360 hub, Needs attention lens, Category/UTM/Company.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-29-customer-360-wave2-invoice-customers.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task  
2. **Inline Execution** — this session with checkpoints  

Which approach?
