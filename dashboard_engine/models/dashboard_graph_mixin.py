# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api, _
from collections import defaultdict
from babel.dates import format_date
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.tools import Query
from odoo.tools.safe_eval import safe_eval
from odoo.tools import safe_eval as safe_eval_mod

_logger = logging.getLogger(__name__)

MAX_RECORDS = 6


class BaseDashboardGraphMixin(models.AbstractModel):
    """
    High-level dashboard graph mixin responsible for:

    - Graph data computation
    - Dataset formatting
    - Label localization
    - Chart type resolution
    - UI-ready payload generation

    SQL generation is delegated to DashboardGraphSQLMixin.
    """

    _name = "base.dashboard.graph.mixin"
    _inherit = ["base.dashboard.graph.sql.mixin"]
    _description = "Graph Data"

    color = fields.Integer(
        string="Color Index", help="The color of the customer"
    )
    dashboard_button_name = fields.Char(
        string="Dashboard Button", compute="_compute_dashboard_button_name"
    )
    # dashboard_graph_data / dashboard_graph_type are declared on ``base`` so
    # that any configured host model carries them without a static _inherit.
    # See models/base.py; redeclaring them here would shadow that definition.
    currency_id = fields.Many2one(
        "res.currency",
        compute="_get_company_currency",
        readonly=True,
        string="Currency",
        help="Utility field to express amount currency",
    )

    def _run_grouped_query(
        self,
        *,
        domain,
        groupby,
        aggregates,
        propagate_to,
        count_field,
        amount_field=None,
    ):
        """
        Execute a grouped query on crm.lead and propagate results.
        """
        grouped_data = self.env[self._get_graph_model()].formatted_read_group(
            domain=domain,
            groupby=[groupby],
            aggregates=aggregates,
        )

        self._propagate_grouped_result(
            grouped_data,
            groupby,
            count_field,
            amount_field,
        )

    def _propagate_grouped_result(
        self,
        grouped_data,
        field,
        count_field,
        amount_field=None,
    ):
        """
        Propagate grouped read_group results to parent records.

        :param grouped_data: result of formatted_read_group
        :param field: grouping field name
        :param count_field: destination count field on record
        :param amount_field: optional destination amount field
        """
        aggregate_spec = self._get_aggregate_spec()
        # Pre-compute ID set for O(1) membership checks instead of
        # O(N) ``record in self`` on each iteration.
        self_ids = set(self.ids)
        seen_ids = set()

        for group in grouped_data:
            group_key = group.get(field)
            if not group_key:
                continue
            record = self.browse(group_key[0])
            while record:
                if record.id in self_ids:
                    record[count_field] += group.get("__count", 0)

                    if amount_field and aggregate_spec:
                        record[amount_field] += group.get(aggregate_spec, 0)

                    seen_ids.add(record.id)
                record = record.parent_id

        # Zero-fill records not touched by any group
        for record in self.browse(list(self_ids - seen_ids)):
            record[count_field] = 0
            if amount_field:
                record[amount_field] = 0

    def action_primary_button(self):
        """
        Placeholder action for the primary dashboard button.

        This method is intended to be overridden by specific
        dashboard implementations.
        """
        return False

    def _graph_key(self):
        """
        Return a list containing the graph key.

        The key is used for lineCharts to have the on-hover label.
        """
        return dict(self.env.user._get_graph_measures()).get(
            self.env.user._get_graph_measure()
        )

    def _get_dashboard_user_filter_context_map(self):
        """
        Define dashboard application context keys used for user-based graph filtering.

        This method returns a mapping of context flags (e.g. `in_crm_customer_app`,
        `in_sales_customer_app`) that indicate which application is currently active
        in the dashboard environment.

        The returned keys are used to:
        - Detect the active dashboard application
        - Decide whether user-based filtering should be applied
        - Enable downstream SQL conditions via `_extra_sql_conditions`

        The base implementation returns an empty mapping and is intended
        to be extended by application-specific modules (CRM, Sales, POS,
        Website, etc.) without modifying core dashboard logic.
        """
        return {}

    def _compute_dashboard_button_name(self):
        """
        Compute the dashboard button label for the customer.

        This method can be overridden by dashboard-specific modules
        to provide contextual button labels.
        """
        self.dashboard_button_name = (
            self.env.user._get_graph_primary_button_title()
        )

    def _get_company_currency(self):
        """
        Compute the currency based on the record company.

        Falls back to the current environment company currency
        if no company is set on the record.
        """
        for record in self:
            if getattr(record.sudo(), "company_id"):
                record.currency_id = record.sudo().company_id.currency_id
            else:
                record.currency_id = self.env.company.currency_id

    def _compute_dashboard_graph(self):
        """
        Computes and stores dashboard graph data and type for each record.
        """
        in_apps = self.env.context.get("initializer")
        if in_apps:
            self = self.with_context(dashboard_rendering=True)
        for record in self:
            record.dashboard_graph_data = False
            record.dashboard_graph_type = False
            if in_apps:
                record_wise_graph_data = record.with_context(
                    dashboard_rendering=True
                )._get_graph()
                if (
                    not record_wise_graph_data
                    or record.id not in record_wise_graph_data
                ):
                    continue
                graph_data = record_wise_graph_data[record.id]
                if (
                    not graph_data
                    or "values" not in graph_data[0]
                    or not graph_data[0]["values"]
                ):
                    continue
                record.dashboard_graph_data = json.dumps(graph_data)
                record.dashboard_graph_type = graph_data[0]["type"]

    def _get_graph_type(self, records):
        """
        Determines the chart type (line/bar) based on record count.
        """
        if len(records) > (MAX_RECORDS - 1):
            graph_type = "line"
        else:
            graph_type = "bar"
        return graph_type

    def _get_where_clause(self, model):
        """
        Returns the SQL where clause for the dashboard graph custom filter.
        """
        my_data_domain = []
        custom_domain = self.env.user._get_graph_custom_filter()
        data_scope_domain = self.env.user._get_graph_data_scope_domain()
        graph_my_data_field = self.env.user._get_graph_my_data_field()
        if graph_my_data_field:
            if getattr(self.env.user, graph_my_data_field, False):
                my_data_domain = self._get_my_data_domain()
        domain = fields.Domain.AND(
            [data_scope_domain, custom_domain, my_data_domain]
        )
        return model._search(domain).where_clause

    def _graph_data(self):
        """
        Executes the dashboard graph SQL query and returns the result as a list of dicts.
        """
        # Gather metadata and context
        data_field = self.env.user._get_graph_data_field()
        if not data_field:
            return []
        query_context = self._prepare_query_context(data_field)
        field_condition = self._build_field_condition(data_field)
        # Build base query
        query = self._build_graph_query(query_context, field_condition)
        # Prepare query parameters
        query_parameters = self._prepare_query_parameters(query_context)
        self.env.cr.execute(query, query_parameters)
        return self.env.cr.dictfetchall()

    def _get_graph(self):
        """
        Formats and returns the dashboard graph data for this record, including
        chart labels and formatting for UI consumption.
        """

        def format_chart_data(raw_data, chart_type):
            """
            Formats raw chart data by renaming the keys according to the chart
            type.
            For a 'line' chart:
                - 'x_field' becomes 'x'
                - 'y_field' becomes 'y'
            For all other chart types (e.g., 'bar', 'line'):
                - 'x_field' becomes 'label'
                - 'y_field' becomes 'value'
            Parameters:
                raw_data (list): A list of dictionaries with keys 'x_field' and
                'y_field'.
                chart_type (str): The type of chart to be rendered (e.g., 'line',
                'bar').
            Returns:
                list: A list of dictionaries with renamed keys suitable for the
                given chart type.
            """
            x_key = "x" if chart_type == "line" else "label"
            y_key = "y" if chart_type == "line" else "value"
            formatted_data = []
            for record in raw_data:
                data = {
                    x_key: str(record.get("x_field")),
                    y_key: record.get("y_field"),
                }
                if "group_names" in record:
                    data["group_names"] = record["group_names"]
                if "group_color_keys" in record:
                    data["group_color_keys"] = record["group_color_keys"]
                if "domains" in record:
                    data["domains"] = record["domains"]
                if "x_domain" in record:
                    data["x_domain"] = record["x_domain"]
                formatted_data.append(data)
            return formatted_data

        def get_week_name(start_date, locale):
            """Generates a week name (string) from a datetime according to the
            locale:
            If it's the current week, returns "This Week"
            Else, return Odoo standard week format "Ww YYYY"
            """
            today = datetime.today().date()
            start_of_this_week = today - relativedelta(days=today.weekday())
            end_of_this_week = start_of_this_week + relativedelta(days=6)

            # Format the week string using Odoo standard pattern
            week_label = format_date(start_date, "'W'w YYYY", locale=locale)

            if start_of_this_week <= start_date.date() <= end_of_this_week:
                return _("This Week")

            return week_label

        self.ensure_one()
        today = datetime.today().date()
        locale = self.env.context.get("lang") or "en_US"
        dashboard_graph_groups = self.env.user._get_graph_groupby()
        primary_field = dashboard_graph_groups[:1]
        GraphModel = self.env[self._get_graph_model()]
        graph_data = self._graph_data()
        datasets = defaultdict(
            lambda: {
                "x_field": None,
                "y_field": [],
                "group_names": [],
                "group_color_keys": [],
            }
        )
        from dateutil.relativedelta import relativedelta
        import pytz
        from odoo.fields import Datetime

        def _get_date_domain(f_record, group, year, period):
            f_name = f_record.name
            if not year and not period:
                return [(f_name, "=", False)]

            # Extract base field if it's a date period field
            date_field_name = f_name
            if f_record.is_date_period():
                date_field_name = f_record.get_date_period().split(":")[0]

            try:
                y = int(year) if year else datetime.now().year
                if group == "year":
                    start = datetime(y, 1, 1)
                    end = start + relativedelta(years=1)
                elif group == "month":
                    p = int(period) if period else 1
                    start = datetime(y, p, 1)
                    end = start + relativedelta(months=1)
                elif group == "quarter":
                    if isinstance(period, str) and period.startswith("Q"):
                        p = int(period.split()[0].replace("Q", ""))
                    else:
                        p = int(period) if period else 1
                    start = datetime(y, (p - 1) * 3 + 1, 1)
                    end = start + relativedelta(months=3)
                elif group == "week":
                    p = int(period) if period else 1
                    week_str = f"{y}-W{p:02d}-1"
                    start = datetime.strptime(week_str, "%G-W%V-%u")
                    end = start + relativedelta(days=7)
                elif group == "day":
                    start = datetime.strptime(str(period), "%Y-%m-%d")
                    end = start + relativedelta(days=1)
                else:
                    return []

                # Handle Timezone for Datetime fields (Odoo standard)
                base_field = self.env[self._get_graph_model()]._fields.get(
                    date_field_name
                )

                if base_field and base_field.type == "datetime":
                    user_tz = pytz.timezone(
                        self.env.context.get("tz") or "UTC"
                    )
                    # Convert Local boundaries to UTC for the ORM domain
                    start_utc = user_tz.localize(start).astimezone(pytz.utc)
                    end_utc = user_tz.localize(end).astimezone(pytz.utc)
                    start_str = start_utc.strftime("%Y-%m-%d %H:%M:%S")
                    end_str = end_utc.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # For Date fields, just use YYYY-MM-DD
                    start_str = start.strftime("%Y-%m-%d")
                    end_str = end.strftime("%Y-%m-%d")

                return [
                    "&",
                    (date_field_name, ">=", start_str),
                    (date_field_name, "<", end_str),
                ]
            except Exception:
                return []

        # First pass: identify all unique secondary groups (series) and their display names
        series_map = {}  # tuple of secondary values -> {group_name, color_key}
        x_axis_data = defaultdict(dict)  # x_val -> {series_key -> y_val}
        x_field_labels = {}  # x_val -> display_label
        x_date_params = {}  # x_val -> {year, period}

        for item in graph_data:
            x_val = item["x"]
            y_val = item["y"]

            # Build display label for X-axis if not already done
            if x_val not in x_field_labels:
                # Reuse the existing formatting logic to get x_field_labels[x_val]
                # (Extracted from original logic)
                label = str(x_val) if x_val is not False else _("None")
                if primary_field.is_date_period():
                    date_field, group = primary_field.get_date_period().split(
                        ":"
                    )
                    year_alias = f"{date_field}_year"
                    year = item.get(year_alias)
                    period = x_val
                    if period and year:
                        if group == "month":
                            date_obj = datetime(int(year), int(period), 1)
                            is_this_month = (
                                int(year) == today.year
                                and int(period) == today.month
                            )
                            month_label = format_date(
                                date_obj, "MMMM yyyy", locale=locale
                            )
                            label = (
                                _("This Month")
                                if is_this_month
                                else month_label
                            )
                        elif group == "quarter":
                            current_q = (today.month - 1) // 3 + 1
                            this_q_label = f"Q{current_q} {today.year}"
                            label = (
                                _("This Quarter")
                                if period == this_q_label
                                else period
                            )
                        elif group == "week":
                            week_value = f"{int(year)}-W{int(period):02d}"
                            week_start = datetime.strptime(
                                week_value + "-1", "%G-W%V-%u"
                            )
                            label = get_week_name(week_start, locale)
                        elif group == "year":
                            is_this_year = int(period) == today.year
                            year_label = str(period)
                            label = (
                                _("This Year") if is_this_year else year_label
                            )
                        else:
                            date_obj = (
                                datetime.strptime(period, "%Y-%m-%d")
                                if isinstance(period, str)
                                else period
                            )
                            day_label = format_date(
                                date_obj, "dd MMM yyyy", locale=locale
                            )
                            label = (
                                _("Today") if date_obj == today else day_label
                            )
                    elif period:
                        if group == "year":
                            is_this_year = int(period) == today.year
                            year_label = str(period)
                            label = (
                                _("This Year") if is_this_year else year_label
                            )
                        else:
                            date_obj = (
                                datetime.strptime(period, "%Y-%m-%d")
                                if isinstance(period, str)
                                else period
                            )
                            day_label = format_date(
                                date_obj, "dd MMM yyyy", locale=locale
                            )
                            label = (
                                _("Today") if date_obj == today else day_label
                            )
                    x_field_labels[x_val] = label

        # ── Build the drill-down base domain ──────────────────────────
        # This domain must be self-sufficient: when the user clicks a
        # graph element and navigates to the list view, there is NO
        # dashboard context — so we embed the complete filter set here.
        #
        # The SQL graph query applies these filters:
        #   1. WHERE graph_table.data_field IN (dashboard_record_ids)
        #   2. AND <where_clause from custom_filter + data_scope + my_data>
        #
        # We replicate both as an ORM domain on the GRAPH MODEL:
        data_field = self.env.user._get_graph_data_field()
        hierarchy_ids = self._get_hierarchy_record_ids()

        # Filter #1: scope to this dashboard's records
        drilldown_base = [(data_field, "in", hierarchy_ids)]

        # Filter #2: same filters the SQL WHERE clause uses
        # (these are resolved from self.env.user which holds the config)
        custom_filter = self.env.user._get_graph_custom_filter()
        data_scope_domain = self.env.user._get_graph_data_scope_domain()
        my_data_domain = []
        graph_my_data_field = self.env.user._get_graph_my_data_field()
        if graph_my_data_field and getattr(
            self.env.user, graph_my_data_field, False
        ):
            my_data_domain = self._get_my_data_domain()

        drilldown_base = list(
            fields.Domain.AND(
                [
                    drilldown_base,
                    custom_filter,
                    data_scope_domain,
                    my_data_domain,
                ]
            )
        )

        for item in graph_data:
            x_val = item["x"]
            y_val = item["y"]

            # Label generation (standard Odoo logic)
            if x_val not in x_field_labels:
                label = x_val if x_val else _("None")
                if primary_field.ttype in ("many2one", "many2many"):
                    val = (
                        self.env[primary_field.relation]
                        .browse(x_val)
                        .display_name
                    )
                    label = val if val else _("None")
                elif primary_field.ttype == "selection":
                    selection = dict(
                        GraphModel.fields_get([primary_field.name])[
                            primary_field.name
                        ]["selection"]
                    )
                    label = selection.get(x_val, x_val)
                x_field_labels[x_val] = label

            # Identify secondary group values (series) and calculate domain
            parts = []

            # Start with the full base domain for this graph model
            point_domain = list(drilldown_base)

            # Primary domain
            if not primary_field.is_date_period():
                if primary_field.store:
                    point_domain.append((primary_field.name, "=", x_val))
            else:
                date_field_name, group = primary_field.get_date_period().split(
                    ":"
                )
                year_alias = f"{date_field_name}_year"
                year = item.get(year_alias)
                period = (
                    x_val
                    if group == "day"
                    else item.get(f"{date_field_name}_{group}") or x_val
                )
                x_date_params[x_val] = {"year": year, "period": period}
                point_domain.extend(
                    _get_date_domain(primary_field, group, year, period)
                )

            for field in dashboard_graph_groups[1:]:
                val = (
                    item.get(field.name)
                    if field.ttype != "many2many"
                    else item.get(field.column2)
                )
                if field.ttype == "char":
                    if field.is_date_period():
                        date_field_name, group = field.get_date_period().split(
                            ":"
                        )
                        year_alias = f"{date_field_name}_year"
                        year = item.get(year_alias)
                        period = item.get(f"{date_field_name}_{group}")
                        if period and year:
                            if group == "month":
                                parts.append(
                                    format_date(
                                        datetime(int(year), int(period), 1),
                                        "MMMM yyyy",
                                        locale=locale,
                                    )
                                )
                            elif group == "quarter":
                                parts.append(f"{period}")
                            elif group == "week":
                                week_value = f"{int(year)}-W{int(period):02d}"
                                week_start = datetime.strptime(
                                    week_value + "-1", "%G-W%V-%u"
                                )
                                parts.append(get_week_name(week_start, locale))
                            elif group == "year":
                                parts.append(str(year))
                        elif period:
                            # Day or other period field
                            date_obj = (
                                datetime.strptime(period, "%Y-%m-%d")
                                if isinstance(period, str)
                                else period
                            )
                            parts.append(
                                format_date(
                                    date_obj, "dd MMM yyyy", locale=locale
                                )
                            )
                        else:
                            parts.append(str(period) or str(year))

                        point_domain.extend(
                            _get_date_domain(field, group, year, period or val)
                        )
                    else:
                        parts.append(val if val is not False else _("None"))
                        if field.store:
                            point_domain.append((field.name, "=", val))
                elif field.ttype == "many2many":
                    parts.append(
                        self.env[field.relation].browse(val).display_name
                        if val
                        else _("None")
                    )
                    point_domain.append(
                        (field.name, "in", [val] if val else [])
                    )
                elif field.ttype == "many2one":
                    parts.append(
                        self.env[field.relation].browse(val).display_name
                        if val
                        else _("None")
                    )
                    if field.store:
                        point_domain.append((field.name, "=", val))
                elif field.ttype == "selection":
                    selection = dict(
                        GraphModel.fields_get([field.name])[field.name][
                            "selection"
                        ]
                    )
                    parts.append(selection.get(val, val))
                    if field.store:
                        point_domain.append((field.name, "=", val))
                else:
                    parts.append(str(val) if val is not False else _("None"))
                    if field.store:
                        point_domain.append((field.name, "=", val))

            series_key = tuple(parts)
            if series_key not in series_map:
                color_key = " / ".join(
                    [str(p) if p else _("None") for p in (parts or [label])]
                )
                series_map[series_key] = {"color_key": color_key}

            x_axis_data[x_val][series_key] = {
                "y": y_val,
                "domain": point_domain,
            }

        # Second pass: Build consistent datasets
        # Preserve natural SQL encounter order for Odoo-compliant stacking
        sorted_series_keys = list(series_map.keys())

        final_values = []
        # Maintain SQL order for X-axis
        seen_x = []
        for item in graph_data:
            if item["x"] not in seen_x:
                seen_x.append(item["x"])

        # ── Gap Filling for Date Groupings ────────────────────────────
        if primary_field.is_date_period() and seen_x:
            date_field_name, group = primary_field.get_date_period().split(":")

            # Identify min/max based on the raw x_val (which are date strings for 'day')
            # or based on year/period for other groups.
            if group == "day":
                try:
                    all_dates = [
                        datetime.strptime(x, "%Y-%m-%d") for x in seen_x if x
                    ]
                    if all_dates:
                        curr = min(all_dates)
                        last = max(all_dates)
                        while curr <= last:
                            date_str = curr.strftime("%Y-%m-%d")
                            if date_str not in seen_x:
                                seen_x.append(date_str)
                                # Label and Date Params
                                day_label = format_date(
                                    curr, "dd MMM yyyy", locale=locale
                                )
                                x_field_labels[date_str] = (
                                    _("Today")
                                    if curr.date() == today
                                    else day_label
                                )
                                x_date_params[date_str] = {
                                    "year": curr.year,
                                    "period": date_str,
                                }
                            curr += relativedelta(days=1)
                        # Sort the labels to keep chronological order
                        seen_x.sort()
                except Exception:
                    pass
            elif group == "month":
                # Similar logic could be added for month/week gaps if needed
                pass

        for x_val in seen_x:
            # Domain for the entire X-axis point (ignoring series)
            x_domain = list(drilldown_base)
            if not primary_field.is_date_period():
                if primary_field.store:
                    x_domain.append((primary_field.name, "=", x_val))
            else:
                date_field_name, group = primary_field.get_date_period().split(
                    ":"
                )
                x_params = x_date_params.get(x_val, {})
                x_domain.extend(
                    _get_date_domain(
                        primary_field,
                        group,
                        x_params.get("year"),
                        x_params.get("period"),
                    )
                )

            current_label = x_field_labels.get(x_val, str(x_val))
            dynamic_group_names = []
            for sk in sorted_series_keys:
                if sk:
                    sk_str = " / ".join(
                        [str(p) if p else _("None") for p in sk]
                    )
                    dynamic_group_names.append(f"{current_label} / {sk_str}")
                else:
                    dynamic_group_names.append(current_label)

            dataset = {
                "x_field": current_label,
                "x_domain": x_domain,
                "y_field": [
                    x_axis_data.get(x_val, {}).get(sk, {}).get("y", 0)
                    for sk in sorted_series_keys
                ],
                "domains": [
                    x_axis_data.get(x_val, {}).get(sk, {}).get("domain", [])
                    for sk in sorted_series_keys
                ],
                "group_names": dynamic_group_names,
                "group_color_keys": [
                    series_map[sk]["color_key"] for sk in sorted_series_keys
                ],
            }
            final_values.append(dataset)

        values = final_values
        only_date_groupby = (
            len(dashboard_graph_groups) == 1 and primary_field.is_date_period()
        )
        if only_date_groupby:
            for dataset in values:
                dataset["y_field"] = [sum(dataset["y_field"])]

        graph_key = self._graph_key()
        graph_type = self._get_graph_type(values)
        values = format_chart_data(values, graph_type)
        currency_id = self.env.user._get_currency_id()
        return {
            self.id: [
                {
                    "values": values,
                    "area": True,
                    "key": graph_key,
                    "is_sample_data": False if values else True,
                    "type": graph_type,
                    "currency_id": currency_id,
                    "model": self._get_graph_model(),
                }
            ]
        }

    # action portion: START

    # ------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------

    def _get_dashboard_action_eval_context(self):
        """Evaluation context for string-based expressions."""
        return {
            "self": self,
            "active_id": self.id,
            "active_ids": self.ids,
            "uid": self.env.user.id,
            "user": self.env.user,
            "env": self.env,
            "time": safe_eval_mod.time,
            "allowed_company_ids": self.env.context.get(
                "allowed_company_ids", self.env.companies.ids
            ),
        }

    def _evaluate_domain(self, domain):
        """Normalize and safely evaluate domain expressions."""
        if not domain:
            return []

        # Resolve lambdas or string expressions
        domain = self._normalize_dashboard_config_value(domain)

        if isinstance(domain, list):
            return domain
        return []

    # ------------------------------------------------------------
    # Action builder
    # ------------------------------------------------------------

    def _get_dashboard_action_extra_domain(self, extra_domain):
        """
        Build and normalize dashboard action domain.

        Handles:
        - Existing action domain
        - Additional domain from configuration
        """
        return self._normalize_dashboard_action_value(extra_domain)

    def _get_dashboard_action_default_context(self, default_context):
        """Build graph-related default context."""
        user = self.env.user
        data_field = user._get_graph_data_field()
        if not default_context or not isinstance(default_context, dict):
            default_context = {}
        return {
            **{
                f"default_{data_field}": self.id,
                f"search_default_{data_field}": [self.id],
            },
            **default_context,
        }

    def _get_dashboard_action_extra_context(
        self, extra_context, action_model=None
    ):
        """
        Build graph-related extra context.

        Logic:
        1. If extra_context is explicitly defined (even as {}), respect it.
        2. If not defined, only propagate graph state if the dashboard
           graph model matches the target action model.
        """
        # If explicitly defined in config (dict), use it as-is
        if isinstance(extra_context, dict) and not extra_context:
            return extra_context

        # If not defined (False), check model matching
        dashboard_model = self._get_graph_model()
        if dashboard_model != action_model:
            return {}

        user = self.env.user
        return {
            "graph_measure": user._get_graph_measure(),
            "graph_domain": user._get_graph_custom_filter(),
            "graph_groupbys": user._get_graph_groups(),
            "graph_mode": self.dashboard_graph_type,
            "graph_stacked": True,
            "graph_order": self.env.context.get("graph_order"),
            "graph_cumulated": self.env.context.get("graph_cumulated"),
            "pivot_measures": [user._get_graph_measure()],
            "pivot_column_groupby": [],
            "dashboard_rendering": True,
        }

    def _get_dashboard_action_default_values(self, default_values):
        """
        Normalize and evaluate default_values for dashboard actions.

        Supports:
        - Static values (e.g., {"type": "lead"})
        - Python expressions as strings
        - Callable/lambda expressions
        """
        if not default_values or not isinstance(default_values, dict):
            return {}

        defaults = {}

        for field, value in default_values.items():
            field = f"default_{field}"
            defaults[field] = self._normalize_dashboard_action_value(value)

        return defaults

    def _normalize_dashboard_action_value(self, value):
        """
        Normalize dashboard action value.

        Supports:
        - Callable values
        - String expressions (evaluated safely)
        - Static values
        """
        # Callable → execute safely
        if callable(value):
            try:
                return value(self)
            except Exception:
                _logger.warning(
                    "Dashboard: callable value evaluation failed for %s",
                    self._name,
                    exc_info=True,
                )
                return False

        # String → evaluate safely
        if isinstance(value, str):
            # If it's a field name on self, return its value directly to avoid safe_eval NameError
            if hasattr(self, value):
                return getattr(self, value)

            try:
                return safe_eval(
                    value,
                    self._get_dashboard_action_eval_context(),
                )
            except Exception:
                # Silently ignore simple field names that failed eval
                _logger.debug(
                    "Dashboard: string expression evaluation failed for %r, returning as-is",
                    value,
                )
                return value

        # Static value
        return value

    def _get_dashboard_action_search_defaults(self, search_defaults):
        """
        Convert `search_defaults` configuration into proper
        `search_default_*` context keys.

        Supported value types:
        - Boolean → directly assigned
        - String → directly assigned
        - List → treated as OR-condition of fields on `self`
                 (if any field in list is truthy, search default = True)
        """
        if not search_defaults or not isinstance(search_defaults, dict):
            return {}

        defaults = {}

        for filter_name, value in search_defaults.items():
            filter_name = f"search_default_{filter_name}"

            # Boolean → assign directly
            if isinstance(value, bool):
                defaults[filter_name] = value
                continue

            # String → evaluate expression safely
            if isinstance(value, str):
                try:
                    defaults[filter_name] = safe_eval(
                        value, self._get_dashboard_action_eval_context()
                    )
                except Exception:
                    defaults[filter_name] = value
                continue

            # List/Tuple → Evaluate elements and decide result
            if isinstance(value, (list, tuple)):
                evaluated_values = []
                is_field_list = True

                for item in value:
                    eval_item = self._normalize_dashboard_action_value(item)
                    evaluated_values.append(eval_item)

                    # If any item is not a string or not a field, it's not a 'field OR' list
                    if not isinstance(item, str) or not hasattr(self, item):
                        is_field_list = False

                if is_field_list:
                    # Legacy 'OR' logic for field lists
                    defaults[filter_name] = any(evaluated_values)
                else:
                    # Standard list of values (e.g. IDs for M2O)
                    defaults[filter_name] = evaluated_values
                continue

            # Fallback
            defaults[filter_name] = value

        return defaults

    def _get_dashboard_action_views(self, views_config):
        """
        Normalize views configuration.

        Expected format:
            [
                ("module.view_xml_id", "form"),
                ("module.view_tree_xml_id", "tree"),
            ]

        Returns:
            list of tuples (view_id, view_type)
        """
        if not views_config:
            return []

        result = []
        for view in views_config:
            if isinstance(view, (list, tuple)) and len(view) == 2:
                try:
                    view_id = self.env.ref(view[0]).id
                    result.append((view_id, view[1]))
                except Exception:
                    continue

        return result

    def _get_default_action_view_mode(self, view_mode):
        """
        Normalize and evaluate action view_mode.

        Supports:
        - Static string (e.g., "tree,form")
        - Python expression as string
        - Callable returning string
        """

        if not view_mode:
            return ""

        return view_mode

    def _prepare_dashboard_action(self, section, *keys):
        """
        Build dashboard action from nested configuration:

        actions:
            section
                key
                    variant (optional)
                        config
        """
        self.ensure_one()

        action_cfg = self._get_dashboard_action_config(section, *keys)
        if not action_cfg.get("action"):
            # Module-based variants
            IrModule = self.env["ir.module.module"].sudo()

            for module_name, variant_cfg in action_cfg.items():
                if not isinstance(variant_cfg, dict):
                    continue

                module_installed = IrModule.search(
                    [
                        ("name", "=", module_name),
                        ("state", "=", "installed"),
                    ],
                    limit=1,
                )

                if module_installed:
                    action_cfg = variant_cfg
                    break
            else:
                return False

        action_ref = self._normalize_dashboard_config_value(
            action_cfg.get("action")
        )
        action = self.env.ref(action_ref)._get_action_dict()

        # ------------------------------------------------------------
        # DOMAIN
        # ------------------------------------------------------------

        # If 'domain' is explicitly provided in config, it REPLACES the action's domain.
        # Otherwise, we evaluate the action's domain and APPEND 'extra_domain'.
        custom_domain = action_cfg.get("domain")
        if custom_domain is not None:
            action["domain"] = self._evaluate_domain(custom_domain)
        else:
            action["domain"] = self._evaluate_domain(
                action.get("domain", [])
            ) + self._get_dashboard_action_extra_domain(
                action_cfg.get("extra_domain", [])
            )
        user = self.env.user
        data_field = user._get_graph_data_field()
        action["domain"] += self._get_dashboard_hierarchy_domain(
            relation_field=data_field
        )

        # ------------------------------------------------------------
        # CONTEXT
        # ------------------------------------------------------------

        action_context = safe_eval(
            action.get("context", {}) or {},
            self._get_dashboard_action_eval_context(),
        )
        action["context"] = {
            **action_context,
            **(
                self._get_dashboard_action_default_context(
                    action_cfg.get("default_context", {})
                )
            ),
            **(
                self._get_dashboard_action_extra_context(
                    action_cfg.get("extra_context", False),
                    action_model=action.get("res_model"),
                )
            ),
            **(
                self._get_dashboard_action_default_values(
                    action_cfg.get("default_values", {})
                )
            ),
            **self._get_dashboard_action_search_defaults(
                action_cfg.get("search_defaults", {})
            ),
        }

        # ------------------------------------------------------------
        # VIEWS
        # ------------------------------------------------------------

        views = self._get_dashboard_action_views(action_cfg.get("views", []))
        if views:
            action["views"] = views

        # ------------------------------------------------------------
        # VIEW MODE
        # ------------------------------------------------------------

        view_mode = self._get_default_action_view_mode(
            action_cfg.get("view_mode", "")
        )
        if view_mode:
            action["view_mode"] = view_mode
        return action

    def _get_dashboard_action(self, section, *keys):
        """Public API to build and return a dashboard action."""
        return self._prepare_dashboard_action(section, *keys)

    # action portion: END

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _normalize_domain(self, domain):
        """Ensure domain is a mutable list."""
        return list(domain) if not isinstance(domain, list) else domain

    # ------------------------------------------------------------------
    # Dashboard-scoped record filtering
    # ------------------------------------------------------------------

    def _dashboard_record_ids(self, extra_domain=None):
        """
        Return the IDs of records visible in the current dashboard scope.

        Uses a direct SQL query with ``_search()`` for efficiency
        instead of the heavier ``formatted_read_group`` ORM call.
        The query runs a single ``SELECT DISTINCT`` on the data field,
        letting PostgreSQL optimize via indices.

        Uses a context flag to prevent infinite recursion when the
        graph model also inherits this mixin.
        """
        model_domain = []
        custom_domain = self.env.user._get_graph_custom_filter()
        data_scope_domain = self.env.user._get_graph_data_scope_domain()
        if custom_domain:
            model_domain.extend(custom_domain)
        if data_scope_domain:
            model_domain.extend(data_scope_domain)
        if extra_domain:
            model_domain.extend(extra_domain)
        graph_model = self.env[self._get_graph_model()].with_context(
            _dashboard_fetching_data=True
        )
        data_field = self.env.user._get_graph_data_field()
        graph_table = graph_model._table

        # Build an efficient SQL query via the ORM's _search, then
        # execute it directly to avoid formatted_read_group overhead.
        sub_query = graph_model._search(model_domain)
        if sub_query.where_clause:
            sql = (
                f"SELECT DISTINCT {graph_table}.{data_field} "
                f"FROM {sub_query.from_clause.code} "
                f"WHERE {sub_query.where_clause.code}"
            )
            params = sub_query.where_clause.params
        else:
            sql = (
                f"SELECT DISTINCT {graph_table}.{data_field} "
                f"FROM {graph_table}"
            )
            params = ()

        self.env.cr.execute(sql, params)
        return [row[0] for row in self.env.cr.fetchall() if row[0]]

    # ------------------------------------------------------------------
    # ORM override: dashboard domain injection
    # ------------------------------------------------------------------

    def _is_dashboard_context(self):
        """
        Check whether the current ORM call is executed within a
        dashboard context.

        Returns True only when all of the following hold:
        - The ``initializer`` key is present in context.
        - We are NOT already inside a recursive ``_fetch_data`` call
          (indicated by the ``_dashboard_fetching_data`` flag).

        This prevents:
        - Non-dashboard operations (websocket, mail, bus, cron) from
          hitting dashboard-specific logic (which would raise TypeError
          on None config values).
        - Infinite recursion when ``_dashboard_record_ids`` calls
          ``formatted_read_group`` on a model that also inherits this
          mixin.
        """
        ctx = self.env.context
        # We are in dashboard context if 'initializer' is set
        is_dashboard = bool(ctx.get("initializer")) and not ctx.get(
            "_dashboard_fetching_data"
        )

        if not is_dashboard:
            return False

        # EXCLUSIONS:
        # 1. If we are in a form view, we are opening a record, not rendering the dashboard.
        if ctx.get("params", {}).get("view_type") == "form":
            return False

        # 2. If active_id is present, we are likely acting on a specific record
        # (e.g., loading its sub-contacts or related records).
        if ctx.get("active_id") and not ctx.get("dashboard_rendering"):
            return False

        return True

    def _fetch_data(self, domain):
        """
        Inject dashboard-scoped domain filters when in a dashboard
        context. Otherwise pass the domain through unchanged.

        Synchronization strategy:
            The kanban list and the dashboard graph must always reflect
            the **same** record scope.  Three independent sources of
            "my data" filtering can restrict that scope:

            1. **Kanban search filter** – the ``my_partner`` / ``my_data``
               toggle in the search bar (lives in ``domain``).
            2. **User graph config** – the "My Pipeline" toggle stored
               on ``res.users`` (e.g. ``customer_dashboard_my_pipeline``).
            3. **with_analytics filter** – the "With Analytics" toggle
               that limits the kanban to records having graph data.

            When *with_analytics* is active we must resolve partner IDs
            via ``_dashboard_record_ids``.  If *either* source (1) or
            source (2) restricts to the current user's data, we pass
            ``('user_id', '=', uid)`` as ``extra_domain`` so that the
            SQL query matches the graph's actual scope.
        """
        if not self._is_dashboard_context():
            return self._normalize_domain(domain)

        domain = self._normalize_domain(domain)
        graph_my_data_field = self._get_graph_my_data_field()
        graph_with_analytics_field = self._get_graph_with_analytics_field()

        # ── 1. Detect if kanban 'My Data' filter is active in domain ──
        is_my_data_active = False
        for arg in domain:
            if (
                isinstance(arg, (list, tuple))
                and len(arg) >= 3
                and arg[0] == graph_my_data_field
                and arg[2] in ([True], 1)
            ):
                is_my_data_active = True
                break

        # ── 2. Detect if user's graph-level 'My Pipeline' config is on ─
        #    This is the toggle on res.users (e.g.
        #    customer_dashboard_my_pipeline) — separate from the kanban
        #    search bar filter but equally restricts the graph scope.
        is_user_my_data_active = False
        user_my_data_field = self.env.user._get_graph_my_data_field()
        if user_my_data_field:
            is_user_my_data_active = bool(
                getattr(self.env.user, user_my_data_field, False)
            )

        # Unified flag: user_id scoping required by either source
        needs_user_scope = is_my_data_active or is_user_my_data_active

        # ── 3. Process 'My Data' field replacement ────────────────────
        for index, arg in enumerate(domain):
            if (
                isinstance(arg, (list, tuple))
                and len(arg) >= 3
                and arg[0] == graph_my_data_field
            ):
                if arg[2] in ([True], 1):
                    # For models without user_id (like res.partner),
                    # resolve via graph model
                    if "user_id" not in self._fields:
                        domain[index : index + 1] = [
                            (
                                "id",
                                "in",
                                self._dashboard_record_ids(
                                    extra_domain=[
                                        ("user_id", "=", self.env.uid)
                                    ]
                                ),
                            )
                        ]
                    else:
                        domain[index : index + 1] = self._get_my_data_domain()
                break

        # ── 4. Process 'With Analytics' field replacement ─────────────
        for index, arg in enumerate(domain):
            if (
                isinstance(arg, (list, tuple))
                and len(arg) >= 3
                and arg[0] == graph_with_analytics_field
            ):
                if arg[2] in ([True], 1):
                    # Synchronize with the full graph scope:
                    # include user_id if EITHER the kanban filter OR
                    # the user's graph config restricts to "my" data.
                    extra = (
                        [("user_id", "=", self.env.uid)]
                        if needs_user_scope
                        else None
                    )
                    domain[index : index + 1] = [
                        (
                            "id",
                            "in",
                            self._dashboard_record_ids(extra_domain=extra),
                        )
                    ]
                break

        return domain

    @api.model
    def formatted_read_group(
        self,
        domain,
        groupby=(),
        aggregates=(),
        having=(),
        offset=0,
        limit=None,
        order=None,
    ) -> list[dict]:
        domain = self._fetch_data(domain)
        return super().formatted_read_group(
            domain,
            groupby,
            aggregates,
            having=having,
            offset=offset,
            limit=limit,
            order=order,
        )

    @api.model
    @api.readonly
    def search_fetch(
        self, domain, field_names, offset=0, limit=None, order=None
    ):
        domain = self._fetch_data(domain)
        return super().search_fetch(
            domain=domain,
            field_names=field_names,
            offset=offset,
            limit=limit,
            order=order,
        )


