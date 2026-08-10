# App Store Demo Data — Developer / AI Agent Handover (Standard Odoo Only)

> **Date:** 2026-08-06 (rev: AI agent runbook)  
> **Audience:** Human developer **or** Gemini/Cursor AI agent  
> **Scope:** Odoo **standard modules only** — no custom dashboard apps  
> **Bar:** Data must be **more than enough** for **every** dashboard we ship (daily boards + all 360 hubs). Sparse boards are a fail.

### Is this MD enough for Gemini to build automatically?

| Part | Enough alone? | Role |
|------|---------------|------|
| §§1–10 + Appendix A | **No** — product/spec only | What & how much |
| **§11 AI Agent Runbook** | **Yes — use as the execution prompt** | How to build, install, verify |

**Prompt to the AI:**  
“Follow `2026-08-06-app-store-demo-data-and-media-handover.md` end-to-end. Implement §11. Obey volume §3 and coverage §4. Do not install any gritxi/dashboard module.”

**Still needed from the human once (fill into §11.1):** Odoo path, Python/venv, config file, Postgres access, addons path where the new module will live.

---

## 1. Mission

Build one reproducible dataset (`apps_store_demo_data` module or script) so that when product later installs our dashboard packs, **every board is dense**.

| You do | You do not |
|--------|------------|
| Master data + transactions in standard Odoo | Install gritxi / dashboard modules |
| Cover **all** rows in §4–§5 | Screenshots / Studio / blueprints |
| QA in standard menus (§7) | Guess which boards exist |

**Rule:** If a later dashboard groups by host X, then **≥80% of visible hosts** must have real activity — not empty cards.

**DB name:** `apps_store_demo_std`

---

## 2. Install standard apps (all required for full catalog)

To cover **all** our dashboards, install **everything below** on one company. Do not ship P0-only if the goal is full 360 coverage.

| App | Technical | Needed for |
|-----|-----------|------------|
| Contacts | `contacts` / `base` | All partner hosts |
| CRM | `crm` | CRM boards, Customer 360, Salesperson 360, Company CRM, teams, attribution |
| Sales | `sale_management` | Sales boards, Product 360, Salesperson 360, Company Sales |
| Invoicing / Accounting | `account` | Invoice Customers, Vendor Bills, Company Invoice, Customer 360 AR |
| Inventory | `stock` | Stock / Warehouse / Product 360 / Category 360 |
| Purchase | `purchase` | Vendor bills story (optional but recommended with vendors) |
| Website eCommerce | `website_sale` | Website Customers/Products, Website 360, Product 360 website slice |
| Point of Sale | `point_of_sale` | POS Customers/Products/Sessions, POS Product 360, Product 360 POS slice |

```python
"depends": [
    "crm",
    "sale_management",
    "account",
    "stock",
    "purchase",
    "website_sale",
    "point_of_sale",
],
```

- Exactly **one** `res.company` (logo set)
- Dates spread over **last 120 days** (not only today)
- Prefer empty DB + this module (skip Odoo built-in demo data)

---

## 3. Volume targets (“more than enough”)

These are **minimums**. Exceed them if easy. Keep UI snappy (avoid 10k+ noise rows).

### 3.1 Master data

| Model / role | Minimum | Notes |
|--------------|--------:|-------|
| `res.company` | 1 | Logo, phone, website |
| Sales `res.users` | **8** | Avatars on all; each on a team |
| `crm.team` | **4** | Enterprise, SMB, Retail, Online (example names) |
| Customers (`res.partner`) | **24** | **16+** with logo/image |
| **Hero customers** | **10** | Max activity; listed in README by name |
| Vendors | **6** | For Vendor Bills board |
| `utm.campaign` | **5** | All used on leads + SO |
| `utm.source` | **5** | All used |
| `utm.medium` | **5** | All used |
| `product.category` | **6** | All have sales + stock |
| Products | **30** | **20+** with images; mix storable + service; `sale_ok`; POS-available subset |
| `stock.warehouse` | **2** | Both active with moves + quants |
| Extra stock locations | **6+** | For Warehouse 360 location scopes |
| `website` | **2** | Both with shop orders (Website 360 needs multi-site story) |
| `pos.config` | **2** | |
| Closed `pos.session` | **10** | Spread across configs; all with orders |

