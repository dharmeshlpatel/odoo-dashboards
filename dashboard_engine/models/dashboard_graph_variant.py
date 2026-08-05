# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Graph Model picker bundle (Phase 3): model + primary button together."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools.relation_path import (
    validate_path as validate_relation_path,
    validate_path_chain as validate_relation_path_chain,
)


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
    )
    primary_action_context = fields.Char(default="{}")
    is_default = fields.Boolean(
        string="Default",
        default=False,
        help="Blueprint default chart model when the user has not picked one in the gear.",
    )
    is_available = fields.Boolean(
        compute="_compute_is_available",
        help="True when the model is installed and the link + action are usable.",
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
        """Hide variants whose model/action is not usable on this database."""
        rows = super().name_search(
            name=name, domain=domain, operator=operator, limit=None
        )
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

    def _graph_model_candidates(self):
        self.ensure_one()
        rows = []
        for variant in self.graph_variant_ids.sorted("sequence"):
            if variant._is_valid_candidate():
                rows.append(
                    {
                        "id": variant.id,
                        "graph_model": variant.graph_model,
                        "label": variant.primary_button_label,
                        "action_xmlid": variant.primary_action_xmlid,
                        "is_default": bool(variant.is_default),
                    }
                )
        return rows

    def _default_graph_variant(self):
        """Blueprint default option (is_default), else first valid by sequence."""
        self.ensure_one()
        marked = self.graph_variant_ids.filtered("is_default").sorted("sequence")
        for variant in marked:
            if variant._is_valid_candidate():
                return variant
        for variant in self.graph_variant_ids.sorted("sequence"):
            if variant._is_valid_candidate():
                return variant
        return marked[:1]

    def _studio_mark_default_graph_variant(self, variant):
        """Exclusive default + mirror chart/primary fields onto the blueprint."""
        self.ensure_one()
        if not variant or variant.blueprint_id != self:
            return
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

    def _sync_blueprint_from_default_variant(self):
        """Keep blueprint graph_model / primary fields = Default option."""
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
        if vals:
            self.with_context(skip_graph_variant_sync=True).write(vals)

    def _effective_graph_variant(self):
        """User gear pick, else blueprint Default option."""
        self.ensure_one()
        pref = self._current_pref()
        if pref:
            if (
                pref.preferred_graph_variant_id
                and pref.preferred_graph_variant_id._is_valid_candidate()
            ):
                return pref.preferred_graph_variant_id
            if pref.preferred_graph_model:
                match = self.graph_variant_ids.filtered(
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
            "primary_action_context",
            "is_default",
        }
    )

    def get_studio_payload(self):
        payload = super().get_studio_payload()
        variants = []
        for variant in self.graph_variant_ids.sorted("sequence"):
            variants.append(
                {
                    "id": variant.id,
                    "sequence": variant.sequence,
                    "graph_model": variant.graph_model or "",
                    "graph_model_id": variant.graph_model_id.id or False,
                    "graph_model_label": (
                        variant.graph_model_id.name
                        or variant.graph_model
                        or ""
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
                    "is_default": bool(variant.is_default),
                    "is_available": bool(variant.is_available),
                }
            )
        payload["graph_variants"] = variants
        payload["default_graph_variant_id"] = (
            self.graph_variant_ids.filtered("is_default")[:1].id or False
        )
        return payload

    def studio_set_default_graph_variant(self, variant_id):
        self.ensure_one()
        variant = self.graph_variant_ids.filtered(lambda v: v.id == int(variant_id))[:1]
        if not variant:
            raise UserError(_("Unknown chart model option on this dashboard."))
        self._studio_mark_default_graph_variant(variant)
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
            elif key == "primary_action_context":
                clean["primary_action_context"] = (value or "").strip() or "{}"
        if clean:
            variant.write(clean)
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
        created = self.env["dashboard.blueprint.graph.variant"].create(
            {
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
            }
        )
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

    def _seed_crm_graph_variant_defaults(self):
        """Ensure CRM / Customer 360 boards expose Chart model in Configuration."""
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
            (
                "customer_360_dashboard.blueprint_customer_360",
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
        domain="[('blueprint_id', '=', blueprint_id)]",
        help="Pick which records feed the chart. The left button label and "
        "screen change with this choice so they always match. "
        "Empty = blueprint default.",
    )
    has_graph_variants = fields.Boolean(compute="_compute_has_graph_variants")

    @api.depends(
        "blueprint_id",
        "blueprint_id.graph_variant_ids",
        "blueprint_id.graph_variant_ids.graph_model",
        "blueprint_id.graph_variant_ids.primary_action_xmlid",
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
            pref._clear_stale_graph_fields()

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
        if "preferred_graph_variant_id" in vals or "preferred_graph_model" in vals:
            self._clear_stale_graph_fields()
        return res

    def _clear_stale_graph_fields(self):
        for pref in self:
            model = pref.preferred_graph_model or pref.blueprint_id.graph_model
            if not model or model not in self.env:
                continue
            Model = self.env[model]
            if pref.measure_field_id and pref.measure_field_id.name not in Model._fields:
                pref.measure_field_id = False
            stale = pref.groupby_ids.filtered(lambda f: f.name not in Model._fields)
            if stale:
                pref.groupby_ids = [(3, f.id) for f in stale]