def build_dashboard_methods(config):
    """
    Generate compute and action methods for a dashboard config.

    This factory method loops over the 'actions' definition inside the dashboard
    config and automatically generates the binding methods needed for view buttons
    and field computes, using 'action_name' and 'compute_name' metadata.
    """
    methods = {}
    actions = config.get("actions", {})

    for section, section_cfg in actions.items():
        if section == "menu":
            for subsection, keys_cfg in section_cfg.items():
                for key, key_cfg in keys_cfg.items():
                    action_name = key_cfg.get("action_name")
                    if action_name:

                        def _make_action(
                            sec=section, subsec=subsection, k=key
                        ):
                            def action_handler(self):
                                self.ensure_one()
                                return self._get_dashboard_action(
                                    sec, subsec, k
                                )

                            return action_handler

                        methods[action_name] = _make_action()
        else:
            for key, key_cfg in section_cfg.items():
                action_name = key_cfg.get("action_name")
                if action_name:

                    def _make_action(sec=section, k=key):
                        def action_handler(self):
                            self.ensure_one()
                            return self._get_dashboard_action(sec, k)

                        return action_handler

                    methods[action_name] = _make_action()

                compute_name = key_cfg.get("compute_name")
                if compute_name:
                    # Extract field names at generation time to ensure they are
                    # always assigned a default value even if the config is not
                    # found for the current dashboard context.
                    compute_cfg = key_cfg.get("compute", {})
                    field_specs = compute_cfg.get("fields", [])
                    field_names = [
                        s.get("field") for s in field_specs if s.get("field")
                    ]

                    def _make_compute(sec=section, k=key, fnames=field_names):
                        def compute_handler(self):
                            self._compute_dashboard_action_fields(
                                sec, k, expected_fields=fnames
                            )

                        return compute_handler

                    methods[compute_name] = _make_compute()

    # ── User Preferences Sync Compute ─────────────────────
    user_prefs = config.get("user_prefs", {})
    for compute_name, pref_cfg in user_prefs.items():
        if isinstance(pref_cfg, dict) and pref_cfg.get("fields"):
            pref_fields = pref_cfg["fields"]

            def _make_sync(mapping=pref_fields):
                def handler(self):
                    user = self.env.user
                    for partner_field, user_field in mapping.items():
                        # Support callables, groups, and direct field values
                        if callable(user_field):
                            val = user_field(self)
                        elif user_field.startswith("group:"):
                            group_xml_id = user_field.split("group:")[1]
                            val = user.has_group(group_xml_id)
                        else:
                            val = getattr(user, user_field)

                        for record in self:
                            record[partner_field] = val

                return handler

            methods[compute_name] = _make_sync()

    return methods
