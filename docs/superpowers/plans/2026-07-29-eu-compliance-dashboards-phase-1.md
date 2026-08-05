# EU Compliance Dashboards — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship six `dashboard_engine` preset apps (Policy Admin → Hub → Rest → Breaks → Worktime → Protected) that show more than action-599, with country/company policy strip, Phase-1 must-have widgets, and a redirect from the classic Compliance Dashboard form.

**Architecture:** Thin Apps modules under `odoo-dashboards-19.1-v2/` (one dashboard = one module), same pattern as `crm_customer_dashboard`. Shared policy/health helpers live in one small common module so Hub and domain boards share one pack snapshot API. Host/graph data binds primarily to `hr.attendance.violation` (and company settings for Admin). Classic `hr_attendance_dashboard_core` form stays installable but its menu/server action redirects to the Hub blueprint when the Hub module is installed.

**Tech Stack:** Odoo 19, `dashboard_engine` blueprints/slots/scopes, `hr_attendance_violation_core`, EU rule modules under `hr-attendance-compliance-v2/odoo-eu-apps/`, XML `noupdate` seeds, Python tests.

**Spec:** `docs/superpowers/specs/2026-07-29-eu-compliance-dashboards-gap-map-design.md`

## Global Constraints

- Work under `custom/addons/gritxi/odoo-dashboards-19.1-v2/` for preset apps; touch `hr-attendance-compliance-v2` only for redirect + any tiny helper hooks the presets need
- Phase 1 scope = **exactly 6** dashboards: **A, H, R, B, W, P** (build order A → H → R → B → W → P)
- **One dashboard = one Apps module**; no mega module that owns all six presets
- Layout = `dashboard_engine` blueprints (KPI / graph / list slots), **not** a new `view_mode=form` mega-sheet
- Module not installed → hide tile / show “not installed”; never fake zero
- Multi-company: all domains respect `company_id`; Admin matrix iterates companies the user can read
- Pack `requires_verify` / counsel flags: dashboards may display and deep-link; **never** mass-clear verify from a dashboard action
- DE-only tiles (MiLoG, BUrlG, ArbMedVV, Betriebsrat, ArbZG reports) are **optional Hub shortcuts** when modules present — not Phase-1 boards
- Punctuality full board = Phase 2; Hub may show a thin late KPI only
- After UI/data changes on dashboard presets: upgrade relevant DB, restart engine port if used (`:19005` for engine-only; staging compliance often `:19010`), hard-refresh
- **Do not git commit** unless the user explicitly asks (skip Commit steps)

## Resolved open points (from spec)

1. Preset technical names: `attendance_compliance_policy_admin`, `attendance_compliance_hub`, `attendance_rest_dashboard`, `attendance_breaks_dashboard`, `attendance_worktime_dashboard`, `attendance_protected_workers_dashboard`
2. Shared helper module: `attendance_compliance_dashboard_common` (policy strip + health snapshot RPC; no blueprint of its own)
3. Primary host for ops boards: `hr.attendance.violation` (open findings); Admin also reads `res.company` pack fields
4. Classic action-599: redirect to Hub when Hub installed; optional “Classic snapshot” later (not Phase 1)

## File map

| Path | Responsibility |
|------|----------------|
| `attendance_compliance_dashboard_common/` | Policy strip + settings-health JSON API; shared constants (domain codes) |
| `attendance_compliance_policy_admin/` | Blueprint **A** — matrix + health + pack diff |
| `attendance_compliance_hub/` | Blueprint **H** — Hub KPIs, action queue, policy strip, why/channel, trends |
| `attendance_rest_dashboard/` | Blueprint **R** — rest findings, blocks, earliest allow, comp, derogation, youth floor |
| `attendance_breaks_dashboard/` | Blueprint **B** — quota debt, interrupt, countdown |
| `attendance_worktime_dashboard/` | Blueprint **W** — caps, avg, headroom, forecast |
| `attendance_protected_workers_dashboard/` | Blueprint **P** — night / youth / holiday + next ban window |
| `hr_attendance_dashboard_core` (compliance-v2) | Redirect `action_open_dashboard` → Hub when installed |
| Each preset: `data/seed_blueprints.xml`, `seed_blueprint_headers.xml`, `seed_conditions.xml` (as needed), `__manifest__.py` | Same thin pattern as `crm_customer_dashboard` |
| Tests under each preset + common | Install smoke, company isolation, hide-when-missing-module |

## Blueprint keys (stable)