### 3.2 Transactions

| Domain | Minimum | Rules |
|--------|--------:|-------|
| CRM opportunities | **100** | ~30% won, ~20% lost, rest open; **10+** fat open deals on heroes |
| CRM activities | **40+** | On heroes / salespeople |
| Sale orders | **120** | **≥80** confirmed (`sale`/`done`); mix draft/sent/cancel |
| SO lines | multi | Every category + top 20 products appear often |
| Posted customer invoices | **80** | Prefer from SO |
| **Open overdue** customer invoices | **15** | Ages 7 / 30 / 60+ days; on **≥8** hero customers |
| Partial payments | **10** | |
| Posted vendor bills | **30** | On all 6 vendors |
| Overdue vendor bills | **8** | |
| Stock quants | most storables | Both warehouses |
| Low-stock products | **6** | Clear “attention” story |
| Stock pickings / moves | **60+** | In / out / internal; link deliveries to SO |
| Website/eCommerce orders | **50** | Split across **both** websites; known customers + guests |
| POS orders | **80** | Across **10** closed sessions; known customers + anonymous |

### 3.3 Density rules (non-negotiable)

1. **Same hero customer** must have: CRM + confirmed SO + invoice + **≥1 overdue invoice** + (ideally) website and/or POS order.  
2. **Same top product** must have: SO lines + on-hand stock + (ideally) website sale + POS sale.  
3. **Every salesperson (8)** has CRM **and** Sales volume (not CRM-only or Sales-only).  
4. **Every team (4)** has CRM **and** Sales volume.  
5. **Every UTM campaign/source/medium** appears on multiple leads **and** multiple SOs.  
6. **Every product category** has SO lines **and** stock on member products.  
7. **Both warehouses** have receipts, deliveries, and internal transfers.  
8. **Both websites** have orders (do not leave second site empty).  
9. **Every closed POS session** has multiple order lines.  
10. History covers **≥90 days** so charts are not flat.

---

## 4. Full dashboard coverage matrix

Developer does not install these modules. This matrix is the **acceptance map**: your standard data must satisfy the “Needs” column for **every** row.

### 4.1 All 360 hubs (priority — must be dense)

| Later dashboard | Host | Needs (standard data) | Pass when |
|-----------------|------|------------------------|-----------|
| **Customer 360** | `res.partner` | Per hero: CRM opps + SO + invoices + overdue; ideally website/POS orders | ≥10 partners rich on CRM+Sales+AR; ≥8 with overdue |
| **Salesperson 360** | `res.users` | Per user: CRM opps + SO | All **8** users have both CRM and Sales |
| **Product 360** | `product.product` | Per top product: SO lines + stock; ideally POS + website | ≥20 products with sales+stock; ≥10 also POS and/or website |
| **Product Category 360** | `product.category` | Per category: SO lines + stock on children | All **6** categories have sales **and** stock |
| **Company 360** | `res.company` | Company-wide CRM + SO + invoices | Single company has large volume in all three |
| **Warehouse 360** | `stock.warehouse` | Moves + quants + location activity | Both WH non-empty; location moves visible |
| **Website 360** | `website` | Orders per website | **Both** websites have ≥20 orders each |
| **POS Product 360** | `product.product` | POS lines (+ sales/stock shares) | ≥15 products with POS sales; same SKUs also in SO/stock |

### 4.2 Daily boards — CRM / Sales / Accounting

