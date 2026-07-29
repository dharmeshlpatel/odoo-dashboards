# Dashboard Studio Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Studio **Setup** mode so admins can edit host (guarded), required apps, company, share links, and menu fields with form parity — without leaving Studio for Advanced.

**Architecture:** Extend `get_studio_payload` / `studio_write_blueprint` with Setup fields and host-change cleanup on the server; OWL gains `setup` mode (Setup | Content | Layout), two-column Dashboard/Menu form, header chip → Setup, confirm dialog on draft host change. Publish/menu sync stays on existing blueprint write/publish paths.

**Tech Stack:** Odoo 19, OWL 2, existing Studio client action + `dialog` service, `dashboard.blueprint` studio_* RPCs.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-dashboard-studio-setup-design.md`
- Engine version bump `19.0.1.0.x` (current floor ≥ `.93`)
- Host editable only when `state == 'draft'`; published → lock host in Studio
- Host change: confirm client-side; server surgical cleanup (no slot row deletes)
- Modes order: Setup · Content · Layout; default open remains **Content**
- Studio group gates writes (existing)
- After UI changes: restart `:19005` with `-u dashboard_engine --dev=xml,assets`
- Commit only when user asks

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | Payload setup keys, whitelist, cleanup helper, search RPCs |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Setup mode state, save/discard, confirm, pickers |
| `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` | Mode tabs, Setup form, header chip |
| `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` | Setup two-column chrome |
| `dashboard_engine/tests/test_dashboard_studio.py` | Payload, write, host lock, cleanup |
| `__manifest__.py` | Version bump |

---

### Task 1: Payload + whitelist + host cleanup + search RPCs

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_studio.py`

**Interfaces:**
- Produces: extended `get_studio_payload()` keys; `studio_write_blueprint` accepts Setup fields; `_studio_cleanup_after_host_change()`; `studio_search_models|menus|modules|share_blueprints`

- [x] **Step 1: Extend `_STUDIO_BP_WRITE_FIELDS`**
- [x] **Step 2: Extend `get_studio_payload`**
- [x] **Step 3: Implement cleanup + wire into `studio_write_blueprint`**
- [x] **Step 4: Search RPCs**
- [x] **Step 5: Tests** (18 passed)

---

### Task 2: OWL Setup mode UI + save/confirm + chip

**Files:**
- Modify: `dashboard_studio_action.js`, `.xml`, `.scss`

**Interfaces:**
- Consumes: payload Setup keys + search RPCs + `studio_write_blueprint`
- Produces: `studioMode === 'setup'`, setup editor draft, header chip click

- [x] **Step 1: Mode switcher**
- [x] **Step 2: Setup state**
- [x] **Step 3: Setup template**
- [x] **Step 4: Header chip**
- [x] **Step 5: Save / Discard**
- [x] **Step 6: SCSS**

---

### Task 3: Ship on :19005

- [x] Bump `__manifest__.py` version (`19.0.1.0.94`)
- [x] Kill :19005; restart with `-u dashboard_engine --dev=xml,assets`
- [x] Wait `/web/login` HTTP 200
- [ ] Manual smoke by user: Setup → menu name → Save; draft host confirm; published host locked; chip opens Setup
- [ ] Commit when user asks

---

## Out of scope

- Rename blueprint name/key in Setup
- Host change while published
- Auto field remapping
- Embedded Advanced notebooks

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Setup mode + order | T2 |
| Full Dashboard/Menu fields | T1+T2 |
| Host draft/published lock | T1+T2 |
| Confirm + surgical cleanup | T1+T2 |
| Header chip | T2 |
| Search pickers | T1+T2 |
| Tests | T1 |
| Ship :19005 | T3 |

## Commit policy

Commit only when the user asks.
