# CRM Customer Dashboard — Migration Audit

Read-only inventory. No product code was changed for this document.  
Use this when Sonnet (or a careful human pass) does the actual cutover.

**Scope:** v1 `customer_dashboard` + `crm_customer_dashboard` vs v2 `dashboard_engine` seed `crm_customers`.  
**Out of scope here:** sales / website / POS xpath extensions on the same card.

Status key:

| Tag | Meaning |
|-----|---------|
| **Covered** | Engine + seed already match v1 closely enough |
| **Needs work** | Must fix before claiming CRM parity (seed and/or engine) |
| **Accept** | Deliberate difference, or v1 bug / niche, document and move on |
| **Later** | Real gap, but after CRM-core parity (or when Sonnet is back) |

---

## A. Already covered

| Feature | Notes |
|---------|--------|
| Kanban shell + gear js_class | Generated arch uses same classes / js_class |
| Header (image, name, job@company, city/country, email, tags) | Seeded header items match v1 AnalyticDashboardTop |
| Graph model / link / caption | `crm.lead` / `partner_id` / Open pipeline |
| Settings popup shell | Gear → per-user pref form; Pipeline / Leads / Only mine scopes |
| Open opportunities KPI | Count + expected_revenue; domain on slot |
| Overdue KPI + danger style | Shared condition with `date_deadline < today` |
| View → Opportunities menu | Seeded |
| Bottom Opportunities button | Seeded + salesman group |
| Soft CRM dependency | Blueprint inactive until `crm` installed |
| Batched slots/graph (perf) | Engine path, not v1 N+1 RPC widgets |
| Unassigned KPI | Seeded (`seed_crm_parity.xml`); neutral “Unassigned” label (no Lead/Opportunity flip) |
| Leads View/New/Report menus | Seeded + `crm.group_use_lead` |
| New Opportunity | Soft-dep `report_sale_crm` |
| Report Opportunities / Activities | Seeded; enterprise variant on Opportunities report |
| Meetings bottom button | `meeting_count` + calendar act_window (not object `schedule_meeting`) |
| Primary label + graph groupby | “Pipeline Analysis” / `stage_id` (multi-groupby still Accept) |
| Overdue domain | Matches v1 (`date_closed` + deadline + opportunity), not open-KPI probability |

---

## B. Needs work (CRM-core parity)

Remaining gaps after seed fill `19.0.1.0.4`. Items 6, 10, 11 closed in
`19.0.1.0.5`/`19.0.1.0.6` — see notes below the table.

| # | Gap | v1 | v2 today | Suggested fix |
|---|-----|----|----------|---------------|
| ~~1~~ | ~~**Unassigned label flip**~~ | Lead vs Opportunity wording by `group_use_lead` | **Done in 19.0.1.0.8** — `label_alt` / `label_plural_alt` / `label_alt_groups_xmlids` on the slot; CRM seed flips to Lead(s) when viewer has `crm.group_use_lead` | — |
| ~~6~~ | ~~**Primary action variants / dynamic title**~~ | Enterprise / report_sale_crm; “Leads Analysis” when scoped | **Done** — `primary_action_variant_ids` (Enterprise wins when installed) + `primary_label_alt_scope_id`/`primary_label_alt` flip to “Leads Analysis” when Pipeline is unticked | — |
| ~~7~~ | ~~**Ordered multi-groupby**~~ | `stage_id` + `x_date_deadline_month` | **Done in 19.0.1.0.11** — `graph_groupby_extra_ids`/`ordered_graph_groupby_extra_ids` (blueprint) + `groupby_extra_ids` (pref), `many2many_ordered_tags` widget; CRM Customers seeded with `date_deadline` as the second level (`_seed_crm_multigroupby_dualdate_defaults`, self-heals on registry boot so it also applies if `crm` installs after this module) | — |
| ~~10~~ | ~~**Partner hierarchy on actions**~~ | `partner_id child_of` current | **Done** — `blueprint.link_hierarchy` widens every CRM action/menu to `child_of`, and `_hierarchy_fold_map` (two fixed queries) folds child-company leads into the parent card's own KPI/graph counts, so the badge and its click-through always agree | — |
| ~~11~~ | ~~**Scopes → KPIs**~~ | Graph My Pipeline / scopes affect analysis; KPIs had (buggy) my_pipeline hook | **Done (restrict-mode only)** — `_restrict_scope_domain()` (e.g. “Only mine”) now narrows the graph, KPI counts and their click-through actions for slots on the same model as the chart. Include-mode scopes (Pipeline/Leads) stay graph-only by design: a KPI's own `compute_domain` already hardcodes its type, so blending an include scope on top would double up or contradict it | — |
| ~~12~~ | ~~**Action-variant builder UI**~~ | Configured in Python dicts | **Done in 19.0.1.0.8** — primary variants already on “Left button + Graph”; slot variants (+ label flip fields) editable via the slot form opened from the Slots list | — |

