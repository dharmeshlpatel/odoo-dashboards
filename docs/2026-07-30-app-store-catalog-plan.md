# Dashboard App Store Catalog Plan

> **Repo:** `odoo-dashboards-19.1-v2`
> **Date:** 2026-07-30
> **Author:** Agent review — product catalog strategy
> **Purpose:** Define what to build, what to skip, and the ship order for the Odoo App Store

---

## 1. Core Distinction — Two Product Types

Before listing apps, every item must be classified as one of two fundamentally different products:

| Type | Meaning | Example |
|------|---------|---------|
| **Daily board** | Single-app story. One host, one data source. Used daily by the team working in that app. | CRM Customers, Sales Products |
| **360 hub** | Cross-app compose for managers. Pulls KPIs from multiple daily boards via share pool. | Customer 360, Salesperson 360 |

> **Key rule:**
> "Customer-wise everything" = **Customer 360** (hub).
> "CRM customer-wise" = **CRM Customers** (daily).
> Both are useful — they are not the same product and must never be merged.

**Why this matters for the App Store:**
- A hub with thin data looks broken. Build daily packs first, then compose the hub.
- Building every channel × every host as a full board = 40+ menus, most empty, confusing buyers.

---

## 2. Current Inventory

### 2.1 360 Hubs

| Hub | Status | Notes |
|-----|--------|-------|
| Customer 360 | ✅ Exists | Phase 1 densify: overdue amount + Website/POS share |
| Salesperson 360 | ✅ Phase 1 | Compose CRM + Sales salesperson packs |
| Product 360 | ✅ Phase 2 | Sales + Stock + POS + Website product share |
| Product Category 360 | ✅ Phase 2 | Sales + Stock category share |
| Company 360 | ✅ Phase 2 | Host `res.company` (Q3 partner migrate deferred) |
| Sales Team 360 | ❌ Missing | Dailies exist (Phase 1); hub not required yet |
| Warehouse 360 | ✅ Phase 3 | Location scopes on hub |
| Website 360 | ✅ Phase 5 | Host locked to `website.website` |
| POS Product 360 | ✅ Phase 5 | Shares product pool under POS Reporting |
| POS Category 360 | ❌ Hold | No POS category daily — skip per Tier C |

### 2.2 Daily Boards

| Board | Status |
|-------|--------|
| CRM Customers | ✅ |
| CRM Campaign / Medium / Source | ✅ |
| CRM Salesperson | ✅ |
| CRM Company | ✅ (`company_crm`) |
| **CRM Sales Team** | ✅ Phase 1 |
| Sales Customers | ✅ |
| Sales Campaign / Medium / Source | ✅ |
| Sales Salesperson | ✅ |
| Sales Company | ✅ |
| Sales Products | ✅ |
| Sales Product Category | ✅ |
| **Sales Team** | ✅ Phase 1 |
| Invoice Customers (AR daily) | ✅ |
| Vendor Bills | ✅ |
| Website Customers | ✅ |
| Website Products | ✅ |
| Website UTM / Team / Company / Category | ❌ Missing |
| POS Customers | ✅ |
| POS Products | ✅ |
| POS UTM / Team / Company / Category / Session | ❌ Missing |
| Warehouse | ✅ (overview) |
| Stock Products | ✅ Phase 2 |
| Stock Category | ✅ |
| Location | ❌ Missing (by design — scope in Warehouse 360) |
| POS Sessions | ✅ Phase 4 |

---

## 3. Tier Classification

### Tier A — Build now (clear buyer, data exists)

| Item | Type | Reason |
|------|------|--------|
| **Sales Team** (CRM + Sales daily) | Daily | Biggest gap — present in every instance, no board today |
| **Salesperson 360** | Hub | Compose from existing CRM + Sales packs |
| **Product 360** | Hub | Sales + Stock packs exist; clear buyer (product managers) |
| **Product Category 360** | Hub | Category packs exist; logical extension of Product 360 |
| **Company 360** | Hub | Three daily packs exist; essential for B2B buyers |
| **Warehouse 360** | Hub | Stock pack exists; clear ops story |
| Customer 360 (densify) | Hub | Add Invoice + Website KPIs to what's already live |

