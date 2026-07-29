# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Blueprint data models and runtime slot/action/graph APIs."""
import hashlib
import json
import logging
import re
from ast import literal_eval
from xml.sax.saxutils import escape as xml_escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.date_utils import get_timedelta
from odoo.tools.safe_eval import safe_eval

from ..tools.many2many_utils import (
    compute_many2many_order,
)

from .dashboard_graph_periods import get_period_year
from .ir_model_fields import GRAPH_CUSTOM_GROUP
from ..tools.date_utils import _get_period_dates
from ..tools.domain_utils import _date_range_to_domain
from ..tools.condition_domain import compile_context_value
from ..tools.relation_path import (
    RelationPathInfo,
    first_hop as relation_first_hop,
    is_direct as relation_path_is_direct,
    validate_path as validate_relation_path,
)

_logger = logging.getLogger(__name__)

SLOT_SECTIONS = [
    ("kpi", "Right · KPIs"),
    ("button_box", "Footer · Totals"),
    ("bottom", "Footer · Shortcuts"),
    ("menu_views", "Manage menu · Views"),
    ("menu_new", "Manage menu · New"),
    ("menu_reports", "Manage menu · Reports"),
]

# Stored driver for what a figure slot puts on the card (KPIs / bottoms).
SLOT_VALUE_MODES = [
    ("count", "Count only"),
    ("amount", "Amount only"),
    ("count_amount", "Count + Amount"),
]

# Sections pooled across share_link_ids (V1 shared-kanban parity).
# Header and left primary button are never shared.
SHARED_SLOT_SECTIONS = frozenset(code for code, _label in SLOT_SECTIONS)

# Mirrors the v1 dashboards: bars stay readable up to five points, beyond that
# a line reads better, and a card never shows more than a dozen groups.
GRAPH_BAR_LIMIT = 6
GRAPH_MAX_GROUPS = 12


GRANULARITIES = [
    ("day", "Day"),
    ("week", "Week"),
    ("month", "Month"),
    ("quarter", "Quarter"),
    ("year", "Year"),
]
AGGREGATORS = [
    ("sum", "Total"),
    ("avg", "Average"),
    ("max", "Maximum"),
    ("min", "Minimum"),
]
DATE_TYPES = ("date", "datetime")
NUMERIC_TYPES = ("integer", "float", "monetary")

# Named by what they mean on a card rather than by their Font Awesome class,
# so the builder never asks anyone to know icon names.
HEADER_ICONS = [
    ("fa-map-marker", "Location"),
    ("fa-envelope", "Email"),
    ("fa-phone", "Phone"),
    ("fa-building", "Company"),
    ("fa-briefcase", "Job"),
    ("fa-user", "Person"),
    ("fa-globe", "Website"),
    ("fa-calendar", "Date"),
    ("fa-tag", "Category"),
    ("fa-barcode", "Reference"),
]
HEADER_SEPARATORS = [
    (", ", "Paris, France"),
    (" at ", "Sales Manager at Acme"),
    (" | ", "Service | Furniture"),
    (" - ", "Acme - Paris"),
    (" ", "Acme Paris"),
]

# Wave F Layout Studio — known Odoo-native card widgets (no free HTML).
STUDIO_LAYOUT_WIDGETS = frozenset(
    {"header", "primary", "graph", "kpis", "totals", "shortcuts", "manage"}
)
# Palette labels — manage is validated if present but always lives in the ⋮ menu,
# never in the card body (classic kanban behaviour).
STUDIO_LAYOUT_WIDGET_LABELS = {
    "header": "Header",
    "primary": "Primary button",
    "graph": "Chart",
    "kpis": "KPIs",
    "totals": "Totals",
    "shortcuts": "Shortcuts",
}
STUDIO_LAYOUT_CARD_WIDGETS = frozenset(
    {"header", "primary", "graph", "kpis", "totals", "shortcuts"}
)


