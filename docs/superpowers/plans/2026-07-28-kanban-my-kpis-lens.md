# Kanban Lens — My Data + With KPIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship kanban search lenses **My …** and **With KPIs** on published dashboards — configurable labels required, graphs/KPIs stay in sync — without reviving the five `report_*` modules.

**Architecture:** Virtual booleans on `base` (`dashboard_my_data`, `dashboard_with_kpis`) rewritten in dashboard context via blueprint helpers; blueprint `lens_*` fields drive generated search inherit + action context; publish upserts search view and wires `search_view_id`.

**Tech Stack:** Odoo 19 ORM, `dashboard.blueprint` publish path, `ir.ui.view` search inherit, existing TransactionCase tests.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-kanban-my-kpis-lens-design.md`
- Engine bump from current `19.0.1.0.96` → next patch (`19.0.1.0.97` or higher if already moved)
- Technical names: `dashboard_with_kpis`, `lens_kpis_*`, `show_dashboard_kpis_filter`, `search_default_dashboard_with_kpis` — **not** `*analytics*`
- UI default seed label for KPIs: **With KPIs**
- Labels **required** when matching lens enabled — no host-model auto-default
- Do **not** add depends on `report_sale_stock` / `report_account` / `report_pos_sale` / `report_stock_enterprise` / `report_website_sale`
- Keep `report_sale_crm` for CRM create actions only
- Wave 2 drill-down “My Orders” **out of scope**
- Studio Setup lens controls **out of scope**
- After code/view changes: restart `:19005` with `-u dashboard_engine --dev=xml,assets`; wait until `http://127.0.0.1:19005/web/login` returns 200
- Commit only when the user asks

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/base.py` | Virtual lens fields + `search_fetch` domain rewrite when `dashboard_blueprint_key` set |
| `dashboard_engine/models/dashboard_blueprint.py` | `lens_*` fields, constrains/health, `_lens_my_domain`, `_lens_kpis_host_ids`, `_upsert_search_view`, extend `_upsert_window_action` / `_sync_generated_artifacts` |
| `dashboard_engine/views/dashboard_blueprint_views.xml` | Advanced form group “Kanban lens” |
| `dashboard_engine/tests/test_dashboard_lens.py` | New tests (constrain, publish context, rewrite domains) |
| Preset `**/data/seed_blueprints.xml` (+ salesperson seed) | Explicit `lens_*` values per host |
| `dashboard_engine/__manifest__.py` | Version bump |

---

### Task 1: Blueprint lens fields + required-label constrain + form UI

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (near menu / dashboard fields ~line 147+)
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` (Dashboard group or new group after Menu)
- Test: `dashboard_engine/tests/test_dashboard_lens.py` (create)

**Interfaces:**
- Produces: fields `lens_my_enabled`, `lens_my_default`, `lens_my_label`, `lens_kpis_enabled`, `lens_kpis_default`, `lens_kpis_label` on `dashboard.blueprint`
- Produces: `@api.constrains` raising `ValidationError` when enabled ∧ empty label

- [ ] **Step 1: Write failing tests**

```python
# dashboard_engine/tests/test_dashboard_lens.py
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboardKanbanLens(TransactionCase):
    def _partner_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_lens_my_requires_label(self):
        with self.assertRaises(ValidationError):
            self.env["dashboard.blueprint"].create(
                {
                    "name": "Lens My No Label",
                    "key": "lens_my_no_label",
                    "host_model_id": self._partner_model().id,
                    "lens_my_enabled": True,
                    "lens_my_label": False,
                }
            )

    def test_lens_kpis_requires_label(self):
        with self.assertRaises(ValidationError):
            self.env["dashboard.blueprint"].create(
                {
                    "name": "Lens KPIs No Label",
                    "key": "lens_kpis_no_label",
                    "host_model_id": self._partner_model().id,
                    "lens_kpis_enabled": True,
                    "lens_kpis_label": False,
                }
            )
```

- [ ] **Step 2: Run tests — expect FAIL** (fields missing)

Run (adjust config/db to local dashboard DB):

```bash
./odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-tags=/dashboard_engine:TestDashboardKanbanLens --stop-after-init
```

Expected: FAIL — unknown fields or import/collection error until fields exist.

- [ ] **Step 3: Add fields + constrain + form**

On `dashboard.blueprint`:

```python
lens_my_enabled = fields.Boolean(string="Show My filter", default=False)
lens_my_default = fields.Boolean(string="My filter on by default", default=False)
lens_my_label = fields.Char(string="My filter label")
lens_kpis_enabled = fields.Boolean(string="Show With KPIs filter", default=False)
lens_kpis_default = fields.Boolean(string="With KPIs on by default", default=False)
lens_kpis_label = fields.Char(string="With KPIs filter label")

@api.constrains(
    "lens_my_enabled", "lens_my_label",
    "lens_kpis_enabled", "lens_kpis_label",
)
def _check_lens_labels(self):
    for rec in self:
        if rec.lens_my_enabled and not (rec.lens_my_label or "").strip():
            raise ValidationError(_("My filter is on: set My filter label."))
        if rec.lens_kpis_enabled and not (rec.lens_kpis_label or "").strip():
            raise ValidationError(_("With KPIs filter is on: set With KPIs filter label."))
```

Also append matching issues in `_health_issues()` (same messages) so the health banner shows them.

Form XML — new group after Menu:

```xml
<group string="Kanban lens">
    <field name="lens_my_enabled"/>
    <field name="lens_my_default" invisible="not lens_my_enabled"/>
    <field name="lens_my_label" invisible="not lens_my_enabled"
           required="lens_my_enabled"/>
    <field name="lens_kpis_enabled"/>
    <field name="lens_kpis_default" invisible="not lens_kpis_enabled"/>
    <field name="lens_kpis_label" invisible="not lens_kpis_enabled"
           required="lens_kpis_enabled"/>
</group>
```

- [ ] **Step 4: Re-run tests — expect PASS** for Task 1 tests

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Lens domain helpers on blueprint

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_lens.py`

**Interfaces:**
- Produces: `blueprint._lens_my_domain() -> list` (ORM domain on **host** model)
- Produces: `blueprint._lens_kpis_host_ids(extra_domain=None) -> list[int]`
- Produces: `blueprint._lens_can_resolve_my() -> bool` (for health / disabling useless My)
- Consumes: `graph_model`, `graph_data_field` / `_resolve_graph_path_string()`, `graph_domain`, `_restrict_scope_domain()`, host `_fields`

**Semantics (locked):**

**My** (`_lens_my_domain`):
1. If host has `user_id` → `[("user_id", "=", self.env.uid)]`
2. Else if graph model has `user_id` and a resolvable link field to host → `[("id", "in", ids)]` where ids are distinct link values from graph rows with `user_id = uid` (+ graph domain + restrict scopes), using `_dashboard_fetching_data` context to avoid recursion
3. Else → cannot resolve (`_lens_can_resolve_my()` False)

**With KPIs** (`_lens_kpis_host_ids`):
1. Distinct host link ids from graph model under blueprint graph domain + restrict scopes (same practical set as v1 “analytics” presence)
2. Wave 1: graph-based presence is enough (KPI slot presence may share the same host set via graph link; do not invent a second slow path unless tests prove a gap)

- [ ] **Step 1: Write failing tests**

```python
def test_lens_my_domain_on_users_host(self):
    users_model = self.env["ir.model"].search([("model", "=", "res.users")], limit=1)
    bp = self.env["dashboard.blueprint"].create(
        {
            "name": "Lens Users",
            "key": "lens_users_my",
            "host_model_id": users_model.id,
            "lens_my_enabled": True,
            "lens_my_label": "My Users",
            "graph_model": "res.users",
            "graph_data_field": "id",
        }
    )
    self.assertTrue(bp._lens_can_resolve_my())
    self.assertEqual(bp._lens_my_domain(), [("user_id", "=", self.env.uid)])

def test_lens_kpis_host_ids_from_graph(self):
    # Create partner + child partner linked via parent_id graph on partners
    parent = self.env["res.partner"].create({"name": "Lens Parent"})
    child = self.env["res.partner"].create(
        {"name": "Lens Child", "parent_id": parent.id}
    )
    bp = self.env["dashboard.blueprint"].create(
        {
            "name": "Lens KPI Graph",
            "key": "lens_kpi_graph",
            "host_model_id": self._partner_model().id,
            "lens_kpis_enabled": True,
            "lens_kpis_label": "With KPIs",
            "graph_model": "res.partner",
            "graph_data_field": "parent_id",
            "graph_domain": f"[('id', '=', {child.id})]",
        }
    )
    ids = bp._lens_kpis_host_ids()
    self.assertIn(parent.id, ids)
```

- [ ] **Step 2: Run — expect FAIL** (methods missing)

- [ ] **Step 3: Implement helpers** on `dashboard.blueprint` (place near `_build_graph_payloads`)

Sketch:

```python
def _lens_can_resolve_my(self):
    self.ensure_one()
    Host = self.env.get(self.host_model_name)
    if Host is None:
        return False
    if "user_id" in Host._fields:
        return True
    if not self.graph_model or self.graph_model not in self.env:
        return False
    Graph = self.env[self.graph_model]
    return "user_id" in Graph._fields and bool(
        self._resolve_graph_path_string()[0] or self.graph_data_field
    )