### Tier B — Build later (only when the channel generates revenue)

| Item | Type | Reason |
|------|------|--------|
| Website UTM / Category / Company daily boards | Daily | Clone the Sales UTM pattern when Website is a paid add-on |
| Website 360 | Hub | Hold until host model is confirmed |
| POS Category 360 / Product 360 | Hub | After POS daily packs are denser |
| POS Session board | Daily | Useful for shop managers; one board, not 9 POS clones |

### Tier C — Skip as full matrix (weak / confuses buyers)

| Item | Why to skip |
|------|------------|
| Full Website × (campaign + source + medium + team + company + category) | Use scopes + soft-share on existing boards instead of 9 new apps |
| Full POS × UTM matrix | POS often has no UTM data; boards will be empty |
| Location board (standalone) | Too narrow — add location scopes to Warehouse 360 instead |
| "Everything 360" for every host at once | Thin in the App Store; confuses buyers |

> **Rule for Website/POS channel gaps:**
> Use the v2 engine's **scope + soft-share** pattern.
> One "Website Customers" app with a "Campaigns" scope toggle beats 6 separate apps.

---

## 4. Recommended Ship Sequence

```
Phase 1 — Tier A foundations
  ├── Sales Team daily board (CRM + Sales)    ← biggest gap, affects every instance
  ├── Salesperson 360                          ← compose from existing packs
  └── Customer 360 (densify — Invoice + Website KPIs)

Phase 2 — Tier A hubs
  ├── Product 360
  ├── Product Category 360
  └── Company 360

Phase 3 — Ops
  └── Warehouse 360

Phase 4 — Next channel (when ready)
  ├── POS Session board (daily)
  ├── POS Customers + Products (densify existing)
  └── Website Customers + Products (densify existing)

Phase 5 — Website / POS full story
  ├── Website 360 (after host model confirmed)
  └── POS Product 360 / POS Category 360
```

---

## 5. Implementation Rules

### For every new Daily board

1. Host model decided and locked before any KPI work starts
2. Data must be non-empty for ≥ 80% of target instances — validate before shipping
3. Missing module → show `"—"` or hide the KPI block — never fake zeros
4. One clear primary graph + supporting KPIs — not a kitchen sink
5. `soft_module_depends` on every KPI that requires an optional module

### For every new 360 hub

1. Minimum **two** daily packs must be published before the hub starts
2. Hub uses `share_link_ids` — never duplicates model/domain config
3. Every KPI carries `soft_module_depends` — hides cleanly if source app not installed
4. Hub card shows a graceful "not installed" state when a linked board is absent

### Anti-patterns to avoid

| Anti-pattern | Correct approach |
|-------------|-----------------|
| Clone full CRM matrix for every new channel | Add scopes + soft-share on the existing board |
| Build a hub before both daily packs exist | Ship daily packs first, hub second |
| Name a hub after the app ("CRM 360") | Name after the business object ("Customer 360") |
| Build Location as a standalone app | Add location scopes to Warehouse 360 |
| Build POS UTM / source / medium boards | Use POS Customers scopes instead |

---

## 6. App Store Naming Convention

| Pattern | Correct example | Wrong |
|---------|----------------|-------|
| `{App} {Host}s` | CRM Customers, Sales Products | ~~CRM Customer Board~~ |
| `{Host} 360` | Customer 360, Product 360 | ~~CRM 360~~ |
| `{App} {Management Object}` | CRM Sales Team, Sales Team | ~~Team 360 CRM~~ |
| Scope for channel variants | CRM Customers + "Pipeline" scope | ~~CRM Customer Campaigns~~ (standalone) |

---

## 7. Architectural Decisions — Resolved

> All answers verified against live Odoo 19 source models.
> These are **locked decisions**, not suggestions.

---

### Q1 — Sales Team host model: `crm.team`

**Decision: `crm.team` is the host model.**