class DashboardBlueprint(models.Model):
    _name = "dashboard.blueprint"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Blueprint"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    key = fields.Char(
        string="Key",
        required=True,
        index=True,
        help="Stable technical key used in generated views and context.",
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        default="draft",
        required=True,
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        help="Who may configure this blueprint in a multi-company database. "
        "Leave empty so every company's dashboard admins share it (the "
        "default — most blueprints are one shared template). Runtime "
        "dashboard DATA is always scoped by the host/graph model's own "
        "multi-company record rules regardless of this field; it only "
        "governs who can see/edit the blueprint *configuration* itself "
        "(see security/dashboard_engine_security.xml).",
    )
    host_model_id = fields.Many2one(
        "ir.model",
        string="Host Model",
        required=True,
        ondelete="cascade",
        help="Model shown as kanban cards (partner, product, warehouse, …).",
    )
    host_model_name = fields.Char(
        related="host_model_id.model",
        store=True,
        readonly=True,
        string="Host Model Name",
    )
    module_depends = fields.Char(
        help="Comma-separated module technical names. Blueprint stays inactive "
        "until all listed modules are installed (soft dependency).",
    )
    menu_name = fields.Char(translate=True, string="Menu Name")
    menu_parent_xmlid = fields.Char(
        string="Parent Menu XML ID",
        help="Optional parent menu xmlid, e.g. crm.crm_menu_root. "
        "Left empty → under Dashboard Engine root.",
    )
    menu_sequence = fields.Integer(default=50, string="Menu Sequence")
    lens_my_enabled = fields.Boolean(string="Show My filter", default=False)
    lens_my_default = fields.Boolean(string="My filter on by default", default=False)
    lens_my_label = fields.Char(string="My filter label")
    lens_kpis_enabled = fields.Boolean(string="Show With KPIs filter", default=False)
    lens_kpis_default = fields.Boolean(string="With KPIs on by default", default=False)
    lens_kpis_label = fields.Char(string="With KPIs filter label")
    primary_button_label = fields.Char(
        translate=True,
        default="Open Analysis",
        string="Button Label",
        help="Label on the primary button beside the graph.",
    )
    primary_action_xmlid = fields.Char(
        string="Action",
        help="Optional existing window/graph action xmlid opened by the left "
        "card button (e.g. crm_enterprise.crm_opportunity_action_dashboard). "
        "If empty, a runtime action is built from the graph settings below.",
    )
    primary_action_domain = fields.Char(
        string="Extra Domain",
        default="[]",
        help="Extra domain merged into the primary action. "
        "Supports {{id}} for the host record id.",
    )
    primary_action_context = fields.Char(
        string="Extra Context",
        default="{}",
        help="Extra context keys merged into the primary action. "
        "Supports {{id}} for the host record id.",
    )
    alternate_action_ids = fields.One2many(
        "dashboard.blueprint.action.variant",
        "blueprint_id",
        string="Alternate Actions",
        copy=True,
        help="Opens a different screen when a listed app is installed, e.g. "
        "an Enterprise dashboard instead of the plain list. The first "
        "variant whose apps are all present wins; otherwise the primary "
        "action above is used.",
    )
    include_child_records = fields.Boolean(
        string="Include Child Records",
        help="When the primary action links back with a single field (no "
        "relation path), also include records under this card's children "
        "(e.g. a company's contacts), not only records linked to this "
        "record itself. Uses the ORM's child_of on that field.",
    )
    primary_label_alt_scope_id = fields.Many2one(
        "dashboard.blueprint.scope",
        string="When this filter is off",
        ondelete="cascade",
        domain="[('blueprint_id', '=', id)]",
        help="Optional settings filter. While it is ticked, the button shows "
        "Button Label; while it is off, Alternate Label is shown.",
    )
    primary_label_alt = fields.Char(
        translate=True,
        string="Alternate Label",
        help="Button label when the selected settings filter is off.",
    )

    # Graph configuration (targets any model — no hard app depends)
    graph_model = fields.Char(
        help="Technical model name for the card graph (e.g. crm.lead)."
    )
    graph_data_field = fields.Char(
        string="Link to Host",
        help="Many2one path on the graph model that points back to this "
        "host record (e.g. partner_id on crm.lead for a customer card, "
        "or product_id.categ_id for a category card). Pick fields in order "
        "with the relation path widget; KPI slots use the same label.",
    )
    graph_relation_path_id = fields.Many2one(
        "dashboard.relation.path",
        string="Relation Path (legacy)",
        ondelete="restrict",
        help="Deprecated: prefer Link to Host. Kept for migration.",
    )
    graph_measure = fields.Char(default="__count")
    graph_groupby = fields.Char(help="Group-by field, e.g. create_date:month")
    graph_domain = fields.Char(
        string="Custom Filter",
        default="[]",
        help="Optional domain on the graph model (Python list), same idea "
        "as Custom Filter on a list or graph view.",
    )
    graph_caption = fields.Char(translate=True, string="Graph Title")

    # Source of truth for the builder (same chrome as the live ⚙️ popup):
    # one ordered Group By tag list. First tag = top level; each next tag is
    # a deeper split. Primary/extra columns below stay as one-way mirrors so
    # runtime / seeds / tests that still touch them keep working.
    graph_groupby_ids = fields.Many2many(
        "ir.model.fields",
        "dashboard_blueprint_groupby_rel",
        "blueprint_id",
        "field_id",
        string="Group By",
        help="Choose how the graph should group the data. Add several "
        "fields in order (for example Created on, then Stage) — the first "
        "is the top level, each next tag is a deeper split.",
    )
    ordered_graph_groupby_ids = fields.Char(
        help="Machine-written selection order for Group By tags."
    )
    graph_groupby_has_date = fields.Boolean(
        compute="_compute_graph_groupby_has_date",
        help="Deprecated UI helper; date buckets are chosen via virtual tags.",
    )
    graph_groupby_allowed_field_ids = fields.Many2many(
        "ir.model.fields",
        compute="_compute_graph_groupby_allowed_field_ids",
        help="Group By picker domain: stored non-dates + virtual "
        "x_<date>_<period> tags (v1-style, generated per graph model).",
    )

    # Compat mirrors of graph_groupby_ids (first tag / rest). Written from the
    # unified list — not a second source of truth for the builder UI.
    # Ordered multi-level group-by (H3): extras after the primary. Date
    # fields here always bucket by month (no per-level granularity picker).
    graph_groupby_extra_ids = fields.Many2many(
        "ir.model.fields",
        "dashboard_blueprint_groupby_extra_rel",
        "blueprint_id",
        "field_id",
        string="Then split by",
        help="Mirror of Group By tags after the first. Prefer the unified "
        "Group By control on Configuration.",
    )
    ordered_graph_groupby_extra_ids = fields.Char(
        help="Machine-written selection order for the tags above."
    )

    _GRAPH_GROUPBY_LEGACY_KEYS = (
        "graph_groupby",
        "graph_groupby_field_id",
        "graph_groupby_granularity",
        "graph_groupby_extra_ids",
        "ordered_graph_groupby_extra_ids",
    )
    # Dual date-row filters (H4): blueprint defaults for the settings popup's
    # Creation Date / Closed Date columns. Viewers only pick months/years;
    # which date fields those columns bind to is configured here.
    period_field_id = fields.Many2one(
        "ir.model.fields",
        string="Creation Date",
        ondelete="set null",
        help="Default date/datetime field for the settings popup's "
        "Creation Date month/year filters (e.g. create_date).",
    )
    closed_period_field_id = fields.Many2one(
        "ir.model.fields",
        string="Closed Date",
        ondelete="set null",
        help="Optional default for the second date-filter row in the settings "
        "popup (e.g. date_closed / Closed Date, alongside Creation Date).",
    )

    # Card header: the block above the graph. Technical mirrors, pickers below.
    header_image_field = fields.Char()
    header_title_field = fields.Char(default="display_name")

    header_image_field_id = fields.Many2one(
        "ir.model.fields",
        string="Image",
        compute="_compute_header_image_field_id",
        inverse="_inverse_header_image_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Image shown at the top left of the card. Leave empty for none.",
    )
    header_image_style = fields.Selection(
        [
            ("avatar", "Fit the whole picture (logos, avatars)"),
            ("cover", "Fill the square, cropping edges (photos)"),
        ],
        default="avatar",
    )
    header_title_field_id = fields.Many2one(
        "ir.model.fields",
        string="Title",
        compute="_compute_header_title_field_id",
        inverse="_inverse_header_title_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Big bold line at the top of the card. Defaults to the record name.",
    )
    header_line_ids = fields.One2many(
        "dashboard.blueprint.header.item",
        "blueprint_id",
        string="Header Lines",
        copy=True,
    )

    @api.depends("header_image_field", "host_model_name")
    def _compute_header_image_field_id(self):
        for rec in self:
            rec.header_image_field_id = rec._mirror_field(
                rec.host_model_name, rec.header_image_field
            )

    def _inverse_header_image_field_id(self):
        for rec in self:
            rec.header_image_field = rec.header_image_field_id.name or False

    @api.depends("header_title_field", "host_model_name")
    def _compute_header_title_field_id(self):
        for rec in self:
            rec.header_title_field_id = rec._mirror_field(
                rec.host_model_name, rec.header_title_field
            )

    def _inverse_header_title_field_id(self):
        for rec in self:
            rec.header_title_field = rec.header_title_field_id.name or False

    # ------------------------------------------------------------------
    # Configuration pickers.
    #
    # Each is stored, computed from its technical mirror above and writing
    # back to it, so the blueprint can be configured by picking records while
    # the runtime keeps reading plain technical names. See dashboard_mirror.py
    # for why both halves exist.
    # ------------------------------------------------------------------

    graph_model_id = fields.Many2one(
        "ir.model",
        string="Graph Model",
        compute="_compute_graph_model_id",
        inverse="_inverse_graph_model_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Records counted on the card graph, e.g. Leads for a customer card.",
    )
    graph_data_field_id = fields.Many2one(
        "ir.model.fields",
        string="Link to Host",
        compute="_compute_graph_data_field_id",
        inverse="_inverse_graph_data_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Many2one on the graph model that links a counted row to this "
        "host. Prefer the relation path control on Configuration.",
    )
    graph_groupby_field_id = fields.Many2one(
        "ir.model.fields",
        string="Split by",
        compute="_compute_graph_groupby",
        inverse="_inverse_graph_groupby",
        store=True,
        readonly=False,
        ondelete="set null",
    )
    graph_groupby_granularity = fields.Selection(
        GRANULARITIES,
        string="Per",
        compute="_compute_graph_groupby",
        inverse="_inverse_graph_groupby",
        store=True,
        readonly=False,
        help="Only for date fields: the size of each bar.",
    )
    graph_groupby_is_date = fields.Boolean(
        compute="_compute_graph_groupby_is_date",
        help="Drives whether a granularity has to be chosen.",
    )
    graph_measure_field_id = fields.Many2one(
        "ir.model.fields",
        string="Measures",
        compute="_compute_graph_measure",
        inverse="_inverse_graph_measure",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Leave empty to count records.",
    )
    graph_measure_aggregator = fields.Selection(
        AGGREGATORS,
        string="Measured as",
        # No default: on a stored editable computed field a default counts as
        # a user-supplied value, which runs the inverse instead of the compute
        # and would wipe the measure on create. The compute falls back to sum.
        compute="_compute_graph_measure",
        inverse="_inverse_graph_measure",
        store=True,
        readonly=False,
    )
    module_ids = fields.Many2many(
        "ir.module.module",
        string="Required Apps",
        compute="_compute_module_ids",
        inverse="_inverse_module_ids",
        store=True,
        readonly=False,
        help="The dashboard stays hidden until every listed app is installed.",
    )
    menu_parent_id = fields.Many2one(
        "ir.ui.menu",
        string="Parent Menu",
        compute="_compute_menu_parent_id",
        inverse="_inverse_menu_parent_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Leave empty to place the dashboard under Dashboard Engine.",
    )
    primary_action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Action",
        compute="_compute_primary_action_id",
        inverse="_inverse_primary_action_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Existing screen opened by the card's main button. Leave empty "
        "to build one from the graph settings.",
    )

    @api.depends("graph_model")
    def _compute_graph_model_id(self):
        for rec in self:
            rec.graph_model_id = rec._mirror_model(rec.graph_model)

    def _inverse_graph_model_id(self):
        for rec in self:
            rec.graph_model = rec.graph_model_id.model or False

    @api.depends("graph_data_field", "graph_model")
    def _compute_graph_data_field_id(self):
        for rec in self:
            rec.graph_data_field_id = rec._mirror_field(
                rec.graph_model, rec.graph_data_field
            )

    def _inverse_graph_data_field_id(self):
        for rec in self:
            rec.graph_data_field = rec.graph_data_field_id.name or False

    @api.depends("graph_groupby", "graph_model")
    def _compute_graph_groupby(self):
        for rec in self:
            name, _sep, granularity = (rec.graph_groupby or "").partition(":")
            rec.graph_groupby_field_id = rec._mirror_field(rec.graph_model, name)
            rec.graph_groupby_granularity = granularity or False

    def _inverse_graph_groupby(self):
        for rec in self:
            field = rec.graph_groupby_field_id
            if not field:
                rec.graph_groupby = False
                continue
            granularity = (
                rec.graph_groupby_granularity if field.ttype in DATE_TYPES else False
            )
            rec.graph_groupby = (
                "%s:%s" % (field.name, granularity) if granularity else field.name
            )

    @api.depends("graph_groupby_field_id.ttype")
    def _compute_graph_groupby_is_date(self):
        for rec in self:
            rec.graph_groupby_is_date = (
                rec.graph_groupby_field_id.ttype in DATE_TYPES
            )

    @api.depends("graph_groupby_ids", "ordered_graph_groupby_ids")
    def _compute_graph_groupby_has_date(self):
        for rec in self:
            ordered = rec._ordered_graph_groupby_fields()
            rec.graph_groupby_has_date = any(
                f.ttype in DATE_TYPES or f.is_date_period() for f in ordered
            )

    @api.depends("graph_model", "graph_model_id")
    def _compute_graph_groupby_allowed_field_ids(self):
        Fields = self.env["ir.model.fields"]
        for rec in self:
            model = rec.graph_model or (
                rec.graph_model_id.model if rec.graph_model_id else False
            )
            rec.graph_groupby_allowed_field_ids = (
                Fields.dashboard_groupby_allowed_fields(model)
            )

    @api.onchange("graph_groupby_ids")
    def _onchange_graph_groupby_ids(self):
        for rec in self:
            rec.ordered_graph_groupby_ids = compute_many2many_order(
                rec.graph_groupby_ids.ids,
                rec.ordered_graph_groupby_ids,
            )
            rec._apply_legacy_graph_groupby_mirror_on_cache()

    @api.model
    def _field_to_groupby_spec(self, field, period_hint="month"):
        """Turn a Group By tag into a read_group spec (v1 virtual-aware)."""
        if not field:
            return False
        if field.is_date_period():
            return field.get_date_period() or False
        if field.ttype in DATE_TYPES:
            period = period_hint if period_hint in GRAPH_CUSTOM_GROUP else "month"
            return "%s:%s" % (field.name, period)
        return field.name

    def _primary_period_hint(self):
        """Granularity encoded in ``graph_groupby`` (e.g. create_date:year)."""
        self.ensure_one()
        _name, _sep, gran = (self.graph_groupby or "").partition(":")
        if gran in GRAPH_CUSTOM_GROUP:
            return gran
        if self.graph_groupby_granularity in GRAPH_CUSTOM_GROUP:
            return self.graph_groupby_granularity
        return "month"

    @api.model
    def _normalize_groupby_fields_to_period_tags_for_model(
        self, model_name, fields_ordered, period_hint="month"
    ):
        """Replace raw date tags with virtual ``x_<date>_<period>`` tags."""
        Fields = self.env["ir.model.fields"]
        if not model_name:
            return list(fields_ordered)
        Fields.ensure_date_period_fields(model_name)
        normalized = []
        first_date = True
        for field in fields_ordered:
            if field.is_date_period():
                normalized.append(field)
                continue
            if field.ttype in DATE_TYPES:
                period = period_hint if first_date else "month"
                first_date = False
                virtual = Fields.period_field_for(model_name, field.name, period)
                normalized.append(virtual if virtual else field)
                continue
            normalized.append(field)
        return normalized

    def _normalize_groupby_fields_to_period_tags(self, fields_ordered, period_hint="month"):
        self.ensure_one()
        model = self.graph_model or (
            self.graph_model_id.model if self.graph_model_id else False
        )
        return self._normalize_groupby_fields_to_period_tags_for_model(
            model, fields_ordered, period_hint=period_hint
        )

    @api.onchange("graph_groupby_extra_ids")
    def _onchange_graph_groupby_extra_ids(self):
        for rec in self:
            rec.ordered_graph_groupby_extra_ids = compute_many2many_order(
                rec.graph_groupby_extra_ids.ids,
                rec.ordered_graph_groupby_extra_ids,
            )

    def _parse_ordered_field_ids(self, order_char, records):
        """Preserve user tag order from a comma-separated id list."""
        self.ensure_one()
        try:
            ordered_ids = [
                int(v) for v in (order_char or "").split(",") if v.strip()
            ]
        except ValueError:
            ordered_ids = []
        by_id = {f.id: f for f in records}
        ordered = [by_id[i] for i in ordered_ids if i in by_id]
        ordered += [f for f in records if f.id not in ordered_ids]
        return ordered

    def _ordered_graph_groupby_fields(self):
        """All Group By levels in unified tag order."""
        self.ensure_one()
        if not self.graph_groupby_ids:
            return self.env["ir.model.fields"]
        return self.env["ir.model.fields"].browse(
            [
                f.id
                for f in self._parse_ordered_field_ids(
                    self.ordered_graph_groupby_ids, self.graph_groupby_ids
                )
            ]
        )

    def _ordered_groupby_extra_fields(self):
        """Extras after the primary, in tag order."""
        self.ensure_one()
        if self.graph_groupby_ids:
            return list(self._ordered_graph_groupby_fields())[1:]
        return self._parse_ordered_field_ids(
            self.ordered_graph_groupby_extra_ids, self.graph_groupby_extra_ids
        )

    def _groupby_specs_from_fields(self, fields_ordered, period_hint="month"):
        """Build read_group specs; first raw date uses ``period_hint``."""
        specs = []
        first_date = True
        for field in fields_ordered:
            if field.is_date_period():
                spec = self._field_to_groupby_spec(field)
                if spec:
                    specs.append(spec)
                continue
            if field.ttype in DATE_TYPES:
                hint = period_hint if first_date else "month"
                first_date = False
                spec = self._field_to_groupby_spec(field, period_hint=hint)
            else:
                spec = self._field_to_groupby_spec(field)
            if spec:
                specs.append(spec)
        return specs

    def _groupby_all_specs(self):
        """Ordered read_group specs from the unified Group By tag list."""
        self.ensure_one()
        return self._groupby_specs_from_fields(
            self._ordered_graph_groupby_fields(),
            period_hint=self._primary_period_hint(),
        )

    def _groupby_extra_specs(self):
        """Extra group-by levels (after the primary one) in read_group form."""
        self.ensure_one()
        specs = self._groupby_all_specs()
        if specs:
            return specs[1:]
        return self._groupby_specs_from_fields(
            self._ordered_groupby_extra_fields(),
            period_hint="month",
        )

    def _legacy_graph_groupby_mirror_vals(self):
        """Vals that project the unified list onto primary + extras mirrors."""
        self.ensure_one()
        ordered = list(self._ordered_graph_groupby_fields())
        primary = ordered[0] if ordered else False
        extras = ordered[1:]
        graph_groupby = (
            self._field_to_groupby_spec(
                primary, period_hint=self._primary_period_hint()
            )
            if primary
            else False
        )
        # Only write the technical char + extras. Do NOT write
        # graph_groupby_granularity / graph_groupby_field_id — those are
        # stored computes with an inverse that would re-enter write().
        return {
            "graph_groupby": graph_groupby,
            "graph_groupby_extra_ids": [(6, 0, [f.id for f in extras])],
            "ordered_graph_groupby_extra_ids": (
                ",".join(str(f.id) for f in extras) or False
            ),
        }

    def _apply_legacy_graph_groupby_mirror_on_cache(self):
        """Onchange helper: update legacy mirrors on the UI cache only."""
        for rec in self:
            ordered = rec._parse_ordered_field_ids(
                rec.ordered_graph_groupby_ids, rec.graph_groupby_ids
            )
            primary = ordered[0] if ordered else self.env["ir.model.fields"]
            if primary:
                rec.graph_groupby = rec._field_to_groupby_spec(
                    primary, period_hint=rec._primary_period_hint()
                )
                if not primary.is_date_period() and primary.ttype not in DATE_TYPES:
                    rec.graph_groupby_granularity = False
            else:
                rec.graph_groupby = False
            extras = ordered[1:]
            rec.graph_groupby_extra_ids = [(6, 0, [f.id for f in extras])]
            rec.ordered_graph_groupby_extra_ids = (
                ",".join(str(f.id) for f in extras) or False
            )

    def _unified_graph_groupby_vals_from_legacy(self, force=False):
        """Vals to lift primary + extras into the unified tag list."""
        self.ensure_one()
        if self.graph_groupby_ids and not force:
            return {}
        primary = self.graph_groupby_field_id
        extras = self._parse_ordered_field_ids(
            self.ordered_graph_groupby_extra_ids, self.graph_groupby_extra_ids
        )
        ordered = ([primary] + list(extras)) if primary else list(extras)
        if not ordered:
            return {}
        return {
            "graph_groupby_ids": [(6, 0, [f.id for f in ordered])],
            "ordered_graph_groupby_ids": ",".join(str(f.id) for f in ordered),
        }

    def _mirror_legacy_graph_groupby_from_unified(self):
        """Persist primary/extra mirrors from the unified tag list (one-way)."""
        for rec in self:
            rec.with_context(dashboard_groupby_mirroring=True).write(
                rec._legacy_graph_groupby_mirror_vals()
            )

    def _ensure_unified_graph_groupby(self):
        """Heal rows that still only have legacy primary/extra filled."""
        for rec in self:
            if rec.graph_groupby_ids:
                continue
            if not (rec.graph_groupby_field_id or rec.graph_groupby_extra_ids):
                continue
            vals = rec._unified_graph_groupby_vals_from_legacy(force=True)
            if vals:
                rec.with_context(dashboard_groupby_mirroring=True).write(vals)
                rec.with_context(dashboard_groupby_mirroring=True).write(
                    rec._legacy_graph_groupby_mirror_vals()
                )

    def _normalize_unified_graph_groupby_period_tags(self):
        """Swap raw date Group By tags for virtual x_<date>_<period> tags."""
        for rec in self:
            if not rec.graph_model and not rec.graph_model_id:
                continue
            ordered = list(rec._ordered_graph_groupby_fields())
            if not ordered:
                continue
            normalized = rec._normalize_groupby_fields_to_period_tags(
                ordered, period_hint=rec._primary_period_hint()
            )
            if [f.id for f in normalized] == [f.id for f in ordered]:
                continue
            rec.with_context(dashboard_groupby_mirroring=True).write(
                {
                    "graph_groupby_ids": [(6, 0, [f.id for f in normalized])],
                    "ordered_graph_groupby_ids": ",".join(
                        str(f.id) for f in normalized
                    ),
                }
            )
            rec.with_context(dashboard_groupby_mirroring=True).write(
                rec._legacy_graph_groupby_mirror_vals()
            )

    @api.model
    def _heal_unified_graph_groupby_blueprints(self):
        """Batch-heal blueprints on registry load (idempotent)."""
        candidates = self.search(
            [
                "|",
                ("graph_groupby_ids", "!=", False),
                "|",
                ("graph_groupby_field_id", "!=", False),
                ("graph_groupby_extra_ids", "!=", False),
            ]
        )
        if candidates:
            candidates._ensure_unified_graph_groupby()
            candidates._normalize_unified_graph_groupby_period_tags()
        # Ensure virtual period tags exist for every published graph model.
        Fields = self.env["ir.model.fields"]
        for model_name in {
            m
            for m in self.search([]).mapped("graph_model")
            if m
        }:
            Fields.ensure_date_period_fields(model_name)

    @api.depends("graph_measure", "graph_model")
    def _compute_graph_measure(self):
        for rec in self:
            raw = rec.graph_measure or "__count"
            name, _sep, aggregator = raw.partition(":")
            if raw == "__count":
                rec.graph_measure_field_id = False
                rec.graph_measure_aggregator = rec.graph_measure_aggregator or "sum"
                continue
            rec.graph_measure_field_id = rec._mirror_field(rec.graph_model, name)
            rec.graph_measure_aggregator = aggregator or "sum"

    def _inverse_graph_measure(self):
        for rec in self:
            if not rec.graph_measure_field_id:
                rec.graph_measure = "__count"
                continue
            rec.graph_measure = "%s:%s" % (
                rec.graph_measure_field_id.name,
                rec.graph_measure_aggregator or "sum",
            )

    @api.depends("module_depends")
    def _compute_module_ids(self):
        Module = self.env["ir.module.module"].sudo()
        for rec in self:
            names = rec._mirror_names(rec.module_depends)
            rec.module_ids = Module.search([("name", "in", names)]) if names else False

    def _inverse_module_ids(self):
        for rec in self:
            rec.module_depends = ",".join(sorted(rec.module_ids.mapped("name"))) or False

    @api.depends("menu_parent_xmlid")
    def _compute_menu_parent_id(self):
        for rec in self:
            rec.menu_parent_id = rec._mirror_record(
                "ir.ui.menu", rec.menu_parent_xmlid
            )

    def _inverse_menu_parent_id(self):
        for rec in self:
            rec.menu_parent_xmlid = rec._mirror_xmlid(rec.menu_parent_id)

    @api.depends("primary_action_xmlid")
    def _compute_primary_action_id(self):
        for rec in self:
            rec.primary_action_id = rec._mirror_record(
                "ir.actions.act_window", rec.primary_action_xmlid
            )

    def _inverse_primary_action_id(self):
        for rec in self:
            rec.primary_action_xmlid = rec._mirror_xmlid(rec.primary_action_id)

    health_issue_count = fields.Integer(compute="_compute_health")
    health_message = fields.Text(compute="_compute_health")

    @api.depends(
        "graph_model",
        "graph_model_id",
        "graph_data_field",
        "graph_data_field_id",
        "menu_parent_xmlid",
        "menu_parent_id",
        "primary_action_xmlid",
        "primary_action_id",
        "slot_ids.compute_model",
        "slot_ids.compute_model_id",
        "slot_ids.action_xmlid",
        "slot_ids.action_id",
        "slot_ids.groups_xmlids",
        "slot_ids.group_ids",
        "alternate_action_ids.action_xmlid",
        "alternate_action_ids.action_id",
        "alternate_action_ids.module_depends",
    )
    def _compute_health(self):
        for rec in self:
            issues = rec._health_issues()
            rec.health_issue_count = len(issues)
            rec.health_message = "\n".join(issues)

    def _action_xmlid_exists(self, xmlid):
        """True when *xmlid* resolves to any action (window, client, server, …).

        Slot/primary pickers are typed as ``ir.actions.act_window`` for the
        UI; soft-deps may still open client actions (e.g. follow-up report).
        Health must accept those too.
        """
        if not xmlid or "." not in xmlid:
            return False
        return bool(self.env.ref(xmlid, raise_if_not_found=False))

    def _health_issues(self):
        """References recorded in the mirrors whose target is gone.

        A mirror without a resolved picker means the blueprint points at
        something this database no longer has — usually an uninstalled app.
        """
        self.ensure_one()
        issues = []
        checks = [
            (self.graph_model, self.graph_model_id, _("Chart model")),
            (self.graph_data_field, self.graph_data_field_id, _("Link to Host")),
            (self.menu_parent_xmlid, self.menu_parent_id, _("Parent menu")),
        ]
        for mirror, picker, label in checks:
            if mirror and not picker:
                issues.append(_("%(label)s: %(ref)s is missing.", label=label, ref=mirror))
        if self.primary_action_xmlid and not self._action_xmlid_exists(
            self.primary_action_xmlid
        ):
            issues.append(
                _(
                    "%(label)s: %(ref)s is missing.",
                    label=_("Main card button action"),
                    ref=self.primary_action_xmlid,
                )
            )

        for variant in self.alternate_action_ids:
            if not self._modules_installed(variant.module_depends):
                continue
            # Picker is act_window-only; runtime accepts any ir.actions.* xmlid.
            if variant.action_xmlid and not self._action_xmlid_exists(
                variant.action_xmlid
            ):
                issues.append(
                    _(
                        "Alternate primary action %(name)s opens %(ref)s, "
                        "which is missing.",
                        name=variant.name or variant.action_xmlid,
                        ref=variant.action_xmlid,
                    )
                )

        for slot in self.slot_ids:
            # Soft-dep items are hidden at runtime until their apps exist —
            # do not treat their unresolved mirrors as blueprint breakage.
            if not self._modules_installed(slot.module_depends):
                continue
            if slot.compute_model and not slot.compute_model_id:
                issues.append(
                    _(
                        "Item %(slot)s counts %(ref)s, which is missing.",
                        slot=slot.name or slot.key,
                        ref=slot.compute_model,
                    )
                )
            if (
                slot.action_xmlid
                and not slot.action_method
                and not self._action_xmlid_exists(slot.action_xmlid)
            ):
                issues.append(
                    _(
                        "Item %(slot)s opens %(ref)s, which is missing.",
                        slot=slot.name or slot.key,
                        ref=slot.action_xmlid,
                    )
                )
            missing_groups = set(
                slot._mirror_names(slot.groups_xmlids)
            ) - set(slot._mirror_names(slot._mirror_xmlids(slot.group_ids)))
            for group in sorted(missing_groups):
                issues.append(
                    _(
                        "Item %(slot)s is limited to group %(ref)s, which is missing.",
                        slot=slot.name or slot.key,
                        ref=group,
                    )
                )
        if self.lens_my_enabled and not (self.lens_my_label or "").strip():
            issues.append(_("My filter is on: set My filter label."))
        if self.lens_my_enabled and not self._lens_can_resolve_my():
            issues.append(_("My filter cannot resolve for this host/graph."))
        if self.lens_kpis_enabled and not (self.lens_kpis_label or "").strip():
            issues.append(_("With KPIs filter is on: set With KPIs filter label."))
        return issues

    def action_health_check(self):
        self.ensure_one()
        if not self.health_issue_count:
            message = _("Every reference in this blueprint resolves.")
            kind = "success"
        else:
            message = self.health_message
            kind = "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Blueprint health"),
                "message": message,
                "type": kind,
                "sticky": bool(self.health_issue_count),
            },
        }

    def _resolve_mirrors(self):
        """Re-resolve pickers from their mirrors.

        Uninstalling a module empties the pickers through ``ondelete``, while
        the mirrors keep the technical names. Running this at boot means a
        blueprint repairs itself once the module is installed again, without
        anyone reconfiguring it.
        """
        for rec in self:
            broken = (
                (rec.graph_model and not rec.graph_model_id)
                or (
                    rec.graph_data_field
                    and "." not in rec.graph_data_field
                    and not rec.graph_data_field_id
                )
                or (rec.menu_parent_xmlid and not rec.menu_parent_id)
                or (rec.primary_action_xmlid and not rec.primary_action_id)
            )
            if broken:
                rec.modified(
                    [
                        "graph_model",
                        "graph_data_field",
                        "graph_groupby",
                        "graph_measure",
                        "menu_parent_xmlid",
                        "primary_action_xmlid",
                    ]
                )
                rec.flush_recordset()

    # Master O2M (all sections). Used by runtime, export, copy, and Technical.
    # Form pages use the section-specific O2Ms below — same inverse, filtered
    # domains — so the UI does not bind one field six times.
    slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="All Slots",
        copy=True,
    )
    kpi_slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="Right · KPIs",
        domain=[("section", "=", "kpi")],
        copy=False,
    )
    button_box_slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="Footer · Totals",
        domain=[("section", "=", "button_box")],
        copy=False,
    )
    bottom_slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="Footer · Shortcuts",
        domain=[("section", "=", "bottom")],
        copy=False,
    )
    menu_views_slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="Manage menu · Views",
        domain=[("section", "=", "menu_views")],
        copy=False,
    )
    menu_new_slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="Manage menu · New",
        domain=[("section", "=", "menu_new")],
        copy=False,
    )
    menu_reports_slot_ids = fields.One2many(
        "dashboard.blueprint.slot",
        "blueprint_id",
        string="Manage menu · Reports",
        domain=[("section", "=", "menu_reports")],
        copy=False,
    )
    share_link_ids = fields.Many2many(
        "dashboard.blueprint",
        "dashboard_blueprint_share_rel",
        "blueprint_id",
        "share_id",
        string="Share Links With",
        help="Pool card links with other dashboards on the same host model "
        "(bi-directional).\n"
        "Shared: Manage menu (Views / New / Reports), Right · KPIs, "
        "Footer · Totals, Footer · Shortcuts.\n"
        "Not shared: Header, Primary button, Configuration (scopes / graph / "
        "filters), Menu entry, and this blueprint’s own identity.\n"
        "Each shared link still respects its Required Apps and access groups.",
    )
    scope_ids = fields.One2many(
        "dashboard.blueprint.scope", "blueprint_id", string="Scopes", copy=True
    )
    pref_ids = fields.One2many(
        "dashboard.user.pref", "blueprint_id", string="User preferences"
    )
    studio_layout = fields.Json(
        string="Studio Layout",
        help="Wave F page grid (JSON). Empty uses the classic fixed card shell.",
    )

    generated_view_id = fields.Many2one("ir.ui.view", readonly=True, copy=False)
    generated_search_view_id = fields.Many2one(
        "ir.ui.view", readonly=True, copy=False
    )
    generated_action_id = fields.Many2one(
        "ir.actions.act_window", readonly=True, copy=False
    )
    generated_menu_id = fields.Many2one("ir.ui.menu", readonly=True, copy=False)
    generated_arch_hash = fields.Char(
        readonly=True,
        copy=False,
        help="Fingerprint of the generated kanban arch, so boot-time "
        "reconciliation only rewrites views that actually changed.",
    )

    _dashboard_blueprint_key_uniq = models.Constraint(
        "UNIQUE(key)",
        "Blueprint key must be unique.",
    )

    @api.constrains("share_link_ids", "host_model_id")
    def _check_share_same_host(self):
        for rec in self:
            for other in rec.share_link_ids:
                if (
                    rec.host_model_id
                    and other.host_model_id
                    and other.host_model_id != rec.host_model_id
                ):
                    raise ValidationError(
                        _(
                            "Cannot share links between %(a)s and %(b)s: "
                            "they use different host models.",
                            a=rec.display_name,
                            b=other.display_name,
                        )
                    )

    @api.constrains("key")
    def _check_key(self):
        for rec in self:
            if not rec.key or not rec.key.replace("_", "").isalnum():
                raise ValidationError(
                    _("Blueprint key must be alphanumeric/underscore.")
                )

    @api.constrains(
        "lens_my_enabled",
        "lens_my_label",
        "lens_kpis_enabled",
        "lens_kpis_label",
    )
    def _check_lens_labels(self):
        for rec in self:
            if rec.lens_my_enabled and not (rec.lens_my_label or "").strip():
                raise ValidationError(_("My filter is on: set My filter label."))
            if rec.lens_kpis_enabled and not (rec.lens_kpis_label or "").strip():
                raise ValidationError(
                    _("With KPIs filter is on: set With KPIs filter label.")
                )

    @api.constrains(
        "graph_data_field",
        "graph_relation_path_id",
        "graph_model",
        "host_model_name",
    )
    def _check_graph_relation_path(self):
        for rec in self:
            path_str, source = rec._resolve_graph_path_string()
            if not path_str:
                continue
            if not source or not rec.host_model_name:
                continue
            validate_relation_path(
                rec.env, source, path_str, rec.host_model_name
            )

    def _resolve_graph_path_string(self):
        """Return ``(dotted_path, source_model)`` for the chart link.

        Legacy ``graph_relation_path_id`` wins when set (pre-migration).
        Otherwise use ``graph_data_field``.
        """
        self.ensure_one()
        legacy = self.graph_relation_path_id
        if legacy and legacy.domain_field:
            return legacy.domain_field, legacy.source_model or self.graph_model
        if self.graph_data_field:
            return self.graph_data_field, self.graph_model
        return False, False

    @api.model
    def _modules_installed_static(self, module_csv):
        """Return True when every listed module is installed (or list empty).

        Results are memoized on the cursor for the request so a card page
        with many soft-dep slots does not re-query ``ir.module.module``.
        """
        names = tuple(
            sorted(
                n.strip()
                for n in (module_csv or "").split(",")
                if n and n.strip()
            )
        )
        if not names:
            return True
        cache = self.env.cr.cache.setdefault("dashboard_engine.modules_installed", {})
        if names in cache:
            return cache[names]
        Module = self.env["ir.module.module"].sudo()
        installed = set(
            Module.search(
                [("name", "in", list(names)), ("state", "=", "installed")]
            ).mapped("name")
        )
        result = set(names).issubset(installed)
        cache[names] = result
        return result

    def _modules_installed(self, module_csv):
        self.ensure_one()
        return self._modules_installed_static(module_csv)

    def _is_runtime_active(self):
        self.ensure_one()
        return (
            self.active
            and self.state == "published"
            and self.host_model_name in self.env
            and self._modules_installed(self.module_depends)
        )

    def action_publish(self):
        for rec in self:
            if not rec.host_model_id:
                raise UserError(_("Select a host model before publishing."))
            rec.state = "published"
            rec._sync_generated_artifacts()
        return True

    def action_unpublish(self):
        self.write({"state": "draft"})
        for rec in self:
            rec._sync_generated_artifacts()
        return True

    def action_open_studio(self):
        """Open Dashboard Studio client action for this blueprint."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "dashboard_engine.studio",
            "name": _("Dashboard Studio"),
            "params": {"blueprint_id": self.id},
            "context": {
                "active_id": self.id,
                "active_model": self._name,
            },
        }

    # ------------------------------------------------------------------
    # Dashboard Studio — payload + guided writes + catalogs
    # ------------------------------------------------------------------

    _STUDIO_SLOT_FIELDS = (
        "id",
        "key",
        "name",
        "section",
        "sequence",
        "label",
        "label_plural",
        "icon",
        "style",
        "show_if_zero",
        "action_xmlid",
        "action_method",
        "action_model",
        "amount_field",
        "count_field",
        "compute_model",
        "relate_field",
        "compute_domain",
        "value_mode",
        "module_depends",
        "action_context",
    )
    _STUDIO_SLOT_WRITE_FIELDS = frozenset(
        {
            "label",
            "label_plural",
            "icon",
            "style",
            "show_if_zero",
            "action_xmlid",
            "action_method",
            "action_model",
            "amount_field",
            "count_field",
            "compute_model",
            "relate_field",
            "compute_domain",
            "value_mode",
            "module_depends",
            "name",
            "sequence",
            "condition_ids",
            "action_context",
        }
    )
    _STUDIO_BP_WRITE_FIELDS = frozenset(
        {
            "primary_button_label",
            "primary_action_xmlid",
            "primary_action_context",
            "graph_caption",
            "graph_measure",
            "graph_groupby",
            "graph_groupby_field_ids",
            "graph_measure_field_id",
            "graph_measure_aggregator",
            "graph_data_field",
            "graph_domain",
            "period_field_id",
            "closed_period_field_id",
            "include_child_records",
            "header_title_field",
            "header_image_field",
            "header_image_style",
            # Setup mode (Dashboard + Menu)
            "host_model_id",
            "menu_name",
            "menu_parent_id",
            "menu_sequence",
            "company_id",
            "module_ids",
            "share_link_ids",
        }
    )
    _STUDIO_HEADER_WRITE_FIELDS = frozenset(
        {"sequence", "kind", "alignment", "icon", "field_names", "separator"}
    )
    _STUDIO_SCOPE_WRITE_FIELDS = frozenset(
        {"name", "description", "mode", "domain", "default_on", "sequence"}
    )

    def _studio_slot_dict(self, slot):
        data = {f: slot[f] for f in self._STUDIO_SLOT_FIELDS}
        data["condition_ids"] = slot.condition_ids.ids
        data["condition_names"] = slot.condition_ids.mapped("name")
        return data

    def get_studio_payload(self):
        """JSON-friendly snapshot for the Studio OWL client action."""
        self.ensure_one()
        slots = [
            self._studio_slot_dict(slot)
            for slot in self.slot_ids.sorted(
                lambda s: (s.section or "", s.sequence, s.id)
            )
        ]
        headers = []
        for item in self.header_line_ids.sorted("sequence"):
            ka = item._effective_kind_alignment()
            headers.append(
                {
                    "id": item.id,
                    "sequence": item.sequence,
                    "kind": ka["kind"],
                    "alignment": ka["alignment"],
                    "icon": item.icon or False,
                    "field_names": item.field_names or "",
                    "separator": item.separator or False,
                }
            )
        scopes = []
        for scope in self.scope_ids.sorted("sequence"):
            scopes.append(
                {
                    "id": scope.id,
                    "name": scope.name,
                    "description": scope.description or False,
                    "mode": scope.mode,
                    "domain": scope.domain or "[]",
                    "default_on": scope.default_on,
                    "sequence": scope.sequence,
                }
            )
        ordered_groupby = list(self._ordered_graph_groupby_fields())
        return {
            "id": self.id,
            "name": self.name,
            "key": self.key,
            "state": self.state,
            "host_model": self.host_model_name or "",
            "host_model_id": self.host_model_id.id or False,
            "host_model_label": self.host_model_id.name or self.host_model_name or "",
            "host_editable": self.state == "draft",
            "menu_name": self.menu_name or "",
            "menu_parent_id": self.menu_parent_id.id or False,
            "menu_parent_name": self.menu_parent_id.display_name or "",
            "menu_sequence": self.menu_sequence,
            "company_id": self.company_id.id or False,
            "company_name": self.company_id.display_name or "",
            "module_ids": self.module_ids.ids,
            "module_names": self.module_ids.mapped("display_name"),
            "share_link_ids": self.share_link_ids.ids,
            "share_link_names": self.share_link_ids.mapped("display_name"),
            "generated_menu_name": self.generated_menu_id.display_name or "",
            "multi_company": self.env.user.has_group("base.group_multi_company"),
            "primary_button_label": self.primary_button_label or "",
            "primary_action_xmlid": self.primary_action_xmlid or "",
            "primary_action_context": self.primary_action_context or "{}",
            "graph_caption": self.graph_caption or "",
            "graph_model": self.graph_model or "",
            "graph_measure": self.graph_measure or "",
            "graph_groupby": self.graph_groupby or "",
            "graph_groupby_field_ids": [f.id for f in ordered_groupby],
            "graph_groupby_field_names": [f.name for f in ordered_groupby],
            "graph_measure_field_id": self.graph_measure_field_id.id or False,
            "graph_measure_aggregator": self.graph_measure_aggregator or False,
            "graph_data_field": self.graph_data_field or "",
            "graph_domain": self.graph_domain or "[]",
            "period_field_id": self.period_field_id.id or False,
            "closed_period_field_id": self.closed_period_field_id.id or False,
            "include_child_records": bool(self.include_child_records),
            "header_title_field": self.header_title_field or "",
            "header_image_field": self.header_image_field or "",
            "header_image_style": self.header_image_style or "avatar",
            "slots": slots,
            "headers": headers,
            "scopes": scopes,
            "advanced_action_xmlid": "dashboard_engine.action_dashboard_blueprint",
            "layout": self.studio_layout or self._default_studio_layout(),
            "layout_is_custom": bool(self.studio_layout),
            "layout_widget_labels": dict(STUDIO_LAYOUT_WIDGET_LABELS),
        }

    @api.model
    def _default_studio_layout(self):
        """Classic card composition as Layout Studio schema v1."""
        return {
            "version": 1,
            "rows": [
                {
                    "id": "r_header",
                    "cols": [
                        {
                            "id": "c_header",
                            "span": 12,
                            "widget": {"type": "header"},
                        }
                    ],
                },
                {
                    "id": "r_main",
                    "cols": [
                        {
                            "id": "c_primary",
                            "span": 7,
                            "widget": {"type": "primary"},
                        },
                        {
                            "id": "c_kpis",
                            "span": 5,
                            "widget": {"type": "kpis"},
                        },
                    ],
                },
                {
                    "id": "r_graph",
                    "cols": [
                        {
                            "id": "c_graph",
                            "span": 12,
                            "widget": {"type": "graph"},
                        }
                    ],
                },
                {
                    "id": "r_footer",
                    "cols": [
                        {
                            "id": "c_totals",
                            "span": 6,
                            "widget": {"type": "totals"},
                        },
                        {
                            "id": "c_shortcuts",
                            "span": 6,
                            "widget": {"type": "shortcuts"},
                        },
                    ],
                },
            ],
        }

    @api.model
    def studio_default_layout(self):
        """Public RPC for Layout Studio Reset."""
        return self._default_studio_layout()

    def _validate_studio_layout(self, layout):
        """Raise UserError if layout is not a valid Wave F schema."""
        if not layout:
            return
        if not isinstance(layout, dict):
            raise UserError(_("Layout must be a JSON object."))
        if layout.get("version") != 1:
            raise UserError(_("Unsupported layout version."))
        rows = layout.get("rows")
        if not isinstance(rows, list) or not rows:
            raise UserError(_("Layout needs at least one row."))
        seen_types = set()
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                raise UserError(_("Each layout row needs an id."))
            cols = row.get("cols") or []
            if not isinstance(cols, list) or not cols:
                raise UserError(_("Each layout row needs at least one column."))
            span_sum = 0
            for col in cols:
                if not isinstance(col, dict) or not col.get("id"):
                    raise UserError(_("Each layout column needs an id."))
                try:
                    span = int(col.get("span") or 0)
                except (TypeError, ValueError) as exc:
                    raise UserError(_("Column span must be an integer.")) from exc
                if span < 1 or span > 12:
                    raise UserError(_("Column span must be between 1 and 12."))
                span_sum += span
                widget = col.get("widget") or {}
                wtype = widget.get("type")
                if wtype == "richtext":
                    # Reserved hook — ignored at publish time in Wave F.
                    continue
                if wtype not in STUDIO_LAYOUT_WIDGETS:
                    raise UserError(_("Unknown layout widget: %s") % wtype)
                if wtype in seen_types:
                    raise UserError(
                        _("Widget “%s” can only appear once on the page.")
                        % STUDIO_LAYOUT_WIDGET_LABELS.get(wtype, wtype)
                    )
                seen_types.add(wtype)
            if span_sum < 1 or span_sum > 12:
                raise UserError(
                    _("Row “%s”: column spans must add up to at most 12 (got %s).")
                    % (row.get("id"), span_sum)
                )

    def studio_write_layout(self, layout):
        """Persist Layout Studio grid (or clear with falsy layout)."""
        self.ensure_one()
        if not layout:
            self.studio_layout = False
        else:
            # Drop empty draft rows so Save after “Add row” alone does not fail.
            if isinstance(layout, dict) and isinstance(layout.get("rows"), list):
                layout = {
                    **layout,
                    "rows": [
                        row
                        for row in layout["rows"]
                        if isinstance(row, dict) and (row.get("cols") or [])
                    ],
                }
            self._validate_studio_layout(layout)
            self.studio_layout = layout
        return self.get_studio_payload()

    def _studio_model_has_field(self, model_name, field_name):
        if not model_name or not field_name or model_name not in self.env:
            return False
        return field_name in self.env[model_name]._fields

    def _studio_cleanup_after_host_change(self):
        """Clear invalid host-tied refs after host model change. Returns count."""
        self.ensure_one()
        host = self.host_model_name
        cleared = 0
        bp_vals = {}
        if self.header_title_field and not self._studio_model_has_field(
            host, self.header_title_field
        ):
            bp_vals["header_title_field"] = False
            cleared += 1
        if self.header_image_field and not self._studio_model_has_field(
            host, self.header_image_field
        ):
            bp_vals["header_image_field"] = False
            cleared += 1
        if bp_vals:
            self.write(bp_vals)
        for item in self.header_line_ids:
            names = [
                n.strip()
                for n in (item.field_names or "").split(",")
                if n.strip()
            ]
            kept = [n for n in names if self._studio_model_has_field(host, n)]
            if kept != names:
                cleared += len(names) - len(kept)
                item.write({"field_names": ",".join(kept) or False})
        for slot in self.slot_ids:
            slot_vals = {}
            model_name = slot.compute_model or host
            if slot.count_field and not self._studio_model_has_field(
                model_name, slot.count_field
            ):
                slot_vals["count_field"] = False
                cleared += 1
            if slot.amount_field and not self._studio_model_has_field(
                model_name, slot.amount_field
            ):
                slot_vals["amount_field"] = False
                cleared += 1
            if slot_vals:
                slot.write(slot_vals)
        bad_links = self.share_link_ids.filtered(
            lambda o: o.host_model_id != self.host_model_id
        )
        if bad_links:
            cleared += len(bad_links)
            self.write({"share_link_ids": [(3, link.id) for link in bad_links]})
        return cleared

    def _studio_validate_graph_domain(self, domain_str):
        """Reject invalid Custom Filter strings on Studio writes."""
        if domain_str in (False, None, ""):
            return "[]"
        if isinstance(domain_str, (list, tuple)):
            domain_str = str(list(domain_str))
        if not isinstance(domain_str, str):
            raise UserError(_("Custom Filter must be a valid Python domain list."))
        self._safe_domain(domain_str, strict=True)
        return domain_str

    def studio_write_blueprint(self, vals):
        """Write a whitelist of blueprint fields from Studio."""
        self.ensure_one()
        clean = {}
        for key, value in (vals or {}).items():
            if key not in self._STUDIO_BP_WRITE_FIELDS:
                continue
            if key in ("module_ids", "share_link_ids"):
                ids = value if isinstance(value, (list, tuple)) else []
                clean[key] = [(6, 0, [int(i) for i in ids if i])]
            elif key == "host_model_id":
                if self.state == "published":
                    raise UserError(
                        _(
                            "Unpublish to change the host model, or use Advanced."
                        )
                    )
                clean[key] = int(value) if value else False
            elif key in ("menu_parent_id", "company_id"):
                clean[key] = int(value) if value else False
            elif key in ("period_field_id", "closed_period_field_id"):
                clean[key] = int(value) if value else False
            elif key == "menu_sequence":
                clean[key] = int(value or 0)
            elif key == "graph_domain":
                clean[key] = self._studio_validate_graph_domain(value)
            elif key == "include_child_records":
                clean[key] = bool(value)
            elif key == "graph_groupby_field_ids":
                ids = [int(i) for i in (value or []) if i]
                clean["graph_groupby_ids"] = [(6, 0, ids)]
                clean["ordered_graph_groupby_ids"] = ",".join(str(i) for i in ids)
            elif key == "graph_measure_field_id":
                clean[key] = int(value) if value else False
            elif key == "graph_measure_aggregator":
                clean[key] = value or False
            else:
                clean[key] = value
        old_host = self.host_model_id.id
        if clean:
            mirror_groupby = "graph_groupby_ids" in clean
            self.write(clean)
            if mirror_groupby:
                self._mirror_legacy_graph_groupby_from_unified()
        cleanup_count = 0
        if (
            "host_model_id" in clean
            and clean.get("host_model_id")
            and clean["host_model_id"] != old_host
        ):
            cleanup_count = self._studio_cleanup_after_host_change()
        payload = self.get_studio_payload()
        payload["setup_cleanup_count"] = cleanup_count
        return payload

    def _studio_prepare_slot_vals(self, vals):
        clean = {}
        for key, value in (vals or {}).items():
            if key not in self._STUDIO_SLOT_WRITE_FIELDS:
                continue
            if key == "condition_ids":
                ids = value if isinstance(value, (list, tuple)) else []
                clean[key] = [(6, 0, [int(i) for i in ids])]
            else:
                clean[key] = value
        return clean

    def studio_write_slot(self, slot_id, vals):
        self.ensure_one()
        slot = self.slot_ids.filtered(lambda s: s.id == slot_id)[:1]
        if not slot:
            raise UserError(_("Unknown slot on this dashboard."))
        clean = self._studio_prepare_slot_vals(vals)
        if clean:
            slot.write(clean)
        return self.get_studio_payload()

    def studio_create_slot(self, section, vals=None):
        self.ensure_one()
        if section not in dict(SLOT_SECTIONS):
            raise UserError(_("Unknown card section: %s") % section)
        vals = dict(vals or {})
        clean = self._studio_prepare_slot_vals(vals)
        seq = (
            max(
                self.slot_ids.filtered(lambda s: s.section == section).mapped(
                    "sequence"
                )
                or [0]
            )
            + 10
        )
        key = vals.get("key") or "studio_%s_%s" % (section, seq)
        label = clean.get("label") or clean.get("name") or _("New item")
        slot_vals = {
            "blueprint_id": self.id,
            "section": section,
            "sequence": seq,
            "key": key,
            "name": clean.get("name") or label,
            "label": label,
            "show_if_zero": clean.get("show_if_zero", True),
            "style": clean.get("style") or "default",
            "value_mode": clean.get("value_mode") or "count",
        }
        # Sensible defaults so Publish does not create a dead KPI/shortcut.
        if section in ("kpi", "bottom") and not clean.get("compute_model") and not clean.get(
            "count_field"
        ):
            host = self.host_model_name or "res.partner"
            slot_vals.update(
                {
                    "compute_model": host,
                    "compute_domain": "[]",
                    "action_model": host,
                    "label_plural": clean.get("label_plural") or label,
                    "show_if_zero": True,
                }
            )
        if section == "button_box" and not clean.get("amount_field") and not clean.get(
            "count_field"
        ):
            # Host identity count is a safe placeholder until the admin picks a field.
            slot_vals["count_field"] = "id"
            slot_vals["value_mode"] = "count"
        slot_vals.update(clean)
        created = self.env["dashboard.blueprint.slot"].create(slot_vals)
        payload = self.get_studio_payload()
        payload["created_slot_id"] = created.id
        return payload

    def studio_unlink_slot(self, slot_id):
        self.ensure_one()
        slot = self.slot_ids.filtered(lambda s: s.id == slot_id)[:1]
        if slot:
            slot.unlink()
        return self.get_studio_payload()

    def studio_reorder_slots(self, section, ordered_ids):
        """Rewrite sequence for slots in ``section`` to match ``ordered_ids``."""
        self.ensure_one()
        if section not in dict(SLOT_SECTIONS):
            raise UserError(_("Unknown card section: %s") % section)
        ordered_ids = [int(i) for i in (ordered_ids or [])]
        slots = self.slot_ids.filtered(lambda s: s.section == section)
        by_id = {s.id: s for s in slots}
        if set(ordered_ids) != set(by_id):
            raise UserError(_("Slot list is out of date. Reload Studio and try again."))
        for index, slot_id in enumerate(ordered_ids):
            by_id[slot_id].sequence = (index + 1) * 10
        return self.get_studio_payload()

    def studio_write_header_item(self, item_id, vals):
        self.ensure_one()
        item = self.header_line_ids.filtered(lambda h: h.id == item_id)[:1]
        if not item:
            raise UserError(_("Unknown header line on this dashboard."))
        clean = {
            key: value
            for key, value in (vals or {}).items()
            if key in self._STUDIO_HEADER_WRITE_FIELDS
        }
        if clean:
            item.write(clean)
        return self.get_studio_payload()

    def studio_create_header_item(self, vals=None):
        self.ensure_one()
        vals = dict(vals or {})
        clean = {
            key: value
            for key, value in vals.items()
            if key in self._STUDIO_HEADER_WRITE_FIELDS
        }
        seq = max(self.header_line_ids.mapped("sequence") or [0]) + 10
        created = self.env["dashboard.blueprint.header.item"].create(
            {
                "blueprint_id": self.id,
                "sequence": clean.get("sequence", seq),
                "kind": clean.get("kind") or "subtitle",
                "alignment": clean.get("alignment") or "left",
                "icon": clean.get("icon") or False,
                "field_names": clean.get("field_names") or "",
                "separator": clean.get("separator") or False,
            }
        )
        payload = self.get_studio_payload()
        payload["created_header_id"] = created.id
        return payload

    def studio_unlink_header_item(self, item_id):
        self.ensure_one()
        item = self.header_line_ids.filtered(lambda h: h.id == item_id)[:1]
        if item:
            item.unlink()
        return self.get_studio_payload()

    def studio_reorder_headers(self, ordered_ids):
        self.ensure_one()
        ordered_ids = [int(i) for i in (ordered_ids or [])]
        items = self.header_line_ids
        by_id = {h.id: h for h in items}
        if set(ordered_ids) != set(by_id):
            raise UserError(
                _("Header list is out of date. Reload Studio and try again.")
            )
        for index, item_id in enumerate(ordered_ids):
            by_id[item_id].sequence = (index + 1) * 10
        return self.get_studio_payload()

    def studio_write_scope(self, scope_id, vals):
        self.ensure_one()
        scope = self.scope_ids.filtered(lambda s: s.id == scope_id)[:1]
        if not scope:
            raise UserError(_("Unknown scope on this dashboard."))
        clean = {}
        for key, value in (vals or {}).items():
            if key not in self._STUDIO_SCOPE_WRITE_FIELDS:
                continue
            if key == "domain":
                clean["domain"] = self._studio_validate_graph_domain(value)
            elif key == "mode":
                if value not in ("include", "restrict"):
                    raise UserError(_("Invalid scope mode."))
                clean["mode"] = value
            elif key == "default_on":
                clean["default_on"] = bool(value)
            elif key == "sequence":
                clean["sequence"] = int(value)
            elif key == "name":
                name = (value or "").strip()
                if not name:
                    raise UserError(_("Scope name is required."))
                clean["name"] = name
            elif key == "description":
                clean["description"] = value or False
        if clean:
            scope.write(clean)
        return self.get_studio_payload()

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
        created = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": self.id,
                "name": name,
                "description": vals.get("description") or False,
                "mode": mode,
                "domain": domain,
                "default_on": bool(vals.get("default_on")),
                "sequence": int(vals.get("sequence") or seq),
            }
        )
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
            raise UserError(
                _("Scope list is out of date. Reload Studio and try again.")
            )
        for index, scope_id in enumerate(ordered_ids):
            by_id[scope_id].sequence = (index + 1) * 10
        return self.get_studio_payload()

    def studio_search_actions(self, term="", limit=20):
        """Return window actions for Studio pickers (xmlid + label)."""
        self.ensure_one()
        limit = min(int(limit or 20), 50)
        Action = self.env["ir.actions.act_window"]
        domain = [("name", "ilike", term or "")]
        actions = Action.search(domain, limit=limit, order="name")
        result = []
        for action in actions:
            xmlid = action.get_external_id().get(action.id) or ""
            if not xmlid:
                continue
            result.append(
                {
                    "id": action.id,
                    "xmlid": xmlid,
                    "name": action.display_name or action.name,
                    "res_model": action.res_model or "",
                }
            )
        return result

    def studio_search_models(self, term="", limit=20):
        """ir.model picker for Setup host model."""
        self.ensure_one()
        limit = min(int(limit or 20), 50)
        domain = [("transient", "=", False)]
        if term:
            domain = [
                "&",
                ("transient", "=", False),
                "|",
                ("name", "ilike", term),
                ("model", "ilike", term),
            ]
        models = self.env["ir.model"].search(domain, limit=limit, order="name")
        return [
            {
                "id": m.id,
                "name": m.name,
                "model": m.model,
            }
            for m in models
        ]

    def studio_search_menus(self, term="", limit=20):
        """Parent menu picker for Setup."""
        self.ensure_one()
        limit = min(int(limit or 20), 50)
        domain = [("name", "ilike", term or "")] if term else []
        menus = self.env["ir.ui.menu"].search(domain, limit=limit, order="name, id")
        return [
            {"id": m.id, "name": m.complete_name or m.display_name or m.name}
            for m in menus
        ]

    def studio_search_modules(self, term="", limit=20):
        """Required apps picker for Setup."""
        self.ensure_one()
        limit = min(int(limit or 20), 50)
        domain = []
        if term:
            domain = [
                "|",
                ("shortdesc", "ilike", term),
                ("name", "ilike", term),
            ]
        modules = self.env["ir.module.module"].search(domain, limit=limit, order="shortdesc")
        return [
            {
                "id": m.id,
                "name": m.shortdesc or m.display_name or m.name,
                "technical": m.name,
            }
            for m in modules
        ]

    def studio_search_share_blueprints(self, term="", limit=20):
        """Share-link picker: other blueprints on the same host model."""
        self.ensure_one()
        limit = min(int(limit or 20), 50)
        domain = [
            ("id", "!=", self.id),
            ("host_model_id", "=", self.host_model_id.id),
        ]
        if term:
            domain = [
                "&",
                ("id", "!=", self.id),
                ("host_model_id", "=", self.host_model_id.id),
                "|",
                ("name", "ilike", term),
                ("key", "ilike", term),
            ]
        blueprints = self.search(domain, limit=limit, order="name")
        return [
            {"id": bp.id, "name": bp.display_name or bp.name, "key": bp.key}
            for bp in blueprints
        ]

    def studio_search_companies(self, term="", limit=20):
        """Company picker for Setup (multi-company)."""
        self.ensure_one()
        limit = min(int(limit or 20), 50)
        domain = [("name", "ilike", term or "")] if term else []
        companies = self.env["res.company"].search(domain, limit=limit, order="name")
        return [{"id": c.id, "name": c.display_name or c.name} for c in companies]

    @api.model
    def studio_search_groups(self, term="", limit=20):
        """Group picker for friendly action-context (xmlid + label)."""
        limit = min(int(limit or 20), 50)
        Group = self.env["res.groups"]
        domain = []
        if term:
            domain = [
                "|",
                ("name", "ilike", term),
                ("full_name", "ilike", term),
            ]
        groups = Group.search(domain, limit=limit, order="name")
        xmlids = groups.get_external_id()
        rows = []
        for group in groups:
            xmlid = xmlids.get(group.id) or ""
            if not xmlid:
                continue
            rows.append(
                {
                    "id": group.id,
                    "name": group.full_name or group.display_name or group.name,
                    "xmlid": xmlid,
                }
            )
        return rows

    @api.model
    def studio_group_labels(self, xmlids=None):
        """Map group xmlids → human labels for Action defaults UI."""
        result = {}
        for xmlid in xmlids or []:
            if not xmlid or not isinstance(xmlid, str):
                continue
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group and group._name == "res.groups":
                result[xmlid] = group.full_name or group.display_name or group.name
            else:
                result[xmlid] = xmlid
        return result

    def studio_model_fields(self, model_name=None, ttypes=None):
        """Field catalog for host / graph / compute model pickers."""
        self.ensure_one()
        model_name = model_name or self.host_model_name
        if not model_name or model_name not in self.env:
            return []
        Model = self.env[model_name]
        wanted = set(ttypes) if ttypes else None
        fields_meta = Model.fields_get()
        rows = []
        for name, meta in fields_meta.items():
            if name.startswith("_"):
                continue
            ttype = meta.get("type")
            if wanted and ttype not in wanted:
                continue
            if meta.get("deprecated"):
                continue
            rows.append(
                {
                    "name": name,
                    "string": meta.get("string") or name,
                    "ttype": ttype,
                    "relation": meta.get("relation") or False,
                }
            )
        rows.sort(key=lambda r: (r["string"] or "").lower())
        return rows

    def studio_condition_catalog(self, model=None):
        """Reusable conditions for Studio KPI/shortcut pickers.

        When ``model`` is set (slot compute model), only return matching
        conditions — same filter Advanced uses on ``condition_ids``.
        """
        self.ensure_one()
        domain = []
        if model:
            domain = [("model", "=", model)]
        conditions = self.env["dashboard.condition"].search(domain, order="name")
        return [
            {"id": c.id, "name": c.name, "model": c.model or ""}
            for c in conditions
        ]

    def studio_header_icons(self):
        self.ensure_one()
        return [{"value": value, "label": label} for value, label in HEADER_ICONS]

    def studio_sample_records(self, term="", limit=20):
        """Host records for the Studio live preview picker."""
        self.ensure_one()
        model_name = self.host_model_name
        if not model_name or model_name not in self.env:
            return []
        limit = min(int(limit or 20), 40)
        Model = self.env[model_name]
        if term:
            return [
                {"id": row[0], "name": row[1]}
                for row in Model.name_search(term, operator="ilike", limit=limit)
            ]
        records = Model.search([], limit=limit, order="id desc")
        return [{"id": rec.id, "name": rec.display_name} for rec in records]

    def studio_preview_payload(self, res_id=None):
        """Live card snapshot for one host record (Wave D)."""
        self.ensure_one()
        empty = {
            "ok": False,
            "res_id": False,
            "res_name": "",
            "title": "",
            "header_lines": [],
            "primary_label": self.primary_button_label or "",
            "graph_caption": self.graph_caption or "",
            "slots": self._empty_slots_payload(),
            "graph_bars": [],
            "graph_type": False,
            "graph_json": False,
        }
        model_name = self.host_model_name
        if not model_name or model_name not in self.env:
            return empty
        Model = self.env[model_name]
        if res_id:
            record = Model.browse(int(res_id)).exists()
        else:
            record = Model.search([], limit=1, order="id desc")
        if not record:
            return empty

        title_field = self.header_title_field or "display_name"
        title = record.display_name
        if title_field in record._fields:
            raw = record[title_field]
            if isinstance(raw, models.BaseModel):
                title = raw.display_name
            elif raw:
                title = raw

        header_lines = []
        for item in self.header_line_ids.sorted("sequence"):
            names = [
                name.strip()
                for name in (item.field_names or "").split(",")
                if name.strip()
            ]
            values = []
            for name in names:
                if name not in record._fields:
                    continue
                raw = record[name]
                if isinstance(raw, models.BaseModel):
                    text = raw.display_name if raw else ""
                else:
                    text = str(raw) if raw not in (False, None) else ""
                if text:
                    values.append(text)
            sep = item.separator or ", "
            ka = item._effective_kind_alignment()
            header_lines.append(
                {
                    "id": item.id,
                    "kind": ka["kind"],
                    "alignment": ka["alignment"],
                    "icon": item.icon or False,
                    "text": sep.join(values),
                    "field_names": item.field_names or ",".join(names),
                }
            )

        graph_bars = []
        graph_type = False
        graph_json = False
        if self._has_graph():
            try:
                payloads = self._build_graph_payloads(record)
                payload = payloads.get(record.id) or {}
                graph_type = payload.get("type") or False
                raw_json = payload.get("json") or ""
                if raw_json:
                    graph_json = raw_json if isinstance(raw_json, str) else json.dumps(raw_json)
                    data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                    values = data.get("values") or data.get("data") or []
                    if isinstance(values, list):
                        nums = []
                        for row in values[:8]:
                            if isinstance(row, dict):
                                nums.append(
                                    float(
                                        row.get("value")
                                        or row.get("count")
                                        or row.get("y")
                                        or 0
                                    )
                                )
                            elif isinstance(row, (int, float)):
                                nums.append(float(row))
                        peak = max(nums) if nums else 0
                        graph_bars = [
                            int(round((n / peak) * 100)) if peak else 0 for n in nums
                        ]
            except Exception:
                graph_bars = []
                graph_json = False

        return {
            "ok": True,
            "res_id": record.id,
            "res_name": record.display_name,
            "title": title,
            "header_lines": header_lines,
            "primary_label": self._resolved_primary_label()
            or self.primary_button_label
            or "",
            "graph_caption": self.graph_caption or "",
            "slots": self._build_slots_payload(record),
            "graph_bars": graph_bars,
            "graph_type": graph_type,
            "graph_json": graph_json,
        }

    def write(self, vals):
        """Unified Group By is the builder write path; legacy columns mirror it.

        Legacy-only writes (seeds / tests / RPC) are accepted: applied, then
        lifted into ``graph_groupby_ids`` and re-mirrored so storage stays
        coherent. Context ``dashboard_groupby_mirroring`` skips re-entry when
        the mirror helpers write the technical columns.
        """
        vals = dict(vals)
        if self.env.context.get("dashboard_groupby_mirroring"):
            res = super().write(vals)
            self._sync_artifacts_after_write(vals)
            return res

        unified_touched = (
            "graph_groupby_ids" in vals or "ordered_graph_groupby_ids" in vals
        )
        legacy_touched = any(k in vals for k in self._GRAPH_GROUPBY_LEGACY_KEYS)

        if legacy_touched and not unified_touched:
            res = super().write(vals)
            for rec in self:
                unified = rec._unified_graph_groupby_vals_from_legacy(force=True)
                if unified:
                    rec.with_context(dashboard_groupby_mirroring=True).write(unified)
                rec.with_context(dashboard_groupby_mirroring=True).write(
                    rec._legacy_graph_groupby_mirror_vals()
                )
            if "share_link_ids" in vals:
                self._sync_share_link_symmetric()
            self._sync_artifacts_after_write(vals)
            return res

        res = super().write(vals)
        if unified_touched:
            self._mirror_legacy_graph_groupby_from_unified()
        if "share_link_ids" in vals:
            self._sync_share_link_symmetric()
        self._sync_artifacts_after_write(vals)
        return res

    def _sync_artifacts_after_write(self, vals):
        """Keep generated artifacts in sync when published blueprints change."""
        sync_fields = {
            "name",
            "key",
            "active",
            "state",
            "host_model_id",
            "menu_name",
            "menu_parent_xmlid",
            "menu_sequence",
            "primary_button_label",
            "primary_action_xmlid",
            "primary_action_domain",
            "primary_action_context",
            "graph_caption",
            "module_depends",
            "header_title_field",
            "header_image_field",
            "header_image_style",
            "header_line_ids",
            "studio_layout",
            "lens_my_enabled",
            "lens_my_default",
            "lens_my_label",
            "lens_kpis_enabled",
            "lens_kpis_default",
            "lens_kpis_label",
        }
        if sync_fields.intersection(vals):
            for rec in self.filtered(lambda b: b.state == "published"):
                rec._sync_generated_artifacts()

    @api.onchange("name")
    def _onchange_name_suggest_key(self):
        """Fill a stable key from the title when the user has not set one."""
        if self.name and not self.key:
            self.key = self._suggest_key(self.name)

    @api.model
    def _suggest_key(self, name):
        """``CRM Customers`` → ``crm_customers`` (unique-ish, ASCII)."""
        slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
        return slug or "dashboard"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("key") and vals.get("name"):
                vals["key"] = self._suggest_key(vals["name"])
        records = super().create(vals_list)
        # Seeds / RPC often set graph_groupby (+ extras) only. After create,
        # computed field mirrors are filled — lift into the unified tag list.
        # If the caller already passed graph_groupby_ids, re-mirror down so
        # primary/extra stay coherent.
        records.filtered("graph_groupby_ids")._mirror_legacy_graph_groupby_from_unified()
        records._ensure_unified_graph_groupby()
        records.filtered("share_link_ids")._sync_share_link_symmetric()
        for rec in records.filtered(lambda b: b.state == "published"):
            rec._sync_generated_artifacts()
        return records

    def unlink(self):
        views = self.mapped("generated_view_id") | self.mapped(
            "generated_search_view_id"
        )
        actions = self.mapped("generated_action_id")
        menus = self.mapped("generated_menu_id")
        res = super().unlink()
        menus.unlink()
        actions.unlink()
        views.unlink()
        return res

    # ------------------------------------------------------------------
    # Artifact generation
    # ------------------------------------------------------------------

    def _register_hook(self):
        """Reconcile generated artifacts once the full registry is available.

        ``ir.module.write()`` fires part-way through module loading, when
        models owned by modules that load after this one are not in the
        registry yet. Blueprints hosted on those models are skipped there and
        picked up here, where every model is guaranteed to exist.
        """
        res = super()._register_hook()
        for blueprint in self.sudo().search([]):
            try:
                blueprint._resolve_mirrors()
                blueprint.slot_ids._resolve_slot_mirrors()
                blueprint.alternate_action_ids._resolve_stale_mirrors(
                    [("action_id", ("action_xmlid",))]
                )
                if blueprint._artifacts_need_sync():
                    blueprint._sync_generated_artifacts()
            except Exception:
                _logger.warning(
                    "Dashboard engine: artifact sync failed for blueprint %s",
                    blueprint.key,
                    exc_info=True,
                )
        self._seed_crm_multigroupby_dualdate_defaults()
        self._seed_crm_scope_presentation_defaults()
        self.sudo()._heal_unified_graph_groupby_blueprints()
        self.env["dashboard.user.pref"].sudo()._heal_unified_groupby_prefs()
        return res

    def _seed_crm_multigroupby_dualdate_defaults(self):
        """H3/H4 defaults for the seeded CRM Customers blueprint.

        Runs on every registry rebuild (safe/idempotent, like the mirror
        self-heal above) rather than only from a migration, so it also
        applies when ``crm`` is installed after ``dashboard_engine`` — the
        seed XML cannot ``ref=`` CRM's fields directly since it must still
        load with CRM absent (soft dependency).
        """
        blueprint = self.sudo().search([("key", "=", "crm_customers")], limit=1)
        if not blueprint or "crm.lead" not in self.env:
            return
        try:
            Fields = self.env["ir.model.fields"].sudo()
            vals = {}
            if not blueprint.graph_groupby_extra_ids:
                deadline = Fields.search(
                    [("model", "=", "crm.lead"), ("name", "=", "date_deadline")],
                    limit=1,
                )
                if deadline:
                    vals["graph_groupby_extra_ids"] = [(6, 0, deadline.ids)]
                    vals["ordered_graph_groupby_extra_ids"] = str(deadline.id)
            if not blueprint.period_field_id:
                created = Fields.search(
                    [("model", "=", "crm.lead"), ("name", "=", "create_date")],
                    limit=1,
                )
                if created:
                    vals["period_field_id"] = created.id
            if not blueprint.closed_period_field_id:
                closed = Fields.search(
                    [("model", "=", "crm.lead"), ("name", "=", "date_closed")],
                    limit=1,
                )
                if closed:
                    vals["closed_period_field_id"] = closed.id
            if vals:
                blueprint.write(vals)
        except Exception:
            _logger.warning(
                "Dashboard engine: CRM multi-groupby/dual-date seed failed",
                exc_info=True,
            )

    def _seed_crm_scope_presentation_defaults(self):
        """Fill CRM Customers scope help / label variants when still blank.

        Seed XML is ``noupdate``; this keeps upgraded databases in sync with
        the presentation data without hardcoding anything into the gear form.
        Only touches empty description / missing label-variant rows.
        """
        get_ref = self.env.ref
        try:
            pipeline = get_ref(
                "dashboard_engine.scope_crm_pipeline", raise_if_not_found=False
            )
            leads = get_ref(
                "dashboard_engine.scope_crm_leads", raise_if_not_found=False
            )
            mine = get_ref(
                "dashboard_engine.scope_crm_mine", raise_if_not_found=False
            )
        except Exception:
            return
        if pipeline and not pipeline.description:
            pipeline.description = (
                "Include opportunity-related records in the dashboard analysis."
            )
        if leads and not leads.description:
            leads.description = (
                "Include lead-related records in the dashboard analysis."
            )
        # Gear order: restrict first (own row), then include pair — widget
        # packs include scopes two-across from sequence alone.
        if mine and mine.sequence >= 20:
            mine.sequence = 10
        if pipeline and pipeline.sequence < 20:
            pipeline.sequence = 20
        if leads and leads.sequence < 30:
            leads.sequence = 30
        if not mine:
            return
        if mine.name in (False, "Only mine"):
            mine.name = "My Pipeline"
        if not mine.description:
            mine.description = "Show only opportunities that are assigned to you."
        Label = self.env["dashboard.blueprint.scope.label"].sudo()
        variants = [
            (
                "sale",
                10,
                "My Pipeline and Sales Orders",
                "Check this box to show opportunities and sales orders "
                "you are responsible for.",
            ),
            (
                "sale,website_sale",
                20,
                "My Pipeline, Sales and Website Orders",
                "Check this box to show opportunities, sales and website "
                "orders you are responsible for.",
            ),
        ]
        # Heal older seeds that keyed variants on sale_management.
        for label in mine.label_ids.filtered(
            lambda l: "sale_management" in (l.module_depends or "")
        ):
            label.module_depends = (label.module_depends or "").replace(
                "sale_management", "sale"
            )
        for module_depends, sequence, name, description in variants:
            existing = mine.label_ids.filtered(
                lambda l, m=module_depends: (l.module_depends or "") == m
            )[:1]
            if existing:
                continue
            Label.create(
                {
                    "scope_id": mine.id,
                    "sequence": sequence,
                    "module_depends": module_depends,
                    "name": name,
                    "description": description,
                }
            )

    def _artifacts_need_sync(self):
        """Whether generated artifacts are missing or out of date."""
        self.ensure_one()
        if not self._is_runtime_active():
            return bool(self.generated_menu_id.active)
        if not (
            self.generated_view_id
            and self.generated_action_id
            and self.generated_menu_id
        ):
            return True
        return self.generated_arch_hash != self._kanban_arch_hash()

    def _kanban_arch_hash(self):
        self.ensure_one()
        return hashlib.sha256(self._kanban_arch().encode()).hexdigest()

    def _sync_generated_artifacts(self):
        """Create or update kanban view + action + menu for this blueprint."""
        self.ensure_one()
        if not self._is_runtime_active():
            if self.generated_menu_id:
                self.generated_menu_id.active = False
            if self.generated_action_id:
                # Keep action but hide menu; leave view for republish.
                pass
            return

        search_view = self._upsert_search_view()
        view = self._upsert_kanban_view()
        action = self._upsert_window_action(view, search_view)
        menu = self._upsert_menu(action)
        self.write(
            {
                "generated_view_id": view.id,
                "generated_search_view_id": search_view.id,
                "generated_action_id": action.id,
                "generated_menu_id": menu.id,
                "generated_arch_hash": self._kanban_arch_hash(),
            }
        )

    # ------------------------------------------------------------------
    # Card header
    # ------------------------------------------------------------------

    def _header_field_names(self):
        """Every host-model field the header reads."""
        self.ensure_one()
        names = [self.header_title_field or "display_name"]
        if self.header_image_field:
            names.append(self.header_image_field)
        for item in self.header_line_ids:
            names.extend(item._field_names())
        return names

    def _header_image_arch(self):
        """Picture box, in one of the two shapes the v1 dashboards use."""
        self.ensure_one()
        name = self.header_image_field
        if not name:
            return ""
        if self.header_image_style == "cover":
            container = (
                "o_media_left position-relative o_image_50_cover oe_img_bg "
                "o_bg_img_center flex-shrink-0 rounded-3 me-3"
            )
            img_class = "h-100 o_media_object d-block rounded border border-info"
            options = "{'img_class': 'object-fit-cover'}"
        else:
            container = (
                "o_media_left position-relative flex-shrink-0 me-4 "
                "dashboard_kanban_image_container"
            )
            img_class = (
                "o_media_object d-block rounded border border-info "
                "dashboard_kanban_image"
            )
            options = "{}"
        return f"""
                <div class="{container}" t-if="record.{name}.raw_value">
                    <field name="{name}" widget="image" class="{img_class}"
                           options="{options}"/>
                </div>"""

    def _header_field_is_tags(self, model_name, field_name):
        """True when the host field should render as many2many tags."""
        if not model_name or not field_name or model_name not in self.env:
            return False
        field = self.env[model_name]._fields.get(field_name)
        return bool(field and field.type in ("many2many", "one2many"))

    def _header_tags_fields_arch(self, names, model_name):
        """Render each multi-relation field as a coloured tags block."""
        blocks = []
        for name in names:
            field = (
                self.env[model_name]._fields.get(name)
                if model_name and model_name in self.env
                else None
            )
            comodel = (
                self.env.get(field.comodel_name)
                if field and field.type in ("many2many", "one2many")
                else None
            )
            options = (
                "{'color_field': 'color'}"
                if comodel is not None and "color" in comodel._fields
                else "{}"
            )
            blocks.append(
                f"""
                    <div class="me-2 dashboard_tag_container">
                        <field name="{name}" widget="many2many_tags"
                               options="{options}" class="m-0"/>
                    </div>"""
            )
        return "".join(blocks)

    def _header_line_has_tags(self, item):
        return any(
            self._header_field_is_tags(item.host_model_name, name)
            for name in item._field_names()
        )

    def _header_line_arch(self, item, *, force_tags_column=False):
        """One header line: ordered fields joined by Shown as, or tags.

        Alignment only moves text left/center/right inside the line (flex
        justify). Multi-relation fields render as tags; when ``force_tags_column``
        they sit in the far-right tags area, otherwise they follow alignment
        under the title like other lines.
        """
        names = item._field_names()
        if not names:
            return ""
        model_name = item.host_model_name
        ka = item._effective_kind_alignment()
        kind = ka["kind"]
        alignment = ka["alignment"]
        flex_justify = {
            "left": "justify-content-start",
            "center": "justify-content-center",
            "right": "justify-content-end",
        }.get(alignment, "justify-content-start")
        tag_names = [
            name for name in names if self._header_field_is_tags(model_name, name)
        ]
        text_names = [name for name in names if name not in tag_names]

        if force_tags_column:
            return self._header_tags_fields_arch(names, model_name)

        def _aligned_row(shown, inner, extra_classes=""):
            muted = " text-muted fw-bold" if kind == "subtitle" else ""
            return f"""
                        <div class="d-flex w-100 {flex_justify} dashboard_header_line dashboard_header_align_{alignment}{extra_classes}" t-if="{shown}">
                            <span class="dashboard_header_line_inner d-inline-flex align-items-center flex-wrap{muted}">{inner}</span>
                        </div>"""

        parts = []
        if text_names:
            separator = xml_escape(item.separator or ", ")
            tests = ["record.%s.raw_value" % name for name in text_names]
            body_parts = []
            for index, name in enumerate(text_names):
                if index:
                    earlier = " or ".join(tests[:index])
                    body_parts.append(
                        f'<t t-if="({earlier}) and {tests[index]}">{separator}</t>'
                    )
                body_parts.append(
                    f'<t t-if="{tests[index]}"><field name="{name}"/></t>'
                )
            body = "".join(body_parts)
            shown = " or ".join(tests)
            icon = ""
            if kind == "inline" and item.icon:
                label = xml_escape(dict(HEADER_ICONS).get(item.icon, item.icon))
                icon = (
                    f'<i class="fa {item.icon} me-1" title="{label}" '
                    f'role="img" aria-label="{label}"/>'
                )
            parts.append(_aligned_row(shown, f"{icon}{body}"))
        if tag_names:
            tags = self._header_tags_fields_arch(tag_names, model_name)
            if kind == "inline" and alignment == "left":
                tag_class = " dashboard_header_left_tags mt-1"
            else:
                tag_class = " dashboard_header_inline_tags mt-1"
            parts.append(
                f"""
                        <div class="d-flex w-100 {flex_justify} dashboard_header_line dashboard_header_align_{alignment}{tag_class}">
                            <span class="dashboard_header_line_inner d-inline-flex align-items-center flex-wrap">{tags}</span>
                        </div>"""
            )
        return "".join(parts)

    def _header_arch(self):
        self.ensure_one()
        title = self.header_title_field or "display_name"
        items = self.header_line_ids

        def _ka(item):
            return item._effective_kind_alignment()

        subtitles = "".join(
            self._header_line_arch(item)
            for item in items
            if _ka(item)["kind"] == "subtitle"
        )
        # Text / non-side tags: stay under the title; alignment is justify only.
        # Multi-record fields with inline + right keep the classic far-right column.
        inline_main = items.filtered(
            lambda i: _ka(i)["kind"] == "inline"
            and not (
                _ka(i)["alignment"] == "right" and self._header_line_has_tags(i)
            )
        )
        details = "".join(self._header_line_arch(item) for item in inline_main)
        side_tags = items.filtered(
            lambda i: _ka(i)["kind"] == "inline"
            and _ka(i)["alignment"] == "right"
            and self._header_line_has_tags(i)
        )
        tags = "".join(
            self._header_line_arch(item, force_tags_column=True) for item in side_tags
        )
        subtitle_block = (
            f"""
                    <div class="d-flex flex-column mb-1 w-100 dashboard_header_subtitles">{subtitles}
                    </div>"""
            if subtitles
            else ""
        )
        detail_block = (
            f"""
                    <div class="d-flex flex-column w-100 text-muted small dashboard_contact_info dashboard_header_inline_stack">{details}
                    </div>"""
            if details
            else ""
        )
        tag_block = (
            f"""
                <div class="d-flex align-items-start justify-content-end flex-wrap ms-3 dashboard_header_right">{tags}
                </div>"""
            if tags
            else ""
        )
        return f"""
            <div class="d-flex position-relative py-2 overflow-visible align-items-center">{self._header_image_arch()}
                <div class="d-flex flex-grow-1 flex-column justify-content-center position-relative min-w-0 w-100">
                    <a class="o_employee_redirect d-flex flex-column w-100" type="open">
                        <span class="oe_kanban_action dashboard_kanban_title fs-4 fw-bold text-body"><field name="{title}"/></span>{subtitle_block}{detail_block}
                    </a>
                </div>{tag_block}
            </div>"""

    def _layout_widget_arch(self, widget_type, key, caption):
        """Return inner HTML for one Layout Studio widget type."""
        self.ensure_one()
        if widget_type == "header":
            return self._header_arch()
        if widget_type == "primary":
            return f"""
                <div name="kanban_primary_left">
                    <button type="object" name="action_dashboard_engine_primary"
                            class="btn btn-primary"
                            context="{{'dashboard_blueprint_key': '{key}'}}">
                        <field name="dashboard_primary_label"/>
                    </button>
                </div>"""
        if widget_type == "kpis":
            return f"""
                <div name="kanban_primary_right">
                    <field name="dashboard_slots" widget="dashboard_slots"
                           options="{{'display': 'kpis'}}"/>
                </div>"""
        if widget_type == "graph":
            return f"""
                <t t-if="record.dashboard_graph_data.raw_value">
                    <div class="o_analytic_kanban_graph_section w-100">
                        <div t-if="'{caption}'"
                             class="o_analytic_graph_caption text-uppercase text-muted small fw-bold mb-1">
                            {caption}
                        </div>
                        <field name="dashboard_graph_data"
                               widget="analytic_dashboard_graph"
                               t-att-graph_type="record.dashboard_graph_type.raw_value"/>
                    </div>
                </t>
                <t t-else="">
                    <t t-call="dashboard_engine.EmptyGraph"/>
                </t>"""
        if widget_type == "totals":
            return f"""
                <div class="oe_button_box" name="button_box">
                    <field name="dashboard_slots" widget="dashboard_slots"
                           options="{{'display': 'button_box'}}"/>
                </div>"""
        if widget_type == "shortcuts":
            return f"""
                <div class="o_kanban_primary_bottom bottom_block">
                    <field name="dashboard_slots" widget="dashboard_slots"
                           options="{{'display': 'buttons'}}"/>
                </div>"""
        if widget_type == "manage":
            # Manage sections belong in the kanban card ⋮ menu template, not the body.
            return ""
        return ""

    def _kanban_arch_from_layout(self, layout):
        """Compose card body from Layout Studio rows/cols.

        Uses classic Odoo dashboard row patterns when a row matches known
        compositions (primary+kpis, totals+shortcuts, full-width graph) so
        published cards stay tight; other mixes use a Bootstrap grid.
        """
        self.ensure_one()
        key = self.key
        caption = self.graph_caption or ""
        rows_html = []
        for row in layout.get("rows") or []:
            cols = []
            for col in row.get("cols") or []:
                widget = col.get("widget") or {}
                wtype = widget.get("type")
                if wtype == "richtext" or wtype == "manage":
                    continue
                if wtype not in STUDIO_LAYOUT_CARD_WIDGETS:
                    continue
                cols.append(col)
            if not cols:
                continue
            types = [(c.get("widget") or {}).get("type") for c in cols]
            type_set = set(types)
            row_id = row.get("id") or ""

            if type_set == {"header"}:
                inner = self._layout_widget_arch("header", key, caption)
                rows_html.append(
                    f'<div data-studio-row="{row_id}" data-studio-widget="header">'
                    f"{inner}</div>"
                )
                continue

            if type_set <= {"primary", "kpis"} and "primary" in type_set:
                # Classic: fluid primary column + auto-sized KPIs.
                parts = []
                for col in cols:
                    wtype = (col.get("widget") or {}).get("type")
                    inner = self._layout_widget_arch(wtype, key, caption)
                    if wtype == "primary":
                        parts.append(
                            f'<div class="col mb-3 mb-sm-0" data-studio-widget="primary">'
                            f"{inner}</div>"
                        )
                    else:
                        parts.append(
                            f'<div class="col-auto" data-studio-widget="kpis">'
                            f"{inner}</div>"
                        )
                rows_html.append(
                    f'<div class="row" data-studio-row="{row_id}">'
                    f'{"".join(parts)}</div>'
                )
                continue

            if type_set <= {"totals", "shortcuts"}:
                # Classic footer row — do not wrap in col-* (breaks button_box CSS).
                parts = []
                for col in cols:
                    wtype = (col.get("widget") or {}).get("type")
                    parts.append(
                        f'<div data-studio-widget="{wtype}">'
                        f"{self._layout_widget_arch(wtype, key, caption)}</div>"
                    )
                rows_html.append(
                    f'<div class="row footer" data-studio-row="{row_id}">'
                    f'{"".join(parts)}</div>'
                )
                continue

            if type_set == {"graph"}:
                inner = self._layout_widget_arch("graph", key, caption)
                rows_html.append(
                    f'<div class="row mt-auto" data-studio-row="{row_id}">'
                    f'<div class="w-100" data-studio-widget="graph">{inner}</div>'
                    f"</div>"
                )
                continue

            # Generic grid (e.g. KPIs | chart side-by-side).
            cols_html = []
            for col in cols:
                wtype = (col.get("widget") or {}).get("type")
                span = int(col.get("span") or 12)
                inner = self._layout_widget_arch(wtype, key, caption)
                cell_class = "o_ds_layout_cell h-100"
                if wtype == "graph":
                    cell_class += " o_ds_layout_graph"
                cols_html.append(
                    f'<div class="col-{span}" data-studio-widget="{wtype}">'
                    f'<div class="{cell_class}">{inner}</div></div>'
                )
            rows_html.append(
                f'<div class="row g-3 align-items-start" data-studio-row="{row_id}">'
                f'{"".join(cols_html)}</div>'
            )
        body = "\n".join(rows_html) or self._legacy_card_body_arch()
        return body

    def _legacy_card_body_arch(self):
        """Classic fixed card body (pre–Layout Studio)."""
        self.ensure_one()
        key = self.key
        caption = self.graph_caption or ""
        return f"""
            <div class="mt-3 p-0 container-fluid">
                <div class="row">
                    <div class="col mb-3 mb-sm-0" name="kanban_primary_left">
                        <button type="object" name="action_dashboard_engine_primary"
                                class="btn btn-primary"
                                context="{{'dashboard_blueprint_key': '{key}'}}">
                            <field name="dashboard_primary_label"/>
                        </button>
                    </div>
                    <div class="col-auto" name="kanban_primary_right">
                        <field name="dashboard_slots" widget="dashboard_slots"
                               options="{{'display': 'kpis'}}"/>
                    </div>
                </div>
                <div class="row mt-auto">
                    <t t-if="record.dashboard_graph_data.raw_value">
                        <div class="o_analytic_kanban_graph_section w-100">
                            <div t-if="'{caption}'"
                                 class="o_analytic_graph_caption text-uppercase text-muted small fw-bold mb-1">
                                {caption}
                            </div>
                            <field name="dashboard_graph_data"
                                   widget="analytic_dashboard_graph"
                                   t-att-graph_type="record.dashboard_graph_type.raw_value"/>
                        </div>
                    </t>
                    <t t-else="">
                        <t t-call="dashboard_engine.EmptyGraph"/>
                    </t>
                </div>
                <div class="row footer">
                    <div class="oe_button_box" name="button_box">
                        <field name="dashboard_slots" widget="dashboard_slots"
                               options="{{'display': 'button_box'}}"/>
                    </div>
                    <div class="o_kanban_primary_bottom bottom_block">
                        <field name="dashboard_slots" widget="dashboard_slots"
                               options="{{'display': 'buttons'}}"/>
                    </div>
                </div>
            </div>"""

    def _kanban_arch(self):
        self.ensure_one()
        host = self.env.get(self.host_model_name)
        highlight = ""
        declared = [
            "id",
            "dashboard_graph_data",
            "dashboard_graph_type",
            "dashboard_slots",
            "dashboard_primary_label",
        ]
        if host is not None and "color" in host._fields:
            highlight = ' highlight_color="color"'
            declared.append("color")
        for name in self._header_field_names():
            if name not in declared and (host is None or name in host._fields):
                declared.append(name)
        fields_arch = "\n    ".join(
            '<field name="%s"/>' % name for name in declared
        )

        layout = self.studio_layout
        if layout:
            try:
                self._validate_studio_layout(layout)
                # Header may be a grid widget; if not present, keep classic top header.
                types_used = {
                    (col.get("widget") or {}).get("type")
                    for row in layout.get("rows") or []
                    for col in row.get("cols") or []
                }
                if "header" in types_used:
                    # Header first (no extra top margin); body rows get classic spacing.
                    body_layout = dict(layout)
                    body_layout["rows"] = [
                        row
                        for row in (layout.get("rows") or [])
                        if not any(
                            (col.get("widget") or {}).get("type") == "header"
                            for col in (row.get("cols") or [])
                        )
                    ]
                    header_html = self._header_arch()
                    body_html = self._kanban_arch_from_layout(body_layout)
                    card_inner = (
                        f"{header_html}"
                        f'<div class="mt-3 p-0 container-fluid o_ds_layout_body">'
                        f"{body_html}</div>"
                    )
                else:
                    card_inner = (
                        f"{self._header_arch()}"
                        f'<div class="mt-3 p-0 container-fluid o_ds_layout_body">'
                        f"{self._kanban_arch_from_layout(layout)}</div>"
                    )
            except UserError:
                card_inner = f"{self._header_arch()}{self._legacy_card_body_arch()}"
        else:
            card_inner = f"{self._header_arch()}{self._legacy_card_body_arch()}"

        return f"""