| Later dashboard | Host | Needs |
|-----------------|------|-------|
| CRM Customers | `res.partner` | Opps on ≥20 customers |
| CRM Salespersons | `res.users` | Opps on all 8 users |
| CRM Attribution (Campaign / Medium / Source) | `utm.*` | Opps tagged for **every** campaign, medium, source |
| CRM Sales Team (in `sales_team_dashboard`) | `crm.team` | Opps on all 4 teams |
| Sales Customers | `res.partner` | Confirmed SO on ≥20 customers |
| Sales Salespersons | `res.users` | SO on all 8 users |
| Sales Products | `product.product` | SO lines on ≥25 products |
| Sales Categories | `product.category` | SO lines in all 6 categories |
| Sales Attribution (Campaign / Medium / Source) | `utm.*` | SO tagged for every UTM record |
| Sales Team | `crm.team` | SO on all 4 teams |
| Invoice Customers | `res.partner` | Posted invoices on ≥20 customers; overdue on ≥8 |
| Vendor Bills | `res.partner` (vendor) | Bills on all 6 vendors; overdue on ≥3 |
| Company CRM / Sales / Invoice (daily company boards) | `res.company` | Same as Company 360 sources |

### 4.3 Daily boards — Stock / Warehouse

| Later dashboard | Host | Needs |
|-----------------|------|-------|
| Stock Products | `product.product` | Quants / moves on most storables |
| Stock Categories | `product.category` | Stock under all 6 categories |
| Warehouse | `stock.warehouse` | Activity on both warehouses |

### 4.4 Daily boards — Website / POS

| Later dashboard | Host | Needs |
|-----------------|------|-------|
| Website Sales Customers | `res.partner` | Website orders on ≥12 known customers |
| Website Sales Products | `product.product` | Website lines on ≥15 products |
| POS Sales Customers | `res.partner` | POS orders on ≥12 known customers |
| POS Sales Products | `product.product` | POS lines on ≥15 products |
| POS Sessions | `pos.session` | **10** closed sessions with lines each |

### 4.5 Engine / Studio

| Later item | Needs from you |
|------------|----------------|
| `dashboard_engine` / Studio media | **No special data** — rich business data above is enough. Product team handles Studio UI. |

---

## 5. Suggested module layout

```
apps_store_demo_data/
  __manifest__.py          # standard depends only (§2)
  README.md                # install + hero names + §7 checklist
  data/ or hooks/
    00_company
    10_users_teams
    20_partners            # 24 customers + 6 vendors + images
    30_utm                 # 5×5×5 used everywhere
    40_products            # 6 cats, 30 products, images
    50_crm                 # 100 opps
    60_sale                # 120 orders
    70_account             # 80 invoices + 15 overdue + 30 bills
    80_stock               # 2 WH, quants, 60+ moves
    90_website             # 2 websites, 50 orders
    95_pos                 # 2 configs, 10 sessions, 80 orders
  static/img/
```

Prefer **Python post_init** for posting invoices with past due dates, stock quants, POS close, website orders.

---

## 6. Why 360s fail (avoid these)

| Failure | Cause in your data | Fix |
|---------|-------------------|-----|
| Customer 360 thin | Partner has CRM but no SO/invoice | Heroes must have all three (+ overdue) |
| Salesperson 360 half-empty | User has only leads or only SO | Every user: both |
| Product 360 stock missing | Sold products never received in stock | Top sellers always have quants |
| Product 360 channel gaps | No website/POS on same SKU | Top 10 SKUs sold in SO + web + POS |
| Category 360 empty cell | Category used only in sales or only in stock | All 6 cats: both |
| Warehouse 360 one card dead | Second WH unused | Both WH get moves |
| Website 360 one site empty | All orders on default website | Split orders across 2 sites |
| POS Product 360 empty | POS products ≠ sales catalog | Reuse same product records |
| Attribution empty | UTM only on contacts | Set UTM on **leads and SO** |
| Team boards empty | `team_id` blank | Always set team on lead + SO |

---

## 7. QA checklist (standard Odoo only)

Sign off only when **all** boxes pass on a fresh DB.

### Master

```
[ ] 1 company with logo
[ ] 8 sales users with avatars; each in a team
[ ] 4 teams with members
[ ] 24 customers (16+ images); 10 heroes named in README
[ ] 6 vendors
[ ] 5 campaigns + 5 sources + 5 mediums (all used)
[ ] 6 categories; 30 products (20+ images)
[ ] 2 warehouses; 6+ locations in use
[ ] 2 websites with shop
[ ] 2 POS configs; 10 closed sessions
```

