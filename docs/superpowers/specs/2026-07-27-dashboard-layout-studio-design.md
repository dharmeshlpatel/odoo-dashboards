# Dashboard Layout Studio — rearrangeable Odoo-native card pages

**Date:** 2026-07-27  
**Module:** `dashboard_engine`  
**Status:** Approved product direction (expertise path for market uniqueness)  
**Depends on:** Studio Complete (Waves C–E) shipped  
**Related:** `2026-07-27-dashboard-studio-complete-design.md`

## Market positioning (one line)

> Install ready-made CRM/Sales **customer cards**, customize every KPI/shortcut in Studio, then **rearrange the same Odoo-native widgets** on a responsive page grid — Publish. Not a generic HTML page builder; not a rigid single layout forever.

### Uniqueness vs alternatives

| Competitor / alternative | Gap we fill |
|--------------------------|-------------|
| Kisolve-style free canvas | We stay Odoo-record cards + real CRM actions/counts |
| Fixed V1/V2 card shell only | Admins can change page composition |
| Odoo Studio forms | We own dashboard cards, not form views |

**Hook for later (not Wave F):** optional `text` / sanitized HTML block type — schema allows `type: "richtext"` but Wave F does not ship the editor or renderer.

## Problem

Studio Complete edits **content** inside fixed zones. Buyers still ask to “move the chart under the KPIs” / “put shortcuts on the right.” Without layout freedom, the product feels unfinished vs page builders — while full free-form HTML would erase our differentiator.

## Decision (locked)

| Choice | Decision |
|--------|----------|
| Shape | **Layout Studio** — 12-column Bootstrap grid of **known widget types** |
| Content editing | Existing Card Studio zone editors (unchanged) |
| Layout store | JSON on `dashboard.blueprint.studio_layout` (structured, versioned schema) |
| Default | Empty / falsy layout → current fixed card arch (backward compatible) |
| Publish | `_kanban_arch` renders from layout when set; else legacy `_kanban_arch` card shell |
| Raw HTML primary artifact | **No** in Wave F |
| Free absolute canvas | **No** |

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│  Studio modes                                                 │
│  Content (zones)  |  Layout (grid)  |  Preview (sample host) │
└────────────────────────────┬─────────────────────────────────┘
                             │ studio_layout_* RPC
┌────────────────────────────▼─────────────────────────────────┐
│  dashboard.blueprint.studio_layout (JSON)                     │
│  + existing slots / headers / scopes / graph fields           │
└────────────────────────────┬─────────────────────────────────┘
                             │ Publish → generated kanban arch
┌────────────────────────────▼─────────────────────────────────┐
│  Live host kanban (same runtime widgets: slots, graph, …)    │
└──────────────────────────────────────────────────────────────┘
```

### Layout schema (v1)

```json
{
  "version": 1,
  "rows": [
    {
      "id": "r1",
      "cols": [
        { "id": "c1", "span": 12, "widget": { "type": "header" } }
      ]
    },
    {
      "id": "r2",
      "cols": [
        { "id": "c2", "span": 7, "widget": { "type": "primary" } },
        { "id": "c3", "span": 5, "widget": { "type": "kpis" } }
      ]
    },
    {
      "id": "r3",
      "cols": [
        { "id": "c4", "span": 12, "widget": { "type": "graph" } }
      ]
    },
    {
      "id": "r4",
      "cols": [
        { "id": "c5", "span": 6, "widget": { "type": "totals" } },
        { "id": "c6", "span": 6, "widget": { "type": "shortcuts" } }
      ]
    },
    {
      "id": "r5",
      "cols": [
        { "id": "c7", "span": 12, "widget": { "type": "manage" } }
      ]
    }
  ]
}
```

**Wave F widget types:** `header` | `primary` | `graph` | `kpis` | `totals` | `shortcuts` | `manage`  

Each maps 1:1 to existing generated arch fragments / slot widgets (no new runtime compute models).

**Reserved for later:** `richtext` with `{ "html": "..." }` — ignored by Wave F renderer if present.

### Default layout factory

`_default_studio_layout()` returns the schema above (matches today’s card).  
**Reset layout** restores default.  
**Migrate:** on first open of Layout mode, if `studio_layout` empty, seed default without writing until Save (or auto-save on first Layout edit).

## Studio UX (Wave F)

1. Mode toggle: **Content | Layout | Preview** (Preview already exists; Layout is new).  
2. Layout canvas: rows; each row has columns with span 1–12; drag widgets between cells; add row / split column / delete empty.  
3. Palette: widget types not yet on the page (or allow duplicates only for types that make sense — Wave F: **at most one** of each type except future richtext).  
4. Span control: buttons 3 / 4 / 6 / 8 / 12.  
5. Save layout via `studio_write_layout(layout)`; Publish regenerates kanban.  
6. Content mode still edits slot/header/config as today.

## Backend

| Piece | Responsibility |
|-------|----------------|
| Field `studio_layout` Json on blueprint | Persist layout |
| `get_studio_payload` | Include `layout` (+ `layout_default` flag) |
| `studio_write_layout(vals)` | Validate schema version + widget allow-list + span sums ≤ 12 |
| `_kanban_arch` | If layout: compose Bootstrap rows from widget renderers; else legacy |
| Widget render helpers | `_layout_widget_arch(type)` reuse existing header/slots/graph snippets |

## Security / validation

- Studio group only (same as today).  
- Reject unknown widget types (except ignore `richtext` with warning in payload).  
- Per-row sum(`span`) must be 1–12.  
- Sanitize: no user HTML in Wave F.

## Success criteria

1. Admin opens Layout mode on CRM Customers, moves KPIs left of chart, Save + Publish → live kanban matches.  
2. Presets with empty `studio_layout` look identical to today.  
3. Content Studio (add KPI etc.) still works with custom layouts.  
4. Product story: “Odoo-native card widgets you can rearrange” — not “build any webpage.”

## Non-goals (Wave F)

- Absolute free canvas / pixel positioning  
- Arbitrary HTML/Jinja as primary layout  
- Nested grids deeper than one row of columns  
- Dragging individual KPI items across pages (that stays Content mode)  
- Shipping richtext editor (schema hook only)

## Delivery

1. Spec (this doc)  
2. Implementation plan Wave F  
3. Ship on `:19005` + tests  
4. Docs / App Store blurb update  

## Agent note

Composer/Auto. Prefer extending Studio OWL + `_kanban_arch`; no new module.
