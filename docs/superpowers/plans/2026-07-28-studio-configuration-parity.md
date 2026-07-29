# Studio Configuration Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Studio **Configuration** match Advanced for scopes (full CRUD), nested **Link to Host**, multi **Group By**, selective **Measure**, and **Include child records** beside the link.

**Architecture:** Studio-native OWL UI + blueprint RPCs (no embedded Advanced form). Persist through existing fields (`scope_ids`, `graph_data_field`, `graph_groupby_ids` / order, `graph_measure_field_id` / aggregator, `include_child_records`). Extend payload + whitelist; mirror Advanced semantics.

**Tech Stack:** Odoo 19, `dashboard.blueprint`, Studio OWL (`dashboard_studio_action.js` / `.xml`), `TestDashboardStudio`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-studio-configuration-parity-design.md`
- Do **not** rename technical fields
- Labels stay: **Link to Host**, **Graph Title**, **Custom Filter**, **Group By**, **Measure**
- Scopes: full Add / edit / remove / reorder; **no** `label_ids` variants this pass
- Graph Model in Configuration stays **read-only**
- Domain writes use `_safe_domain(..., strict=True)`
- Studio writes behind studio group + whitelist / dedicated scope RPCs
- Work root: `custom/addons/gritxi/odoo-dashboards-19.1-v2`
- After UI changes: kill `:19005`, restart `-u dashboard_engine --dev=xml,assets`, wait login **200**
- **Commit only when the user asks**

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | Payload keys; scope CRUD RPCs; whitelist for groupby ids / measure field+aggregator |
| `dashboard_engine/tests/test_dashboard_studio.py` | TDD for RPCs + payload |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Editor state, dirty, catalogs, path hops, save |
| `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` | General Settings + Graph Configuration layout |
| `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` | Row layout for Link + Include child if needed |
| `dashboard_engine/__manifest__.py` | Version bump on ship |
| Spec already written | No new design unless drift |

---

### Task 1: Scope payload + CRUD RPCs (Python, TDD)

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_studio.py`

**Interfaces:**
- Consumes: existing `studio_write_scope`, `get_studio_payload`, header create/unlink/reorder patterns
- Produces:
  - Payload scope dict: `id`, `name`, `description`, `mode`, `domain`, `default_on`, `sequence`
  - `studio_write_scope(scope_id, vals)` whitelist: `name`, `description`, `mode`, `domain`, `default_on`, `sequence`
  - `studio_create_scope(vals) -> payload` with `created_scope_id`
  - `studio_unlink_scope(scope_id) -> payload`
  - `studio_reorder_scopes(ordered_ids) -> payload`

- [ ] **Step 1: Write failing tests**

```python
def test_studio_payload_scope_includes_domain_and_description(self):
    bp = self._make_bp()  # helper already in file, or create with one scope
    Scope = self.env["dashboard.blueprint.scope"]
    scope = Scope.create({
        "blueprint_id": bp.id,
        "name": "Pipeline",
        "description": "Open opportunities",
        "mode": "include",
        "domain": "[('type', '=', 'opportunity')]",
        "default_on": True,
        "sequence": 10,
    })
    payload = bp.get_studio_payload()
    row = next(s for s in payload["scopes"] if s["id"] == scope.id)
    self.assertEqual(row["description"], "Open opportunities")
    self.assertIn("opportunity", row["domain"] or "")
    self.assertEqual(row["mode"], "include")

def test_studio_scope_crud_and_reorder(self):
    bp = self._make_bp()
    payload = bp.studio_create_scope({
        "name": "Leads",
        "mode": "include",
        "domain": "[('type', '=', 'lead')]",
        "default_on": False,
    })
    sid = payload["created_scope_id"]
    self.assertTrue(sid)
    bp.studio_write_scope(sid, {
        "description": "Lead rows",
        "default_on": True,
        "domain": "[('type', '=', 'lead')]",
    })
    scope = self.env["dashboard.blueprint.scope"].browse(sid)
    self.assertEqual(scope.description, "Lead rows")
    self.assertTrue(scope.default_on)
    other = bp.studio_create_scope({"name": "Mine", "mode": "restrict", "domain": "[]"})
    oid = other["created_scope_id"]
    bp.studio_reorder_scopes([oid, sid])
    names = bp.scope_ids.sorted("sequence").mapped("name")
    self.assertEqual(names[:2], ["Mine", "Leads"])
    bp.studio_unlink_scope(oid)
    self.assertFalse(self.env["dashboard.blueprint.scope"].browse(oid).exists())

def test_studio_write_scope_rejects_bad_domain(self):
    bp = self._make_bp()
    payload = bp.studio_create_scope({"name": "X", "mode": "include", "domain": "[]"})
    with self.assertRaises(UserError):
        bp.studio_write_scope(payload["created_scope_id"], {"domain": "not a domain"})
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /Users/dharmesh/Applications/odoo/19.0 && \
venv/python3.12.11/bin/python server/odoo-bin \
  -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-tags=/dashboard_engine:TestDashboardStudio.test_studio_payload_scope_includes_domain_and_description,/dashboard_engine:TestDashboardStudio.test_studio_scope_crud_and_reorder,/dashboard_engine:TestDashboardStudio.test_studio_write_scope_rejects_bad_domain \
  --stop-after-init -u dashboard_engine --http-port=0
```

