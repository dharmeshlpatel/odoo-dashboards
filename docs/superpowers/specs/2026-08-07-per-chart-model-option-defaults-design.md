# Per-Chart-Model-Option defaults (Group By / Measure / Data to Include)

**Date:** 2026-08-07
**Module:** `dashboard_engine`
**Status:** Implemented (19.0.1.0.192) — options-only UX
**Scope:** Group By, Measure, Measured As, and default Data to Include ticks are managed **only** on each Chart Model Option (`dashboard.blueprint.graph.variant`), even when there is a single chart model. Blueprint fields remain as a mirror of the Default option for older packs / code paths. Include **scope definitions** (name/domain) stay on the blueprint.

## Problem

Today Group By / Measure / Measured As / Data to Include live only on the blueprint (and mirrored per-user in `dashboard.user.pref`). A Chart Model Option (variant) only stores the model + link-to-host + primary button. When a user switches Chart Model in the gear:

- `dashboard.user.pref._clear_stale_graph_fields()` drops any Group By / Measure field that does not exist on the new model.
- `_effective_graph_settings()` then falls back straight to the **blueprint's single shared default**, which was written for whichever model the builder had in mind first — usually wrong for the other model.

Data to Include scopes already self-filter per model (`_domain_applies_to_model`), so irrelevant tick boxes correctly disappear — but *which of the remaining boxes are ticked by default* is still one global `default_on` per scope, not per chart model.

## Goal

A builder configuring "Opportunities" and "Leads" as two Chart Model Options on one dashboard should be able to say: *"On Opportunities, group by Stage and measure Expected Revenue, with Pipeline ticked; on Leads, group by Source and count records, with New Leads ticked"* — without maintaining two separate dashboards.

## Out of scope

- Per-variant KPI / bottom-slot configuration (slots already have their own `compute_model_id`, independent of the chart).
- Changing how scopes are *filtered* per model (`_domain_applies_to_model` already does this correctly).
- Any change to `dashboard.user.pref`'s own per-user override — a user's personal picks still win over both variant and blueprint defaults, exactly as today.

## Design

### Precedence chain

```
blueprint default  →  variant default (if this option configured one)  →  user pref (if set & valid on current model)
```

Existing blueprints are unaffected: a variant with everything empty behaves exactly as it does today (falls straight through to the blueprint default).

### 1. Group By / Measure / Measured As — new fields on `dashboard.blueprint.graph.variant`

```python
default_measure_field_id = fields.Many2one(
    "ir.model.fields", string="Default Measure", ondelete="set null",
    domain="[('model_id', '=', graph_model_id), "
           "('ttype', 'in', ['integer', 'float', 'monetary']), ('store', '=', True)]",
)
default_measure_aggregator = fields.Selection(AGGREGATORS, string="Default Measured As")
default_groupby_ids = fields.Many2many(
    "ir.model.fields", "dashboard_graph_variant_groupby_rel",
    "variant_id", "field_id", string="Default Group By",
    domain="[('id', 'in', graph_groupby_allowed_field_ids)]",
)
default_ordered_groupby_ids = fields.Char()
graph_groupby_allowed_field_ids = fields.Many2many(
    "ir.model.fields", compute="_compute_graph_groupby_allowed_field_ids",
)  # same dashboard_groupby_allowed_fields(graph_model) helper already used on the blueprint
```

All nullable, same "unified ordered tag list" pattern already used by `dashboard.blueprint.graph_groupby_ids` / `ordered_graph_groupby_ids` and by `dashboard.user.pref.groupby_ids` — reuses `_parse_ordered_field_ids`, `compute_many2many_order`, and a `_groupby_all_specs()` / `_measure_spec()` pair mirroring the ones already on `dashboard.blueprint` and `dashboard.user.pref`.

**Resolution change**, inside `_effective_graph_settings()` (single choke point, no other call site touched):

```python
variant = self._effective_graph_variant()
...
if variant and variant.default_groupby_ids:
    v_specs = variant._groupby_all_specs()
    settings["groupby"], settings["groupbys"] = v_specs[0], v_specs
if variant and variant.default_measure_field_id:
    settings["measure"] = variant._measure_spec()
# ... then pref overrides apply on top, unchanged
```

`dashboard.user.pref._clear_stale_graph_fields()` needs **no change** — once a stale pref field is cleared, `_effective_graph_settings()`'s existing `if pref._ordered_groupby_fields() and specs:` guard already falls through to whatever `settings` holds at that point, which will now be the variant's own default instead of the blueprint's.

### 2. Data to Include — default tick-set per variant

New field on `dashboard.blueprint.graph.variant`:

```python
default_scope_ids = fields.Many2many(
    "dashboard.blueprint.scope", "dashboard_graph_variant_scope_rel",
    "variant_id", "scope_id", string="Default Data to Include",
    domain="[('blueprint_id', '=', blueprint_id), ('mode', '=', 'include')]",
)
```

Empty (the common case) = "use each scope's own `default_on`," identical to today. When non-empty, it is the exact tick-set applied for that variant instead of `scope_ids.filtered("default_on")`.

**Resolution changes** in the two places that currently read `scope_ids.filtered("default_on")`:

- `_default_pref_values()` (seeds a fresh `dashboard.user.pref` row) — use `variant.default_scope_ids or self.scope_ids.filtered("default_on")` for the *effective* variant at creation time.
- `_effective_graph_settings()`'s no-pref branch (`defaults = self.scope_ids.filtered("default_on")`) — same substitution.

Restrict-mode scopes ("My Data") are **not** included here — those stay a personal, per-user tick (`dashboard.user.pref.scope_ids` for `mode == "restrict"`), never a builder-set default per model, consistent with how "My" filters work everywhere else in the engine.

### 3. Studio UI

Inside each Chart Model Option row (Configuration → Chart Model Options), an optional, collapsed **"Defaults for this model"** panel — hidden until the row has a `graph_model` chosen:

- Group By tags (reuses `dashboard_groupby_tags` widget, catalog from `studio_groupby_fields(variant.graph_model)`)
- Measure + Measured As (reuses `studio_model_fields(variant.graph_model, numeric, stored_only=True)`)
- Data to Include checkboxes, scoped to `scope_ids` whose domain already applies to `variant.graph_model` (reuse `_domain_applies_to_model`)

Collapsed by default so single-chart-model dashboards (the majority) see no new UI at all.

### 4. Advanced form

Same three field groups added to the `graph_variant_ids` list as `optional="hide"` columns, domains scoped to that row (`graph_model_id` / `graph_model`), matching the pattern already used for `primary_action_id` on that same list.

## Data model summary

| Model | Change |
|---|---|
| `dashboard.blueprint.graph.variant` | New: `default_measure_field_id`, `default_measure_aggregator`, `default_groupby_ids`, `default_ordered_groupby_ids`, `default_scope_ids`, `graph_groupby_allowed_field_ids` (compute) |
| `dashboard.blueprint` (`_effective_graph_settings`) | Insert variant-default layer between blueprint default and pref override |
| `dashboard.blueprint` (`_default_pref_values`) | Seed `scope_ids` from `variant.default_scope_ids` when set |

No changes to `dashboard.user.pref` fields or its stale-field clearing logic.

## Security

No new groups or record rules. New fields follow the same access as the rest of `dashboard.blueprint.graph.variant` (Studio/manager write, internal user read) — no new model, no new relation to secure beyond the two new relation tables.

## Testing considerations

- Blueprint with one variant, no defaults set on it → chart settings identical to current behavior (regression guard).
- Two variants (e.g. `crm.lead` filtered to won vs. all): each with its own `default_groupby_ids`/`default_measure_field_id` → switching the gear's Chart Model picker changes Group By/Measure to that variant's configured values, not the blueprint's.
- User has a personal pref Group By valid on both models → pref wins over both variant and blueprint defaults on every model switch (precedence unchanged at the top).
- User has a personal pref Group By valid only on the previous model → switching model clears the stale pref field and falls back to the **new model's variant default** (not blank), the core UX fix.
- `default_scope_ids` set on a variant with two include-scopes, only one ticked → a fresh `dashboard.user.pref` for that variant seeds with only that one ticked; a variant without `default_scope_ids` still seeds from each scope's own `default_on`.
- Restrict-mode ("My Data") scopes are unaffected by `default_scope_ids` — remain a pure per-user pref choice.

## Risks

- Adds two new relation tables and ~6 fields to an already large model (`dashboard.blueprint.graph.variant`) — mitigated by keeping everything optional/nullable and off the critical path when unset.
- Studio gets one more (collapsed) panel per chart-model row — needs care to stay hidden for the common single-model case so it doesn't read as new required configuration.
- `_effective_graph_settings()` is a hot path (evaluated per render); the added variant lookups are in-memory recordset reads (no extra queries beyond what `_effective_graph_variant()` already fetches), so no expected performance regression.

## Success criteria

- A dashboard with two Chart Model Options can have independently useful Group By/Measure/Include defaults, with zero configuration required for dashboards that only ever use one chart model.
- Switching Chart Model in the gear never leaves Group By/Measure looking "wrong" for the newly selected model when the builder took the time to configure that model's option.
- No behavior change for any existing blueprint until a builder explicitly opens a variant row's "Defaults for this model" panel and sets something.
