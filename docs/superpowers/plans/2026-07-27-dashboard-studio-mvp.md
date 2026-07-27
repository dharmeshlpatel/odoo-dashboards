# Dashboard Studio MVP Implementation Plan

> **For agentic workers:** Implement task-by-task in `dashboard_engine`. Prefer Composer/Auto; escalate only if OWL client-action wiring stalls after one attempt.

**Goal:** Non-technical admins customize an installed preset via a visual Studio (card map + zone editors) that writes the same `dashboard.blueprint` records as the Advanced form, then Publish.

**Architecture:** Approach A — `ir.actions.client` OWL app with static card map + guided zone panels. No second layout store. Mutations go through thin Python RPC helpers on `dashboard.blueprint`.

**Tech Stack:** Odoo 19, OWL 2, `web.assets_backend`, existing blueprint/slot/header/scope models.

## Global Constraints

- Engine version bump for assets/security (continue `19.0.1.0.x`)
- Studio edits **existing** published/draft presets only (no blank-create in MVP)
- Zone vocabulary matches form UX: Header, Primary, KPIs, Totals (`button_box`), Shortcuts (`bottom`), Manage (`menu_*`), Configuration
- Access group: `Dashboard Studio`; Advanced form stays Manager-oriented
- No free-form Jinja / page builder
- Mockup reference: canvas `dashboard-studio-mvp-mockup` + approved product spec `docs/superpowers/specs/2026-07-27-preset-apps-studio-mvp-design.md`

**Agent note:** Use Composer/Auto for this plan. Sonnet not required for security + client action + structured OWL editors.

---

### Task 1: Security — Studio group

**Files:**
- Modify: `dashboard_engine/security/dashboard_engine_security.xml`
- Modify: `dashboard_engine/security/ir.model.access.csv` (if Studio needs explicit ACL beyond manager)

- [x] Add `group_dashboard_engine_studio` (“Studio”), sequence between User and Administrator
- [x] Manager implies Studio; Studio implies User
- [x] Studio may write blueprint / slot / header / scope (same write ACL as manager for those models, or imply manager)

### Task 2: Entry points

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` — `action_open_studio`
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` — list/form “Customize” button
- Create: `dashboard_engine/views/dashboard_studio_views.xml` — `ir.actions.client`
- Modify: `__manifest__.py` data list + version

- [x] Client action tag: `dashboard_engine.studio`
- [x] Context passes `blueprint_id` / `active_id`
- [x] Groups: Studio

### Task 3: Studio RPC payload + writes

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_studio.py`

- [x] `get_studio_payload()` → zones, slots by section, headers, scopes, graph summary, state
- [x] `studio_write_slot(slot_id, vals)` / `studio_create_slot(section, vals)` / `studio_unlink_slot`
- [x] `studio_write_header_item` / create / unlink
- [x] `studio_write_blueprint(vals)` for primary label, graph caption, etc.
- [x] Reuse `action_publish` / `action_unpublish`
- [x] Tests: change KPI label via RPC; assert field updated

### Task 4: OWL Studio shell

**Files:**
- Create: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Create: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Create: `dashboard_engine/static/src/scss/studio/dashboard_studio.scss`
- Assets already glob `static/src/js/**/*` and `xml/**/*`

- [x] Register client action `dashboard_engine.studio`
- [x] Layout: top bar Discard/Publish · left card map · right editor
- [x] Zone selection state; highlight active zone
- [x] Load payload on start; reload after writes

### Task 5: Zone editors (MVP depth)

**Priority order:**
1. KPIs (`section=kpi`) — label, plural, show_if_zero, action_xmlid
2. Shortcuts (`bottom`) — label, icon, action
3. Primary — button label, primary_action_xmlid, graph_caption
4. Header lines — field_names, kind, icon
5. Totals (`button_box`) — label, amount_field
6. Manage menus — label + action per `menu_views|menu_new|menu_reports`
7. Configuration — toggle scopes `default_on`; show groupby/measure read-only or simple Char (full domain stays Advanced)

- [x] Each editor calls RPC then refreshes payload
- [x] Plain-language labels (no domain widget in Studio MVP)

### Task 6: Verify on :19005

- [x] `-u dashboard_engine --dev=xml,assets`
- [ ] Open CRM Customers blueprint → Customize → rename a KPI → Publish → open live kanban and confirm

---

## Out of this plan

- Blank dashboard wizard
- Live WYSIWYG of generated kanban arch
- Drag-reorder zones into non-card layouts
- Studio editing of raw domains / technical page