| Code | Module | `dashboard.blueprint` `key` |
|------|--------|-----------------------------|
| A | `attendance_compliance_policy_admin` | `attendance_compliance_policy` |
| H | `attendance_compliance_hub` | `attendance_compliance_hub` |
| R | `attendance_rest_dashboard` | `attendance_rest` |
| B | `attendance_breaks_dashboard` | `attendance_breaks` |
| W | `attendance_worktime_dashboard` | `attendance_worktime` |
| P | `attendance_protected_workers_dashboard` | `attendance_protected_workers` |

---

### Task 1: Shared common module — policy strip + health API

**Files:**
- Create: `attendance_compliance_dashboard_common/__init__.py`
- Create: `attendance_compliance_dashboard_common/__manifest__.py`
- Create: `attendance_compliance_dashboard_common/models/__init__.py`
- Create: `attendance_compliance_dashboard_common/models/compliance_dashboard_api.py`
- Create: `attendance_compliance_dashboard_common/security/ir.model.access.csv` (if transient/helper model needs ACL)
- Create: `attendance_compliance_dashboard_common/tests/test_policy_snapshot.py`

**Interfaces:**
- Consumes: `res.company` rest/break/worktime pack fields when present; `hr.attendance.violation` counts when violation module present
- Produces:
  - `env['attendance.compliance.dashboard.api'].get_policy_strip(company)` → `dict`
  - `get_settings_health(company)` → `list[dict]`
  - `get_pack_matrix(companies)` → `list[dict]` (Admin)

- [ ] **Step 1: Write failing test for policy strip shape**

```python
# attendance_compliance_dashboard_common/tests/test_policy_snapshot.py
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestPolicySnapshot(TransactionCase):
    def test_get_policy_strip_keys(self):
        Api = self.env["attendance.compliance.dashboard.api"]
        strip = Api.get_policy_strip(self.env.company)
        for key in (
            "company_name", "country_code", "rest_pack_name", "rest_hours_label",
            "enable_label", "counsel_state", "modified_state", "open_risk_count",
        ):
            self.assertIn(key, strip)
```

- [ ] **Step 2: Run test — expect FAIL (model missing)**

Run (from Odoo root, DB that has `dashboard_engine` + attendance addons on path):

```bash
venv/python3.12.11/bin/python server/odoo-bin -c <compliance-or-engine-conf> -d <db> \
  --test-enable --stop-after-init --http-port=0 --no-http \
  -i attendance_compliance_dashboard_common \
  --test-tags=/attendance_compliance_dashboard_common
```

Expected: FAIL — module/model not found or import error.

- [ ] **Step 3: Implement minimal common module**

`__manifest__.py` depends: `dashboard_engine`, `hr_attendance_core` (soft-optional fields via `hasattr` / `_fields` checks for rest/breaks/worktime/violation).

```python
# models/compliance_dashboard_api.py
from odoo import api, models

class AttendanceComplianceDashboardApi(models.AbstractModel):
    _name = "attendance.compliance.dashboard.api"
    _description = "Compliance dashboard shared snapshots"

    @api.model
    def get_policy_strip(self, company):
        company = company or self.env.company
        # Read pack/enable fields only if present on res.company
        # Return dict with stable keys from Step 1
        ...

    @api.model
    def get_settings_health(self, company):
        ...

    @api.model
    def get_pack_matrix(self, companies=None):
        companies = companies or self.env["res.company"].search([])
        return [self.get_policy_strip(c) for c in companies]
```

Graceful: missing `rest_policy_pack_id` → empty strings / `not_installed` markers — never raise.

- [ ] **Step 4: Re-run tests — expect PASS**

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 2: Policy Admin preset (A)

**Files:**
- Create: `attendance_compliance_policy_admin/` (manifest, seeds, hooks mirroring `crm_customer_dashboard`)
- Depends: `attendance_compliance_dashboard_common`, `hr_attendance_core`, and soft depends documented for rest/breaks/worktime packs

**Interfaces:**
- Consumes: `get_pack_matrix`, `get_settings_health`
- Produces: published blueprint `key=attendance_compliance_policy`, menu under Attendances → Management (or Configuration)

- [ ] **Step 1: Scaffold module + failing install smoke test**

```python
def test_blueprint_seeded(self):
    bp = self.env["dashboard.blueprint"].search([("key", "=", "attendance_compliance_policy")], limit=1)
    self.assertTrue(bp)
    self.assertEqual(bp.state, "published")
```

- [ ] **Step 2: Seed blueprint**

Host: `res.company` (admin matrix is company-centric) **or** `hr.attendance.violation` with company graph — prefer **`res.company`** for Admin so matrix rows = companies.