<kanban create="false" can_open="0" class="o_analytic_kanban_dashboard"{highlight}
        js_class="analytic_dashboard_config_settings_kanban">
    {fields_arch}
    <templates>
        <t t-name="card">{card_inner}
        </t>
        <t t-name="menu">
            <div class="container">
                <div class="row">
                    <div class="col-4" name="kanban_manage_views">
                        <h5 class="o_kanban_card_manage_title">
                            <span role="separator">View</span>
                        </h5>
                        <field name="dashboard_slots" widget="dashboard_slots"
                               options="{{'display': 'menu', 'section': 'views'}}"/>
                    </div>
                    <div class="col-4" name="kanban_manage_new">
                        <h5 class="o_kanban_card_manage_title">
                            <span role="separator">New</span>
                        </h5>
                        <field name="dashboard_slots" widget="dashboard_slots"
                               options="{{'display': 'menu', 'section': 'new'}}"/>
                    </div>
                    <div class="col-4" name="kanban_manage_reports">
                        <h5 class="o_kanban_card_manage_title">
                            <span role="separator">Reporting</span>
                        </h5>
                        <field name="dashboard_slots" widget="dashboard_slots"
                               options="{{'display': 'menu', 'section': 'reports'}}"/>
                    </div>
                </div>
                {self._kanban_menu_footer_arch(host)}
            </div>
        </t>
    </templates>
