# Inline relation path (ModelFieldSelector) — design

**Date:** 2026-07-27  
**Module:** `dashboard_engine`  
**Status:** Implemented (19.0.1.0.72)  
**Decision:** Approach **A+** (approved in chat)

## Goal

Replace the confusing **Relation Paths** catalog + hop Steps list with an
Odoo-standard **field drill-down** (same idea as search/domain:
`Order Line → Product → Category`).

Runtime behaviour stays the same: a many2one chain from the aggregated
model back to the kanban card, used for domains and multi-hop
`read_group` folding.

## Problem

Today there are two ways to link chart/KPI data to a card:

| Mechanism | UI | Example |
|---|---|---|
| `graph_data_field` / `relate_field` | Single many2one name | `partner_id` |
| `graph_relation_path_id` / `relation_path_id` | Named path + O2M hops | `product_id` then `categ_id` |

Seeds almost always use the Char field. Multi-hop needs the catalog, which
forces users to maintain a second master-data form. That catalog is the
confusion — not the dotted path itself.

## Target behaviour

1. On blueprint (graph) and on KPI/stat slots, one control:
   **ModelFieldSelector** rooted at the chart/compute model.
2. User drills only through **many2one** links until the chain lands on
   the **card (host) model**.
3. Stored value is a Char dotted path: `partner_id` or `product_id.categ_id`.
4. Empty slot path → inherit blueprint graph path (same rule as today).
5. Relation Paths **menu is hidden**; hop model kept only as a migration
   bridge for one version, then removable.

## Non-goals

- No change to KPI/graph aggregation math beyond how the path is loaded.
- No named reusable path catalog in v1 of this change (revisit only if
  many blueprints truly share one edited-once path).
- No support for x2many hops (same constraint as today).

## Data model

### Canonical store

| Record | Field (Char) | Meaning |
|---|---|---|
| `dashboard.blueprint` | `graph_data_field` (extended) | Dotted many2one path from `graph_model` → host |
| `dashboard.blueprint.slot` | `relate_field` (extended) | Dotted path from slot compute model → host; empty = inherit blueprint |

Optional display label (computed, not stored): human path string for list views.

### Deprecated (bridge)

| Field | After migration |
|---|---|
| `graph_relation_path_id` | Copy `domain_field` → `graph_data_field` if Char empty; then clear M2O |
| `relation_path_id` | Same → `relate_field` |
| `dashboard.relation.path` / `.hop` | Menu hidden; models remain until a later cleanup version |
| Relation Paths menuitem | Invisible / removed from menu |

### Why reuse `graph_data_field` / `relate_field`

They already mean “link to the card”. Extending them to dotted paths
avoids a third field and matches seed XML already in tree.

## Runtime helper

New module tool (preferred location):

`dashboard_engine/tools/relation_path.py`

| API | Role |
|---|---|
| `validate_path(env, source_model, path, target_model)` | many2one-only; last relation == target |
| `domain_leaf(path, host_ids)` | `(path, 'in'\|'=', ids)` |
| `first_hop(path)` | first segment for `read_group` |
| `is_direct(path)` | single segment |
| `map_first_hop_to_hosts(env, source_model, path, host_ids)` | move logic from `dashboard.relation.path` |

Blueprint/slot code that today does `_graph_link_path()` / `path.domain_leaf`
switches to this helper + the Char field (no M2O required).

`_graph_link_path()` can become a thin adapter that builds a simple
namespace/dict from the Char for minimal call-site churn, or call sites
are updated directly to the helper — prefer **direct helper** for clarity.

## UI

### Blueprint — Dashboard behaviour (graph)

- Keep model picker for graph model.
- Replace “Relation Path” M2O + dual “Data field” where redundant with
  **one** ModelFieldSelector bound to `graph_data_field`, `resModel` =
  graph model.
- Help text: “Drill into related records until you reach this card’s model.”
- Validate on save: path ends on `host_model_name`.

### Slot form

- Same selector on `relate_field`, `resModel` = slot compute model
  (fallback blueprint graph model).
- Placeholder / empty: “Use blueprint chart link”.

### OWL

- Prefer stock `ModelFieldSelector` / a small Char field widget wrapping it
  (pattern similar to domain path editors), restricted via
  `followRelations` / field filter to **many2one** only if the API allows;
  otherwise validate on the server (source of truth).

### Relation Paths app

- Remove or hide menuitem under Dashboard Engine.
- Form may remain for support/debug until model cleanup.

## Migration

Version bump on `dashboard_engine` (next minor after current).

`migrations/<version>/post-inline-relation-path.py`:

1. For each blueprint with `graph_relation_path_id`: if M2O is set,
   set `graph_data_field = path.domain_field` (**M2O wins** when both
   were filled — path was the explicit multi-hop config).
2. Same for slots (`relation_path_id` → `relate_field`).
3. Clear the M2O fields after copy so the form shows one source of truth.
4. Do **not** unlink path records in this step (safe rollback / audit).

## Export / import (templates)

- Export Char path string under existing keys (prefer `graph_data_field` /
  `relate_field`); stop requiring nested `graph_relation_path` hop JSON
  for new exports.
- Import: if legacy `graph_relation_path` blob present, compile
  `domain_field` into Char; if Char present, use it.

## Constraints & errors

- Path required for graph when graph model ≠ host model (same product
  rule as today when a link is needed).
- Non-many2one segment → `ValidationError`.
- Final `relation` ≠ host model → `ValidationError` (same message intent
  as current hop check).
- Missing field after module uninstall → soft-fail in mapping (log), hard
  fail on write/validate when field defs are available.

## Testing

- Direct: `partner_id` domain + graph.
- Multi-hop: `product_id.categ_id` domain + first-hop fold map.
- Slot inherits blueprint Char when `relate_field` empty.
- Slot override wins when set.
- Migration copies M2O `domain_field` into Char.
- Template round-trip with Char only.
- Invalid end model blocked on save.

## Rollout

1. Helper + Char validation + wire runtime (M2O still works as fallback).
2. UI selector; hide catalog menu.
3. Migration copies data; clear M2Os.
4. Later version: delete `dashboard.relation.path` models if unused.

## Out of scope / later

- Named path library (Approach B) if product proves heavy reuse.
- Dropping bridge models.
- x2many / mixed path types.