def _lens_my_domain(self):
    self.ensure_one()
    Host = self.env[self.host_model_name]
    if "user_id" in Host._fields:
        return [("user_id", "=", self.env.uid)]
    ids = self._lens_kpis_host_ids(
        extra_domain=[("user_id", "=", self.env.uid)]
    )
    return [("id", "in", ids)] if ids else [("id", "=", False)]

def _lens_kpis_host_ids(self, extra_domain=None):
    """Distinct host ids that appear in this blueprint's graph scope."""
    self.ensure_one()
    if not self.graph_model or self.graph_model not in self.env:
        return []
    link = self._resolve_graph_path_string()[0] or self.graph_data_field
    if not link or "." in link:
        # Multi-hop: resolve via existing path helpers if available;
        # Wave 1 minimum: only simple field names, else return [].
        if "." in (link or ""):
            return []
    Graph = self.env[self.graph_model].with_context(_dashboard_fetching_data=True)
    domain = list(self._graph_domain_list())  # reuse existing graph domain eval helper if named differently
    domain = domain + list(self._restrict_scope_domain() or [])
    if extra_domain:
        domain = domain + list(extra_domain)
    # Prefer read_group / _read_group on link field, or SQL DISTINCT like v1
    rows = Graph.read_group(domain, [link], [link], lazy=False)
    return [r[link][0] if isinstance(r.get(link), tuple) else r.get(link)
            for r in rows if r.get(link)]
```

**Implementer note:** Reuse the blueprint’s existing graph-domain evaluation helper (search for how `_build_graph_payloads` builds domain — do not invent a second parser). Prefer `_read_group` / `read_group` compatible with Odoo 19 API used elsewhere in this file.

- [ ] **Step 4: Health** — if `lens_my_enabled` and not `_lens_can_resolve_my()`, append health issue: My filter cannot resolve for this host/graph.

- [ ] **Step 5: Re-run Task 2 tests — PASS**

---

### Task 3: Virtual fields + `search_fetch` rewrite on `base`

**Files:**
- Modify: `dashboard_engine/models/base.py`
- Test: `dashboard_engine/tests/test_dashboard_lens.py`

**Interfaces:**
- Produces: `dashboard_my_data`, `dashboard_with_kpis` Boolean fields on `base` (`store=False`)
- Produces: override `search_fetch` (and/or `_search` if required) that rewrites domain when `dashboard_blueprint_key` is in context
- Consumes: `dashboard.blueprint._get_rendering_blueprint` / `_get_blueprint(key)`, `_lens_my_domain`, `_lens_kpis_host_ids`

- [ ] **Step 1: Failing test**

```python
def test_search_rewrites_lens_flags(self):
    partner = self.env["res.partner"].create({"name": "Lens Rewrite"})
    # give partner a user_id if field exists — commercial partners may use user_id
    if "user_id" in partner._fields:
        partner.user_id = self.env.user
    bp = self.env["dashboard.blueprint"].create(
        {
            "name": "Lens Rewrite BP",
            "key": "lens_rewrite_bp",
            "host_model_id": self._partner_model().id,
            "lens_my_enabled": True,
            "lens_my_label": "My Partners",
            "lens_kpis_enabled": True,
            "lens_kpis_label": "With KPIs",
            "graph_model": "res.partner",
            "graph_data_field": "id",
            "state": "published",
        }
    )
    # Ensure graph row "presence" includes this partner id as link
    Partner = self.env["res.partner"].with_context(
        dashboard_blueprint_key=bp.key,
        initializer=bp.key,
        dashboard_rendering=True,
    )
    found = Partner.search([("dashboard_my_data", "=", True)])
    self.assertIn(partner.id, found.ids)
    found2 = Partner.search(
        [("dashboard_with_kpis", "=", True), ("id", "=", partner.id)]
    )
    self.assertIn(partner.id, found2.ids)
```

Adjust fixture if `res.partner.user_id` / graph `id` link needs a different shape — keep assertion: virtual flags never hit SQL as columns.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement on `base`**

```python
dashboard_my_data = fields.Boolean(store=False)
dashboard_with_kpis = fields.Boolean(store=False)

@api.model
@api.readonly
def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
    domain = self._dashboard_lens_rewrite_domain(domain)
    return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

