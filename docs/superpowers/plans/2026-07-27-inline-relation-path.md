# Inline Relation Path Implementation Plan

> **For agentic workers:** Execute task-by-task in this session (inline). Steps use checkbox syntax.

**Goal:** Replace Relation Paths catalog/hops UX with Odoo `field_selector` drill-down on `graph_data_field` / `relate_field` Char paths; keep runtime domain + multi-hop fold behaviour.

**Architecture:** `tools/relation_path.py` owns validate/domain/fold; blueprint/slot resolve an effective dotted path (Char, M2O fallback); UI uses many2one-only field selector; menu hidden; migration copies M2O → Char.

**Tech Stack:** Odoo 19, OWL `field_selector`, Python helper, post migration.

**Spec:** `docs/superpowers/specs/2026-07-27-inline-relation-path-design.md`

## Global Constraints

- Module: `dashboard_engine` under `odoo-dashboards-19.1-v2`
- many2one-only chains; final relation must equal host model
- Reuse `graph_data_field` / `relate_field` (no new Char field names)
- Do not unlink `dashboard.relation.path` records in migration
- UI verify: upgrade + restart `:19005`

## File map

| File | Role |
|---|---|
| `tools/relation_path.py` | Helper + `RelationPathInfo` |
| `models/dashboard_blueprint.py` | Resolve path from Char; validate; call helper |
| `static/src/js/fields/dashboard_relation_path_selector.js` | many2one-only field_selector |
| `views/dashboard_blueprint_views.xml` | Selector UI; hide M2O path |
| `views/dashboard_engine_menus.xml` | Hide Relation Paths menu |
| `migrations/.../post-inline-relation-path.py` | Copy M2O → Char |
| `models/dashboard_blueprint_template.py` | Export/import Char |
| `tests/test_dashboard_blueprint.py` | Char multi-hop tests |

---

### Task 1: Helper + unit behaviour via existing tests

**Files:** Create `dashboard_engine/tools/relation_path.py`; export from `tools/__init__.py` if needed

- [ ] Implement `first_hop`, `is_direct`, `domain_leaf`, `validate_path`, `map_first_hop_to_hosts`, `RelationPathInfo`
- [ ] Wire blueprint `_graph_link_path` / `_slot_link_path` / `_host_domain_leaf` / constraints to Char + helper (M2O fallback)
- [ ] Adapt multi-hop tests to set `graph_data_field="parent_id.country_id"` (keep path helper tests optional)

### Task 2: UI selector + hide catalog

- [ ] Register `dashboard_relation_path` widget (many2one filter, follow_relations)
- [ ] Blueprint form: `graph_data_field` with widget; hide `graph_data_field_id` + `graph_relation_path_id`
- [ ] Slot lists: `relate_field` with widget; hide `relate_field_id` + `relation_path_id`
- [ ] Hide Relation Paths menuitem (`invisible="1"` or active=False)

### Task 3: Migration + templates + ship

- [ ] `post-inline-relation-path.py`: M2O domain_field → Char; clear M2Os
- [ ] Template export/import prefer Char; accept legacy path blob
- [ ] Bump `__manifest__.py`; upgrade DB; restart `:19005`
