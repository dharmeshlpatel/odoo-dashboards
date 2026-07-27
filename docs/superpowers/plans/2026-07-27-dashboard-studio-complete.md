# Dashboard Studio Complete — Wave C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Studio MVP into a complete Card Studio: add/remove/reorder all zones, guided slot editors, configuration (scopes + graph), publish — without opening the Advanced form for day-to-day work.

**Architecture:** Extend the existing OWL client action `dashboard_engine.studio` and `dashboard.blueprint` `studio_*` RPCs. Single source of truth remains blueprint/slot/header/scope records. No second layout store. Wave D (live preview) is a follow-up plan after Wave C ships.

**Tech Stack:** Odoo 19, OWL 2, `web.assets_backend`, existing `dashboard_engine` models.

## Global Constraints

- Engine version bump continue `19.0.1.0.x` on each shippable slice
- Card shell fixed (Header · Primary · KPIs · Totals · Shortcuts · Manage · Config)
- No free-form page builder; no blank-dashboard wizard in Wave C
- Studio group gates Customize; Manager implies Studio
- Prefer Composer/Auto; escalate only if OWL/domain UI stalls after one solid attempt
- After UI changes: restart `:19005` with `-u dashboard_engine --dev=xml,assets`, wait for `/web/login` 200
- Docs: update this plan checkboxes; design lives in `docs/superpowers/specs/2026-07-27-dashboard-studio-complete-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | Expand payload fields; `studio_reorder_*`; catalog RPCs; widen write whitelist carefully |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Shell: zones, dirty, publish, load payload |
| `dashboard_engine/static/src/js/studio/studio_zone_panel.js` | Right editor host; add/remove/reorder chrome |
| `dashboard_engine/static/src/js/studio/editors/*.js` | Per-zone editors (kpi, bottom, totals, primary, header, manage, config) |
| `dashboard_engine/static/src/xml/studio/*` | Templates |
| `dashboard_engine/static/src/scss/studio/*` | Layout polish |
| `dashboard_engine/tests/test_dashboard_studio.py` | Expand RPC coverage |
| `__manifest__.py` | Version bump (assets already globbed) |

---

### Task 1: Expand studio payload + reorder RPC

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Modify: `dashboard_engine/tests/test_dashboard_studio.py`

- [x] Extend `_STUDIO_SLOT_FIELDS` / write whitelist for Wave C fields: `icon`, `style`, `value_mode` (if present), `count_field`, `amount_field`, `compute_model`, `relate_field`, `compute_domain`, `action_model`, `action_method`, `module_depends`, `condition_ids` (as id list)
- [x] Add `studio_reorder_slots(section, ordered_ids)` and `studio_reorder_headers(ordered_ids)` writing `sequence`
- [x] Tests: create slot → reorder → unlink; assert sequences and payload

**Verify:** `odoo-bin … --test-tags=/dashboard_engine:TestDashboardStudio` → 0 failed

---

### Task 2: Catalog RPCs for pickers

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`

- [x] `studio_search_actions(term, limit=20)` → id / xmlid / name / model
- [x] `studio_model_fields(model_name, ttypes=None)` → name / string / ttype for host or compute model
- [x] `studio_condition_catalog()` → id / name for `dashboard.condition`
- [x] `studio_header_icons()` → reuse `HEADER_ICONS` (or FA allow-list already used)
- [x] ACL: callable by Studio group (same as other studio methods)

**Verify:** shell smoke on CRM Customers blueprint catalogs return non-empty lists when CRM installed

---

### Task 3: OWL shell — Add / Remove / Reorder UI

**Files:**
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Create: `dashboard_engine/static/src/js/studio/studio_zone_panel.js` (+ xml) if shell grows too large

- [x] Per list zone: **Add**, **Remove** (confirm), **Move up/down** (or drag if cheap)
- [x] Add calls `studio_create_slot(section, {label, name, …defaults})` then select new id
- [x] Remove calls `studio_unlink_slot`
- [x] Reorder calls `studio_reorder_slots`
- [x] Header zone same with header create/unlink/reorder helpers
- [x] Card map reflects counts/labels after refresh

**Verify:** UI on `:19005` — add KPI on CRM Customers, see it in list; remove; reorder

---

### Task 4: KPI + Shortcut guided editors

**Files:**
- Create: `dashboard_engine/static/src/js/studio/editors/kpi_editor.js` (+ xml)
- Create: `dashboard_engine/static/src/js/studio/editors/shortcut_editor.js` (+ xml) or one shared `slot_metrics_editor.js`
- Modify: shell to mount editor by zone

- [x] Fields: label, plural, show_if_zero, icon, style
- [x] Value source: compute_model + relate_field pickers OR host count/amount fields
- [x] Action: searchable xmlid via `studio_search_actions`; optional action_method Char
- [x] Conditions: multi-select from `studio_condition_catalog`
- [x] Save via `studio_write_slot`; toast on validation UserError
- [x] Sensible defaults on create so Publish does not generate a dead slot

**Verify:** new KPI with `res.partner` child count pattern (or CRM opp) → Publish → live card shows count

---

### Task 5: Totals, Primary, Header, Manage editors

**Files:**
- Create/modify editors under `static/src/js/studio/editors/`
- Modify: templates

- [x] Totals: label, amount_field / count_field from host field catalog
- [x] Primary: `studio_write_blueprint` for primary_button_label, primary_action_xmlid, graph_caption
- [x] Header: kind, field_names (multi from catalog), icon from `studio_header_icons`
- [x] Manage: filter by menu section; label + action_xmlid; add/remove per section

**Verify:** change primary label + add one Manage Views item → Publish → visible on live card

---

### Task 6: Configuration panel (scopes + graph)

**Files:**
- Create: `dashboard_engine/static/src/js/studio/editors/config_editor.js` (+ xml)
- Modify: `dashboard_blueprint.py` write whitelist for graph fields used by Studio

- [x] Scopes: toggle `default_on` (existing); optional rename via `studio_write_scope`
- [x] Graph: measure + groupby field + date granularity from `studio_model_fields(graph_model)`
- [x] Persist via `studio_write_blueprint` (extend `_STUDIO_BP_WRITE_FIELDS` for `graph_measure`, `graph_groupby` or unified groupby API already used by form)
- [x] Domains for scopes: “Edit in Advanced” link (action to form view) — no full domain widget required in Wave C

**Verify:** change groupby → Publish → graph context on live card matches

---

### Task 7: Polish + entry + ship Wave C

**Files:**
- Modify: Studio SCSS, toolbar
- Modify: live kanban / blueprint views if adding Customize from runtime
- Modify: `__manifest__.py` version
- Modify: design/plan checkboxes

- [x] Dirty flag; Discard reloads payload; disable Save when clean
- [x] Publish / Unpublish with success/error toasts
- [x] Optional: button on generated dashboard action or blueprint form already present
- [x] Upgrade + restart `:19005`; hard-refresh assets
- [x] Manual checklist: CRM Customers add KPI + shortcut + reorder + config groupby + Publish

**Verify:** `/web/login` 200; manual checklist pass

---

## Wave D (live preview) — shipped in 19.0.1.0.86

1. [x] Sample host record picker in Studio toolbar / map pane  
2. [x] Left canvas renders preview from `studio_preview_payload` (`get_record_slots` + header + graph bars)  
3. [x] Fallback to static card map when no sample record  
4. [x] Tests + `:19005` smoke  

---

## Wave E + polish — shipped in 19.0.1.0.87

- [x] Blank dashboard wizard (`dashboard.blueprint.create.wizard`) + menu **New Dashboard**
- [x] Customize on live kanban (Studio group)
- [x] Manage section picker (Views / New / Reports)
- [x] Drag-and-drop reorder for slot lists
- [x] DomainSelectorDialog for KPI/shortcut domain
- [x] Chart.js canvas preview when `graph_json` available

---

## Out of this plan

- Free-form page builder (explicit non-goal)  
- Full domain widget embedded inline (dialog covers Wave E polish)  
- Drag zones into non-card layouts  

---

## Commit policy

Commit only when the user asks. Prefer one commit per completed Task after verification.
