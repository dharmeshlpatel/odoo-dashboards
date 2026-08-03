# Dashboards Hub + Per-User/Per-Company Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Dashboard Engine hub (grouped left list + embedded dashboard viewer) and make chart settings persist per user **and** company, while remembering the last-opened hub dashboard only for the current login session.

**Architecture:** New `dashboard.blueprint.group` + optional `group_id` on blueprints gates hub membership. Hub is a client action that embeds the existing generated kanban via Odoo’s `@web/views/view` `View` component (same pattern as `board`). Chart prefs gain `company_id` with a one-time backfill migration. Last-opened dashboard is stored in `request.session` keyed by company id (no new DB model).

**Tech Stack:** Odoo 19, OWL 2, existing `dashboard_engine` Studio/kanban assets, `ir.actions.client`, `@web/views/view`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-03-dashboards-hub-and-per-user-persistence-design.md`
- Mockup reference: `.cursor` assets `dashboards-hub-mockup.png` (layout only; real cards come from existing kanban)
- Engine version floor: `19.0.1.0.123` — bump patch per shippable task
- Do **not** remove/repurpose `menu_parent_xmlid`, `menu_group_ids`, `menu_web_icon*`
- Hub visibility toggle = `group_id` only (no group → absent from hub)
- No new security groups; reuse `group_dashboard_engine_user` / manager / studio
- After UI/asset changes: kill `:19005`, restart with `-u dashboard_engine --dev=xml,assets`, wait for `/web/login` HTTP 200
- Commit only when the user asks
- Prefer `_inherit` / new files; no monkey patches of core menus

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint_group.py` | New `dashboard.blueprint.group` model |
| `dashboard_engine/models/dashboard_blueprint.py` | `group_id`; `_current_pref` company filter; hub RPCs; session last-opened |
| `dashboard_engine/models/__init__.py` | Import group model |
| `dashboard_engine/views/dashboard_blueprint_group_views.xml` | Group list/form + action |
| `dashboard_engine/views/dashboard_blueprint_views.xml` | `group_id` on blueprint form |
| `dashboard_engine/views/dashboard_hub_views.xml` | Client action for hub |
| `dashboard_engine/views/dashboard_engine_menus.xml` | “Dashboards” + Groups admin menu |
| `dashboard_engine/security/ir.model.access.csv` | ACL for group model |
| `dashboard_engine/migrations/19.0.1.0.124/post-pref-company.py` | Backfill `dashboard.user.pref.company_id` |
| `dashboard_engine/static/src/js/hub/dashboard_hub_action.js` | Hub OWL client action |
| `dashboard_engine/static/src/xml/hub/dashboard_hub_action.xml` | Left list + right View host |
| `dashboard_engine/static/src/scss/hub/dashboard_hub.scss` | Hub chrome |
| `dashboard_engine/tests/test_dashboard_hub.py` | Hub tree, last-opened session, group filter |
| `dashboard_engine/tests/test_dashboard_pref_company.py` | Pref company isolation + migration helper |
| `dashboard_engine/tests/__init__.py` | Register new tests |
| `dashboard_engine/__manifest__.py` | Data/assets + version |

---

### Task 1: Per-user + per-company chart prefs

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`DashboardUserPref`, `_current_pref`, `_default_pref_values`)
- Create: `dashboard_engine/migrations/19.0.1.0.124/post-pref-company.py`
- Create: `dashboard_engine/tests/test_dashboard_pref_company.py`
- Modify: `dashboard_engine/tests/__init__.py`
- Modify: `dashboard_engine/__manifest__.py` (version → `19.0.1.0.124`)

**Interfaces:**
- Consumes: existing `dashboard.user.pref`, `_get_or_create_pref()`
- Produces: `company_id` on prefs; `_current_pref()` domain includes `('company_id', '=', self.env.company.id)`; migration backfills rows

- [ ] **Step 1: Write the failing tests**

