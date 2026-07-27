# Product architecture — Preset Apps + Studio MVP (edit presets)

**Date:** 2026-07-27  
**Module family:** `odoo-dashboards-19.1-v2`  
**Status:** Draft — awaiting user review  
**Decision owners:** Product + Odoo architect (agreed in chat 2026-07-27)

## Positioning (one line)

> Live CRM/Sales **customer cards** for Odoo — install ready-made dashboards from Apps, then non-technical admins redesign them visually. Not a free-form Jinja page builder (Kisolve lane).

## Problem

- Today’s `dashboard_engine` mixes **runtime** and **business presets** (soft `module_depends` + seed XML). Packaging and App Store story are weak.
- The Blueprint form is powerful but too technical for the buyers who demand a **visual editor**.
- Competing on “drag-and-drop any dashboard page” (Kisolve-style) is the wrong fight; competing on **Odoo-native card dashboards** is winnable.

## Product shape

```text
┌─────────────────────────────────────────────────────────┐
│  Apps (install)                                          │
│  crm_customer_dashboard / sales_customer_dashboard / …   │
│  → hard depends + XML presets (dashboard.blueprint…)     │
└───────────────────────────┬─────────────────────────────┘
                            │ writes / ships records
┌───────────────────────────▼─────────────────────────────┐
│  dashboard_engine                                        │
│  • Runtime (kanban, scopes, share links, slots, …)       │
│  • Studio MVP (OWL) — edits existing presets             │
│  • Blueprint form — Advanced / partner mode              │
└───────────────────────────┬─────────────────────────────┘
                            │ publish
┌───────────────────────────▼─────────────────────────────┐
│  Live host kanban (res.partner / …)                      │
└─────────────────────────────────────────────────────────┘
```

**Single source of truth:** Studio and Blueprint form both read/write `dashboard.blueprint` (+ scopes, slots, headers). No second layout store. No raw Jinja kanban arch as the primary artifact.

## Phase A — Preset Apps (Idea 1)

### Goal

Engine = logic only. Each business dashboard is its own installable app.

### Module responsibilities

| Module | Role |
|---|---|
| `dashboard_engine` | Models, security, OWL runtime widgets, Studio (Phase B), Blueprint form (Advanced), generic conditions/periods helpers |
| `crm_customer_dashboard` | `depends`: `dashboard_engine`, `crm` (+ report modules as needed); CRM Customers (+ salesperson if in scope) blueprint XML, share links with Sales when both installed |
| `sales_customer_dashboard` | Same pattern for Sales |
| Later | `pos_…`, `website_…`, warehouse, enterprise overlays — same thin-data pattern |

Naming may follow V1 (`crm_customer_dashboard`) for market familiarity; technical XMLIDs can stay `dashboard_engine.*` during migration or move to the new module namespace with a migration script — **pick one namespace strategy in the implementation plan** (prefer new module xmlids + one-shot migrate).

### What leaves the engine

- Seed blueprints and parity XML currently under `dashboard_engine/data/seed_*.xml` that are app-specific (CRM, Sales, POS, Website, warehouse headers tied to those apps).
- Soft “activate when crm installed” as the **primary** delivery mechanism for those presets.

### What stays in the engine

- Generic conditions that are reusable (e.g. overdue patterns) if still model-agnostic.
- Graph period catalog data if generic.
- Empty / demo-free install: engine alone shows **no** CRM menu dashboard until a preset app is installed.

### Hard depends

Preset apps use real `depends` on business apps (and report modules where V1 had them: e.g. `report_crm`, `report_sale`, …) so missing apps never leave half-broken soft seeds.

### Share Links

Preserved. CRM ↔ Sales pooling stays data (`share_link_ids`) owned by the preset modules’ XML / post-init, not duplicated slot copies.

## Phase B — Studio MVP (path A only)

### Goal

Non-technical admin opens an **installed** preset and customizes the live card visually, then publishes.

### In scope (MVP)

