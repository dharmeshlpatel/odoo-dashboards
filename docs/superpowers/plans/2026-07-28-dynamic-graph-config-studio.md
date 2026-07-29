# Dynamic Graph Config — Blueprint + Studio (Odoo-standard labels) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish **dynamic Configuration** for graph/settings by (1) locking which v1 dict keys belong on the blueprint, (2) exposing the high-value gaps in Studio with **Odoo-standard labels**, (3) aligning Advanced form copy — without renaming technical fields or reviving v1 `res.users` dict toggles.

**Architecture:** Treat v1 `_CRM_DASHBOARD_GRAPH_CONFIG` (and peer sales dicts) as a **checklist**, not code to port. Blueprint remains source of truth; Studio Content/Setup edit whitelist fields; user prefs keep personal overrides. Labels use Odoo vocabulary (Graph, Group By, Measures, Custom Filter).

**Tech Stack:** Odoo 19, `dashboard.blueprint` + scopes/periods, Studio OWL (`dashboard_studio_action`), Advanced form XML.

## Global Constraints

- **Do not rename** technical fields (`graph_data_field`, `relate_field`, `host_model_id`, `graph_domain`, …)
- **UI labels only** for naming polish; prefer Odoo words: **Graph**, **Group By**, **Measures**, **Custom Filter**, **Domain** (manager)
- **Do not** reintroduce `graph_my_data_field` / `customer_dashboard_my_pipeline` on `res.users` — kanban lens + restrict scope “Only mine” cover the product need
- **Do not** hard-depend on or edit live v1 modules under `odoo-dashboards-19.1` for runtime (v2 path only); v1 dicts are reference only
- **Do not** revive the five `report_*` packs
- Keep `report_sale_crm` as today
- Studio writes stay behind `group_dashboard_engine_studio` + `_STUDIO_BP_WRITE_FIELDS` whitelist
- After UI/asset changes: restart `:19005` with `-u dashboard_engine --dev=xml,assets`; wait for `/web/login` 200
- Commit only when the user asks
- Spec references: kanban lens `2026-07-28-kanban-my-kpis-lens-design.md`; Studio Setup `2026-07-28-dashboard-studio-setup-design.md`; CRM audit

---

## Decision matrix (locked — implement only “Promote / Label”)

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
| `graph_config_form_view_ref` | generated settings | None | **Skip** — engine owns form |
| `graph_my_data_field` (user) | lens + restrict scope | None as dict | **Reject** — do not port |
| (slots) `relate_field` | slot field | High | Studio already has it — label **Link to Host** (same as chart link) |
| Kanban lens | `lens_*` | High | Already shipped — out of this plan except label consistency in Studio if shown later |

**Product rule:** Blueprint = template defaults. Prefs = personal. Lens = who I see. Do not merge into one mega-form.

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | Extend `_STUDIO_BP_WRITE_FIELDS` + `get_studio_payload` for promoted fields |
| `dashboard_engine/views/dashboard_blueprint_views.xml` | Odoo-standard string= / help polish (no field renames) |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Editor state, dirty, save payload for new Content fields |
| `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` | Content “Graph Configuration” / “Filters” blocks; Odoo labels |
| `dashboard_engine/tests/test_dashboard_studio.py` | Whitelist writes + payload keys |
| `docs/superpowers/specs/…` optional short note | Matrix “closed” for CRM audit (optional Task 5) |
| `__manifest__.py` | Version bump |

**Out of tree:** do not modify `odoo-dashboards-19.1/**` runtime dicts.

---

### Task 1: Label pass (Advanced form) — Odoo-standard copy only

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`string=` / `help=` on graph fields)
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` (section titles, placeholders)

**Locked label map (apply exactly):**

| Field / UI | `string=` / title |
|------------|-------------------|
| Section | **Graph Configuration** (keep) |
| `graph_model_id` | **Graph Model** |
| `graph_data_field` | **Link to Host** — improve **help** (path on graph model → host card); keep position under Graph Model |
| `graph_caption` | **Graph Title** |
| `graph_groupby_ids` | **Group By** (keep) |
| `graph_measure_field_id` | **Measure** (singular OK like Studio graph editor) or keep **Measures** if already plural in form — match live ⚙️ popup |
| `graph_measure_aggregator` | keep near Measure; do not invent “Aggregation” unless form already needs it |
| `graph_domain` | **Custom Filter** (remove ellipsis `…` if present in string=; Odoo uses Custom Filter) |
| `period_field_id` / `closed_period_field_id` | keep clear date labels (Create Date / Closed Date style as today) |
| Slot `relate_field` | **Link to Host** (same as chart) |
| Host | **Host Model** (keep) |

- [ ] **Step 1:** Grep current strings; apply map (fields + XML overrides)
- [ ] **Step 2:** Grep Studio XML for “Link to card” / “Custom Filter” / “Graph” — align same words (Task 2–3 will add missing controls)
- [ ] **Step 3:** Manual: open Advanced CRM Customers → Configuration page — labels match table
- [ ] **Step 4:** Commit only if user asks

---

### Task 2: Studio payload + whitelist — promote high-value gaps

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_studio.py`

**Promote into Studio writes (must be in `_STUDIO_BP_WRITE_FIELDS` + `get_studio_payload`):**

| Key | Notes |
|-----|--------|
| `graph_data_field` (and/or `graph_data_field_id` if picker uses id) | Chart link |
| `graph_domain` | Custom Filter domain string / domain widget payload |
| `period_field_id` | Default period field |
| `closed_period_field_id` | Second period row |
| `include_child_records` | Hierarchy rollup — small Boolean, high clarity |

