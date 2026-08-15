# -*- coding: utf-8 -*-

from odoo import models, api, fields, tools

# Supported date grouping options for dashboard graphs
GRAPH_CUSTOM_GROUP = ["day", "week", "month", "quarter", "year"]


class IrModelFields(models.Model):
    _inherit = "ir.model.fields"

    """
    Extension of `ir.model.fields` to support dynamic date-based
    virtual fields (day, week, month, quarter, year) for dashboards.

    These virtual fields are generated automatically for every
    date/datetime field of configured dashboard models and are used
    exclusively for graph group-by operations.
    """

    def _date_field_types(self):
        """
        Return supported date field types eligible for dashboard grouping.

        Only these field types will be used to generate
        virtual date-period group-by fields.

        :return: tuple of supported date field types
        """
        return ("date", "datetime")

    @api.model
    def is_dashboard_date_period_name(self, name):
        """True when ``name`` matches ``x_<date_field>_<period>``."""
        if not name or not isinstance(name, str) or not name.startswith("x_"):
            return False
        try:
            _date_field, group = name[2:].rsplit("_", 1)
        except ValueError:
            return False
        return group in GRAPH_CUSTOM_GROUP

    def _with_period_fields_visible(self):
        """Internal lookups must see period tags even on Advanced forms."""
        return self.with_context(dashboard_hide_date_period_fields=False)

    @api.model
    def _dashboard_date_period_candidate_domain(self, model_name=None):
        """Broad domain for virtual period-tag candidates (refined in Python)."""
        domain = [
            ("store", "=", False),
            ("readonly", "=", True),
            ("ttype", "=", "char"),
            ("name", "=like", "x_%"),
        ]
        if model_name:
            domain.append(("model", "=", model_name))
        return domain

    @api.model
    @tools.ormcache("model_name")
    def _dashboard_date_period_names(self, model_name):
        """Cached technical names of period tags on ``model_name``."""
        if not model_name:
            return ()
        candidates = (
            self.sudo()
            ._with_period_fields_visible()
            .search(self._dashboard_date_period_candidate_domain(model_name))
        )
        return tuple(f.name for f in candidates if f.is_date_period())

    @api.model
    @tools.ormcache()
    def _all_dashboard_date_period_ids(self):
        """Cached ids of all dashboard period tags (for Advanced picker hide)."""
        candidates = (
            self.sudo()
            ._with_period_fields_visible()
            .search(self._dashboard_date_period_candidate_domain())
        )
        return tuple(f.id for f in candidates if f.is_date_period())

    def _invalidate_dashboard_date_period_cache(self):
        self.env.registry.clear_cache()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        """Hide period tags from field pickers unless Group By opts back in.

        Studio / Advanced forms pass ``dashboard_hide_date_period_fields``.
        Group By widgets set that flag to False so period tags stay available.
        """
        if self.env.context.get("dashboard_hide_date_period_fields"):
            period_ids = self._all_dashboard_date_period_ids()
            if period_ids:
                domain = list(
                    fields.Domain(domain or [])
                    & fields.Domain("id", "not in", period_ids)
                )
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    def _get_origin_field(self):
        """
        Resolve the original date/datetime field for a virtual
        dashboard date-period field.

        Virtual fields follow the naming convention:
            x_<date_field>_<period>

        This helper extracts the original date field name,
        validates its existence and type, and returns the
        corresponding `ir.model.fields` record.

        :return: ir.model.fields record or empty recordset
        """
        self.ensure_one()
        try:
            # Virtual fields are expected to start with 'x_'
            if self.name.startswith("x_"):
                name_clean = self.name.split("x_")[1]
                date_field, group = name_clean.rsplit("_", 1)
                # Locate the original date/datetime field on the same model
                field = self.search(
                    [
                        ("name", "=", date_field),
                        ("model_id", "=", self.model_id.id),
                        ("ttype", "in", self._date_field_types()),
                    ]
                )
                return field or self.env["ir.model.fields"]
        except IndexError:
            # Malformed field name → treat as non-date-period field
            return self.env["ir.model.fields"]

    def is_date_period(self):
        """
        Check whether this field represents a dashboard date-period field.

        A field is considered a date-period field if it can be
        successfully resolved to an original date/datetime field.

        :return: True if linked to a date/datetime field, else False
        """
        self.ensure_one()
        return bool(self._get_origin_field())

    def get_date_period(self):
        """
        Return the date-period expression for this virtual field.

        Prefer ``ir.default`` (``<date_field>:<period>``); fall back to
        parsing the virtual name ``x_<date_field>_<period>`` so group-by
        works even before defaults are seeded.

        :return: default value string or empty string
        """
        self.ensure_one()
        origin = self._get_origin_field()
        if not origin:
            return ""
        IrDefault = self.env["ir.default"].sudo()
        default_value = IrDefault._get(
            model_name=self.model_id.model,
            field_name=self.name,
            company_id=self.env.company.id,
        )
        if default_value:
            return default_value
        try:
            name_clean = self.name[2:] if self.name.startswith("x_") else self.name
            date_field, group = name_clean.rsplit("_", 1)
        except ValueError:
            return ""
        if group in GRAPH_CUSTOM_GROUP and date_field == origin.name:
            return "%s:%s" % (date_field, group)
        return ""

    @api.model
    def ensure_date_period_fields(self, model_name):
        """Create missing ``x_<date>_<period>`` virtual fields for a model.

        Registers the model in ``dashboard.graph_parameter`` (so later
        date-field creates keep spawning virtual siblings) then builds any
        missing day/week/month/quarter/year tags — same as v1, but driven
        by whatever date fields the model has right now.
        """
        if not model_name or model_name not in self.env:
            return self.browse()
        self.env["dashboard.graph_parameter"].set_param(model_name)
        vals = self._get_date_field_values_from_field(model_name)
        if not vals:
            return self.browse()
        created = self.sudo().create(vals)
        self._set_company_defaults(model_name, created)
        if created:
            self._invalidate_dashboard_date_period_cache()
        return created

    @api.model
    def period_field_for(self, model_name, date_field_name, period="month"):
        """Return the virtual ``x_<date>_<period>`` field, creating siblings first."""
        if (
            not model_name
            or not date_field_name
            or period not in GRAPH_CUSTOM_GROUP
        ):
            return self.browse()
        self.ensure_date_period_fields(model_name)
        return self._with_period_fields_visible().search(
            [
                ("model", "=", model_name),
                ("name", "=", "x_%s_%s" % (date_field_name, period)),
                ("store", "=", False),
            ],
            limit=1,
        )

    @api.model
    def dashboard_groupby_allowed_fields(self, model_name):
        """``ir.model.fields`` allowed in Group By pickers (v1 rules, dynamic).

        - Stored non-date fields (except ``id``)
        - Virtual ``x_<date>_<period>`` tags for every date/datetime field
        - Raw date/datetime fields are excluded (pick a period tag instead)
        """
        if not model_name or model_name not in self.env:
            return self.browse()
        self.ensure_date_period_fields(model_name)
        # Advanced form sets dashboard_hide_date_period_fields; Group By must
        # still resolve the virtual period tags.
        candidates = self._with_period_fields_visible().search(
            [
                ("model", "=", model_name),
                (
                    "ttype",
                    "in",
                    [
                        "boolean",
                        "char",
                        "float",
                        "integer",
                        "monetary",
                        "many2one",
                        "selection",
                        "date",
                        "datetime",
                    ],
                ),
            ]
        )
        allowed = self.browse()
        for field in candidates:
            if field.is_date_period():
                allowed |= field
                continue
            if field.ttype in self._date_field_types():
                continue
            if field.store and field.name != "id":
                allowed |= field
        return allowed

    @api.model
    def dashboard_graph_measure_fields(self, model_name):
        """``ir.model.fields`` allowed in Measure pickers.

        Same list as the model's standard graph Measures menu: numeric fields
        with an aggregator, minus ``id`` and graph-arch ``invisible`` fields.
        Count (``__count``) is not a field — leave the picker empty to count.
        """
        if not model_name or model_name not in self.env:
            return self.browse()
        names = self.env["base.dashboard.config.mixin"]._graph_measure_names_for_model(
            model_name
        )
        if not names:
            return self.browse()
        return self.search([("model", "=", model_name), ("name", "in", names)])

    def dashboard_graph_aggregator(self):
        """Aggregator the standard graph uses for this field (usually sum)."""
        self.ensure_one()
        if not self.model or self.model not in self.env:
            return "sum"
        meta = self.env[self.model].fields_get([self.name]).get(self.name) or {}
        return meta.get("aggregator") or "sum"

    def _get_date_field_values_from_field(self, model):
        """
        Build virtual dashboard date-period fields for all
        date/datetime fields of a given model.

        For each eligible base field, this method generates
        non-stored, read-only virtual fields corresponding
        to supported date periods.

        :param model: technical model name
        :return: list of field value dictionaries
        """
        # Collect all date/datetime fields of the given model
        fields = self.search(
            [("model", "=", model), ("ttype", "in", self._date_field_types())]
        )
        result = []
        for f in fields:
            result.extend(self._get_date_field_values(f))
        return result

    def _get_date_field_values(self, field):
        """
        Build virtual dashboard date-period fields for a single
        date/datetime field.

        One virtual field is generated per supported date group
        (day, week, month, quarter, year), unless it already exists.

        :param field: ir.model.fields record
        :return: list of field value dictionaries
        """
        values = []
        model = field.model

        # Generate one virtual field per supported date group
        for group in GRAPH_CUSTOM_GROUP:
            name = f"x_{field.name}_{group}"

            # Skip creation if the virtual field already exists
            if self.search_count(
                [
                    ("name", "=", name),
                    ("model_id", "=", field.model_id.id),
                    ("store", "=", False),
                ]
            ):
                continue

            values.append(
                {
                    "name": name,
                    "field_description": f"{field.field_description} > {group.title()}",
                    "model": model,
                    "model_id": field.model_id.id,
                    "ttype": "char",
                    "store": False,
                    "readonly": True,
                }
            )
        return values

    def _set_company_defaults(self, model, fields):
        """
        Set default date-period values for all companies.

        This method assigns a default `<date_field>:<period>`
        expression for each generated virtual date-period field
        using `ir.default`, ensuring consistent behavior
        across companies.

        :param model: technical model name
        :param fields: recordset of generated virtual fields
        """
        IrDefault = self.env["ir.default"]
        companies = self.env["res.company"].search([])

        # Apply defaults for every company in the system
        for field in fields:
            name_clean = field.name.split("x_")[1]
            date_field, group = name_clean.rsplit("_", 1)
            default_value = f"{date_field}:{group}"

            for company in companies:
                IrDefault.set(
                    model_name=model,
                    field_name=field.name,
                    value=default_value,
                    company_id=company.id,
                )

    def get_domain(self, field):
        """
        Build the domain used to locate virtual dashboard
        date-period fields for a given base field.

        :param field: ir.model.fields record
        :return: domain list usable in ORM searches
        """
        patterns = [f"x_{field.name}_{group}" for group in GRAPH_CUSTOM_GROUP]
        return [
            ("model", "=", field.model),
            ("name", "in", patterns),
            ("store", "=", False),
            ("readonly", "=", True),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create model fields and automatically generate
        related dashboard date-period fields when applicable.

        For each newly created date/datetime field belonging
        to a configured dashboard model, corresponding
        virtual date-period fields are generated and
        default values are assigned per company.
        """
        # Retrieve models configured for dashboard graph support
        fields = super(IrModelFields, self).create(vals_list)
        if any(f.is_date_period() for f in fields):
            self._invalidate_dashboard_date_period_cache()
        graph_models = self.env["dashboard.graph_parameter"].get_param()
        if graph_models:
            for field in fields:
                # Only generate virtual fields for date/datetime fields
                if (
                    field.ttype in ("date", "datetime")
                    and field.model in graph_models
                ):
                    new_fields_vals = self._get_date_field_values(field)
                    field_ids = self.sudo().create(new_fields_vals)
                    self._set_company_defaults(field.model, field_ids)
        return fields

    def write(self, vals):
        """
        Handle field type changes and maintain related
        dashboard date-period virtual fields.

        This method ensures that:
            - Virtual fields are removed when a base field
              stops being date/datetime
            - Virtual fields are created when a base field
              becomes date/datetime
        """
        old_fields = {rec.id: rec.ttype for rec in self}

        res = super().write(vals)

        for field in self:
            old_type = old_fields.get(field.id)
            new_type = field.ttype

            if old_type in ("date", "datetime") and new_type not in (
                "date",
                "datetime",
            ):
                # Remove virtual fields if base field is no longer date-based
                self.search(self.get_domain(field)).unlink()

            if old_type not in ("date", "datetime") and new_type in (
                "date",
                "datetime",
            ):
                # Create virtual fields if base field becomes date-based
                self.create(self._get_date_field_values(field))

        return res

    def unlink(self):
        """
        Ensure related dashboard date-period fields are
        cleaned up when base date fields are removed.

        This prevents orphaned virtual fields and keeps
        the schema consistent.
        """
        if not self.env.context.get("allow_unlink"):
            # Recursively remove related virtual fields first
            for field in self.filtered(
                lambda x: x.ttype in ("date", "datetime")
            ):
                self.search(self.get_domain(field)).with_context(
                    allow_unlink=True
                ).unlink()
        drop_period_cache = any(f.is_date_period() for f in self)
        res = super().unlink()
        if drop_period_cache:
            self._invalidate_dashboard_date_period_cache()
        return res