```python
# dashboard_engine/tests/test_dashboard_pref_company.py
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "dashboard_engine")
class TestDashboardPrefCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Hub Pref Co B"})
        cls.user = cls.env.ref("base.user_admin")
        cls.user.write({
            "company_ids": [(4, cls.company_b.id)],
            "company_id": cls.company_a.id,
        })
        Partner = cls.env["ir.model"]._get("res.partner")
        cls.bp = cls.env["dashboard.blueprint"].create({
            "name": "Pref Co Test",
            "key": "pref_co_test",
            "host_model_id": Partner.id,
            "state": "published",
        })

    def test_prefs_are_split_by_company(self):
        bp_a = self.bp.with_user(self.user).with_company(self.company_a)
        pref_a = bp_a._get_or_create_pref()
        self.assertEqual(pref_a.company_id, self.company_a)
        measure = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "credit_limit")], limit=1
        )
        pref_a.write({"measure_field_id": measure.id, "measure_aggregator": "avg"})

        bp_b = self.bp.with_user(self.user).with_company(self.company_b)
        self.assertFalse(bp_b._current_pref())
        pref_b = bp_b._get_or_create_pref()
        self.assertEqual(pref_b.company_id, self.company_b)
        self.assertNotEqual(pref_a.id, pref_b.id)
        self.assertFalse(pref_b.measure_field_id)

    def test_legacy_row_without_company_is_not_matched(self):
        """Rows with company_id=False must not satisfy _current_pref after the change."""
        Pref = self.env["dashboard.user.pref"].sudo()
        orphan = Pref.create({
            "user_id": self.user.id,
            "blueprint_id": self.bp.id,
            "company_id": False,
        })
        bp_a = self.bp.with_user(self.user).with_company(self.company_a)
        self.assertFalse(bp_a._current_pref())
        self.assertTrue(orphan.exists())
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
./odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-enable --stop-after-init \
  --test-tags=dashboard_engine.tests.test_dashboard_pref_company
```

Expected: FAIL (no `company_id` / domain still matches orphan).

- [ ] **Step 3: Add field + lookup + defaults**

On `DashboardUserPref` in `dashboard_blueprint.py`:

```python
company_id = fields.Many2one(
    "res.company",
    string="Company",
    required=True,
    index=True,
    default=lambda self: self.env.company,
    ondelete="cascade",
)
```

Update `_current_pref`:

```python
def _current_pref(self):
    self.ensure_one()
    return self.env["dashboard.user.pref"].search(
        [
            ("blueprint_id", "=", self.id),
            ("user_id", "=", self.env.uid),
            ("company_id", "=", self.env.company.id),
        ],
        limit=1,
    )
```

In `_default_pref_values`, add:

```python
"company_id": self.env.company.id,
```

Add SQL uniqueness (Odoo 19 style):

```python
_company_pref_uniq = models.Constraint(
    "unique(user_id, blueprint_id, company_id)",
    "A user can have only one preference row per dashboard and company.",
)
```

(If this module’s Odoo build still uses `_sql_constraints`, use that tuple form instead — match whatever other models in this DB already use.)

- [ ] **Step 4: Migration backfill**

```python
# dashboard_engine/migrations/19.0.1.0.124/post-pref-company.py
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_user_pref AS p
           SET company_id = u.company_id
          FROM res_users AS u
         WHERE p.user_id = u.id
           AND (p.company_id IS NULL OR p.company_id = 0)
        """
    )
    _logger.info(
        "dashboard_user_pref: backfilled company_id on %s rows", cr.rowcount
    )
```

Note: column is created by ORM on module update **before** post-migrate runs when version bumps. Ship this migration with the version that introduces the field.

- [ ] **Step 5: Register tests + bump version to `19.0.1.0.124`**

```python
# tests/__init__.py — add:
from . import test_dashboard_pref_company  # noqa: F401
```

- [ ] **Step 6: Run tests — expect PASS**

Same command as Step 2. Expected: PASS.

- [ ] **Step 7: Commit** (only if user asks)

```bash
git add dashboard_engine/models/dashboard_blueprint.py \
  dashboard_engine/migrations/19.0.1.0.124/post-pref-company.py \
  dashboard_engine/tests/test_dashboard_pref_company.py \
  dashboard_engine/tests/__init__.py \
  dashboard_engine/__manifest__.py
git commit -m "feat(dashboard_engine): persist chart prefs per user and company"
```

---

### Task 2: Dashboard groups model + blueprint `group_id`