### Per-host density (maps to boards)

```
[ ] ≥20 customers have CRM opps
[ ] ≥20 customers have confirmed SO
[ ] ≥20 customers have posted invoices
[ ] ≥8 customers have open overdue invoices
[ ] ≥10 hero customers have CRM + SO + invoice (+ overdue)
[ ] All 8 users have CRM opps AND sale orders
[ ] All 4 teams have CRM opps AND sale orders
[ ] Every UTM campaign/source/medium appears on leads AND sale orders
[ ] ≥25 products have SO lines
[ ] Most storables have on-hand; 6 low-stock
[ ] All 6 categories have SO lines AND stock
[ ] Both warehouses have receipts + deliveries + internal moves
[ ] ≥12 customers have website orders; ≥15 products sold on website
[ ] Both websites have ≥20 orders each
[ ] ≥12 customers have POS orders; ≥15 products sold on POS
[ ] All 10 POS sessions have multiple lines
[ ] ≥10 products appear in SO + stock + (website or POS)
```

### Hand back

```
[ ] README: create DB, install apps, install module, login
[ ] README: 10 hero customer names, 8 user names, 4 team names, 2 WH, 2 websites
[ ] Optional DB dump for product team
[ ] Zero depends on custom dashboard modules
```

---

## 8. Anti-patterns

| Avoid | Why |
|-------|-----|
| Odoo built-in demo only | Wrong shape; empty 360 compose |
| Multi-company | Breaks company / filter story |
| Skipping Website or POS | Website 360 / POS 360 / Product 360 channels stay empty |
| One website / one warehouse only | 360 compare story dies |
| UTM unused on SO/leads | Six attribution boards empty |
| All invoices paid | Customer 360 “attention” dead |
| Different product sets for POS vs Sales | POS Product 360 cannot compose |
| P0-only delivery when full catalog needed | Half the App Store listings look empty |

---

## 9. Effort estimate

| Work | Rough effort |
|------|----------------|
| Master + CRM + Sales + Accounting (dense) | 2.5–3.5 days |
| Stock + warehouses + categories | +1–1.5 days |
| Website (2 sites) + POS (sessions) | +1.5–2.5 days |
| Density QA against §7 | 0.5–1 day |
| **Total (full catalog)** | **~6–8 days** |

---

## 10. Done definition

You are done when:

1. Module/script installs on clean Odoo 19 with **only** standard apps in §2.  
2. Volume §3 and density §3.3 are met.  
3. **Every row** in §4.1–§4.4 is satisfiable from your data (product can verify after installing packs).  
4. §7 checklist is fully checked.  
5. README + optional dump handed to product.

Product team then installs dashboard modules and captures App Store media. If any board is empty, the gap is in **this** dataset — fix data, do not fake KPIs.

---

## Appendix A — Quick count card (print for desk)

| Item | Min |
|------|----:|
| Customers / heroes / vendors | 24 / 10 / 6 |
| Users / teams | 8 / 4 |
| UTM C/S/M | 5 / 5 / 5 |
| Categories / products | 6 / 30 |
| Warehouses / websites / POS configs / sessions | 2 / 2 / 2 / 10 |
| Opps / SO / invoices / overdue / bills | 100 / 120 / 80 / 15 / 30 |
| Website orders / POS orders / stock moves | 50 / 80 / 60+ |
| History window | 120 days |

---

## 11. AI Agent Runbook (execute this)

Use this section as the **implementation spec**. Spec §§1–10 define success criteria; this section defines **how the agent builds and loads** the data.

### 11.1 Environment (human fills before agent runs)

```text
ODOO_BIN=          # e.g. /path/to/odoo-bin  OR  venv/python …/odoo-bin
ODOO_CONF=         # e.g. /path/to/odoo.conf  (addons_path must include a writable custom addons dir)
PYTHON=            # e.g. /path/to/venv/bin/python
DB_NAME=apps_store_demo_std
ADDONS_DIR=        # writable folder on addons_path where apps_store_demo_data will be created
ADMIN_PASSWORD=    # for new DB
```

