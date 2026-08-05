# Implementation Plan — Panel Filters, Linked My & Smart Maps

**Date:** 2026-08-03  
**Spec:** [2026-08-03-panel-filters-linked-my-and-smart-maps-design.md](../specs/2026-08-03-panel-filters-linked-my-and-smart-maps-design.md)  
**Module:** `dashboard_engine` (+ CRM/Sales seeds)

---

## Ship rule

> **Sprint 1 = Phase 0 + Phase 1 only.**  
> Later phases reuse the same map plumbing. Do not boil the ocean.

---

## Phase 0 — Foundation & honesty

- [x] Shared slots use **viewer** blueprint prefs for My (`_panel_viewer` / `_slot_panel_domain`)
- [x] `_lens_kpis_host_ids` / attention use full `_effective_graph_settings()["domain"]`
- [x] Configuration popup redesign (Odoo-style titles + guiding help)
- [x] My label “…and Sales Orders” only when sale + share link / map active
- [x] Tests: viewer My on borrowed Sales KPI; lens domain parity

**Done when:** Linked Sales KPI follows CRM My tick; With KPIs matches chart filters; gear popup sections are clear.

---

## Phase 1 — Cross-model My map

- [x] Add `dashboard.blueprint.scope.target` (o2m on restrict scope)
- [x] Fields: target_model, domain, module_depends, apply_kpi/bottom/views/reports, apply_menu_new (defaults only)
- [x] Seed CRM Customers My → crm.lead + sale.order
- [x] Apply via viewer prefs + map; `_domain_applies_to_model` fail-open
- [x] Mapped domain still runs under the **target model's own record rules / `company_id`** — no `sudo()` shortcut
- [x] Mapped slot queries reuse the existing page-batched pattern
- [x] Cache resolved target maps per blueprint (request cache)
- [x] New: assignee defaults only
- [x] Tests: mapped bottom/views; Meetings unmapped untouched
- [x] Update gear popup help text for linked Sales when map active

**Done when:** Product B′ My works for CRM↔Sales commercial surfaces, safely across companies, and the gear help text matches what really happens.

---

## Phase 2 — Panel filter pack

- [x] API: panel domain = period + custom + My (include scopes stay chart-only)
- [x] Period field mapping on targets (seed date_order)
- [x] Apply to mapped KPI/bottom/views/reports
- [x] Custom Filter: same-name+ttype only; else skip
- [x] Log/trace when a leaf or map is skipped
- [x] Tests: gear period → Sales Orders bottom by date_order

---

## Phase 3 — Smart link & Graph Model picker

- [x] On share_link write: auto-accept high-confidence maps
- [x] Studio + Advanced editor for target maps
- [x] Studio “Suggest maps” ranked list (`studio_suggest_scope_targets`)
- [x] Label honesty gate (Sales wording needs link + map)
- [x] Graph Model picker bundle (variant model + pref selector + primary button swap)

---

## Phase 4 — Odd surfaces (Studio when-My)

- [x] Slot flags: `panel_follow_my` / `panel_follow_filters`
- [x] Studio/Advanced columns on KPI + bottom lists
- [x] Meetings seed: Follow My + calendar.event map / action model
- [x] Partner short doc

---

## Phase 5 — Polish

- [x] Reuse one `read_group` when slots share the same fingerprint (model/link/domain/aggregates)
- [x] Cache Hub action + view metadata client-side per blueprint
- [x] More preset maps (invoice + calendar; website uses sale.order)
- [x] Label honesty / auto-composed via scope.label + maps
- [x] In-app / partner help
- [x] Chart model picker visible in Configuration (Many2one under Graph Configuration)

---

## Risk register

| Risk | Mitigation |
|------|------------|
| Crash on bad domain | `_domain_applies_to_model` + fail-open |
| Cross-model map leaks data across companies | Record rules always applied on target model |
| Chart model changes but primary button stays on the old model | Graph Model picker requires a matching variant |
| Hub menu with many 360-style dashboards feels slow | Client-side action/view cache per blueprint |
| Cross-model maps double query count | Page-batched `read_group` + map cache |
| Wrong delivery date field | No silent auto; seed or Studio |
| End user forced into Studio | Seeds + auto-link Phase 3 |
