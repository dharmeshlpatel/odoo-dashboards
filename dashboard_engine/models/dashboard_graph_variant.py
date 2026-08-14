# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Graph Model picker bundle (Phase 3): model + primary button together."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools.many2many_utils import compute_many2many_order
from ..tools.relation_path import (
    validate_path as validate_relation_path,
    validate_path_chain as validate_relation_path_chain,
)

VARIANT_AGGREGATORS = [
    ("sum", "Total"),
    ("avg", "Average"),
    ("max", "Maximum"),
    ("min", "Minimum"),
]


class DashboardBlueprintGraphVariant(models.Model):
    """One chart-model option for the end-user Configuration picker.

    A model is only offered when it has a direct many2one back to Host and
    this variant row exists (label + action + context). Switching swaps the
    whole bundle — never leaves the primary button on the old model.
    """

    _name = "dashboard.blueprint.graph.variant"
    _description = "Dashboard Graph Model Variant"
    _inherit = ["dashboard.mirror.mixin"]
    _order = "sequence, id"
    _rec_name = "primary_button_label"

    blueprint_id = fields.Many2one(
        "dashboard.blueprint", required=True, ondelete="cascade", index=True
    )
    host_model_name = fields.Char(
        related="blueprint_id.host_model_name",
        string="Host Model",
    )
    sequence = fields.Integer(default=10)
    graph_model = fields.Char(required=True, index=True)
    graph_model_id = fields.Many2one(
        "ir.model",
        string="Chart Model",
        compute="_compute_graph_model_id",
        inverse="_inverse_graph_model_id",
        store=True,
        readonly=False,
        ondelete="cascade",
    )
    graph_data_field = fields.Char(
        help="Many2one on the chart model pointing at the host (e.g. partner_id).",
    )
    primary_button_label = fields.Char(required=True, translate=True)
    primary_action_xmlid = fields.Char(required=True)
    primary_action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Primary Action",
        compute="_compute_primary_action_id",
        inverse="_inverse_primary_action_id",
        readonly=False,
        domain=(
            "['|', ('res_model', '=', graph_model), ('res_model', '=', False)]"
        ),
    )
    primary_action_context = fields.Char(default="{}")
    primary_action_domain = fields.Char(
        string="Extra Domain",
        default="[]",
        help="Extra domain merged into this option's primary action. "
        "Supports {{id}} for the host record id.",
    )
    primary_label_alt_scope_id = fields.Many2one(
        "dashboard.blueprint.scope",
        string="When this filter is off",
        ondelete="cascade",
        domain="[('blueprint_id', '=', blueprint_id)]",
        help="Optional settings filter. While it is ticked, the button shows "
        "Button Label; while it is off, Alternate Label is shown.",
    )
    primary_label_alt = fields.Char(
        translate=True,
        string="Alternate Label",
        help="Button label when the selected settings filter is off.",
    )
    alternate_action_ids = fields.One2many(
        "dashboard.blueprint.action.variant",
        "graph_variant_id",
        string="Alternate Actions",
        copy=True,
        help="Opens a different screen when a listed app is installed. "
        "First match wins; otherwise this option's primary action is used.",
    )
    is_default = fields.Boolean(
        string="Default",
        default=False,
        help="Blueprint default chart model when the user has not picked one in the gear.",
    )
    is_available = fields.Boolean(
        compute="_compute_is_available",
        help="True when the model is installed and the link + action are usable.",
    )
    # Optional defaults for this chart model (empty = inherit blueprint defaults).
    graph_groupby_allowed_field_ids = fields.Many2many(
        "ir.model.fields",
        compute="_compute_graph_groupby_allowed_field_ids",
    )
    default_groupby_ids = fields.Many2many(
        "ir.model.fields",
        "dashboard_graph_variant_groupby_rel",
        "variant_id",
        "field_id",
        string="Default Group By",
        domain="[('id', 'in', graph_groupby_allowed_field_ids)]",
    )
    default_ordered_groupby_ids = fields.Char(
        string="Default Group By Order",
        help="Comma-separated ir.model.fields ids preserving tag order.",
    )
    default_measure_field_id = fields.Many2one(
        "ir.model.fields",
        string="Default Measure",
        ondelete="set null",
        domain=(
            "[('model_id', '=', graph_model_id), "
            "('ttype', 'in', ['integer', 'float', 'monetary']), "
            "('store', '=', True)]"
        ),
    )
    default_measure_aggregator = fields.Selection(
        VARIANT_AGGREGATORS,
        string="Default Measured As",
    )
    default_scope_ids = fields.Many2many(
        "dashboard.blueprint.scope",
        "dashboard_graph_variant_scope_rel",
        "variant_id",
        "scope_id",
        string="Default Data to Include",
        domain="[('id', 'in', applicable_include_scope_ids)]",
        help="Include scopes whose domain matches this chart model. "
        "Ticked ones start on in the live gear for this option.",
    )
    # Same Include boxes as Studio: edit name/domain here; shared on the blueprint.
    include_scope_ids = fields.One2many(
        related="blueprint_id.scope_ids",
        readonly=False,
        string="Data to Include",
    )
    scope_warning = fields.Char(
        string="Scope Warning",
        translate=True,
        help="Message shown in the live settings popup when all 'Include' "
        "scopes for this chart model are unticked. Leave empty for no warning.",
    )
    applicable_include_scope_ids = fields.Many2many(
        "dashboard.blueprint.scope",
        compute="_compute_applicable_include_scope_ids",
        help="Include scopes whose domain fields exist on this chart model.",
    )
    date_filter_ids = fields.One2many(
        "dashboard.blueprint.graph.variant.date.filter",
        "variant_id",
        string="Date Filters",
        copy=True,
        help="Date fields offered in the live gear for this chart model "
        "(e.g. Creation Date, Closed Date). Each option has its own list "
        "since date field names are not portable across models.",
    )
    graph_domain = fields.Char(
        string="Custom Filter",
        default="[]",
        help="Optional domain on this chart model (Python list). "
        "Not shared across Chart Model Options — field names differ by model.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            siblings = rec.blueprint_id.graph_variant_ids
            if rec.is_default or len(siblings) == 1:
                rec.blueprint_id._studio_mark_default_graph_variant(rec)
            elif not siblings.filtered("is_default"):
                first = siblings.sorted("sequence")[:1]
                if first:
                    rec.blueprint_id._studio_mark_default_graph_variant(first)
        return records

    def write(self, vals):
        vals = dict(vals)
        res = super().write(vals)
        if "graph_model" in vals or "graph_model_id" in vals:
            self._clear_stale_default_fields()
        if "default_groupby_ids" in vals and "default_ordered_groupby_ids" not in vals:
            for rec in self:
                rec.default_ordered_groupby_ids = compute_many2many_order(
                    rec.default_groupby_ids.ids,
                    rec.default_ordered_groupby_ids,
                )
        if self.env.context.get("skip_graph_variant_default"):
            return res
        if vals.get("is_default"):
            for rec in self:
                rec.blueprint_id._studio_mark_default_graph_variant(rec)
        elif any(
            key in vals
            for key in (
                "graph_model",
                "graph_data_field",
                "primary_button_label",
                "primary_action_xmlid",
                "primary_action_context",
                "primary_action_domain",
                "primary_label_alt_scope_id",
                "primary_label_alt",
                "default_groupby_ids",
                "default_ordered_groupby_ids",
                "default_measure_field_id",
                "default_measure_aggregator",
                "default_scope_ids",
                "scope_warning",
                "graph_domain",
            )
        ):
            for bp in self.filtered("is_default").mapped("blueprint_id"):
                bp._sync_blueprint_from_default_variant()
        return res

    def unlink(self):
        blueprints = self.mapped("blueprint_id")
        was_default = {bp.id: bp.graph_variant_ids.filtered("is_default") for bp in blueprints}
        res = super().unlink()
        for bp in blueprints.exists():
            if not bp.graph_variant_ids:
                continue
            if not bp.graph_variant_ids.filtered("is_default"):
                # Prefer the row that was default, else first by sequence.
                previous = was_default.get(bp.id)
                survivor = (previous & bp.graph_variant_ids)[:1] or bp.graph_variant_ids.sorted(
                    "sequence"
                )[:1]
                if survivor:
                    bp._studio_mark_default_graph_variant(survivor)
        return res

    @api.depends("graph_model")
    def _compute_graph_model_id(self):
        Model = self.env["ir.model"].sudo()
        for rec in self:
            rec.graph_model_id = (
                Model.search([("model", "=", rec.graph_model)], limit=1)
                if rec.graph_model
                else False
            )

    def _inverse_graph_model_id(self):
        for rec in self:
            rec.graph_model = rec.graph_model_id.model or False

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

    @api.depends(
        "graph_model",
        "blueprint_id.scope_ids",
        "blueprint_id.scope_ids.mode",
        "blueprint_id.scope_ids.domain",
    )
    def _compute_applicable_include_scope_ids(self):
        for rec in self:
            rec.applicable_include_scope_ids = rec.blueprint_id.scope_ids.filtered(
                lambda s, m=rec.graph_model: s.mode == "include"
                and s._domain_applies_to_model(m)
            )

    @api.onchange("default_groupby_ids")
    def _onchange_default_groupby_ids(self):
        for rec in self:
            rec.default_ordered_groupby_ids = compute_many2many_order(
                rec.default_groupby_ids.ids,
                rec.default_ordered_groupby_ids,
            )

    def _clear_stale_default_fields(self):
        """Drop Group By / Measure / Include defaults that do not fit the model."""
        for rec in self:
            model = rec.graph_model
            if not model or model not in self.env:
                continue
            Model = self.env[model]
            vals = {}
            if (
                rec.default_measure_field_id
                and rec.default_measure_field_id.name not in Model._fields
            ):
                vals["default_measure_field_id"] = False
                vals["default_measure_aggregator"] = False
            stale_gb = rec.default_groupby_ids.filtered(lambda f: f.model != model)
            if stale_gb:
                keep = rec.default_groupby_ids - stale_gb
                vals["default_groupby_ids"] = [(6, 0, keep.ids)]
                vals["default_ordered_groupby_ids"] = (
                    ",".join(str(i) for i in keep.ids) or False
                )
            bad_scopes = rec.default_scope_ids.filtered(
                lambda s: not s._domain_applies_to_model(model)
            )
            if bad_scopes:
                keep_scopes = rec.default_scope_ids - bad_scopes
                vals["default_scope_ids"] = [(6, 0, keep_scopes.ids)]
            if vals:
                rec.with_context(skip_graph_variant_default=True).write(vals)
            stale_dates = rec.date_filter_ids.filtered(
                lambda d: d.field_name and d.field_name not in Model._fields
            )
            if stale_dates:
                stale_dates.unlink()

    def _ordered_default_groupby_fields(self):
        """Default Group By tags in configured order."""
        self.ensure_one()
        if not self.default_groupby_ids:
            return self.env["ir.model.fields"]
        return self.env["ir.model.fields"].browse(
            [
                f.id
                for f in self.blueprint_id._parse_ordered_field_ids(
                    self.default_ordered_groupby_ids, self.default_groupby_ids
                )
            ]
        )

    def _suggested_option_defaults_vals(self):
        """Pack-style Group By / Measure when an option row is still empty.

        Used once by ``_ensure_option_graph_defaults`` so the gear can reseed
        when the user switches Chart Model (e.g. Sales Orders on CRM Customers).
        """
        self.ensure_one()
        specs = {
            "sale.order": {
                "groupby_names": ["x_date_order_month"],
                "measure_name": "amount_untaxed",
                "aggregator": "sum",
            },
            "sale.report": {
                "groupby_names": ["x_date_month"],
                "measure_name": "price_subtotal",
                "aggregator": "sum",
            },
        }
        spec = specs.get(self.graph_model)
        if not spec or self.graph_model not in self.env:
            return {}
        Fields = self.env["ir.model.fields"]
        Fields.ensure_date_period_fields(self.graph_model)
        vals = {}
        if not self.default_groupby_ids and spec.get("groupby_names"):
            ordered = Fields.browse()
            for name in spec["groupby_names"]:
                field = Fields.search(
                    [("model", "=", self.graph_model), ("name", "=", name)],
                    limit=1,
                )
                if field:
                    ordered |= field
            if ordered:
                vals["default_groupby_ids"] = [(6, 0, ordered.ids)]
                vals["default_ordered_groupby_ids"] = ",".join(
                    str(f.id) for f in ordered
                )
        if not self.default_measure_field_id and spec.get("measure_name"):
            measure = Fields.search(
                [
                    ("model", "=", self.graph_model),
                    ("name", "=", spec["measure_name"]),
                    ("store", "=", True),
                ],
                limit=1,
            )
            if measure:
                vals["default_measure_field_id"] = measure.id
                vals["default_measure_aggregator"] = (
                    spec.get("aggregator") or "sum"
                )
        return vals

    def _pref_defaults_for_gear(self):
        """Group By / Measure / Include to apply when this option is selected.

        Uses the option row first; if Group By / Measure are still empty, uses
        pack-style suggestions (same rules as ``_ensure_option_graph_defaults``)
        without writing — safe for gear onchange.
        """
        self.ensure_one()
        ordered = list(self._ordered_default_groupby_fields())
        measure = self.default_measure_field_id
        agg = (self.default_measure_aggregator or "sum") if measure else False
        # Empty option Include = no include ticks (options-only UX).
        include = self.default_scope_ids
        if not ordered or not measure:
            suggested = self._suggested_option_defaults_vals()
            if not ordered and suggested.get("default_groupby_ids"):
                ids = suggested["default_groupby_ids"][0][2]
                ordered = list(self.env["ir.model.fields"].browse(ids))
            if not measure and suggested.get("default_measure_field_id"):
                measure = self.env["ir.model.fields"].browse(
                    suggested["default_measure_field_id"]
                )
                agg = suggested.get("default_measure_aggregator") or "sum"
        return ordered, measure, agg, include

    def _groupby_all_specs(self):
        """Ordered read_group specs from this variant's default Group By list."""
        self.ensure_one()
        return self.blueprint_id._groupby_specs_from_fields(
            self._ordered_default_groupby_fields(),
            period_hint="month",
        )

    def _measure_spec(self):
        self.ensure_one()
        if not self.default_measure_field_id:
            return None
        return "%s:%s" % (
            self.default_measure_field_id.name,
            self.default_measure_aggregator or "sum",
        )

    @api.depends("primary_action_xmlid")
    def _compute_primary_action_id(self):
        for rec in self:
            rec.primary_action_id = rec._mirror_record(
                "ir.actions.act_window", rec.primary_action_xmlid
            )

    def _inverse_primary_action_id(self):
        for rec in self:
            rec.primary_action_xmlid = rec._mirror_xmlid(rec.primary_action_id)

    @api.depends(
        "graph_model",
        "graph_data_field",
        "primary_action_xmlid",
        "blueprint_id.graph_data_field",
        "blueprint_id.host_model_name",
    )
    def _compute_is_available(self):
        for rec in self:
            rec.is_available = rec._is_valid_candidate()

    def _is_valid_candidate(self):
        self.ensure_one()
        bp = self.blueprint_id
        if not self.graph_model or self.graph_model not in self.env:
            return False
        if not self.primary_action_xmlid:
            return False
        if not bp._action_xmlid_exists(self.primary_action_xmlid):
            return False
        link = self.graph_data_field or bp.graph_data_field
        if not link or not bp.host_model_name:
            return False
        try:
            validate_relation_path(
                self.env, self.graph_model, link, bp.host_model_name
            )
        except ValidationError:
            return False
        return True

    def _default_link_to_host(self, graph_model=None):
        """First many2one on chart model that points at the host card."""
        self.ensure_one()
        model_name = graph_model or self.graph_model
        host = self.blueprint_id.host_model_name
        if not model_name or model_name not in self.env or not host:
            return False
        Model = self.env[model_name]
        for name, field in Model._fields.items():
            if (
                field.type == "many2one"
                and field.comodel_name == host
                and not name.startswith("_")
            ):
                return name
        return False

    @api.depends("primary_button_label", "graph_model")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                rec.primary_button_label or rec.graph_model or "Chart Model"
            )

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """List usable Chart Model Options for the gear picker.

        Hide unfinished options (missing link/action). If the typed label only
        matches an unusable row, still return other valid options for the same
        domain — otherwise the dropdown shows only an empty "Chart Model" box.
        """
        rows = super().name_search(
            name=name, domain=domain, operator=operator, limit=None
        )
        available = self._name_search_available_rows(rows, limit)
        if available or not name:
            return available
        # Typed label matched only invalid options (or nothing usable) — show
        # every valid option in the caller's domain so the picker is never blank.
        fallback = super().name_search(
            name="", domain=domain, operator="ilike", limit=None
        )
        return self._name_search_available_rows(fallback, limit)

    @api.model
    def _name_search_available_rows(self, rows, limit=100):
        available = []
        for variant_id, label in rows:
            variant = self.browse(variant_id)
            if variant._is_valid_candidate():
                available.append((variant_id, label))
            if limit and len(available) >= limit:
                break
        return available