**Hard rules for the agent**

1. Create module **only** under `ADDONS_DIR/apps_store_demo_data/`.  
2. `__manifest__.py` `depends` = **only** packages listed in §2 (no `dashboard_*`, no gritxi).  
3. Do **not** enable Odoo “Load demonstration data” / `-i base` with demo unless unavoidable; prefer empty DB + this module.  
4. One company only.  
5. Idempotent-ish: safe to reinstall with `-u apps_store_demo_data` after fixing bugs (use xmlids / external ids where possible; `post_init` may guard with a marker).  
6. If a standard API differs on this Odoo build, **inspect local Odoo source** under `addons/` / `odoo/addons/` and adapt — do not invent fake fields.  
7. Stop and report if Accounting chart of accounts is missing (setup wizard not finished) — fix CoA first, then continue.

### 11.2 End-to-end command sequence

Agent must run in this order (adapt paths from §11.1):

```bash
# 1) Scaffold module under ADDONS_DIR (see §11.3)

# 2) Create DB + install standard apps + demo module in one shot
#    (without Odoo demo data flag)
$PYTHON $ODOO_BIN -c $ODOO_CONF -d $DB_NAME \
  -i crm,sale_management,account,stock,purchase,website_sale,point_of_sale,apps_store_demo_data \
  --without-demo=all \
  --stop-after-init

# 3) If post_init failed: fix code, then
$PYTHON $ODOO_BIN -c $ODOO_CONF -d $DB_NAME \
  -u apps_store_demo_data --stop-after-init

# 4) Run density self-check (see §11.6)
$PYTHON $ODOO_BIN shell -c $ODOO_CONF -d $DB_NAME < apps_store_demo_data/scripts/verify_density.py
# or paste verify code into shell
```

If `-i` list fails because some app name differs (CE vs EE), resolve technical names from Apps menu / `ir.module.module` and retry. Common aliases: `sale` vs `sale_management`; keep whatever provides Sale Orders UI.

**Accounting note:** On first install, ensure company has a chart of accounts (module `account` + localization, e.g. `l10n_generic_coa` or country pack). If invoices cannot post, install an `l10n_*` CoA module first, then re-run demo data.

Suggested extra depend if CoA missing:

```python
# pick one that matches the deployment; generic is fine for demo
"l10n_generic_coa",  # or local country l10n
```

### 11.3 Module scaffold (create these files)

```
apps_store_demo_data/
  __init__.py
  __manifest__.py
  hooks.py                 # post_init_hook entry
  README.md
  models/__init__.py       # empty ok
  scripts/verify_density.py
  static/description/icon.png   # optional
  static/img/                   # placeholders ok (1x1 PNG or generated)
```

**`__manifest__.py` (minimum):**

```python
# -*- coding: utf-8 -*-
{
    "name": "Apps Store Demo Data (Standard)",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "summary": "Dense standard Odoo demo data for dashboard App Store captures",
    "depends": [
        "crm",
        "sale_management",
        "account",
        "stock",
        "purchase",
        "website_sale",
        "point_of_sale",
        # add CoA if needed:
        # "l10n_generic_coa",
    ],
    "data": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
```

**`__init__.py`:**

```python
from .hooks import post_init_hook
```

**Implementation style:** put **all** record creation in `hooks.py` (or `hooks/*.py` imported from there). Prefer ORM in `post_init_hook(env)` over huge XML for dated invoices, stock, POS.

### 11.4 Creation algorithm (strict order)

Implement `post_init_hook(env)` as follows. Use `env` in sudo when needed. Wrap in `env.cr.commit()` only if required by long hook patterns used in that codebase; default Odoo hook commits with the install transaction.

**Step A — Marker**  
If `ir.config_parameter` key `apps_store_demo_data.loaded` == `1` and counts already meet §3, skip (or force reload via param `apps_store_demo_data.force=1`).

