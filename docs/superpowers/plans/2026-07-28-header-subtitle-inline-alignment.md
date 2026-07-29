# Header Subtitle / Inline + Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace header Kind `left`/`right` with **subtitle** / **inline** plus **alignment** (`left`/`center`/`right` on both kinds); migrate data; update live card arch, Advanced form, Studio Header (Title & Image + lines), and field chips as **`Label (technical_name)`**.

**Architecture:** Change `dashboard.blueprint.header.item` selection + new `alignment` field; post-migrate DB and seeds; rewrite `_header_arch` / `_header_line_arch` for the new matrix; Advanced list columns + tag label format; Studio Header zone parity with Advanced.

**Tech Stack:** Odoo 19, `dashboard_engine`, Studio OWL, `many2many_ordered_tags`, blueprint tests.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-header-subtitle-inline-alignment-design.md`
- Kind values only: `subtitle`, `inline`
- Alignment on **both** kinds: `left`, `center`, `right` (default `left`)
- Icon UI when `kind == inline` and `alignment == left`
- Field chips / pickers: **`Label (technical_name)`** (e.g. `Job Position (function)`)
- Do **not** rename `field_names` storage
- Work root: `custom/addons/gritxi/odoo-dashboards-19.1-v2`
- After UI/model changes: restart `:19005` with `-u dashboard_engine --dev=xml,assets`; login **200**
- **Commit only when the user asks**
- Bump version to **19.0.1.0.100** on ship (current is `19.0.1.0.99`)

---

## File map

| File | Responsibility |
|------|----------------|
| `dashboard_engine/models/dashboard_blueprint.py` | `kind` / `alignment`; arch; Studio whitelist; create defaults |
| `dashboard_engine/migrations/19.0.1.0.100/post-header-kind-alignment.py` | Migrate left/right → inline+align |
| `dashboard_engine/views/dashboard_blueprint_views.xml` | Advanced Header list columns |
| `dashboard_engine/static/src/js/fields/many2many_ordered_tags_field.js` (+ xml if needed) | Tag label `Label (name)` option |
| Preset `**/data/seed_blueprint_headers.xml` (+ parity seeds with kind) | New kind/alignment |
| `dashboard_engine/tests/test_dashboard_blueprint.py` | Migration-equivalent mapping + arch |
| `dashboard_engine/tests/test_dashboard_studio.py` | Payload `alignment`; Studio header writes |
| `dashboard_engine/static/src/js/studio/dashboard_studio_action.js` | Title & Image + lines editor |
| `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` | Header zone layout |
| `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` | Layout polish if needed |
| `dashboard_engine/__manifest__.py` | Version `19.0.1.0.100` |

---

### Task 1: Model + migration + live arch (Python, TDD)

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (`DashboardBlueprintHeaderItem`, `_header_line_arch`, `_header_arch`, `studio_create_header_item` default kind)
- Create: `dashboard_engine/migrations/19.0.1.0.100/post-header-kind-alignment.py`
- Test: `dashboard_engine/tests/test_dashboard_blueprint.py`

**Interfaces:**
- Consumes: current left/right/subtitle arch
- Produces:
  - `kind ∈ {subtitle, inline}`
  - `alignment ∈ {left, center, right}`
  - Arch placement matrix from the spec
  - Migration SQL/ORM: left→inline+left, right→inline+right, subtitle→subtitle+left

- [ ] **Step 1: Failing tests**

```python
def test_header_kind_inline_alignment_migration_mapping(self):
    """Simulate old kinds via create-then-write as migrator would."""
    bp = self._header_blueprint([])  # existing helper
    Item = self.env["dashboard.blueprint.header.item"]
    # After model change, creating with left must fail or map — prefer explicit migrator unit:
    # Call migrator helper if extracted, OR create rows with SQL in test.
    # Preferred: public helper on blueprint model:
    mapped = self.env["dashboard.blueprint.header.item"]._map_legacy_header_kind("left")
    self.assertEqual(mapped, {"kind": "inline", "alignment": "left"})
    mapped = self.env["dashboard.blueprint.header.item"]._map_legacy_header_kind("right")
    self.assertEqual(mapped, {"kind": "inline", "alignment": "right"})
    mapped = self.env["dashboard.blueprint.header.item"]._map_legacy_header_kind("subtitle")
    self.assertEqual(mapped, {"kind": "subtitle", "alignment": "left"})

def test_header_arch_inline_center_and_subtitle_align(self):
    bp = self._header_blueprint([
        {"kind": "subtitle", "alignment": "center", "field_names": "email"},
        {"kind": "inline", "alignment": "center", "field_names": "phone"},
        {"kind": "inline", "alignment": "right", "field_names": "category_id"},
        {"kind": "inline", "alignment": "left", "icon": "fa-envelope", "field_names": "email"},
    ])
    arch = bp._header_arch()
    self.assertIn("justify-content-center", arch)  # or text-center class chosen in impl
    self.assertIn("dashboard_header_inline_right", arch)  # or existing right tags container
    self.assertIn("fa-envelope", arch)