Already present (do not regress): `primary_button_label`, `graph_caption`, `graph_measure`, `graph_groupby`, scopes `default_on`, Setup fields from Setup plan.

- [ ] **Step 1: Failing tests**

```python
def test_studio_payload_includes_graph_link_and_custom_filter(self):
    bp = …  # published/draft with graph_model crm.lead, graph_data_field partner_id, graph_domain "[]"
    payload = bp.get_studio_payload()
    self.assertEqual(payload.get("graph_data_field"), "partner_id")
    self.assertIn("graph_domain", payload)
    self.assertIn("period_field_id", payload)
    self.assertIn("closed_period_field_id", payload)
    self.assertIn("include_child_records", payload)

def test_studio_write_graph_data_field_and_domain(self):
    bp = …
    bp.studio_write_blueprint({
        "graph_data_field": "partner_id",
        "graph_domain": "[('type', '=', 'opportunity')]",
        "include_child_records": True,
    })
    self.assertEqual(bp.graph_data_field, "partner_id")
    self.assertIn("opportunity", bp.graph_domain or "")
    self.assertTrue(bp.include_child_records)
```

- [ ] **Step 2:** Run → FAIL
- [ ] **Step 3:** Extend payload + whitelist; validate `graph_domain` with existing `_safe_domain` (reject invalid → `UserError`/`ValidationError` consistent with form)
- [ ] **Step 4:** Run → PASS

**Interfaces produced:** payload keys above; whitelist accepts same keys.

---

### Task 3: Studio Content UI — Graph + Filters blocks (Odoo labels)

**Files:**
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Modify: SCSS only if spacing needed

**UX (Content mode, configuration / graph area):**

1. **Graph Configuration** (title exact)
   - Graph Model: read-only summary (change host/model stays Setup/Advanced — do not duplicate full model picker unless already easy)
   - **Link to Host**: text or relation-path control (reuse pattern from Advanced if OWL widget available; else Char with placeholder `partner_id`)
   - **Graph Title**, **Group By**, **Measure** (existing editors — ensure labels match Task 1)
   - **Include child records**: checkbox

2. **Filters**
   - Period field + Closed period field: selects fed by `studio_search_*` or payload catalogs of date fields on `graph_model`
   - **Custom Filter**: domain editor if feasible in Studio; else Char + help “Python domain list” for managers — prefer domain widget parity with Advanced when low-cost

3. Slot editor: **Link to Host** for `relate_field` (same wording as chart)

- [ ] **Step 1:** Wire editor defaults from payload; dirty detection; Save via `studio_write_blueprint`
- [ ] **Step 2:** Manual on `:19005` — CRM Customers Studio Content: change Graph Title + Custom Filter domain → Save → reload payload persists
- [ ] **Step 3:** Commit only if user asks

**Out of Task 3:** building full scope create/edit UI; Studio Setup lens fields; pixel-perfect Advanced clone.

---

### Task 4: Catalogs for period / link pickers (if Task 3 needs RPC)

**Files:** `dashboard_blueprint.py` (+ tests)

- [ ] If Char-only is too weak: add `studio_search_graph_fields(term, ttypes=('date','datetime'))` and/or reuse existing field search helpers
- [ ] Payload may include `graph_date_field_catalog`: `[{id, name, string}, …]`
- [ ] Tests for empty graph_model → empty catalog

Skip this task if Task 3 Char/select from existing payload field catalogs is enough.

---

### Task 5: Docs + CRM audit close-out

**Files:**
- Optional: short addition to `CRM_MIGRATION_AUDIT.md` §A/C — “dict → blueprint closed; Studio promotes link/periods/custom filter; user My Pipeline rejected; labels Odoo-standard”
- Optional: one-page `docs/superpowers/specs/2026-07-28-dynamic-graph-config-studio-design.md` with the decision matrix (copy from this plan)

- [ ] Mark audit items so future agents do not re-port `graph_my_data_field` / `graph_config_form_view_ref`

---

### Task 6: Ship on :19005

- [ ] Bump `dashboard_engine` version
- [ ] Kill `:19005`; restart `-u dashboard_engine --dev=xml,assets`
- [ ] Wait for `http://127.0.0.1:19005/web/login` → 200
- [ ] Smoke: Advanced labels; Studio Content Graph + Custom Filter + periods; live ⚙️ popup still works
- [ ] Commit only when user asks

---

## Explicitly out of this plan

| Item | Why |
|------|-----|
| Rename `graph_data_field` → something else | Upgrade / seed / Studio breakage |
| Port `graph_my_data_field` to blueprint/prefs | Duplicate of lens + Only mine |
| Port `graph_config_form_view_ref` | Engine generates settings |
| Port `graph_computed_groupby_fields` as Char list | Engine Accept |
| Edit `odoo-dashboards-19.1` dict modules | v2 is canonical |
| Full scope CRUD in Studio | Advanced remains |
| Wave 2 drill-down / report_* | Separate |

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Odoo-standard labels (Custom Filter, Graph, Group By, Measures) | T1, T3 |
| No technical renames | Global |
| Promote link / periods / custom filter / include_child to Studio | T2–T4 |
| Reject user My Pipeline dict | Matrix + T5 |
| v1 dict = checklist only | Global |
| Ship :19005 | T6 |

---

## Commit policy

Commit only when the user asks, unless execution is under an explicit “do it / ship” request covering this plan.
