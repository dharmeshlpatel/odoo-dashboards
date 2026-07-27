# Dashboard Studio Complete — Card Studio then Live Preview

**Date:** 2026-07-27  
**Module:** `dashboard_engine` (odoo-dashboards-19.1-v2)  
**Status:** Approved product direction (A then B)  
**Supersedes for Studio depth:** Phase B MVP label-only editors (keep entry points / RPC skeleton)  
**Related:** `2026-07-27-preset-apps-studio-mvp-design.md` (positioning + Phase A packaging still apply)

## Positioning (one line)

> Non-technical admins redesign installed **customer/salesperson card** dashboards visually — content in Studio, then (Wave F) **rearrange the same Odoo-native widgets** on a page grid. Not a generic HTML page builder.

## Problem

The Blueprint form is complete but too technical. Studio MVP today only edits labels on existing items. Buyers expect a professional visual editor with full card customization; without add/remove and guided pickers, Studio has weak App Store value.

## Decision (locked)

| Choice | Decision |
|--------|----------|
| Product shape | **A — Complete Card Studio**, then **B — Live WYSIWYG preview** |
| Free-form HTML page builder | **Out** — Wave F is **Layout Studio** (grid of known widgets); see `2026-07-27-dashboard-layout-studio-design.md` |
| Source of truth | `dashboard.blueprint` + slots / headers / scopes — no second layout store |
| Advanced form | Remains for partners / raw domains / technical fields |
| Blank dashboard wizard | Out of Waves C–D (optional later Wave E) |

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  OWL Dashboard Studio (client action)                   │
│  Card map / live preview · zone panels · catalogs       │
└───────────────────────────┬─────────────────────────────┘
                            │ studio_* RPC
┌───────────────────────────▼─────────────────────────────┐
│  dashboard.blueprint (+ slot / header / scope)          │
│  Validation · health · publish → generated kanban       │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Live host kanban (runtime widgets unchanged)           │
└─────────────────────────────────────────────────────────┘
```

**Reuse:** Existing `action_open_studio`, `get_studio_payload`, `studio_write_*`, `studio_create_slot`, `studio_unlink_slot`, Studio security group, assets under `static/src/js|xml|scss/studio/`.

## Wave C — Complete Card Studio (market value)

### Goals

Anything a non-tech admin needs for day-to-day card customization is doable in Studio without opening the Advanced form.

### In scope

1. **Structure CRUD** for all card zones  
   - Add / Remove / Reorder (sequence) for: KPIs, Totals (`button_box`), Shortcuts (`bottom`), Manage (`menu_views|menu_new|menu_reports`), Header lines  
   - Fixed card shell (no arbitrary zone layout)

2. **Guided zone editors**  
   - **KPIs / Shortcuts:** label, plural, show_if_zero, icon, style, value mode (count / amount / both), compute model + link-to-card, conditions M2M picker, action xmlid (searchable) or host method, optional `module_depends`  
   - **Totals:** label + amount/count field pickers  
   - **Primary:** button label, primary action, graph caption  
   - **Header:** kind, field_names (from host field catalog), icon  
   - **Manage:** label + action per menu section  
   - Domains: studio-friendly builder for common filters; link out to Advanced for extras

3. **Configuration**  
   - Scope `default_on` (+ rename if cheap)  
   - Graph measure / groupby / granularity via field catalog (not raw Char as primary UX)

4. **Workflow polish**  
   - Dirty state, Discard, Publish / Unpublish, validation errors as notifications  
   - Optional “Customize” entry from live dashboard for Studio users

5. **Catalog RPCs**  
   - Host / compute model fields, action xmlid search, icon list, condition list — JSON helpers on blueprint or thin studio service model

### Out of Wave C

- Live pixel preview of real records (Wave D)  
- Blank-from-scratch wizard  
- Free-form layout / Jinja page builder  
- Replacing Odoo Studio for forms/views

### Success criteria (Wave C)

1. Admin can add a new KPI and a new bottom shortcut in Studio, Publish, and see them on the live kanban.  
2. Admin can remove or reorder items without the Blueprint form.  
3. Admin can change graph groupby/measure and a scope default via Configuration.  
4. Advanced form still works; Studio writes the same records.  
5. Studio group ACL continues to gate Customize.

## Wave D — Live WYSIWYG preview

### Goals

Same editors; left canvas shows a **real sample host card** (partner / user / …) that refreshes after saves.

### In scope

- Sample record picker (or first available host record)  
- Preview using existing runtime payload paths where practical (`get_record_slots`, graph helpers)  
- Zone highlight on preview when editing  
- Fallback to static card map if no sample record

### Out of Wave D

- Editing layout structure beyond the fixed card  
- Second layout persistence store

### Success criteria (Wave D)

1. Changing a KPI label updates the preview without leaving Studio.  
2. Preview uses a real host record the admin can switch.

## Non-goals (initiative)

- Competing with free-form dashboard page builders  
- Host-model Python inheritance  
- Rewriting runtime kanban OWL from scratch

## Risks

| Risk | Mitigation |
|------|------------|
| Studio becomes a second incomplete form | Zone vocabulary matches form; Advanced remains escape hatch |
| Slot create without enough fields = broken KPI | Create wizards with required defaults + validation before Publish |
| Share-link pooled slots confuse edits | Document which sections share; write through same ORM as form |
| Scope creep to page builder | Reject free layout; review against positioning |

## Delivery order

1. This design approved (done).  
2. Implementation plan Wave C (task-by-task).  
3. Ship Wave C on `:19005`.  
4. Implementation plan Wave D (or same plan Part 2).  
5. Ship Wave D.  
6. Optional Wave E: blank dashboard wizard (separate decision).

## Agent note

Prefer Composer/Auto. Escalate only if OWL client-action or domain-builder wiring stalls after a solid attempt.