```

Adjust class names in asserts to match the implementation chosen in Step 3 (document exact classes in the test once written).

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /Users/dharmesh/Applications/odoo/19.0 && \
venv/python3.12.11/bin/python server/odoo-bin \
  -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --test-tags=/dashboard_engine:TestDashboardBlueprint.test_header_kind_inline_alignment_migration_mapping,/dashboard_engine:TestDashboardBlueprint.test_header_arch_inline_center_and_subtitle_align \
  --stop-after-init -u dashboard_engine --http-port=0
```

- [ ] **Step 3: Implement model + arch**

On `dashboard.blueprint.header.item`:

```python
kind = fields.Selection(
    [("subtitle", "Subtitle"), ("inline", "Inline")],
    required=True,
    default="subtitle",
)
alignment = fields.Selection(
    [("left", "Left"), ("center", "Center"), ("right", "Right")],
    required=True,
    default="left",
)

@api.model
def _map_legacy_header_kind(self, old_kind):
    return {
        "left": {"kind": "inline", "alignment": "left"},
        "right": {"kind": "inline", "alignment": "right"},
        "subtitle": {"kind": "subtitle", "alignment": "left"},
        "inline": {"kind": "inline", "alignment": "left"},
    }.get(old_kind, {"kind": "subtitle", "alignment": "left"})
```

Rewrite `_header_line_arch` / `_header_arch`:

- Filter `subtitle` / `inline` instead of left/right  
- `inline + right` → former right tags path  
- `inline + left` → former left (icon)  
- `inline + center` / `subtitle + *` → apply Bootstrap align classes (`justify-content-start|center|end` or `text-start|center|end`) on the line wrapper  

Update `studio_create_header_item` default from `kind or "left"` → `kind or "subtitle"` and set `alignment` default `left`.

Add `_STUDIO_HEADER_WRITE_FIELDS` entry: `alignment`.

Payload header dict includes `alignment`.

- [ ] **Step 4: Migration script**

`dashboard_engine/migrations/19.0.1.0.100/post-header-kind-alignment.py`:

```python
def migrate(cr, version):
    cr.execute("""
        UPDATE dashboard_blueprint_header_item
           SET alignment = COALESCE(alignment, 'left')
         WHERE alignment IS NULL OR alignment = ''
    """)
    # Map legacy kinds — column still holds left/right until selection updated
    cr.execute("""
        UPDATE dashboard_blueprint_header_item
           SET kind = 'inline', alignment = 'left'
         WHERE kind = 'left'
    """)
    cr.execute("""
        UPDATE dashboard_blueprint_header_item
           SET kind = 'inline', alignment = 'right'
         WHERE kind = 'right'
    """)
    cr.execute("""
        UPDATE dashboard_blueprint_header_item
           SET kind = 'subtitle', alignment = COALESCE(NULLIF(alignment, ''), 'left')
         WHERE kind = 'subtitle'
    """)
```

Ensure `__manifest__` version bump happens in Task 5 (or bump early so migration folder matches). Prefer bump in Task 5; name migration folder `19.0.1.0.100` and bump manifest in Task 5 before upgrade.

- [ ] **Step 5: Run tests — PASS** (extend to full header-related TestDashboardBlueprint if needed)

- [ ] **Step 6: Commit only if user asks**

---

### Task 2: Seeds + Advanced form + field chip label

**Files:**
- Modify: all preset `**/data/seed_blueprint_headers.xml` (and any seed using `kind` left/right)
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml`
- Modify: `dashboard_engine/static/src/js/fields/many2many_ordered_tags_field.js` (+ template if tag text comes from display_name)
- Possibly: small `ir.model.fields` inherit **or** load `name` + `field_description` in tag records

**Interfaces:**
- Consumes: Task 1 fields
- Produces: Advanced UI columns; tags show `Job Position (function)`

- [ ] **Step 1: Update seeds**

Replace:

```xml
<field name="kind">left</field>
```

with:

```xml
<field name="kind">inline</field>
<field name="alignment">left</field>
```

and `right` → `inline` + `alignment` `right`. Subtitle rows get `<field name="alignment">left</field>` if missing.

- [ ] **Step 2: Advanced list view**

```xml
<field name="kind"/>
<field name="alignment"/>
<field name="icon" invisible="kind != 'inline' or alignment != 'left'"/>
<field name="field_ids" widget="many2many_ordered_tags"
       options="{'no_create': True, 'separator': False, 'label_format': 'string_name'}"
       domain="[('model', '=', host_model_name)]"/>
