# Dynamic Selective Action Defaults (No Free Typing)

**Date:** 2026-08-10
**Module:** `dashboard_engine`
**Status:** Proposed — spec for next implementation pass
**Related:** `2026-07-29-friendly-action-context-editor-design.md`, `2026-07-28-dynamic-action-context-tokens-design.md`

## Positioning (one line)

> "When Opened" rows must never ask an admin to *type* a filter name, field name, or model name — every choice is a dropdown built from the real target model, resolved live from the action the admin already picked.

## Problem (from user feedback)

Current **230** UI (purpose-based rows: card-pass / list filter / form default / role value) is friendlier than raw JSON, but three inputs are still free text:

1. **Filter name** — admin types `my_pipeline`, `assigned_to_me`.
2. **Form field** — admin types `partner_id`, `type`.
3. **Group-rule field** (role value) — same as above.

This is still "technical" because the admin must know the exact internal name and it can typo/break silently.

## Decision (locked)

| Choice | Locked |
|---|---|
| Resolve a **target model** per row's owning action, then query it live | Yes — no more guessing |
| Filter name → `<select>` of real `<filter>` entries from that model's search view | Yes |
| Form field / role field → `<select>` of real fields (`fields_get`), grouped by type | Yes |
| Value for the picked field → type-aware widget (selection dropdown, Yes/No, record search, text) | Yes |
| Card-pass target (`active_id` etc.) | Already a select — unchanged |
| When target model can't be resolved (custom method, no action chosen yet) | Fall back to text input + inline hint, never block |
| Legacy free-typed rows (existing data) | Keep rendering as "Custom setting" (already shipped) — no migration forced |
| Saved/user `ir.filters` as a source for the filter dropdown | **Non-goal v1** — only search-view `<filter>` nodes (deterministic, no per-user clutter) |

## Target model resolution (the key piece)

Every "When Opened" row belongs to one action config: the **primary action** editor or a **slot** editor. Each already has enough to resolve a model, in this order:

1. `action_xmlid` set → look up that window action's `res_model` (new tiny RPC, see below).
2. `action_method` set (custom host method) → target model is **unknown** until run time. Treat as unresolved (fall back to text + hint: *"Custom method — can't auto-detect fields"*).
3. Neither set → use the editor's own model: `compute_model` (slot) or `host_model_name` (primary/payload).

This mirrors the pattern already used for `openDomainEditor` / `openGraphDomainEditor` in `dashboard_studio_action.js` (`resModel = editor.compute_model || payload.host_model`), so it is a one-line addition, not a new concept.

## Backend additions (`dashboard_blueprint.py`)

All follow the existing `studio_*` RPC style (`ensure_one`, small limits, plain dicts/lists — see `studio_model_fields`, `studio_search_actions`).

1. `studio_resolve_action_model(action_xmlid)` → `{"res_model": "sale.order"}` or `{"res_model": False}`.
   Reuses `ir.actions.act_window` lookup already done inside `studio_search_actions`.

2. `studio_action_search_filters(model_name)` → list of `{"name": "my_pipeline", "string": "My Pipeline"}`.
   Parse the model's default `search` view arch (`get_view(model_name, view_type="search")`), collect `<filter>` nodes that have a `name` attribute (skip separators / groups without `name`), dedupe by name, sort by `string`.

3. Extend `studio_model_fields` (non-breaking): when `ttype == "selection"`, include `"selection": [[value, label], ...]` from `fields_get()[name]["selection"]` so the value widget can render a dropdown without a second round trip. Also drop `ttype == "one2many"` from results here (can't hold a scalar default) unless a caller explicitly asks via `ttypes`.

4. `studio_search_records(model_name, term="", limit=8)` → thin wrapper around `name_search` for many2one/many2many "fixed value" pickers, guarded the same way `studio_search_actions` guards `res_model` (must exist in `self.env`, not transient).

## Frontend additions

**`context_kv_utils.js`**
- `resolveActionTargetModel({ action_xmlid, action_method, compute_model, host_model })` → returns model name or `null`. Pure JS, no RPC (RPC happens in the component so it can cache/await).

**`dashboard_studio_action.js`**
- Per-editor cached catalogs (mirrors existing `variantDefaultsCatalogs` pattern):
  - `state.actionFieldsCatalog[model]`
  - `state.actionFilterCatalog[model]`
- `contextTargetModel()` — computed from current editor (primary or slot, whichever is open).
- `contextFieldOptions()` / `contextFilterOptions()` — lazy-load via the new RPCs, keyed by `contextTargetModel()`, `await`ed once and cached.
- Rewire the three existing handlers (`onContextSearchFilterName`, `onContextFormFieldName`, `onContextGroupSettingName`) to accept a **selected value from a `<select>`** instead of a typed string — logic (`toSearchFilterKey` / `toFormDefaultKey`) stays the same, only the DOM control changes.
- New: `onContextFixedValueForField(row, fieldMeta, ev)` — renders Yes/No for boolean, `<select>` for selection (using the field's own `selection` list), search-and-pick list for many2one/many2many (reuse the exact search-hit list markup already used for group rules — `getContextGroupHits` / `pickContextGroup` pattern), else plain text.

**XML (`dashboard_studio_action.xml`, both Primary and slot blocks)**
- `search_filter` purpose: `<select>` populated by `contextFilterOptions()`; if target model unresolved, show a small hint and keep the current text input as fallback.
- `form_default` / `group_setting` purpose: field `<select>` populated by `contextFieldOptions()`; value control switches on the picked field's `ttype` per the rules above.
- Loading state: while a catalog RPC is in flight, disable the row's selects and show "Loading fields…" (small `form-text`, no spinner needed).
- Unresolved-model state: hint text "Pick an Action above first" instead of a disabled empty select.

## Non-goals (v1)

- `ir.filters` (saved/user filters) as a filter-name source.
- Domain-level defaults (that's the existing `openDomainEditor` — out of scope here).
- Auto-detecting the model behind a custom `action_method` (would require executing it).
- Date-specific value pickers (relative date presets) for prefill/role values — keep plain text for date/datetime fields in v1.

## Implementation order (for the agent that builds this)

1. Backend: add the 3 new/extended `studio_*` methods above. Unit-test `studio_action_search_filters` against a model with a known filter (e.g. `crm.lead` → `assigned_to_me`).
2. `context_kv_utils.js`: add `resolveActionTargetModel`.
3. `dashboard_studio_action.js`: add cached catalogs + `contextTargetModel/contextFieldOptions/contextFilterOptions`; rewire the three handlers to selects; add the type-aware value control handler.
4. XML: swap the three text inputs (filter name, form field, group-setting field) for selects in **both** Primary and slot blocks; add the type-aware value control for form-default `fixedValue` and group-rule `value`.
5. Bump `__manifest__.py` version, restart `:19005` with `-u dashboard_engine`, smoke test on two different target models (e.g. a CRM lead card and a Sales order card) to confirm the dropdowns list real filters/fields for each, and that switching Action changes the options.

## Success

1. Picking "Turn on a list filter" on a CRM-model card shows a dropdown with real filter names (`assigned_to_me`, …), not a text box.
2. Picking "Prefill a form field" shows a dropdown of that model's real fields; picking a `selection` field shows its real option labels, not free text.
3. Switching the row's Action (different `action_xmlid`) refreshes the field/filter options to match the new target model.
4. Legacy rows with typed keys that don't match any known field/filter still open (as "Custom setting") — nothing breaks for existing blueprints.