Expected: FAIL (missing keys / methods / domain validation).

- [ ] **Step 3: Implement**

In `get_studio_payload` scope loop, add `description` and `domain` (string, default `"[]"`).

Extend `studio_write_scope` clean whitelist; for `domain` call the same normalization as `_studio_validate_graph_domain` / `_safe_domain(..., strict=True)`.

Add:

```python
def studio_create_scope(self, vals):
    self.ensure_one()
    vals = vals or {}
    name = (vals.get("name") or "").strip()
    if not name:
        raise UserError(_("Scope name is required."))
    mode = vals.get("mode") or "include"
    if mode not in ("include", "restrict"):
        raise UserError(_("Invalid scope mode."))
    domain = self._studio_validate_graph_domain(vals.get("domain") or "[]")
    seq = max(self.scope_ids.mapped("sequence") or [0]) + 10
    created = self.env["dashboard.blueprint.scope"].create({
        "blueprint_id": self.id,
        "name": name,
        "description": vals.get("description") or False,
        "mode": mode,
        "domain": domain,
        "default_on": bool(vals.get("default_on")),
        "sequence": int(vals.get("sequence") or seq),
    })
    payload = self.get_studio_payload()
    payload["created_scope_id"] = created.id
    return payload

def studio_unlink_scope(self, scope_id):
    self.ensure_one()
    scope = self.scope_ids.filtered(lambda s: s.id == scope_id)[:1]
    if scope:
        scope.unlink()
    return self.get_studio_payload()

def studio_reorder_scopes(self, ordered_ids):
    self.ensure_one()
    ordered_ids = [int(i) for i in (ordered_ids or [])]
    by_id = {s.id: s for s in self.scope_ids}
    if set(ordered_ids) != set(by_id):
        raise UserError(_("Scope list is out of date. Reload Studio and try again."))
    for index, scope_id in enumerate(ordered_ids):
        by_id[scope_id].sequence = (index + 1) * 10
    return self.get_studio_payload()
```

- [ ] **Step 4: Run tests — expect PASS** (same command as Step 2)

- [ ] **Step 5: Commit only if user asks**

---

### Task 2: Studio UI — General Settings scopes (full CRUD)

**Files:**
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Modify: `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` (only if list needs handles/row CSS)

**Interfaces:**
- Consumes: Task 1 RPCs
- Produces: Configuration zone **General Settings** with editable scope rows; Save/reload via payload refresh (create/write/unlink/reorder may write immediately like slots, or batch — **prefer immediate RPC on Add/Remove/Reorder/blur Save**, matching slot patterns)

- [ ] **Step 1: Replace config Scopes block with General Settings**

XML structure:

```xml
<div class="o_ds_fieldset">
  <h3>General Settings</h3>
  <p class="text-muted small">Each line becomes a tick box in the live ⚙️ popup. Use uid in a filter for the current user.</p>
  <!-- Add button -->
  <!-- For each scope: handle, name, description, mode select, domain (button opens dialog or textarea), Default checkbox, remove -->
</div>
```

Wire JS methods (names exact):

- `addScope()` → `studio_create_scope`
- `updateScope(scopeId, field, value)` → `studio_write_scope`
- `removeScope(scopeId)` → `studio_unlink_scope`
- `reorderScopes(orderedIds)` → `studio_reorder_scopes` (reuse drag pattern from slots/headers if present; else up/down buttons)

Domain: reuse Custom Filter domain dialog pattern already in Studio for `graph_domain` if one exists; else Char + `Domain` dialog helper.

- [ ] **Step 2: Manual smoke on :19005** (after a restart later or Task 5) — CRM Customers: add scope, set domain, reorder, remove

- [ ] **Step 3: Commit only if user asks**

---

### Task 3: Payload + whitelist — Group By M2M + Measure selective (Python, TDD)

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_studio.py`

**Interfaces:**
- Consumes: `graph_groupby_ids`, `ordered_graph_groupby_ids`, `_mirror_legacy_graph_groupby_from_unified`, `graph_measure_field_id`, `graph_measure_aggregator`, `graph_measure`
- Produces payload keys:
  - `graph_groupby_field_ids`: ordered list of `ir.model.fields` ids
  - `graph_groupby_field_names`: ordered technical names (optional helper for UI)
  - `graph_measure_field_id`: int or False
  - `graph_measure_aggregator`: string or False
- Whitelist adds: `graph_groupby_field_ids` (list → write M2M + order), `graph_measure_field_id`, `graph_measure_aggregator`  
  Keep writing `graph_measure` / `graph_groupby` for backward compat **or** derive them in `studio_write_blueprint` when ids are sent.

- [ ] **Step 1: Failing tests**

```python
def test_studio_payload_groupby_and_measure_ids(self):
    bp = self._make_bp_with_graph()  # graph_model set
    # set groupby via Advanced fields
    Field = self.env["ir.model.fields"]
    f1 = Field.search([("model", "=", bp.graph_model), ("name", "=", "stage_id")], limit=1)
    # skip assert if missing; use a real stored field on graph model
    bp.write({
        "graph_groupby_ids": [(6, 0, f1.ids)],
        "ordered_graph_groupby_ids": str(f1.id),
        "graph_measure_field_id": False,
        "graph_measure": "__count",
    })
    payload = bp.get_studio_payload()
    self.assertIn("graph_groupby_field_ids", payload)
    self.assertEqual(payload["graph_groupby_field_ids"], f1.ids)
    self.assertIn("graph_measure_field_id", payload)
    self.assertFalse(payload["graph_measure_field_id"])

def test_studio_write_groupby_ids_and_measure_field(self):
    bp = self._make_bp_with_graph()
    Field = self.env["ir.model.fields"]
    measure = Field.search([
        ("model", "=", bp.graph_model),
        ("ttype", "in", ["integer", "float", "monetary"]),
        ("store", "=", True),
    ], limit=1)
    group = Field.search([
        ("model", "=", bp.graph_model),
        ("name", "in", ["stage_id", "user_id", "create_date"]),
    ], limit=1)
    bp.studio_write_blueprint({
        "graph_groupby_field_ids": group.ids,
        "graph_measure_field_id": measure.id,
        "graph_measure_aggregator": "sum",
    })
    self.assertIn(group.id, bp.graph_groupby_ids.ids)
    self.assertEqual(bp.graph_measure_field_id.id, measure.id)
    self.assertEqual(bp.graph_measure_aggregator, "sum")
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement payload + `studio_write_blueprint` branches**

When `graph_groupby_field_ids` present:

```python
ids = [int(i) for i in (value or []) if i]
ordered = ",".join(str(i) for i in ids)
clean["graph_groupby_ids"] = [(6, 0, ids)]
clean["ordered_graph_groupby_ids"] = ordered
# after write, call _mirror_legacy_graph_groupby_from_unified on record if needed
```