Required slots/KPIs (from spec):
- Pack matrix (primary list / custom slot fed by `get_pack_matrix`)
- Settings health cards
- Company vs pack default side-by-side + last apply user/date (must-have widget)
- Missing violation catalogue count when violation module present
- Deep links: Rest Policy Packs, Break Policy Packs, Suite Settings

Menu: `Attendance Compliance · Policy` · parent `hr_attendance.menu_hr_attendance_settings` or Management — pick **Configuration** for Admin ACL (`group_hr_attendance_manager`).

- [ ] **Step 3: Install/upgrade + test PASS**

- [ ] **Step 4: Manual UI check** — multi-company DB: DE vs ES rows differ on daily hours (11 vs 12)

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 3: Compliance Hub preset (H)

**Files:**
- Create: `attendance_compliance_hub/`
- Depends: `attendance_compliance_dashboard_common`, `hr_attendance_violation_core` (hard for meaningful Hub; if violation missing, Hub still loads with empty KPIs)

**Interfaces:**
- Consumes: policy strip API; violation open/critical counts; optional suite_ops / deployment readiness fields if modules present (same pattern as `hr_attendance_dashboard_core`)
- Produces: blueprint `key=attendance_compliance_hub`; share-link targets to R/B/W/P blueprints when those modules installed

- [ ] **Step 1: Failing test — Hub blueprint + strip keys available to payload**

- [ ] **Step 2: Seed Hub blueprint**

Host: `hr.attendance.violation`  
Graph: open violations by type or week  
KPIs (599 parity + more):
- Open / Critical violations
- Pending approvals / pending requests (when modules present)
- Domain rollups: rest / breaks / worktime / protected (domain on violation type codes — document code list in common)
- Thin punctuality late count (optional, if punctuality types exist)
- Deployment / go-live badges when deployment/suite_ops present

Must-have widgets:
- Policy strip (header slot / custom widget calling `get_policy_strip`)
- Action queue list with **why** (rule + pack hours) and **channel** chip
- Week trend graph

Shortcuts: open violations, settings, Policy Admin, drill to R/B/W/P menus

- [ ] **Step 3: Tests PASS + UI on :19010 / engine DB**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 4: Redirect classic action-599 → Hub

**Files:**
- Modify: `hr-attendance-compliance-v2/odoo-attendance-core/hr_attendance_dashboard_core/models/compliance_dashboard.py` (`action_open_dashboard`)
- Modify: `__manifest__.py` optional soft depend note; prefer runtime check for Hub module

**Interfaces:**
- Consumes: Hub blueprint `key=attendance_compliance_hub` published action / generated menu
- Produces: same menu “Compliance Dashboard” opens Hub kanban/action instead of form snapshot

- [ ] **Step 1: Failing test**

```python
def test_open_dashboard_prefers_hub_when_installed(self):
    # skipUnless Hub module installed
    action = self.env["hr.attendance.compliance.dashboard"].action_open_dashboard()
    self.assertNotEqual(action.get("res_model"), "hr.attendance.compliance.dashboard")
    # or assert xmlid / tag points at Hub blueprint action
```

- [ ] **Step 2: Implement redirect**

```python
def action_open_dashboard(self):
    if self.env["ir.module.module"]._get_module_data("attendance_compliance_hub") == "installed":
        bp = self.env["dashboard.blueprint"].sudo().search(
            [("key", "=", "attendance_compliance_hub"), ("state", "=", "published")], limit=1
        )
        if bp and bp.generated_action_id:
            return bp.generated_action_id.read()[0]
    # legacy form snapshot path (existing code)
    ...
```

Use the project’s real API for “is module installed” and “open blueprint” (match how other presets open).

- [ ] **Step 3: Test PASS; menu on :19010 opens Hub**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 5: Rest dashboard (R)

**Files:**
- Create: `attendance_rest_dashboard/`
- Depends: `dashboard_engine`, `hr_attendance_rest_period_eu`, `hr_attendance_violation_core`, `attendance_compliance_dashboard_common`

**Interfaces:**
- Consumes: rest violation types; company rest pack fields; compensatory records if model exists
- Produces: blueprint `key=attendance_rest`

- [ ] **Step 1: Failing seed/install test**

- [ ] **Step 2: Seed Rest blueprint + slots**

KPIs / lists from spec:
- Short daily rest, Strict blocked CI, weekly rest gaps, comp overdue
- Earliest allowed time on blocked rows
- Same-spell skip count (if logged; else document “N/A until engine exposes counter”)
- Compensatory due → overdue queue + deep link to Mark fulfilled (form/action — dashboard does not reimplement close-out)
- Must-have: derogation usage (CH/NL), youth floor applied vs not
- Policy strip (shared)

