# Restrict Scope (“My Pipeline”) — Surface Matrix

**Date:** 2026-07-28  
**Module:** `dashboard_engine` (+ CRM / Sales presets)  
**Status:** Approved (product + architect dialogue)  
**Related:** `2026-07-28-kanban-my-kpis-lens-design.md`, `2026-07-28-dynamic-graph-config-studio-design.md`  
**Does not revive:** `res.users` `customer_dashboard_my_pipeline`, per-slot `conditional_domain` / `search_defaults.my_pipeline`

## Positioning (one line)

> Gear **My Pipeline** (restrict scope) shapes only the **dashboard panel** — graph, primary graph button, and right KPIs — not bottoms or any Manage menu.

## Product rule (locked)

> **My Pipeline** = “my numbers on this card.”  
> **Bottoms + menus** = “open the app for this customer” — partner/action context only, never inherit restrict.

Kanban lens **My Partners** stays a separate control (which host cards). Do not merge with gear My Pipeline.

## Surface matrix (locked)

| Surface | Inherit restrict scope? |
|---------|-------------------------|
| Graph data | **Yes** |
| Primary graph action button | **Yes** |
| Right KPIs (`section=kpi`) — count and click | **Yes** (when slot compute/action model is the blueprint graph model) |
| Bottom smart buttons (`section=bottom`) | **No** |
| Menu views (`menu_views`) | **No** |
| Menu new (`menu_new`) | **No** |
| Menu reports (`menu_reports`) | **No** |

Deliberate vs v1: reports and same-model bottoms no longer follow the My boolean. Views / new already did not in v1.

## Architecture

- Single source of truth: blueprint **restrict** scopes (e.g. `scope_crm_mine`), via user prefs ticks.
- Include scopes (Pipeline / Leads) stay **graph-only** (unchanged).
- Domain is authoritative on Yes surfaces. Optional `search_default_*` mirror is polish only — never instead of domain.
- Do **not** re-add per-slot `conditional_domain` / `search_defaults` for “mine”.

## Engine follow-up

**Done (19.0.1.0.103):** `_honours_restrict_scope()` — restrict applies only when
`section == 'kpi'` and `compute_model == graph_model`. Bottoms and Manage
menus never inherit restrict.

Tests: `test_only_mine_scope_narrows_crm_kpi_count_and_action`,
`test_only_mine_scope_skips_bottom_and_menu_slots`.

## Non-goals

- Reviving `customer_dashboard_my_pipeline` on `res.users`
- Passing My into View / New / Reports for v1 parity
- Treating bottoms as a second KPI strip under My

## Success criteria

1. My on → graph, primary button, right KPIs agree on “mine”.  
2. My on → bottoms and all menus unchanged vs My off (aside from unrelated partner domain).  
3. Spec cited by future agents before “fixing” My onto reports or bottoms.