**Why:**
- `crm.lead.team_id → crm.team` (verified: `crm/models/crm_lead.py` line 111)
- `sale.order.team_id → crm.team` (verified: `sale/models/sale_order.py` line 216)
- Both CRM and Sales use the same FK. The join `[('team_id', '=', host.id)]` works identically across both models — no grouping needed.
- `crm.team` has `name`, `member_ids → res.users`, `company_id`, and `is_membership_multi`. It is the canonical sales team object in Odoo.
- `res.users grouped by team` would require a computed groupby — it's a query design, not a host. Never use a query design as a card host.

**KPI domain pattern:**
```python
# crm.lead KPIs:
[('team_id', '=', host.id)]

# sale.order KPIs:
[('team_id', '=', host.id)]

# No join needed — same field name, same comodel on both sides
```

**Card header:** `crm.team.name` as title. No image field on `crm.team` → use the team color or initials widget.

**Menu:** `crm.crm_menu_report` for CRM Sales Team daily; `sale.menu_sale_report` for Sales Team daily.

---

### Q2 — Salesperson 360 host: `res.users`

**Decision: `res.users` is the host model.**

**Why:**
- `crm.lead.user_id → res.users` (verified: `crm/models/crm_lead.py` line 104)
- `sale.order.user_id → res.users` (verified: `sale/models/sale_order.py` line 207)
- `account.move` does not have a salesperson FK — invoices join via `partner_id` or `invoice_user_id → res.users`
- `hr.employee.user_id → res.users` (verified: `hr/models/hr_employee.py` line 86-88, a `related` on `resource_id.user_id`)

**The key architectural rule:** Every daily pack (CRM, Sales, Invoice) joins on `user_id → res.users`. If the host were `hr.employee`, every KPI would need `[('user_id', '=', host.user_id.id)]` — an extra hop with no benefit.

**`hr.employee` is NOT the host**, but it *can* enrich the card header:
- Use `hr.employee` (found via `env['hr.employee'].search([('user_id','=',host.id)])`) to get the employee photo and job title for the card header image.
- All KPI domains use `host.id` directly against `user_id`.

**KPI domain pattern:**
```python
# crm.lead KPIs:
[('user_id', '=', host.id)]

# sale.order KPIs:
[('user_id', '=', host.id)]

# account.move (invoice_user_id):
[('invoice_user_id', '=', host.id), ('move_type', 'in', ['out_invoice', 'out_refund'])]
```

**Card header:** `res.users.name` as title; `hr.employee` image via `soft_module_depends='hr'` — shows avatar when HR is installed, falls back to user initials when not.

---

### Q3 — Company 360 host: `res.partner` filtered by `is_company=True`

**Decision: `res.partner` with `is_company=True` is the host. Use `commercial_partner_id` for joins.**

**Why:**
- `commercial_partner_id` is the canonical company-level grouping field on every partner (verified: `res_partner.py` line 302, 514-519).
- `commercial_partner_id` self-references: if the partner IS a company, it equals itself. If it's a contact, it points to its parent company.
- This means `[('partner_id.commercial_partner_id', '=', host.id)]` captures all contacts, child companies, and the company itself in one domain — across CRM, Sales, and Invoice.

**Why NOT a dedicated "commercial partner" view:**
- There is no `commercial.partner` model in Odoo. Creating one adds a sync problem. `res.partner` with `is_company=True` is the native Odoo pattern.

**KPI domain pattern:**
```python
# crm.lead:
[('partner_id.commercial_partner_id', '=', host.id)]

# sale.order:
[('partner_id.commercial_partner_id', '=', host.id)]

# account.move:
[('commercial_partner_id', '=', host.id), ('move_type', 'in', ['out_invoice', 'out_refund'])]
# Note: account.move has commercial_partner_id directly — no extra hop
```

**Host domain in blueprint:**
```python
[('is_company', '=', True), ('active', '=', True)]
```

**Aligns with existing `company_crm` pack:** the existing pack almost certainly uses this same domain — confirm before building Company 360 to ensure share pool consistency.

---

### Q4 — Customer 360 primary Invoice KPI: **Overdue amount**

**Decision: Overdue amount (`amount_residual` where `invoice_date_due < today`) is the primary Invoice KPI.**

