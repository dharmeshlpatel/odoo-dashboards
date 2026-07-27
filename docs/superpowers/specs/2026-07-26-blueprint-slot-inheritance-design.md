# Blueprint Slot Inheritance (V1-parity pool) — Design

**Status:** Approved for planning (2026-07-26)  
**Module:** `dashboard_engine`

## Problem

CRM Customers and Sales Customers (and further N dashboards on the same host) each own Manage / KPI / bottom slots. Showing the same links on multiple cards today means copying slots. V1 solved this with a shared kanban base that every app extends.

## Goals

1. **Bi-directional share** of selected card zones across linked blueprints (N-level / connected component).
2. **Per-link visibility** still driven by each slot’s `group_ids` / `module_depends` / `visible_if_context` (V2 dynamic; V1 used XML `groups=`).
3. **Dedupe** by stable key; first in resolution order wins.
4. **Not shared:** header + left primary button (and primary variants).

## Non-goals

- Sharing graph config, scopes, or menu entry.
- Merging headers or primary CTAs.
- Editing a “virtual” shared slot from every blueprint form (each slot stays owned by one blueprint; others consume it at runtime).

## Model

### Link field

- `dashboard.blueprint.share_blueprint_ids` — `Many2many` to `dashboard.blueprint` (symmetric relation table).
- UI label: **Share links with**.
- Constraint (soft warning or hard): same `host_model_id` recommended; block different host models.

### Shared sections

```
kpi, button_box, bottom, menu_views, menu_new, menu_reports
```

### Local (never shared)

- Header fields / `header_item_ids`
- Primary button + `primary_action_variant_ids`

### Effective slot set (runtime)

For rendering blueprint `B`:

1. Build the **connected component** of blueprints reachable via `share_blueprint_ids` (undirected), including `B`.
2. Collect slots whose `section` is in the shared set from every blueprint in that component.
3. **Order:** `B`’s slots first (by `sequence`), then other blueprints ordered by `(sequence, id)`, each blueprint’s slots by `sequence`.
4. **Dedupe key** (first wins):
   - Primary: `(section, key)` when `key` is set
   - Else: `(section, action_xmlid)` when `action_xmlid` is set
   - Else: keep (no key → never collapsed)
5. Filter with existing `slot._is_visible(ctx)`.

### Builder UX

- On **Card layout** (or a short note on Manage): “Share links with” M2M.
- Slot lists still show **only this blueprint’s owned slots** (edit ownership stays clear).
- Optional later: read-only “Also shown from shared blueprints” list — out of scope for v1 of this feature.

### Seeds

- Link `crm_customers` ↔ `sales_customers` (and website/POS customer packs when present).
- Remove duplicated Sales-origin slots from CRM seeds when keys collide (`box_total_due`, `bottom_deliveries`, …) so Sales owns them and CRM consumes via share.

## Decisions locked

| Topic | Choice |
|---|---|
| Direction | Bi-directional connected component (V1 pool) |
| Duplicates | Dedupe by `(section, key)` then `(section, action_xmlid)`; current blueprint first |
| Visibility | Unchanged `_is_visible` on each slot |
| Header / primary | Local only |
