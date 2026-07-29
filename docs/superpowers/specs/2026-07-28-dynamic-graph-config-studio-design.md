# Dynamic Graph Config — Blueprint + Studio (Odoo-standard labels)

**Date:** 2026-07-28  
**Module:** `dashboard_engine` (odoo-dashboards-19.1-v2)  
**Status:** Approved (matrix locked — implementation Tasks 1–3, 6)  
**Related:** `2026-07-28-dashboard-studio-setup-design.md`, `2026-07-28-kanban-my-kpis-lens-design.md`, plan `2026-07-28-dynamic-graph-config-studio.md`

## Positioning (one line)

> v1 `_CRM_DASHBOARD_GRAPH_CONFIG` (and peer sales dicts) is a **checklist only** — blueprint + Studio carry dynamic graph configuration with **Odoo-standard UI labels**, without renaming technical fields or reviving `res.users` dict toggles.

## Product rule

Blueprint = template defaults. User prefs = personal. Kanban lens = who I see. Do not merge into one mega-form.

## Global constraints (locked)

- Do **not** rename technical fields (`graph_data_field`, `relate_field`, `host_model_id`, `graph_domain`, …).
- **UI labels only** — prefer Odoo words: **Graph**, **Group By**, **Measures**, **Custom Filter**, **Domain** (manager Advanced).
- Do **not** reintroduce `graph_my_data_field` / `customer_dashboard_my_pipeline` on `res.users` — kanban lens + restrict scope “Only mine” cover the product need.
- Do **not** port `graph_config_form_view_ref` — the engine owns generated settings forms.
- v1 dict modules under `odoo-dashboards-19.1` are reference only; v2 path is canonical.
- Studio writes stay behind `group_dashboard_engine_studio` + `_STUDIO_BP_WRITE_FIELDS` whitelist.

## Locked UI labels (Advanced + Studio)

| Field / UI | Label |
|------------|--------|
| Section | **Graph Configuration** |
| `graph_model_id` | **Graph Model** |
| `graph_data_field` / slot `relate_field` | **Link to Host** |
| `graph_caption` | **Graph Title** |
| `graph_groupby_ids` | **Group By** |
| `graph_measure_field_id` | **Measure** (or **Measures** if form already plural — match live ⚙️ popup) |
| `graph_domain` | **Custom Filter** (no ellipsis in `string=`) |
| Host | **Host Model** |

Period rows keep clear date labels (e.g. Create Date / Closed Date style as on the Advanced form).

## Studio promotion (Tasks 2–3)

High-value gaps promoted to Studio Content (whitelist + payload): **Link to Host** (`graph_data_field`), **Custom Filter** (`graph_domain`), period fields (`period_field_id`, `closed_period_field_id`), `include_child_records`. Scopes, group by, measure, primary button, graph title remain as already shipped.

**Task 4 (RPC catalogs for period/link pickers):** skipped — Char/select from existing payload field catalogs was enough.

## Decision matrix (locked — implement only Promote / Label)

Checklist source: v1 `_CRM_DASHBOARD_GRAPH_CONFIG` on `crm_customer_dashboard/models/res_users.py` (peer sales dicts share the same shape).

| v1 dict key | Blueprint today | Dynamic value? | Action |
|-------------|-----------------|----------------|--------|
| `graph_model` | `graph_model` / `graph_model_id` | High | **Keep** + Studio Content/Setup show as **Graph Model** (Odoo: Graph) |
| `graph_data_field` | `graph_data_field` | High | **Keep** + **expose in Studio Content** (chart section); label **Link to Host** (UI only; stays under Graph Model) |
| `graph_primary_button_title` | `primary_button_label` + alt scope | High | **Keep** (already Studio) |
| `graph_data_scope` | `scope_ids` (include) | High | **Keep**; Studio already toggles `default_on` — optional: edit name/domain stays Advanced |
| `graph_data_scope.warning` | none as field | Low | **Skip** — soft UX; document Accept |
| `graph_filter` periods | `period_field_id` / `closed_period_field_id` | High | **Promote to Studio Content** (Filters block) with Odoo-ish **Period** labels |
| `graph_filter.operator` | user pref | Medium | **Skip blueprint Studio** — personal; defaults heal from blueprint periods |
| `graph_groupby` defaults | `graph_groupby_ids` | High | **Keep** + Studio (already) — label **Group By** |
| `graph_computed_groupby_fields` | engine period tags | Low | **Skip** — Accept (engine handles) |
| `graph_measure` + aggregator | measure fields | High | **Keep** + Studio — labels **Measure** / keep aggregator near Measure |
| `graph_custom_filter` | `graph_domain` + prefs | High | **Promote `graph_domain` to Studio** (manager) — label **Custom Filter** (Odoo standard) |
| `graph_config_form_view_ref` | generated settings | None | **Skip** — engine owns form; **do not re-port** |
| `graph_my_data_field` (user) | lens + restrict scope | None as dict | **Reject** — do not port; **do not re-port** |
| (slots) `relate_field` | slot field | High | Studio already has it — label **Link to Host** (same as chart link) |
| Kanban lens | `lens_*` | High | Already shipped — label consistency in Studio if shown later |

## Explicitly out of scope

| Item | Why |
|------|-----|
| Rename `graph_data_field` | Upgrade / seed / Studio breakage |
| Port `graph_my_data_field` | Duplicate of lens + Only mine |
| Port `graph_config_form_view_ref` | Engine generates settings |
| Port `graph_computed_groupby_fields` as Char list | Engine Accept |
| Edit live v1 dict modules | v2 is canonical |
| Full scope CRUD in Studio | **Superseded** — see `2026-07-28-studio-configuration-parity-design.md` |
| `graph_data_scope.warning` as blueprint field | Soft UX — Accept |

## Future agents

Do **not** reopen CRM/sales dict → blueprint ports for **`graph_my_data_field`** or **`graph_config_form_view_ref`**. Use this matrix and kanban lens spec instead.
