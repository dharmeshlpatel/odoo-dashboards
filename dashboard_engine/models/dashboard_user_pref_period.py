# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Per-Chart-Model-Option date filter rows on live user prefs (step 2)."""
from odoo import _, api, fields, models


class DashboardUserPrefPeriodLine(models.Model):
    """One live date-filter row (label + month/year picks) on a preference.

    Rows are rebuilt from the active Chart Model Option's ``date_filter_ids``
    (or blueprint Open/Closed fields when that list is empty). End users edit
    months and years; builders set which date fields appear and optional
    default months/years for first-time gear opens.
    """

    _name = "dashboard.user.pref.period.line"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard User Preference Date Filter Line"
    _order = "sequence, id"
    _rec_name = "label"

    pref_id = fields.Many2one(
        "dashboard.user.pref",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True, translate=True)
    field_name = fields.Char(
        string="Date Field Name",
        help="Technical date/datetime field on the active chart model.",
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Date Field",
        compute="_compute_field_id",
        inverse="_inverse_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
    )
    date_filter_id = fields.Many2one(
        "dashboard.blueprint.graph.variant.date.filter",
        string="Chart Model Date Filter",
        ondelete="set null",
        index=True,
    )
    period_mq_ids = fields.Many2many(
        "period.month.quarter",
        "dashboard_user_pref_period_line_mq_rel",
        "line_id",
        "period_mq_id",
        string="Months",
    )
    period_year_ids = fields.Many2many(
        "period.year",
        "dashboard_user_pref_period_line_year_rel",
        "line_id",
        "period_year_id",
        string="Years",
    )

    @api.depends("field_name", "pref_id.graph_model")
    def _compute_field_id(self):
        for rec in self:
            model = rec.pref_id.graph_model or (
                rec.pref_id.blueprint_id.graph_model if rec.pref_id.blueprint_id else False
            )
            rec.field_id = rec._mirror_field(model, rec.field_name)

    def _inverse_field_id(self):
        for rec in self:
            rec.field_name = rec.field_id.name or False

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_period_line_legacy_mirror"):
            if any(
                key in vals
                for key in (
                    "field_id",
                    "field_name",
                    "period_mq_ids",
                    "period_year_ids",
                    "sequence",
                    "label",
                )
            ):
                self.mapped("pref_id")._mirror_period_lines_to_legacy()
        return res