class DashboardBlueprintGraphPicker(models.Model):
    _inherit = "dashboard.blueprint"

    graph_variant_ids = fields.One2many(
        "dashboard.blueprint.graph.variant",
        "blueprint_id",
        string="Graph Model Variants",
    )
    pooled_default_graph_variant_id = fields.Many2one(
        "dashboard.blueprint.graph.variant",
        string="Default Shared Chart Option",
        ondelete="set null",
        copy=False,
        help="Studio Default for compose hubs (e.g. Customer 360) when the "
        "chosen Chart Model Option comes from Share Links. Does not change "
        "the owner pack's own Default. Empty = first valid pooled option.",
    )
    effective_graph_variant_ids = fields.Many2many(
        "dashboard.blueprint.graph.variant",
        compute="_compute_effective_graph_variant_ids",
        string="All Chart Model Options",
        help="Local options plus Share Links peers (same pool as Studio).",
    )
    shared_graph_variant_ids = fields.Many2many(
        "dashboard.blueprint.graph.variant",
        compute="_compute_effective_graph_variant_ids",
        string="Shared Chart Model Options",
        help="Read-only Chart Model Options from Share Links peers.",
    )
    has_shared_graph_variants = fields.Boolean(
        compute="_compute_effective_graph_variant_ids",
    )
    has_effective_graph_variants = fields.Boolean(
        compute="_compute_effective_graph_variant_ids",
    )
    default_chart_option_id = fields.Many2one(
        "dashboard.blueprint.graph.variant",
        string="Default Chart Model Option",
        compute="_compute_default_chart_option_id",
        inverse="_inverse_default_chart_option_id",
        domain="[('id', 'in', effective_graph_variant_ids)]",
        help="Chart new users see (same as Studio Default radio). Can point "
        "at a Shared option on 360 hubs without changing the owner pack.",
    )
    has_graph_variants = fields.Boolean(
        string="Has Chart Model Options",
        compute="_compute_has_graph_variants",
        help="True when this blueprint owns at least one Chart Model Option. "
        "Used by Advanced form modifiers (One2many length is unreliable in "
        "invisible= expressions).",
    )

    @api.depends("graph_variant_ids")
    def _compute_has_graph_variants(self):
        for bp in self:
            bp.has_graph_variants = bool(bp.graph_variant_ids)

    @api.depends(
        "graph_variant_ids",
        "graph_variant_ids.sequence",
        "graph_variant_ids.graph_model",
        "share_link_ids",
        "share_link_ids.graph_variant_ids",
        "share_link_ids.graph_variant_ids.sequence",
        "share_link_ids.graph_variant_ids.graph_model",
    )
    def _compute_effective_graph_variant_ids(self):
        for bp in self:
            eff = bp._effective_graph_variants()
            bp.effective_graph_variant_ids = eff
            shared = eff.filtered(lambda v, b=bp: v.blueprint_id != b)
            bp.shared_graph_variant_ids = shared
            bp.has_shared_graph_variants = bool(shared)
            bp.has_effective_graph_variants = bool(eff)

    @api.depends(
        "graph_variant_ids",
        "graph_variant_ids.is_default",
        "graph_variant_ids.sequence",
        "pooled_default_graph_variant_id",
        "share_link_ids",
        "share_link_ids.graph_variant_ids",
        "share_link_ids.graph_variant_ids.is_default",
    )
    def _compute_default_chart_option_id(self):
        for bp in self:
            bp.default_chart_option_id = bp._default_graph_variant()

    def _inverse_default_chart_option_id(self):
        for bp in self:
            variant = bp.default_chart_option_id
            if not variant:
                continue
            if variant.blueprint_id == bp:
                bp._studio_mark_default_graph_variant(variant)
            else:
                bp._studio_mark_pooled_default_graph_variant(variant)

    @api.model
    def _graph_variant_dedupe_key(self, variant):
        """Stable identity for shared Chart Model Option collapsing.

        Same chart model across Share Links collapses; the current blueprint
        wins (same order as ``_effective_slots``). ``None`` = never collapse.
        """
        model = (variant.graph_model or "").strip()
        if not model:
            return None
        return ("model", model)

    def _share_graph_peer_sort_key(self, blueprint):
        """Pack dashboards before *360 hubs when collapsing shared chart options.

        Customer 360 should compose CRM/Sales options, not become their owner
        when the same ``graph_model`` exists on both.
        """
        key = (blueprint.key or "").strip().lower()
        is_hub = key.endswith("_360") or key.endswith("360")
        return (1 if is_hub else 0, blueprint.sequence, blueprint.id)

    def _effective_graph_variants(self):
        """Chart Model Options from the share component, deduped.

        Order: this blueprint first (by sequence), then other linked blueprints
        (packs before *360 hubs), by ``(sequence, id)``. First wins on
        ``_graph_variant_dedupe_key``. Studio edit surfaces stay on
        ``graph_variant_ids`` (local only).
        """
        self.ensure_one()
        if self.env.context.get("dashboard_studio_local_only"):
            return self.graph_variant_ids.sorted("sequence")
        component = self._share_pool_members()
        peers = (component - self).sorted(self._share_graph_peer_sort_key)
        ordered_ids = []
        seen_keys = set()
        for blueprint in [self] + list(peers):
            for variant in blueprint.graph_variant_ids.sorted("sequence"):
                key = self._graph_variant_dedupe_key(variant)
                if key is not None:
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                ordered_ids.append(variant.id)
        return self.env["dashboard.blueprint.graph.variant"].browse(ordered_ids)

    def _graph_model_candidates(self):
        self.ensure_one()
        rows = []
        default = self._default_graph_variant()
        default_id = default.id if default else False
        for variant in self._effective_graph_variants():
            if variant._is_valid_candidate():
                rows.append(
                    {
                        "id": variant.id,
                        "graph_model": variant.graph_model,
                        "label": variant.primary_button_label,
                        "action_xmlid": variant.primary_action_xmlid,
                        "is_default": bool(default_id and variant.id == default_id),
                        "is_local": variant.blueprint_id == self,
                        "source_blueprint_id": variant.blueprint_id.id,
                        "source_blueprint_name": (
                            variant.blueprint_id.display_name
                            or variant.blueprint_id.name
                            or ""
                        ),
                    }
                )
        return rows

    def _default_graph_variant(self):
        """Local Default, else hub shared Default, else first valid pooled option.

        Local ``is_default`` stays on this blueprint. Compose hubs (e.g.
        Customer 360) can point ``pooled_default_graph_variant_id`` at a Share
        Links peer without changing that pack's own Default.
        """
        self.ensure_one()
        marked = self.graph_variant_ids.filtered("is_default").sorted("sequence")
        for variant in marked:
            if variant._is_valid_candidate():
                return variant
        pool = self._effective_graph_variants()
        pooled = self.pooled_default_graph_variant_id
        if (
            pooled
            and pooled in pool
            and pooled.blueprint_id != self
            and pooled._is_valid_candidate()
        ):
            return pooled
        for variant in self.graph_variant_ids.sorted("sequence"):
            if variant._is_valid_candidate():
                return variant
        for variant in pool:
            if variant._is_valid_candidate():
                return variant
        return marked[:1] or pooled[:1]

    def _studio_mark_default_graph_variant(self, variant):
        """Exclusive local default + mirror chart/primary fields onto the blueprint."""
        self.ensure_one()
        if not variant or variant.blueprint_id != self:
            return
        if self.pooled_default_graph_variant_id:
            self.with_context(skip_graph_variant_default=True).write(
                {"pooled_default_graph_variant_id": False}
            )
        others = (self.graph_variant_ids - variant).filtered("is_default")
        if others:
            others.with_context(skip_graph_variant_default=True).write(
                {"is_default": False}
            )
        if not variant.is_default:
            variant.with_context(skip_graph_variant_default=True).write(
                {"is_default": True}
            )
        self._sync_blueprint_from_default_variant()

    def _studio_mark_pooled_default_graph_variant(self, variant):
        """Hub-only Default pointing at a Share Links peer option."""
        self.ensure_one()
        if not variant or variant.blueprint_id == self:
            return
        pool = self._effective_graph_variants()
        if variant not in pool:
            raise UserError(
                _("That chart model option is not available via Share Links.")
            )
        if not variant._is_valid_candidate():
            raise UserError(_("That chart model option is incomplete."))
        # Clear local defaults so the shared pick is what new users see.
        locals_default = self.graph_variant_ids.filtered("is_default")
        if locals_default:
            locals_default.with_context(skip_graph_variant_default=True).write(
                {"is_default": False}
            )
        if self.pooled_default_graph_variant_id != variant:
            self.with_context(skip_graph_variant_default=True).write(
                {"pooled_default_graph_variant_id": variant.id}
            )

    def _sync_blueprint_from_default_variant(self):
        """Keep blueprint chart fields = Default Chart Model Option."""
        self.ensure_one()
        if self.env.context.get("skip_graph_variant_sync"):
            return
        variant = self.graph_variant_ids.filtered("is_default")[:1]
        if not variant:
            return
        vals = {}
        if variant.graph_model and variant.graph_model != (self.graph_model or ""):
            vals["graph_model"] = variant.graph_model
        link = variant.graph_data_field or False
        # Only mirror a finished link (ends on host). Incomplete hop chains stay
        # on the option row until the builder lands on the card model.
        link_ready = False
        if link and variant.graph_model and self.host_model_name:
            try:
                validate_relation_path(
                    self.env, variant.graph_model, link, self.host_model_name
                )
                link_ready = True
            except ValidationError:
                link_ready = False
        if link_ready and (link or False) != (self.graph_data_field or False):
            vals["graph_data_field"] = link
        elif not link and (self.graph_data_field or False):
            # Explicit clear on the Default option
            vals["graph_data_field"] = False
        if variant.primary_button_label and variant.primary_button_label != (
            self.primary_button_label or ""
        ):
            vals["primary_button_label"] = variant.primary_button_label
        if variant.primary_action_xmlid and variant.primary_action_xmlid != (
            self.primary_action_xmlid or ""
        ):
            vals["primary_action_xmlid"] = variant.primary_action_xmlid
        ctx = variant.primary_action_context or "{}"
        if ctx != (self.primary_action_context or "{}"):
            vals["primary_action_context"] = ctx
        domain = (variant.primary_action_domain or "[]").strip() or "[]"
        bp_domain = (self.primary_action_domain or "[]").strip() or "[]"
        if domain != bp_domain:
            vals["primary_action_domain"] = domain
        alt_scope = variant.primary_label_alt_scope_id
        if (alt_scope.id if alt_scope else False) != (
            self.primary_label_alt_scope_id.id
            if self.primary_label_alt_scope_id
            else False
        ):
            vals["primary_label_alt_scope_id"] = alt_scope.id if alt_scope else False
        alt_label = (variant.primary_label_alt or "").strip() or False
        bp_alt = (self.primary_label_alt or "").strip() or False
        if alt_label != bp_alt:
            vals["primary_label_alt"] = alt_label
        # Group By / Measure live on the option; mirror onto blueprint for packs
        # and code paths that still read blueprint fields.
        ordered = list(variant._ordered_default_groupby_fields())
        bp_ordered = list(self._ordered_graph_groupby_fields())
        if [f.id for f in ordered] != [f.id for f in bp_ordered]:
            vals["graph_groupby_ids"] = [(6, 0, [f.id for f in ordered])]
            vals["ordered_graph_groupby_ids"] = (
                ",".join(str(f.id) for f in ordered) or False
            )
        measure = variant.default_measure_field_id
        if (measure.id if measure else False) != (
            self.graph_measure_field_id.id if self.graph_measure_field_id else False
        ):
            vals["graph_measure_field_id"] = measure.id if measure else False
        agg = variant.default_measure_aggregator or False
        if measure and agg != (self.graph_measure_aggregator or False):
            vals["graph_measure_aggregator"] = agg
        elif not measure and self.graph_measure_aggregator:
            vals["graph_measure_aggregator"] = False
        if not measure and (self.graph_measure or "") not in ("", "__count"):
            vals["graph_measure"] = "__count"
        # Translated Char: force a fresh read before mirroring.
        variant.invalidate_recordset(["scope_warning"])
        warn = (variant.scope_warning or "").strip() or False
        bp_warn = (self.scope_warning or "").strip() or False
        if warn != bp_warn:
            vals["scope_warning"] = warn
        v_domain = (variant.graph_domain or "[]").strip() or "[]"
        bp_domain = (self.graph_domain or "[]").strip() or "[]"
        if v_domain != bp_domain:
            vals["graph_domain"] = v_domain
        if vals:
            self.with_context(skip_graph_variant_sync=True).write(vals)

    def _ensure_default_graph_variant_row(self):
        """Create one Chart Model Option from blueprint when none exist yet.

        Skip compose hubs (*360) and any blueprint whose Share Links peers
        already define chart options — those must not auto-own pack charts.
        """
        self.ensure_one()
        if self.graph_variant_ids or not self.graph_model:
            return
        if self._is_compose_hub():
            return
        peers = self._share_pool_members() - self
        if any(peer.graph_variant_ids for peer in peers):
            return
        xmlid = (self.primary_action_xmlid or "").strip()
        if not xmlid:
            Action = self.env["ir.actions.act_window"].sudo()
            act = Action.search(
                [("res_model", "=", self.graph_model)], order="id", limit=1
            )
            if act:
                xmlid = act.get_external_id().get(act.id) or ""
        if not xmlid:
            return
        created = self.env["dashboard.blueprint.graph.variant"].create(
            {
                "blueprint_id": self.id,
                "sequence": 10,
                "graph_model": self.graph_model,
                "graph_data_field": self.graph_data_field or False,
                "primary_button_label": self.primary_button_label
                or _("Chart Model"),
                "primary_action_xmlid": xmlid,
                "primary_action_context": self.primary_action_context or "{}",
                "primary_action_domain": (
                    (self.primary_action_domain or "[]").strip() or "[]"
                ),
                "primary_label_alt_scope_id": (
                    self.primary_label_alt_scope_id.id or False
                ),
                "primary_label_alt": self.primary_label_alt or False,
                "is_default": True,
                "scope_warning": self.scope_warning or False,
                "graph_domain": (self.graph_domain or "[]").strip() or "[]",
            }
        )
        legacy_alts = self.alternate_action_ids
        if legacy_alts:
            legacy_alts.write({"graph_variant_id": created.id})

    def _seed_variant_date_filters_from_blueprint(self, variant):
        """Copy blueprint Open/Closed date fields onto an empty option list.

        Additive only — never overwrites builder-chosen date filters. Runtime
        still uses blueprint period fields until the prefs migration (step 2).
        """
        self.ensure_one()
        if not variant or variant.date_filter_ids:
            return
        model = variant.graph_model
        if not model:
            return
        lines = []
        seq = 10
        seen = set()
        for field in (self.period_field_id, self.closed_period_field_id):
            if (
                not field
                or field.id in seen
                or field.model != model
                or field.ttype not in ("date", "datetime")
            ):
                continue
            seen.add(field.id)
            lines.append(
                {
                    "variant_id": variant.id,
                    "sequence": seq,
                    "label": field.field_description or field.name,
                    "field_id": field.id,
                }
            )
            seq += 10
        if lines:
            self.env["dashboard.blueprint.graph.variant.date.filter"].create(lines)

    def _ensure_option_graph_defaults(self):
        """Fill empty option Group By / Measure / Include from blueprint once.

        Options-only UX: builders edit on the option row. Older packs still
        store defaults on the blueprint — copy them onto matching options.
        """
        self.ensure_one()
        for variant in self.graph_variant_ids:
            vals = {}
            same_model = variant.graph_model == (self.graph_model or "")
            if not variant.default_groupby_ids and same_model and self.graph_groupby_ids:
                ordered = [
                    f
                    for f in self._ordered_graph_groupby_fields()
                    if f.model == variant.graph_model
                ]
                if ordered:
                    vals["default_groupby_ids"] = [(6, 0, [f.id for f in ordered])]
                    vals["default_ordered_groupby_ids"] = ",".join(
                        str(f.id) for f in ordered
                    )
            if (
                not variant.default_measure_field_id
                and same_model
                and self.graph_measure_field_id
                and self.graph_measure_field_id.model == variant.graph_model
            ):
                vals["default_measure_field_id"] = self.graph_measure_field_id.id
                vals["default_measure_aggregator"] = (
                    self.graph_measure_aggregator or "sum"
                )
            if not variant.default_scope_ids:
                applicable = self.scope_ids.filtered(
                    lambda s, m=variant.graph_model: s.mode == "include"
                    and s.default_on
                    and s._domain_applies_to_model(m)
                )
                if applicable:
                    vals["default_scope_ids"] = [(6, 0, applicable.ids)]
            if same_model:
                self._seed_variant_date_filters_from_blueprint(variant)
            if same_model and (
                not (variant.graph_domain or "").strip()
                or (variant.graph_domain or "").strip() == "[]"
            ):
                bp_domain = (self.graph_domain or "").strip()
                if bp_domain and bp_domain != "[]":
                    vals["graph_domain"] = bp_domain
            if not (variant.scope_warning or "").strip() and (
                self.scope_warning or ""
            ).strip():
                vals["scope_warning"] = self.scope_warning
            # Heal empty Link to Host so the gear picker can list the option.
            if not (variant.graph_data_field or "").strip():
                link = (self.graph_data_field or "").strip() or False
                if link and variant.graph_model == (self.graph_model or ""):
                    vals["graph_data_field"] = link
                else:
                    guessed = variant._default_link_to_host()
                    if guessed:
                        vals["graph_data_field"] = guessed
            # Secondary chart models (e.g. Sales Orders) are not on the blueprint
            # mirror — fill pack-style Group By / Measure when still empty.
            if not variant.default_groupby_ids or not variant.default_measure_field_id:
                # Merge after current vals so a same-model blueprint copy wins.
                suggested = variant._suggested_option_defaults_vals()
                for key, value in suggested.items():
                    if key == "default_groupby_ids" and (
                        vals.get("default_groupby_ids")
                        or variant.default_groupby_ids
                    ):
                        continue
                    if key == "default_measure_field_id" and (
                        vals.get("default_measure_field_id")
                        or variant.default_measure_field_id
                    ):
                        continue
                    if key == "default_ordered_groupby_ids" and (
                        vals.get("default_ordered_groupby_ids")
                        or variant.default_ordered_groupby_ids
                    ):
                        continue
                    if key == "default_measure_aggregator" and (
                        vals.get("default_measure_aggregator")
                        or variant.default_measure_aggregator
                    ):
                        continue
                    vals[key] = value
            if vals:
                variant.with_context(skip_graph_variant_default=True).write(vals)

    def _effective_graph_variant(self):
        """User gear pick (local or Share Links peer), else local Default.

        Studio left preview always follows the blueprint Default option so
        Content edits (set Default, Title Label, …) mirror immediately — not
        the admin's personal gear preference.
        """
        self.ensure_one()
        if self.env.context.get("dashboard_studio_preview"):
            return self._default_graph_variant()
        pool = self._effective_graph_variants()
        pref = self._current_pref()
        if pref:
            preferred = pref.preferred_graph_variant_id
            if (
                preferred
                and preferred in pool
                and preferred._is_valid_candidate()
            ):
                return preferred
            if pref.preferred_graph_model:
                match = pool.filtered(
                    lambda v: v.graph_model == pref.preferred_graph_model
                    and v._is_valid_candidate()
                )[:1]
                if match:
                    return match
        return self._default_graph_variant()

    def _effective_primary_bundle(self):
        """Label / action / context for the left primary button."""
        self.ensure_one()
        variant = self._effective_graph_variant()
        if variant:
            return {
                "label": variant.primary_button_label,
                "action_xmlid": variant.primary_action_xmlid,
                "action_context": variant.primary_action_context or "{}",
                "graph_model": variant.graph_model,
                "graph_data_field": variant.graph_data_field or self.graph_data_field,
            }
        return {
            "label": self.primary_button_label,
            "action_xmlid": self.primary_action_xmlid,
            "action_context": self.primary_action_context or "{}",
            "graph_model": self.graph_model,
            "graph_data_field": self.graph_data_field,
        }

    def studio_graph_model_candidates(self):
        self.ensure_one()
        return self._graph_model_candidates()

    _STUDIO_GRAPH_VARIANT_WRITE_FIELDS = frozenset(
        {
            "sequence",
            "graph_model",
            "graph_data_field",
            "primary_button_label",
            "primary_action_xmlid",
            "primary_action_id",
            "primary_action_context",
            "primary_action_domain",
            "primary_label_alt_scope_id",
            "primary_label_alt",
            "is_default",
            "default_groupby_field_ids",
            "default_measure_field_id",
            "default_measure_aggregator",
            "default_scope_ids",
            "scope_warning",
            "graph_domain",
        }
    )

    def _studio_graph_variant_dict(self, variant):
        """One Chart Model Option for Studio (owned or Share Links peer)."""
        self.ensure_one()
        owned = variant.blueprint_id == self
        ordered_gb = variant._ordered_default_groupby_fields()
        owner_includes = variant.blueprint_id.scope_ids.filtered(
            lambda s: s.mode == "include"
        )
        applicable = owner_includes.filtered(
            lambda s, m=variant.graph_model: s._domain_applies_to_model(m)
        )
        return {
            "id": variant.id,
            "sequence": variant.sequence,
            "owned": owned,
            "source_blueprint_id": variant.blueprint_id.id,
            "source_blueprint_name": (
                variant.blueprint_id.display_name or variant.blueprint_id.name or ""
            ),
            "source_blueprint_key": variant.blueprint_id.key or "",
            "graph_model": variant.graph_model or "",
            "graph_model_id": variant.graph_model_id.id or False,
            "graph_model_label": (
                variant.graph_model_id.name or variant.graph_model or ""
            ),
            "graph_data_field": variant.graph_data_field or "",
            "primary_button_label": variant.primary_button_label or "",
            "primary_action_xmlid": variant.primary_action_xmlid or "",
            "primary_action_id": variant.primary_action_id.id or False,
            "primary_action_name": (
                variant.primary_action_id.display_name
                or variant.primary_action_xmlid
                or ""
            ),
            "primary_action_context": variant.primary_action_context or "{}",
            "primary_action_domain": variant.primary_action_domain or "[]",
            "primary_label_alt_scope_id": (
                variant.primary_label_alt_scope_id.id or False
            ),
            "primary_label_alt": variant.primary_label_alt or "",
            "alternate_actions": [
                {
                    "id": alt.id,
                    "sequence": alt.sequence,
                    "name": alt.name or "",
                    "module_depends": alt.module_depends or "",
                    "module_ids": alt.module_ids.ids,
                    "module_names": alt.module_ids.mapped("name"),
                    "action_xmlid": alt.action_xmlid or "",
                    "action_id": alt.action_id.id or False,
                    "action_name": (
                        alt.action_id.display_name or alt.action_xmlid or ""
                    ),
                    "action_domain": alt.action_domain or "[]",
                }
                for alt in variant.alternate_action_ids.sorted("sequence")
            ],
            # Default flag is local only — peer defaults stay on their owner.
            "is_default": False,  # filled in get_studio_payload from _default_graph_variant
            "is_available": bool(variant.is_available),
            "default_groupby_field_ids": ordered_gb.ids,
            "default_groupby_field_names": [
                f.field_description or f.name for f in ordered_gb
            ],
            "default_measure_field_id": (
                variant.default_measure_field_id.id or False
            ),
            "default_measure_field_name": (
                variant.default_measure_field_id.field_description
                or variant.default_measure_field_id.name
                or ""
            ),
            "default_measure_aggregator": (
                variant.default_measure_aggregator or "sum"
            ),
            "default_scope_ids": variant.default_scope_ids.ids,
            "applicable_include_scope_ids": applicable.ids,
            "applicable_include_scopes": [
                {"id": s.id, "name": s.name or "", "mode": "include"}
                for s in applicable.sorted("sequence")
            ],
            "scope_warning": variant.scope_warning or "",
            "graph_domain": variant.graph_domain or "[]",
            "date_filters": [
                {
                    "id": d.id,
                    "label": d.label or "",
                    "field_id": d.field_id.id or False,
                    "field_name": d.field_name or "",
                    "field_label": (
                        d.field_id.field_description or d.field_name or ""
                    ),
                    "default_period_mq_ids": d.default_period_mq_ids.ids,
                    "default_period_year_ids": d.default_period_year_ids.ids,
                }
                for d in variant.date_filter_ids.sorted("sequence")
            ],
        }

    def get_studio_payload(self):
        self._ensure_default_graph_variant_row()
        self._ensure_option_graph_defaults()
        # Heal writes skip the Default-option sync; run it once after fill.
        if self.graph_variant_ids.filtered("is_default"):
            self._sync_blueprint_from_default_variant()
        # Drop stale hub pointer when the option left Share Links / was deleted.
        pooled = self.pooled_default_graph_variant_id
        if pooled:
            pool = self._effective_graph_variants()
            if pooled not in pool or pooled.blueprint_id == self:
                self.with_context(skip_graph_variant_default=True).write(
                    {"pooled_default_graph_variant_id": False}
                )
        payload = super().get_studio_payload()
        # Always pool Share Links peers (read-only fields; Default radio allowed).
        default = self._default_graph_variant()
        default_id = default.id if default else False
        variants = []
        for variant in self._effective_graph_variants():
            row = self._studio_graph_variant_dict(variant)
            row["is_default"] = bool(default_id and variant.id == default_id)
            variants.append(row)
        payload["graph_variants"] = variants
        payload["default_graph_variant_id"] = default_id or False
        payload["pooled_default_graph_variant_id"] = (
            self.pooled_default_graph_variant_id.id or False
        )
        payload["period_mq_catalog"] = [
            {"id": row.id, "name": row.name or "", "label": row.display_name or row.name or ""}
            for row in self.env["period.month.quarter"].search([])
        ]
        payload["period_year_catalog"] = [
            {"id": row.id, "name": row.name or "", "label": row.display_name or row.name or ""}
            for row in self.env["period.year"].search([])
        ]
        return payload

    def studio_set_default_graph_variant(self, variant_id):
        self.ensure_one()
        variant_id = int(variant_id)
        pool = self._effective_graph_variants()
        variant = pool.filtered(lambda v: v.id == variant_id)[:1]
        if not variant:
            raise UserError(_("Unknown chart model option on this dashboard."))
        if variant.blueprint_id == self:
            self._studio_mark_default_graph_variant(variant)
        else:
            self._studio_mark_pooled_default_graph_variant(variant)
        return self.get_studio_payload()

    def studio_write_graph_variant(self, variant_id, vals):
        self.ensure_one()
        variant = self.graph_variant_ids.filtered(lambda v: v.id == variant_id)[:1]
        if not variant:
            raise UserError(_("Unknown chart model option on this dashboard."))
        clean = {}
        set_default = False
        for key, value in (vals or {}).items():
            if key not in self._STUDIO_GRAPH_VARIANT_WRITE_FIELDS:
                continue
            if key == "is_default":
                set_default = bool(value)
                continue
            if key == "sequence":
                clean["sequence"] = int(value)
            elif key == "graph_model":
                model = (value or "").strip()
                if not model:
                    raise UserError(_("Chart Model is required."))
                if model not in self.env:
                    raise UserError(_("Unknown model: %s") % model)
                clean["graph_model"] = model
                # Heal Link to host when the old path does not fit the new model.
                next_link = clean.get(
                    "graph_data_field", variant.graph_data_field or False
                )
                host = self.host_model_name
                ok = False
                if next_link and host:
                    try:
                        validate_relation_path(self.env, model, next_link, host)
                        ok = True
                    except ValidationError:
                        ok = False
                if not ok:
                    clean["graph_data_field"] = variant._default_link_to_host(model)
            elif key == "graph_data_field":
                # Allow incomplete hop chains while the builder drills toward
                # the host; OK / runtime still require a full path to host.
                path = (value or "").strip() or False
                if path:
                    try:
                        validate_relation_path_chain(
                            self.env,
                            clean.get("graph_model") or variant.graph_model,
                            path,
                        )
                    except ValidationError as err:
                        raise UserError(err.args[0]) from err
                clean["graph_data_field"] = path
            elif key == "primary_button_label":
                label = (value or "").strip()
                if not label:
                    raise UserError(_("Primary Button label is required."))
                clean["primary_button_label"] = label
            elif key == "primary_action_xmlid":
                xmlid = (value or "").strip()
                if not xmlid:
                    raise UserError(_("Primary action is required."))
                clean["primary_action_xmlid"] = xmlid
            elif key == "primary_action_id":
                action_id = int(value) if value else False
                if not action_id:
                    raise UserError(_("Primary action is required."))
                action = self.env["ir.actions.act_window"].browse(action_id)
                if not action.exists():
                    raise UserError(_("Unknown window action."))
                xmlid = action.get_external_id().get(action.id) or ""
                if not xmlid:
                    raise UserError(
                        _("This action has no external ID (xmlid). "
                          "Export it or pick another action.")
                    )
                clean["primary_action_xmlid"] = xmlid
            elif key == "primary_action_context":
                clean["primary_action_context"] = (value or "").strip() or "{}"
            elif key == "primary_action_domain":
                # Same shape as Custom Filter; may include {{id}} tokens.
                clean["primary_action_domain"] = self._studio_validate_graph_domain(
                    value
                )
            elif key == "primary_label_alt_scope_id":
                sid = int(value) if value else False
                if sid:
                    scope = self.scope_ids.filtered(lambda s: s.id == sid)[:1]
                    if not scope:
                        raise UserError(
                            _("Alternate label filter must belong to this dashboard.")
                        )
                    clean["primary_label_alt_scope_id"] = sid
                else:
                    clean["primary_label_alt_scope_id"] = False
                    clean["primary_label_alt"] = False
            elif key == "primary_label_alt":
                clean["primary_label_alt"] = (value or "").strip() or False
            elif key == "default_groupby_field_ids":
                ids = [int(i) for i in (value or []) if i]
                allowed = set(variant.graph_groupby_allowed_field_ids.ids)
                ids = [i for i in ids if i in allowed]
                clean["default_groupby_ids"] = [(6, 0, ids)]
                clean["default_ordered_groupby_ids"] = (
                    ",".join(str(i) for i in ids) or False
                )
            elif key == "default_measure_field_id":
                mid = int(value) if value else False
                if mid:
                    field = self.env["ir.model.fields"].browse(mid)
                    if (
                        not field.exists()
                        or field.model != variant.graph_model
                        or field.ttype not in ("integer", "float", "monetary")
                        or not field.store
                    ):
                        raise UserError(
                            _("Default Measure must be a stored numeric field "
                              "on this chart model.")
                        )
                clean["default_measure_field_id"] = mid
                if not mid:
                    clean["default_measure_aggregator"] = False
            elif key == "default_measure_aggregator":
                agg = (value or "").strip() or False
                if agg and agg not in dict(VARIANT_AGGREGATORS):
                    raise UserError(_("Unknown Measured As value: %s") % agg)
                clean["default_measure_aggregator"] = agg
            elif key == "default_scope_ids":
                ids = [int(i) for i in (value or []) if i]
                model = clean.get("graph_model") or variant.graph_model
                allowed = set(
                    self.scope_ids.filtered(
                        lambda s, m=model: s.mode == "include"
                        and s._domain_applies_to_model(m)
                    ).ids
                )
                ids = [i for i in ids if i in allowed]
                clean["default_scope_ids"] = [(6, 0, ids)]
            elif key == "scope_warning":
                clean["scope_warning"] = (value or "").strip() or False
            elif key == "graph_domain":
                clean["graph_domain"] = self._studio_validate_graph_domain(value)
        if clean:
            variant.write(clean)
            # Translated Char can leave a stale cache on the option row; push
            # the Default option warning onto the blueprint from the written val.
            if "scope_warning" in clean and variant.is_default:
                warn = (clean.get("scope_warning") or "").strip() or False
                if ((self.scope_warning or "").strip() or False) != warn:
                    self.with_context(skip_graph_variant_sync=True).write(
                        {"scope_warning": warn}
                    )
            if "graph_domain" in clean and variant.is_default:
                domain = clean.get("graph_domain") or "[]"
                if ((self.graph_domain or "[]").strip() or "[]") != domain:
                    self.with_context(skip_graph_variant_sync=True).write(
                        {"graph_domain": domain}
                    )
        if set_default:
            self._studio_mark_default_graph_variant(variant)
        return self.get_studio_payload()

    def studio_create_graph_variant(self, vals=None):
        self.ensure_one()
        vals = vals or {}
        model = (vals.get("graph_model") or self.graph_model or self.host_model_name or "").strip()
        if not model:
            raise UserError(_("Chart Model is required."))
        if model not in self.env:
            raise UserError(_("Unknown model: %s") % model)
        label = (vals.get("primary_button_label") or "").strip() or _("Chart Model")
        xmlid = (vals.get("primary_action_xmlid") or self.primary_action_xmlid or "").strip()
        if not xmlid:
            Action = self.env["ir.actions.act_window"].sudo()
            act = Action.search([("res_model", "=", model)], order="id", limit=1)
            if act:
                xmlid = act.get_external_id().get(act.id) or ""
        if not xmlid:
            raise UserError(
                _(
                    "Set a Primary action under Chart & Primary first, "
                    "or pass one when adding this option."
                )
            )
        seq = max(self.graph_variant_ids.mapped("sequence") or [0]) + 10
        make_default = bool(vals.get("is_default")) or not self.graph_variant_ids
        create_vals = {
            "blueprint_id": self.id,
            "sequence": int(vals.get("sequence") or seq),
            "graph_model": model,
            "graph_data_field": (
                (vals.get("graph_data_field") or self.graph_data_field or "").strip()
                or False
            ),
            "primary_button_label": label,
            "primary_action_xmlid": xmlid,
            "primary_action_context": (
                (vals.get("primary_action_context") or "{}").strip() or "{}"
            ),
            "is_default": make_default,
            "scope_warning": (
                (vals.get("scope_warning") or self.scope_warning or "").strip()
                or False
            ),
            "graph_domain": "[]",
        }
        # Seed chart defaults from blueprint when this option matches the
        # current blueprint chart model (first / default option).
        if model == (self.graph_model or ""):
            if "graph_domain" in vals:
                create_vals["graph_domain"] = self._studio_validate_graph_domain(
                    vals.get("graph_domain")
                )
            else:
                create_vals["graph_domain"] = (
                    (self.graph_domain or "[]").strip() or "[]"
                )
            ordered = [
                f
                for f in self._ordered_graph_groupby_fields()
                if f.model == model
            ]
            if ordered:
                create_vals["default_groupby_ids"] = [(6, 0, [f.id for f in ordered])]
                create_vals["default_ordered_groupby_ids"] = ",".join(
                    str(f.id) for f in ordered
                )
            if (
                self.graph_measure_field_id
                and self.graph_measure_field_id.model == model
            ):
                create_vals["default_measure_field_id"] = self.graph_measure_field_id.id
                create_vals["default_measure_aggregator"] = (
                    self.graph_measure_aggregator or "sum"
                )
            include = self.scope_ids.filtered(
                lambda s: s.mode == "include"
                and s.default_on
                and s._domain_applies_to_model(model)
            )
            if include:
                create_vals["default_scope_ids"] = [(6, 0, include.ids)]
        created = self.env["dashboard.blueprint.graph.variant"].create(create_vals)
        self._seed_variant_date_filters_from_blueprint(created)
        payload = self.get_studio_payload()
        payload["created_graph_variant_id"] = created.id
        return payload

    def studio_unlink_graph_variant(self, variant_id):
        self.ensure_one()
        variant = self.graph_variant_ids.filtered(lambda v: v.id == variant_id)[:1]
        if variant:
            variant.unlink()
        return self.get_studio_payload()

    def studio_reorder_graph_variants(self, ordered_ids):
        self.ensure_one()
        ordered_ids = [int(i) for i in (ordered_ids or [])]
        by_id = {v.id: v for v in self.graph_variant_ids}
        if set(ordered_ids) != set(by_id):
            raise UserError(
                _("Chart Model list is out of date. Reload Studio and try again.")
            )
        for index, variant_id in enumerate(ordered_ids):
            by_id[variant_id].sequence = (index + 1) * 10
        return self.get_studio_payload()

    def _studio_find_graph_variant(self, variant_id):
        variant = self.graph_variant_ids.filtered(lambda v: v.id == int(variant_id))[:1]
        if not variant:
            raise UserError(_("Unknown chart model option on this dashboard."))
        return variant

    def _studio_find_date_filter(self, row_id, *, required=True):
        """Resolve a date-filter row that belongs to this blueprint."""
        self.ensure_one()
        try:
            rid = int(row_id)
        except (TypeError, ValueError):
            rid = 0
        row = self.env["dashboard.blueprint.graph.variant.date.filter"].browse(rid)
        if row.exists() and row.variant_id.blueprint_id == self:
            return row
        if required:
            raise UserError(_("Unknown date filter on this dashboard."))
        return row.browse()

    def studio_create_graph_variant_date_filter(self, variant_id, vals=None):
        self.ensure_one()
        variant = self._studio_find_graph_variant(variant_id)
        if not variant.graph_model:
            raise UserError(_("Set Chart Model first."))
        vals = vals or {}
        field_id = int(vals.get("field_id") or 0) or False
        field = self.env["ir.model.fields"].browse(field_id) if field_id else None
        if not field or not field.exists() or field.model != variant.graph_model:
            raise UserError(_("Pick a date field on this chart model."))
        if field.ttype not in ("date", "datetime"):
            raise UserError(_("Date Filter fields must be Date or Datetime."))
        if variant.date_filter_ids.filtered(lambda d: d.field_id == field or d.field_name == field.name):
            raise UserError(_("That date field is already on this chart model."))
        label = (vals.get("label") or "").strip() or field.field_description or field.name
        seq = max(variant.date_filter_ids.mapped("sequence") or [0]) + 10
        created = self.env["dashboard.blueprint.graph.variant.date.filter"].create(
            {
                "variant_id": variant.id,
                "sequence": seq,
                "label": label,
                "field_id": field.id,
            }
        )
        payload = self.get_studio_payload()
        payload["created_graph_variant_date_filter_id"] = created.id
        return payload

    def studio_write_graph_variant_date_filter(self, row_id, vals):
        self.ensure_one()
        # Soft-miss: label blur can race with Remove (unlink wins first).
        row = self._studio_find_date_filter(row_id, required=False)
        if not row:
            return self.get_studio_payload()
        clean = {}
        for key, value in (vals or {}).items():
            if key == "label":
                label = (value or "").strip()
                if not label:
                    raise UserError(_("Date Filter label is required."))
                clean["label"] = label
            elif key == "field_id":
                field_id = int(value) if value else False
                field = self.env["ir.model.fields"].browse(field_id) if field_id else None
                if (
                    not field
                    or not field.exists()
                    or field.model != row.variant_id.graph_model
                    or field.ttype not in ("date", "datetime")
                ):
                    raise UserError(_("Pick a date field on this chart model."))
                clean["field_id"] = field.id
            elif key == "default_period_mq_ids":
                ids = [int(i) for i in (value or []) if i]
                clean["default_period_mq_ids"] = [(6, 0, ids)]
            elif key == "default_period_year_ids":
                ids = [int(i) for i in (value or []) if i]
                clean["default_period_year_ids"] = [(6, 0, ids)]
        if clean:
            row.write(clean)
        return self.get_studio_payload()

    def studio_unlink_graph_variant_date_filter(self, row_id):
        self.ensure_one()
        row = self._studio_find_date_filter(row_id, required=False)
        if row:
            row.unlink()
        return self.get_studio_payload()

    def _studio_find_alternate_action(self, row_id, *, required=True):
        self.ensure_one()
        try:
            rid = int(row_id)
        except (TypeError, ValueError):
            rid = 0
        row = self.env["dashboard.blueprint.action.variant"].browse(rid)
        if (
            row.exists()
            and row.blueprint_id == self
            and row.graph_variant_id
            and row.graph_variant_id.blueprint_id == self
        ):
            return row
        if required:
            raise UserError(_("Unknown alternate action on this dashboard."))
        return row.browse()

    def studio_create_graph_variant_alternate_action(self, variant_id, vals=None):
        self.ensure_one()
        variant = self._studio_find_graph_variant(variant_id)
        vals = vals or {}
        seq = max(variant.alternate_action_ids.mapped("sequence") or [0]) + 10
        module_ids = [int(i) for i in (vals.get("module_ids") or []) if i]
        action_id = int(vals.get("action_id") or 0) or False
        xmlid = (vals.get("action_xmlid") or "").strip() or False
        create_vals = {
            "blueprint_id": self.id,
            "graph_variant_id": variant.id,
            "sequence": seq,
            "name": (vals.get("name") or "").strip() or _("Alternate action"),
        }
        if module_ids:
            create_vals["module_ids"] = [(6, 0, module_ids)]
        if action_id:
            create_vals["action_id"] = action_id
        elif xmlid:
            create_vals["action_xmlid"] = xmlid
        created = self.env["dashboard.blueprint.action.variant"].create(create_vals)
        payload = self.get_studio_payload()
        payload["created_graph_variant_alternate_action_id"] = created.id
        return payload

    def studio_write_graph_variant_alternate_action(self, row_id, vals):
        self.ensure_one()
        row = self._studio_find_alternate_action(row_id, required=False)
        if not row:
            return self.get_studio_payload()
        clean = {}
        for key, value in (vals or {}).items():
            if key == "name":
                clean["name"] = (value or "").strip() or False
            elif key == "sequence":
                clean["sequence"] = int(value or 0)
            elif key == "module_ids":
                ids = [int(i) for i in (value or []) if i]
                clean["module_ids"] = [(6, 0, ids)]
            elif key == "action_id":
                aid = int(value) if value else False
                if not aid:
                    clean["action_id"] = False
                    clean["action_xmlid"] = False
                else:
                    action = self.env["ir.actions.act_window"].browse(aid)
                    if not action.exists():
                        raise UserError(_("Unknown window action."))
                    xmlid = action.get_external_id().get(action.id) or ""
                    if not xmlid:
                        raise UserError(
                            _("This action has no external ID (xmlid). "
                              "Export it or pick another action.")
                        )
                    clean["action_id"] = aid
                    clean["action_xmlid"] = xmlid
            elif key == "action_xmlid":
                clean["action_xmlid"] = (value or "").strip() or False
            elif key == "action_domain":
                # Same shape as Primary Action Domain; may include {{id}} tokens.
                # Empty / [] means inherit the Chart Model Option domain at runtime.
                clean["action_domain"] = self._studio_validate_graph_domain(value)
        if clean:
            row.write(clean)
        return self.get_studio_payload()

    def studio_unlink_graph_variant_alternate_action(self, row_id):
        self.ensure_one()
        row = self._studio_find_alternate_action(row_id, required=False)
        if row:
            row.unlink()
        return self.get_studio_payload()

    def _seed_crm_graph_variant_defaults(self):
        """Ensure CRM Customers exposes Chart model options in Configuration.

        Customer 360 must NOT be seeded here — it composes CRM / Sales / …
        options via Share Links. Seeding duplicates makes Sales show
        ``Shared from Customer 360`` for Pipeline / Sales Orders.
        """
        Variant = self.env["dashboard.blueprint.graph.variant"].sudo()
        specs = [
            (
                "crm_customer_dashboard.blueprint_crm_customers",
                [
                    {
                        "sequence": 10,
                        "graph_model": "crm.lead",
                        "graph_data_field": "partner_id",
                        "primary_button_label": "Pipeline Analysis",
                        "primary_action_xmlid": "crm.crm_lead_action_pipeline",
                        "primary_action_context": (
                            '{"default_type": {"__de__": "group_value", '
                            '"default": "opportunity", "map": [{"groups": '
                            '["crm.group_use_lead"], "value": "lead"}]}}'
                        ),
                    },
                    {
                        "sequence": 20,
                        "graph_model": "sale.order",
                        "graph_data_field": "partner_id",
                        "primary_button_label": "Sales Orders",
                        "primary_action_xmlid": "sale.action_orders",
                        "primary_action_context": "{}",
                    },
                ],
            ),
        ]
        for xmlid, rows in specs:
            bp = self.env.ref(xmlid, raise_if_not_found=False)
            if not bp:
                continue
            for row in rows:
                if row["graph_model"] not in self.env:
                    continue
                if not self._action_xmlid_exists(row["primary_action_xmlid"]):
                    continue
                existing = bp.graph_variant_ids.filtered(
                    lambda v, m=row["graph_model"]: v.graph_model == m
                )[:1]
                if existing:
                    ctx = (row.get("primary_action_context") or "").strip()
                    if ctx and ctx != "{}" and (
                        existing.primary_action_context or ""
                    ).strip() in ("", "{}"):
                        existing.write({"primary_action_context": ctx})
                        if existing.is_default:
                            bp._sync_blueprint_from_default_variant()
                    continue
                create_vals = {"blueprint_id": bp.id, **row}
                if row["sequence"] == 10 and not bp.graph_variant_ids.filtered(
                    "is_default"
                ):
                    create_vals["is_default"] = True
                Variant.create(create_vals)
            if bp.graph_variant_ids and not bp.graph_variant_ids.filtered("is_default"):
                match = bp.graph_variant_ids.filtered(
                    lambda v: v.graph_model == bp.graph_model
                )[:1]
                bp._studio_mark_default_graph_variant(
                    match or bp.graph_variant_ids.sorted("sequence")[:1]
                )