---

## C. Accept (document, do not block CRM-core)

| Item | Why accept |
|------|------------|
| v1 KPI `my_pipeline` conditional likely broken | Engine checks wrong flag name in v1 compute mixin; graph path is correct. Don’t reintroduce the bug. |
| Graph caption stays “Open pipeline” when Leads scoped | v1 same hardcoded caption |
| ~~Multi-level ordered group-by in popup~~ | **Done in 19.0.1.0.11** — see §B item 7 |
| ~~Period filters UI richness~~ | **Done in 19.0.1.0.11** — `period_closed_field_id`/`period_closed_mq_ids`/`period_closed_year_ids` add the second (Closed Date) row; both rows pool into one `period_operator` match, same as v1 |
| Sales / Website / POS card injects | Separate blueprints or later “extension slots”, not CRM-core |
| Color picker in card ⋮ menu | Cosmetic; low value |
| Search defaults “My Partners” / “With Analytics” | Kanban action context polish; do after visual parity |
| Overdue ≠ open KPI domain | v1 overdue uses `date_closed=False`, not `probability`/`active` — keep that |
| `condition_crm_default_type` orphan | Create defaults belong in action context (New Lead/Opp); do not AND onto View domains |
| Meetings via act_window | Object method `schedule_meeting` not supported; calendar action + partner domain is close enough |
| New Lead/Opp need `report_sale_crm` | Soft-dep; slots hide until that custom module is installed |

---

## D. Later (engine product, not CRM seed alone)