**Rationale:**
- `amount_total` (total billed) is a vanity metric — it goes up regardless of collection health.
- Open invoices count is useful but doesn't communicate urgency.
- **Overdue amount is the one number a manager acts on.** It drives calls, follow-ups, and collection workflows.
- It is computable from `account.move` without any extra module: `amount_residual` (verified: `account_move.py` line 559) + `invoice_date_due < today` + `payment_state in ('not_paid', 'partial')` + `state = 'posted'`.

**Supporting KPIs (secondary, in order):**
1. Open invoices count (total unpaid, not overdue)
2. Total billed this period (`amount_total`, current month/quarter scope)
3. Average days to pay (requires payment date history — `soft_module_depends`)

**Primary graph:** Bar chart — overdue amount by age bucket (0–30d, 31–60d, 61–90d, 90d+). This is the standard AR aging view and gives immediate visual priority.

**Domain for primary KPI:**
```python
[
    ('commercial_partner_id', '=', host.id),
    ('move_type', 'in', ['out_invoice', 'out_refund']),
    ('state', '=', 'posted'),
    ('payment_state', 'in', ['not_paid', 'partial']),
    ('invoice_date_due', '<', fields.Date.today()),
]
```
Measure: `SUM(amount_residual)`

---

### Q5 — Location: scope inside Warehouse 360, NOT a standalone app

**Decision: Location is a scope filter inside Warehouse 360. No standalone Location app.**

**Why:**
- `stock.location.warehouse_id` is a stored computed field on every location (verified: `stock_location.py` line 85). The location already knows its warehouse.
- A per-location board would show KPIs for a single bin/zone — useful in large warehouses with 50+ locations, but almost always empty for the 80% of instances with 2–5 internal locations.
- The right pattern: Warehouse 360 hosts `stock.warehouse`, and users switch between locations via a scope dropdown (e.g. "Shelf A / Shelf B / All") using the `location_id` domain filter.

**Scope domain pattern inside Warehouse 360:**
```python
# "All locations" scope (default — no extra filter):
[('location_id.warehouse_id', '=', host.id)]

# Specific location scope (user-configurable):
[('location_id', '=', scope_location_id)]
```

**Exception — when a standalone Location app makes sense:** Only if the customer has a multi-warehouse, multi-location 3PL setup with dedicated location managers. That is a Phase 5 enterprise add-on, not a base App Store product.

---

### Summary Table — All Decisions

| # | Question | Answer | Confidence |
|---|---------|--------|-----------|
| 1 | Sales Team host model | `crm.team` — direct FK in both CRM and Sales | ✅ Locked |
| 2 | Salesperson 360 host | `res.users` — all packs join on `user_id`; use `hr.employee` for header image only | ✅ Locked |
| 3 | Company 360 host | Shipped on `res.company` to match existing dailies; Q3 `res.partner` migrate = follow-up | ⚠️ Deferred |
| 4 | Customer 360 primary Invoice KPI | Overdue amount (`amount_residual` where `invoice_date_due < today`) | ✅ Locked |
| 5 | Location vs standalone | Location is a scope inside Warehouse 360 — no standalone app | ✅ Locked |

---

## 8. Menu Placement — Reporting Submenu Rule

### 8.1 The Rule

> **Every dashboard must be placed under the `Reporting` submenu of its own app's main menu.**
>
> It must **never** appear at the top level of the main navigation, and **never** under a generic "Dashboards" menu that sits outside the app.
>
> 360 hubs are the **one exception** — they compose cross-app data and belong under a dedicated top-level "360" group or under the primary app that owns the host model.

### 8.2 How it works in the engine