**Files:**
- Create: `dashboard_engine/models/dashboard_blueprint_group.py`
- Modify: `dashboard_engine/models/__init__.py`
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (add `group_id`)
- Create: `dashboard_engine/views/dashboard_blueprint_group_views.xml`
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` (add `group_id` near Menu group)
- Modify: `dashboard_engine/views/dashboard_engine_menus.xml`
- Modify: `dashboard_engine/security/ir.model.access.csv`
- Modify: `dashboard_engine/__manifest__.py` (data entry + version → `19.0.1.0.125`)
- Modify: `dashboard_engine/tests/test_dashboard_hub.py` (create file with group tests; expand in Task 3)

**Interfaces:**
- Produces: `dashboard.blueprint.group` (`name`, `sequence`, `dashboard_ids`); `dashboard.blueprint.group_id`

- [ ] **Step 1: Write failing group test**

```python
# start of dashboard_engine/tests/test_dashboard_hub.py
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "dashboard_engine")
class TestDashboardHubGroups(TransactionCase):
    def test_group_model_and_link(self):
        group = self.env["dashboard.blueprint.group"].create({
            "name": "SALES",
            "sequence": 10,
        })
        Partner = self.env["ir.model"]._get("res.partner")
        bp = self.env["dashboard.blueprint"].create({
            "name": "Customer 360",
            "key": "hub_customer_360",
            "host_model_id": Partner.id,
            "state": "published",
            "group_id": group.id,
            "menu_sequence": 5,
        })
        self.assertEqual(group.dashboard_ids, bp)
        self.assertEqual(bp.group_id, group)
```

- [ ] **Step 2: Run — expect FAIL** (`dashboard.blueprint.group` missing)

- [ ] **Step 3: Create model**

```python
# dashboard_engine/models/dashboard_blueprint_group.py
from odoo import fields, models


class DashboardBlueprintGroup(models.Model):
    _name = "dashboard.blueprint.group"
    _description = "Dashboard Group"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    dashboard_ids = fields.One2many(
        "dashboard.blueprint",
        "group_id",
        string="Dashboards",
    )
```

Import in `models/__init__.py` **before** `dashboard_blueprint`.

On `DashboardBlueprint` add:

```python
group_id = fields.Many2one(
    "dashboard.blueprint.group",
    string="Hub Group",
    ondelete="set null",
    index=True,
    help="If set, this dashboard appears under that group in the Dashboards hub. "
    "Leave empty to keep it out of the hub (standalone menu still works if configured).",
)
```

- [ ] **Step 4: ACL + views + menus**

`ir.model.access.csv` rows:

```csv
access_dashboard_blueprint_group_internal,access_dashboard_blueprint_group_internal,model_dashboard_blueprint_group,base.group_user,1,0,0,0
access_dashboard_blueprint_group_user,access_dashboard_blueprint_group_user,model_dashboard_blueprint_group,group_dashboard_engine_user,1,0,0,0
access_dashboard_blueprint_group_manager,access_dashboard_blueprint_group_manager,model_dashboard_blueprint_group,group_dashboard_engine_manager,1,1,1,1
access_dashboard_blueprint_group_studio,access_dashboard_blueprint_group_studio,model_dashboard_blueprint_group,group_dashboard_engine_studio,1,1,1,1
```

Group views: simple list/form + `action_dashboard_blueprint_group`.

Blueprint form — inside the existing Menu `<group>`, add:

```xml
<field name="group_id" options="{'no_create_edit': False}"/>
```

Menus (`dashboard_engine_menus.xml`):

```xml
<menuitem id="menu_dashboard_engine_groups"
          name="Groups"
          parent="menu_dashboard_engine_root"
          action="action_dashboard_blueprint_group"
          sequence="8"
          groups="dashboard_engine.group_dashboard_engine_manager"/>
