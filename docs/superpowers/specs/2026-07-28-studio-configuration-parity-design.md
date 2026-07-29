# Studio Configuration Parity — Scopes, Link to Host, Group By, Measure

**Date:** 2026-07-28  
**Module:** `dashboard_engine` (odoo-dashboards-19.1-v2)  
**Status:** Approved (design dialogue)  
**Depends on:** Dynamic Graph Config Studio (`2026-07-28-dynamic-graph-config-studio-design.md`) shipped for labels + Char/select promote  
**Related:** Advanced Configuration page in `dashboard_blueprint_views.xml`; Studio zone `config` in `dashboard_studio_action`

## Positioning (one line)

> Studio **Configuration** matches Advanced for day-to-day graph setup: full scopes, nested Link to Host, multi Group By, selective Measure — without embedding the Advanced form.

## Problem

Studio Configuration today is thinner than Advanced:

| Control | Studio today | Advanced |
|---------|--------------|----------|
| Scopes | Default-on toggle only | Full list: add / name / mode / domain / default |
| Link to Host | Plain Char | Nested `dashboard_relation_path` |
| Include child | Separate checkbox below | Near the link field |
| Group By | Single `<select>` | Many2many tags (`graph_groupby_ids`) |
| Measure | Free-text Char | Field picker + aggregator |

Admins who live in Studio still bounce to Advanced for real configuration.

## Decision (locked)

| Choice | Decision |
|--------|----------|
| Product shape | **Studio-native UI + RPCs** mirroring Advanced (Approach 3) |
| Rejected | Embed Advanced form (dual chrome); mount raw OWL field widgets without Studio glue (fragile) |
| Scopes depth | **A — full parity**: Add / edit / remove / reorder; name, description, mode, domain, default |
| Scope label variants | **Out** this pass (stay Advanced) |
| Graph Model in Configuration | **Read-only** summary (change stays Setup / Advanced) |
| Technical fields | **No renames** (`graph_data_field`, `graph_groupby_ids`, `scope_ids`, …) |
| Labels | Keep locked: **Link to Host**, **Graph Title**, **Custom Filter**, **Group By**, **Measure** |

This **supersedes** the earlier matrix line that left “full scope CRUD in Studio” to Advanced only (`2026-07-28-dynamic-graph-config-studio-design.md`).

## Configuration zone layout

1. **General Settings** — scopes (full CRUD)  
2. **Graph Configuration** — Graph Model (ro), Link to Host + Include child (same row), Graph Title, Group By, Measure (+ aggregator when needed)  
3. **Filters** — Creation Date / Closed Date / Custom Filter (keep current promote)

## Spec by control

### 1. Scopes (General Settings)

| Studio control | Blueprint | Notes |
|----------------|-----------|--------|
| Ordered list | `scope_ids` | Handle reorder → `sequence` |
| Name | `name` | Required |
| Description | `description` | Optional |
| Mode | `mode` | `include` / `restrict` |
| Domain | `domain` | Dialog or Char; validate with `_safe_domain(..., strict=True)` on write |
| Default | `default_on` | Boolean |

**RPCs (extend / add):**

- `studio_write_scope` — whitelist: `name`, `description`, `mode`, `domain`, `default_on`, `sequence` (not only `default_on`)  
- `studio_create_scope` — create on blueprint; return payload + `created_scope_id`  
- `studio_unlink_scope`  
- `studio_reorder_scopes(ordered_ids)` — same pattern as headers/slots  

**Payload:** each scope includes `id`, `name`, `description`, `mode`, `domain`, `default_on`, `sequence`.

### 2. Link to Host (nested) + Include child

| Studio control | Blueprint | Notes |
|----------------|-----------|--------|
| Nested path builder | `graph_data_field` | Step picker on graph model (M2O hops); display path string; save Char |
| Include child records | `include_child_records` | Checkbox **beside** Link to Host (same row) |

Reuse Advanced semantics (relation path), not necessarily the form widget class — Studio catalogs / RPC for relation fields at each hop is enough.

### 3. Group By (Many2many)

| Studio control | Blueprint | Notes |
|----------------|-----------|--------|
| Multi ordered tags/select | `graph_groupby_ids` + `ordered_graph_groupby_ids` | First = top level; same storage as Advanced |

Payload exposes ordered field ids/names for hydrate. Whitelist write accepts ordered id list (or existing groupby write helpers).

### 4. Measure (selective)

| Studio control | Blueprint | Notes |
|----------------|-----------|--------|
| Measure field | `graph_measure_field_id` / `graph_measure` | Select: Count (`__count`) or stored integer/float/monetary on graph model |
| Aggregator | `graph_measure_aggregator` | Visible when a field (not Count) is chosen |

Replace free-text-only Measure input.

## Out of this pass

| Item | Why |
|------|-----|
| Scope `label_ids` variants | Advanced remains |
| Change Graph Model in Configuration | Setup / Advanced |
| Embed Advanced form / mount form widgets raw | Rejected approach |
| `graph_data_scope.warning` as editable field | Still Accept |
| Pixel-perfect clone of Advanced CSS | Behavior parity first |

## Success criteria

- CRM Customers Studio → Configuration: add a scope with domain; reorder; remove — persists after Save/reload  
- Link to Host: build nested path; Include child on same row; persists  
- Group By: pick 2+ fields; order preserved  
- Measure: pick field + aggregator (or Count); no raw `__count` typing required  
- Advanced form still shows the same values  
- `:19005` upgraded; login 200; hard-refresh assets  

## Ship notes

- Tests: scope CRUD RPCs; groupby/measure/link writes via Studio whitelist  
- Commit only when the user asks  
- Bump `dashboard_engine` version on ship; restart `:19005` with `-u dashboard_engine --dev=xml,assets`
