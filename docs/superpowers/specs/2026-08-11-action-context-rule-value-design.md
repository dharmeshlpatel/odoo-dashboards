# Action Context: Set Value by Rule (Group + Card Condition)

**Date:** 2026-08-11  
**Module:** `dashboard_engine`  
**Status:** Implemented (19.0.1.0.232)  
**Related:** `2026-07-29-friendly-action-context-editor-design.md`, `2026-07-28-dynamic-action-context-tokens-design.md`, `2026-08-10-dynamic-selective-action-defaults-design.md`

## Positioning

> When Opened defaults can vary by **user group** or **card condition**, with type-aware Then/Otherwise widgets — without raw JSON.

## Locked titles

| Purpose | Title |
|---------|-------|
| Card pass | Open with this record |
| Search filter | Apply a search filter |
| Form default | Prefill a form field |
| Rules | Set value by rule |

## Token

- Legacy seeds keep `__de__: group_value` with `map: [{groups, value}]`.
- New mixed / card rules use `__de__: rule_value` with:

```json
{
  "__de__": "rule_value",
  "default": "opportunity",
  "map": [
    {"when": {"type": "group", "groups": ["crm.group_use_lead"]}, "value": "lead"},
    {"when": {"type": "record", "domain": "[('country_id.code', '=', 'DE')]"}, "value": "b2b_de"}
  ]
}
```

Studio serializes `group_value` when every rule is group-only (compatible round-trip); otherwise `rule_value`.

## Evaluation

1. First matching rule wins.  
2. `group` → `user.has_group`.  
3. `record` → `record.filtered_domain(domain)` on the clicked host card; skip if no record; empty domain never matches; invalid domain skips with a warning.  
4. Free-form **user domain** is out of scope (v2).

## Studio UX

- When → User group | Card condition (domain dialog on host model).  
- Then use / Otherwise use → boolean / selection / many2one widgets (same as Prefill).  
- Advanced form widget supports the same When types with a domain Char (Studio remains the preferred editor).