When `graph_measure_field_id` / aggregator present, write those fields (False + clear measure → `__count` via existing inverse/compute).

Add keys to `_STUDIO_BP_WRITE_FIELDS`.

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit only if user asks**

---

### Task 4: Studio UI — Link to Host nested, Include child beside, Group By M2M, Measure select

**Files:**
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Modify: `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` (flex row for link + include child)

**Interfaces:**
- Consumes: Task 3 payload keys; `studio_model_fields(graphModel)` already returns `ttype` + `relation`
- Produces: Configuration Graph block UX per spec

- [ ] **Step 1: Link to Host nested path UI**

- Show current path segments from `editor.graph_data_field` (split on `.`)
- At each hop, `<select>` of many2one fields from `studio_model_fields(model, ['many2one'])` for that hop’s model (start = `payload.graph_model`)
- Buttons: Add hop / Remove last hop
- On change, join names → `editor.graph_data_field`, mark dirty, save via existing `studio_write_blueprint`

- [ ] **Step 2: Include child beside Link to Host**

Same row CSS:

```xml
<div class="o_ds_field_row">
  <label class="o_ds_field flex-grow-1">…Link to Host path…</label>
  <label class="o_ds_check">Include child records</label>
</div>
```

- [ ] **Step 3: Group By multi ordered**

- Multi-select or add-from-dropdown + chip list ordered
- State: `editor.graph_groupby_field_ids` (array)
- Hydrate from payload; dirty vs payload; save key `graph_groupby_field_ids`

- [ ] **Step 4: Measure selective**

- Select: empty/`__count` = Count; else measure field id from catalog filtered to integer/float/monetary (from `searchRead` or `studio_model_fields` + field ids via `ir.model.fields`)
- Aggregator `<select>` when measure field set (`sum`, `avg`, `min`, `max`, `count_distinct` — match `AGGREGATORS` on blueprint)
- Save `graph_measure_field_id`, `graph_measure_aggregator`

- [ ] **Step 5: Manual smoke** — CRM Customers Studio Configuration: nested path, 2 groupbys, measure Expected Revenue sum, include child on/off → Save → reload

- [ ] **Step 6: Commit only if user asks**

---

### Task 5: Ship on :19005

**Files:**
- Modify: `dashboard_engine/__manifest__.py` (bump patch, e.g. `19.0.1.0.99` if currently `.98`)

- [ ] **Step 1: Bump version**
- [ ] **Step 2: Kill listener on 19005; restart**

```bash
cd /Users/dharmesh/Applications/odoo/19.0
pkill -f "config/dashboard_engine_v2.conf" || true
nohup venv/python3.12.11/bin/python server/odoo-bin \
  -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  -u dashboard_engine --dev=xml,assets \
  >> /tmp/dashboard_engine_v2_19005.log 2>&1 &
# wait until curl http://127.0.0.1:19005/web/login → 200
```

- [ ] **Step 3: Smoke checklist** — General Settings scopes CRUD; Link to Host nested + Include child beside; Group By multi; Measure select; Filters still work; Advanced shows same values
- [ ] **Step 4: Commit only if user asks**

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| General Settings + full scope CRUD | T1, T2 |
| Nested Link to Host | T4 |
| Include child beside link | T4 |
| Group By Many2many ordered | T3, T4 |
| Measure selective + aggregator | T3, T4 |
| Filters keep periods / Custom Filter | unchanged (verify T5) |
| No technical renames / no label_ids | Global |
| Ship :19005 | T5 |

## Explicitly out of plan

| Item | Why |
|------|-----|
| Scope label variants | Spec out |
| Change Graph Model in Configuration | Spec out |
| Embed Advanced form | Rejected |
| `graph_data_scope.warning` field | Accept |

---

## Self-review (plan author)

1. Spec coverage: all five user items + General Settings placement mapped.  
2. No TBD/placeholder steps.  
3. RPC/payload names consistent across Tasks 1–4 (`graph_groupby_field_ids`, scope CRUD names).