```

Manifest `data`: insert `views/dashboard_blueprint_group_views.xml` before blueprint views / menus.

- [ ] **Step 5: Run group test — expect PASS**

- [ ] **Step 6: Commit** (only if user asks)

---

### Task 3: Hub backend — tree payload + session last-opened

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Modify: `dashboard_engine/tests/test_dashboard_hub.py`
- Modify: `dashboard_engine/__manifest__.py` (version → `19.0.1.0.126`)

**Interfaces:**
- Produces:
  - `DashboardBlueprint.get_hub_tree() -> list[dict]`
  - `DashboardBlueprint.hub_get_last_opened() -> int|False`
  - `DashboardBlueprint.hub_set_last_opened(blueprint_id: int) -> True`
  - Session key: `dashboard_hub_last_opened` → `{str(company_id): blueprint_id}`

- [ ] **Step 1: Write failing hub API tests**

```python
@tagged("post_install", "-at_install", "dashboard_engine")
class TestDashboardHubApi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Group = cls.env["dashboard.blueprint.group"]
        cls.g_sales = Group.create({"name": "SALES", "sequence": 10})
        cls.g_crm = Group.create({"name": "CRM", "sequence": 20})
        Partner = cls.env["ir.model"]._get("res.partner")
        vals = {
            "host_model_id": Partner.id,
            "state": "published",
        }
        cls.bp_c360 = cls.env["dashboard.blueprint"].create({
            **vals,
            "name": "Customer 360",
            "key": "hub_c360",
            "group_id": cls.g_sales.id,
            "menu_sequence": 10,
        })
        cls.bp_p360 = cls.env["dashboard.blueprint"].create({
            **vals,
            "name": "Product 360",
            "key": "hub_p360",
            "group_id": cls.g_sales.id,
            "menu_sequence": 20,
        })
        cls.bp_crm = cls.env["dashboard.blueprint"].create({
            **vals,
            "name": "Customer",
            "key": "hub_crm_customer",
            "group_id": cls.g_crm.id,
            "menu_sequence": 10,
        })
        cls.bp_orphan = cls.env["dashboard.blueprint"].create({
            **vals,
            "name": "Orphan",
            "key": "hub_orphan",
            "menu_sequence": 1,
        })
        cls.bp_draft = cls.env["dashboard.blueprint"].create({
            "host_model_id": Partner.id,
            "state": "draft",
            "name": "Draft Hub",
            "key": "hub_draft",
            "group_id": cls.g_sales.id,
        })

    def test_hub_tree_skips_ungrouped_and_draft(self):
        tree = self.env["dashboard.blueprint"].get_hub_tree()
        names = [d["name"] for g in tree for d in g["dashboards"]]
        self.assertEqual(
            [(g["name"], [d["name"] for d in g["dashboards"]]) for g in tree],
            [
                ("SALES", ["Customer 360", "Product 360"]),
                ("CRM", ["Customer"]),
            ],
        )
        self.assertNotIn("Orphan", names)
        self.assertNotIn("Draft Hub", names)

    def test_hub_tree_includes_action_id(self):
        self.bp_c360.action_publish()  # ensure generated_action_id
        tree = self.env["dashboard.blueprint"].get_hub_tree()
        first = tree[0]["dashboards"][0]
        self.assertTrue(first["action_id"])
        self.assertEqual(first["id"], self.bp_c360.id)

    def test_last_opened_session_roundtrip(self):
        from odoo.http import request
        # TransactionCase may not have a real HTTP request; use a unit-style
        # helper that accepts an explicit session dict in tests, see Step 3.
        Blueprint = self.env["dashboard.blueprint"]
        session = {}
        Blueprint._hub_session_set_last_opened(session, self.env.company.id, self.bp_crm.id)
        self.assertEqual(
            Blueprint._hub_session_get_last_opened(session, self.env.company.id),
            self.bp_crm.id,
        )
        # Stale id falls back
        gone = self.bp_crm.id
        self.bp_crm.unlink()
        resolved = Blueprint._hub_resolve_initial_blueprint_id(
            session, self.env.company.id
        )
        self.assertEqual(resolved, self.bp_c360.id)
        self.assertNotEqual(resolved, gone)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement helpers + public RPCs on `DashboardBlueprint`**