</kanban>
""".strip()

    def _kanban_menu_footer_arch(self, host):
        """Color picker + Configuration link — same chrome as v1 customer cards."""
        color_block = ""
        if host is not None and "color" in host._fields:
            color_block = """
                <div t-if="widget.editable" class="o_kanban_card_manage_settings row">
                    <field class="col-8" name="color" widget="kanban_color_picker"/>
                </div>"""
        # type="open" opens the host record form (v1 parity). Dashboard gear
        # settings stay on the kanban control panel separately.
        config_block = """
                <div class="row o_kanban_card_manage_settings">
                    <div class="col-6 text-end">
                        <a class="dropdown-item" t-if="widget.editable" type="open">Configuration</a>
                    </div>
                </div>"""
        return f"{color_block}{config_block}"

    def _upsert_kanban_view(self):
        self.ensure_one()
        View = self.env["ir.ui.view"].sudo()
        vals = {
            "name": f"dashboard.engine.kanban.{self.key}",
            "model": self.host_model_name,
            "type": "kanban",
            "arch": self._kanban_arch(),
            "priority": 99,
        }
        if self.generated_view_id:
            self.generated_view_id.write(vals)
            return self.generated_view_id
        return View.create(vals)

    def _host_default_search_view(self):
        """Primary search view for the host model (lowest priority)."""
        self.ensure_one()
        View = self.env["ir.ui.view"].sudo()
        view_id = View.default_view(self.host_model_name, "search")
        return View.browse(view_id) if view_id else View.browse()

    def _search_arch(self):
        """Inherit arch injecting only enabled lens filters."""
        self.ensure_one()
        parts = []
        if self.lens_my_enabled:
            label = xml_escape((self.lens_my_label or "").strip())
            parts.append(
                f'<filter name="dashboard_my_data" string="{label}" '
                f"domain=\"[('dashboard_my_data', '=', True)]\" "
                f"invisible=\"not context.get('show_dashboard_my_filter')\"/>"
            )
        if self.lens_kpis_enabled:
            if parts:
                parts.append("<separator/>")
            label = xml_escape((self.lens_kpis_label or "").strip())
            parts.append(
                f'<filter name="dashboard_with_kpis" string="{label}" '
                f"domain=\"[('dashboard_with_kpis', '=', True)]\" "
                f"invisible=\"not context.get('show_dashboard_kpis_filter')\"/>"
            )
        inner = "\n            ".join(parts)
        return (
            "<data>\n"
            '  <xpath expr="//search" position="inside">\n'
            f"            {inner}\n"
            "  </xpath>\n"
            "</data>"
        )

    def _upsert_search_view(self):
        self.ensure_one()
        View = self.env["ir.ui.view"].sudo()
        parent = self._host_default_search_view()
        vals = {
            "name": f"dashboard.engine.search.{self.key}",
            "model": self.host_model_name,
            "type": "search",
            "arch": self._search_arch(),
            "priority": 99,
            "mode": "primary",
        }
        if parent:
            vals["inherit_id"] = parent.id
        else:
            # No host search: standalone primary with enabled filters only.
            filters = []
            if self.lens_my_enabled:
                label = xml_escape((self.lens_my_label or "").strip())
                filters.append(
                    f'<filter name="dashboard_my_data" string="{label}" '
                    f"domain=\"[('dashboard_my_data', '=', True)]\" "
                    f"invisible=\"not context.get('show_dashboard_my_filter')\"/>"
                )
            if self.lens_kpis_enabled:
                if filters:
                    filters.append("<separator/>")
                label = xml_escape((self.lens_kpis_label or "").strip())
                filters.append(
                    f'<filter name="dashboard_with_kpis" string="{label}" '
                    f"domain=\"[('dashboard_with_kpis', '=', True)]\" "
                    f"invisible=\"not context.get('show_dashboard_kpis_filter')\"/>"
                )
            vals["arch"] = f"<search>{''.join(filters)}</search>"
            vals["inherit_id"] = False
        if self.generated_search_view_id:
            self.generated_search_view_id.write(vals)
            return self.generated_search_view_id
        return View.create(vals)

    def _lens_action_context(self):
        """Context keys for generated act_window (lens show + search defaults)."""
        self.ensure_one()
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
        return ctx

    def _upsert_window_action(self, view, search_view=None):
        self.ensure_one()
        Action = self.env["ir.actions.act_window"].sudo()
        vals = {
            "name": self.menu_name or self.name,
            "res_model": self.host_model_name,
            "view_mode": "kanban,list,form",
            "view_id": view.id,
            "search_view_id": search_view.id if search_view else False,
            "context": self._lens_action_context(),
            "domain": [],
            "target": "current",
        }
        if self.generated_action_id:
            self.generated_action_id.write(vals)
            return self.generated_action_id
        return Action.create(vals)

    def _upsert_menu(self, action):
        self.ensure_one()
        Menu = self.env["ir.ui.menu"].sudo()
        parent = self.env.ref(
            "dashboard_engine.menu_dashboard_engine_root", raise_if_not_found=False
        )
        if self.menu_parent_xmlid:
            parent = self.env.ref(
                self.menu_parent_xmlid, raise_if_not_found=False
            ) or parent
        vals = {
            "name": self.menu_name or self.name,
            "action": f"ir.actions.act_window,{action.id}",
            "parent_id": parent.id if parent else False,
            "sequence": self.menu_sequence,
            "active": True,
        }
        if self.generated_menu_id:
            self.generated_menu_id.write(vals)
            return self.generated_menu_id
        return Menu.create(vals)

    # ------------------------------------------------------------------
    # Runtime APIs consumed by OWL widgets
    # ------------------------------------------------------------------

    @api.model
    def _get_blueprint(self, key):
        bp = self.search([("key", "=", key)], limit=1)
        if not bp or not bp._is_runtime_active():
            return self.browse()
        return bp

    @api.model
    def get_record_slots(self, blueprint_key, res_model, res_id):
        """Return KPI / button / menu payload for one host record."""
        bp = self._get_blueprint(blueprint_key)
        if not bp or bp.host_model_name != res_model:
            return self._empty_slots_payload()
        record = self.env[res_model].browse(res_id).exists()
        if not record:
            return self._empty_slots_payload()
        return bp._build_slots_payload(record)

    def _empty_slots_payload(self):
        return {
            "kpis": [],
            "buttons": [],
            "button_box": [],
            "menu": {"views": [], "new": [], "reports": []},
        }

    def _share_neighbors(self):
        """Direct share links in both directions (undirected edge)."""
        self.ensure_one()
        reverse = self.search([("share_link_ids", "in", self.id)])
        return self.share_link_ids | reverse

    def _share_component(self):
        """Connected component of blueprints linked via share_link_ids."""
        self.ensure_one()
        seen = self.browse()
        queue = self.browse(self.ids)
        while queue:
            current = queue[0]
            queue = queue[1:]
            if current in seen:
                continue
            seen |= current
            queue |= current._share_neighbors() - seen
        return seen

    @api.model
    def _slot_dedupe_key(self, slot):
        """Stable identity for shared-slot collapsing; ``None`` = never collapse."""
        if slot.key:
            return ("key", slot.section, slot.key)
        if slot.action_xmlid:
            return ("action", slot.section, slot.action_xmlid)
        return None

    def _effective_slots(self):
        """Shared-section slots from the share component, deduped.

        Order: this blueprint first (by slot sequence), then other blueprints
        by ``(sequence, id)``, each with slots by sequence. First wins on
        ``_slot_dedupe_key``.
        """
        self.ensure_one()
        component = self._share_component()
        peers = (component - self).sorted(lambda b: (b.sequence, b.id))
        ordered_ids = []
        seen_keys = set()
        for blueprint in [self] + list(peers):
            slots = blueprint.slot_ids.filtered(
                lambda s: s.section in SHARED_SLOT_SECTIONS
            ).sorted("sequence")
            for slot in slots:
                key = self._slot_dedupe_key(slot)
                if key is not None:
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                ordered_ids.append(slot.id)
        return self.env["dashboard.blueprint.slot"].browse(ordered_ids)

    def _find_effective_slot(self, slot_key):
        """Resolve a slot key inside the share component (dedupe order)."""
        self.ensure_one()
        if not slot_key:
            return self.env["dashboard.blueprint.slot"]
        return self._effective_slots().filtered(lambda s: s.key == slot_key)[:1]

    def _sync_share_link_symmetric(self):
        """Keep the M2M tags mirrored both ways for builder UX."""
        if self.env.context.get("skip_share_sync"):
            return
        for rec in self:
            for other in rec.share_link_ids:
                if rec not in other.share_link_ids:
                    other.with_context(skip_share_sync=True).write(
                        {"share_link_ids": [(4, rec.id)]}
                    )
            stale = self.search(
                [
                    ("id", "!=", rec.id),
                    ("share_link_ids", "in", rec.id),
                    ("id", "not in", rec.share_link_ids.ids or [0]),
                ]
            )
            for other in stale:
                other.with_context(skip_share_sync=True).write(
                    {"share_link_ids": [(3, rec.id)]}
                )

    def _build_slots_payload(self, record):
        self.ensure_one()
        payloads = self._build_slots_payloads(record)
        return payloads.get(record.id) or self._empty_slots_payload()

    def _build_slots_payloads(self, records):
        """Return ``{record_id: slot payload}`` for a whole recordset.

        Slot visibility is record-independent, so it is resolved once, and
        each visible slot aggregates its figures for every card in a single
        query. The cost is therefore one query per slot, not per card.

        Slots are the effective shared pool (bi-directional inherit), not only
        ``self.slot_ids``.
        """
        self.ensure_one()
        if not records:
            return {}
        ctx = dict(self.env.context)
        candidates = self._effective_slots()
        visible = self.env["dashboard.blueprint.slot"].browse(
            [s.id for s in candidates if s._is_visible(ctx)]
        )
        values = {slot.id: slot._compute_values_batch(records) for slot in visible}

        payloads = {}
        for record in records:
            sections = {}
            for slot in visible:
                item = slot._to_slot_item(
                    record, values[slot.id].get(record.id, (None, None))
                )
                if item:
                    sections.setdefault(slot.section, []).append(item)
            payload = self._empty_slots_payload()
            payload["kpis"] = sections.get("kpi", [])
            payload["buttons"] = sections.get("bottom", [])
            payload["button_box"] = sections.get("button_box", [])
            payload["menu"] = {
                "views": sections.get("menu_views", []),
                "new": sections.get("menu_new", []),
                "reports": sections.get("menu_reports", []),
            }
            payloads[record.id] = payload
        return payloads

    @api.model
    def _get_rendering_blueprint(self, res_model):
        """Blueprint currently rendering ``res_model``, or an empty recordset.

        Resolved from the context key that generated actions inject, so the
        payload computes on ``base`` stay inert everywhere else.
        """
        key = self.env.context.get("dashboard_blueprint_key")
        if not key:
            return self.browse()
        bp = self._get_blueprint(key)
        if not bp or bp.host_model_name != res_model:
            return self.browse()
        return bp

    def _has_graph(self):
        self.ensure_one()
        return bool(self.graph_model) and self.graph_model in self.env

    @api.model
    def _merge_domains(self, existing, extra):
        """Concatenate two domains, dropping leaves already present.

        Deduplication is only safe while both sides are plain conjunctions;
        once explicit operators appear their positions matter, so the parts
        are concatenated untouched.
        """
        combined = list(existing) + list(extra)
        if any(isinstance(item, str) for item in combined):
            return combined
        merged = []
        seen = []
        # Compared as lists rather than hashed, since leaf values may be lists.
        for leaf in combined:
            normalized = list(leaf)
            if normalized not in seen:
                seen.append(normalized)
                merged.append(leaf)
        return merged

    # ------------------------------------------------------------------
    # Per-user settings
    # ------------------------------------------------------------------

    def _current_pref(self):
        """This user's saved settings for this dashboard, if any."""
        self.ensure_one()
        return self.env["dashboard.user.pref"].search(
            [("blueprint_id", "=", self.id), ("user_id", "=", self.env.uid)],
            limit=1,
        )

    def _unified_groupby_pref_defaults(self):
        """Default ordered Group By tags from the blueprint's Group By list."""
        self.ensure_one()
        if self.graph_groupby_ids:
            unique = list(self._ordered_graph_groupby_fields())
        else:
            ordered = []
            if self.graph_groupby_field_id:
                ordered.append(self.graph_groupby_field_id)
            ordered.extend(self._ordered_groupby_extra_fields())
            seen = set()
            unique = []
            for field in ordered:
                if field.id in seen:
                    continue
                seen.add(field.id)
                unique.append(field)
        return {
            "groupby_ids": [(6, 0, [f.id for f in unique])],
            "ordered_groupby_ids": ",".join(str(f.id) for f in unique) or False,
        }

    def _default_pref_values(self):
        """A fresh preference row starts from what the blueprint declares.

        Group By is seeded only on the unified tag list; legacy primary/extra
        columns are filled by ``dashboard.user.pref`` write's one-way mirror.
        """
        self.ensure_one()
        vals = {
            "blueprint_id": self.id,
            "user_id": self.env.uid,
            "scope_ids": [(6, 0, self.scope_ids.filtered("default_on").ids)],
            "measure_field_id": self.graph_measure_field_id.id,
            "measure_aggregator": self.graph_measure_aggregator,
            "groupby_granularity": self.graph_groupby_granularity,
            "period_field_id": self.period_field_id.id
            or (
                self.graph_groupby_field_id.id
                if self.graph_groupby_field_id.ttype in DATE_TYPES
                else False
            ),
            "period_closed_field_id": self.closed_period_field_id.id or False,
        }
        vals.update(self._unified_groupby_pref_defaults())
        return vals

    def _get_or_create_pref(self):
        self.ensure_one()
        pref = self._current_pref()
        if not pref:
            pref = (
                self.env["dashboard.user.pref"]
                .sudo()
                .create(self._default_pref_values())
                .with_user(self.env.user)
            )
        else:
            heal = {}
            if not pref.period_field_id and self.period_field_id:
                heal["period_field_id"] = self.period_field_id.id
            if not pref.period_closed_field_id and self.closed_period_field_id:
                heal["period_closed_field_id"] = self.closed_period_field_id.id
            if heal:
                pref.sudo().write(heal)
            pref.sudo()._ensure_unified_groupby()
        return pref

    def _effective_graph_settings(self):
        """Blueprint configuration with this user's choices applied on top."""
        self.ensure_one()
        bp_specs = self._groupby_all_specs()
        if bp_specs:
            settings = {
                "groupby": bp_specs[0],
                "measure": self.graph_measure or "__count",
                "domain": list(self._safe_domain(self.graph_domain)),
                "groupbys": bp_specs,
            }
        else:
            settings = {
                "groupby": self.graph_groupby or "id",
                "measure": self.graph_measure or "__count",
                "domain": list(self._safe_domain(self.graph_domain)),
            }
            settings["groupbys"] = [settings["groupby"]] + self._groupby_extra_specs()
        pref = self._current_pref()
        if not pref:
            defaults = self.scope_ids.filtered("default_on")
            if defaults:
                settings["domain"] = self._merge_domains(
                    settings["domain"], self._default_scope_domain(defaults)
                )
            return settings
        # Pref Group By is always the unified ordered list (legacy columns
        # are mirrors only). Empty list → keep blueprint defaults above.
        specs = pref._groupby_all_specs()
        if pref._ordered_groupby_fields() and specs:
            settings["groupby"] = specs[0]
            settings["groupbys"] = specs
        settings["measure"] = pref._measure_spec() or settings["measure"]
        settings["domain"] = self._merge_domains(
            settings["domain"], pref._pref_domain()
        )
        return settings

    def _default_scope_domain(self, scopes):
        self.ensure_one()
        included = [s._scope_domain() for s in scopes if s.mode == "include"]
        parts = [list(fields.Domain.OR(included))] if included else []
        parts.extend(s._scope_domain() for s in scopes if s.mode == "restrict")
        parts = [part for part in parts if part]
        return list(fields.Domain.AND(parts)) if parts else []

    def action_open_settings(self):
        """Open this dashboard's settings for the current user."""
        self.ensure_one()
        pref = self._get_or_create_pref()
        return {
            "type": "ir.actions.act_window",
            "name": _("Configuration"),
            "res_model": "dashboard.user.pref",
            "res_id": pref.id,
            "views": [
                (self.env.ref("dashboard_engine.dashboard_user_pref_view_form").id, "form")
            ],
            "target": "new",
            "context": {"dashboard_blueprint_key": self.key},
        }

    @api.model
    def action_open_settings_for_key(self, key):
        blueprint = self.search([("key", "=", key)], limit=1)
        if not blueprint:
            return self.env["ir.actions.actions"]._for_xml_id(
                "dashboard_engine.action_dashboard_blueprint"
            )
        return blueprint.action_open_settings()

    @api.model
    def action_open_studio_for_key(self, key):
        """Open Dashboard Studio for a published dashboard (live kanban entry)."""
        blueprint = self.search([("key", "=", key)], limit=1)
        if not blueprint:
            raise UserError(_("Dashboard not found."))
        return blueprint.action_open_studio()

    def _graph_link_path(self):
        """Multi-hop link info, or falsy for direct / missing links.

        Single-segment Char paths stay falsy so ``include_child_records``
        hierarchy folding keeps working. Multi-hop Char (or legacy path
        records) return :class:`RelationPathInfo`.
        """
        self.ensure_one()
        path_str, source = self._resolve_graph_path_string()
        if not path_str or not source or relation_path_is_direct(path_str):
            return None
        return RelationPathInfo(
            env=self.env, path=path_str, source_model=source
        )

    def _host_domain_leaf(self, host_ids, path=None, link_field=None):
        """Domain leaf restricting aggregated records to the given cards."""
        self.ensure_one()
        if path is None:
            path = self._graph_link_path()
        if path:
            return path.domain_leaf(host_ids)
        link = link_field if link_field is not None else (
            self._resolve_graph_path_string()[0] or self.graph_data_field
        )
        if not link or not host_ids:
            return False
        ids = list(host_ids)
        if len(ids) == 1:
            return (link, "=", ids[0])
        return (link, "in", ids)

    def _hierarchy_enabled(self):
        """True when this blueprint should roll child cards into parents."""
        self.ensure_one()
        if not self.include_child_records or not self.host_model_name:
            return False
        Host = self.env.get(self.host_model_name)
        return bool(Host is not None and "parent_id" in Host._fields)

    def _hierarchy_fold_map(self, host_ids):
        """``{linked_id: [visible_host_id, ...]}`` for every id reachable
        from ``host_ids`` through ``parent_id``, itself included.

        Two queries total, regardless of how deep the hierarchy is or how
        many cards are on the page: one to expand the cards to every
        descendant (``child_of``), one implicit batched read of every
        descendant's ``parent_id`` used to walk back up in memory.
        """
        self.ensure_one()
        ids = [i for i in host_ids if i]
        if not ids:
            return {}
        if not self._hierarchy_enabled():
            return {i: [i] for i in ids}
        Host = self.env[self.host_model_name].with_context(active_test=False)
        descendants = Host.search([("id", "child_of", ids)])
        parent_by_id = {rec.id: (rec.parent_id.id or None) for rec in descendants}
        visible = set(ids)
        fold = {}
        for start_id in parent_by_id:
            current, seen, hits = start_id, set(), []
            while current and current not in seen:
                seen.add(current)
                if current in visible:
                    hits.append(current)
                current = parent_by_id.get(current)
            fold[start_id] = hits
        return fold

    def _restrict_scope_domain(self):
        """Domain from ticked 'narrows down' scopes (e.g. My Pipeline).

        Include scopes (Pipeline / Leads) stay graph-only: KPI slots keep
        their own domains. Restrict scopes apply to graph, primary button,
        and right KPIs only — not bottoms or Manage menus.
        See docs/superpowers/specs/2026-07-28-restrict-scope-surface-matrix-design.md
        """
        self.ensure_one()
        available = self.scope_ids.filtered(lambda s: s.mode == "restrict")
        if not available:
            return []
        pref = self._current_pref()
        chosen = (pref.scope_ids & available) if pref else available.filtered("default_on")
        parts = [part for part in (s._scope_domain() for s in chosen) if part]
        if not parts:
            return []
        if len(parts) == 1:
            return list(parts[0])
        return list(fields.Domain.AND(parts))

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
        link = self._resolve_graph_path_string()[0] or self.graph_data_field
        if not link or "." in link:
            return False
        return "user_id" in Graph._fields

    def _lens_my_domain(self):
        self.ensure_one()
        Host = self.env.get(self.host_model_name)
        if Host is not None and "user_id" in Host._fields:
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
            return []
        Graph = self.env[self.graph_model].with_context(
            _dashboard_fetching_data=True
        )
        domain = list(self._safe_domain(self.graph_domain))
        domain = domain + list(self._restrict_scope_domain() or [])
        if extra_domain:
            domain = domain + list(extra_domain)
        try:
            groups = Graph.formatted_read_group(
                domain=domain,
                groupby=[link],
                aggregates=["__count"],
            )
        except Exception:
            _logger.debug(
                "Lens KPI host ids failed for blueprint %s", self.key
            )
            return []
        ids = []
        seen = set()
        for group in groups:
            host_id = self._graph_group_id(group.get(link))
            if host_id and host_id not in seen:
                seen.add(host_id)
                ids.append(host_id)
        return ids

    def _build_graph_payloads(self, records):
        """Return ``{record_id: {"json": str, "type": str}}`` for a recordset.

        Direct links group on the host field itself. Multi-hop paths group on
        the first hop and fold hop→host in Python, because read_group cannot
        group by a dotted field. Either way the cost is one grouped query for
        every visible card.
        """
        self.ensure_one()
        if not records:
            return {}
        Graph = self.env[self.graph_model]
        path = self._graph_link_path()
        path_str, _source = self._resolve_graph_path_string()
        link = path.first_hop_field if path else path_str
        settings = self._effective_graph_settings()
        groupby = settings["groupby"]
        # Ordered multi-level group-by (H3): the primary level stays the
        # graph's own group-by field, any extra levels ride along after it.
        groupby_levels = settings.get("groupbys") or [groupby]
        measure = settings["measure"]
        aggregate = "__count" if measure == "__count" else measure
        base_domain = settings["domain"]
        domain = list(base_domain)
        fold_map = None
        if not path and link and self._hierarchy_enabled():
            fold_map = self._hierarchy_fold_map(records.ids)
            leaf = (link, "in", list(fold_map.keys())) if fold_map else False
        else:
            leaf = self._host_domain_leaf(records.ids, path=path)
        if leaf:
            domain.append(leaf)
        groupby_spec = ([link] if link else []) + groupby_levels
        try:
            groups = Graph.formatted_read_group(
                domain=domain,
                groupby=groupby_spec,
                aggregates=[aggregate],
            )
        except Exception:
            _logger.warning(
                "Dashboard engine graph failed for blueprint %s",
                self.key,
                exc_info=True,
            )
            return {}

        hop_to_hosts = (
            path.map_first_hop_to_hosts(records.ids)
            if path and not path.is_direct
            else None
        )

        # V1-compatible shape: first group-by = X axis, further levels =
        # coloured series (legend). A single group-by stays one series
        # whose legend key is the human measure name (not "__count").
        series_levels = groupby_levels[1:]
        # host -> ordered x keys; host -> x_key -> series_key -> point
        x_order = {}
        series_order = {}
        cells = {}
        for group in groups:
            hop_id = self._graph_group_id(group.get(link)) if link else None
            if hop_to_hosts is not None:
                host_ids = hop_to_hosts.get(hop_id, [])
            elif fold_map is not None:
                host_ids = fold_map.get(hop_id, [])
            elif link:
                host_ids = [hop_id] if hop_id in records._ids else []
            else:
                host_ids = [None]
            level_values = [group.get(level) for level in groupby_levels]
            x_raw = level_values[0]
            x_key = self._graph_group_id(x_raw)
            x_label = self._graph_group_label(x_raw)
            if series_levels:
                series_values = level_values[1:]
                series_labels = [
                    self._graph_group_label(value) for value in series_values
                ]
                series_key = tuple(series_labels)
                color_key = " / ".join(series_labels) if series_labels else x_label
            else:
                series_values = []
                series_key = ()
                color_key = False
            value = group.get(aggregate) or 0
            for host_id in host_ids:
                host_x = x_order.setdefault(host_id, [])
                if x_key not in host_x:
                    host_x.append(x_key)
                host_series = series_order.setdefault(host_id, [])
                if series_key not in host_series:
                    host_series.append(series_key)
                cell_key = (host_id, x_key, series_key)
                cell = cells.get(cell_key)
                if cell:
                    cell["value"] += value
                else:
                    cells[cell_key] = {
                        "x_label": x_label,
                        "color_key": color_key,
                        "value": value,
                        "level_values": level_values,
                        "series_values": series_values,
                    }

        payloads = {}
        series_legend = bool(series_levels)
        measure_key = (
            _("Count")
            if measure == "__count"
            else (self.graph_caption or measure or _("Count"))
        )
        for record in records:
            host_id = record.id if link else None
            ordered_x = x_order.get(host_id) or []
            ordered_series = series_order.get(host_id) or [()]
            if not ordered_x:
                continue
            ordered_x = ordered_x[:GRAPH_MAX_GROUPS]
            values = []
            for x_key in ordered_x:
                y_values = []
                domains = []
                group_names = []
                color_keys = []
                x_label = None
                for series_key in ordered_series:
                    cell = cells.get((host_id, x_key, series_key))
                    if cell:
                        x_label = cell["x_label"]
                        y_values.append(cell["value"])
                        domains.append(
                            self._graph_point_domain(
                                base_domain,
                                path=path,
                                host_id=host_id,
                                groupby_levels=groupby_levels,
                                values=cell["level_values"],
                                link=None if path else link,
                            )
                        )
                        if series_legend:
                            series_label = cell["color_key"] or _("None")
                            group_names.append("%s / %s" % (x_label, series_label))
                            color_keys.append(series_label)
                        else:
                            group_names.append(x_label or _("None"))
                    else:
                        # Keep series indexes aligned across X points.
                        y_values.append(0)
                        domains.append([])
                        if series_legend:
                            series_label = (
                                " / ".join(series_key) if series_key else _("None")
                            )
                            group_names.append(
                                "%s / %s"
                                % (x_label or self._graph_group_label(x_key), series_label)
                            )
                            color_keys.append(series_label)
                        else:
                            group_names.append(
                                x_label or self._graph_group_label(x_key)
                            )
                if x_label is None:
                    x_label = self._graph_group_label(x_key)
                point = {
                    "label": x_label,
                    "value": y_values,
                    "domains": domains,
                    "group_names": group_names,
                }
                if series_legend:
                    point["group_color_keys"] = color_keys
                values.append(point)
            graph_type = "bar" if len(values) < GRAPH_BAR_LIMIT else "line"
            payloads[record.id] = {
                "type": graph_type,
                "json": json.dumps(
                    [
                        {
                            "values": values,
                            "area": True,
                            "key": measure_key,
                            "is_sample_data": False,
                            "type": graph_type,
                            "currency_id": self.env.company.currency_id.id,
                            "model": self.graph_model,
                            "measure": measure,
                        }
                    ]
                ),
            }
        return payloads

    @api.model
    def _graph_group_id(self, value):
        """Record id out of a read_group many2one value."""
        if isinstance(value, (list, tuple)):
            return value[0] if value else False
        return value

    @api.model
    def _graph_group_label(self, value):
        if isinstance(value, (list, tuple)):
            value = value[1] if len(value) > 1 else value[0]
        if value is False or value is None:
            return _("None")
        return str(value)

    def _graph_point_domain(
        self, base_domain, host_id, groupby_levels, values, path=None, link=None
    ):
        """Drill-down domain behind a single graph point.

        ``groupby_levels``/``values`` are parallel lists: one read_group
        spec and its matching value per level (H3 ordered multi-groupby).
        A single-level graph just passes one-item lists.
        """
        domain = list(base_domain)
        if not path and link and host_id and self._hierarchy_enabled():
            leaf = (link, "child_of", host_id)
        else:
            leaf = self._host_domain_leaf(
                [host_id] if host_id else [], path=path, link_field=link
            )
        if leaf:
            domain.append(leaf)
        for level, value in zip(groupby_levels, values):
            domain += self._graph_groupby_domain(level, value)
        return domain

    def _graph_groupby_domain(self, groupby, value):
        """Leaves matching one group of the graph's group-by.

        A granularity spec such as ``create_date:month`` is a read-group
        instruction, not a field, so it cannot be matched with ``=``; it has
        to be expanded into a half-open range over the underlying date field.
        """
        self.ensure_one()
        field_name, _sep, granularity = groupby.partition(":")
        raw = self._graph_group_id(value)
        if not granularity:
            return [(field_name, "=", raw)]
        if not raw:
            return [(field_name, "=", False)]

        field = self.env[self.graph_model]._fields.get(field_name)
        is_date = bool(field) and field.type == "date"
        start = (
            fields.Date.to_date(raw) if is_date else fields.Datetime.to_datetime(raw)
        )
        if not start:
            return [(field_name, "=", False)]
        # get_timedelta has no quarter, and read_group does emit one.
        span = (
            get_timedelta(3, "month")
            if granularity == "quarter"
            else get_timedelta(1, granularity)
        )
        to_string = fields.Date.to_string if is_date else fields.Datetime.to_string
        return [
            (field_name, ">=", to_string(start)),
            (field_name, "<", to_string(start + span)),
        ]

    @api.model
    def execute_slot_action(self, blueprint_key, slot_key, res_model, res_id):
        """Build and return an act_window for a slot click."""
        bp = self._get_blueprint(blueprint_key)
        if not bp:
            return False
        slot = bp._find_effective_slot(slot_key)
        if not slot:
            return False
        record = self.env[res_model].browse(res_id).exists()
        if not record:
            return False
        return slot._prepare_action(record)

    @api.model
    def execute_primary_action(self, blueprint_key, res_model, res_id):
        bp = self._get_blueprint(blueprint_key)
        if not bp:
            return False
        record = self.env[res_model].browse(res_id).exists()
        if not record:
            return False

        label = bp._resolved_primary_label()
        settings = bp._effective_graph_settings()

        # Prefer an existing window/graph action when configured.
        primary_xmlid = bp._resolved_primary_action_xmlid()
        result = False
        if primary_xmlid:
            try:
                action = self.env.ref(primary_xmlid).sudo()
                result = action._get_action_dict()
            except Exception:
                _logger.warning(
                    "Missing primary action xmlid %s for blueprint %s",
                    primary_xmlid,
                    bp.key,
                )
                result = False
            if result:
                action_model = result.get("res_model")
                domain = bp._primary_action_domain(
                    record, settings, action_model=action_model
                )
                existing = result.get("domain") or []
                if isinstance(existing, str):
                    existing = bp._safe_domain(existing)
                result["domain"] = bp._merge_domains(existing, domain)
                result["context"] = bp._primary_action_context(
                    record,
                    settings,
                    result.get("context"),
                    action_model=action_model,
                )
                if label:
                    result["name"] = label
                return result

        # Fallback: runtime action from graph settings.
        if not bp.graph_model or bp.graph_model not in self.env:
            return False
        path = bp._graph_link_path()
        path_str, _source = bp._resolve_graph_path_string()
        default_link = relation_first_hop(path_str) if path_str else False
        domain = bp._primary_action_domain(
            record, settings, action_model=bp.graph_model
        )
        return {
            "type": "ir.actions.act_window",
            "name": label or bp.name,
            "res_model": bp.graph_model,
            "views": [[False, "graph"], [False, "list"], [False, "form"]],
            "view_mode": "graph,list,form",
            "domain": domain,
            "context": {
                **bp._primary_action_context(
                    record, settings, action_model=bp.graph_model
                ),
                f"default_{default_link}": record.id if default_link else False,
            },
            "target": "current",
        }

    def _field_path_exists_on(self, model_name, field_path):
        """True when ``field_path`` (possibly dotted) resolves on ``model_name``."""
        if not model_name or model_name not in self.env or not field_path:
            return False
        if not isinstance(field_path, str) or field_path in (".id", "id"):
            return field_path == "id"
        model = self.env[model_name]
        parts = field_path.split(".")
        for index, part in enumerate(parts):
            if part not in model._fields:
                return False
            field = model._fields[part]
            if index < len(parts) - 1:
                if not getattr(field, "relational", False):
                    return False
                model = self.env[field.comodel_name]
        return True

    def _domain_leaf_valid_on(self, model_name, leaf):
        if not isinstance(leaf, (list, tuple)) or len(leaf) != 3:
            return True
        return self._field_path_exists_on(model_name, leaf[0])

    def _sanitize_domain_for_model(self, domain, model_name):
        """Drop leaves whose field path is missing on ``model_name``.

        Used when the primary action targets a different model than the
        mini-chart (e.g. ``sale.order`` vs ``sale.report``), so graph
        host fields like ``product_id`` are not applied blindly.
        """
        if not domain:
            return []
        if not model_name or model_name not in self.env:
            return list(domain)
        Model = self.env[model_name]
        try:
            fields.Domain(domain).optimize(Model)
            return list(domain)
        except ValueError:
            pass
        cleaned = []
        for item in domain:
            if isinstance(item, str) and item in ("!", "|", "&"):
                cleaned.append(item)
            elif isinstance(item, (list, tuple)) and len(item) == 3:
                if self._domain_leaf_valid_on(model_name, item):
                    cleaned.append(tuple(item))
            else:
                cleaned.append(item)
        try:
            return list(fields.Domain(cleaned).optimize(Model))
        except Exception:
            return [
                item
                for item in cleaned
                if isinstance(item, (list, tuple)) and len(item) == 3
            ]

    def _primary_action_domain(self, record, settings=None, action_model=None):
        """Domain for the card's main button — same slice as the mini-chart.

        Combines the blueprint's static primary domain, the host link
        (``child_of`` when hierarchy is on), and the viewer's effective
        graph domain (include/restrict scopes, periods, custom filter).

        When ``action_model`` differs from ``graph_model``, graph host
        leaves that are invalid on the opened model are dropped; packs
        should then set ``primary_action_domain`` (e.g.
        ``order_line.product_id`` on ``sale.order``).
        """
        self.ensure_one()
        if settings is None:
            settings = self._effective_graph_settings()
        domain = self._eval_domain_with_record(self.primary_action_domain, record)
        leaf = self._primary_host_leaf(record)
        if leaf and (
            not action_model or self._domain_leaf_valid_on(action_model, leaf)
        ):
            domain = list(domain) + [leaf]
        merged = self._merge_domains(domain, settings.get("domain") or [])
        if action_model:
            return self._sanitize_domain_for_model(merged, action_model)
        return merged

    def _primary_action_context(
        self, record, settings=None, base_context=None, action_model=None
    ):
        """Context for the card's main button.

        Drops ``search_default_*`` keys from the base action so their UI
        filters cannot hide rows the card graph already counted. Passes
        the viewer's measure / group-by so the opened graph matches the
        mini-chart when the target model is the same.
        """
        self.ensure_one()
        if settings is None:
            settings = self._effective_graph_settings()
        ctx = self._eval_context_with_record(base_context, record)
        # Inherited actions (e.g. CRM Enterprise dashboard) ship their own
        # search defaults; keeping them would show a different set of rows
        # than the card graph, even with a matching domain.
        ctx = {
            key: value
            for key, value in ctx.items()
            if not (isinstance(key, str) and key.startswith("search_default_"))
        }
        ctx.update(
            self._eval_context_with_record(self.primary_action_context, record)
        )
        # Only mirror graph groupbys/measure when the opened action uses the
        # same model as the mini-chart. Otherwise SearchModel.createNewGroupBy
        # receives fields that are not on the target search view and OWL
        # crashes on `const { string } = field` (field undefined).
        if (
            self.graph_model
            and self.graph_model in self.env
            and (not action_model or action_model == self.graph_model)
        ):
            groupby = settings.get("groupby")
            # Blueprint stores ``field:aggregator`` for read_group; Odoo
            # Graph/Pivot context expects the bare field name.
            measure = self._odoo_view_measure_name(settings.get("measure"))
            groupbys = settings.get("groupbys") or ([groupby] if groupby else [])
            if groupbys:
                ctx["graph_groupbys"] = groupbys
            if measure:
                ctx["graph_measure"] = measure
                ctx["pivot_measures"] = (
                    [measure] if measure != "__count" else []
                )
            # Match the mini-chart (bar vs line). Card type is computed on
            # the host; fall back to the same <6-points → bar rule.
            graph_mode = False
            if "dashboard_graph_type" in record._fields:
                graph_mode = record.dashboard_graph_type
            if not graph_mode:
                payloads = self._build_graph_payloads(record)
                graph_mode = (payloads.get(record.id) or {}).get("type")
            if graph_mode:
                ctx["graph_mode"] = graph_mode
        ctx["dashboard_blueprint_key"] = self.key
        ctx["active_id"] = record.id
        return ctx

    @api.model
    def _odoo_view_measure_name(self, measure):
        """Strip ``:aggregator`` so Graph/Pivot can resolve ``fields[measure]``."""
        if not measure:
            return measure
        if measure == "__count" or ":" not in measure:
            return measure
        return measure.partition(":")[0]

    def _resolved_primary_action_xmlid(self):
        """Primary action xmlid: first installed variant, else the default."""
        self.ensure_one()
        for variant in self.alternate_action_ids.sorted("sequence"):
            if self._modules_installed(variant.module_depends):
                return variant.action_xmlid
        return self.primary_action_xmlid

    def _resolved_primary_label(self):
        """Button text, flipped per viewer when a reference scope is set."""
        self.ensure_one()
        default_label = self.primary_button_label or _("Open Analysis")
        scope = self.primary_label_alt_scope_id
        if not scope or not self.primary_label_alt:
            return default_label
        pref = self._current_pref()
        active = (
            scope in pref.scope_ids if pref else scope.default_on
        )
        return default_label if active else self.primary_label_alt

    def _primary_host_leaf(self, record):
        """Domain leaf linking the primary action back to one card.

        Direct (no relation path) links honour ``include_child_records`` with
        ``child_of``; anything routed through a relation path keeps the
        exact-match/​multi-hop behaviour, since hierarchy there would need
        folding support the path model does not have yet.
        """
        self.ensure_one()
        path = self._graph_link_path()
        if path or not self.include_child_records:
            return self._host_domain_leaf([record.id], path=path)
        path_str, _source = self._resolve_graph_path_string()
        link = path_str or self.graph_data_field
        if not link or not relation_path_is_direct(link):
            return self._host_domain_leaf([record.id], path=path)
        return (link, "child_of", record.id)

    def _eval_domain_with_record(self, domain_str, record):
        """Parse domain and replace {{id}} with the host record id."""
        self.ensure_one()
        domain = self._safe_domain(domain_str)
        resolved = []
        for item in domain:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 3
                and item[2] == "{{id}}"
            ):
                resolved.append((item[0], item[1], record.id))
            else:
                resolved.append(item)
        return resolved

    def _eval_context_with_record(self, context_value, record):
        """Normalize action context, {{id}} replacements, and ``__de__`` tokens.

        Token resolution is generic (any model): see
        ``tools.condition_domain.compile_context_value``.
        """
        self.ensure_one()
        if not context_value:
            return {}
        if isinstance(context_value, dict):
            ctx = dict(context_value)
        else:
            raw = str(context_value).replace("{{id}}", str(record.id))
            try:
                ctx = json.loads(raw) if raw.lstrip().startswith("{") else None
            except Exception:
                ctx = None
            if ctx is None:
                try:
                    ctx = safe_eval(raw)
                except Exception:
                    return {}
            if not isinstance(ctx, dict):
                return {}
        resolved = {}
        for key, value in ctx.items():
            if value == "{{id}}":
                resolved[key] = record.id
            elif isinstance(value, str):
                resolved[key] = value.replace("{{id}}", str(record.id))
            else:
                resolved[key] = value
        return compile_context_value(
            resolved,
            self.env,
            record=record,
            model_name=record._name if record is not None else None,
        )

    @api.model
    def _safe_domain(self, domain_str, strict=False):
        if not domain_str:
            return []
        try:
            domain = (
                literal_eval(domain_str)
                if isinstance(domain_str, str)
                else domain_str
            )
        except Exception as exc:
            if strict:
                raise UserError(
                    _("Custom Filter must be a valid Python domain list.")
                ) from exc
            return []
        if not isinstance(domain, (list, tuple)):
            if strict:
                raise UserError(
                    _("Custom Filter must be a valid Python domain list.")
                )
            return []
        return list(domain)