class DashboardBlueprintGraphVariantDateFilter(models.Model):
    """One date filter choice for a Chart Model Option.

    A model-level date filter cannot work across options: ``crm.lead`` has
    both a creation date and a closed date, while ``sale.order`` only has
    one. Each option therefore keeps its own small list of date fields to
    offer in the live gear, resolved through ``dashboard.mirror.mixin`` so
    renames of the underlying field are caught instead of failing silently.
    """

    _name = "dashboard.blueprint.graph.variant.date.filter"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Chart Model Option Date Filter"
    _order = "sequence, id"
    _rec_name = "label"

    variant_id = fields.Many2one(
        "dashboard.blueprint.graph.variant",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    label = fields.Char(
        required=True,
        translate=True,
        help="Shown to end users in the live date filter picker, e.g. Closed Date.",
    )
    field_name = fields.Char(
        string="Date Field Name",
        help="Technical date/datetime field on the chart model, e.g. date_closed.",
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Date Field",
        compute="_compute_field_id",
        inverse="_inverse_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Convenience picker for Date Field Name.",
    )
    default_period_mq_ids = fields.Many2many(
        "period.month.quarter",
        "dashboard_graph_variant_date_filter_mq_rel",
        "date_filter_id",
        "period_mq_id",
        string="Default Months / Quarters",
        help="Seeded into the live gear the first time a user has no months "
        "picked for this date row. Users can always change their own picks.",
    )
    default_period_year_ids = fields.Many2many(
        "period.year",
        "dashboard_graph_variant_date_filter_year_rel",
        "date_filter_id",
        "period_year_id",
        string="Default Years",
        help="Seeded into the live gear the first time a user has no years "
        "picked for this date row. Users can always change their own picks.",
    )

    @api.depends("field_name", "variant_id.graph_model")
    def _compute_field_id(self):
        for rec in self:
            rec.field_id = rec._mirror_field(rec.variant_id.graph_model, rec.field_name)

    def _inverse_field_id(self):
        for rec in self:
            rec.field_name = rec.field_id.name or False

    @api.constrains("field_id")
    def _check_field_type(self):
        for rec in self:
            if rec.field_id and rec.field_id.ttype not in ("date", "datetime"):
                raise ValidationError(_("Date Filter fields must be Date or Datetime."))


class DashboardUserPrefGraphPicker(models.Model):
    _inherit = "dashboard.user.pref"

    preferred_graph_model = fields.Char(
        string="Chart Model (Technical)",
        help="Technical model name mirrored from the Chart Model picker.",
    )
    preferred_graph_variant_id = fields.Many2one(
        "dashboard.blueprint.graph.variant",
        string="Chart Model",
        ondelete="set null",
        domain="[('id', 'in', allowed_graph_variant_ids)]",
        help="Pick which records feed the chart. The left button label and "
        "screen change with this choice so they always match. "
        "Includes Chart Model Options from Share Links dashboards on the "
        "same host. Empty = blueprint default.",
    )
    allowed_graph_variant_ids = fields.Many2many(
        "dashboard.blueprint.graph.variant",
        compute="_compute_allowed_graph_variant_ids",
        string="Allowed Chart Models",
        help="Local Chart Model Options plus those pooled via Share Links.",
    )
    has_graph_variants = fields.Boolean(compute="_compute_has_graph_variants")

    @api.depends(
        "blueprint_id",
        "blueprint_id.graph_variant_ids",
        "blueprint_id.graph_variant_ids.graph_model",
        "blueprint_id.graph_variant_ids.primary_action_xmlid",
        "blueprint_id.share_link_ids",
        "blueprint_id.share_link_ids.graph_variant_ids",
        "blueprint_id.share_link_ids.graph_variant_ids.graph_model",
        "blueprint_id.share_link_ids.graph_variant_ids.primary_action_xmlid",
    )
    def _compute_allowed_graph_variant_ids(self):
        for pref in self:
            if pref.blueprint_id:
                pref.allowed_graph_variant_ids = (
                    pref.blueprint_id._effective_graph_variants()
                )
            else:
                pref.allowed_graph_variant_ids = False

    @api.depends(
        "blueprint_id",
        "blueprint_id.graph_variant_ids",
        "blueprint_id.graph_variant_ids.graph_model",
        "blueprint_id.graph_variant_ids.primary_action_xmlid",
        "blueprint_id.share_link_ids",
        "blueprint_id.share_link_ids.graph_variant_ids",
        "blueprint_id.share_link_ids.graph_variant_ids.graph_model",
        "blueprint_id.share_link_ids.graph_variant_ids.primary_action_xmlid",
    )
    def _compute_has_graph_variants(self):
        for pref in self:
            pref.has_graph_variants = bool(pref.blueprint_id._graph_model_candidates())

    @api.onchange("preferred_graph_variant_id")
    def _onchange_preferred_graph_variant_id(self):
        for pref in self:
            pref.preferred_graph_model = (
                pref.preferred_graph_variant_id.graph_model
                if pref.preferred_graph_variant_id
                else False
            )
            # Cache-only: never write() from onchange — the dialog UI would not
            # refresh Group By / Measure / Data to Include otherwise.
            pref._apply_variant_graph_defaults(cache_only=True)

    def write(self, vals):
        vals = dict(vals)
        if "preferred_graph_variant_id" in vals and "preferred_graph_model" not in vals:
            variant = self.env["dashboard.blueprint.graph.variant"].browse(
                vals["preferred_graph_variant_id"] or []
            )
            vals["preferred_graph_model"] = (
                variant.graph_model if variant else False
            )
        res = super().write(vals)
        if (
            "preferred_graph_variant_id" in vals or "preferred_graph_model" in vals
        ) and not self.env.context.get("skip_variant_graph_defaults"):
            self._apply_variant_graph_defaults(cache_only=False)
        return res

    def _resolve_pref_graph_variant(self):
        """Preferred option, else blueprint Default option.

        Prefer the selected row even when not yet ``is_available`` so the gear
        onchange still reseeds from that option while the builder finishes it.
        """
        self.ensure_one()
        if self.preferred_graph_variant_id:
            return self.preferred_graph_variant_id
        if self.blueprint_id:
            return self.blueprint_id._default_graph_variant()
        return self.env["dashboard.blueprint.graph.variant"]

    def _apply_variant_graph_defaults(self, cache_only=False):
        """Copy Chart Model Option defaults onto this preference.

        Keeps My Data (restrict) ticks; replaces Include ticks, Group By,
        Measure, and Measured As from the active option.
        """
        for pref in self:
            variant = pref._resolve_pref_graph_variant()
            if not variant:
                pref._clear_stale_graph_fields()
                pref._sync_pref_period_lines(cache_only=cache_only or not pref.ids)
                continue
            ordered, measure, agg, include = variant._pref_defaults_for_gear()
            restrict = pref.scope_ids.filtered(lambda s: s.mode == "restrict")
            order_char = ",".join(str(f.id) for f in ordered) or False
            groupby_ids = [f.id for f in ordered]
            scope_ids = (restrict | include).ids
            if cache_only or not pref.ids:
                # Always use (6, 0, ids) on the form cache — a bare record list
                # corrupts many2many NewId caches and breaks later filtered().
                pref.groupby_ids = [(6, 0, groupby_ids)]
                pref.ordered_groupby_ids = order_char
                pref.measure_field_id = measure.id if measure else False
                pref.measure_aggregator = agg
                pref.scope_ids = [(6, 0, scope_ids)]
            else:
                pref.with_context(skip_variant_graph_defaults=True).write(
                    {
                        "groupby_ids": [(6, 0, groupby_ids)],
                        "ordered_groupby_ids": order_char,
                        "measure_field_id": measure.id if measure else False,
                        "measure_aggregator": agg,
                        "scope_ids": [(6, 0, scope_ids)],
                    }
                )
            pref._clear_stale_graph_fields()
            # Date filter rows follow the active Chart Model Option list.
            pref._sync_pref_period_lines(cache_only=cache_only or not pref.ids)

    def _clear_stale_graph_fields(self):
        for pref in self:
            model = (
                (
                    pref.preferred_graph_variant_id.graph_model
                    if pref.preferred_graph_variant_id
                    else False
                )
                or pref.preferred_graph_model
                or pref.graph_model
                or pref.blueprint_id.graph_model
            )
            if not model or model not in self.env:
                continue
            Model = self.env[model]
            if pref.measure_field_id and pref.measure_field_id.name not in Model._fields:
                pref.measure_field_id = False
                pref.measure_aggregator = False
            # Resolve ids first — NewId m2m caches can be fragile mid-onchange.
            groupby = pref.groupby_ids.exists()
            stale = groupby.filtered(
                lambda f: f.model != model
                or (not f.is_date_period() and f.name not in Model._fields)
            )
            if stale:
                keep = (groupby - stale).ids
                pref.groupby_ids = [(6, 0, keep)]
                pref.ordered_groupby_ids = ",".join(str(i) for i in keep) or False