```python
_HUB_SESSION_KEY = "dashboard_hub_last_opened"


@api.model
def _hub_visible_blueprints(self):
    """Published, runtime-active blueprints that belong to a hub group."""
    bps = self.search([
        ("state", "=", "published"),
        ("active", "=", True),
        ("group_id", "!=", False),
    ])
    return bps.filtered(lambda b: b._is_runtime_active()).sorted(
        key=lambda b: (b.group_id.sequence, b.group_id.id, b.menu_sequence, b.id)
    )


@api.model
def get_hub_tree(self):
    """Left-panel payload: groups → dashboards (only grouped + visible)."""
    bps = self._hub_visible_blueprints()
    tree = []
    current_gid = None
    bucket = None
    for bp in bps:
        if bp.group_id.id != current_gid:
            current_gid = bp.group_id.id
            bucket = {
                "id": bp.group_id.id,
                "name": bp.group_id.name,
                "sequence": bp.group_id.sequence,
                "dashboards": [],
            }
            tree.append(bucket)
        bucket["dashboards"].append({
            "id": bp.id,
            "name": bp.menu_name or bp.name,
            "key": bp.key,
            "action_id": bp.generated_action_id.id or False,
            "menu_sequence": bp.menu_sequence,
        })
    return tree


@api.model
def _hub_session_get_last_opened(self, session, company_id):
    data = session.get(self._HUB_SESSION_KEY) or {}
    raw = data.get(str(company_id))
    return int(raw) if raw else False


@api.model
def _hub_session_set_last_opened(self, session, company_id, blueprint_id):
    data = dict(session.get(self._HUB_SESSION_KEY) or {})
    if blueprint_id:
        data[str(company_id)] = int(blueprint_id)
    else:
        data.pop(str(company_id), None)
    session[self._HUB_SESSION_KEY] = data
    return True


@api.model
def _hub_resolve_initial_blueprint_id(self, session, company_id):
    visible = self._hub_visible_blueprints()
    if not visible:
        return False
    remembered = self._hub_session_get_last_opened(session, company_id)
    if remembered and remembered in visible.ids:
        return remembered
    if remembered:
        self._hub_session_set_last_opened(session, company_id, False)
    return visible[0].id


@api.model
def hub_get_initial_state(self):
    """Called by the OWL hub on open."""
    from odoo.http import request
    session = request.session
    company_id = self.env.company.id
    tree = self.get_hub_tree()
    initial_id = self._hub_resolve_initial_blueprint_id(session, company_id)
    return {
        "tree": tree,
        "active_blueprint_id": initial_id,
        "company_id": company_id,
    }


@api.model
def hub_set_last_opened(self, blueprint_id):
    from odoo.http import request
    bp = self.browse(int(blueprint_id)).exists()
    if not bp or bp not in self._hub_visible_blueprints():
        # Quietly ignore invalid picks; client will fall back on next load
        return False
    return self._hub_session_set_last_opened(
        request.session, self.env.company.id, bp.id
    )
```

Ensure `action_publish` / `_sync_generated_artifacts` has run for hub test blueprints that assert `action_id` (call `action_publish()` or `_sync_generated_artifacts()` in setUp after create).

- [ ] **Step 4: Run hub API tests — expect PASS**

- [ ] **Step 5: Commit** (only if user asks)

---

### Task 4: Hub OWL client action (left list + embedded View)

**Files:**
- Create: `dashboard_engine/static/src/js/hub/dashboard_hub_action.js`
- Create: `dashboard_engine/static/src/xml/hub/dashboard_hub_action.xml`
- Create: `dashboard_engine/static/src/scss/hub/dashboard_hub.scss`
- Create: `dashboard_engine/views/dashboard_hub_views.xml`
- Modify: `dashboard_engine/views/dashboard_engine_menus.xml`
- Modify: `dashboard_engine/__manifest__.py` (data + version → `19.0.1.0.127`)

**Interfaces:**
- Consumes: `hub_get_initial_state`, `hub_set_last_opened`, `generated_action_id` via `/web/action/load`
- Produces: client action tag `dashboard_engine.hub`

**Embedding decision (locked):** use `@web/views/view` `View` with control panel **enabled** (unlike `board`, which hides it). Load the blueprint’s `generated_action_id` through `/web/action/load`, then pass `resModel`, `type: 'kanban'`, `viewId`, `searchViewId`, `context`, `domain`, and `views` — same shape as `board.BoardAction`, but keep the search/control panel so gear + filters work. Remount with `t-key` when the selection changes.

- [ ] **Step 1: Client action XML + menu**

```xml
<!-- dashboard_engine/views/dashboard_hub_views.xml -->
<odoo>
    <record id="action_dashboard_hub" model="ir.actions.client">
        <field name="name">Dashboards</field>
        <field name="tag">dashboard_engine.hub</field>
    </record>
</odoo>
```