class DashboardBlueprintSlot(models.Model):
    _name = "dashboard.blueprint.slot"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Blueprint Slot"
    _order = "sequence, id"

    blueprint_id = fields.Many2one(
        "dashboard.blueprint", required=True, ondelete="cascade", index=True
    )
    host_model_name = fields.Char(
        related="blueprint_id.host_model_name", readonly=True
    )
    key = fields.Char(required=True)
    name = fields.Char(required=True, translate=True)
    section = fields.Selection(SLOT_SECTIONS, required=True, default="kpi")
    sequence = fields.Integer(default=10)
    label = fields.Char(translate=True)
    label_plural = fields.Char(translate=True)
    label_alt = fields.Char(
        translate=True,
        string="Label when group matches",
        help="Optional wording used instead of Label when the viewer is in "
        "one of the groups below (e.g. 'Unassigned Lead' when CRM Uses Leads).",
    )
    label_plural_alt = fields.Char(
        translate=True,
        string="Plural when group matches",
    )
    label_alt_groups_xmlids = fields.Char(
        string="Flip label for groups",
        help="Comma-separated group xmlids. When the viewer has any of these, "
        "the alternate labels above are used.",
    )
    icon = fields.Char(help="Font Awesome class without 'fa ', e.g. fa-star")
    style = fields.Selection(
        [("default", "Default"), ("danger", "Danger")],
        default="default",
        required=True,
    )
    groups_xmlids = fields.Char(
        help="Comma-separated group xmlids required to see this slot."
    )
    module_depends = fields.Char(
        help="Comma-separated modules that must be installed."
    )
    visible_if_context = fields.Char(
        help="JSON object of context keys that must match, "
        'e.g. {"in_pos_app": true}'
    )
    show_if_zero = fields.Boolean(default=False)

    ui_number_from_related = fields.Boolean(
        string="Number from related records",
        compute="_compute_ui_number_source",
    )
    ui_number_from_host = fields.Boolean(
        string="Number from card fields",
        compute="_compute_ui_number_source",
    )

    # Value sources (host field OR remote compute)
    count_field = fields.Char(string="Count Field Name")
    amount_field = fields.Char(string="Amount Field Name")
    compute_model = fields.Char(string="Count Model Name")
    compute_domain = fields.Char(default="[]")
    compute_aggregator = fields.Char(default="__count")
    amount_aggregator = fields.Char(
        help="Optional second aggregate, e.g. expected_revenue:sum"
    )
    relate_field = fields.Char(
        string="Link to Host",
        help="Many2one path on the count model that points back to this "
        "host (same meaning as Link to Host on the graph). Leave empty "
        "to reuse the chart link field.",
    )
    relation_path_id = fields.Many2one(
        "dashboard.relation.path",
        string="Relation Path (legacy)",
        ondelete="restrict",
        help="Deprecated: prefer Link to Host. Kept for migration.",
    )
    condition_ids = fields.Many2many(
        "dashboard.condition",
        "dashboard_slot_condition_rel",
        "slot_id",
        "condition_id",
        string="Conditions",
        help="Reusable filters merged into the count and the opened list. "
        "Use these for relative dates (overdue) and group-dependent values.",
    )
    action_variant_ids = fields.One2many(
        "dashboard.blueprint.slot.action.variant",
        "slot_id",
        string="Action by installed app",
        copy=True,
        help="When a listed app is installed, open that screen instead.",
    )

    # Action sources
    action_xmlid = fields.Char()
    action_method = fields.Char(
        help="Optional host-record method to call instead of opening an "
        "action xmlid (e.g. open_follow_up_report). Used when the screen "
        "is built by another app and needs record-specific params.",
    )
    action_model = fields.Char(string="Action Model Name")
    action_domain = fields.Char(default="[]")
    action_context = fields.Char(
        default="{}",
        help="JSON context; use {{id}} for host record id.",
    )
    action_view_mode = fields.Char(default="list,form")

    # ------------------------------------------------------------------
    # Configuration pickers (see dashboard_mirror.py for the pattern)
    # ------------------------------------------------------------------

    compute_model_id = fields.Many2one(
        "ir.model",
        string="Count Model",
        compute="_compute_compute_model_id",
        inverse="_inverse_compute_model_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Records this figure counts, e.g. Opportunities.",
    )
    relate_field_id = fields.Many2one(
        "ir.model.fields",
        string="Link to Host",
        compute="_compute_relate_field_id",
        inverse="_inverse_relate_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Many2one on the count model that links rows to this host. "
        "Leave empty to reuse the graph Link to Host field.",
    )
    count_measure_field_id = fields.Many2one(
        "ir.model.fields",
        string="Counting",
        compute="_compute_count_measure",
        inverse="_inverse_count_measure",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Leave empty to count how many records there are.",
    )
    count_aggregator_type = fields.Selection(
        AGGREGATORS,
        string="Counted as",
        compute="_compute_count_measure",
        inverse="_inverse_count_measure",
        store=True,
        readonly=False,
    )
    amount_measure_field_id = fields.Many2one(
        "ir.model.fields",
        string="Amount shown",
        compute="_compute_amount_measure",
        inverse="_inverse_amount_measure",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Optional monetary total displayed beside the figure.",
    )
    amount_aggregator_type = fields.Selection(
        AGGREGATORS,
        string="Amount as",
        compute="_compute_amount_measure",
        inverse="_inverse_amount_measure",
        store=True,
        readonly=False,
    )
    count_field_id = fields.Many2one(
        "ir.model.fields",
        string="Count Field",
        compute="_compute_count_field_id",
        inverse="_inverse_count_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Take the figure straight from a field on the card's record "
        "instead of counting anything.",
    )
    amount_field_id = fields.Many2one(
        "ir.model.fields",
        string="Amount Field",
        compute="_compute_amount_field_id",
        inverse="_inverse_amount_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
    )
    action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Action",
        compute="_compute_action_id",
        inverse="_inverse_action_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Existing screen to open on click.",
    )
    action_model_id = fields.Many2one(
        "ir.model",
        string="Action Model",
        compute="_compute_action_model_id",
        inverse="_inverse_action_model_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Used when no existing screen is chosen.",
    )
    group_ids = fields.Many2many(
        "res.groups",
        string="Only for",
        compute="_compute_group_ids",
        inverse="_inverse_group_ids",
        store=True,
        readonly=False,
        help="Leave empty to show this item to everyone.",
    )
    module_ids = fields.Many2many(
        "ir.module.module",
        string="Required Apps",
        compute="_compute_slot_module_ids",
        inverse="_inverse_slot_module_ids",
        store=True,
        readonly=False,
    )
    value_mode = fields.Selection(
        SLOT_VALUE_MODES,
        string="Shows",
        default="count",
        required=True,
        help="What the card displays for this row. Drives which amount "
        "fields are used and what the runtime sends to the card.",
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

    @api.depends("compute_model")
    def _compute_compute_model_id(self):
        for rec in self:
            rec.compute_model_id = rec._mirror_model(rec.compute_model)

    def _inverse_compute_model_id(self):
        for rec in self:
            rec.compute_model = rec.compute_model_id.model or False

    @api.depends("relate_field", "compute_model")
    def _compute_relate_field_id(self):
        for rec in self:
            rec.relate_field_id = rec._mirror_field(
                rec.compute_model, rec.relate_field
            )

    def _inverse_relate_field_id(self):
        for rec in self:
            rec.relate_field = rec.relate_field_id.name or False

    @api.depends("compute_aggregator", "compute_model")
    def _compute_count_measure(self):
        for rec in self:
            raw = rec.compute_aggregator or "__count"
            name, _sep, aggregator = raw.partition(":")
            if raw == "__count":
                rec.count_measure_field_id = False
                rec.count_aggregator_type = rec.count_aggregator_type or False
                continue
            rec.count_measure_field_id = rec._mirror_field(rec.compute_model, name)
            rec.count_aggregator_type = aggregator or "sum"

    def _inverse_count_measure(self):
        for rec in self:
            if not rec.count_measure_field_id:
                rec.compute_aggregator = "__count"
                continue
            rec.compute_aggregator = "%s:%s" % (
                rec.count_measure_field_id.name,
                rec.count_aggregator_type or "sum",
            )

    @api.depends("amount_aggregator", "compute_model")
    def _compute_amount_measure(self):
        for rec in self:
            name, _sep, aggregator = (rec.amount_aggregator or "").partition(":")
            rec.amount_measure_field_id = rec._mirror_field(rec.compute_model, name)
            rec.amount_aggregator_type = aggregator or False

    def _inverse_amount_measure(self):
        for rec in self:
            if not rec.amount_measure_field_id:
                rec.amount_aggregator = False
                continue
            rec.amount_aggregator = "%s:%s" % (
                rec.amount_measure_field_id.name,
                rec.amount_aggregator_type or "sum",
            )

    @api.depends("count_field", "host_model_name")
    def _compute_count_field_id(self):
        for rec in self:
            rec.count_field_id = rec._mirror_field(
                rec.host_model_name, rec.count_field
            )

    def _inverse_count_field_id(self):
        for rec in self:
            rec.count_field = rec.count_field_id.name or False

    @api.depends("amount_field", "host_model_name")
    def _compute_amount_field_id(self):
        for rec in self:
            rec.amount_field_id = rec._mirror_field(
                rec.host_model_name, rec.amount_field
            )

    def _inverse_amount_field_id(self):
        for rec in self:
            rec.amount_field = rec.amount_field_id.name or False

    @api.depends("action_xmlid")
    def _compute_action_id(self):
        for rec in self:
            rec.action_id = rec._mirror_record(
                "ir.actions.act_window", rec.action_xmlid
            )

    def _inverse_action_id(self):
        for rec in self:
            rec.action_xmlid = rec._mirror_xmlid(rec.action_id)

    @api.depends("action_model")
    def _compute_action_model_id(self):
        for rec in self:
            rec.action_model_id = rec._mirror_model(rec.action_model)

    def _inverse_action_model_id(self):
        for rec in self:
            rec.action_model = rec.action_model_id.model or False

    @api.depends("groups_xmlids")
    def _compute_group_ids(self):
        for rec in self:
            rec.group_ids = rec._mirror_records("res.groups", rec.groups_xmlids)

    def _inverse_group_ids(self):
        for rec in self:
            rec.groups_xmlids = rec._mirror_xmlids(rec.group_ids)

    @api.depends("module_depends")
    def _compute_slot_module_ids(self):
        Module = self.env["ir.module.module"].sudo()
        for rec in self:
            names = rec._mirror_names(rec.module_depends)
            rec.module_ids = Module.search([("name", "in", names)]) if names else False

    def _inverse_slot_module_ids(self):
        for rec in self:
            rec.module_depends = (
                ",".join(sorted(rec.module_ids.mapped("name"))) or False
            )

    @api.constrains(
        "relate_field",
        "relation_path_id",
        "compute_model",
        "blueprint_id",
    )
    def _check_slot_relation_path(self):
        for rec in self:
            path_str, source = rec._resolve_slot_path_string()
            if not path_str or not source:
                continue
            host = rec.blueprint_id.host_model_name
            if not host:
                continue
            # Inherited blueprint path is validated on the blueprint.
            if (
                not rec.relate_field
                and not rec.relation_path_id
                and path_str == (rec.blueprint_id._resolve_graph_path_string()[0] or "")
            ):
                continue
            validate_relation_path(rec.env, source, path_str, host)

    def _resolve_slot_mirrors(self):
        """Re-resolve this slot's own pickers, and its action variants'.

        Same idea as ``DashboardBlueprint._resolve_mirrors``, one level
        down: a slot referencing ``report_sale_crm`` before that module was
        installed stays broken forever otherwise, since nothing marks a
        static ``action_xmlid``/``compute_model`` dirty when the module
        installs later.
        """
        self._resolve_stale_mirrors(
            [
                ("compute_model_id", ("compute_model",)),
                ("relate_field_id", ("relate_field", "compute_model")),
                ("count_measure_field_id", ("compute_aggregator", "compute_model")),
                ("amount_measure_field_id", ("amount_aggregator", "compute_model")),
                ("count_field_id", ("count_field", "host_model_name")),
                ("amount_field_id", ("amount_field", "host_model_name")),
                ("action_id", ("action_xmlid",)),
                ("action_model_id", ("action_model",)),
                ("group_ids", ("groups_xmlids",)),
            ]
        )
        self.action_variant_ids._resolve_stale_mirrors(
            [("action_id", ("action_xmlid",))]
        )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [self._prepare_value_mode_vals(dict(vals)) for vals in vals_list]
        records = super().create(prepared)
        for bp in records.mapped("blueprint_id").filtered(lambda b: b.state == "published"):
            bp._sync_generated_artifacts()
        return records

    def write(self, vals):
        existing = self.value_mode if len(self) == 1 else None
        vals = self._prepare_value_mode_vals(dict(vals), existing_mode=existing)
        res = super().write(vals)
        for bp in self.mapped("blueprint_id").filtered(lambda b: b.state == "published"):
            bp._sync_generated_artifacts()
        return res

    def unlink(self):
        blueprints = self.mapped("blueprint_id")
        res = super().unlink()
        for bp in blueprints.filtered(lambda b: b.state == "published"):
            bp._sync_generated_artifacts()
        return res

    @api.model
    def _prepare_value_mode_vals(self, vals, existing_mode=None):
        """Keep amount sources coherent with Shows.

        Explicit Count only clears the amount. Setting an amount while still
        on Count only promotes the row to Count + Amount (seeds + pickers).
        """
        if vals.get("value_mode") == "count":
            vals["amount_aggregator"] = False
            return vals
        mode = vals.get("value_mode", existing_mode) or "count"
        if vals.get("amount_aggregator") and mode == "count":
            vals["value_mode"] = "count_amount"
        elif (
            vals.get("amount_field")
            and not vals.get("count_field")
            and not vals.get("compute_model")
            and "value_mode" not in vals
            and mode == "count"
        ):
            vals["value_mode"] = "amount"
        return vals

    def _wants_count(self):
        self.ensure_one()
        return (self.value_mode or "count") in ("count", "count_amount")

    def _wants_amount(self):
        self.ensure_one()
        return (self.value_mode or "count") in ("amount", "count_amount")

    @api.onchange("amount_measure_field_id")
    def _onchange_amount_measure_field_id(self):
        if self.amount_measure_field_id and self.value_mode == "count":
            self.value_mode = "count_amount"

    @api.onchange("value_mode")
    def _onchange_value_mode(self):
        if self.value_mode == "count":
            self.amount_measure_field_id = False
            self.amount_aggregator_type = False

    @api.constrains("value_mode", "section", "amount_aggregator")
    def _check_value_mode(self):
        for rec in self:
            if rec.section != "kpi":
                continue
            if rec._wants_amount() and not rec.amount_aggregator:
                raise ValidationError(
                    _(
                        "Set Amount shown for KPI “%(name)s” when Shows is "
                        "Amount only or Count + Amount.",
                        name=rec.name,
                    )
                )

    def _is_visible(self, ctx):
        """Visibility depends on modules, groups and context — never on the record."""
        self.ensure_one()
        bp = self.blueprint_id
        if not bp._modules_installed(self.module_depends):
            return False
        user = self.env.user
        for group in (self.groups_xmlids or "").split(","):
            group = group.strip()
            if group and not user.has_group(group):
                return False
        if self.visible_if_context:
            try:
                rules = json.loads(self.visible_if_context)
            except Exception:
                rules = {}
            for key, expected in rules.items():
                if bool(ctx.get(key)) != bool(expected):
                    return False
        return True

    def _eval_domain(self, domain_str, record):
        domain = self.blueprint_id._safe_domain(domain_str)
        # Replace magic tokens
        resolved = []
        for item in domain:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 3
                and item[2] == "{{id}}"
            ):
                resolved.append((item[0], item[1], record.id))
            else:
                resolved.append(item)
        return self._merge_condition_domain(resolved, record)

    def _eval_domain_batch(self, domain_str, records):
        """Like ``_eval_domain`` but resolves ``{{id}}`` against a recordset."""
        domain = self.blueprint_id._safe_domain(domain_str)
        resolved = []
        for item in domain:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 3
                and item[2] == "{{id}}"
            ):
                resolved.append((item[0], "in", records.ids))
            else:
                resolved.append(item)
        # Conditions that need a single card (value_type=record) are skipped
        # in the batch path; relative dates and static rules still apply.
        return self._merge_condition_domain(resolved, record=None)

    def _merge_condition_domain(self, domain, record=None):
        """AND the slot's reusable conditions onto an already-resolved domain."""
        self.ensure_one()
        extra = self.env["dashboard.condition"].merge_conditions(
            self.condition_ids, record=record
        )
        if not extra:
            return domain
        return self.blueprint_id._merge_domains(domain, extra)

    def _compute_values_batch(self, records):
        """Return ``{record_id: (count, amount)}`` for this slot.

        Aggregation over a related model is done with a single grouped query
        for the whole recordset, so adding cards to the dashboard does not add
        queries. ``value_mode`` then drops the metrics the card should not show.
        """
        self.ensure_one()
        host_count = (
            self.count_field
            if self._wants_count() and self.count_field in records._fields
            else None
        )
        host_amount = (
            self.amount_field
            if self._wants_amount() and self.amount_field in records._fields
            else None
        )
        values = {
            record.id: (
                record[host_count] or 0 if host_count else None,
                record[host_amount] or 0 if host_amount else None,
            )
            for record in records
        }

        if not self.compute_model or self.compute_model not in self.env:
            return self._apply_value_mode_to_values(values)

        path = self._slot_link_path()
        path_str, _source = self._resolve_slot_path_string()
        relate = (
            path.first_hop_field
            if path
            else (path_str or self.relate_field or self.blueprint_id.graph_data_field)
        )
        if not relate and not path:
            # Nothing links the aggregate back to a card; the same figure would
            # apply to every card, so compute it once.
            values = self._apply_aggregate(values, records, relate=None, path=None)
        else:
            values = self._apply_aggregate(
                values, records, relate=relate, path=path
            )
        return self._apply_value_mode_to_values(values)

    def _apply_value_mode_to_values(self, values):
        """Null out count/amount the Shows mode should not expose."""
        self.ensure_one()
        mode = self.value_mode or "count"
        if mode == "count":
            return {rid: (count, None) for rid, (count, _amount) in values.items()}
        if mode == "amount":
            return {rid: (None, amount) for rid, (_count, amount) in values.items()}
        return values

    def _resolve_slot_path_string(self):
        """Return ``(dotted_path, source_model)`` for this slot's link."""
        self.ensure_one()
        bp = self.blueprint_id
        legacy = self.relation_path_id
        if legacy and legacy.domain_field:
            return (
                legacy.domain_field,
                legacy.source_model or self.compute_model or bp.graph_model,
            )
        if self.relate_field:
            return (
                self.relate_field,
                self.compute_model or bp.graph_model,
            )
        # Inherit blueprint chart link when models align.
        if (
            not self.compute_model
            or self.compute_model == bp.graph_model
        ):
            return bp._resolve_graph_path_string()
        return False, False

    def _slot_link_path(self):
        """Multi-hop path for this slot, or falsy for direct / missing links."""
        self.ensure_one()
        path_str, source = self._resolve_slot_path_string()
        if not path_str or not source or relation_path_is_direct(path_str):
            return None
        return RelationPathInfo(
            env=self.env, path=path_str, source_model=source
        )

    def _honours_restrict_scope(self):
        """Whether gear restrict scopes (e.g. My Pipeline) apply to this slot.

        Product matrix: right KPIs only, and only when counting the graph
        model. Bottoms and Manage menus stay partner/action context only.
        """
        self.ensure_one()
        bp = self.blueprint_id
        return (
            self.section == "kpi"
            and bool(self.compute_model)
            and self.compute_model == bp.graph_model
        )

    def _apply_aggregate(self, values, records, relate, path=None):
        self.ensure_one()
        Model = self.env[self.compute_model]
        aggregate = self.compute_aggregator or "__count"
        aggregates = []
        if self._wants_count() or not self._wants_amount():
            aggregates.append(aggregate)
        if self._wants_amount() and self.amount_aggregator:
            aggregates.append(self.amount_aggregator)
        if not aggregates:
            aggregates = [aggregate]
        domain = self._eval_domain_batch(self.compute_domain, records)
        if self._honours_restrict_scope():
            domain = list(domain) + self.blueprint_id._restrict_scope_domain()
        fold_map = None
        if not path and relate and self.blueprint_id._hierarchy_enabled():
            fold_map = self.blueprint_id._hierarchy_fold_map(records.ids)
            leaf = (relate, "in", list(fold_map.keys())) if fold_map else False
        else:
            leaf = self.blueprint_id._host_domain_leaf(
                records.ids, path=path, link_field=relate if not path else None
            )
        if leaf:
            domain = list(domain) + [leaf]
        try:
            groups = Model.formatted_read_group(
                domain=domain,
                groupby=[relate] if relate else [],
                aggregates=aggregates,
            )
        except Exception:
            _logger.debug(
                "Slot compute failed %s/%s", self.blueprint_id.key, self.key
            )
            return values

        hop_to_hosts = (
            path.map_first_hop_to_hosts(records.ids)
            if path and not path.is_direct
            else None
        )

        by_host = {}
        for group in groups:
            hop_id = (
                self.blueprint_id._graph_group_id(group.get(relate))
                if relate
                else None
            )
            if hop_to_hosts is not None:
                host_ids = hop_to_hosts.get(hop_id, [])
            elif fold_map is not None:
                host_ids = fold_map.get(hop_id, [])
            elif relate:
                host_ids = [hop_id]
            else:
                host_ids = [None]
            count = (
                (group.get(aggregate, 0) or 0)
                if (self._wants_count() or not self._wants_amount())
                else None
            )
            amount = (
                (group.get(self.amount_aggregator, 0) or 0)
                if self._wants_amount() and self.amount_aggregator
                else None
            )
            for host_id in host_ids:
                prev_count, prev_amount = by_host.get(host_id, (None, None))
                if count is not None:
                    prev_count = (prev_count or 0) + count
                if amount is not None:
                    prev_amount = (prev_amount or 0) + amount
                by_host[host_id] = (prev_count, prev_amount)

        for record in records:
            got = by_host.get(record.id if relate else None)
            if got is None:
                # No matching rows for this card: zero the metrics this mode asks for.
                count = 0 if self._wants_count() else None
                amount = (
                    0
                    if self._wants_amount() and self.amount_aggregator
                    else None
                )
            else:
                count, amount = got
            previous_count, previous_amount = values[record.id]
            values[record.id] = (
                count if count is not None else previous_count,
                amount if amount is not None else previous_amount,
            )
        return values

    def _resolved_labels(self):
        """Singular / plural text, flipped when the viewer matches a group.

        Slot config is read as sudo (same as other runtime helpers) so a
        salesperson without the engine ACL still gets the right wording;
        the group check always uses the real viewer.
        """
        self.ensure_one()
        slot = self.sudo()
        singular = slot.label or slot.name
        plural = slot.label_plural or singular
        if slot.label_alt_groups_xmlids and (
            slot.label_alt or slot.label_plural_alt
        ):
            if any(
                self.env.user.has_group(group)
                for group in slot._mirror_names(slot.label_alt_groups_xmlids)
            ):
                singular = slot.label_alt or singular
                plural = slot.label_plural_alt or slot.label_alt or plural
        return singular, plural

    def _to_slot_item(self, record, values=None):
        self.ensure_one()
        if values is None:
            values = self._compute_values_batch(record).get(record.id, (None, None))
        count, amount = values
        # Hide when every metric this Shows mode supplies is zero.
        # Amount-only host fields (e.g. total_due / total_invoiced) use the
        # same show_if_zero flag as count badges — model-agnostic.
        if not self.show_if_zero:
            count_empty = count is None or not count
            amount_empty = amount is None or not amount
            mode = self.value_mode or "count"
            if mode == "amount":
                if amount_empty:
                    return False
            elif mode == "count":
                if count_empty:
                    return False
            elif (count is not None or amount is not None) and count_empty and amount_empty:
                return False
        singular, plural = self._resolved_labels()
        label = plural if count is not None and count != 1 else singular
        item = {
            "key": self.key,
            "sequence": self.sequence,
            "label": label,
            "style": self.style or "default",
            "method": "action_dashboard_engine_slot",
            # Consumed by the dashboard_slots field widget, which passes it to
            # doActionButton; action_dashboard_engine_slot reads it back.
            "context": {
                "dashboard_blueprint_key": self.blueprint_id.key,
                "dashboard_slot_key": self.key,
            },
        }
        if self.icon:
            item["icon"] = self.icon
        if count is not None:
            item["count"] = count
        if amount is not None:
            item["amount"] = amount
            currency = getattr(record, "currency_id", False) or self.env.company.currency_id
            item["currency_id"] = currency.id
        return item

    def _resolved_action_xmlid(self):
        """Action to open: first matching module variant, else the slot default."""
        self.ensure_one()
        bp = self.blueprint_id
        for variant in self.action_variant_ids.sorted("sequence"):
            if bp._modules_installed(variant.module_depends):
                return variant.action_xmlid
        return self.action_xmlid

    def _prepare_action(self, record):
        self.ensure_one()
        # Host method wins: other apps often return a fully built client
        # action (report_id + partner params) that xmlid alone cannot express.
        if self.action_method:
            method = self.action_method.strip()
            if method and hasattr(record, method) and callable(getattr(record, method)):
                try:
                    return getattr(record, method)()
                except Exception:
                    _logger.warning(
                        "Slot host method %s failed for %s/%s",
                        method,
                        self.blueprint_id.key,
                        self.key,
                        exc_info=True,
                    )
                    return False
            _logger.warning(
                "Missing host method %s for slot %s/%s",
                method,
                self.blueprint_id.key,
                self.key,
            )
            return False

        action_xmlid = self._resolved_action_xmlid()
        if action_xmlid:
            try:
                action = self.env.ref(action_xmlid).sudo()
                result = action._get_action_dict()
            except Exception:
                _logger.warning(
                    "Missing action xmlid %s for slot %s",
                    action_xmlid,
                    self.key,
                )
                return False
        elif self.action_model and self.action_model in self.env:
            result = {
                "type": "ir.actions.act_window",
                "name": self.label or self.name,
                "res_model": self.action_model,
                "view_mode": self.action_view_mode or "list,form",
                "views": [[False, "list"], [False, "form"]],
                "target": "current",
            }
        else:
            return False

        domain = self._eval_domain(self.action_domain, record)
        if self._honours_restrict_scope():
            domain = list(domain) + self.blueprint_id._restrict_scope_domain()
        if domain:
            existing = result.get("domain") or []
            if isinstance(existing, str):
                existing = self.blueprint_id._safe_domain(existing)
            result["domain"] = self.blueprint_id._merge_domains(existing, domain)

        ctx = self.blueprint_id._eval_context_with_record(
            self.action_context, record
        )
        result_ctx = result.get("context") or {}
        if isinstance(result_ctx, str):
            try:
                result_ctx = safe_eval(result_ctx)
            except Exception:
                result_ctx = {}
        # Drop inherited search defaults (e.g. CRM "My Pipeline") so they
        # cannot hide rows the slot domain / conditions already selected.
        # Slot action_context may re-add intentional search_default_* keys.
        result_ctx = {
            key: value
            for key, value in result_ctx.items()
            if not (isinstance(key, str) and key.startswith("search_default_"))
        }
        result["context"] = {
            **result_ctx,
            **ctx,
            "dashboard_blueprint_key": self.blueprint_id.key,
            "active_id": record.id,
            "active_ids": [record.id],
        }
        return result


