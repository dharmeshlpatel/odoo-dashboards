"""
Base Dashboard Configuration Mixin

This module provides a reusable abstract mixin for building configurable,
period-based dashboard graphs in Odoo.

It centralizes:
- Graph period handling (month / quarter / year)
- Timezone-safe date range domain generation
- Measure and group-by resolution for graph views
- Dashboard initializer-based configuration
- Generic onchange and default logic for dashboard filters

The mixin is designed to be extended by specific dashboard implementations
(CRM, Sales, Custom dashboards, etc.) by overriding configuration hooks.
"""

# -*- coding: utf-8 -*-

import pytz
import logging
import time
from odoo import models, fields, api, _
from odoo import tools
from datetime import datetime, timedelta
from odoo.tools.safe_eval import safe_eval
from ast import literal_eval
from ..models.dashboard_graph_periods import (
    get_period_year,
)
from ..models.ir_model_fields import (
    GRAPH_CUSTOM_GROUP,
)
from ..tools.date_utils import (
    _get_year_dates,
    _get_period_dates,
)
from ..tools.domain_utils import (
    _date_range_to_domain,
)
from odoo.addons.dashboard_engine.tools.many2many_utils import (
    compute_many2many_order,
)
from odoo.tools.misc import submap
from lxml import etree

_logger = logging.getLogger(__name__)

READ_GROUP_ADDITIONAL_AGGREGATE = {"sum_currency": False}

ALLOWED_GROUPBY_TYPES = (
    "boolean",
    "char",
    "date",
    "datetime",
    "integer",
    "many2many",
    "many2one",
    "selection",
)