**Step B — Company**  
- Get `env.company` (single).  
- Write name, phone, email, website, logo (binary from `static/img/company.png` or tiny PNG bytes).  

**Step C — Users & teams**  
- Create 8 internal users (login `demo.sales1` …), password documented in README (e.g. `demo`), group `sales_team.group_sale_salesman` / CRM user.  
- Set `image_1920` on each.  
- Create 4 `crm.team`; set `member_ids`.  
- Keep lists: `users[]`, `teams[]`.

**Step D — UTM**  
- Create 5 campaign / 5 source / 5 medium with stable xmlids or name keys.  
- Keep round-robin helpers: `utm_for(i) -> dict`.

**Step E — Partners**  
- 24 customers: `customer_rank=1` (or v19 equivalent), names screenshot-friendly.  
- First 10 = heroes.  
- 16+ with `image_1920`.  
- 6 vendors: `supplier_rank=1`.  
- Country/city optional but nice.

**Step F — Products**  
- 6 `product.category`.  
- 30 products: ~22 `type='consu'`/`'product'` storable as allowed in v19, ~8 service.  
- Flags: `sale_ok=True`, `purchase_ok=True` on goods; `available_in_pos=True` on ≥20 goods; website publish on ≥20.  
- Assign category; images on ≥20.  
- List prices / standard_price > 0.

**Step G — Second warehouse**  
- Ensure 2 `stock.warehouse` (create second if only one).  
- Note `lot_stock_id` per WH.

**Step H — CRM (100 opps)**  
For i in 0..99:  
- `type='opportunity'`  
- Rotate partner (heroes overweight), user, team, UTM, stage  
- `expected_revenue` varied; 10+ high value open on heroes  
- `date_deadline` / create dates spread over 120 days (write `create_date` via SQL only if ORM blocks; prefer business date fields)  
- Won/lost/open mix §3.2  
- Create ≥40 `mail.activity` on heroes  

**Step I — Sales (120 SO)**  
For each order:  
- partner, user, team, UTM, `date_order` over 120 days  
- 2–5 lines from product pool (cover all categories)  
- Confirm ≥80 via `action_confirm()`  
- Leave rest draft/sent/cancel  

**Step J — Stock**  
- Set quants on storables in **both** WH (`stock.quant` / inventory adjustment API for this Odoo version).  
- 6 products with very low qty.  
- Validate enough pickings from confirmed SO; create extra internal transfers / receipts to reach **60+** done moves across 120 days.  

**Step K — Accounting**  
- From confirmed SO: create invoices (`_create_invoices` / wizard pattern for this version), `action_post()`.  
- Ensure ≥80 posted customer invoices.  
- Create **15** open overdue: set `invoice_date` and `invoice_date_due` in the past; post; **do not** fully pay.  
- 10 partial payments via `account.payment` register.  
- 30 vendor bills (`move_type='in_invoice'`) on vendors; post; 8 overdue unpaid.  

**Step L — Websites**  
- Ensure **2** `website` records (duplicate/create second).  
- Publish products on both as needed.  
- Create **50** confirmed website/sale orders with `website_id` set — **≥20 per website**.  
- Mix hero partners + public/guest.  

**Step M — POS**  
- 2 `pos.config` linked to stock/WH as required.  
- Open session → create orders (partner optional) → pay → close; repeat until **10** closed sessions and **≥80** orders.  
- Reuse same `product.product` as Sales (critical).  
- Prefer official POS order APIs / models for this Odoo version; if UI-only methods exist, use ORM equivalents found in `point_of_sale` tests in the source tree.

**Step N — Finish**  
- Set `ir.config_parameter` `apps_store_demo_data.loaded = 1`.  
- Write `README.md` with hero names, logins, counts actually created.

### 11.5 Odoo 19 practical tips for the agent