class DashboardUserPrefPeriod(models.Model):
    _inherit = "dashboard.user.pref"

    period_line_ids = fields.One2many(
        "dashboard.user.pref.period.line",
        "pref_id",
        string="Date Filters",
        copy=True,
        help="Date rows shown in the live gear for the active Chart Model. "
        "Rebuilt when the Chart Model Option changes.",
    )
    has_period_lines = fields.Boolean(compute="_compute_has_period_lines")

    _PERIOD_LEGACY_KEYS = (
        "period_field_id",
        "period_mq_ids",
        "period_year_ids",
        "period_closed_field_id",
        "period_closed_mq_ids",
        "period_closed_year_ids",
    )

    @api.depends("period_line_ids")
    def _compute_has_period_lines(self):
        for pref in self:
            pref.has_period_lines = bool(pref.period_line_ids)

    def _period_line_specs_from_active_option(self):
        """Specs for gear date rows: option list, else blueprint Open/Closed."""
        self.ensure_one()
        specs = []
        variant = False
        if hasattr(self, "_resolve_pref_graph_variant"):
            variant = self._resolve_pref_graph_variant()
        if variant and variant.date_filter_ids:
            seen = set()
            for row in variant.date_filter_ids.sorted("sequence"):
                name = row.field_name or (row.field_id.name if row.field_id else False)
                if not name or name in seen:
                    continue
                seen.add(name)
                specs.append(
                    {
                        "sequence": (len(specs) + 1) * 10,
                        "label": row.label
                        or (row.field_id.field_description if row.field_id else False)
                        or name
                        or _("Date"),
                        "field_name": name,
                        "field_id": row.field_id.id if row.field_id else False,
                        "date_filter_id": row.id,
                        "default_period_mq_ids": row.default_period_mq_ids.ids,
                        "default_period_year_ids": row.default_period_year_ids.ids,
                    }
                )
            return specs

        bp = self.blueprint_id
        if not bp:
            return specs
        for index, field in enumerate((bp.period_field_id, bp.closed_period_field_id)):
            if not field:
                continue
            default_label = (
                _("Creation Date") if index == 0 else _("Closed Date")
            )
            specs.append(
                {
                    "sequence": (index + 1) * 10,
                    "label": field.field_description or field.name or default_label,
                    "field_name": field.name,
                    "field_id": field.id,
                    "date_filter_id": False,
                    "default_period_mq_ids": [],
                    "default_period_year_ids": [],
                }
            )
        return specs

    def _sync_pref_period_lines(self, cache_only=False):
        """Rebuild date-filter lines from the active Chart Model Option.

        Keeps month/year picks when ``field_name`` matches an existing line.
        New rows seed from the builder defaults on the Chart Model date filter.
        """
        for pref in self:
            specs = pref._period_line_specs_from_active_option()
            by_name = {
                (line.field_name or ""): line
                for line in pref.period_line_ids
                if line.field_name
            }
            commands = [(5, 0, 0)]
            create_vals = []
            for spec in specs:
                name = spec.get("field_name") or ""
                old = by_name.get(name)
                if old:
                    mq_ids = old.period_mq_ids.ids
                    year_ids = old.period_year_ids.ids
                else:
                    mq_ids = list(spec.get("default_period_mq_ids") or [])
                    year_ids = list(spec.get("default_period_year_ids") or [])
                vals = {
                    "sequence": spec["sequence"],
                    "label": spec["label"],
                    "field_name": spec.get("field_name") or False,
                    "field_id": spec.get("field_id") or False,
                    "date_filter_id": spec.get("date_filter_id") or False,
                    "period_mq_ids": [(6, 0, mq_ids)],
                    "period_year_ids": [(6, 0, year_ids)],
                }
                if cache_only or not pref.ids:
                    commands.append((0, 0, vals))
                else:
                    vals["pref_id"] = pref.id
                    create_vals.append(vals)
            if cache_only or not pref.ids:
                pref.period_line_ids = commands
                pref._mirror_period_lines_to_legacy(cache_only=True)
            else:
                o2m = [(5, 0, 0)] + [
                    (
                        0,
                        0,
                        {
                            "sequence": vals["sequence"],
                            "label": vals["label"],
                            "field_name": vals.get("field_name") or False,
                            "field_id": vals.get("field_id") or False,
                            "date_filter_id": vals.get("date_filter_id") or False,
                            "period_mq_ids": vals["period_mq_ids"],
                            "period_year_ids": vals["period_year_ids"],
                        },
                    )
                    for vals in create_vals
                ]
                pref.with_context(skip_period_line_legacy_mirror=True).write(
                    {"period_line_ids": o2m}
                )
                pref._mirror_period_lines_to_legacy()

    def _mirror_period_lines_to_legacy(self, cache_only=False):
        """Copy lines[0]/lines[1] onto the legacy Open/Closed columns."""
        for pref in self:
            lines = pref.period_line_ids.sorted("sequence")
            open_line = lines[0] if len(lines) > 0 else False
            closed_line = lines[1] if len(lines) > 1 else False
            vals = {
                "period_field_id": open_line.field_id.id
                if open_line and open_line.field_id
                else False,
                "period_mq_ids": [(6, 0, open_line.period_mq_ids.ids if open_line else [])],
                "period_year_ids": [
                    (6, 0, open_line.period_year_ids.ids if open_line else [])
                ],
                "period_closed_field_id": closed_line.field_id.id
                if closed_line and closed_line.field_id
                else False,
                "period_closed_mq_ids": [
                    (6, 0, closed_line.period_mq_ids.ids if closed_line else [])
                ],
                "period_closed_year_ids": [
                    (6, 0, closed_line.period_year_ids.ids if closed_line else [])
                ],
            }
            if cache_only or not pref.ids:
                for key, value in vals.items():
                    pref[key] = value
            else:
                pref.with_context(
                    skip_period_line_lift=True,
                    skip_variant_graph_defaults=True,
                ).write(vals)

    def _lift_legacy_period_to_lines(self):
        """Build/update lines[0]/lines[1] from legacy Open/Closed columns."""
        Line = self.env["dashboard.user.pref.period.line"]
        for pref in self:
            specs = []
            if pref.period_field_id:
                specs.append(
                    {
                        "sequence": 10,
                        "label": pref.period_field_id.field_description
                        or pref.period_field_id.name
                        or _("Creation Date"),
                        "field_name": pref.period_field_id.name,
                        "field_id": pref.period_field_id.id,
                        "period_mq_ids": pref.period_mq_ids.ids,
                        "period_year_ids": pref.period_year_ids.ids,
                    }
                )
            if pref.period_closed_field_id:
                specs.append(
                    {
                        "sequence": 20,
                        "label": pref.period_closed_field_id.field_description
                        or pref.period_closed_field_id.name
                        or _("Closed Date"),
                        "field_name": pref.period_closed_field_id.name,
                        "field_id": pref.period_closed_field_id.id,
                        "period_mq_ids": pref.period_closed_mq_ids.ids,
                        "period_year_ids": pref.period_closed_year_ids.ids,
                    }
                )
            if not specs:
                if pref.period_line_ids:
                    pref.with_context(skip_period_line_legacy_mirror=True).write(
                        {"period_line_ids": [(5, 0, 0)]}
                    )
                continue
            # Prefer keeping extra lines (index >= 2) from option sync.
            keep_extra = pref.period_line_ids.sorted("sequence")[2:]
            commands = [(5, 0, 0)]
            for spec in specs:
                commands.append(
                    (
                        0,
                        0,
                        {
                            "sequence": spec["sequence"],
                            "label": spec["label"],
                            "field_name": spec["field_name"],
                            "field_id": spec["field_id"],
                            "period_mq_ids": [(6, 0, spec["period_mq_ids"])],
                            "period_year_ids": [(6, 0, spec["period_year_ids"])],
                        },
                    )
                )
            for extra in keep_extra:
                commands.append(
                    (
                        0,
                        0,
                        {
                            "sequence": extra.sequence,
                            "label": extra.label,
                            "field_name": extra.field_name,
                            "field_id": extra.field_id.id if extra.field_id else False,
                            "date_filter_id": extra.date_filter_id.id
                            if extra.date_filter_id
                            else False,
                            "period_mq_ids": [(6, 0, extra.period_mq_ids.ids)],
                            "period_year_ids": [(6, 0, extra.period_year_ids.ids)],
                        },
                    )
                )
            pref.with_context(skip_period_line_legacy_mirror=True).write(
                {"period_line_ids": commands}
            )
            # Touch Line create path when write O2M is flaky on NewId — for
            # real ids the command above is enough.
            if not pref.period_line_ids and pref.ids:
                Line.with_context(skip_period_line_legacy_mirror=True).create(
                    [
                        {
                            "pref_id": pref.id,
                            "sequence": spec["sequence"],
                            "label": spec["label"],
                            "field_name": spec["field_name"],
                            "field_id": spec["field_id"],
                            "period_mq_ids": [(6, 0, spec["period_mq_ids"])],
                            "period_year_ids": [(6, 0, spec["period_year_ids"])],
                        }
                        for spec in specs
                    ]
                )

    def _period_domain(self):
        """Date ranges from dynamic period lines (fallback: legacy two slots)."""
        self.ensure_one()
        lines = self.period_line_ids.sorted("sequence")
        ranges = []
        if lines:
            for line in lines:
                ranges += self._period_ranges(
                    line.field_id, line.period_mq_ids, line.period_year_ids
                )
        else:
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for pref in records.filtered(lambda p: not p.period_line_ids):
            # Prefer option/blueprint specs (incl. builder default months/years).
            # Lifting empty legacy Open/Closed first would create blank lines and
            # block those defaults on the following sync.
            if pref._period_line_specs_from_active_option():
                pref._sync_pref_period_lines()
            elif pref.period_field_id or pref.period_closed_field_id:
                pref._lift_legacy_period_to_lines()
                if not pref.period_line_ids:
                    pref._sync_pref_period_lines()
        return records

    def write(self, vals):
        vals = dict(vals)
        legacy_touched = any(k in vals for k in self._PERIOD_LEGACY_KEYS)
        lines_touched = "period_line_ids" in vals
        res = super().write(vals)
        if (
            legacy_touched
            and not lines_touched
            and not self.env.context.get("skip_period_line_lift")
        ):
            self._lift_legacy_period_to_lines()
        if lines_touched and not self.env.context.get("skip_period_line_legacy_mirror"):
            self._mirror_period_lines_to_legacy()
        return res