class BaseDashboardConfigMixin(models.AbstractModel):
    """
    Abstract mixin providing shared dashboard graph configuration logic.

    This mixin:
    - Reads dashboard configuration from context-based initializers
    - Builds dynamic domains for graph data
    - Computes available measures and group-by fields
    - Handles default values and onchange logic for dashboard filters

    Intended to be inherited by dashboard-specific models.
    """

    _name = "base.dashboard.config.mixin"
    _description = "Base Dashboard Configuration Mixin"
    _inherit = ["base.dashboard.mixin"]

    @api.model
    def _get_dashboard_installed_fields(self):
        """
        Identify dashboard-related availability fields on the model.

        This method scans the model's fields and returns all field names
        that follow the naming convention:
            `<module_name>_dashboard_installed`

        These boolean fields are used to dynamically detect whether
        corresponding dashboard modules are installed, without hardcoding
        module names in the logic.

        Typical usage:
        - Used by `_compute_dashboard_module_availability`
        - Enables conditional UI rendering and feature toggling
          based on installed dashboard modules

        :return: iterable of field names ending with `_dashboard_installed`
        """
        # Filter all model fields to find dashboard availability flags
        return filter(
            # Only consider boolean fields following the dashboard naming convention
            lambda field: field.endswith("_dashboard_installed"),
            self.fields_get(),
        )

    def _compute_dashboard_module_availability(self):
        """
        Compute dashboard module availability flags dynamically.

        This compute method evaluates which dashboard-related modules
        are installed in the system and updates corresponding boolean
        fields on the record.

        Each boolean field ending with `_dashboard_installed` represents
        a dashboard module. The module name is derived directly from
        the field name, allowing new dashboards to be supported without
        modifying this logic.

        Example:
            sales_dashboard_installed → checks if module `sales_dashboard` is installed

        Typical usage:
        - Control visibility of dashboard menus or actions
        - Enable or disable dashboard-specific features at runtime

        This method relies on:
        - `_get_dashboard_installed_fields()` for field discovery
        - `ir.module.module._is_module_installed()` for module state lookup
        """
        # Access module registry to check installation status
        ir_module = self.env["ir.module.module"]
        # Compute availability flags per record
        for record in self:
            # Iterate over all dashboard availability fields dynamically
            for field_name in self._get_dashboard_installed_fields():
                # Extract module name from field and set installation status
                setattr(
                    record,
                    field_name,
                    ir_module._is_module_installed(
                        field_name.split("_installed")[0]
                    ),
                )



    def _graph_get_dashboard_periods(self):
        """
        Collect selected dashboard time periods per date field.

        This method gathers the selected:
            - Month / Quarter periods
            - Year periods

        for each configured date field and returns them as a structured mapping.

        Returned structure:
            {
                "<date_field>": [
                    [<month_or_quarter_keys>],
                    [<year_keys>]
                ]
            }

        This output acts as the base input for:
            - Date range calculation
            - Domain generation for dashboard graph queries

        :return: dict mapping date field to selected period keys
        """
        # Final mapping of date field → selected periods
        graph_dashboard_periods = {}
        # Iterate over configured month/quarter and year period fields
        for field, [
            mq_period_field,
            year_period_field,
        ] in self._graph_get_dashboard_mq_year_period_fields().items():
            # Extract selected month/quarter period identifiers
            mq_periods = [
                mq_period.name for mq_period in getattr(self, mq_period_field)
            ]
            # Extract selected year period identifiers
            year_periods = [
                year_period.name
                for year_period in getattr(self, year_period_field)
            ]
            graph_dashboard_periods.update({field: [mq_periods, year_periods]})
        return graph_dashboard_periods

    def _graph_get_dates(self):
        """
        Build timezone-aware date range domains for dashboard filters.

        For each configured date field and selected period combination:
            - Resolve concrete date ranges (start_date, end_date)
            - Convert them into ORM-compatible domain fragments
            - Apply web-client timezone offset for accurate comparisons

        The resulting domains are later combined using AND / OR
        depending on the selected filter operator.

        :return: list of domain fragments
        """
        dates = []
        # Web client timezone offset (in minutes) for correct date conversion
        tz_offset = self.env.context.get("webclient_tz_offset", 0)
        # Process each date field with its selected periods
        for field, [
            mq_periods,
            year_periods,
        ] in self._graph_get_dashboard_periods().items():
            # Year period is mandatory to compute concrete date ranges
            if not year_periods:
                continue

            for year_key in year_periods:
                # Resolve actual date ranges for the selected year and sub-periods
                year = get_period_year().get(year_key)
                date_ranges = _get_period_dates(year, mq_periods)

                for start_date, end_date in date_ranges:
                    # Convert date range into a timezone-aware domain
                    dates.append(
                        _date_range_to_domain(
                            field,
                            start_date,
                            end_date,
                            tz_offset,
                        )
                    )
        return dates

    def _prepare_graph_custom_filter(self):
        """
        Build the final custom domain for dashboard graph queries.

        This method combines all generated date range domains
        according to the configured filter operator:

        Operators:
            - 'any'  → OR between period domains
            - others → AND between all period domains

        This allows flexible dashboard filtering such as:
            - Any selected period
            - All selected periods together

        :return: fields.Domain expression
        """
        # Container for composed domain expressions
        domain = []
        # Retrieve computed date-range domains;
        # exit early if no periods are selected.
        graph_data_filter_dates = self._graph_get_dates()
        if not graph_data_filter_dates:
            return domain
        # Determine how multiple period domains should be combined
        if self._graph_get_dashboard_filter_operator() == "any":
            for dates in graph_data_filter_dates:
                # Group each date range with AND, then combine using OR
                domain.append(fields.Domain.AND(dates))
            return fields.Domain.OR(domain)
        else:
            for dates in graph_data_filter_dates:
                # Merge all date ranges into a single AND domain
                domain.extend(dates)
            return fields.Domain.AND(domain)

    def _compute_report_measures(
        self,
        fields,
        field_attrs=None,
        active_measures=None,
        sum_aggregator_only=False,
    ):
        """
        Compute and prepare available graph measures for dashboard reports.

        This method determines which model fields can be used as graph measures
        by closely following the web client’s graph view logic. It evaluates:
            - Field visibility rules from the graph view
            - Numeric field types eligible for aggregation
            - Supported aggregators defined on fields
            - Optional restriction to sum-only aggregators

        A default "__count" measure is always included to ensure that
        graphs remain functional even when no numeric fields are available.

        The resulting measures structure is optimized for graph rendering
        and UI consumption.

        :param fields: Result of `fields_get()` for the graph model
        :param field_attrs: Optional graph-view attributes (visibility, labels)
        :param active_measures: Optional list of measures to force-include
        :param sum_aggregator_only: If True, restrict measures to sum aggregators
        :return: Ordered dict mapping measure names to measure definitions
        """
        if field_attrs is None:
            field_attrs = {}
        if active_measures is None:
            active_measures = []

        # "__count" is always available as a fallback measure
        measures = {
            "__count": {
                "name": "__count",
                "string": "Count",
                "type": "integer",
            }
        }

        # Iterate through all model fields to identify valid measure candidates
        for field_name, field in fields.items():
            if field_name == "id":
                continue

            # Skip fields explicitly marked as invisible in the graph view
            field_attr = field_attrs.get(field_name, {})
            if field_attr.get("isInvisible", False):
                continue

            # Only numeric field types can be used as graph measures
            if field.get("type") in ["integer", "float", "monetary"]:
                aggregator = field.get("aggregator")
                # Aggregator defines how values are combined (sum, avg, etc.)
                if aggregator:
                    # Optionally restrict measures to sum-only aggregators
                    if sum_aggregator_only and aggregator != "sum":
                        continue
                    # Limit field definition to keys required by the graph view
                    filtered_field = submap(
                        field,
                        ["type", "aggregator", "name", "string", "sortable"],
                    )
                    measures[field_name] = filtered_field

        # Force-include explicitly requested measures (e.g. functional fields)
        for measure in active_measures:
            if measure not in measures and measure in fields:
                # Apply the same filtering rules for forced measures
                filtered_field = submap(
                    fields[measure],
                    ["type", "aggregator", "name", "string", "sortable"],
                )
                measures[measure] = filtered_field

        # Override measure labels if graph view provides custom strings
        for field_name, field_attr in field_attrs.items():
            if field_attr.get("string") and field_name in measures:
                measures[field_name] = dict(measures[field_name])
                measures[field_name]["string"] = field_attr["string"]

        # Sort measures: "__count" last, others alphabetically by label
        def sort_key(item):
            field_name, field_def = item
            if field_name == "__count":
                return 1, ""  # Count goes last
            return 0, field_def.get("string", "").lower()

        sorted_measures = sorted(measures.items(), key=sort_key)
        return dict(sorted_measures)

    def _graph_get_measures(self):
        """
        Resolve available graph measures based on the graph view definition.

        This method inspects the graph view architecture of the configured
        graph model to determine:
            - Which fields are present in the graph view
            - Which fields are explicitly marked as invisible
            - Custom display labels defined at the view level

        The extracted view metadata is then passed to
        `_compute_report_measures` to build a final, UI-ready
        measures definition.

        This ensures that backend measure availability stays
        fully aligned with the actual graph view configuration.

        :return: dict mapping measure name to measure definition
        """
        graph_model_name = self._get_graph_model()
        fields = self.env[graph_model_name].fields_get()
        return self._compute_report_measures(
            fields, self._graph_field_attrs_for_model(graph_model_name)
        )

    @api.model
    def _graph_field_attrs_for_model(self, model_name):
        """Graph-view field attrs (invisible / label) for ``model_name``."""
        field_attrs = {}
        if not model_name or model_name not in self.env:
            return field_attrs
        graph_model = self.env[model_name]
        try:
            graph_view = (graph_model.get_views([(False, "graph")])["views"]).get(
                "graph"
            )
        except Exception:
            graph_view = None
        if graph_view and graph_view.get("arch"):
            view_tree = etree.fromstring(graph_view["arch"], None)
            for field_element in view_tree.xpath(".//field"):
                field_name = field_element.get("name")
                if not field_name:
                    continue
                inv = field_element.get("invisible")
                field_attrs[field_name] = {
                    "isInvisible": inv in ("1", "True", "true"),
                    "string": field_element.get("string"),
                }
        return field_attrs

    @api.model
    def _graph_measure_names_for_model(self, model_name):
        """Measure field names like the standard graph Measures menu (no Count)."""
        if not model_name or model_name not in self.env:
            return []
        fields = self.env[model_name].fields_get()
        measures = self._compute_report_measures(
            fields, self._graph_field_attrs_for_model(model_name)
        )
        return [name for name in measures if name != "__count"]

    def _get_currency_id(self):
        """
        Resolve the currency ID for the selected graph measure.

        This helper checks whether the currently selected graph measure
        represents a monetary field. If so, it returns the company currency ID
        so the graph can correctly format and aggregate monetary values.

        If the selected measure is:
            - not set
            - not found in available graph measures
            - not of type 'monetary'

        then no currency is required and the method returns None.

        :return: int or None (company currency ID if applicable)
        """
        # Fetch all resolved graph measures
        graph_measures = self._graph_get_measures()
        # Get the currently selected graph measure
        graph_measure = self._get_graph_measure()
        if graph_measure:
            field_values = graph_measures.get(graph_measure)
            # Selected measure is not part of resolved measures
            if not field_values:
                return None
            # Monetary measures require a currency for proper display
            if field_values.get("type") == "monetary":
                return self.env.company.currency_id.id
        return None

    def _get_group_by_selection(self):
        """
        Return available group-by field selections for dashboard graphs.

        This method inspects the graph model and collects all fields
        that are marked as groupable by Odoo.

        The result is formatted as a list of (field_name, label) tuples,
        sorted alphabetically by label, and typically used to populate
        group-by selection widgets in the UI.

        :return: list of (field_name, string) tuples
        """
        # Resolve the model used for graph grouping
        GraphModel = self.env[self._get_graph_model()]
        # Fetch ALL field definitions in a single call (avoids N+1)
        all_fields = GraphModel.fields_get()
        # Collect groupable fields with their display labels
        values = [
            (name, meta["string"])
            for name, meta in all_fields.items()
            if meta.get("groupable")
        ]
        # Sort fields alphabetically by label for better UX
        values.sort(key=lambda x: x[1].lower())
        return values

    def _graph_get_dashboard_filter_operator(self):
        """
        Return the evaluated dashboard filter operator domain.

        This method retrieves the value stored in the filter-operator field
        defined by the dashboard configuration and returns its evaluated
        domain expression.

        The returned value is later used to decide how multiple
        date-period domains should be combined (AND / OR).

        :return: fields.Domain or list representing the filter operator result
        """
        # Fetch the computed filter operator value from its configured field
        return getattr(
            self,
            self._get_graph_period_filter_operator_field(),
        )

    def _graph_get_dashboard_mq_year_period_fields(self):
        """
        Return configured month/quarter and year period field mappings.

        This method reads dashboard configuration and returns a mapping
        defining which many2many fields represent:
            - Month / Quarter period selections
            - Year period selections

        The mapping is keyed by the target date field and is used
        throughout the dashboard filter pipeline.

        :return: dict mapping date field → [mq_period_field, year_period_field]
        """
        mq_year_period_fields = {}
        graph_filter = self._get_dashboard_config_value("graph_filter", {})
        fields_config = graph_filter.get("fields", {})
        for (
            date_field,
            periods,
        ) in fields_config.items():
            mq_period_config = periods.get("mq_period", {})
            year_period_config = periods.get("year_period", {})

            mq_period_field = (
                mq_period_config.get("field", False)
                if isinstance(mq_period_config, dict)
                else mq_period_config
            )
            year_period_field = (
                year_period_config.get("field", False)
                if isinstance(year_period_config, dict)
                else year_period_config
            )

            # Only include properly configured period fields
            if mq_period_field and year_period_field:
                mq_year_period_fields[date_field] = [
                    mq_period_field,
                    year_period_field,
                ]

        return mq_year_period_fields

    def _compute_default_graph_mq_year_period(self):
        graph_filter = self._get_dashboard_config_value("graph_filter", {})
        fields_config = graph_filter.get("fields", {})

        period_models = {
            "mq_period": "period.month.quarter",
            "year_period": "period.year",
        }

        # Build default values per field → ids
        default_values = {}
        for periods in fields_config.values():
            for period_type, period_config in periods.items():
                model_name = period_models.get(period_type)
                if not model_name:
                    continue

                period_field = (
                    period_config.get("field")
                    if isinstance(period_config, dict)
                    else period_config
                )
                default_periods = (
                    period_config.get("default", [])
                    if isinstance(period_config, dict)
                    else []
                )

                if period_field and default_periods:
                    default_values[period_field] = (
                        self.env[model_name]
                        .search([("name", "in", default_periods)])
                        .ids
                    )

        # Apply defaults only if field is empty
        for rec in self:
            for period_field, default_period_ids in default_values.items():
                setattr(rec, period_field, default_period_ids)
                # Trigger onchange to recompute dependent graph period fields
                getattr(rec, "_onchange_" + period_field)()
            if default_values:
                getattr(self, "_compute_default_graph_custom_filter")()

    def _inverse_default_graph_mq_year_period(self):
        """
        Inverse method for default group-by and filter computation.

        No inverse logic is required because defaults are only
        applied when fields are empty.
        """
        pass

    def _get_graph_period_filter_operator_field(self):
        """
        Return the field name storing the dashboard filter operator.

        This field typically holds a computed domain generated from
        selected dashboard periods and is updated via onchange logic.

        :return: str (field name)
        """
        # Resolve operator field name from dashboard configuration
        return (
            self._get_dashboard_config_value("graph_filter", {})
            .get("operator", {})
            .get("field")
        )

    def _onchange_graph_filter_operator(self):
        """
        Onchange handler for dashboard filter operator updates.

        When the filter operator is changed, this method recomputes
        the custom filter domain and stores it in the configured
        custom-filter field to keep the graph data in sync.

        :return: None
        """
        # Recompute and apply the updated custom filter domain
        custom_filter_field = self._get_graph_custom_filter_field()
        if custom_filter_field:
            setattr(
                self,
                custom_filter_field,
                self._prepare_graph_custom_filter(),
            )

    def _get_extra_fields(self, model, related_field):
        """
        Resolve the final related field for group-by domain computation.

        This helper recursively traverses a related field chain to identify
        the final `ir.model.fields` record that can safely be used
        for dashboard group-by operations.

        Validation rules applied at each step:
            - Field must exist on the given model
            - Field type must be allowed for group-by operations
            - For multi-level relations, the field must define a relation
            - Final resolved field must be storable

        This method is primarily used while resolving non-stored
        related fields inside `_get_graph_group_by_domain`.

        :param model: Odoo model name
        :param related_field: List of related field path segments
                              (e.g. ['partner_id', 'country_id', 'name'])
        :return: ir.model.fields record if valid, otherwise None
        """
        # No related path provided → nothing to resolve
        if not related_field:
            return None
        # Locate the first field in the related chain on the given model
        field = self.env["ir.model.fields"].search(
            [
                ("model_id.model", "=", model),
                ("name", "=", related_field[0]),
            ],
            limit=1,
        )
        if not field:
            return None
        # Disallow unsupported field types for group-by usage
        if field.ttype not in ALLOWED_GROUPBY_TYPES:
            return None
        # Last segment reached → return validated field
        if len(related_field) == 1:
            return field
        # Cannot traverse further without a relational target
        if not field.relation:
            return None
        # Recursively resolve the remaining related field path
        return self._get_extra_fields(field.relation, related_field[1:])

    def _get_graph_computed_groupby_fields(self):
        """
        Return field names that require model-level SQL generation
        for group-by operations.

        These are non-stored computed fields that need special
        ``_read_group_groupby`` queries instead of normal column
        references.

        Override this in downstream modules to register additional
        computed fields for dashboard grouping.

        :return: tuple of field name strings
        """
        return self._get_dashboard_config_value(
            "graph_computed_groupby_fields", ()
        )

    def _get_graph_group_by_domain(self):
        """
        Compute the domain restricting allowed group-by fields for dashboards.

        This method builds a domain on `ir.model.fields` to determine
        which fields are eligible for grouping in dashboard graphs.

        Rules applied:
            - Only allowed technical field types are considered
            - Stored fields are preferred
            - Related fields are resolved recursively when possible
            - Custom date-period grouping fields are injected
            - Certain technical fields are explicitly whitelisted

        The resulting domain is consumed by many2many group-by selectors
        to prevent invalid or unsupported groupings.

        :return: domain usable on ir.model.fields
        """
        model = self._get_graph_model()
        # Fetch all candidate fields from the target graph model
        field_ids = self.env["ir.model.fields"].search(
            [
                ("model_id.model", "=", model),
                (
                    "ttype",
                    "in",
                    ALLOWED_GROUPBY_TYPES,
                ),
            ]
        )
        # Pre-build name → record index for O(1) lookups
        fields_by_name = {f.name: f for f in field_ids}
        # Pre-compute computed groupby names once
        computed_names = self._get_graph_computed_groupby_fields()
        # Accumulate IDs of fields allowed for group-by usage
        allowed_field_ids = []
        for field in field_ids:
            # Allow computed fields registered for dashboard grouping
            if field.name in computed_names:
                allowed_field_ids.append(field.id)
                continue
            # Inject custom date-period grouping fields for stored date fields
            if field.ttype in ("date", "datetime") and field.store:
                for group in GRAPH_CUSTOM_GROUP:
                    vf = fields_by_name.get(f"x_{field.name}_{group}")
                    if vf:
                        allowed_field_ids.append(vf.id)
                continue
            # Prefer directly stored fields for grouping
            if field.store:
                if field.name != "id":
                    allowed_field_ids.append(field.id)
                continue
            # Attempt to resolve non-stored related fields recursively
            if field.related:
                related_field = field.related.split(".")
                final_field = self._get_extra_fields(model, related_field)
                if final_field and final_field.store:
                    allowed_field_ids.append(field.id)
        # Return domain limiting selectable group-by fields
        return [("id", "in", allowed_field_ids)]

    def _get_graph_default_groupby_field_names(self):
        """
        Return default group-by field names configured for the dashboard.

        This helper reads the dashboard initializer configuration and
        returns the list of field *names* that should be applied as
        default group-by values when the dashboard is first loaded.

        These names are later resolved into `ir.model.fields` records
        by `_default_groupby_fields`.

        :return: list of field names
        """
        # Read default group-by field names from dashboard configuration
        graph_model_rec_name = self.env[self._get_graph_model()]._rec_name
        groupby_config = self._get_dashboard_config_value("graph_groupby", {})
        return (
            groupby_config.get("default", [graph_model_rec_name])
            if isinstance(groupby_config, dict)
            else [graph_model_rec_name]
        )

    def _default_groupby_fields(self):
        """
        Resolve default group-by fields as ir.model.fields records.

        This method converts the configured default group-by field names
        into actual `ir.model.fields` records for the active graph model.

        It is mainly used while initializing dashboard state to ensure
        that valid group-by fields are preselected.

        :return: ir.model.fields recordset
        """
        # Resolve the graph model for which group-by fields apply
        model = self._get_graph_model()
        # Fetch ir.model.fields records matching configured default names
        return self.env["ir.model.fields"].search(
            [
                ("model_id.model", "=", model),
                (
                    "name",
                    "in",
                    self._get_graph_default_groupby_field_names(),
                ),
            ]
        )

    def _get_current_year_domain(self, date_field=None):
        """
        Compute the default domain for the current year in user timezone.

        This helper builds a date range domain covering the full
        current calendar year, taking the user's timezone into account.

        The resulting domain is typically used as the initial
        filter for dashboards that default to the current year.

        :param date_field: Optional date field name to filter on.
            Defaults to 'create_date' if not specified.
        :return: domain list suitable for ORM searches
        """
        if not date_field:
            date_field = "create_date"
        # Get current UTC date as reference
        today_utc = datetime.now(tz=pytz.UTC)
        current_year = today_utc.year
        # Determine user's timezone (context → user → UTC fallback)
        tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
        user_tz = pytz.timezone(tz_name)
        # Resolve start and end dates for the current calendar year
        start_date, end_date = _get_year_dates(current_year)
        # Convert local dates to UTC datetimes for server-side comparison
        start_utc = user_tz.localize(start_date).astimezone(pytz.UTC)
        end_utc = user_tz.localize(end_date).astimezone(pytz.UTC) - timedelta(
            seconds=1
        )
        # Build ORM domain filtering records within the current year
        domain = [
            "&",
            (
                date_field,
                ">=",
                start_utc.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT),
            ),
            (
                date_field,
                "<=",
                end_utc.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT),
            ),
        ]
        return domain

    def _get_default_graph_custom_filter(self):
        """
        Return the default domain configured for dashboard graphs.

        This method fetches the default custom domain from the dashboard
        initializer configuration. The returned domain is typically applied
        when the dashboard is first loaded or when filters are reset.

        :return: list representing an ORM domain
        """
        # Read default custom domain from dashboard configuration
        custom_filter_config = self._get_dashboard_config_value(
            "graph_custom_filter", {}
        )
        return (
            custom_filter_config.get("default", [])
            if isinstance(custom_filter_config, dict)
            else []
        )

    @api.model
    def _get_graph_measures(self):
        """
        Return available graph measures as selection values.

        This helper converts the resolved graph measure definitions
        into a simplified list of `(name, label)` tuples suitable
        for use in selection fields.

        :return: list of (measure_name, display_label) tuples
        """
        # Convert measure definitions into selection-friendly tuples
        graph_measures = self._graph_get_measures()
        return [
            (graph_measure["name"], graph_measure["string"])
            for graph_measure in graph_measures.values()
        ]

    def _get_graph_measure_field(self):
        """
        Return the field name used to store the selected graph measure.

        This field is defined in the dashboard initializer configuration
        and is typically a selection field on the dashboard model.

        :return: str (field name)
        """
        # Resolve graph measure field name from dashboard configuration
        return self._get_dashboard_config_value("graph_measure", {}).get(
            "field"
        )

    def _get_graph_measure(self):
        """
        Return the currently selected graph measure value.

        This method dynamically reads the value from the configured
        graph-measure field on the record.

        :return: str (measure name)
        """
        # Fetch selected graph measure from its configured field
        return getattr(self, self._get_graph_measure_field())

    def _get_graph_measure_aggregator(self):
        # Fetch selected graph measure aggregator from its configured field
        return getattr(self, self._get_graph_measure_aggregator_field())

    def _get_graph_default_measure(self):
        """
        Return the default graph measure configured for the dashboard.

        This value is used when no measure has been explicitly selected
        by the user. Defaults to "__count" if not configured.

        :return: str (default measure name)
        """
        # Read default measure from dashboard configuration
        return self._get_dashboard_config_value("graph_measure", {}).get(
            "default", "__count"
        )

    def _get_graph_groupby_field(self):
        """
        Return the field name used to store selected group-by values.

        This field is defined in the dashboard initializer configuration
        and usually represents a many2many relation to `ir.model.fields`.

        :return: str (field name)
        """
        # Resolve group-by field name from dashboard configuration
        groupby_config = self._get_dashboard_config_value("graph_groupby", {})
        return (
            groupby_config.get("field", False)
            if isinstance(groupby_config, dict)
            else groupby_config
        )

    def _compute_default_graph_measure(self):
        """
        Compute and apply the default graph measure.

        This compute method ensures that a valid graph measure is always set
        on the record. If the configured graph-measure field is empty,
        it assigns the default measure from dashboard configuration
        and triggers the corresponding onchange to keep dependent fields
        (such as aggregators) in sync.

        :return: None
        """
        for rec in self:
            # Resolve the field used to store the selected graph measure
            measure_field = rec._get_graph_measure_field()
            if not measure_field:
                continue
            # Apply default measure only if no value is currently set
            if not getattr(rec, measure_field):
                setattr(
                    rec,
                    measure_field,
                    self._get_graph_default_measure(),
                )
                # Trigger onchange to recompute dependent graph fields
                getattr(rec, "_onchange_" + measure_field)()

    def _inverse_default_graph_measure(self):
        """
        Inverse method for default graph measure computation.

        No inverse logic is required because the default value
        is only applied when the field is empty.
        """
        pass

    def _compute_default_graph_groupby(self):
        """
        Compute and apply default group-by and custom filter values.

        This method ensures that:
            - Default group-by fields are applied when none are selected
            - Default custom filter domain is applied when empty

        It also triggers the necessary onchange handlers so that
        ordered many2many fields and filter domains remain consistent.

        :return: None
        """
        for rec in self:
            # Resolve configured group-by field
            groupby_field = rec._get_graph_groupby_field()
            if not groupby_field:
                continue
            # Apply default group-by fields if none are selected
            if not getattr(rec, groupby_field):
                setattr(
                    rec,
                    groupby_field,
                    self._default_groupby_fields().ids,
                )
                # Trigger onchange to maintain ordered group-by values
                getattr(
                    rec,
                    "_onchange_" + groupby_field,
                )()

    def _inverse_default_graph_groupby(self):
        """
        Inverse method for default group-by and filter computation.

        No inverse logic is required because defaults are only
        applied when fields are empty.
        """
        pass

    def _compute_default_graph_custom_filter(self):
        """
        Compute and apply default group-by and custom filter values.

        This method ensures that:
            - Default group-by fields are applied when none are selected
            - Default custom filter domain is applied when empty

        It also triggers the necessary onchange handlers so that
        ordered many2many fields and filter domains remain consistent.

        :return: None
        """
        for rec in self:
            # Resolve configured custom-filter field
            custom_filter_field = rec._get_graph_custom_filter_field()
            if not custom_filter_field:
                continue
            # Apply default custom filter domain if missing
            custom_filter = []
            current_custom_filter = rec._get_graph_custom_filter()
            current_custom_filter = (
                [current_custom_filter] if current_custom_filter else []
            )
            default_custom_filter = rec.with_context(
                tz=rec.tz
            )._get_default_graph_custom_filter()
            default_custom_filter = (
                [default_custom_filter] if default_custom_filter else []
            )
            if not any([current_custom_filter, default_custom_filter]):
                setattr(rec, custom_filter_field, custom_filter)
                continue
            if rec._graph_get_dashboard_filter_operator() == "any":
                for cd_customer_filter in [
                    current_custom_filter,
                    default_custom_filter,
                ]:
                    if not cd_customer_filter:
                        continue
                    # Group each date range with AND, then combine using OR
                    custom_filter.append(fields.Domain.AND(cd_customer_filter))
                custom_filter = fields.Domain.OR(custom_filter)
            else:
                for cd_custom_filter in [
                    current_custom_filter,
                    default_custom_filter,
                ]:
                    if not cd_custom_filter:
                        continue
                    # Merge all date ranges into a single AND domain
                    custom_filter.extend(cd_custom_filter)
                custom_filter = fields.Domain.AND(custom_filter)
            setattr(rec, custom_filter_field, custom_filter)

    def _inverse_default_graph_custom_filter(self):
        """
        Inverse method for default group-by and filter computation.

        No inverse logic is required because defaults are only
        applied when fields are empty.
        """
        pass

    def _get_graph_measure_aggregator_field(self):
        """
        Return the field name used to store the graph measure aggregator.

        This field holds the selected aggregation method
        (e.g. sum, avg, count, sum_currency) for the current graph measure.

        :return: str (field name)
        """
        # Resolve graph measure aggregator field from dashboard configuration
        return self._get_dashboard_config_value("graph_measure", {}).get(
            "aggregator"
        )

    def _get_default_graph_data_scope(self, field):
        """
        Return the default data-scope value for a given dashboard field.

        This helper reads the `graph_data_scope` configuration and resolves
        whether a specific boolean field should be enabled by default
        when the dashboard is initialized.

        :param field: Name of the boolean data-scope field
        :return: bool indicating default enabled/disabled state
        """
        # Read graph data-scope configuration from dashboard initializer
        default_values = {}
        data_scope_config = self._get_dashboard_config_value(
            "graph_data_scope", {}
        )
        fields_config = data_scope_config.get("fields", {})

        if isinstance(fields_config, (list, tuple)):
            for field_config in fields_config:
                if isinstance(field_config, dict):
                    field_name = field_config.get("field")
                    if field_name:
                        default_values.update(
                            {field_name: field_config.get("default", False)}
                        )

        elif isinstance(fields_config, dict):
            field_name = fields_config.get("field")
            if field_name:
                default_values.update(
                    {field_name: fields_config.get("default", False)}
                )
            else:
                for field_name, values in fields_config.items():
                    default_values.update(
                        {field_name: values.get("default", False)}
                    )

        return default_values.get(field)

    def _get_graph_data_scope_domain(self):
        """
        Return the default data-scope value for a given dashboard field.

        This helper reads the `graph_data_scope` configuration and resolves
        whether a specific boolean field should be enabled by default
        when the dashboard is initialized.

        :param field: Name of the boolean data-scope field
        :return: bool indicating default enabled/disabled state
        """
        # Read graph data-scope configuration from dashboard initializer
        domain = []
        data_scope_config = self._get_dashboard_config_value(
            "graph_data_scope", {}
        )
        fields_config = data_scope_config.get("fields", {})

        if isinstance(fields_config, (list, tuple)):
            for field_config in fields_config:
                if isinstance(field_config, dict):
                    field_name = field_config.get("field")
                    if field_name and getattr(self, field_name):
                        domain.append(
                            self._normalize_dashboard_config_value(
                                field_config.get("domain", [])
                            )
                        )

        elif isinstance(fields_config, dict):
            field_name = fields_config.get("field")
            if field_name:
                domain.append(
                    self._normalize_dashboard_config_value(
                        fields_config.get("domain", [])
                    )
                )
            else:
                for field_name, values in fields_config.items():
                    domain.append(
                        {
                            field_name: self._normalize_dashboard_config_value(
                                values.get("domain", [])
                            )
                        }
                    )
        return fields.Domain.OR(domain)

    def _get_default_graph_operator(self):
        """
        Return the default dashboard filter operator.

        This method reads the default operator configuration used
        for combining dashboard date-period filters when no
        operator has been explicitly selected.

        Typical values include:
            - 'any' (OR behavior)
            - other values implying AND behavior
        """
        # Read default filter operator from dashboard configuration
        return (
            self._get_dashboard_config_value("graph_filter", {})
            .get("operator", {})
            .get("default")
        )

    def _onchange_graph_measure(self):
        """
        Onchange handler for graph measure selection.

        When the graph measure changes, this method updates the
        corresponding aggregator field based on the selected
        measure type to ensure correct aggregation behavior.

        - Monetary measures use 'sum_currency'
        - Other measures fall back to their configured aggregator
        """
        # Fetch resolved graph measures metadata
        graph_measures = self._graph_get_measures()
        # Get metadata for the currently selected measure
        field_values = graph_measures.get(self._get_graph_measure())
        if not field_values:
            return None
        # Monetary measures require currency-aware aggregation
        if field_values.get("type") == "monetary":
            setattr(
                self,
                self._get_graph_measure_aggregator_field(),
                "sum_currency",
            )
        else:
            # Apply default aggregator for non-monetary measures
            setattr(
                self,
                self._get_graph_measure_aggregator_field(),
                graph_measures[self._get_graph_measure()].get(
                    "aggregator", "count"
                ),
            )

    def _onchange_graph_groupby(self):
        """
        Onchange handler for dashboard group-by selection.

        This method maintains the ordered many2many representation
        of selected group-by fields so that the order chosen by the user
        is preserved and reused in graph rendering.
        """
        # Resolve configured group-by field name
        groupby_field = self._get_graph_groupby_field()
        if groupby_field:
            # Recompute and persist the ordered group-by field sequence
            setattr(
                self,
                "ordered_" + groupby_field,
                (
                    compute_many2many_order(
                        getattr(self, groupby_field).ids,
                        getattr(self, "ordered_" + groupby_field),
                    )
                ),
            )

    def _onchange_graph_filter_mq_period(self, period_field):
        """
        Onchange handler for month/quarter period selection.

        This method ensures consistency between month/quarter and year
        period selections:
            - If a month/quarter is selected without a year,
              the current year is automatically applied.
            - Any change triggers a recomputation of the custom
              dashboard filter domain.

        :param period_field: Date field key for which the period changed
        :return: None
        """
        # Resolve configured month/quarter and year period fields
        (
            mq_period_field,
            year_period_field,
        ) = self._graph_get_dashboard_mq_year_period_fields().get(period_field)
        # Read currently selected period IDs
        mq_period_ids = getattr(self, mq_period_field).ids
        year_period_ids = getattr(self, year_period_field).ids
        # Auto-select current year if month/quarter is set without a year
        if mq_period_ids and not year_period_ids:
            period_year = self.env["period.year"].search(
                [("name", "=", "year")]
            )
            setattr(self, year_period_field, [(6, 0, period_year.ids)])
        # Recompute custom filter domain after period change
        custom_filter_field = self._get_graph_custom_filter_field()
        if custom_filter_field:
            setattr(
                self,
                custom_filter_field,
                self._prepare_graph_custom_filter(),
            )

    def _onchange_graph_filter_year_period(self, period_field):
        """
        Onchange handler for year period selection.

        This method maintains valid period combinations:
            - If all year periods are removed, related month/quarter
              selections are cleared.
            - Any change triggers a recomputation of the custom
              dashboard filter domain.

        :param period_field: Date field key for which the year changed
        :return: None
        """
        # Resolve configured month/quarter and year period fields
        (
            mq_period_field,
            year_period_field,
        ) = self._graph_get_dashboard_mq_year_period_fields().get(period_field)
        year_period_ids = getattr(self, year_period_field).ids
        # Clear month/quarter periods if no year is selected
        if not year_period_ids:
            setattr(self, mq_period_field, [(6, 0, [])])
        # Recompute custom filter domain after year change
        custom_filter_field = self._get_graph_custom_filter_field()
        if custom_filter_field:
            setattr(
                self,
                custom_filter_field,
                self._prepare_graph_custom_filter(),
            )

    def _onchange_graph_data_scope(self):
        """
        Validate dashboard boolean data-scope configuration.

        Ensures that at least one dependent boolean option
        remains enabled. Prevents invalid graph states.
        """
        dependent_fields = []
        data_scope_config = self._get_dashboard_config_value(
            "graph_data_scope", {}
        )
        fields_config = data_scope_config.get("fields", {})

        if isinstance(fields_config, (list, tuple)):
            for field_config in fields_config:
                if isinstance(field_config, dict):
                    field_name = field_config.get("field")
                    if field_name:
                        dependent_fields.append(field_name)

        elif isinstance(fields_config, dict):
            field_name = fields_config.get("field")
            if field_name:
                dependent_fields.append(field_name)
            else:
                for field_name in fields_config.keys():
                    dependent_fields.append(field_name)

        warning_message = data_scope_config.get("warning")

        if dependent_fields and not any(
            getattr(self, field) for field in dependent_fields
        ):
            setattr(self, dependent_fields[0], True)
            return {
                "warning": {
                    "title": _("Error!"),
                    "message": warning_message,
                }
            }

    def _get_graph_custom_filter_field(self):
        """
        Return the field name used to store the computed custom filter domain.

        This field is defined in the dashboard initializer configuration
        and holds the dynamically generated domain based on
        selected periods and operators.

        :return: str (field name)
        """
        # Resolve custom filter field name from dashboard configuration
        self.ensure_one()
        custom_filter_config = self._get_dashboard_config_value(
            "graph_custom_filter", {}
        )
        return (
            custom_filter_config.get("field", False)
            if isinstance(custom_filter_config, dict)
            else custom_filter_config
        )

    def _get_graph_custom_filter(self):
        """
        Return the evaluated custom domain for dashboard graph queries.

        This helper safely evaluates the stored custom domain expression
        and returns it as a Python list usable by ORM searches.

        :return: list representing an ORM domain
        """
        # Read raw custom domain value from its configured field
        self.ensure_one()
        graph_custom_filter_field = self._get_graph_custom_filter_field()
        if not graph_custom_filter_field:
            return []
        graph_custom_domain = getattr(self, graph_custom_filter_field)
        # Safely evaluate domain string into a Python structure
        return literal_eval(graph_custom_domain) if graph_custom_domain else []

    def _get_graph_groups(self):
        """
        Resolve final group-by keys used in graph queries.

        This method converts selected `ir.model.fields` group-by records
        into the actual group-by expressions consumed by graph queries.

        Special handling:
            - Date-period fields are converted into their corresponding
              date aggregation keys (day / week / month / year)
            - All other fields use their technical field names

        :return: list of group-by strings
        """
        # Build final list of group-by expressions for graph queries
        graph_groups = []
        for group_by_field in self._get_graph_groupby():
            if group_by_field.ttype == "char":
                # Convert date-period field into its aggregation expression
                if group_by_field.is_date_period():
                    graph_groups.append(group_by_field.get_date_period())
                    continue
            # Use technical field name for standard group-by
            graph_groups.append(group_by_field.name)
        return graph_groups

    def _get_graph_groupby(self):
        """
        Return ordered group-by fields selected for the dashboard graph.

        This method reads the ordered many2many value storing
        selected group-by field IDs and resolves them into
        `ir.model.fields` records, preserving user-defined order.

        :return: ir.model.fields recordset
        """
        # Resolve configured group-by field name
        groupby_field = self._get_graph_groupby_field()
        if not groupby_field:
            return self.env["ir.model.fields"].browse([])
        # Parse ordered many2many IDs stored as a comma-separated string
        ordered_groupby = getattr(
            self,
            "ordered_" + groupby_field,
        )
        ordered_groupby_ids = (
            map(
                int,
                ordered_groupby.split(","),
            )
            if ordered_groupby
            else []
        )
        return self.env["ir.model.fields"].browse(list(ordered_groupby_ids))

    def _get_graph_data_field(self):
        """
        Return the primary data field used for graph aggregation.

        This field is defined in the dashboard initializer configuration
        and usually represents a date or datetime field used to
        filter and group graph data.

        :return: str (field name)
        """
        self.ensure_one()
        # Resolve graph data field from dashboard configuration
        return self._get_dashboard_config_value("graph_data_field")

    def _get_graph_primary_button_title(self):
        """
        Return the resolved title for the primary dashboard action button.

        The configuration value may be:
            - A static string
            - A callable (e.g., lambda self: ...) returning a string

        If the value is callable, it is executed with the current record.
        Otherwise, the static value is returned as-is.

        :return: str
        """
        self.ensure_one()

        button_title_config = self._get_dashboard_config_value(
            "graph_primary_button_title",
            _("Big Pretty Button :)"),
        )
        return self._normalize_dashboard_config_value(button_title_config)

    def _get_graph_config_form_view_ref(self):
        """
        Build the XML ID reference for the dashboard configuration form view.

        The final view reference is composed dynamically using:
            - Current dashboard initializer
            - Configured form view reference suffix

        :return: str (full XML ID of form view)
        """
        self.ensure_one()
        # Compose full XML ID using initializer and configured view reference
        return "%s.%s" % (
            self.env.context.get("initializer"),
            self._get_dashboard_config_value("graph_config_form_view_ref"),
        )

    def get_graph_config_form_view_ref(self):
        """
        Public helper to retrieve the dashboard configuration form view reference.

        This method enriches the execution context with required values
        (initializer, timezone offset, etc.) before delegating to the
        internal resolver.

        :return: str (full XML ID of form view)
        """
        # Ensure required context keys are present for view resolution
        self = self.with_context(
            initializer=self.env.context.get("initializer"),
            webclient_tz_offset=self.env.context.get("webclient_tz_offset"),
        )
        return self._get_graph_config_form_view_ref()


