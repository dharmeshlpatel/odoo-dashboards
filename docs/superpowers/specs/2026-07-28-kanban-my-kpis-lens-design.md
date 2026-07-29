# Kanban Lens — My Data + With KPIs (Wave 1)

**Date:** 2026-07-28  
**Module:** `dashboard_engine` (+ preset action context seeds)  
**Status:** Approved (design dialogue)  
**Related:** CRM audit deferred item “Search defaults My Partners / With Analytics”; naming brainstorm 2026-07-28  
**Does not revive:** `report_account`, `report_pos_sale`, `report_sale_stock`, `report_stock_enterprise`, `report_website_sale`  
**Keeps:** `report_sale_crm` (create Lead/Opp actions only)

## Positioning (one line)

> The dashboard kanban gets a first-class **lens** — “My …” and **With KPIs** — so daily browsing matches v1 habit value, without porting the old `report_*` drill-down stack.

## Problem

v1 kanban search offered **My Partners / My Products** and **With Analytics**. Graphs and card lists stayed in sync when those filters were on.

v2 publishes generated actions with only `dashboard_blueprint_key` + `initializer`. Host models use lightweight `base` hooks (no shell modules). Engine graph mixin still *knows* how to rewrite `my_*` / analytics-style domains, but:

1. Hosts no longer inherit that mixin for search.
2. Virtual boolean fields and search filters are missing.
3. Generated action context never enables or defaults those filters.

Drill-down “My Orders / My Quotation” from `report_*` is a **separate** problem (Wave 2+). This spec is **kanban lens only**.

## Decision (locked)

| Choice | Decision |
|--------|----------|
| Product priority | **Kanban lens first** (My + With KPIs) |
| KPI filter **UI label** (default) | **With KPIs** (replaces v1 “With Analytics”) |
| KPI filter **technical names** | `*_with_kpis` / `lens_kpis_*` (not `*analytics*`) |
| KPI filter **meaning** | Hosts that have dashboard data for this blueprint (graph and/or KPI slot presence) — label says KPIs for product tone |
| `report_*` revive (five modules) | **Out** of Wave 1 and of core product path |
| `report_sale_crm` | **Keep** for CRM create actions |
| Field placement | Virtual booleans on **`base`** (any host), rewritten only in dashboard context |
| Domain rewrite home | Move / mirror rewrite onto **`base`** when `dashboard_blueprint_key` is set (not only graph mixin) |
| Filter UI | Generated search view that **inherits** the host’s standard search + injects lens filters; action **context flags** |
| My / KPIs labels | **Always required** on the blueprint when the matching lens is enabled — no host-model auto-default |
| Label resolution | Use `lens_my_label` / `lens_kpis_label` as stored; empty label + enabled filter = publish/health error |
| Defaults (on/off) | Blueprint flags: show My, show With KPIs, default-on for each; presets seed labels explicitly |
| User “My Pipeline” toggle on `res.users` | **Out of Wave 1** (graph-config preference); kanban search is enough for ship |
| Studio Setup control for lens | **Out of Wave 1** (Advanced / seed only; Studio later) |
| Drill-down My Orders on opened lists | **Wave 2** — host-scoped standard actions; no `report_*` |

### Product rule

> The dashboard filters **who/what you manage**; the card filters **which record**; opened actions must not fight those two.

### Naming (locked from brainstorm)

| Layer | Locked value |
|-------|----------------|
| Audience | Sales users **and** admins |
| Stress | Relevance / “cards worth showing” |
| Default UI label | **With KPIs** |
| Rejected UI labels | With Analytics, On this dashboard, Non-empty only, Hide empty, With results, Tracked (kept as alternatives only if a preset overrides `lens_kpis_label`) |

## Field & filter model

### Virtual fields on `base`

| Technical name | Type | Meaning |
|----------------|------|---------|
| `dashboard_my_data` | Boolean (non-stored) | Search flag: restrict hosts to current user’s scope |
| `dashboard_with_kpis` | Boolean (non-stored) | Search flag: only hosts with dashboard data (graph/KPI presence) for this blueprint |

