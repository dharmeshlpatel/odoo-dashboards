# Blueprint Full-Form UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the entire Dashboard Blueprint form (sheet + all notebook pages) with professional zone naming, Shortcuts progressive columns, and a static card map — view/label UX only.

**Architecture:** Rename UI strings in `SLOT_SECTIONS`, O2M `string=`, and form separators/page titles. Infer Shortcuts “number source” from existing slot fields (`compute_model` vs `count_field`/`amount_field`) via a non-stored computed helper field for list `invisible`. Add a static HTML card-map block + light SCSS on the Card layout page. No new models; no runtime kanban changes.

**Tech Stack:** Odoo 19 (`dashboard_engine`), XML views, Python fields on `dashboard.blueprint.slot`, SCSS under `web.assets_backend`, existing TransactionCase tests.

**Spec:** `docs/superpowers/specs/2026-07-27-blueprint-full-form-ux-design.md`  
**Prototype:** workspace canvas `blueprint-full-form-ux-prototype.canvas.tsx`

## Global Constraints

- Module path: `custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/`
- Bump `__manifest__.py` version once at the end (current is `19.0.1.0.75` → `19.0.1.0.76` unless already bumped mid-work)
- No new stored DB columns unless inference fails (prefer non-stored compute)
- Do **not** rename primary-button V1 fields (`primary_button_label`, `primary_label_alt*`)
- Do **not** change slot `section` selection **codes** (`kpi`, `button_box`, `bottom`, …)
- After UI changes: kill :19005, upgrade `-u dashboard_engine`, restart, hard-refresh
- **Do not git commit** unless the user explicitly asks (user rule overrides plan commit steps — skip Step “Commit” everywhere)

## File map

| File | Responsibility |
|---|---|
| `models/dashboard_blueprint.py` | `SLOT_SECTIONS` labels; O2M `string=`; slot helper fields for Shortcuts UI |
| `views/dashboard_blueprint_views.xml` | Page/separator titles, help copy, card map, column `invisible` |
| `static/src/scss/blueprint_form_card_map.scss` | Card map layout (flat, no shadows) |
| `tests/test_dashboard_blueprint.py` | Inference / section label smoke if useful |
| `__manifest__.py` | Version bump |

---

### Task 1: Rename SLOT_SECTIONS + O2M strings

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`SLOT_SECTIONS` ~L33–40; O2M strings ~L1047–1085)

**Interfaces:**
- Consumes: existing section codes
- Produces: updated human labels used by Technical “All Links” and Selection widgets

- [ ] **Step 1: Update `SLOT_SECTIONS`**

Replace labels only:

```python
SLOT_SECTIONS = [
    ("kpi", "Right · KPIs"),
    ("button_box", "Footer · Totals"),
    ("bottom", "Footer · Shortcuts"),
    ("menu_views", "Manage menu · Views"),
    ("menu_new", "Manage menu · New"),
    ("menu_reports", "Manage menu · Reports"),
]
```

- [ ] **Step 2: Align O2M field strings**

```python
kpi_slot_ids = fields.One2many(..., string="Right · KPIs", ...)
button_box_slot_ids = fields.One2many(..., string="Footer · Totals", ...)
bottom_slot_ids = fields.One2many(..., string="Footer · Shortcuts", ...)
menu_views_slot_ids = fields.One2many(..., string="Manage menu · Views", ...)
menu_new_slot_ids = fields.One2many(..., string="Manage menu · New", ...)
menu_reports_slot_ids = fields.One2many(..., string="Manage menu · Reports", ...)
```

- [ ] **Step 3: Smoke-check Python**

Run (from repo root, with project venv):

```bash
PY=/Users/dharmesh/Applications/odoo/19.0/venv/python3.12.11/bin/python
$PY -c "import ast; ast.parse(open('custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/models/dashboard_blueprint.py').read())"
```

Expected: no output, exit 0

- [ ] **Step 4: Commit** — skip unless user asks

---

### Task 2: Rename form pages, separators, help copy

