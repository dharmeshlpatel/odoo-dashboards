# Dynamic Kanban Dashboard Engine — Implementation Plan

Status: active. Supersedes earlier dual-config plans.

## 1. Requirement

Replace thirteen hand-coded dashboard modules with one engine where a dashboard is
**configuration data**, not code. A non-developer must be able to build a kanban
dashboard for any Odoo model — including through multi-hop relations such as
Product Category -> Product -> Sales Order Line — by picking records from lists
rather than typing technical strings. The result must be visually and behaviourally
identical to the existing hand-built dashboards, must load with a query count that
does not grow with card count, and must be packageable (templates, export/import).

### The constraint that shapes everything

`dashboard_engine` **already contains the complete, proven v1 engine** ported from
`base_dashboard`: the mixin chain, the SQL graph engine, the Chart.js field widget
(`analytic_dashboard_graph` in `static/src/js/fields/basic_fields.js`), the
`dashboard_slots` Json field renderer, the SCSS and the kanban view classes.

The blueprint layer then built a **second, parallel implementation** that bypasses
all of it — per-card RPC widgets and a hand-rolled CSS bar chart. Therefore this is
not "build an engine". It is "feed the engine that already exists, and delete the
duplicate".

| Concern | Ported to v2 (unused) | What the generated card uses today |
|---|---|---|
| Graph render | `analytic_dashboard_graph` field -> Chart.js canvas | `dashboard_engine_graph` widget -> CSS `div` bars |
| Graph data | `_get_graph()` + SQL mixin, `data_field IN (ids)` | `get_record_graph` RPC per card |
| KPIs / buttons | `dashboard_slots` Json field + field widget | `dashboard_engine_slots` widget, RPC per card x 6 widgets |
| Settings popup | v1 `res.users` form via gear, `target: "new"` | gear opens the blueprint admin list |

## 2. Architecture

### 2.1 The Blueprint is a configuration compiler, not a renderer

The existing mixins consume a Python config dict (`graph_model`, `graph_groupby`,
`graph_measure`, `actions.primary_right`, `actions.menu`, ...). The blueprint's job
is to **emit that exact dict shape at runtime**. Everything downstream — batched
computes, SQL graph engine, Chart.js rendering, gear popup — then works unchanged.

```
Blueprint records  ->  Compiler  ->  config dict  ->  existing mixins  ->  v1 presentation
  (relational)         (cached)      (v1 shape)       (batched)            (Chart.js field)
```

### 2.2 Alternatives considered

| Approach | Verdict | Reasoning |
|---|---|---|
| A. Runtime RPC engine (current blueprint path) | Reject | 6 widgets x N cards of identical RPCs, each re-running grouped queries. Cannot reuse the Chart.js field, so visual parity is impossible by construction. |
| B. Dynamic field generation (Studio-style custom fields) | Reject | Schema churn per blueprint edit, Python expressions in the database, fragile depends, painful uninstall, upgrade hazard. |
| C. Config compiler + generic mixin fields | **Adopt** | Zero extra round-trips (values ride along with `web_search_read`), reuses the proven stack, exact visual parity for free, no schema churn. Cost is a compile step with cache invalidation. |

### 2.3 Layers

Layer 1 — Configuration records (fully relational):

```
dashboard.blueprint          host model, menu, graph settings, header settings
  |-- dashboard.slot         KPIs, bottom buttons, button box, menu entries
  |-- dashboard.relation.path
  |     \-- dashboard.relation.hop     ordered M2O ir.model.fields
  |-- dashboard.condition              reusable, referenced not duplicated
  |     \-- dashboard.condition.rule   field / operator / value (+ relative dates)
  \-- dashboard.user.pref              per-user popup preferences
```

Layer 2 — Compiler. Pure functions turning records into the config dict, memoized
and invalidated on write. Compiles **templates only**, never user-specific or
record-specific data, which is why the cache is safe to share across users.

Layer 3 — Runtime (exists, unchanged): the `base.dashboard.mixin` chain plus the
generic payload fields.

Layer 4 — Presentation (exists, port wholesale): `analytic_dashboard_graph`
Chart.js field, `dashboard_slots` field widget, `base_dashboard.scss`, gear popup.

Layer 5 — Generation: kanban arch, window action and menu per blueprint, using v1's
arch structure with real fields rather than RPC widgets.

### 2.4 Reaching arbitrary host models

Host models are chosen by configuration, so static `_inherit` per model is
impossible. Follow the precedent already in `models/base.py` and inherit into
`base`, with every compute short-circuiting unless a dashboard is rendering:

```python
class Base(models.AbstractModel):
    _inherit = "base"

    dashboard_graph_data = fields.Text(compute="_compute_dashboard_engine_graph")

    def _compute_dashboard_engine_graph(self):
        key = self.env.context.get("dashboard_blueprint_key")
        if not key:
            self.dashboard_graph_data = False   # costs nothing
            return
```

Trade-off accepted: this reflects a small number of extra non-stored fields onto
every model in the registry. Mitigated by the context guard and by keeping the
field count minimal.

### 2.5 The three lambda patterns, made declarative

These are the only parts of the v1 config dicts that are genuinely logic rather
than data. Each needs a first-class declarative form or code creeps back in.

```python
# 1. Relative dates - required by the overdue-opportunity KPI
#    v1: ("date_deadline", "<", fields.Date.to_string(fields.Datetime.now()))
value_type = fields.Selection([
    ("static", "Fixed value"),
    ("relative_date", "Relative date"),
    ("user", "Current user"),
    ("company", "Current company"),
    ("record", "This card's record"),
])

# 2. Group-dependent values - required by _get_default_crm_type()
group_id = fields.Many2one("res.groups")

# 3. Module-variant actions - required by the crm_enterprise / report_sale_crm branches
module_ids = fields.Many2many("ir.module.module")
```

### 2.6 Deep relation paths

A path compiles to a domain template with a placeholder, resolved once per render:

```python
# Product Category -> Product -> Sales Order Line
domain_template = [("product_id.categ_id", "in", "{{ids}}")]
```

Honest limit: `formatted_read_group` can only group by fields **local to the
aggregated model**. For multi-hop paths, group on the **first hop** and fold the
hop-to-host mapping in Python. One query for all cards either way. This must be
documented in code, because the naive "group by `product_id.categ_id`" fails.

### 2.7 Durability and portability

Every M2O to `ir.model`, `ir.model.fields` or `ir.actions.actions` gets a
machine-written, stored, readonly `Char` mirror of its dotted technical name, plus
`ondelete='restrict'`. This is what lets blueprints survive module uninstalls with
a clear error, and what makes cross-database export work at all, since IDs do not
transfer. An `action_health_check` reports broken references.

## 3. Impact analysis

**v1 and v2 cannot be installed in the same database.** Both define
`base.dashboard.mixin`, `base.dashboard.graph.mixin` and the rest under identical
`_name` values, and both register the same JS keys (`analytic_dashboard_graph`,
`dashboard_slots`, `analytic_dashboard_config_settings_kanban`) and QWeb template
names. Side-by-side verification therefore requires **two databases**.

Generated `ir.ui.menu`, `ir.actions.act_window` and `ir.ui.view` records are owned
by blueprints and must be cleaned up on blueprint deletion and module uninstall.

The `report_*` modules are unaffected and must stay: they provide the search
filters (To Deliver, To Invoice, To Upsell, From Website) that blueprint conditions
reference.

Field-name collision check performed: `dashboard_slots`, `dashboard_values` and
`dashboard_graph_data` appear nowhere in `server/addons` or `enterprise`.

## 4. Edge cases

- Referenced field or action deleted by uninstall -> `ondelete='restrict'` + health check.
- Measure field type changed or made non-aggregatable -> validate at compile, fall back to count.
- M2M hop in a relation path -> duplicate rows, needs distinct handling.
- Company-dependent fields in conditions -> resolve per company, not per compile.
- Mixed currencies when summing -> aggregate per currency, never sum blindly.
- Timezone in date periods -> v1 passes `webclient_tz_offset`; dropping it shifts month boundaries.
- Zero rows -> the `is_sample_data` path, not a broken chart.
- High-cardinality group-by -> cap groups, as v1 does at 6 points.
- User lacks access to a slot's action or field -> omit the slot at payload build.
- Two blueprints publishing the same key -> unique constraint with a clear error.
- Host model without display_name or image -> header config degrades gracefully.

## 5. Odoo 19 compliance

- `_inherit` + `super()`; no monkey patching, no core edits, no hardcoded IDs.
- `models.Constraint` rather than `_sql_constraints` (already migrated).
- `res.groups.privilege` rather than the removed `category_id` (already handled).
- `formatted_read_group` for aggregation. **No raw SQL in new code**; the inherited
  SQL graph mixin stays, parameterized only.
- `fields.Json` for payloads.
- Ordered M2M via the existing `many2many_ordered_tags` widget and its
  machine-written companion order string — the established pattern here. An O2M
  would break parity with the shipped popup.
