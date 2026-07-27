# Phase A: Preset Apps Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move CRM Customers, Sales Customers, and CRM Salespersons blueprint seed data out of `dashboard_engine` into thin Apps modules `crm_customer_dashboard`, `sales_customer_dashboard`, and `crm_salesperson_dashboard`, with hard depends, while keeping runtime/engine-only code in `dashboard_engine`.

**Architecture:** `dashboard_engine` stays `depends: [base, web]` and ships no CRM/Sales customer or salesperson presets. New modules each own **one** dashboard preset and depend on `dashboard_engine` + business apps (+ `report_sale_crm` when actions need it). Data XML moves with stable record **names**; a migration reassigns `ir_model_data.module`. **Do not** create V1-style `customer_dashboard` or `salesperson_dashboard` intermediate modules — the engine already owns that shared shell/runtime role.

**Tech Stack:** Odoo 19, XML `noupdate` data, Python migrations, existing `dashboard_engine` tests.

**Spec:** `docs/superpowers/specs/2026-07-27-preset-apps-studio-mvp-design.md`

## Global Constraints

- Work under `custom/addons/gritxi/odoo-dashboards-19.1-v2/`
- Phase A scope = **`crm_customer_dashboard` + `sales_customer_dashboard` + `crm_salesperson_dashboard`**; leave POS/Website seeds in the engine for a later plan
- **One dashboard = one Apps module** (salesperson is never nested inside a customer module)
- **No** V2 `customer_dashboard` or `salesperson_dashboard` shared-shell modules
- Do **not** change runtime slot/graph algorithms in this plan
- Preserve blueprint `key` values (`crm_customers`, `sales_customers`, `crm_salespersons`)
- Prefer keeping external id **names** (`blueprint_crm_customers`, …); reassign `ir_model_data.module`
- Bump `dashboard_engine` version at the end of Phase A; new modules start at `19.0.1.0.1`
- After data moves: upgrade DB `dashboard_engine_v2.ee`, restart :19005, hard-refresh
- **Do not git commit** unless the user explicitly asks (skip Commit steps)

## Resolved open points (from product spec)

1. Module names: **`crm_customer_dashboard`**, **`sales_customer_dashboard`**, **`crm_salesperson_dashboard`** (V1-style; salesperson is its own app).
2. Salesperson blueprint: **`crm_salesperson_dashboard`** (individual module). Later: `sales_salesperson_dashboard`, etc.
3. Xmlids: **reassign `ir_model_data.module`**; external id name part unchanged (update code refs/tests to the new module prefix).
4. Report depends: CRM customer + CRM salesperson → `report_sale_crm` when slot/actions need it; Sales customer → `sale` only unless `report_sale_stock` is added to V2.

## File map

| Path | Responsibility |
|---|---|
| `crm_customer_dashboard/` (new) | CRM **Customers** preset data + thin manifest |
| `sales_customer_dashboard/` (new) | Sales **Customers** preset data + thin manifest |
| `crm_salesperson_dashboard/` (new) | CRM **Salespersons** preset data + thin manifest |
| `dashboard_engine/__manifest__.py` | Remove CRM/Sales customer + CRM salesperson data files; bump version |
| `dashboard_engine/data/seed_blueprints.xml` | Keep POS (+ any non-moved) only |
| `dashboard_engine/data/seed_blueprint_headers.xml` | Keep POS (non-moved) only |
| `dashboard_engine/data/seed_share_links.xml` | Keep POS↔Website links only |
| `dashboard_engine/migrations/19.0.1.0.78/pre-reassign-preset-xmlids.py` | Reassign xmlids to the three new modules |
| `dashboard_engine/tests/test_dashboard_blueprint.py` | Gate/update CRM/Sales/salesperson seed tests |
| `report_sale_crm` | Keep V2 symlink; CRM customer + CRM salesperson packs depend on it |

---

### Task 1: Inventory CRM customer / Sales customer / CRM salesperson xmlids

**Files:**
- Create: `docs/superpowers/plans/2026-07-27-preset-xmlid-inventory.md`