class DashboardBlueprintSlotActionVariant(models.Model):
    """Alternate screen to open when a given app is installed.

    Replaces the v1 ``crm_enterprise: { action: ... }`` branches without
    Python: the first variant whose apps are present wins.
    """

    _name = "dashboard.blueprint.slot.action.variant"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Slot Action Variant"
    _order = "sequence, id"

    slot_id = fields.Many2one(
        "dashboard.blueprint.slot", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(translate=True)
    module_depends = fields.Char(
        help="Comma-separated module technical names that must be installed."
    )
    module_ids = fields.Many2many(
        "ir.module.module",
        string="Required Apps",
        compute="_compute_module_ids",
        inverse="_inverse_module_ids",
        store=True,
        readonly=False,
    )
    action_xmlid = fields.Char()
    action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Action",
        compute="_compute_action_id",
        inverse="_inverse_action_id",
        store=True,
        readonly=False,
        ondelete="set null",
    )

    @api.depends("module_depends")
    def _compute_module_ids(self):
        Module = self.env["ir.module.module"].sudo()
        for rec in self:
            names = rec._mirror_names(rec.module_depends)
            rec.module_ids = Module.search([("name", "in", names)]) if names else False

    def _inverse_module_ids(self):
        for rec in self:
            rec.module_depends = (
                ",".join(sorted(rec.module_ids.mapped("name"))) or False
            )

    @api.depends("action_xmlid")
    def _compute_action_id(self):
        for rec in self:
            rec.action_id = rec._mirror_record(
                "ir.actions.act_window", rec.action_xmlid
            )

    def _inverse_action_id(self):
        for rec in self:
            rec.action_xmlid = rec._mirror_xmlid(rec.action_id)


