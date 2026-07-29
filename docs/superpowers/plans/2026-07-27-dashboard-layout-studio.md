# Dashboard Layout Studio (Wave F) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins rearrange Odoo-native dashboard widgets (header, primary, graph, KPIs, totals, shortcuts, manage) on a 12-col grid, persist as JSON, and Publish into generated kanban — unique market story without becoming a free HTML page builder.

**Architecture:** Add `studio_layout` Json on `dashboard.blueprint`; Studio gains Layout mode; `_kanban_arch` renders layout when set, else legacy card shell. Content Studio unchanged. Schema reserves `richtext` for a later wave.

**Tech Stack:** Odoo 19, OWL 2, Bootstrap grid in kanban card arch, existing slot/graph widgets.

## Global Constraints

- Engine version bump `19.0.1.0.x`
- Empty layout = 100% backward compatible with current arch
- Widget allow-list Wave F: header, primary, graph, kpis, totals, shortcuts, manage
- At most one instance of each Wave F widget type per layout
- No user HTML rendering in Wave F
- Studio group gates Layout writes
- After UI changes: restart `:19005` with `-u dashboard_engine --dev=xml,assets`
- Spec: `docs/superpowers/specs/2026-07-27-dashboard-layout-studio-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | Field, default layout, validate, write RPC, `_kanban_arch` layout path |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Mode toggle + Layout canvas interactions |
| `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` | Layout UI |
| `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` | Grid chrome |
| `dashboard_engine/tests/test_dashboard_studio.py` | Layout validate + publish arch contains ordered widgets |
| Docs | Spec already written; mark plan checkboxes |

---

### Task 1: Layout field + default + validate + RPC

**Files:** `dashboard_blueprint.py`, tests

- [x] Add `studio_layout = fields.Json(string="Studio Layout")`
- [x] `_default_studio_layout()` returning schema v1 matching current card
- [x] `_validate_studio_layout(layout)` — version, spans, allow-list, uniqueness
- [x] `studio_write_layout(layout)` → validate + write + return `get_studio_payload`
- [x] `get_studio_payload` includes `layout` (or default when empty) and `layout_is_custom`
- [x] Tests: invalid span fails; valid write persists; default factory stable

---

### Task 2: Publish path — render kanban from layout

**Files:** `dashboard_blueprint.py`

- [x] Split legacy body into `_legacy_card_body_arch()` (current inner markup)
- [x] `_layout_widget_arch(widget_type, key, caption)` for each allow-listed type (reuse existing snippets)
- [x] `_kanban_arch_from_layout(layout)` → Bootstrap `row` / `col-*` wrapping widgets
- [x] `_kanban_arch`: if custom layout → layout path; else legacy
- [x] Test: write layout with kpis before primary → published `arch_db` has KPI block before primary button (order assertion)

---

### Task 3: OWL Layout mode

**Files:** Studio JS / XML / SCSS

- [x] Mode tabs: Content | Layout (live sample is ambient on Content map + Layout strip; Preview tab removed)
- [x] Layout canvas: list rows; each col shows widget chip + span control
- [x] Actions: Add row, set span, move widget up/down or drag between cells, remove widget from layout (content remains in blueprint), Reset to default
- [x] Palette of missing widget types
- [x] Save calls `studio_write_layout`; dirty state shared with Content where sensible
- [x] Polish to match existing Studio teal chrome

---

### Task 4: Ship

- [x] Bump `__manifest__.py` version (`19.0.1.0.88`)
- [x] Upgrade + restart `:19005`
- [x] Manual: CRM Customers → Layout → swap KPI/graph columns → Save → Publish → live kanban
- [ ] Commit when user asks (or if already told to ship)

---

## Out of Wave F

- Richtext/HTML block editor (schema hook only)
- Absolute positioning canvas
- Nested grids
- Free-form Jinja

---

## Commit policy

Commit only when the user asks, unless this plan is executed under an explicit “do it / ship” request covering Wave F.
