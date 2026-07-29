# Customer 360 Suite — Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship light **health bands** in `dashboard_engine` and apply them on CRM/Sales Customers overdue / to-invoice / overdue-money slots so daily cards look market-ready before Invoice Customers and Customer 360 hub (Waves 2–3).

**Architecture:** Extend slot `style` with `warning` and a `style_mode` (`static` | `when_positive`). Resolve effective style in `_to_slot_item` from count/amount. Seed CRM/Sales overdue and to-invoice slots to use `when_positive`. OWL + SCSS render warning. Studio exposes the new fields. No Needs-attention lens yet (Wave 3). No new Invoice / 360 modules (Waves 2–3).

**Tech Stack:** Odoo 19, `dashboard.blueprint.slot`, OWL `dashboard_slots` widget, existing CRM/Sales preset XML, TransactionCase tests.

**Spec:** `docs/superpowers/specs/2026-07-29-customer-360-suite-design.md` (Wave 1 only)

## Global Constraints

- Engine version bump at end of Wave 1 (from current `19.0.1.0.110` → `19.0.1.0.111` or next free patch)
- Soft-hide via existing `module_depends` unchanged
- Classic card stack unchanged (no Layout Studio requirement for this wave)
- Out of scope: AI/scores, Needs attention lens, Invoice Customers, Customer 360 hub, Category/UTM/Company packs
- Prefer `_inherit` / field add / seed updates — no core Odoo edits
- After UI/asset changes: kill process on dashboard_engine HTTP port, restart with `-u dashboard_engine --dev=xml,assets`, wait until `/web/login` returns 200 (port from `config/dashboard_engine_v2.conf`, historically `:19005` / `:19016`)
- Do **not** git commit unless the user explicitly asks
- Separate plans later for Wave 2 (Invoice), Wave 3 (360 + attention lens), Wave 4 (clones)

---

## File map

| Path | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | `style` + `style_mode` on `dashboard.blueprint.slot`; `_resolved_style`; `_to_slot_item`; Studio payload clean/serialize |
| `dashboard_engine/static/src/xml/dashboard_slots.xml` | Apply warning CSS classes like danger |
| `dashboard_engine/static/src/scss/base_dashboard.scss` | `.o_dashboard_kpi_warning` / `.o_dashboard_stat_warning` |
| `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` | Style mode + Warning option in Properties |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Editor defaults for `style_mode` if needed |
| `dashboard_engine/views/dashboard_blueprint_views.xml` | Form fields for style_mode (if advanced form still used) |
| `dashboard_engine/tests/test_dashboard_blueprint.py` | Style resolution unit tests |
| `crm_customer_dashboard/data/seed_blueprints.xml` | Overdue Opps → `style_mode=when_positive` |
| `sales_customer_dashboard/data/seed_sales_parity.xml` | To Invoice → warning + when_positive; Total Overdue → when_positive |
| `crm_salesperson_dashboard/data/...` | Same overdue treatment if slot exists |
| `dashboard_engine/migrations/19.0.1.0.111/post-wave1-health-style.py` | Update existing DB slots (noupdate seeds) |
| `dashboard_engine/__manifest__.py` | Version bump |
| Spec status line | Mark Approved after Wave 1 plan accepted |

---

### Task 1: Slot health style API + resolve in `_to_slot_item`

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`DashboardBlueprintSlot.style`, new `style_mode`, `_to_slot_item` ~5244–5250, studio slot clean/serialize lists that include `"style"`)
- Test: `dashboard_engine/tests/test_dashboard_blueprint.py`

**Interfaces:**
- Consumes: existing `_to_slot_item(record, values=(count, amount))`
- Produces:
  - `style_mode`: Selection `[("static", "Always"), ("when_positive", "When value > 0")]`, default `"static"`, required
  - `style`: Selection adds `("warning", "Warning")` beside `default` / `danger`
  - `_resolved_style(self, count, amount) -> str` on `dashboard.blueprint.slot`
  - Payload `item["style"]` is the **resolved** style string

- [ ] **Step 1: Write the failing test**

Add to `TestDashboardBlueprint` (or nearest class that already builds slots):