class DashboardBlueprintActionVariant(models.Model):
    """Alternate screen for the card's primary button.

    Same idea as :class:`DashboardBlueprintSlotActionVariant`, one level up:
    replaces v1's ``crm_enterprise`` vs ``report_sale_crm`` primary-button
    branches. The first variant whose apps are all installed wins.
    """

    _name = "dashboard.blueprint.action.variant"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Blueprint Primary Action Variant"
    _order = "sequence, id"

    blueprint_id = fields.Many2one(
        "dashboard.blueprint", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(translate=True)
    module_depends = fields.Char(
        help="Comma-separated module technical names that must be installed."
    )
    module_ids = fields.Many2many(
        "ir.module.module",
        string="Required Apps",
        compute="_compute_module_ids",
        inverse="_inverse_module_ids",
        store=True,
        readonly=False,
    )
    action_xmlid = fields.Char()
    action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Action",
        compute="_compute_action_id",
        inverse="_inverse_action_id",
        store=True,
        readonly=False,
        ondelete="set null",
    )

    @api.depends("module_depends")
    def _compute_module_ids(self):
        Module = self.env["ir.module.module"].sudo()
        for rec in self:
            names = rec._mirror_names(rec.module_depends)
            rec.module_ids = Module.search([("name", "in", names)]) if names else False

    def _inverse_module_ids(self):
        for rec in self:
            rec.module_depends = (
                ",".join(sorted(rec.module_ids.mapped("name"))) or False
            )

    @api.depends("action_xmlid")
    def _compute_action_id(self):
        for rec in self:
            rec.action_id = rec._mirror_record(
                "ir.actions.act_window", rec.action_xmlid
            )

    def _inverse_action_id(self):
        for rec in self:
            rec.action_xmlid = rec._mirror_xmlid(rec.action_id)


class DashboardBlueprintScope(models.Model):
    """A tick box in the dashboard's settings popup.

    Scopes are what "Pipeline", "Leads" and "My Pipeline" are on the
    hand-written dashboards: named slices of the chart's data that each user
    turns on or off for themselves.

    Label / help text shown in the gear come from ``name`` + ``description``,
    optionally overridden by ``label_ids`` rows whose ``module_depends`` are
    all installed — so presentation is data-driven, never hardcoded in the
    shared settings form.
    """

    _name = "dashboard.blueprint.scope"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Data Scope"
    _order = "sequence, id"
    _rec_name = "name"

    blueprint_id = fields.Many2one(
        "dashboard.blueprint", required=True, ondelete="cascade", index=True
    )
    graph_model = fields.Char(related="blueprint_id.graph_model", readonly=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True, string="Name")
    description = fields.Char(
        translate=True,
        string="Description",
        help="Short explanation shown under the label in the settings popup. "
        "Leave empty for a label-only tick box.",
    )
    label_ids = fields.One2many(
        "dashboard.blueprint.scope.label",
        "scope_id",
        string="Label Variants",
        help="Optional alternate labels / help text that activate when the "
        "listed modules are installed (most specific match wins).",
    )
    mode = fields.Selection(
        [
            ("include", "Include"),
            ("restrict", "Restrict"),
        ],
        default="include",
        required=True,
        help="Include boxes are combined (union). Restrict boxes narrow "
        "the result (intersection), e.g. 'only mine'.",
    )
    domain = fields.Char(default="[]", string="Domain")
    default_on = fields.Boolean(default=True, string="Default")
    display_label = fields.Char(compute="_compute_presentation")
    display_description = fields.Char(compute="_compute_presentation")

    @api.depends(
        "name",
        "description",
        "label_ids.sequence",
        "label_ids.name",
        "label_ids.description",
        "label_ids.module_depends",
    )
    def _compute_presentation(self):
        for rec in self:
            presented = rec._presentation()
            rec.display_label = presented["name"]
            rec.display_description = presented["description"]

    def _presentation(self):
        """Resolve the label / help currently shown in the gear popup."""
        self.ensure_one()
        best = self.env["dashboard.blueprint.scope.label"]
        best_score = -1
        for label in self.label_ids:
            if not self.env["dashboard.blueprint"]._modules_installed_static(
                label.module_depends
            ):
                continue
            # Prefer the most specific variant (more modules / higher sequence).
            module_count = len(
                [n for n in (label.module_depends or "").split(",") if n.strip()]
            )
            score = (module_count * 1000) + (label.sequence or 0)
            if score >= best_score:
                best = label
                best_score = score
        return {
            "name": (best.name if best else None) or self.name,
            "description": (
                (best.description if best else None) or self.description or ""
            ),
        }

    def _scope_domain(self):
        """Domain for this scope, with ``uid`` resolved to the reader."""
        self.ensure_one()
        try:
            return list(
                safe_eval(self.domain or "[]", {"uid": self.env.uid, "user": self.env.user})
            )
        except Exception:
            _logger.warning(
                "Dashboard engine: unreadable scope domain on %s", self.name,
                exc_info=True,
            )
            return []


