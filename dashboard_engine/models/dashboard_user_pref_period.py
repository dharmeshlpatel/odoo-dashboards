# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Per-Chart-Model-Option date filter rows on live user prefs (step 2)."""
import json

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
    # Not required: the gear list marks Label readonly, so OWL treats empty
    # Label as invalid and skips the parent onchange that fills Custom Filter.
    label = fields.Char(translate=True, default="Date")
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

    def _current_period_year(self):
        return self.env["period.year"].search([("name", "=", "year")], limit=1)

    def _default_label_from_vals(self, vals):
        """Fill Label when the gear saves a line without sending the readonly field."""
        label = (vals.get("label") or "").strip() if isinstance(vals.get("label"), str) else vals.get("label")
        if label:
            return label
        field = self.env["ir.model.fields"].browse(vals.get("field_id") or [])
        if field:
            return field.field_description or field.name or _("Date")
        return vals.get("field_name") or _("Date")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("label"):
                vals["label"] = self._default_label_from_vals(vals)
        return super().create(vals_list)

    def _sync_period_mq_year(self, vals):
        """Months need a year; clearing years also clears months (v1 gear)."""
        if self.env.context.get("skip_period_line_mq_year_sync"):
            return
        for rec in self:
            year_cleared = "period_year_ids" in vals and not rec.period_year_ids
            months_touched = "period_mq_ids" in vals
            if year_cleared and not months_touched:
                if rec.period_mq_ids:
                    rec.with_context(
                        skip_period_line_mq_year_sync=True,
                    ).write({"period_mq_ids": [(6, 0, [])]})
                continue
            if rec.period_mq_ids and not rec.period_year_ids:
                year = rec._current_period_year()
                if year:
                    rec.with_context(
                        skip_period_line_mq_year_sync=True,
                    ).write({"period_year_ids": [(6, 0, year.ids)]})

    @api.onchange("period_mq_ids")
    def _onchange_period_mq_ids(self):
        if self.period_mq_ids and not self.period_year_ids:
            year = self._current_period_year()
            if year:
                self.period_year_ids = year
        self._onchange_sync_pref_custom_filter()

    @api.onchange("period_year_ids")
    def _onchange_period_year_ids(self):
        if not self.period_year_ids:
            self.period_mq_ids = False
        self._onchange_sync_pref_custom_filter()

    def _onchange_sync_pref_custom_filter(self):
        """v1 gear: month/year picks rewrite Custom Filter from date ranges."""
        for rec in self:
            pref = rec.pref_id
            if pref:
                pref.custom_filter = pref._custom_filter_char_from_periods()

    def write(self, vals):
        res = super().write(vals)
        self._sync_period_mq_year(vals)
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
                prefs = self.mapped("pref_id")
                prefs._mirror_period_lines_to_legacy()
                if any(k in vals for k in ("period_mq_ids", "period_year_ids")):
                    prefs._sync_custom_filter_from_periods()
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
                    "label": spec["label"] or spec.get("field_name") or _("Date"),
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
                            "label": extra.label or extra.field_name or _("Date"),
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

    def _period_mq_years(self, mq_ids, year_ids):
        """v1: months without a year use the current year for the date domain."""
        if mq_ids and not year_ids:
            year_ids = self.env["period.year"].search([("name", "=", "year")], limit=1)
        return mq_ids, year_ids

    def _collect_period_ranges(self):
        """Raw per-period AND domains (one list per month/year range)."""
        self.ensure_one()
        lines = self.period_line_ids.sorted("sequence")
        ranges = []
        if lines:
            for line in lines:
                mq_ids, year_ids = self._period_mq_years(
                    line.period_mq_ids, line.period_year_ids
                )
                ranges += self._period_ranges(line.field_id, mq_ids, year_ids)
        else:
            mq_ids, year_ids = self._period_mq_years(
                self.period_mq_ids, self.period_year_ids
            )
            ranges = self._period_ranges(self.period_field_id, mq_ids, year_ids)
            closed_mq, closed_year = self._period_mq_years(
                self.period_closed_mq_ids, self.period_closed_year_ids
            )
            ranges += self._period_ranges(
                self.period_closed_field_id, closed_mq, closed_year
            )
        return ranges

    def _combine_period_ranges(self, ranges, operator):
        ranges = [rng for rng in (ranges or []) if rng]
        if not ranges:
            return []
        op = operator or "any"
        combine = fields.Domain.AND if op == "all" else fields.Domain.OR
        return list(combine(ranges))

    def _range_metas(self, ranges):
        """Field + start/end for each month/year range (gear Domain.or)."""
        metas = []
        for rng in ranges or []:
            leaves = [
                item
                for item in rng
                if isinstance(item, (list, tuple)) and len(item) >= 3
            ]
            start = next((item for item in leaves if item[1] == ">="), None)
            end = next((item for item in leaves if item[1] == "<="), None)
            if start and end:
                metas.append(
                    {
                        "field": start[0],
                        "start": start[2],
                        "end": end[2],
                    }
                )
        return metas

    def _period_domain(self):
        """Date ranges from dynamic period lines (fallback: legacy two slots)."""
        self.ensure_one()
        return self._combine_period_ranges(
            self._collect_period_ranges(), self.period_operator
        )

    def _domain_to_char(self, domain):
        """Odoo debug-domain string (quoted operators + tuples for leaves)."""
        chunks = []
        for item in list(domain or []):
            if isinstance(item, str):
                chunks.append(json.dumps(item))
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                chunks.append(
                    "(%s, %s, %s)"
                    % (
                        json.dumps(item[0]),
                        json.dumps(item[1]),
                        json.dumps(item[2]),
                    )
                )
            else:
                chunks.append(json.dumps(item))
        return "[%s]" % ", ".join(chunks) if chunks else "[]"

    def _custom_filter_char_from_periods(self):
        """Serialize live month/year ranges the way v1 wrote graph custom filter."""
        self.ensure_one()
        return self._domain_to_char(
            self._combine_period_ranges(
                self._collect_period_ranges(),
                self.period_operator,
            )
        )

    def _collect_period_ranges_from_picks(self, picks):
        """Raw per-period AND domains from live gear month/year tags."""
        self.ensure_one()
        ranges = []
        lines = {line.id: line for line in self.period_line_ids}
        graph_model = self.graph_model or (
            self.blueprint_id.graph_model if self.blueprint_id else False
        )
        Fields = self.env["ir.model.fields"]
        Mq = self.env["period.month.quarter"]
        Year = self.env["period.year"]
        for pick in picks or []:
            line = lines.get(pick.get("id") or 0)
            field = line.field_id if line else False
            field_name = pick.get("field_name") or (
                line.field_name if line else False
            )
            if not field and field_name and graph_model:
                field = Fields.search(
                    [("model", "=", graph_model), ("name", "=", field_name)],
                    limit=1,
                )
            mq_ids, year_ids = self._period_mq_years(
                Mq.browse(pick.get("period_mq_ids") or []),
                Year.browse(pick.get("period_year_ids") or []),
            )
            ranges += self._period_ranges(field, mq_ids, year_ids)
        return ranges

    def _period_domain_from_picks(self, picks, operator=None):
        """Build the v1 date domain from live gear month/year picks (unsaved)."""
        self.ensure_one()
        return self._combine_period_ranges(
            self._collect_period_ranges_from_picks(picks),
            operator or self.period_operator or "any",
        )

    def web_custom_filter_from_period_picks(self, picks, operator=None):
        """Live gear: rewrite Custom Filter from month/year tags (same as v1)."""
        self.ensure_one()
        op = operator or self.period_operator or "any"
        ranges = self._collect_period_ranges_from_picks(picks)
        return {
            "operator": op,
            "ranges": self._range_metas(ranges),
            "domain": self._domain_to_char(self._combine_period_ranges(ranges, op)),
        }

    def _sync_custom_filter_from_periods(self):
        if self.env.context.get("skip_custom_filter_from_periods"):
            return
        for pref in self:
            value = pref._custom_filter_char_from_periods()
            if pref.custom_filter != value:
                pref.with_context(skip_custom_filter_from_periods=True).write(
                    {"custom_filter": value}
                )

    @api.onchange("period_line_ids", "period_operator")
    def _onchange_period_operator_custom_filter(self):
        for pref in self:
            pref.custom_filter = pref._custom_filter_char_from_periods()

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
        if (
            not self.env.context.get("skip_custom_filter_from_periods")
            and (
                lines_touched
                or "period_operator" in vals
                or (
                    legacy_touched
                    and any(
                        k in vals
                        for k in (
                            "period_mq_ids",
                            "period_year_ids",
                            "period_closed_mq_ids",
                            "period_closed_year_ids",
                            "period_operator",
                        )
                    )
                )
            )
        ):
            self._sync_custom_filter_from_periods()
        return res