Never used as real stored data. Domain entries like `[('dashboard_with_kpis', '=', True)]` are **rewritten** before SQL.

Do **not** introduce `dashboard_with_analytics` / `with_analytics` on v2 hosts.

### Blueprint fields (config)

| Field | Purpose |
|-------|---------|
| `lens_my_enabled` | Show “My …” filter on generated search |
| `lens_my_default` | `search_default_dashboard_my_data` on generated action |
| `lens_my_label` | **Required** when `lens_my_enabled` — UI string (e.g. My Partners / My Products / My Users) |
| `lens_kpis_enabled` | Show **With KPIs** filter |
| `lens_kpis_default` | Default that filter on |
| `lens_kpis_label` | **Required** when `lens_kpis_enabled` — UI string (presets use **With KPIs**) |

**No engine fallback** from host model. Preset XML (or the admin) must set labels. Suggested seed values by host:

| Host | Seed `lens_my_label` | Seed `lens_kpis_label` |
|------|----------------------|------------------------|
| `res.partner` | My Partners | With KPIs |
| `product.product` | My Products | With KPIs |
| `res.users` | My Users | With KPIs |
| `stock.warehouse` | My Warehouses | With KPIs |

Preset seeds also set on/off defaults (match v1 Sales/CRM: both filters often default on).

### Scope semantics (rewrite)

**My data** (when filter active):

1. If host has `user_id` → `[('user_id', '=', uid)]`.
2. Else resolve host ids via blueprint graph model: records where graph `user_id = uid` (same idea as v1 `_dashboard_record_ids` / partner without `user_id`).
3. If blueprint has no graph / no usable user link → **do not show** My (publish/health clears or blocks `lens_my_enabled`; never leave a no-op filter in the UI).

**With KPIs** (when `dashboard_with_kpis` filter active):

1. Host ids that appear in this blueprint’s dashboard-data scope (graph and/or KPI-bearing resolution — same practical set v1 called “analytics”).
2. If My is also active, AND both (KPI-data ∩ my-scope).