Menu (sequence before Blueprints):

```xml
<menuitem id="menu_dashboard_engine_hub"
          name="Dashboards"
          parent="menu_dashboard_engine_root"
          action="action_dashboard_hub"
          sequence="1"
          groups="dashboard_engine.group_dashboard_engine_user"/>
```

Add file to manifest `data` list.

- [ ] **Step 2: Implement OWL action**

```javascript
// dashboard_engine/static/src/js/hub/dashboard_hub_action.js
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { View } from "@web/views/view";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { user } from "@web/core/user";

export class DashboardHubAction extends Component {
    static template = "dashboard_engine.DashboardHubAction";
    static components = { View };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            tree: [],
            activeBlueprintId: false,
            viewProps: null,
            loadingView: false,
        });
        onWillStart(async () => {
            const data = await this.orm.call(
                "dashboard.blueprint",
                "hub_get_initial_state",
                []
            );
            this.state.tree = data.tree || [];
            if (data.active_blueprint_id) {
                await this.selectDashboard(data.active_blueprint_id, false);
            }
        });
    }

    findDashboard(blueprintId) {
        for (const group of this.state.tree) {
            const hit = group.dashboards.find((d) => d.id === blueprintId);
            if (hit) {
                return hit;
            }
        }
        return null;
    }

    async selectDashboard(blueprintId, persist = true) {
        const dash = this.findDashboard(blueprintId);
        if (!dash || !dash.action_id) {
            this.state.activeBlueprintId = false;
            this.state.viewProps = null;
            return;
        }
        this.state.activeBlueprintId = blueprintId;
        this.state.loadingView = true;
        try {
            const action = await rpc("/web/action/load", {
                action_id: dash.action_id,
            });
            if (!action) {
                this.state.viewProps = null;
                return;
            }
            const kanban = (action.views || []).find((v) => v[1] === "kanban");
            const search = (action.views || []).find((v) => v[1] === "search");
            this.state.viewProps = {
                resModel: action.res_model,
                type: "kanban",
                viewId: kanban ? kanban[0] : false,
                views: [
                    [kanban ? kanban[0] : false, "kanban"],
                    [search ? search[0] : false, "search"],
                ],
                context: {
                    ...(action.context || {}),
                    lang: user.context.lang,
                },
                domain: action.domain || [],
                // Keep control panel: search bar + Customize gear
            };
            if (persist) {
                await this.orm.call(
                    "dashboard.blueprint",
                    "hub_set_last_opened",
                    [blueprintId]
                );
            }
        } finally {
            this.state.loadingView = false;
        }
    }
}

registry.category("actions").add("dashboard_engine.hub", DashboardHubAction);
```

- [ ] **Step 3: Template**

```xml
<!-- dashboard_engine/static/src/xml/hub/dashboard_hub_action.xml -->
<templates xml:space="preserve">
    <t t-name="dashboard_engine.DashboardHubAction">
        <div class="o_dashboard_hub d-flex h-100">
            <aside class="o_dashboard_hub_sidebar border-end">
                <t t-foreach="state.tree" t-as="group" t-key="group.id">
                    <div class="o_dashboard_hub_group_label text-muted text-uppercase small px-3 pt-3 pb-1">
                        <t t-esc="group.name"/>
                    </div>
                    <t t-foreach="group.dashboards" t-as="dash" t-key="dash.id">
                        <button type="button"
                                class="o_dashboard_hub_item btn btn-link text-start w-100 rounded-0"
                                t-att-class="{ 'o_active': state.activeBlueprintId === dash.id }"
                                t-on-click="() => this.selectDashboard(dash.id)">
                            <t t-esc="dash.name"/>
                        </button>
                    </t>
                </t>
                <div t-if="!state.tree.length" class="text-muted p-3 small">
                    No dashboards in the hub yet. Assign a Hub Group on a published blueprint.
                </div>
            </aside>
            <main class="o_dashboard_hub_main flex-grow-1 overflow-auto">
                <t t-if="state.viewProps">
                    <View t-props="state.viewProps" t-key="state.activeBlueprintId"/>
                </t>
                <div t-else="" class="text-muted p-4">
                    Select a dashboard from the list.
                </div>
            </main>
        </div>
    </t>
</templates>
```