class DashboardBlueprintScopeLabel(models.Model):
    """Optional module-aware label / help override for a settings tick box.

    Example: a "My Pipeline" restrict-scope can show "My Pipeline and Sales
    Orders" (with matching help) when ``sale_management`` is installed, without
    any CRM-specific branching in the shared settings form.
    """

    _name = "dashboard.blueprint.scope.label"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Scope Label Variant"
    _order = "sequence, id"

    scope_id = fields.Many2one(
        "dashboard.blueprint.scope", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    module_depends = fields.Char(
        string="Required Apps",
        help="Comma-separated module technical names. This variant is used "
        "only when every listed module is installed. Leave empty to always "
        "match (useful as a catch-all override).",
    )
    name = fields.Char(required=True, translate=True, string="Name")
    description = fields.Char(translate=True, string="Description")


class DashboardBlueprintHeaderItem(models.Model):
    """One line of the card header, below the title.

    Subtitle and inline text stay under the title; alignment only left/center/
    right-justifies the line. Icons stay on any inline line. Multi-record
    fields with Inline + Right still use the far-right tags column.
    """

    _name = "dashboard.blueprint.header.item"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Card Header Line"
    _order = "sequence, id"

    blueprint_id = fields.Many2one(
        "dashboard.blueprint", required=True, ondelete="cascade", index=True
    )
    host_model_name = fields.Char(
        related="blueprint_id.host_model_name", readonly=True
    )
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        [
            ("subtitle", "Subtitle"),
            ("inline", "Inline"),
        ],
        required=True,
        default="subtitle",
        help="Subtitle stacks muted text under the title. Inline joins detail "
        "rows or tag columns; use Alignment to place them.",
    )
    alignment = fields.Selection(
        [
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        required=True,
        default="left",
        help="Horizontal placement for this line (subtitle and inline).",
    )
    icon = fields.Selection(
        HEADER_ICONS,
        help="Small icon shown before the text.",
    )
    separator = fields.Selection(
        HEADER_SEPARATORS,
        string="Shown as",
        default=", ",
        help="How multiple field values are joined on Subtitle / Inline "
        "(e.g. Paris, France or Sales Manager at Acme). Ignored for tag "
        "fields pinned to the far-right column (Inline + Right).",
    )
    # Portable ordered technical names (source of truth for export / seeds).
    field_names = fields.Char(
        string="Field Names",
        help="Comma-separated host field names in display order.",
    )
    ordered_field_ids = fields.Char(
        help="Machine-written selection order for the Fields tags.",
    )
    field_ids = fields.Many2many(
        "ir.model.fields",
        "dashboard_header_item_field_rel",
        "item_id",
        "field_id",
        string="Fields",
        compute="_compute_field_ids",
        inverse="_inverse_field_ids",
        store=True,
        readonly=False,
        help="Ordered host fields for this line. Subtitle / Inline join text "
        "fields with Shown as. Many2many / one2many fields render as tags "
        "on Inline Left/Center or the far-right column when Inline + Right.",
    )
    has_multiple_fields = fields.Boolean(
        compute="_compute_has_multiple_fields",
    )

    @api.depends("field_names", "host_model_name")
    def _compute_field_ids(self):
        for rec in self:
            names = rec._parse_field_names(rec.field_names)
            ordered = []
            for name in names:
                field = rec._mirror_field(rec.host_model_name, name)
                if field:
                    ordered.append(field.id)
            rec.field_ids = [(6, 0, ordered)]
            rec.ordered_field_ids = ",".join(str(i) for i in ordered) or False

    def _inverse_field_ids(self):
        for rec in self:
            ordered = rec._ordered_fields()
            rec.field_names = ",".join(f.name for f in ordered) or False
            rec.ordered_field_ids = ",".join(str(f.id) for f in ordered) or False

    @api.depends("field_names", "field_ids", "ordered_field_ids")
    def _compute_has_multiple_fields(self):
        for rec in self:
            rec.has_multiple_fields = len(rec._field_names()) > 1

    @api.onchange("field_ids")
    def _onchange_field_ids(self):
        for rec in self:
            rec.ordered_field_ids = compute_many2many_order(
                rec.field_ids.ids, rec.ordered_field_ids
            )
            ordered = rec._ordered_fields()
            rec.field_names = ",".join(f.name for f in ordered) or False

    @api.model
    def _parse_field_names(self, raw):
        return [name.strip() for name in (raw or "").split(",") if name.strip()]

    def _parse_ordered_field_ids(self, order_char, records):
        by_id = {field.id: field for field in records}
        try:
            ordered_ids = [
                int(value)
                for value in (order_char or "").split(",")
                if value.strip()
            ]
        except ValueError:
            ordered_ids = []
        ordered = [by_id[i] for i in ordered_ids if i in by_id]
        ordered += [field for field in records if field.id not in ordered_ids]
        return ordered

    def _ordered_fields(self):
        self.ensure_one()
        return self._parse_ordered_field_ids(self.ordered_field_ids, self.field_ids)

    @api.model
    def _map_legacy_header_kind(self, old_kind):
        return {
            "left": {"kind": "inline", "alignment": "left"},
            "right": {"kind": "inline", "alignment": "right"},
            "subtitle": {"kind": "subtitle", "alignment": "left"},
            "inline": {"kind": "inline", "alignment": "left"},
        }.get(old_kind, {"kind": "subtitle", "alignment": "left"})

    def _effective_kind_alignment(self):
        """Kind and alignment used for rendering (pre-migration rows included)."""
        self.ensure_one()
        if self.kind in ("left", "right"):
            return self._map_legacy_header_kind(self.kind)
        return {
            "kind": self.kind,
            "alignment": self.alignment or "left",
        }

    @api.model
    def _normalize_kind_alignment_vals(self, vals):
        vals = dict(vals)
        kind = vals.get("kind")
        if kind in ("left", "right", "detail", "tags"):
            if kind == "detail":
                kind = "left"
            elif kind == "tags":
                kind = "right"
            mapped = self._map_legacy_header_kind(kind)
            vals["kind"] = mapped["kind"]
            vals.setdefault("alignment", mapped["alignment"])
        elif kind in ("subtitle", "inline"):
            vals.setdefault("alignment", "left")
        return vals

    @api.model
    def _coerce_legacy_header_fields(self, vals):
        """Map old field_name / field2_name writes onto field_names."""
        vals = dict(vals)
        if vals.get("field_names"):
            vals.pop("field_name", None)
            vals.pop("field2_name", None)
            return self._normalize_kind_alignment_vals(vals)
        names = []
        if vals.get("field_name"):
            names.append(vals["field_name"])
        if vals.get("field2_name"):
            names.append(vals["field2_name"])
        vals.pop("field_name", None)
        vals.pop("field2_name", None)
        if names:
            vals["field_names"] = ",".join(names)
        return self._normalize_kind_alignment_vals(vals)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [
            self._coerce_legacy_header_fields(dict(vals)) for vals in vals_list
        ]
        records = super().create(prepared)
        for bp in records.mapped("blueprint_id").filtered(
            lambda b: b.state == "published"
        ):
            bp._sync_generated_artifacts()
        return records

    def write(self, vals):
        vals = self._coerce_legacy_header_fields(dict(vals))
        res = super().write(vals)
        for bp in self.mapped("blueprint_id").filtered(lambda b: b.state == "published"):
            bp._sync_generated_artifacts()
        return res

    def unlink(self):
        blueprints = self.mapped("blueprint_id")
        res = super().unlink()
        for bp in blueprints.filtered(lambda b: b.state == "published"):
            bp._sync_generated_artifacts()
        return res

    @api.constrains("kind", "alignment", "field_names", "field_ids")
    def _check_right_fields(self):
        """Compatibility hook — right is text justify, not tags-only."""
        return

    def _field_names(self):
        """Fields this line reads, in display order."""
        self.ensure_one()
        names = self._parse_field_names(self.field_names)
        if names:
            return names
        return [field.name for field in self._ordered_fields()]


class DashboardUserPref(models.Model):
    _name = "dashboard.user.pref"
    _description = "Dashboard User Preference"
    _rec_name = "blueprint_id"

    user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade", index=True,
        default=lambda self: self.env.user,
    )
    blueprint_id = fields.Many2one(
        "dashboard.blueprint", required=True, ondelete="cascade", index=True
    )
    prefs = fields.Json(default=dict)

    graph_model = fields.Char(related="blueprint_id.graph_model", readonly=True)
    graph_model_id = fields.Many2one(
        related="blueprint_id.graph_model_id", readonly=True
    )

    scope_ids = fields.Many2many(
        "dashboard.blueprint.scope",
        string="Data to include",
        help="Tick which sets of records the chart (and the main button) "
        "should show. At least one 'Adds these records' box should stay on.",
    )
    measure_field_id = fields.Many2one(
        "ir.model.fields",
        string="Measures",
        ondelete="cascade",
        help="Select the value that the graph should calculate and display "
        "(such as count or expected revenue). Leave empty to count records.",
    )
    measure_aggregator = fields.Selection(
        AGGREGATORS,
        string="Measured as",
        help="How the chosen measure is aggregated on the chart.",
    )
    # Source of truth: one ordered Group By tag list (v1 chrome).
    groupby_ids = fields.Many2many(
        "ir.model.fields",
        "dashboard_user_pref_groupby_rel",
        "pref_id",
        "field_id",
        string="Group By",
        help="Choose how the graph should group the data. Add several "
        "fields in order (for example Created on, then Stage) — the first "
        "is the top level, each next tag is a deeper split.",
    )
    ordered_groupby_ids = fields.Char(
        help="Machine-written selection order for Group By tags."
    )
    groupby_granularity = fields.Selection(
        GRANULARITIES,
        string="Per",
        help="Legacy; date buckets are chosen via virtual x_<date>_<period> "
        "Group By tags (v1-style).",
    )
    groupby_has_date = fields.Boolean(compute="_compute_groupby_has_date")
    groupby_allowed_field_ids = fields.Many2many(
        "ir.model.fields",
        compute="_compute_groupby_allowed_field_ids",
        help="Group By picker domain (stored non-dates + virtual period tags).",
    )

    # Compat mirrors of groupby_ids (first tag / rest). Written only from the
    # unified list — not a second source of truth. Kept for one upgrade cycle
    # so older readers / tests that still touch these columns keep working.
    groupby_field_id = fields.Many2one(
        "ir.model.fields",
        string="Group By (primary)",
        ondelete="cascade",
    )
    groupby_is_date = fields.Boolean(compute="_compute_groupby_is_date")
    groupby_extra_ids = fields.Many2many(
        "ir.model.fields",
        "dashboard_user_pref_groupby_extra_rel",
        "pref_id",
        "field_id",
        string="Then group by",
    )
    ordered_groupby_extra_ids = fields.Char()

    period_field_id = fields.Many2one(
        "ir.model.fields",
        string="Creation Date",
        ondelete="cascade",
        help="Which date on the record the month / year filters below apply "
        "to.",
    )
    period_mq_ids = fields.Many2many(
        "period.month.quarter",
        # Keep the original (implicit) relation table/columns so this
        # upgrade does not drop existing selections.
        "dashboard_user_pref_period_month_quarter_rel",
        "dashboard_user_pref_id",
        "period_month_quarter_id",
        string="Months",
        help="Limit the chart to these months or quarters.",
    )
    period_year_ids = fields.Many2many(
        "period.year",
        "dashboard_user_pref_period_year_rel",
        "dashboard_user_pref_id",
        "period_year_id",
        string="Years",
        help="Limit the chart to these years.",
    )
    # Dual date-row filters (H4): a second, optional date field — e.g.
    # Closed Date alongside the primary Creation Date row above. Both rows'
    # chosen ranges are combined by the same "Match" operator, exactly like
    # v1's single filter-operator across its two date fields.
    period_closed_field_id = fields.Many2one(
        "ir.model.fields",
        string="Closed Date",
        ondelete="cascade",
        help="An optional second date field to filter on, alongside "
        "Creation Date above (for example a closed / won date).",
    )
    period_closed_mq_ids = fields.Many2many(
        "period.month.quarter",
        "dashboard_user_pref_period_closed_mq_rel",
        "pref_id",
        "period_mq_id",
        string="Closed Months",
        help="Limit the chart to these months or quarters of the Closed "
        "Date.",
    )
    period_closed_year_ids = fields.Many2many(
        "period.year",
        "dashboard_user_pref_period_closed_year_rel",
        "pref_id",
        "period_year_id",
        string="Closed Years",
        help="Limit the chart to these years of the Closed Date.",
    )
    period_operator = fields.Selection(
        [("any", "any"), ("all", "all")],
        default="any",
        string="Match",
        help="Whether a record has to fall in any of the chosen periods "
        "(from either date row) or in all of them.",
    )
    custom_filter = fields.Char(
        default="[]",
        string="Custom Filter",
        help="Add custom rules to further narrow down the data based on "
        "your business needs.",
    )

    _dashboard_user_pref_uniq = models.Constraint(
        "UNIQUE(user_id, blueprint_id)",
        "One preference row per user and blueprint.",
    )

    _GROUPBY_LEGACY_KEYS = (
        "groupby_field_id",
        "groupby_extra_ids",
        "ordered_groupby_extra_ids",
    )

    @api.depends("groupby_ids", "ordered_groupby_ids")
    def _compute_groupby_is_date(self):
        for rec in self:
            ordered = rec._ordered_groupby_fields()
            primary = ordered[0] if ordered else False
            rec.groupby_is_date = bool(primary) and primary.ttype in DATE_TYPES

    @api.depends("groupby_ids", "ordered_groupby_ids")
    def _compute_groupby_has_date(self):
        for rec in self:
            ordered = rec._ordered_groupby_fields()
            rec.groupby_has_date = any(
                f.ttype in DATE_TYPES or f.is_date_period() for f in ordered
            )

    @api.depends("graph_model", "graph_model_id", "blueprint_id.graph_model")
    def _compute_groupby_allowed_field_ids(self):
        Fields = self.env["ir.model.fields"]
        for rec in self:
            model = (
                rec.graph_model
                or (rec.graph_model_id.model if rec.graph_model_id else False)
                or rec.blueprint_id.graph_model
            )
            rec.groupby_allowed_field_ids = Fields.dashboard_groupby_allowed_fields(
                model
            )

    @api.onchange("groupby_ids")
    def _onchange_groupby_ids(self):
        for rec in self:
            rec.ordered_groupby_ids = compute_many2many_order(
                rec.groupby_ids.ids, rec.ordered_groupby_ids
            )
            rec._apply_legacy_groupby_mirror_on_cache()

    def _parse_ordered_ids(self, order_char, records):
        """Preserve user tag order from a comma-separated id list."""
        self.ensure_one()
        try:
            ordered_ids = [
                int(v) for v in (order_char or "").split(",") if v.strip()
            ]
        except ValueError:
            ordered_ids = []
        by_id = {f.id: f for f in records}
        ordered = [by_id[i] for i in ordered_ids if i in by_id]
        ordered += [f for f in records if f.id not in ordered_ids]
        return ordered

    def _ordered_groupby_fields(self):
        """All Group By levels in unified tag order.

        Legacy primary/extra columns are not read here — call
        ``_ensure_unified_groupby()`` first if a row may predate the unified
        control.
        """
        self.ensure_one()
        if not self.groupby_ids:
            return self.env["ir.model.fields"]
        return self.env["ir.model.fields"].browse(
            [
                f.id
                for f in self._parse_ordered_ids(
                    self.ordered_groupby_ids, self.groupby_ids
                )
            ]
        )

    def _ordered_groupby_extra_fields(self):
        """Compat: extras mirror in tag order (after the primary)."""
        self.ensure_one()
        return self._ordered_groupby_fields()[1:]

    def _legacy_groupby_mirror_vals(self):
        """Vals that project the unified list onto primary + extras mirrors."""
        self.ensure_one()
        ordered = list(self._ordered_groupby_fields())
        extras = ordered[1:]
        primary = ordered[0] if ordered else False
        vals = {
            "groupby_field_id": primary.id if primary else False,
            "groupby_extra_ids": [(6, 0, [f.id for f in extras])],
            "ordered_groupby_extra_ids": ",".join(str(f.id) for f in extras) or False,
        }
        # Granularity lives in the virtual tag name now; clear the legacy Per.
        if not primary or (
            not primary.is_date_period() and primary.ttype not in DATE_TYPES
        ):
            vals["groupby_granularity"] = False
        return vals

    def _apply_legacy_groupby_mirror_on_cache(self):
        """Onchange helper: update legacy mirrors on the UI cache only."""
        for rec in self:
            ordered = rec._parse_ordered_ids(rec.ordered_groupby_ids, rec.groupby_ids)
            rec.groupby_field_id = ordered[0] if ordered else False
            primary = rec.groupby_field_id
            if primary and (
                not primary.is_date_period() and primary.ttype not in DATE_TYPES
            ):
                rec.groupby_granularity = False
            extras = ordered[1:]
            rec.groupby_extra_ids = [(6, 0, [f.id for f in extras])]
            rec.ordered_groupby_extra_ids = ",".join(str(f.id) for f in extras) or False

    def _mirror_legacy_groupby_from_unified(self):
        """Persist primary/extra mirrors from the unified tag list (one-way)."""
        for rec in self:
            super(DashboardUserPref, rec).write(rec._legacy_groupby_mirror_vals())

    def _unified_groupby_vals_from_legacy(self, force=False):
        """Vals to lift primary + extras into the unified tag list (heal only)."""
        self.ensure_one()
        if self.groupby_ids and not force:
            return {}
        primary = self.groupby_field_id
        extras = self.env["ir.model.fields"].browse(
            [
                f.id
                for f in self._parse_ordered_ids(
                    self.ordered_groupby_extra_ids, self.groupby_extra_ids
                )
            ]
        )
        ordered = ([primary] + list(extras)) if primary else list(extras)
        if not ordered:
            return {}
        return {
            "groupby_ids": [(6, 0, [f.id for f in ordered])],
            "ordered_groupby_ids": ",".join(str(f.id) for f in ordered),
        }

    def _ensure_unified_groupby(self):
        """Heal rows that still only have legacy primary/extra filled."""
        for rec in self:
            if rec.groupby_ids:
                continue
            if not (rec.groupby_field_id or rec.groupby_extra_ids):
                continue
            vals = rec._unified_groupby_vals_from_legacy(force=True)
            if vals:
                super(DashboardUserPref, rec).write(vals)
                super(DashboardUserPref, rec).write(rec._legacy_groupby_mirror_vals())

    @api.model
    def _heal_unified_groupby_prefs(self):
        """Batch-heal prefs on registry load (idempotent)."""
        candidates = self.search(
            [
                "|",
                ("groupby_ids", "!=", False),
                "|",
                ("groupby_field_id", "!=", False),
                ("groupby_extra_ids", "!=", False),
            ]
        )
        if candidates:
            candidates._ensure_unified_groupby()
            candidates._normalize_unified_groupby_period_tags()

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            has_unified = bool(vals.get("groupby_ids")) or bool(
                vals.get("ordered_groupby_ids")
            )
            has_legacy = any(vals.get(k) for k in self._GROUPBY_LEGACY_KEYS)
            # New rows: if only legacy columns were supplied, lift them first.
            if has_legacy and not has_unified:
                primary = vals.get("groupby_field_id")
                extras_cmd = vals.get("groupby_extra_ids") or []
                extra_ids = []
                for cmd in extras_cmd:
                    if cmd and cmd[0] == 6:
                        extra_ids = list(cmd[2] or [])
                order = vals.get("ordered_groupby_extra_ids") or ",".join(
                    str(i) for i in extra_ids
                )
                ordered_ids = []
                if primary:
                    ordered_ids.append(int(primary))
                try:
                    for part in (order or "").split(","):
                        if part.strip():
                            iid = int(part)
                            if iid not in ordered_ids:
                                ordered_ids.append(iid)
                except ValueError:
                    ordered_ids = ([int(primary)] if primary else []) + extra_ids
                for iid in extra_ids:
                    if iid not in ordered_ids:
                        ordered_ids.append(iid)
                vals["groupby_ids"] = [(6, 0, ordered_ids)]
                vals["ordered_groupby_ids"] = (
                    ",".join(str(i) for i in ordered_ids) or False
                )
            prepared.append(vals)
        records = super().create(prepared)
        records._mirror_legacy_groupby_from_unified()
        return records

    def write(self, vals):
        """Unified Group By is the write path; legacy columns are mirrors.

        Legacy-only writes (old tests / RPC) are accepted once: applied, then
        lifted into ``groupby_ids`` and re-mirrored so storage stays coherent.
        """
        vals = dict(vals)
        unified_touched = "groupby_ids" in vals or "ordered_groupby_ids" in vals
        legacy_touched = any(k in vals for k in self._GROUPBY_LEGACY_KEYS)

        if legacy_touched and not unified_touched:
            res = super().write(vals)
            for rec in self:
                unified = rec._unified_groupby_vals_from_legacy(force=True)
                if unified:
                    super(DashboardUserPref, rec).write(unified)
                super(DashboardUserPref, rec).write(rec._legacy_groupby_mirror_vals())
            return res

        res = super().write(vals)
        if unified_touched:
            self._mirror_legacy_groupby_from_unified()
        return res

    # ------------------------------------------------------------------
    # Reading preferences back
    # ------------------------------------------------------------------

    def _groupby_all_specs(self):
        """Ordered read_group specs for every Group By tag.

        Date buckets come from virtual ``x_<date>_<period>`` tags (v1-style).
        Raw date fields still fall back to ``:month`` for one upgrade cycle.
        """
        self.ensure_one()
        self._ensure_unified_groupby()
        fields_ordered = self._ordered_groupby_fields()
        if not fields_ordered:
            bp = self.blueprint_id
            bp_specs = bp._groupby_all_specs()
            if bp_specs:
                return bp_specs
            primary = bp.graph_groupby or None
            extras = bp._groupby_extra_specs()
            if not primary:
                return extras
            return [primary] + extras
        Blueprint = self.env["dashboard.blueprint"]
        hint = self.groupby_granularity or "month"
        return Blueprint._groupby_specs_from_fields(
            fields_ordered, period_hint=hint
        )

    def _normalize_unified_groupby_period_tags(self):
        """Swap raw date Group By tags for virtual period tags on prefs."""
        Blueprint = self.env["dashboard.blueprint"]
        for rec in self:
            model = (
                rec.graph_model
                or (rec.graph_model_id.model if rec.graph_model_id else False)
                or rec.blueprint_id.graph_model
            )
            if not model:
                continue
            ordered = list(rec._ordered_groupby_fields())
            if not ordered:
                continue
            hint = rec.groupby_granularity or rec.blueprint_id._primary_period_hint()
            normalized = Blueprint._normalize_groupby_fields_to_period_tags_for_model(
                model, ordered, period_hint=hint or "month"
            )
            if [f.id for f in normalized] == [f.id for f in ordered]:
                continue
            super(DashboardUserPref, rec).write(
                {
                    "groupby_ids": [(6, 0, [f.id for f in normalized])],
                    "ordered_groupby_ids": ",".join(str(f.id) for f in normalized),
                }
            )
            super(DashboardUserPref, rec).write(rec._legacy_groupby_mirror_vals())

    def _groupby_spec(self):
        """Primary group-by from the pref's unified list, or None if unset."""
        self.ensure_one()
        self._ensure_unified_groupby()
        if not self._ordered_groupby_fields():
            return None
        return self._groupby_all_specs()[0]

    def _groupby_extra_specs(self):
        """Extra group-by levels (after the primary one), in order."""
        self.ensure_one()
        self._ensure_unified_groupby()
        if not self._ordered_groupby_fields():
            return self.blueprint_id._groupby_extra_specs()
        return self._groupby_all_specs()[1:]

    def _measure_spec(self):
        self.ensure_one()
        if not self.measure_field_id:
            return None
        return "%s:%s" % (
            self.measure_field_id.name,
            self.measure_aggregator or "sum",
        )

    def _period_ranges(self, field, mq_ids, year_ids):
        """One flat AND domain per selected range for one date-filter row.

        ``_date_range_to_domain`` returns ``[[start_leaf], [end_leaf]]`` (two
        one-leaf sub-domains, meant to be AND-ed by its caller) rather than a
        ready-to-use domain, so each range is AND-ed here before it is
        pooled with the other ranges/rows and OR-ed or AND-ed as a whole.
        """
        self.ensure_one()
        if not field or not year_ids:
            return []
        tz_offset = self.env.context.get("webclient_tz_offset", 0)
        ranges = []
        months = mq_ids.mapped("name")
        for year_key in year_ids.mapped("name"):
            year = get_period_year().get(year_key)
            if year is None:
                continue
            for start, end in _get_period_dates(year, months):
                leaves = _date_range_to_domain(field.name, start, end, tz_offset)
                ranges.append(list(fields.Domain.AND(leaves)))
        return ranges

    def _period_domain(self):
        """Date ranges for the chosen months / quarters and years.

        Dual date-row filters (H4): ranges from the primary row (e.g.
        Creation Date) and the optional second row (e.g. Closed Date) are
        pooled and combined by the single ``period_operator`` — exactly
        like v1, where one filter-operator spans both date fields.
        """
        self.ensure_one()
        ranges = self._period_ranges(
            self.period_field_id, self.period_mq_ids, self.period_year_ids
        )
        ranges += self._period_ranges(
            self.period_closed_field_id,
            self.period_closed_mq_ids,
            self.period_closed_year_ids,
        )
        if not ranges:
            return []
        combine = fields.Domain.AND if self.period_operator == "all" else fields.Domain.OR
        return list(combine(ranges))

    def _scope_domains(self):
        """Included and restricting domains from the ticked boxes."""
        self.ensure_one()
        available = self.blueprint_id.scope_ids
        chosen = self.scope_ids & available
        included = [s._scope_domain() for s in chosen if s.mode == "include"]
        restricting = [s._scope_domain() for s in chosen if s.mode == "restrict"]
        parts = []
        # No box ticked in a group of "adds" boxes means no data, which is
        # what the hand-written dashboards show too.
        if any(s.mode == "include" for s in available):
            parts.append(list(fields.Domain.OR(included)) if included else [(0, "=", 1)])
        parts.extend(restricting)
        return parts

    def _pref_domain(self):
        self.ensure_one()
        parts = self._scope_domains()
        parts.append(self._period_domain())
        try:
            parts.append(list(safe_eval(self.custom_filter or "[]")))
        except Exception:
            _logger.warning(
                "Dashboard engine: unreadable custom filter on preference %s",
                self.id,
                exc_info=True,
            )
        parts = [part for part in parts if part]
        return list(fields.Domain.AND(parts)) if parts else []