The blueprint field [`menu_parent_id`](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/models/dashboard_blueprint.py#L479-L488) (`ir.ui.menu`) sets exactly where the generated menu entry appears.

Set it via `menu_parent_xmlid` in Studio or in blueprint XML data:

```xml
<field name="menu_parent_xmlid">crm.crm_menu_report</field>
```

The engine then generates the `ir.ui.menu` record under that parent automatically on publish.

### 8.3 Confirmed Reporting Menu `xmlid` Map

| App | Reporting menu `xmlid` | Notes |
|-----|----------------------|-------|
| **CRM** | `crm.crm_menu_report` | Verified in `crm_menu_views.xml` line 60 |
| **Sales** | `sale.menu_sale_report` | Verified in `sale_menus.xml` line 73 |
| **Invoicing / Accounting** | `account.menu_finance_reports` | Verified in `account_menuitem.xml` line 37 |
| **Inventory / Stock** | `stock.menu_warehouse_report` | Verified in `stock_menu_views.xml` line 36 |
| **Point of Sale** | `point_of_sale.menu_report_daily_details` (parent) | POS reporting is one level deeper — use the POS Reporting root |
| **Website** | Add under `website.menu_website` → create a Reporting child | No standard Reporting menu exists; create one in the module |
| **360 hubs** | Customer 360 → `crm.crm_menu_report` **and** `sale.menu_sale_report` | Hub appears in both apps' Reporting via `module_ids` multi-app |

> **POS note:** POS uses `point_of_sale.menu_report_daily_details` as the Reporting section root.
> Confirm the exact parent before publishing POS boards — it may vary between `point_of_sale` and `pos_restaurant`.

### 8.4 Complete Board → Menu Placement Map

| Board | `menu_parent_xmlid` |
|-------|---------------------|
| CRM Customers | `crm.crm_menu_report` |
| CRM Campaign / Medium / Source | `crm.crm_menu_report` |
| CRM Salesperson | `crm.crm_menu_report` |
| CRM Company | `crm.crm_menu_report` |
| CRM Sales Team | `crm.crm_menu_report` |
| Sales Customers | `sale.menu_sale_report` |
| Sales Campaign / Medium / Source | `sale.menu_sale_report` |
| Sales Salesperson | `sale.menu_sale_report` |
| Sales Company | `sale.menu_sale_report` |
| Sales Products | `sale.menu_sale_report` |
| Sales Product Category | `sale.menu_sale_report` |
| Sales Team | `sale.menu_sale_report` |
| Invoice Customers (AR daily) | `account.menu_finance_reports` |
| Vendor Bills | `account.menu_finance_reports` |
| Website Customers | `website.menu_website` → `[new] Reporting` child |
| Website Products | `website.menu_website` → `[new] Reporting` child |
| POS Customers | `point_of_sale.menu_report_daily_details` |
| POS Products | `point_of_sale.menu_report_daily_details` |
| Warehouse (overview) | `stock.menu_warehouse_report` |
| Stock Category | `stock.menu_warehouse_report` |
| **Customer 360** | `crm.crm_menu_report` (primary) |
| **Salesperson 360** | `crm.crm_menu_report` + `sale.menu_sale_report` |
| **Product 360** | `sale.menu_sale_report` + `stock.menu_warehouse_report` |
| **Product Category 360** | `sale.menu_sale_report` + `stock.menu_warehouse_report` |
| **Company 360** | `crm.crm_menu_report` (primary) |
| **Warehouse 360** | `stock.menu_warehouse_report` |

### 8.5 Rules for 360 hub menu placement

A 360 hub may appear in **more than one** app's Reporting menu using `share_link_ids` or by setting `module_ids` to include all source apps. Example for Salesperson 360:

```xml
<!-- Appears in CRM → Reporting AND Sales → Reporting -->
<field name="module_ids" eval="[(4, ref('crm.crm')), (4, ref('sale.sale'))]"/>
<field name="menu_parent_xmlid">crm.crm_menu_report</field>
```

> **Never** place a 360 hub at the Odoo top-level menu root. It must always be inside a Reporting submenu.

### 8.6 Website Reporting menu (create once per module)

Since Website has no standard `Reporting` child menu, create one in the website-dashboard module's XML data, then reference it:

```xml
<!-- Create once in the website dashboard module -->
<menuitem id="menu_website_report"
          name="Reporting"
          parent="website.menu_website"
          sequence="90"/>

<!-- Then use it as the parent for all website boards -->
<field name="menu_parent_xmlid">your_module.menu_website_report</field>
```