def build_dashboard_onchange(config):
    """
    Generate onchange methods for a dashboard initializer config.

    This factory method eliminates boilerplate by creating all
    required ``@api.onchange`` handler methods from the config dict.
    """
    methods = {}

    # ── Filter operator onchange ──────────────────────────
    filter_cfg = config.get("graph_filter", {})
    operator_cfg = filter_cfg.get("operator", {})
    op_field = (
        operator_cfg.get("field") if isinstance(operator_cfg, dict) else None
    )
    if op_field:
        method_name = f"_onchange_{op_field}"

        def _make_op_handler():
            @api.onchange(op_field)
            def handler(self):
                self._onchange_graph_filter_operator()

            return handler

        methods[method_name] = _make_op_handler()

    # ── Date period onchanges (mq_period + year_period) ───
    fields_cfg = filter_cfg.get("fields", {})
    for date_field, periods in fields_cfg.items():
        mq_field = (
            periods.get("mq_period", {}).get("field")
            if isinstance(periods.get("mq_period"), dict)
            else periods.get("mq_period")
        )
        yr_field = (
            periods.get("year_period", {}).get("field")
            if isinstance(periods.get("year_period"), dict)
            else periods.get("year_period")
        )

        if mq_field:
            mname = f"_onchange_{mq_field}"

            def _make_mq(df=date_field, fld=mq_field):
                @api.onchange(fld)
                def handler(self):
                    self._onchange_graph_filter_mq_period(df)

                return handler

            methods[mname] = _make_mq()

        if yr_field:
            mname = f"_onchange_{yr_field}"

            def _make_yr(df=date_field, fld=yr_field):
                @api.onchange(fld)
                def handler(self):
                    self._onchange_graph_filter_year_period(df)

                return handler

            methods[mname] = _make_yr()

    # ── Measure onchange ──────────────────────────────────
    measure_cfg = config.get("graph_measure", {})
    measure_field = (
        measure_cfg.get("field") if isinstance(measure_cfg, dict) else None
    )
    if measure_field:
        mname = f"_onchange_{measure_field}"

        def _make_measure(fld=measure_field):
            @api.onchange(fld)
            def handler(self):
                self._onchange_graph_measure()

            return handler

        methods[mname] = _make_measure()

    # ── Groupby onchange ──────────────────────────────────
    groupby_cfg = config.get("graph_groupby", {})
    groupby_field = (
        groupby_cfg.get("field") if isinstance(groupby_cfg, dict) else None
    )
    if groupby_field:
        mname = f"_onchange_{groupby_field}"

        def _make_groupby(fld=groupby_field):
            @api.onchange(fld)
            def handler(self):
                self._onchange_graph_groupby()

            return handler

        methods[mname] = _make_groupby()

    # ── Data scope onchange ───────────────────────────────
    scope_cfg = config.get("graph_data_scope", {})
    scope_fields_cfg = scope_cfg.get("fields", [])
    scope_field_names = []
    if isinstance(scope_fields_cfg, list):
        for fc in scope_fields_cfg:
            if isinstance(fc, dict) and fc.get("field"):
                scope_field_names.append(fc["field"])
    elif isinstance(scope_fields_cfg, dict):
        fname = scope_fields_cfg.get("field")
        if fname:
            scope_field_names.append(fname)

    if scope_field_names:
        mname = f"_onchange_{scope_field_names[0]}"

        def _make_scope(flds=tuple(scope_field_names)):
            @api.onchange(*flds)
            def handler(self):
                return self._onchange_graph_data_scope()

            return handler

        methods[mname] = _make_scope()

    return methods