| Item | Notes |
|------|--------|
| ~~Scopes applied to slot aggregates~~ | **Done for restrict-mode** — see B11. Include-mode (Pipeline/Leads) staying graph-only is the accepted product rule, not a gap |
| ~~Partner `child_of` as first-class link mode~~ | **Done** — `link_hierarchy` + `_hierarchy_fold_map`, see B10 |
| ~~Dynamic primary button title from scopes~~ | **Done** — see B6 |
| ~~Synthetic period groupby fields (`x_date_deadline_month`)~~ | **Not needed** — the engine's own multi-groupby (§B item 7) buckets any date field by month directly (`_groupby_extra_specs`), no synthetic `ir.model.fields` row required |
| Full empty-diff migration of all 13 dashboards | Phase 11 after CRM accepted. Per-field diff (labels, domains, menu structure) verified programmatically for CRM Customers; a browser-side pixel/layout eyeball across all 13 is still outstanding — see §H7 note below |
| ~~Export/import templates~~ | **Done in 19.0.1.0.12** — `dashboard.blueprint.action_export_template` / `_import_template`, portable JSON (technical names only, no db ids); see `dashboard_blueprint_template.py` |
| ~~Multi-company on blueprints~~ | **Done in 19.0.1.0.13** — optional `company_id` + `rule_dashboard_blueprint_multi_company`; scopes blueprint *configuration* only, runtime data safety is unaffected (already the host/graph model's own record rules) |

---

## E. Recommended sequence (when ready to implement)

1. ~~**Seed-only CRM fill**~~ — done in `19.0.1.0.4` (`seed_crm_parity.xml`).  
2. ~~**Small engine fixes**~~ — done in `19.0.1.0.5`/`19.0.1.0.6`: hierarchy `child_of` + fold-up, primary action variants, restrict-scope → KPIs. Action-variant builder UI closed in `19.0.1.0.8`.
3. **Side-by-side UI check** on two DBs (v1 vs v2).  
4. Only then mark Phase 11 CRM as done.

---

## F. What not to do on a weak model quota

- Do not rewrite the graph SQL mixin “to match v1” in one shot.  
- Do not claim empty diff until B1–B10 are closed or explicitly Accepted.  
- Do not migrate sales/website/POS in the same pass as CRM-core.

---

## G. Side-by-side check (2026-07-26)

**DBs:** v1 `dashboard19-1.ee` `:19001` · v2 `dashboard_engine_v2.ee` `:19005`  
**Card:** CRM Customers / partner **Acme Corporation** (id 9 on both; different lead data).  
**Method:** Odoo shell payload dump + raw `crm.lead` counts (not browser screenshots).

### Setup notes (v2 was incomplete for a fair compare)

| Prerequisite | Before | After (local staging) |
|--------------|--------|------------------------|
| `report_sale_crm` on addons path | Missing (New Lead/Opp hidden) | Symlink `odoo-dashboards-19.1-v2/report_sale_crm` → v1 module + installed |
| CRM “Use Leads” | Off for admin | Enabled via settings |
| Visible KPI smoke data | Unassigned/overdue = 0 on Acme | Created 1 unassigned + 1 overdue opp for payload check |

### Runtime payload (admin, after setup)

| Area | v2 result | Verdict |
|------|-----------|---------|
| KPIs | `unassigned`, `open_opportunities` (+amount), `overdue_opportunities` (danger) | **Pass** (label stays neutral “Unassigned”) |
| Bottom | Opportunities + Meetings (`meeting_count`) | **Pass** |
| View menu | Leads + Opportunities | **Pass** (needs Use Leads) |
| New menu | Lead + Opportunity | **Pass** (needs `report_sale_crm`) |
| Reports | Leads + Opportunities + Activities; Opportunities → `crm_enterprise.crm_opportunity_action_dashboard` | **Pass** |
| Graph | `stage_id` buckets, Pipeline scope applied | **Pass** (no second groupby) |
| Primary label | “Pipeline Analysis” | **Pass** (static; no Leads Analysis flip) |
| Health | 0 issues | **Pass** |

### Still not empty-diff (engine / product)

`child_of` hierarchy, primary action variants, and scope→KPI were closed
in `19.0.1.0.5`/`19.0.1.0.6` (see §B). Primary-button domain match + gear
title/help pass closed in `19.0.1.0.7` (see §H). Remaining per §B: multi-groupby
(item 7), dynamic Unassigned wording (item 1), action-variant builder UI
(item 12). Full dual-date-row filters and settings-block chrome still lag v1.

### Manual UI eyeball (2026-07-26)

Open both cards in the browser:

- v1: http://localhost:19001 → CRM → Customers Dashboard → Acme  
- v2: http://localhost:19005 → CRM → Customers Dashboard → Acme  

---

## H. Eyeball findings → fixes / backlog (2026-07-26)

| # | Finding | Status |
|---|---------|--------|
| H1 | **Pipeline Analysis ≠ card graph** — primary used host leaf only; Enterprise search defaults further filtered the list | **Fixed in 19.0.1.0.7** — `_primary_action_domain` merges `_effective_graph_settings()`; `_primary_action_context` strips `search_default_*` and passes `graph_groupbys` / `graph_measure` |
| H2 | **Gear popup missing section titles / help** vs v1 settings layout | **Improved in 19.0.1.0.7** — General / Graph / Filters headings + help text; field strings renamed (Group By, Measures, …). Not full v1 dual date rows / ordered multi-tags |
| H3 | **Ordered multi-groupby** (`stage_id` + `x_date_deadline_month`) | **Fixed in 19.0.1.0.11** — see §B item 7 |
| H4 | **Dual Creation Date / Closed Date filter rows** | **Fixed in 19.0.1.0.11** — see §B item 7 row above (period filters) |
| H5 | **Unassigned Lead/Opportunity label flip** | **Fixed in 19.0.1.0.8** — see §B item 1 |
| H6 | **Action-variant builder UI** | **Fixed in 19.0.1.0.8** — see §B item 12 |
| H7 | **Settings chrome** (o_setting_box columns, My Pipeline wording variants when Sales/Website installed) | **Improved in 19.0.1.0.9**; dual-date rows (§H4) got their own labelled block in 19.0.1.0.11. Multi-app wording variants remain Accept |

**Re-check after `-u dashboard_engine` on `:19005`:** Pipeline Analysis row count vs card buckets; gear shows “General Settings / Graph Configuration / Filters” with Group By + Measures labels, “Then group by” (multi-groupby tags) and a “Closed Date” row alongside “Creation Date”.

### I. Remaining eyeball scope (Sonnet, 19.0.1.0.11+)

Everything in §B/§H that was engine-shaped is now closed by field-level test
coverage (`test_ordered_extra_groupby_widens_the_graph_levels`,
`test_dual_date_rows_are_pooled_under_one_match_operator`,
`TestDashboardBlueprintTemplate`, `TestDashboardBlueprintMultiCompany` in
`tests/test_dashboard_blueprint.py`). What is **not** covered by an automated
test, and still needs a real browser side-by-side on `:19001` vs `:19005`,
is purely visual/layout: exact pixel spacing of the new "Then group by" tags
row and the "Closed Date" block in the gear popup, and the same pass for the
other 12 dashboards beyond CRM Customers (§D "Full empty-diff migration").
Nothing in this remaining scope is a functional gap.