**Interfaces:**
- Produces: complete `ir.model.data` **name** tuples for the three Phase A modules

- [ ] **Step 1: Generate CRM Customers name list**

From `dashboard_engine/data/`, collect every `id="..."` owned by CRM **Customers** (not salesperson):

- All of `seed_crm_parity.xml`, `seed_conditions.xml` (CRM-only today)
- CRM customer records inside `seed_blueprints.xml` / `seed_blueprint_headers.xml` (`blueprint_crm_customers`, `scope_crm_*`, `slot_crm_*` except `*_sp_*` / salesperson, `header_crm_*`)

```python
CRM_CUSTOMER_XMLID_NAMES = (
    "blueprint_crm_customers",
    "scope_crm_mine",
    # … complete list — no salesperson ids …
)
```

- [ ] **Step 2: Generate Sales Customers name list**

```python
SALES_CUSTOMER_XMLID_NAMES = (
    "blueprint_sales_customers",
    # … complete list …
)
```

- [ ] **Step 3: Generate CRM Salespersons name list**

All of `seed_crm_salesperson.xml` (`blueprint_crm_salespersons`, `scope_crm_sp_*`, `slot_crm_sp_*`, …):

```python
CRM_SALESPERSON_XMLID_NAMES = (
    "blueprint_crm_salespersons",
    # … complete list …
)
```

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 2: Scaffold `crm_customer_dashboard` (Customers only)

**Files:**
- Create: `crm_customer_dashboard/__init__.py`
- Create: `crm_customer_dashboard/__manifest__.py`
- Create: `crm_customer_dashboard/data/` (empty until Task 3)

**Interfaces:**
- Consumes: `dashboard_engine` installed
- Produces: installable CRM **Customers** module skeleton (no salesperson data)

- [ ] **Step 1: Create `__init__.py`**

```python
# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
```

- [ ] **Step 2: Create `__manifest__.py`**

```python
# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "CRM Customers Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "CRM Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "description": """
CRM Customers Dashboard
=======================

Ships the CRM Customers blueprint preset for ``dashboard_engine``.
Requires CRM. Salesperson dashboards ship in ``crm_salesperson_dashboard``.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "report_sale_crm",
    ],
    "data": [
        # filled in Task 3
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
}
```

Confirm `report_sale_crm` is on the addons path (V2 symlink to V1). Prefer keeping this depend when CRM New Lead/Opp actions need it.

- [ ] **Step 3: Verify module appears as uninstalled with the expected depends** (odoo shell / module list).

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 3: Move CRM Customers seed data into `crm_customer_dashboard`

**Files:**
- Create: `crm_customer_dashboard/data/seed_blueprints.xml` (CRM **Customers** slice only)
- Create: `crm_customer_dashboard/data/seed_blueprint_headers.xml` (`header_crm_*`)
- Move: `seed_crm_parity.xml`, `seed_conditions.xml` from engine → CRM customer module
- Modify: `crm_customer_dashboard/__manifest__.py` `data` list
- Modify: engine mixed files (remove CRM **customer** records only)

**Interfaces:**
- Consumes: Task 1 `CRM_CUSTOMER_XMLID_NAMES`, Task 2 scaffold
- Produces: CRM Customers data loadable from new module
- **Does not** move `seed_crm_salesperson.xml` (that is Task 4b)

- [ ] **Step 1: Move CRM-customer-only whole files**

```bash
cd /Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2
mkdir -p crm_customer_dashboard/data
mv dashboard_engine/data/seed_crm_parity.xml crm_customer_dashboard/data/
mv dashboard_engine/data/seed_conditions.xml crm_customer_dashboard/data/
# Do NOT move seed_crm_salesperson.xml here
```

- [ ] **Step 2: Split CRM Customers records out of `seed_blueprints.xml`**

Move `blueprint_crm_customers`, its scopes, scope labels, and core CRM **customer** slots into `crm_customer_dashboard/data/seed_blueprints.xml`. Leave POS and Sales records for their owners.

- [ ] **Step 3: Split `header_crm_*` into `crm_customer_dashboard/data/seed_blueprint_headers.xml`**