Kanban list domain and graph payloads must use the **same** resolved id set.

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│  Generated act_window context                            │
│  dashboard_blueprint_key · show lens flags · search_default_* │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│  Generated search view (inherit_id = host default search)│
│  Injects: lens_my_label · lens_kpis_label                │
│  domain uses dashboard_my_data / dashboard_with_kpis     │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│  base.search path (dashboard context only)               │
│  Rewrite virtual flags → real domains via blueprint      │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│  dashboard.blueprint                                     │
│  _lens_my_domain() · _lens_kpis_host_ids() · graph sync  │
└──────────────────────────────────────────────────────────┘
```

**Reuse:** Existing `_build_graph_payloads`, `_dashboard_record_ids`-style helpers on blueprint, generated `_upsert_window_action` / search view upsert, CRM audit note on deferred search defaults.

## Generated action context (publish)

Extend `_upsert_window_action` context roughly:

```python
{
    "dashboard_blueprint_key": self.key,
    "initializer": self.key,
    "show_dashboard_my_filter": self.lens_my_enabled,
    "show_dashboard_kpis_filter": self.lens_kpis_enabled,
    # only when enabled + default:
    "search_default_dashboard_my_data": True,   # if lens_my_default
    "search_default_dashboard_with_kpis": True, # if lens_kpis_default
}
```

Filters in search arch stay `invisible` unless the matching `show_*` context key is set — same pattern as v1 `show_my_partner_filter` / `show_with_analytics_filter` (v1 name; v2 uses `show_dashboard_kpis_filter`).

## Host coverage (Wave 1)

| Host | Typical My label | Presets |
|------|------------------|---------|
| `res.partner` | My Partners | CRM/Sales/POS/Website customers |
| `product.product` | My Products | Sales/POS/Website products |
| `res.users` | My User (or hide if self-only UX is odd) | CRM/Sales salesperson — **default: lens_my off** unless clear ownership field |
| `stock.warehouse` | My Warehouses (or off) | warehouse — **default: My off**; **With KPIs** on if graph/KPI data exists |

Wave 1 must ship partner + product fully. Users/warehouse: enable KPIs lens; My only when rewrite is correct.

## Explicitly out of Wave 1

- Reviving `report_sale_stock` / `report_account` / `report_pos_sale` / `report_stock_enterprise` / `report_website_sale`
- Drill-down `search_default_my_sale_orders_filter` / My Quotation / My Invoice on opened lists
- Studio Setup toggles for lens fields
- Team / manager hierarchy “My team” (current user only)
- Per-user persistent “My Pipeline” preference on `res.users`
- Renaming technical fields to `my_partner` / `my_product` (use generic names; labels carry meaning)
- Keeping v1 technical names `with_analytics` / `graph_with_analytics_field` on new v2 code paths

## Wave 2 (documented, not this ship)

1. Card open → **host-scoped** domain on standard `sale` / `stock` / `account` / `point_of_sale` actions (already mostly true).
2. Global report slots only → optional user scope via standard My filters when they exist.
3. Rebuild a *specific* missing analysis filter as a thin view inherit only if customers prove a gap — still not a full `report_*` pack.

## Success criteria

1. Published partner dashboard shows **My Partners** + **With KPIs** when blueprint lens flags are on.
2. Defaults match seed (v1-like: both on for CRM/Sales customers).
3. Toggling My changes visible cards **and** card graphs/KPIs consistently.
4. Toggling **With KPIs** hides hosts with no dashboard data for that blueprint; graphs stay consistent.
5. Opening a non-dashboard partner action is unchanged (no filter pollution without dashboard context).
6. Product host dashboards get My Products with the same engine path.
7. No dependency on the five dropped `report_*` modules.
8. Tests: rewrite domains, action context keys (`show_dashboard_kpis_filter`, `search_default_dashboard_with_kpis`), search arch visibility, required-label constrain when lens enabled, partner + product smoke.

## Non-goals

- Pixel-perfect v1 search XML copy  
- Shell modules `customer_dashboard` / `product_dashboard` as hard depends  
- Free-typed domains in Studio for these two filters  
- Engine auto-default of My / KPIs labels from host model name  

## Implementation notes (for plan)

1. Add `dashboard_my_data` / `dashboard_with_kpis` on `base` (non-stored; rewrite in `search`/`search_fetch` before field search).
2. Blueprint lens fields (`lens_my_*`, `lens_kpis_*`) + form group “Kanban lens” (Advanced).
3. `_upsert_search_view`: create/update `ir.ui.view` with `inherit_id` = host model’s primary search view; xpath-inject the two filters; set `search_view_id` on the generated action.
4. Port domain rewrite from graph mixin into `base` gated by `dashboard_blueprint_key` (map old mixin `graph_with_analytics_field` concepts to `dashboard_with_kpis` on the new path only).
5. Blueprint helpers: `_lens_my_domain()`, `_lens_kpis_host_ids()`; health/constrain: enabled lens ⇒ non-empty label; health when My cannot resolve.
6. Seed **explicit** `lens_my_label` / `lens_kpis_label` on every preset that enables those filters; salesperson/warehouse conservative My defaults.
7. Version bump `dashboard_engine` + `-u` on `:19005`.

## Name map (v1 → v2)

| v1 | v2 |
|----|----|
| UI: With Analytics | UI: **With KPIs** |
| `with_analytics` | `dashboard_with_kpis` |
| `show_with_analytics_filter` | `show_dashboard_kpis_filter` |
| `search_default_with_analytics` | `search_default_dashboard_with_kpis` |
| `graph_with_analytics_field` (dict config) | blueprint `lens_kpis_*` + base field `dashboard_with_kpis` |

## Next steps

1. User reviews this spec.  
2. Implementation plan → `docs/superpowers/plans/2026-07-28-kanban-my-kpis-lens.md`.  
3. Ship Wave 1 on `:19005`.  
4. Wave 2 drill-down polish only after Wave 1 accepted in UI.