```python
def test_slot_style_when_positive_resolves_danger_only_if_count(self):
    Slot = self.env["dashboard.blueprint.slot"]
    # Prefer a seeded CRM overdue slot if present; else create minimal slot on a test blueprint.
    slot = self.env.ref(
        "crm_customer_dashboard.slot_crm_overdue_opportunities",
        raise_if_not_found=False,
    )
    if not slot:
        self.skipTest("CRM customer preset not installed")
    slot.write({"style": "danger", "style_mode": "when_positive"})
    partner = self.env["res.partner"].create({"name": "Health Style Partner"})
    zero = slot._to_slot_item(partner, values=(0, None))
    self.assertTrue(zero)
    self.assertEqual(zero["style"], "default")
    positive = slot._to_slot_item(partner, values=(2, None))
    self.assertEqual(positive["style"], "danger")

def test_slot_style_when_positive_warning_for_amount(self):
    bp = self.env["dashboard.blueprint"].search(
        [("key", "=", "sales_customers")], limit=1
    )
    if not bp:
        self.skipTest("Sales customers blueprint missing")
    slot = self.env["dashboard.blueprint.slot"].create({
        "blueprint_id": bp.id,
        "key": "test_health_amount",
        "name": "Test Health Amount",
        "section": "button_box",
        "style": "warning",
        "style_mode": "when_positive",
        "show_if_zero": True,
        "value_mode": "amount",
        "amount_field": "total_due",
    })
    partner = self.env["res.partner"].create({"name": "Amt Health"})
    self.assertEqual(
        slot._to_slot_item(partner, values=(None, 0))["style"],
        "default",
    )
    self.assertEqual(
        slot._to_slot_item(partner, values=(None, 12.5))["style"],
        "warning",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-enable --stop-after-init \
  --test-tags=/dashboard_engine:TestDashboardBlueprint.test_slot_style_when_positive_resolves_danger_only_if_count
```

Expected: FAIL (missing `style_mode` field and/or AssertionError).

- [ ] **Step 3: Implement fields + resolver**

On `DashboardBlueprintSlot`:

```python
style = fields.Selection(
    [
        ("default", "Default"),
        ("warning", "Warning"),
        ("danger", "Danger"),
    ],
    default="default",
    required=True,
)
style_mode = fields.Selection(
    [
        ("static", "Always"),
        ("when_positive", "When value > 0"),
    ],
    string="Style mode",
    default="static",
    required=True,
    help="Always = use Style as painted. "
    "When value > 0 = Style only if count or amount is positive; else Default.",
)

def _resolved_style(self, count, amount):
    self.ensure_one()
    base = self.style or "default"
    if (self.style_mode or "static") != "when_positive":
        return base
    positive = False
    if count is not None and count:
        positive = True
    if amount is not None and amount:
        positive = True
    return base if positive else "default"
```

In `_to_slot_item`, replace `"style": self.style or "default"` with:

```python
"style": self._resolved_style(count, amount),
```

Include `style_mode` in Studio slot serialize/clean lists wherever `"style"` is already listed (search `"style"` in `dashboard_blueprint.py` studio helpers).

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2 for both new tests. Expected: PASS.

- [ ] **Step 5: Commit only if user asks** (skip by default)

---

### Task 2: OWL + SCSS warning band

**Files:**
- Modify: `dashboard_engine/static/src/xml/dashboard_slots.xml`
- Modify: `dashboard_engine/static/src/scss/base_dashboard.scss` (near existing danger rules ~1056)

**Interfaces:**
- Consumes: payload `item.style` in `{"default","warning","danger"}`
- Produces: warning visual parity with danger (amber/warning colors)

- [ ] **Step 1: Extend QWeb class bindings**

For each place that checks `item.style === 'danger'`, also handle warning, e.g. KPI row:

```xml
t-att-class="item.style === 'danger' ? 'o_dashboard_kpi_danger'
           : item.style === 'warning' ? 'o_dashboard_kpi_warning' : ''"
```

Same pattern for `o_dashboard_stat_danger` → `o_dashboard_stat_warning` on bottoms/button_box.

For text emphasis classes, use `text-warning fw-bold` when warning (Bootstrap).

- [ ] **Step 2: Add SCSS**

Mirror danger rules with warning tokens:

```scss
.o_dashboard_kpi_warning a,
.o_dashboard_kpi_warning .fw-bold {
    // use theme warning / amber — match nearby danger block structure
}
.bottom_block .o_dashboard_stat_warning,
.oe_button_box .o_dashboard_stat_warning {
    // same
}
```

- [ ] **Step 3: Manual smoke after upgrade** (after Task 4 seeds): open Sales Customers card with to-invoice &gt; 0 → amber KPI; overdue money → red only when amount &gt; 0.

---

### Task 3: Studio Properties for style_mode + warning