- [ ] **Step 4: Update CRM Customers manifest `data` list**

```python
    "data": [
        "data/seed_conditions.xml",
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_crm_parity.xml",
        # seed_share_links.xml added in Task 5
    ],
```

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 4: Scaffold + move Sales Customers seed data

**(unchanged intent — Sales Customers only; see existing Task 4 section below, ensure no salesperson files)**

---

### Task 4b: Scaffold + move CRM Salespersons into `crm_salesperson_dashboard`

**Files:**
- Create: `crm_salesperson_dashboard/__init__.py`
- Create: `crm_salesperson_dashboard/__manifest__.py`
- Move: `dashboard_engine/data/seed_crm_salesperson.xml` → `crm_salesperson_dashboard/data/`

**Interfaces:**
- Consumes: Task 1 `CRM_SALESPERSON_XMLID_NAMES`
- Produces: installable CRM Salespersons preset (`res.users` host)
- Does **not** depend on `crm_customer_dashboard` or V1 `salesperson_dashboard`

- [ ] **Step 1: Scaffold manifest**

```python
# -*- coding: utf-8 -*-
{
    "name": "CRM Salespersons Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "CRM Salespersons kanban dashboard preset for Dynamic Dashboard Engine",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "report_sale_crm",
    ],
    "data": [
        "data/seed_crm_salesperson.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
}
```

- [ ] **Step 2: Move the salesperson seed file**

```bash
mkdir -p crm_salesperson_dashboard/data
mv dashboard_engine/data/seed_crm_salesperson.xml crm_salesperson_dashboard/data/
```

Fix any `ref('dashboard_engine.…')` inside that file to same-module refs.

- [ ] **Step 3: Verify module lists and installs independently of `crm_customer_dashboard`.**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 4: Scaffold + move Sales seed data

**Files:**
- Create: `sales_customer_dashboard/__init__.py`
- Create: `sales_customer_dashboard/__manifest__.py`
- Create: `sales_customer_dashboard/data/` (moved/split Sales XML)

**Interfaces:**
- Consumes: Task 1 `SALES_XMLID_NAMES`
- Produces: installable Sales preset module

- [ ] **Step 1: Scaffold manifest**

```python
# -*- coding: utf-8 -*-
{
    "name": "Sales Customers Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales",
    "summary": "Sales Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "sale",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_sales_parity.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
}
```

Do **not** hard-depend on `report_sale_stock` unless/until that module exists on the V2 addons path (V2 currently lacks it). Keep stock/account slots’ soft `module_depends` inside the XML.

- [ ] **Step 2: Move/split Sales XML**

- Move `seed_sales_parity.xml` entirely.
- Split Sales blueprint/scopes/slots from engine `seed_blueprints.xml`.
- Split `header_sales_*` from engine `seed_blueprint_headers.xml`.

- [ ] **Step 3: Commit** — skip unless user asks

---

### Task 5: Share links for CRM ↔ Sales only

**Files:**
- Create: `crm_customer_dashboard/data/seed_share_links.xml`
- Create: `sales_customer_dashboard/data/seed_share_links.xml`
- Modify: `dashboard_engine/data/seed_share_links.xml` (POS/Website only, or remove CRM/Sales refs)

**Interfaces:**
- Consumes: both blueprints exist
- Produces: bi-directional CRM↔Sales share pool; POS/Website links stay engine-side until those packs move

- [ ] **Step 1: CRM module share file**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="blueprint_crm_customers" model="dashboard.blueprint">
        <field name="share_link_ids" eval="[(4, ref('sales_customer_dashboard.blueprint_sales_customers'))]"/>
    </record>