@api.model
def _dashboard_lens_rewrite_domain(self, domain):
    key = self.env.context.get("dashboard_blueprint_key")
    if not key or self.env.context.get("_dashboard_fetching_data"):
        return domain
    bp = self.env["dashboard.blueprint"].sudo()._get_blueprint(key)
    if not bp or bp.host_model_name != self._name:
        return domain
    bp = bp.with_user(self.env.user)
    domain = list(domain or [])
    my_on = False
    # detect flags, replace leaves
    out = []
    for leaf in domain:
        if isinstance(leaf, (list, tuple)) and len(leaf) >= 3 and leaf[0] == "dashboard_my_data":
            if leaf[2] in (True, 1, [True], [1]):
                my_on = True
                out.extend(bp._lens_my_domain())
            # drop false toggles
            continue
        if isinstance(leaf, (list, tuple)) and len(leaf) >= 3 and leaf[0] == "dashboard_with_kpis":
            if leaf[2] in (True, 1, [True], [1]):
                ids = bp._lens_kpis_host_ids(
                    extra_domain=[("user_id", "=", self.env.uid)] if my_on else None
                )
                # Fix order: first pass detect my_on, second pass rewrite — implement two-pass
                out.append(("id", "in", ids))
            continue
        out.append(leaf)
    return out
```

**Implementer note:** Use a **two-pass** rewrite (detect `my_on` first, then replace both flags) so KPI ∩ My works. Gate with the same exclusions as graph mixin where relevant (`params.view_type == form`, etc.) — prefer `dashboard_blueprint_key` + not `_dashboard_fetching_data` as the primary gate (v2 publish already sets both key and initializer).

Ensure non-dashboard searches are unchanged (test: search partners without context still works).

- [ ] **Step 4: Re-run — PASS**

---

### Task 4: Generated search view + action context on publish

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`_upsert_window_action`, `_sync_generated_artifacts`, add `_upsert_search_view`, field `generated_search_view_id`)
- Test: `dashboard_engine/tests/test_dashboard_lens.py`

**Interfaces:**
- Produces: `generated_search_view_id` Many2one `ir.ui.view`
- Produces: search arch inheriting host default search, injecting filters named `dashboard_my_data` / `dashboard_with_kpis` with `string` from labels and `invisible` tied to context flags
- Produces: action context keys from spec

- [ ] **Step 1: Failing test**

```python
def test_publish_wires_lens_context_and_search(self):
    bp = self.env["dashboard.blueprint"].create(
        {
            "name": "Lens Publish",
            "key": "lens_publish_bp",
            "host_model_id": self._partner_model().id,
            "menu_name": "Lens Publish",
            "lens_my_enabled": True,
            "lens_my_default": True,
            "lens_my_label": "My Partners",
            "lens_kpis_enabled": True,
            "lens_kpis_default": True,
            "lens_kpis_label": "With KPIs",
            "graph_model": "res.partner",
            "graph_data_field": "parent_id",
            "state": "draft",
        }
    )
    bp.action_publish()
    action = bp.generated_action_id
    ctx = action.context
    if isinstance(ctx, str):
        from odoo.tools.safe_eval import safe_eval
        ctx = safe_eval(ctx)
    self.assertTrue(ctx.get("show_dashboard_my_filter"))
    self.assertTrue(ctx.get("show_dashboard_kpis_filter"))
    self.assertTrue(ctx.get("search_default_dashboard_my_data"))
    self.assertTrue(ctx.get("search_default_dashboard_with_kpis"))
    self.assertEqual(action.search_view_id, bp.generated_search_view_id)
    arch = bp.generated_search_view_id.arch_db or bp.generated_search_view_id.arch
    self.assertIn("My Partners", arch)
    self.assertIn("With KPIs", arch)
    self.assertIn("dashboard_my_data", arch)
    self.assertIn("dashboard_with_kpis", arch)
    self.assertIn("show_dashboard_my_filter", arch)
    self.assertIn("show_dashboard_kpis_filter", arch)
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

1. Add `generated_search_view_id = fields.Many2one("ir.ui.view", readonly=True, copy=False)`
2. `_host_default_search_view()` → `ir.ui.view` search for `host_model_name` with lowest priority / `get_view` helper
3. `_search_arch()` → inherit arch:

```xml
<data>
  <xpath expr="//search" position="inside">
    <filter name="dashboard_my_data" string="LABEL_MY"
            domain="[('dashboard_my_data', '=', True)]"
            invisible="not context.get('show_dashboard_my_filter')"/>
    <separator/>
    <filter name="dashboard_with_kpis" string="LABEL_KPIS"
            domain="[('dashboard_with_kpis', '=', True)]"
            invisible="not context.get('show_dashboard_kpis_filter')"/>
  </xpath>
</data>
```

