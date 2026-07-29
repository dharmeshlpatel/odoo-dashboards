# Dynamic Action Context Tokens (Option A)

**Date:** 2026-07-28  
**Module:** `dashboard_engine`  
**Status:** Approved (go)  
**Related:** `2026-07-28-restrict-scope-surface-matrix-design.md`, condition `__de__` tokens

## Positioning (one line)

> Any blueprint `action_context` / `primary_action_context` may embed the same `__de__` tokens as domains; the engine resolves them at click time for **any** host model.

## Decision

| Choice | Locked |
|--------|--------|
| Scope | Option **A** only (no search-default mirror, no Studio token UI) |
| Reuse | `condition_domain.is_token` / `resolve_token` |
| Surfaces | Primary button + every slot `_prepare_action` via one helper |
| CRM recipe | `default_type` ← `group_value` (Use Leads → lead, else opportunity) |
| Activities report | Seed static graph context (no tokens required) |

## Context value shape

Literals, `{{id}}`, and nested JSON remain supported. Values may be tokens::

    {"default_type": {
        "__de__": "group_value",
        "default": "opportunity",
        "map": [{"groups": ["crm.group_use_lead"], "value": "lead"}]
    }}

Engine has **no** CRM imports; presets supply groups/defaults as data.

## Non-goals

- Studio editor for tokens  
- Restrict → `search_default_*` mirror  
- Changing View / New / bottom My Pipeline matrix  

## Success

1. Generic test: context token resolves by viewer group on a non-CRM blueprint.  
2. CRM KPI/primary with Use Leads → `default_type=lead`; without → `opportunity`.  
3. Activities report opens with seeded graph groupbys.
