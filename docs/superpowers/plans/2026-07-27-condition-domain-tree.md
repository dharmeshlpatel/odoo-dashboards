# Condition Domain Tree Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Make dashboard conditions compile from a portable domain-tree JSON with typed runtime tokens, supporting nested AND/OR/NOT for any Odoo model, while keeping the existing rules O2M as the simple editor that syncs into the tree.

**Architecture:** `domain_tree` (Json) is the compile source of truth. Rules remain the layman editor and rebuild the tree on change. `to_domain(record)` walks the tree and resolves `__de__` tokens at render time. No `safe_eval` of arbitrary Python.

**Tech Stack:** Odoo 19, `fields.Json`, existing `dashboard.condition` / `rule` models.

**Token key:** `__de__` (dashboard engine)

## Token grammar

| Token | Shape | Resolves to |
|---|---|---|
| uid | `{"__de__":"uid"}` | `env.uid` |
| company | `{"__de__":"company"}` | `env.company.id` |
| company_ids | `{"__de__":"company_ids"}` | `env.companies.ids` |
| false / true | `{"__de__":"false\|true"}` | `False` / `True` |
| record | `{"__de__":"record"}` | card id(s); skipped if no record |
| relative_date | `{"__de__":"relative_date","when":"today\|now\|…","days":N}` | date/datetime string |
| group_value | `{"__de__":"group_value","default":…,"map":[{"groups":[xmlid],"value":…}]}` | first matching group value |

Literals (int/str/bool/list) stored as-is.

## Tasks

- [x] RFC (this doc)
- [x] `tools/condition_domain.py` compiler + rules→tree builder
- [x] `domain_tree` field; `to_domain` prefers tree; sync from rules
- [x] Migration `19.0.1.0.61` backfill trees
- [x] Export/import `domain_tree`
- [x] Form: Technical page shows domain tree
- [x] Tests: nested tokens, rules sync, overdue seed still works
- [x] Bump version, upgrade, run tests