Escape labels for XML. Only emit filters that are enabled (or emit both always invisible when disabled — prefer **only enabled** filters in arch to avoid empty labels).

4. `_upsert_search_view()` create/write like `_upsert_kanban_view`
5. `_upsert_window_action(view)` also receives search view; set `search_view_id`; build context:

```python
ctx = {
    "dashboard_blueprint_key": self.key,
    "initializer": self.key,
}
if self.lens_my_enabled:
    ctx["show_dashboard_my_filter"] = True
    if self.lens_my_default:
        ctx["search_default_dashboard_my_data"] = True
if self.lens_kpis_enabled:
    ctx["show_dashboard_kpis_filter"] = True
    if self.lens_kpis_default:
        ctx["search_default_dashboard_with_kpis"] = True
```

6. `_sync_generated_artifacts`: upsert search → kanban → action(menu) → write ids including `generated_search_view_id`

- [ ] **Step 4: Re-run — PASS**

---

### Task 5: Seed presets with explicit lens labels

**Files:** each preset blueprint record:

| Module | Seed file | Host | Suggested seed |
|--------|-----------|------|----------------|
| `crm_customer_dashboard` | `data/seed_blueprints.xml` | partner | My on+default, KPIs on+default, labels My Partners / With KPIs |
| `sales_customer_dashboard` | `data/seed_blueprints.xml` | partner | same |
| `pos_sales_customer_dashboard` | `data/seed_blueprints.xml` | partner | same |
| `website_sales_customer_dashboard` | `data/seed_website_parity.xml` or blueprints | partner | same |
| `sales_product_dashboard` | `data/seed_blueprints.xml` | product | My Products / With KPIs, both on |
| `pos_sales_product_dashboard` | `data/seed_blueprints.xml` | product | same |
| `website_sales_product_dashboard` | `data/seed_blueprints.xml` | product | same |
| `crm_salesperson_dashboard` | `data/seed_crm_salesperson.xml` | users | **My off**; KPIs on + With KPIs |
| `sales_salesperson_dashboard` | `data/seed_blueprints.xml` | users | **My off**; KPIs on |
| `warehouse_dashboard` | `data/seed_blueprints.xml` | warehouse | **My off**; KPIs on if graph exists |

Example partner snippet:

```xml
<field name="lens_my_enabled" eval="True"/>
<field name="lens_my_default" eval="True"/>
<field name="lens_my_label">My Partners</field>
<field name="lens_kpis_enabled" eval="True"/>
<field name="lens_kpis_default" eval="True"/>
<field name="lens_kpis_label">With KPIs</field>
```

- [ ] **Step 1:** Patch all listed seeds
- [ ] **Step 2:** Upgrade modules that own seeds on `:19005` (or `-u` list) so published actions regenerate — republish or rely on `_sync_generated_artifacts` on write/upgrade hooks already used by engine
- [ ] **Step 3:** Manual smoke CRM Customers + Sales Products: filters visible, defaults on, toggle changes card set

---

### Task 6: Ship on :19005

- [ ] Bump `dashboard_engine/__manifest__.py` version (`19.0.1.0.97` unless already higher)
- [ ] Kill process on `:19005`
- [ ] Restart:

```bash
./odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  -u dashboard_engine,crm_customer_dashboard,sales_customer_dashboard,sales_product_dashboard \
  --dev=xml,assets
```

(Include other preset modules as needed for full seed refresh.)

- [ ] Wait until `http://127.0.0.1:19005/web/login` returns HTTP 200
- [ ] Tell user server is ready (hard-refresh if needed)
- [ ] Commit only when user asks

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Virtual fields `dashboard_my_data` / `dashboard_with_kpis` | T3 |
| Blueprint `lens_*` + required labels | T1 |
| Domain rewrite on `base` | T3 |
| `_lens_my_domain` / `_lens_kpis_host_ids` | T2 |
| Generated search + action context | T4 |
| Preset explicit labels | T5 |
| No five `report_*` | Global / T5 |
| Version + `:19005` | T6 |
| Wave 2 / Studio lens / user My Pipeline | Out of plan |

---

## Out of this plan

- Drill-down My Orders / report_* revive  
- Studio Setup lens editors  
- `res.users` persistent My Pipeline prefs  
- Multi-hop graph link for KPI id resolution beyond Wave 1 simple fields (extend later if a preset needs it)

---

## Commit policy

Commit only when the user asks, unless execution is under an explicit “do it / ship” request covering this plan.