- **Inspect before inventing:** `grep` / read models in local `crm`, `sale`, `account`, `stock`, `website_sale`, `point_of_sale`.  
- **Product types** may be `consu` / `service` / `combo` depending on version — match local selection.  
- **Storable stock:** if `type` no longer has `product`, use `is_storable` / tracking fields as in local code.  
- **UTM on SO:** fields often `campaign_id`, `source_id`, `medium_id` (utm).  
- **Overdue:** unpaid posted `out_invoice` with `invoice_date_due < today` and `payment_state` in (`not_paid`, `partial`).  
- **Images:** tiny valid PNG base64 is enough if no assets.  
- **Performance:** `create` in batches; avoid 1-by-1 chatter floods where possible.  
- **Failures:** log exception, fix, `-u apps_store_demo_data`; do not leave half-posted moves without cleanup notes in README.

### 11.6 Automated density verify (agent must pass)

Create `scripts/verify_density.py` runnable via `odoo shell` that **exits non-zero** on failure. Check at least:

```python
# Pseudocode — adapt imports for shell context (env is available)
from datetime import date
errors = []

def need(cond, msg):
    if not cond:
        errors.append(msg)

users = env["res.users"].search([("share", "=", False), ("login", "like", "demo.sales%")])
need(len(users) >= 8, f"users={len(users)}")
teams = env["crm.team"].search([])
need(len(teams) >= 4, f"teams={len(teams)}")
# … customers, vendors, utm, categories, products, warehouses, websites, sessions …

# Per-user CRM + SO
for u in users:
    need(env["crm.lead"].search_count([("user_id", "=", u.id), ("type", "=", "opportunity")]) > 0, f"no CRM {u.login}")
    need(env["sale.order"].search_count([("user_id", "=", u.id), ("state", "in", ("sale", "done"))]) > 0, f"no SO {u.login}")

# Heroes: CRM + SO + overdue invoice
# Overdue sample:
overdue = env["account.move"].search([
    ("move_type", "=", "out_invoice"),
    ("state", "=", "posted"),
    ("payment_state", "in", ("not_paid", "partial")),
    ("invoice_date_due", "<", date.today()),
])
need(len(overdue) >= 15, f"overdue={len(overdue)}")

# Both websites order counts ≥ 20
# Both WH have stock.move done
# POS closed sessions ≥ 10 with orders
# All categories have SOL + quant
# …

if errors:
    print("FAIL:\n- " + "\n- ".join(errors))
    raise SystemExit(1)
print("PASS density checks")
```

Map every box in §7 to an assert. Agent loops: fix hook → upgrade module → re-verify until PASS.

### 11.7 Agent definition of done

```
[ ] Module apps_store_demo_data exists on ADDONS_DIR
[ ] Fresh DB created with --without-demo=all
[ ] Standard apps from §2 installed
[ ] post_init completed without traceback
[ ] verify_density.py prints PASS
[ ] README lists heroes, users, passwords, actual counts
[ ] No dashboard_* / gritxi depends
```

Hand DB name + module path to product team. Stop.

### 11.8 Copy-paste system prompt for Gemini

```text
You are an Odoo 19 implementer. Read and obey the full file
docs/2026-08-06-app-store-demo-data-and-media-handover.md

Goal: create module apps_store_demo_data and load dense standard demo data
into DB apps_store_demo_std for later App Store dashboard screenshots.

Constraints:
- Standard Odoo modules only (see §2). Never install dashboard or gritxi apps.
- Meet all volume minimums in §3 and density rules §3.3.
- Satisfy coverage matrix §4 via data shape (you will not open those dashboards).
- Follow AI runbook §11 for scaffold, install commands, creation order, verify script.
- Fill env from human values in §11.1 before running commands.
- Inspect local Odoo source when APIs differ; do not invent fields.
- Iterate until scripts/verify_density.py PASSes.

Deliver: module code, README, PASS verify log, DB name.
```

---

## Appendix B — What the AI still cannot invent

| Gap | Who provides |
|-----|----------------|
| Real `ODOO_BIN` / conf / Postgres | Human (§11.1) |
| Company localization / CoA choice | Human (country) or agent picks `l10n_generic_coa` |
| Brand assets (nice logos) | Optional; agent may use placeholders |
| Dashboard modules for final screenshots | Product team after data PASS |