</odoo>
```

Use `(4, …)` add semantics if other links may exist; or `(6, 0, [ref(...)])` only when this module fully owns the list for Phase A. Prefer `(6, 0, [ref('sales_customer_dashboard.blueprint_sales_customers')])` for CRM↔Sales-only Phase A, and let a later POS/Website pack extend via migration/hook.

- [ ] **Step 2: Sales module share file** (mirror ref to CRM).

- [ ] **Step 3: Trim engine `seed_share_links.xml`** to POS↔Website only (refs among remaining engine presets). Remove CRM/Sales records from it.

- [ ] **Step 4: Append share files to both manifests `data` lists** (after blueprints exist).

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 6: Strip CRM/Sales from engine manifest + trim mixed files

**Files:**
- Modify: `dashboard_engine/__manifest__.py`
- Modify: `dashboard_engine/data/seed_blueprints.xml` (POS-only remaining customer presets)
- Modify: `dashboard_engine/data/seed_blueprint_headers.xml`
- Modify: `dashboard_engine/data/seed_share_links.xml` (already trimmed in Task 5)
- Delete or leave absent: moved CRM files (already moved)

- [ ] **Step 1: Remove from engine `data` list**

Remove these entries from `dashboard_engine/__manifest__.py`:

```python
"data/seed_conditions.xml",          # moved → crm_customer_dashboard
"data/seed_crm_parity.xml",          # moved → crm_customer_dashboard
"data/seed_sales_parity.xml",        # moved → sales_customer_dashboard
"data/seed_crm_salesperson.xml",     # moved → crm_salesperson_dashboard
```

Keep for now:

```python
"data/seed_blueprints.xml",          # POS (+ trimmed)
"data/seed_blueprint_headers.xml",   # POS (+ trimmed)
"data/seed_pos_parity.xml",
"data/seed_website_parity.xml",
"data/seed_share_links.xml",         # POS↔Website
"data/seed_blueprint_warehouse.xml",
```

- [ ] **Step 2: Ensure mixed XML files no longer contain CRM/Sales records**

If a CRM/Sales record remains in engine XML after the split, delete it from the engine file (source of truth is the new module).

- [ ] **Step 3: Commit** — skip unless user asks

---

### Task 7: Migration — reassign `ir_model_data.module`

**Files:**
- Create: `dashboard_engine/migrations/19.0.1.0.78/pre-reassign-preset-xmlids.py`

**Interfaces:**
- Consumes: Task 1 `CRM_XMLID_NAMES`, `SALES_XMLID_NAMES`
- Produces: existing DB rows owned by new modules before/while they install

- [ ] **Step 1: Write pre-migration**

```python
# -*- coding: utf-8 -*-
"""Reassign CRM/Sales preset xmlids from dashboard_engine to preset apps."""
import logging

_logger = logging.getLogger(__name__)

# Paste complete tuples from the inventory doc (Task 1).
CRM_CUSTOMER_XMLID_NAMES = (
    "blueprint_crm_customers",
    # …
)
SALES_CUSTOMER_XMLID_NAMES = (
    "blueprint_sales_customers",
    # …
)
CRM_SALESPERSON_XMLID_NAMES = (
    "blueprint_crm_salespersons",
    # …
)