**Files:**
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml`

**Interfaces:**
- Consumes: Task 1 labels (match separators to `SLOT_SECTIONS`)
- Produces: full-form string polish

- [ ] **Step 1: Notebook page titles**

- `Kanban Card` → `Card layout` (`name="kanban_card"` can stay)
- `Manage Menu` → `Manage menu` (`name="manage_menu"` stays)

- [ ] **Step 2: Card layout separators**

| Old `separator string` | New |
|---|---|
| `Card Header` | `Header` (optional; or keep `Card Header`) |
| `CARD LEFT` | `Primary button` |
| `CARD RIGHT - KPIs` | `Right · KPIs` |
| `CARD BOTTOM - Stats Buttons` | `Footer · Totals` |
| `CARD BOTTOM - Smart Buttons` | `Footer · Shortcuts` |

Update adjacent muted `<p>` help to one short sentence each (match spec). Replace Share Links help that still says `CARD RIGHT - KPIs` / `CARD BOTTOM`.

- [ ] **Step 3: Primary `{{id}}` help**

Use one concrete sentence:

```xml
<div class="text-muted" colspan="2">
    On customer Acme, <code>{{id}}</code> becomes Acme’s id so the opened
    list is filtered to that customer.
</div>
```

- [ ] **Step 4: Configuration / Manage intros**

- Configuration: one line under page — “Defaults for the live Configuration popup.”
- Manage menu: “Same as the live ⋮ menu — links only.”

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 3: Shortcuts progressive columns (inference)

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`dashboard.blueprint.slot`)
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` (`bottom_slot_ids` list)
- Test: `dashboard_engine/tests/test_dashboard_blueprint.py`

**Interfaces:**
- Consumes: `compute_model`, `count_field`, `amount_field`
- Produces: non-stored booleans (or Selection) for view `invisible`

- [ ] **Step 1: Write failing test**

Add to `tests/test_dashboard_blueprint.py`:

```python
def test_slot_ui_number_source_inference(self):
    Slot = self.env["dashboard.blueprint.slot"]
    bp = self.env.ref("dashboard_engine.blueprint_crm_customers")
    related = Slot.new({
        "blueprint_id": bp.id,
        "section": "bottom",
        "label": "Opps",
        "compute_model": "crm.lead",
    })
    self.assertTrue(related.ui_number_from_related)
    self.assertFalse(related.ui_number_from_host)
    host = Slot.new({
        "blueprint_id": bp.id,
        "section": "bottom",
        "label": "Meetings",
        "count_field": "meeting_count",
    })
    self.assertFalse(host.ui_number_from_related)
    self.assertTrue(host.ui_number_from_host)
```

(Adjust field names if `meeting_count` is not a real field — use any Char name; inference only checks presence on the slot record, not field existence on host.)

- [ ] **Step 2: Run test — expect fail**

```bash
cd /Users/dharmesh/Applications/odoo/19.0
PY=venv/python3.12.11/bin/python
CONF=config/dashboard_engine_v2.conf
$PY server/odoo-bin -c "$CONF" -d dashboard_engine_v2.ee \
  --test-enable --stop-after-init \
  --test-tags=/dashboard_engine:TestDashboardBlueprint.test_slot_ui_number_source_inference \
  2>&1 | tail -40
```

Expected: FAIL — unknown field `ui_number_from_related`

- [ ] **Step 3: Add computed fields on `dashboard.blueprint.slot`**

Near other UI helpers on the slot model:

```python
ui_number_from_related = fields.Boolean(
    string="Number from related records",
    compute="_compute_ui_number_source",
)
ui_number_from_host = fields.Boolean(
    string="Number from card fields",
    compute="_compute_ui_number_source",
)

@api.depends("compute_model", "count_field", "amount_field")
def _compute_ui_number_source(self):
    for rec in self:
        related = bool(rec.compute_model)
        host = (not related) and bool(rec.count_field or rec.amount_field)
        # Empty new row: default to related columns (builder starts with Count Model).
        if not related and not host:
            related = True
        rec.ui_number_from_related = related
        rec.ui_number_from_host = not related
```

Both related+host data: prefer related (spec).

- [ ] **Step 4: Wire `bottom_slot_ids` list invisibles**

On Footer · Shortcuts list:

- `compute_model_id`, `relate_field`: `invisible="not ui_number_from_related"`
- `count_field_id`, `amount_field_id`: `invisible="not ui_number_from_host"`
- Include `ui_number_from_related` / `ui_number_from_host` as `column_invisible="1"` so the client has values

Optional one-line help above the list: “Set Count Model to count related records, or clear it and set Count/Amount Field to use values on the card.”

- [ ] **Step 5: Re-run test — expect pass**

Same command as Step 2. Expected: PASS

- [ ] **Step 6: Commit** — skip unless user asks

---

### Task 4: Static card map on Card layout

**Files:**
- Create: `dashboard_engine/static/src/scss/blueprint_form_card_map.scss`
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` (start of `kanban_card` page, after share links)
- Assets already load `dashboard_engine/static/src/scss/**/*` via `__manifest__.py`

**Interfaces:**
- Consumes: Task 2 zone names
- Produces: visual map only (no click-to-scroll)

- [ ] **Step 1: Add SCSS**

```scss
.o_dashboard_blueprint_card_map {
    display: grid;
    gap: 6px;
    max-width: 420px;
    margin-bottom: 1rem;
    padding: 10px;
    border: 1px solid var(--border-color, #c9ccd2);
    border-radius: 6px;

    .o_db_map_zone {
        padding: 6px 8px;
        font-size: 0.8125rem;
        color: var(--body-color, #212529);
        background: var(--o-view-background-color, #fff);
        border: 1px solid var(--border-color, #c9ccd2);
        border-radius: 4px;
    }
    .o_db_map_row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
    }
}
```

No gradients, no box-shadow.

- [ ] **Step 2: Insert map markup after Share Links block**

```xml
<div class="o_dashboard_blueprint_card_map mb-3" aria-hidden="true">
    <div class="o_db_map_zone">Header</div>
    <div class="o_db_map_row">
        <div class="o_db_map_zone">Primary button</div>
        <div class="o_db_map_zone">Right · KPIs</div>
    </div>
    <div class="o_db_map_zone">Footer · Totals</div>
    <div class="o_db_map_zone">Footer · Shortcuts</div>
</div>
<p class="text-muted mb-3">
    Zones below match this map top → bottom.
</p>
```

- [ ] **Step 3: Commit** — skip unless user asks

---

### Task 5: Version bump, upgrade, UI verify

**Files:**
- Modify: `dashboard_engine/__manifest__.py`

- [ ] **Step 1: Bump version** to `19.0.1.0.76`

- [ ] **Step 2: Restart with upgrade**

```bash
PIDS=$(lsof -tiTCP:19005 -sTCP:LISTEN); [ -n "$PIDS" ] && kill -9 $PIDS
cd /Users/dharmesh/Applications/odoo/19.0
PY=venv/python3.12.11/bin/python
CONF=config/dashboard_engine_v2.conf
$PY server/odoo-bin -c "$CONF" -d dashboard_engine_v2.ee \
  -u dashboard_engine --dev=xml,assets --log-level=warn
```

- [ ] **Step 3: Wait for HTTP 200** on `http://127.0.0.1:19005/web/login`

- [ ] **Step 4: Manual checklist**

1. Blueprint form sheet still shows Dashboard / Menu  
2. Tabs: Configuration · Card layout · Manage menu · Technical  
3. Card map visible; separators use new names  
4. Shortcuts: row with Count Model hides Count Field columns; host-field row hides Count Model  
5. CRM primary label flip still works  
6. Hard-refresh browser  

- [ ] **Step 5: Commit** — skip unless user asks

---

## Spec coverage check

| Spec item | Task |
|---|---|
| Naming map (pages/separators/SLOT_SECTIONS) | 1, 2 |
| Sheet polish (light) | 2 (help only; structure kept) |
| Configuration / Manage intros | 2 |
| Card map phase 1 | 4 |
| Shortcuts progressive disclosure | 3 |
| Primary `{{id}}` sentence | 2 |
| Advanced columns optional/hide | already largely present; Task 2/3 do not regress |
| No runtime change / no new models | Global + all tasks |
| Upgrade + UI verify | 5 |

**Deferred (spec out of scope):** click-to-scroll map, live preview, `value_source` stored field, wizard flow.
