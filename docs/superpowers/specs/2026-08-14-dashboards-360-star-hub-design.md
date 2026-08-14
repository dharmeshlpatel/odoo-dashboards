# Dashboards 360 — Star Hub + Self-Registering Packs

**Date:** 2026-08-14  
**Status:** Prototype  
**Repo:** `odoo-dashboards-19.1-v2`

## Product

| Door | Opens | Share |
|------|--------|--------|
| Apps → **Dashboards 360** | Left list of 360 hubs; right pane is the selected kanban | 360 **composes** installed packs |
| CRM / Sales / POS / Website / Invoice → **Reporting** | That app’s own customers dashboard | **Standalone** — no pack↔pack Share Links |

Do **not** depend on Odoo `board` or `spreadsheet_dashboard`.

## Architecture

### 1. Dashboards 360 is a root app

`dashboard.blueprint.hub` flag **`is_root_app`**.

- True → generate `ir.ui.menu` with **no parent** + `web_icon` (Odoo apps grid).
- False + empty parent → no menu (old Engine behaviour).
- False + parent → nested menu.

Default hub xmlid `dashboard_engine.dashboard_hub_default`: name **Dashboards 360**, `is_root_app=True`.

Group xmlid `dashboard_engine.dashboard_group_360` (“360”) hangs on that hub. Compose hubs (`customer_360`, `product_360`, …) set `group_id` here so they appear as **left links**.

### 2. Compose hub vs pack

Blueprint flag **`is_compose_hub`** (also inferred from `key` ending in `360`).

`_share_pool_members()`:

- **Compose hub** → self + **direct** `share_link_ids` (spokes). Not transitive through spokes.
- **Pack** → self + directly linked **non-hub** peers. A link to a 360 hub does **not** pull sibling packs.

Slots, Chart Model Options, and panel maps use this set (not the old undirected connected component).

### 3. Star Share Links (self-register)

Engine method `_sync_star_share_pool(hub_xmlid, spoke_xmlids)`:

1. If the hub blueprint exists, set its Share Links to **installed spokes only**.
2. Drop spoke↔spoke links inside that pool.
3. Symmetric M2M may still tag the hub on each spoke (builder UX). Packs still do not compose hub/sibling content.

Each customer pack `post_init` calls this helper. **No hard depends** from Customer 360 on Sales/POS/Website. Install a pack → it registers. Uninstall → next sync omits it.

### 4. Soft-empty 360

Customer 360 may ship with only CRM installed. Left link still shows. Shared KPIs/charts grow as packs are installed. Required Apps on slots still hide tiles the user cannot access.

## Out of scope (later)

- Full seed rewrite of every pack to latest Studio field layout.
- Visual clone of spreadsheet Dashboards CSS.
- Putting 360 items inside `spreadsheet.dashboard.group`.
