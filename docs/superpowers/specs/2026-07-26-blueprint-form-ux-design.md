# Blueprint form UX — two-page builder

**Date:** 2026-07-26  
**Module:** `dashboard_engine`  
**Status:** Approved for implementation

## Goal

Make Dashboard Blueprints layman-friendly by collapsing today’s multi-tab form into:

1. **Sheet — Card identity + Menu entry** (always visible)
2. **Notebook page 1 — Dashboard behaviour** (mirrors live ⚙️ popup)
3. **Notebook page 2 — Card layout** (header, body, two-layer bottom)
4. **Notebook page 3 — Manage** (Views / New / Reports as stacked separators)
5. **Notebook page 4 — Advanced** (managers only)

## Naming

| UI label | Meaning |
|---|---|
| Card identity | What each card represents (`host_model`, apps, key) |
| Dashboard behaviour | Scopes, graph, filters (live Configuration popup) |
| Card layout | Header, body, two-layer bottom, manage |

## Card layout zones

1. **Header** — title, image, configurable detail/tag lines (email/phone are not hardcoded)
2. **Body · Left** — primary button + graph placement (button chrome here; graph *data* on page 1)
3. **Body · Right** — KPI slots (`section=kpi`)
4. **Bottom · Stat box** — layer 1 (`section=button_box`)
5. **Bottom · Action bar** — layer 2 (`section=bottom`)
6. **Manage** (own notebook page) — three stacked separators, each with its own O2M: Views / New / Reports

## Non-goals

- No new models; reuse `slot_ids` / `header_item_ids` / `scope_ids`
- No change to runtime kanban rendering beyond form UX
- Advanced technical mirrors stay manager-only