<field name="separator" invisible="kind == 'inline' and alignment == 'right' or not has_multiple_fields"/>
```

Tune `separator` invisible rule to match former `kind == 'right'` → `inline and alignment == right`.

- [ ] **Step 3: Tag label format**

In `Many2ManyOrderedTagsField.get tags()` (or equivalent), when `props.label_format === 'string_name'` (pass via `extractProps` from options):

```javascript
const label = record.data.field_description || record.data.display_name;
const tech = record.data.name;
text = tech ? `${label} (${tech})` : label;
```

Ensure Related models load `name` and `field_description` for `ir.model.fields` in the tags field (context / relatedFields).

- [ ] **Step 4: Manual — Advanced CRM Customers Card layout Header shows new columns and chip format**

- [ ] **Step 5: Commit only if user asks**

---

### Task 3: Studio Header zone parity

**Files:**
- Modify: `dashboard_engine/static/src/js/studio/dashboard_studio_action.js`
- Modify: `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml`
- Modify: `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` (optional)
- Test: `dashboard_engine/tests/test_dashboard_studio.py` (payload alignment + write)

**Interfaces:**
- Consumes: payload `headers[].alignment`, whitelist `alignment`, blueprint title/image fields already in `_STUDIO_BP_WRITE_FIELDS`
- Produces: Studio Header UI like Advanced

- [ ] **Step 1: Backend test**

```python
def test_studio_header_payload_has_alignment(self):
    bp = self._studio_blueprint()
    item = bp.header_line_ids[:1]
    if not item:
        item = self.env["dashboard.blueprint.header.item"].create({
            "blueprint_id": bp.id,
            "kind": "inline",
            "alignment": "center",
            "field_names": "email",
        })
    else:
        item.write({"kind": "inline", "alignment": "center"})
    row = next(h for h in bp.get_studio_payload()["headers"] if h["id"] == item.id)
    self.assertEqual(row["alignment"], "center")
    bp.studio_write_header_item(item.id, {"alignment": "right", "kind": "subtitle"})
    self.assertEqual(item.alignment, "right")
    self.assertEqual(item.kind, "subtitle")
```

- [ ] **Step 2: Studio XML — Header zone**

Two blocks:

1. **Title & Image** — selects for `header_title_field` / `header_image_field` from `catalogs.hostFields` (binary filter for image); select for `header_image_style`  
2. **Header Lines** — list like scopes: reorder, kind (subtitle/inline), alignment (left/center/right), icon (if inline+left), multi-field chips with label `string (name)`, Shown as, remove, Add  

Remove old single-editor-only Kind/comma Char as the primary UX (keep quick edit if useful, but list is source of truth).

- [ ] **Step 3: JS wire**

- Hydrate `editor` / per-line state with `alignment`  
- Save title/image via `studio_write_blueprint`  
- Save lines via `studio_write_header_item` / create / unlink / reorder  
- Field chips: multi-select from hostFields showing `f.string + ' (' + f.name + ')'`; store comma `field_names`  

- [ ] **Step 4: Run TestDashboardStudio focused + full if quick**

- [ ] **Step 5: Commit only if user asks**

---

### Task 4: Ship on :19005

**Files:**
- Modify: `dashboard_engine/__manifest__.py` → `"version": "19.0.1.0.100"`

- [ ] **Step 1: Bump version** (triggers migration `19.0.1.0.100`)

- [ ] **Step 2: Upgrade then serve**

```bash
cd /Users/dharmesh/Applications/odoo/19.0
# prefer stop-after-init upgrade, then long-running server (avoids hung -u+http)
venv/python3.12.11/bin/python server/odoo-bin \
  -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  -u dashboard_engine --stop-after-init --http-port=0
pkill -f "config/dashboard_engine_v2.conf" || true
nohup venv/python3.12.11/bin/python server/odoo-bin \
  -c config/dashboard_engine_v2.conf -d dashboard_engine_v2.ee \
  --dev=xml,assets >> /tmp/dashboard_engine_v2_19005.log 2>&1 &
# wait curl http://127.0.0.1:19005/web/login → 200
```

- [ ] **Step 3: Smoke**

- DB: no header rows with kind left/right  
- Advanced Header: Kind/Alignment; chips `Label (name)`  
- Studio Header: Title & Image + lines; center subtitle visible on live CRM card  
- Hard-refresh browser  

- [ ] **Step 4: Commit only if user asks**

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| kind subtitle/inline | T1 |
| alignment on both kinds | T1, T2, T3 |
| Migration left/right | T1, T2 seeds |
| Live arch matrix + center | T1 |
| Advanced form columns | T2 |
| Label (technical_name) chips | T2, T3 |
| Studio Title & Image + lines | T3 |
| Icon only inline+left | T2, T3 |
| Ship :19005 | T4 |

## Explicitly out of plan

| Item | Why |
|------|-----|
| Rename `field_names` | Spec |
| New HEADER_ICONS set | Spec |
| Pixel-perfect Advanced CSS | Spec |

---

## Self-review (plan author)

1. Spec coverage: all locked decisions mapped to tasks.  
2. No TBD placeholders; migration helper + exact seed/XML patterns included.  
3. Names consistent: `alignment`, `inline`, `label_format: 'string_name'`, version `19.0.1.0.100`.