- Entry: from blueprint list / “Customize dashboard” on an existing published preset (not “New blank dashboard”).
- Visual canvas aligned to card zones already named in the form UX:
  - Header (title, image, lines)
  - Primary button (label, alternate label/filter, action)
  - Right · KPIs
  - Footer · Totals
  - Footer · Shortcuts
  - Manage menu (Views / New / Reports) — simple label + action pickers
- Configuration (scopes, graph, filters) as **guided panels** (plain language), not raw domain-first.
- Publish / Unpublish using existing blueprint actions.
- Access: dedicated group e.g. `Dashboard Studio` (admins); Blueprint form remains for `Dashboard Manager` / technical.

### Out of scope (MVP)

- Blank dashboard from scratch (host model wizard).
- Free-form Jinja / HTML page builder.
- Arbitrary zone reordering into non-card layouts.
- Live WYSIWYG of every kanban pixel (optional later); MVP may be structured editors beside a **static card map** / simplified preview.
- Competing feature-parity with Kisolve page chrome.

### Studio write path

All mutations go through ORM on existing models (`dashboard.blueprint`, `dashboard.blueprint.slot`, scopes, header lines, …). Validation and health checks reuse current engine rules.

## Advanced surface

- Keep **Blueprint form** for partners and power users (full domain widgets, Technical page, Extra Domain/Context).
- Marketing and default menus push users to **Studio on presets**, not the form.

## Non-goals (this initiative)

- Replacing Odoo Studio for forms/views.
- Host-model Python inheritance (engine stays config-driven).
- Rewriting runtime kanban OWL from scratch.

## Success criteria

1. Install `dashboard_engine` alone → no CRM Customers dashboard menu.
2. Install `crm_customer_dashboard` (CRM present) → CRM Customers dashboard works as today.
3. Non-tech admin with Studio access can change a KPI label / add a footer shortcut and see it after Publish without opening the Blueprint form.
4. Share Links between CRM and Sales presets still pools KPIs / footers / Manage menu; Header + Primary stay local.
5. Positioning test: buyer understands “customer card dashboards,” not “any page builder.”

## Delivery order

1. **Spec approved** (this document).  
2. **Implementation plan: Phase A** — extract CRM (+ Sales) seeds into modules; strip engine seeds; migrate xmlids; upgrade path.  
3. **Ship Phase A** and verify parity on `:19005`.  
4. **Implementation plan: Phase B** — Studio MVP OWL on presets.  
5. **Ship Phase B** MVP; gather admin feedback before blank-create or free-canvas.

Do not start Phase B UI before Phase A packaging is stable (Studio must open real preset records from Apps).

## Risks

| Risk | Mitigation |
|---|---|
| Xmlid / noupdate migration breaks existing DBs | Dedicated pre/post migrations; keep keys (`crm_customers`) stable |
| Studio becomes a second incomplete form | Zone-limited MVP; Advanced = existing form |
| Scope creep toward Kisolve | Explicit non-goals; review every “free layout” request against positioning |
| Too many thin modules at once | Phase A starts with CRM + Sales only; POS/Website in a follow-up |

## Open points (resolve in Phase A plan)

1. Exact technical module names (`crm_customer_dashboard` vs `dashboard_crm_customers`).  
2. Whether salesperson blueprint lives in CRM module or a sibling.  
3. Xmlid namespace migration vs keep `dashboard_engine.*` xmlids with data files moved (simpler upgrades, slightly odd ownership).

**Recommendation for open point 3:** keep stable `dashboard_engine.*` xmlids initially while moving file ownership to preset modules via `noupdate` data in the new module that uses the same xmlids through careful migration — **or** new xmlids + rewrite `ir.model.data`. Prefer **same keys + migrate module assignment** so menus/actions survive. Detail in Phase A plan.

## Related docs

- Form UX: `2026-07-27-blueprint-full-form-ux-design.md`  
- Prototype: workspace canvas `blueprint-full-form-ux-prototype.canvas.tsx`  
- V1 reference: `odoo-dashboards-19.1/crm_customer_dashboard` (and siblings)