- Odoo's native domain widget for the advanced escape hatch, never a raw `Char`.
- ORM-only aggregation so record rules, field ACLs and multi-company scoping stay
  enforced by the framework.

## 6. Phases

| Phase | Work | Acceptance |
|---|---|---|
| 0 | Baseline: v1 reference screenshots, `--log-sql` query count, two databases | Baseline recorded |
| 1 | **Done.** Graph parity: payload fields on host models, arch uses `analytic_dashboard_graph`, delete hand-rolled chart | Real Chart.js chart matching the v1 screenshot; CSS bars deleted |
| 2 | **Done.** Slots parity: batched `dashboard_slots` payload, swap 6 RPC widgets for the field | KPIs, buttons, dropdown render with zero extra RPCs; query count flat in cards |
| 3 | **Subsumed by 2.** A separate `dashboard_values` field proved redundant: slot figures come from `compute_model` + `relate_field` aggregation, which already needs no host-model fields | A KPI works on a model with no dashboard-specific fields declared |
| 4 | **Done.** Relational configuration + mirrors + health check. Blueprint level: graph model / link / group-by + granularity / measure + aggregator, required apps, parent menu, primary action. Slot level: counted model, link field, count and amount measures + aggregators, source fields, opened action, listed model, visible-to groups, required apps, domain builders. Health check flags mirrors whose target is gone | No user-typed technical string on any layman tab |
| 5 | **Done.** Relation paths (`dashboard.relation.path` + hops): dotted domain compile, first-hop grouping + Python fold for graphs and slots, builder UI, blueprint/slot pickers | Category-style multi-hop figures with flat query count |
| 6 | **Done.** Conditions (`dashboard.condition` + rules): relative dates, static/user/company/record/empty values, group-dependent overrides, module-gated applicability; slots M2M-reference conditions; action variants by installed app. Seeded overdue condition wired to CRM overdue KPI | Overdue KPI with no Python; shared condition reused |
| 7 | **Done.** Settings popup as a blueprint-bound preferences form: data scopes as tick boxes, measure, group-by, period filters, custom filter. One shared form for every blueprint; preferences are private per user | Gear opens per-user settings; choices change the graph |
| 8 | **Done (through 19.0.1.0.10)**: draft how-to + published success banner, list health/state, search filters, auto key from title, layman slot copy, relation-path field labels | A non-developer builds a dashboard unaided |
| 9 | **Done (19.0.1.0.14)**: module-depends check memoized per request; hierarchy fold already flat; data for every card is already batched in one read regardless of card count. Added lazy Chart.js instantiation: `AnalyticDashboardGraphField` now defers `new Chart(...)` until a card's canvas is within ~200px of the viewport (`IntersectionObserver`), showing a pulsing `GraphLoadingSkeleton` (shares markup with `EmptyGraph`) until then — avoids building 40-80 chart instances on first paint | Query count at 40 and 80 cards nearly identical; off-screen cards render with the loading skeleton, chart animates in on first scroll into view |
| 10 | **Done (19.0.1.0.13)**: runtime sudo render + internal read ACL; prefs own-only; published-vs-draft record rules; optional `company_id` + global multi-company `ir.rule` scopes blueprint *configuration* (runtime data safety was already covered by the host/graph model's own record rules) | No cross-company leakage; no unreadable field exposed |
| 11 | **Done (19.0.1.0.21)**: gear chrome + unified Group By write path; CRM ⋮ menu merges sale/stock/account slots; generated kanban menu has color picker + Configuration footer. Remaining optional: eyeball other card surfaces vs v1 — `CRM_MIGRATION_AUDIT.md` §I | Empty diff, or differences explicitly accepted |
| 12 | **Done (19.0.1.0.12)**: export/import blueprint templates (`action_export_template` / `_import_template`, portable JSON keyed on technical names, no db ids) | Blueprint exported from one database works in another |

## 7. Testing

- **Unit**: compiler emits the exact dict shape the mixins expect (golden fixture
  from the real `_CRM_CUSTOMER_DASHBOARD_CONFIG`); conditions compile correctly
  across a month boundary; invalid hop chains rejected; non-aggregatable measures
  rejected.
- **Integration**: `assertQueryCount` identical at 10, 40 and 80 cards; generated
  arch compared structurally against v1's; popup save changes the graph payload;
  inaccessible slots omitted.
- **Security**: restricted user, two-company database, group-gated slots.
- **Upgrade**: blueprint survives module upgrade; uninstall triggers `restrict` and
  the health check reports it.
- **UI**: side-by-side across the two databases — card, graph, buttons, dropdown,
  popup field by field.

## 8. Source-of-truth map for the migration

The v1 code lives in two trees and the module naming changed between them.

| Old tree (`odoo-dashboards`) | 19.1 tree | Use |
|---|---|---|
| `report_sales_team` | `report_sale` (referenced, absent) | Old tree — defines `sale.dashboard.mixin` |
| `report_crm_team` | `report_sale_crm` | 19.1 |
| `report_pos_sales_team` | `report_pos_sale` | 19.1 |
| `sales_customer_dashboard_enterprise` | `sales_customer_dashboard` | 19.1 |
| `stock_dashboard_enterprise` | absent | Old tree only |

Use 19.1 for `base_dashboard` and everything CRM (newest and complete). Use the old
tree only for `report_sales_team` and `stock_dashboard_enterprise`.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Visual parity claim fails | Phase 1 proves it before anything is built on the assumption |
| `_inherit = "base"` field collision | Checked: clean in core and enterprise |
| Deep-path aggregation degrades to N queries | Explicit test asserting flat query count on a two-hop blueprint |
| Compiler cache serves stale config | Invalidate on write of every configuration model; cache templates only |
| Config UI needs a developer anyway | Phase 8 acceptance is an unaided non-developer, not a field checklist |
| Lambda patterns creep back as "one small module" | Phase 6 lands the declarative forms before migration starts |

## 10. Sonnet handoff — status after `19.0.1.0.13`

Engine + seeds + ACL + builder polish + H3/H4 multi-groupby/dual-date +
Phase 12 export/import + Phase 10 multi-company are all done through
**`19.0.1.0.13`**. Do **not** re-litigate closed CRM §B items 1/6/7/10/11/12
or H1–H7 unless a regression appears (each has test coverage in
`tests/test_dashboard_blueprint.py`).

### Closed this pass (19.0.1.0.11 – 19.0.1.0.13)

1. **H3 / B7 — Ordered multi-groupby.** `graph_groupby_extra_ids` +
   `ordered_graph_groupby_extra_ids` (blueprint) and `groupby_extra_ids`
   (pref) via `many2many_ordered_tags`; `_effective_graph_settings()["groupbys"]`
   feeds `_build_graph_payloads`/`_graph_point_domain`/`_primary_action_context`.
   Self-heals the CRM seed's `date_deadline` second level on every registry
   boot (`_seed_crm_multigroupby_dualdate_defaults`), so it also applies if
   `crm` installs after `dashboard_engine`.
2. **H4 — Dual Creation Date / Closed Date filter rows.** `closed_period_field_id`
   (blueprint default) + `period_closed_field_id`/`period_closed_mq_ids`/
   `period_closed_year_ids` (pref); `_period_ranges`/`_period_domain` pool both
   rows under the single `period_operator`, exactly like v1.
3. **Phase 12 — Export / import blueprint templates.** `dashboard_blueprint_template.py`:
   `action_export_template` downloads a `.dashboard.json`; `_import_template`
   rebuilds a new **draft** blueprint (+ scopes, header items, slots,
   conditions/rules, relation paths, action variants) purely from technical
   names — no database ids cross the wire. `dashboard.mirror.mixin._portable_vals()`
   is the generic building block every model in the tree uses. Import wizard +
   menu item under Dashboard Engine.
4. **Phase 10 — Multi-company.** Optional `company_id` on `dashboard.blueprint`
   + global `rule_dashboard_blueprint_multi_company` ir.rule. Scopes blueprint
   *configuration* visibility only; runtime dashboard data safety was already
   covered by the host/graph model's own multi-company record rules (ORM-only
   aggregation), so this field is deliberately excluded from the Phase 12
   export (meaningless across databases) and defaults to "shared".

### Remaining (optional, non-blocking)

5. Per-dashboard **visual** empty-diff eyeball vs v1 (`:19001` vs `:19005`) for
   the 12 dashboards beyond CRM Customers — see `CRM_MIGRATION_AUDIT.md` §I.
   Every *functional* diff already has a regression test; what's left is
   browser-side pixel/layout comparison, not missing behaviour.

### Verify before coding

- Config: `config/dashboard_engine_v2.conf`, DB `dashboard_engine_v2.ee`, port **19005**.
- Python: `venv/python3.12.11/bin/python`.
- Tests: `-i` / upgrade `dashboard_engine`, then `--test-tags=/dashboard_engine`
  on a free HTTP port (e.g. 19055) so UI on 19005 is not killed.
- Restart UI after upgrade — stale workers keep old Python.
- Audit notes: `CRM_MIGRATION_AUDIT.md` §I for the remaining visual-only scope.