Scopes: open only; Strict only; this week

- [ ] **Step 3: Tests + UI with DE and ES company (12h vs 11h copy from strip)**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 6: Breaks dashboard (B)

**Files:**
- Create: `attendance_breaks_dashboard/`
- Depends: `hr_attendance_breaks_eu`, `hr_attendance_violation_core`, `attendance_compliance_dashboard_common`

- [ ] **Step 1: Failing test**

- [ ] **Step 2: Seed Breaks blueprint**

KPIs: short break, >6h interrupt, debt minutes, Flexible OK rate (if computable)  
Must-have: continuity interrupt **countdown** for employees still checked in (compute from open attendance + company continuity max hours)  
Pack/sector context on strip  
Deep link to attendances / violations

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 7: Worktime dashboard (W)

**Files:**
- Create: `attendance_worktime_dashboard/`
- Depends: `hr_attendance_worktime_limits_eu`, `hr_attendance_violation_core`, `attendance_compliance_dashboard_common`

- [ ] **Step 1: Failing test**

- [ ] **Step 2: Seed Worktime blueprint**

KPIs: over daily, over weekly, avg breach, near limit (absorbs 599 §3/near tiles with **EU** labels)  
Headroom list (used/cap)  
Must-have: **forecast** breach if planned/calendar hours continue (document formula: remaining week headroom − scheduled hours on calendar; if calendar missing, forecast = “insufficient schedule data”)  
Graph: headroom mix under/near/over

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 8: Protected workers dashboard (P)

**Files:**
- Create: `attendance_protected_workers_dashboard/`
- Depends: soft/hard mix — prefer hard depends on modules that exist in target DB; use `module_depends` on slots for night/youth/holidays so partial installs work

- [ ] **Step 1: Failing test**

- [ ] **Step 2: Seed Protected blueprint**

KPIs: night ban breaches, youth workers / youth violations, overdue holiday rest (from 599 `overdue_holiday_rest_count`)  
Must-have: **next banned window** per at-risk employee  
Hide sections when module not installed

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 9: Hub share-links + cross-preset drill

**Files:**
- Modify: Hub (+ optional peers) `data/seed_share_links.xml` or post_init (avoid circular install — follow CRM↔Sales post_init pattern)

- [ ] **Step 1: When R/B/W/P installed, Hub KPI cards deep-link to those blueprints**

- [ ] **Step 2: Test: uninstall Rest module → Hub rest KPI shows not-installed / hidden, Hub still opens**

- [ ] **Step 3: Commit** — skip unless user asks

---

### Task 10: Phase 1 acceptance pass

**Files:** none (QA script / checklist)

- [ ] **Step 1: Run automated tests for all six presets + common + redirect**

- [ ] **Step 2: Manual checklist (from spec)**

- [ ] action-599 menu opens Hub (not form) when Hub installed  
- [ ] Policy strip changes DE → ES (12h)  
- [ ] Admin matrix shows Enable / counsel / drift  
- [ ] Rest shows earliest allow + comp queue  
- [ ] Breaks countdown visible for open spell near 6h  
- [ ] Worktime headroom + forecast row  
- [ ] Protected next ban window  
- [ ] Must-have widgets present or explicitly ticketed with reason  
- [ ] No mass counsel-verify clear from UI  

- [ ] **Step 3: Mark gap-map Status: Phase 1 plan ready / in progress**

- [ ] **Step 4: Commit** — skip unless user asks

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| 6 dashboards A/H/R/B/W/P | Tasks 2–3, 5–8 |
| Build order A→H→R→B→W→P | Task order |
| Policy strip + matrix + health | Tasks 1–2 |
| 599 parity on Hub + redirect | Tasks 3–4 |
| Rest / Breaks / Worktime / Protected depth | Tasks 5–8 |
| Phase 1 must-have widgets | Embedded in Tasks 2–3, 5–8 |
| Hide when module missing | Tasks 3, 8–9 |
| No Phase 2 punctuality board | Explicitly out of scope |
| DE companions optional only | Task 3 shortcuts only |

## Out of this plan

- Phase 2 Punctuality + Overtime balance  
- Phase 3 HSE / DE Betriebsrat boards  
- Rebuilding compensatory Mark fulfilled business logic (deep-link only; product gap stays in `rest_period_eu`)  
- Moving CRM/Sales presets (already Phase A elsewhere)
