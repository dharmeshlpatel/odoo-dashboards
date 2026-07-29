# Customer 360 Suite — Wave 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Customer 360 hub app and a Needs attention kanban lens so managers see partners with overdue pipeline, overdue money, or orders to invoice.

**Architecture:** Engine adds `is_attention_signal` on slots plus `lens_attention_*` on blueprints (virtual domain flag `dashboard_needs_attention`, rewritten like My / With KPIs). Thin module `customer_360_dashboard` owns the hero blueprint (`customer_360`) and joins the partner-customer share pool (CRM + Sales + Invoice + 360). Attention signal slots stay owned by daily apps; 360 composes them via share.

**Tech Stack:** Odoo 19, `dashboard_engine`, `crm`, `contacts`, TransactionCase tests.

**Spec:** `docs/superpowers/specs/2026-07-29-customer-360-suite-design.md` (Wave 3)

## Global Constraints

- One dashboard = one Apps module: `customer_360_dashboard`
- Host: `res.partner`; classic card stack
- Hard depends: `dashboard_engine`, `crm`, `contacts`
- Soft-hide Account/Stock/Sale slots via existing share + `module_depends` (no locked teaser UI)
- Needs attention = union of hosts where any effective `is_attention_signal` slot has count or amount &gt; 0
- Locked attention seeds: CRM `overdue_opportunities`; Sales `to_invoice` + `box_total_overdue`; Invoice `overdue_invoices` + `box_total_overdue`
- Do **not** invent Category/UTM/Company/Vendor packs (Wave 4)
- Engine version bump to `19.0.1.0.112` + post-migrate attention flags on existing DBs
- Do **not** git commit unless the user explicitly asks
- After ship: install/upgrade on `dashboard_engine_v2.ee`, restart conf `http_port` (expect `:19016`), hard-refresh

---

## File map

| Path | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | `lens_attention_*`, `is_attention_signal`, host-id helper, search arch / action context |
| `dashboard_engine/models/base.py` | Rewrite `dashboard_needs_attention` |
| `dashboard_engine/views/dashboard_blueprint_views.xml` | Form + list columns for attention |
| `dashboard_engine/migrations/19.0.1.0.112/post-wave3-attention.py` | Mark seed slots + enable lens on 360 if present |
| `dashboard_engine/tests/test_dashboard_lens.py` | Attention rewrite + positive host ids |
| `dashboard_engine/tests/test_dashboard_blueprint.py` | 360 seed + share square |
| `customer_360_dashboard/*` | Thin hub module |
| `crm/sales/invoice_customer_dashboard/hooks.py` | Expand share pool xmlids |
| Seed XML on CRM/Sales/Invoice | `is_attention_signal` True on locked keys |

---

### Task 1: Engine Needs attention lens

**Files:** `base.py`, `dashboard_blueprint.py`, views, migration, `__manifest__.py` version `19.0.1.0.112`

- [ ] **Step 1:** Add blueprint fields `lens_attention_enabled` / `default` / `label`; slot Boolean `is_attention_signal`.

- [ ] **Step 2:** Implement `slot._lens_attention_positive_host_ids()` (host fields or related read_group) and `blueprint._lens_attention_host_ids()` (union over effective attention slots).

- [ ] **Step 3:** Extend `_search_arch`, `_upsert_search_view` fallback, `_lens_action_context`, constraints (label required when enabled), and `base._dashboard_lens_rewrite_domain` for `dashboard_needs_attention`.

- [ ] **Step 4:** Studio/form UI next to With KPIs; slot list optional column `is_attention_signal`.

- [ ] **Step 5:** Tests — label required; rewrite → `id in …`; positive hosts from compute_model count and host amount field.

---

### Task 2: Mark attention slots on daily apps

**Files:** CRM/Sales/Invoice seed XML (+ migration write for existing DBs)

- [ ] **Step 1:** Set `is_attention_signal` on locked keys listed above.

- [ ] **Step 2:** Migration mirrors XML for already-installed DBs.

---

### Task 3: `customer_360_dashboard` module + share square

**Files:** new module; update four `hooks.py` tuples

- [ ] **Step 1:** Manifest depends `dashboard_engine`, `crm`, `contacts`; post_init share + sync.

- [ ] **Step 2:** Seed blueprint `customer_360`: graph/pipeline like CRM Customers; menu parent `contacts.menu_contacts`; sequence `5` on menu; blueprint `sequence` `5` (first-wins for any own slots); lenses My + With KPIs + Needs attention (attention default **True**); state published. **No own KPI slots** — compose via share.

- [ ] **Step 3:** Minimal scopes (Pipeline default_on) + headers clone CRM (or thin set).

- [ ] **Step 4:** Expand `PARTNER_CUSTOMER_BLUEPRINT_XMLIDS` in CRM/Sales/Invoice/360 hooks.

- [ ] **Step 5:** Tests: 360 seed exists; share pool size ≥ 2 when peers installed; attention enabled on 360.

---

### Task 4: Install / verify

- [ ] **Step 1:** `-u dashboard_engine -i customer_360_dashboard` on `dashboard_engine_v2.ee`, restart, HTTP 200 on login.

- [ ] **Step 2:** Confirm menu under Contacts; Needs attention filter present; shared slots visible when Sale/Account installed.
