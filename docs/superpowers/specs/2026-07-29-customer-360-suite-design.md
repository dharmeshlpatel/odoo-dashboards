# Customer 360 Suite — Market Catalog Design

**Date:** 2026-07-29  
**Status:** Approved · Wave 1 done (uncommitted) · Wave 2 plan: `docs/superpowers/plans/2026-07-29-customer-360-wave2-invoice-customers.md`  
**Repo:** `odoo-dashboards-19.1-v2`  
**Engine:** `dashboard_engine`  
**Audience:** Full suite (Sales/CRM + Finance + Ops)  
**Hero:** Customer 360 on `res.partner`

## Positioning (one line)

> Sell a **dense, cross-app, insight-aware** dashboard suite. Daily work stays in CRM / Sales / Accounting apps; **Customer 360** is the manager + App Store hero built from shared slots.

## Locked decisions

| Topic | Choice |
|-------|--------|
| Buyer | Full suite (CRM, finance, ops) |
| Richness | Dense slots + cross-app + light insights |
| Hero | Customer 360 (`res.partner`) |
| Product shape | Both: enrich daily apps **and** premium 360 hub |
| Insights depth | Light engine add-ons (health bands, Needs attention lens, captions) — no AI/scores in v1 |
| Missing apps | Soft-hide slots via `module_depends` |
| Build approach | Apps-first, hub second (Approach 1) |
| Card layout | Classic stack (not KPI\|chart side-by-side for hero) |

## Classic card stack (spatial layout)

Do **not** put the chart between left/right KPI columns. Use the existing engine stack:

```
┌─────────────────────────────────────────────┐
│  HEADER  · host title                       │
├──────────────────────┬──────────────────────┤
│  PRIMARY button      │  KPIs (section: kpi) │
├──────────────────────┴──────────────────────┤
│              CHART (full width)             │
├──────────────────────────┬──────────────────┤
│  TOTALS (button_box)  │  BOTTOMS         │
└──────────────────────────┴──────────────────┘
     ⋮ menu → Views / New / Reports
```

| Product name | Engine section | Placement |
|--------------|----------------|-----------|
| Action KPIs | `kpi` | Top row, beside primary |
| Chart | `graph` | Middle, full width |
| Money / stock totals | `button_box` | Footer |
| Bottoms | `bottom` | Footer beside totals |
| Views / New / Reports | `menu_views` / `menu_new` / `menu_reports` | Card ⋮ menu |

Layout Studio may allow other compositions later; **Customer 360 v1 ships classic stack**.

---

## Ship waves

| Wave | Deliver | Market story |
|------|---------|--------------|
| **1** | Enrich CRM Customers + Sales Customers (denser slots + soft health on existing KPIs) | Richer than stock Odoo kanban |
| **2** | New **Invoice Customers** + share into CRM/Sales | Money story complete |
| **3** | **Customer 360** hub + Needs attention lens | Screenshot hero |
| **4** | Category → Attribution (Campaign/Medium/Source) → Company → Vendor Bills | Suite breadth |

### Approach 1 (locked)

1. Enrich daily partner apps first.  
2. Add Invoice Customers.  
3. Compose Customer 360 from shared slots.  
4. Apply light insights as soon as health rules exist (can start on Wave 1 KPIs).

---

## Customer 360 card (hero detail)

**Host:** `res.partner`  
**Blueprint key (proposed):** `customer_360`  
**Graph:** open CRM pipeline by stage (`crm.lead`, relate `partner_id`)  
**Primary:** Pipeline Analysis  
**Soft-hide:** Account/Stock-dependent slots vanish when modules missing  

### Slots (Option A — dense)

| Zone | Keys / labels | Notes |
|------|---------------|-------|
| **KPIs** | Open Opps · Overdue Opps · To Deliver · To Invoice | Optional extras via conditions: Unassigned, To Upsell |
| **Totals** | Total Due · Total Overdue · Open Invoices | Reuse follow-up / invoice amounts where available |
| **Bottoms** | Opportunities · Orders · Invoices · Transfers | Four bottoms for hero density |
| **Views** | Leads · Opportunities · Quotations · Orders · Invoices · Transfers | |
| **New** | Lead · Opportunity · Quotation · Invoice | |
| **Reports** | Pipeline · Sales · Invoices · Activities · Aged receivable | Soft-hide enterprise/report deps |

### Health (examples)

