# Friendly Action Context Editor (No JSON for Admins)

**Date:** 2026-07-29  
**Module:** `dashboard_engine`  
**Status:** Shipped (Approach B) · multi-group rules in `19.0.1.0.106`  
**Related:** `2026-07-28-dynamic-action-context-tokens-design.md`

## Positioning (one line)

> Admins edit action context as simple rows (key + value type). The engine still stores and runs `__de__` / `{{id}}` — never shown as raw JSON.

## Product rule (locked)

- Non-technical admins **never** type JSON or `__de__`.
- Surfaces: **Advanced** (primary + slot) **and** **Studio** (same row model).
- Storage stays Char JSON with tokens (portable, runtime unchanged).

## UX rows

| Control | Options |
|---------|---------|
| Context key | Text |
| Value type | **Always the same value** · **This card’s id** · **Depends on the user’s groups** |
| Fixed / Otherwise | Plain text |
| Group rules | Ordered list: search `res.groups` + value; **first matching group wins** |

Multi-group maps: full ordered rule list in both Advanced and Studio. Matches CRM-style `group_value.map` with several entries.

## Technical

- OWL widget `dashboard_context_kv` + shared `context_kv_utils.js`.
- Parse: plain → fixed; `"{{id}}"` / `[{{id}}]` → card id; `__de__: group_value` → group rules.
- Serialize back to shapes `compile_context_value` already resolves.
- `studio_search_groups` / `studio_group_labels` for friendly group names.
- Studio reuses the same serialize/parse helpers; no second storage format.

## Non-goals

- Free-form nested JSON in the UI  
- Seed string DSL (optional later for developers)  
- Changing runtime token resolver  

## Success

1. Admin can set CRM-style `default_type` by group without seeing JSON.  
2. Existing seeded `__de__` contexts round-trip (including multi-entry maps).  
3. Slot Advanced field uses the same widget as primary.  
4. Studio can edit the same context without a raw Char box.