- [ ] **Step 4: SCSS**

```scss
// dashboard_engine/static/src/scss/hub/dashboard_hub.scss
.o_dashboard_hub {
    min-height: 100%;
    background: var(--o-view-background-color, #fff);
}
.o_dashboard_hub_sidebar {
    width: 240px;
    min-width: 200px;
    flex-shrink: 0;
    overflow: auto;
}
.o_dashboard_hub_item {
    color: var(--body-color);
    padding: 0.5rem 1rem;
    text-decoration: none;
    border-left: 3px solid transparent;
    &.o_active {
        border-left-color: var(--primary);
        background: rgba(var(--primary-rgb, 113, 75, 103), 0.08);
        color: var(--primary);
        font-weight: 600;
    }
}
.o_dashboard_hub_main {
    min-width: 0;
}
```

Assets already include `static/src/js/**/*`, `xml/**/*`, `scss/**/*` — no manifest asset path change needed.

- [ ] **Step 5: Restart `:19005` with upgrade**

```bash
# kill process on 19005, then:
./odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  -u dashboard_engine --dev=xml,assets
```

Wait until `http://127.0.0.1:19005/web/login` returns HTTP 200.

- [ ] **Step 6: Manual smoke (user)**

1. Create Groups SALES / CRM; set `group_id` on 2–3 published blueprints; leave one without group.
2. Open **Dashboard Engine → Dashboards**.
3. Left list shows only grouped ones; click switches right panel kanban.
4. Search bar + gear still work on the right.
5. Refresh page → same dashboard selected; logout/login → first dashboard again.
6. Standalone app menus still open the same dashboard full-page.

- [ ] **Step 7: Commit** (only if user asks)

---

### Task 5: Studio Setup — Hub Group field (parity)

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`get_studio_payload`, `_STUDIO_BP_WRITE_FIELDS`, optional `studio_search_hub_groups`)
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Modify: `dashboard_engine/tests/test_dashboard_studio.py`
- Modify: `dashboard_engine/__manifest__.py` (version → `19.0.1.0.128`)

**Interfaces:**
- Produces: Setup payload keys `group_id`, `group_name`; writable via `studio_write_blueprint`

- [ ] **Step 1: Failing studio test** — payload includes `group_id`; write updates it.

- [ ] **Step 2: Backend whitelist + payload + search RPC** (mirror existing menu/module pickers).

- [ ] **Step 3: Setup UI field** under Menu section: “Hub Group” picker.

- [ ] **Step 4: Tests PASS + restart `:19005` if UI verified.**

- [ ] **Step 5: Commit** (only if user asks)

---

### Task 6: Ship checklist

- [ ] All new tests green:

```bash
./odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-enable --stop-after-init \
  --test-tags=dashboard_engine
```

- [ ] Manual smoke from Task 4 Step 6 complete
- [ ] Spec success criteria checked off against live UI
- [ ] Commit design + plan + code when user asks (do not push unless asked)

---

## Out of scope (do not implement in this plan)

- Removing standalone per-app menus
- Subtitle / description field on blueprints
- Favorites / pin / list-vs-kanban hub prefs
- Browser localStorage for last-opened
- Auto-creating Groups for existing blueprints (admin curation)

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Hub menu under Dashboard Engine | T4 |
| `dashboard.blueprint.group` | T2 |
| `group_id` hub visibility toggle | T2 + T3 |
| Left list order (group seq → menu_sequence) | T3 |
| Skip ungrouped / drafts / inactive modules | T3 (`_is_runtime_active`) |
| Right panel = existing kanban + search + gear | T4 (`View` embed) |
| Standalone menus untouched | Global constraint / T4 smoke |
| Pref `company_id` + migration | T1 |
| Last opened session-only, per company | T3 + T4 |
| Fallback to first visible | T3 `_hub_resolve_initial_blueprint_id` |
| No new security groups | T2 ACL only |
| Studio can set Hub Group | T5 |

**Placeholder scan:** none intentional. Embedding technique locked to `View` + `/web/action/load`.

**Type consistency:** session helpers take `(session, company_id[, blueprint_id])`; public RPCs use `request.session`; OWL calls `hub_get_initial_state` / `hub_set_last_opened` only.