| Signal | Band |
|--------|------|
| Overdue Opps &gt; 0 | Red |
| Total Overdue &gt; 0 | Red |
| To Invoice &gt; 0 | Amber |
| Otherwise | Neutral / green when all clear |

### Needs attention lens

Include partner when **any** of:

- Overdue opportunities &gt; 0  
- Total overdue &gt; 0 (when Account follow-up available)  
- Orders to invoice &gt; 0  

Also keep existing lenses: My / With KPIs (names may vary per blueprint).

### Daily apps relationship

| App | Role |
|-----|------|
| CRM Customers | Pipeline-first; shares Sales/Invoice slots where installed |
| Sales Customers | Ops-first (quote → deliver → invoice); shares money boxes |
| Invoice Customers | AR-first; new preset app |
| Customer 360 | Manager hub; composes shared partner slots; richest menus |

**Share rule:** one slot definition linked across partner-host blueprints — no copy-paste drift.

---

## Light insights (engine scope)

### In scope (v1)

1. **Health bands** on slots — green / amber / red from count or amount thresholds (blueprint-configurable).  
2. **Needs attention lens** — domain/filter driven by configured “attention” slots or explicit domain helper.  
3. **Graph captions** — clear story labels (already supported).

### Out of scope (v1)

- AI summaries, predicted churn, composite health scores  
- Locked/teaser UI for missing modules (soft-hide only)  
- Changing classic stack for hero cards  

### Soft-hide (locked)

Missing `account` / `stock` / report modules → related slots hidden via existing `module_depends` (and groups where needed).

---

## Later packs (Wave 4 clones)

Same classic stack + insights. Change host + relate field only.

| Pack | Host | Graph | KPI focus | Totals | Bottoms |
|------|------|-------|-----------|--------|---------|
| Sales by Product Category | `product.category` | Sales € / month | Quotes · Deliver · Invoice · Upsell | Revenue · Margin or stock proxy | Orders · Products · Transfers |
| Stock by Product Category | `product.category` | Moves / week | On hand · Reserved · Forecast · Reorder | Stock value · Incoming | Products · Transfers |
| CRM by Campaign / Medium / Source | `utm.campaign` / `medium` / `source` | Pipeline by stage | Open · Overdue · Won · Lost | Expected € · Won € | Opps · Activities |
| Sales by Campaign / Medium / Source | same UTM hosts | Sales € / month | Quotes · Orders · To invoice | Revenue · Avg order | Orders · Invoices |
| Company · CRM / Sales / Invoice | `res.company` | Same as sibling app | Rollup KPIs | Due / Revenue | Scoped bottoms |
| Vendor Bills | `res.partner` (supplier) | Bills / month | To pay · Overdue · Draft | Amount due · Overdue | Bills · Payments |

### Clone rules

1. One template per story type: CRM funnel · Sales ops · Invoice AR/AP · Stock.  
2. New dashboard = new host + relate (`campaign_id`, `medium_id`, `source_id`, `categ_id`, `company_id`).  
3. Soft-hide and health reuse engine features.  
4. Skip UTM on pure Inventory; skip Invoice UTM unless attribution fields exist on invoices/SOs.

### Wave 4 order

1. Category (Sales + Stock)  
2. Attribution trio (Campaign → Medium → Source)  
3. Company trio  
4. Vendor Bills  

---

## Proposed modules (indicative)

| Module | Wave |
|--------|------|
| Enrich `crm_customer_dashboard` / `sales_customer_dashboard` | 1 |
| `invoice_customer_dashboard` (new) | 2 |
| `customer_360_dashboard` (new hub) | 3 |
| Engine: health bands + attention lens on `dashboard_engine` | 1–3 |
| Category / UTM / Company / Vendor preset apps | 4 |

Exact xmlids and blueprint keys are fixed in the implementation plan.

---

## Success criteria

- App Store screenshots show a full Customer 360 card: primary + KPIs + chart + totals + bottoms + menus.  
- Installing only CRM+Sales still yields a useful card (Invoice/Stock soft-hidden).  
- Needs attention lens surfaces overdue money/pipeline without custom code per customer.  
- Later packs ship as clones without new layout patterns.

## Non-goals (this design)

- Replacing Odoo Spreadsheet / Accounting dashboards  
- Heavy BI / multi-chart widgets on one card  
- AI or predictive scoring  
- Hard depends on `account`+`stock` for the 360 app  

---

## Next step

After user approves this spec → write implementation plan via writing-plans (Wave 1 first: enrich CRM/Sales + health foundations).