def _reassign(cr, names, new_module):
    if not names:
        return
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = %s
         WHERE module = 'dashboard_engine'
           AND name = ANY(%s)
        """,
        (new_module, list(names)),
    )
    _logger.info(
        "reassign-preset-xmlids: moved %s rows to %s",
        cr.rowcount,
        new_module,
    )


def migrate(cr, version):
    _reassign(cr, CRM_CUSTOMER_XMLID_NAMES, "crm_customer_dashboard")
    _reassign(cr, SALES_CUSTOMER_XMLID_NAMES, "sales_customer_dashboard")
    _reassign(cr, CRM_SALESPERSON_XMLID_NAMES, "crm_salesperson_dashboard")
```

- [ ] **Step 2: Bump engine version in manifest to `19.0.1.0.78`** so this migration runs (if Task 5 of this plan already bumped differently, use the next unused version and rename the migrations folder to match).

- [ ] **Step 3: Commit** — skip unless user asks

---

### Task 8: Update tests + post_init awareness

**Files:**
- Modify: `dashboard_engine/tests/test_dashboard_blueprint.py`
- Modify: `dashboard_engine/__init__.py` only if soft-host hooks create Sales product dashboards that should move later (leave warehouse/product hooks for now)

**Interfaces:**
- Consumes: new module xmlids (`crm_customer_dashboard.blueprint_crm_customers`, …)

- [ ] **Step 1: Update xmlid refs in CRM/Sales tests**

Replace:

```python
env.ref("dashboard_engine.blueprint_crm_customers")
```

with:

```python
env.ref("crm_customer_dashboard.blueprint_crm_customers")
```

(and the same for every moved CRM/Sales xmlid used in tests).

- [ ] **Step 2: Gate CRM/Sales seed tests**

At the start of tests that require CRM pack:

```python
crm_bp = self.env.ref(
    "crm_customer_dashboard.blueprint_crm_customers",
    raise_if_not_found=False,
)
if not crm_bp:
    self.skipTest("crm_customer_dashboard not installed")
```

Or mark test classes with a skip unless modules are installed.

- [ ] **Step 3: Fix generic seed tests**

`test_seeded_blueprints_expose_pickers` / `test_seeded_blueprints_are_healthy` must not assume CRM/Sales rows exist inside the engine. Assert on whatever presets remain (POS/Website) **or** search all blueprints regardless of module.

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 9: Install packs, upgrade engine, verify parity

**Files:**
- Modify: `dashboard_engine/__manifest__.py` version (final Phase A version)

- [ ] **Step 1: Ensure addons path includes V2 root**

Confirm `config/dashboard_engine_v2.conf` addons_path lists  
`.../odoo-dashboards-19.1-v2` (parent of both `dashboard_engine` and new modules).

- [ ] **Step 2: Upgrade engine + install preset modules**

```bash
PIDS=$(lsof -tiTCP:19005 -sTCP:LISTEN); [ -n "$PIDS" ] && kill -9 $PIDS
cd /Users/dharmesh/Applications/odoo/19.0
PY=venv/python3.12.11/bin/python
CONF=config/dashboard_engine_v2.conf
$PY server/odoo-bin -c "$CONF" -d dashboard_engine_v2.ee \
  -u dashboard_engine \
  -i crm_customer_dashboard,sales_customer_dashboard,crm_salesperson_dashboard \
  --dev=xml,assets --log-level=warn
```

- [ ] **Step 3: Shell parity checks**

```python
# odoo shell --no-http
crm = env.ref('crm_customer_dashboard.blueprint_crm_customers')
sale = env.ref('sales_customer_dashboard.blueprint_sales_customers')
sp = env.ref('crm_salesperson_dashboard.blueprint_crm_salespersons')
assert crm.key == 'crm_customers' and crm.state == 'published'
assert sale.key == 'sales_customers'
assert sp.key == 'crm_salespersons'
assert sale in crm.share_link_ids and crm in sale.share_link_ids
assert env['ir.module.module'].search([('name','=','dashboard_engine')]).latest_version >= '19.0.1.0.78'
print('parity ok', crm.primary_button_label, crm.primary_label_alt, sp.name)
```

Expected: `parity ok Pipeline Analysis Leads Analysis CRM Salespersons` (or current labels).

- [ ] **Step 4: HTTP 200** on `http://127.0.0.1:19005/web/login`

- [ ] **Step 5: Commit** — skip unless user asks

---

## Spec coverage (Phase A only)

| Spec item | Task |
|---|---|
| Engine without CRM/Sales presets | 6, 9 |
| `crm_customer_dashboard` data + depends | 2, 3 |
| `sales_customer_dashboard` data + depends | 4 |
| `crm_salesperson_dashboard` data + depends | 4b |
| No V2 `customer_dashboard` / `salesperson_dashboard` shells | Global constraint |
| Share Links CRM↔Sales customers | 5 |
| Xmlid reassignment migration | 7 |
| Tests updated | 8 |
| POS/Website remain in engine | Global + Task 6 |
| Studio MVP | **Deferred to Phase B plan** |

## Spec coverage note

Phase B (Studio UI) is intentionally **not** in this plan. After Phase A ships, write `docs/superpowers/plans/2026-07-27-dashboard-studio-mvp.md`.