**Files:**
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` (style `<select>` ~1160)
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` (editor defaults if style fields are initialized)
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml` (slot form: show `style_mode` next to `style`)

- [ ] **Step 1: XML Studio**

Add option Warning; add Style mode select bound to `state.editor.style_mode` with `onEditorInput('style_mode', …)`.

- [ ] **Step 2: Ensure save round-trip**

Confirm `studio_write_slot` clean dict accepts `style_mode` (Task 1 lists). Manual: edit overdue slot → Style mode = When value &gt; 0 → Save → reload Studio → value persists.

- [ ] **Step 3: Blueprint form**

Add `style_mode` field beside `style` on the slot notebook/page so non-Studio admins can edit.

---

### Task 4: Seed CRM / Sales / Salesperson health + migration

**Files:**
- Modify: `crm_customer_dashboard/data/seed_blueprints.xml` — `slot_crm_overdue_opportunities`
- Modify: `sales_customer_dashboard/data/seed_sales_parity.xml` — `slot_sale_to_invoice`, `slot_sale_box_total_overdue`
- Modify: `crm_salesperson_dashboard` overdue slot XML (same keys if present)
- Create: `dashboard_engine/migrations/19.0.1.0.111/post-wave1-health-style.py` (adjust version folder to match bumped version)

**Interfaces:**
- Produces: existing DBs get `style_mode` / warning without relying on `noupdate` XML refresh

- [ ] **Step 1: Update XML seeds**

Overdue opportunities (CRM + salesperson):

```xml
<field name="style">danger</field>
<field name="style_mode">when_positive</field>
```

Sales to invoice:

```xml
<field name="style">warning</field>
<field name="style_mode">when_positive</field>
```

Sales total overdue box:

```xml
<field name="style">danger</field>
<field name="style_mode">when_positive</field>
```

(Keep `show_if_zero` as today for overdue box — often False so zero hides entirely.)

- [ ] **Step 2: Migration post- script**

```python
def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Slot = env["dashboard.blueprint.slot"].sudo()
    mapping = [
        ("overdue_opportunities", {"style": "danger", "style_mode": "when_positive"}),
        ("to_invoice", {"style": "warning", "style_mode": "when_positive"}),
        ("box_total_overdue", {"style": "danger", "style_mode": "when_positive"}),
    ]
    for key, vals in mapping:
        Slot.search([("key", "=", key)]).write(vals)
```

(Use exact keys from seeds; widen domain with blueprint key if collisions exist.)

- [ ] **Step 3: Optional density check (no new hosts)**

Verify CRM↔Sales `share_link_ids` still pool Sales bottoms/totals onto CRM cards (`crm_customer_dashboard/hooks.py`). If share broken, fix hook only — do not invent Invoice slots in Wave 1.

---

### Task 5: Version bump, upgrade, verify

**Files:**
- Modify: `dashboard_engine/__manifest__.py` version → `19.0.1.0.111` (or match migration folder)
- Modify: `docs/superpowers/specs/2026-07-29-customer-360-suite-design.md` status → `Approved · Wave 1 plan ready`

- [ ] **Step 1: Bump version** to match migration directory name.

- [ ] **Step 2: Restart with upgrade**

```bash
# kill listener on dashboard_engine HTTP port, then:
odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  -u dashboard_engine,crm_customer_dashboard,sales_customer_dashboard,crm_salesperson_dashboard \
  --dev=xml,assets
```

Wait until `http://127.0.0.1:<port>/web/login` returns HTTP 200.

- [ ] **Step 3: Manual acceptance**

1. CRM Customers: partner with overdue opps → red KPI; partner with zero overdue → not red (default).  
2. Sales Customers: to invoice &gt; 0 → amber; total overdue &gt; 0 → red.  
3. Studio: open slot → Style mode visible; Warning selectable.  
4. Hard-refresh browser if assets cached.

- [ ] **Step 4: Run regression tags**

```bash
odoo-bin -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-enable --stop-after-init \
  --test-tags=/dashboard_engine
```

Expected: existing suite still green (fix known unrelated failures).

---

## Spec coverage (self-check)

| Spec Wave 1 item | Task |
|------------------|------|
| Health bands green/amber/red | Task 1–2 (`default` / `warning` / `danger` + when_positive) |
| Enrich CRM/Sales soft health | Task 4 |
| Soft-hide unchanged | Global constraint |
| Classic stack | Global constraint |
| Needs attention lens | Deferred Wave 3 |
| Invoice Customers / Customer 360 | Deferred Waves 2–3 |
| Category / UTM / Company | Deferred Wave 4 |

## Follow-up plans (do not implement in this plan)

1. **Wave 2** — `invoice_customer_dashboard` + share into CRM/Sales  
2. **Wave 3** — `customer_360_dashboard` + Needs attention lens  
3. **Wave 4** — Category / Attribution / Company / Vendor clones  

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-29-customer-360-wave1-health-enrichment.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
