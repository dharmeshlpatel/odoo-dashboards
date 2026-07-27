# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Base Dashboard Compute Mixin
============================

Provides a reusable, generic engine for computing aggregated dashboard
metrics (counts, amounts, etc.) from any Odoo model.

Design goals:
- Model-agnostic: works with crm.lead, sale.order, pos.order, etc.
- Hierarchy-aware: propagates results up parent_id chains
- Context-aware: supports application-specific domain injection via hooks
- Config-driven: can read ``compute`` blocks from ``_dashboard_graph_initializer``
  and execute them generically — no per-field ORM code needed
- Consistent interface: ``compute_fields`` is always a dict mapping
  aggregate spec → destination field name
- Extensible: override ``_apply_context_domain()`` per application module

────────────────────────────────────────────────────────────────────────
USAGE — Option A: call the engine directly (explicit API)
────────────────────────────────────────────────────────────────────────

    def _compute_open_opportunities(self):
        self.with_context(dashboard_rendering=True)._compute_grouped_dashboard_data(
            model="crm.lead",
            extra_domain=[
                ("type", "=", "opportunity"),
                ("probability", "<", 100),
                ("active", "=", True),
            ],
            aggregates=["expected_revenue:sum", "__count"],
            compute_fields={
                "__count": "opportunities_count",
                "expected_revenue:sum": "opportunities_amount",
            },
        )

────────────────────────────────────────────────────────────────────────
USAGE — Option B: drive from _dashboard_graph_initializer config (recommended)
────────────────────────────────────────────────────────────────────────

    # In res.partner (or any model inheriting this mixin):
    def _compute_open_opportunities(self):
        self._compute_dashboard_action_fields(
            section="primary_right",
            action_key="open_opportunity",
        )

    # In _dashboard_graph_initializer the ``compute`` block is:
    #   "open_opportunity": {
    #       "compute": {
    #           "fields": [
    #               {
    #                   "model": "",          # "" → use graph_model
    #                   "relational_field": "",  # optional join field
    #                   "field": "opportunities_count",
    #                   "aggregator": "__count",
    #                   "domain": lambda self: [],
    #                   "conditional_domain": {
    #                       "my_pipeline": {           # user boolean flag
    #                           "domain": lambda self: [("user_id", "=", self.env.uid)]
    #                       },
    #                   },
    #               },
    #               {
    #                   "field": "opportunities_amount",
    #                   "aggregator": "expected_revenue:sum",
    #                   ...
    #               },
    #           ]
    #       }
    #   }
"""

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class BaseDashboardComputeMixin(models.AbstractModel):
    """
    Abstract mixin providing a generic, reusable ORM-based engine
    to compute aggregated dashboard metrics on any Odoo model.

    This mixin is intended to be inherited by dashboard-specific
    models (e.g. res.partner, res.users, crm.team) that need to
    display aggregated values such as counts, sums, and averages.

    Key responsibilities
    -------------------
    - Resolve the grouping field from user dashboard configuration
    - Handle parent/child hierarchies (e.g. partner companies)
    - Inject context-based domain filters via ``_apply_context_domain``
    - Execute ORM ``read_group`` queries and propagate results
    - Drive the entire compute from ``_dashboard_graph_initializer`` config
      so individual compute methods become one-liners

    Override hooks
    ---------------
    - ``_compute_on()``:           field name to group graph data by
    - ``_apply_context_domain()``: inject app-specific domain conditions
    """

    _name = "base.dashboard.compute.mixin"
    _description = "Base Dashboard Compute Mixin"

    # ------------------------------------------------------------------
    # Config-driven engine  (preferred — reads initializer compute block)
    # ------------------------------------------------------------------

    def _compute_dashboard_action_fields(
        self, section, *keys, expected_fields=None
    ):
        """
                Generic engine that reads the ``compute`` block from
        ``_dashboard_graph_initializer`` and executes it.

        This is the **recommended public API** for compute methods.
        Instead of hard-coding domain + aggregate logic in every compute
        method, declare it once in ``_dashboard_graph_initializer`` under
        the matching action's ``compute`` key and call this helper.

        The ``compute`` block schema::

            "compute": {
                "fields": [
                    {
                        # Required
                        "field":      "opportunities_count",  # dest field on self
                        "aggregator": "__count",              # ORM aggregate spec

                        # Optional — model resolution
                        "model":            "",  # "" or None → use graph_model
                        "relational_field": "",  # join field override (rare)

                        # Optional — domain
                        "domain": lambda self: [],           # base domain lambda
                        "conditional_domain": {
                            # user boolean flag name → extra domain lambda
                            "my_pipeline": {
                                "domain": lambda self: [
                                    ("user_id", "=", self.env.uid)
                                ]
                            },
                        },
                    },
                    # … more field specs …
                ]
            }

        :param action_key: Key inside the section dict, e.g.
            ``"open_opportunity"``, ``"unassigned_lead_opportunity"``
        :param section: Section inside ``actions``, e.g.
            ``"primary_right"``, ``"bottom_block"``
        :return: None
        """
        self = self.with_context(dashboard_rendering=True)
        # ── Resolve the compute config block ──────────────────────────
        action_cfg = self._get_dashboard_action_config(section, *keys)
        compute_cfg = action_cfg.get("compute", {})
        field_specs = compute_cfg.get("fields", [])
        if not field_specs:
            if expected_fields:
                _logger.debug(
                    "Config missing for %s/%s. Zero-filling: %s",
                    section,
                    keys,
                    expected_fields,
                )
                for field in expected_fields:
                    self[field] = 0
            return

        # ── Resolve the fallback graph model ──────────────────────────
        graph_model = self._get_graph_model()

        # ── Resolve the default group_field once (avoids repeated calls)
        default_group_field = self._compute_on()

        # ── Group field specs by (resolved_model, resolved_group_field)
        #    so we run one read_group per unique (model × join-field)
        #    combination instead of one per destination field.
        #
        #    IMPORTANT: we resolve both values here — never use the raw
        #    empty-string values as a key, because "" and "" look the
        #    same even when they would resolve to different models or
        #    group fields on different record-sets.
        # bucket key: (resolved_model_name, resolved_group_field)
        buckets = {}
        for spec in field_specs:
            if "value" in spec:
                dest_field = spec.get("field")
                value_fn = spec.get("value")
                if dest_field:
                    for record in self:
                        if callable(value_fn):
                            setattr(record, dest_field, value_fn(self, record))
                        else:
                            setattr(record, dest_field, value_fn)
                continue

            resolved_model = spec.get("model") or graph_model
            resolved_group_field = (
                spec.get("relational_field") or default_group_field
            )
            bucket_key = (resolved_model, resolved_group_field)
            buckets.setdefault(bucket_key, []).append(spec)

        # ── Execute one batched read_group per unique bucket ───────────
        for (resolved_model, resolved_group_field), specs in buckets.items():
            _logger.debug(
                "Dashboard compute bucket: model=%s, group=%s, specs=%s",
                resolved_model,
                resolved_group_field,
                specs,
            )
            self._compute_bucket(
                model_name=resolved_model,
                group_field=resolved_group_field,
                field_specs=specs,
            )

    def _compute_bucket(self, model_name, group_field, field_specs):
        """
        Execute one batched ``read_group`` for field specs that share
        the same resolved model and group field.

        Specs within the same bucket may still have different domains,
        so they are further sub-grouped by their resolved domain string.
        Each unique domain produces exactly one ``read_group`` call,
        and all aggregates sharing that domain are fetched in one shot.

        :param model_name: Fully resolved technical model name
                           (e.g. ``"crm.lead"``). Never empty — the
                           caller resolves ``""`` to ``graph_model``.
        :param group_field: Fully resolved grouping field name
                            (e.g. ``"partner_id"``). Never empty — the
                            caller resolves ``""`` to ``_compute_on()``.
        :param field_specs: List of field spec dicts from ``compute.fields``
        :return: None
        """
        has_parent = "parent_id" in self._fields
        # ── Expand child IDs for hierarchy awareness ───────────────────
        domain = self._get_dashboard_hierarchy_domain()
        if domain:
            all_objects = self.with_context(active_test=False).search(domain)
        else:
            all_objects = self

        # ── Reset destination fields to zero before computing ──────────
        for record in self:
            for spec in field_specs:
                dest_field = spec.get("field")
                if dest_field and dest_field in record._fields:
                    record[dest_field] = 0

        # ── Group specs by their resolved domain so we batch queries ───
        # domain_key → list of (aggregate_spec, dest_field)
        domain_groups = {}
        for spec in field_specs:
            resolved_domain = self._resolve_spec_domain(
                spec, all_objects, group_field
            )
            # Use a frozenset of the repr as a hashable cache key
            domain_key = repr(resolved_domain)
            domain_groups.setdefault(
                domain_key,
                {
                    "domain": resolved_domain,
                    "agg_map": {},  # aggregate_spec → dest_field
                },
            )
            agg_spec = spec.get("aggregator", "__count")
            dest_field = spec.get("field", "")
            domain_groups[domain_key]["agg_map"][agg_spec] = dest_field

        # ── Run one read_group per unique domain ───────────────────────
        model_env = self.env[model_name].with_context(active_test=False)
        for domain_info in domain_groups.values():
            domain = domain_info["domain"]
            agg_map = domain_info["agg_map"]  # {aggregate_spec: dest_field}

            # Inject app-specific context domain (override hook)
            domain = self._apply_context_domain(domain, model_name)

            grouped_data = model_env.formatted_read_group(
                domain=domain,
                groupby=[group_field],
                aggregates=list(agg_map.keys()),
            )
            _logger.debug(
                "Dashboard read_group result: data=%s, group=%s, "
                "agg_map=%s, has_parent=%s",
                grouped_data,
                group_field,
                agg_map,
                has_parent,
            )
            self._propagate_group_results(
                grouped_data=grouped_data,
                group_field=group_field,
                agg_map=agg_map,
                has_parent=has_parent,
            )

    def _resolve_spec_domain(self, spec, all_objects, group_field):
        """
        Build the full ORM domain for a single field spec by combining:

        1. The base group filter: ``(group_field, "in", all_objects.ids)``
        2. The spec's base ``domain`` lambda (called with ``self``)
        3. Any ``conditional_domain`` entries whose user boolean flag is True

        :param spec: Field spec dict from ``compute.fields``
        :param all_objects: Recordset of IDs to include (incl. children)
        :param group_field: The field name used for grouping
        :return: ORM domain list
        """
        domain = [(group_field, "in", all_objects.ids)]

        # Base domain lambda
        base_domain_fn = spec.get("domain")
        if callable(base_domain_fn):
            try:
                extra = base_domain_fn(self)
                if extra:
                    domain.extend(list(extra))
            except Exception as e:
                _logger.warning(
                    "dashboard compute: error evaluating base domain for "
                    "field %r: %s",
                    spec.get("field"),
                    e,
                )

        # Conditional domain — applied when user has the flag enabled
        conditional = spec.get("conditional_domain") or {}
        for flag_name, cond_cfg in conditional.items():
            flag_value = getattr(self.env.user, flag_name, False)
            if not flag_value:
                continue
            cond_fn = cond_cfg.get("domain")
            if callable(cond_fn):
                try:
                    cond_extra = cond_fn(self)
                    if cond_extra:
                        domain.extend(list(cond_extra))
                except Exception as e:
                    _logger.warning(
                        "dashboard compute: error evaluating conditional "
                        "domain for flag %r on field %r: %s",
                        flag_name,
                        spec.get("field"),
                        e,
                    )

        return domain

    def _propagate_group_results(
        self, grouped_data, group_field, agg_map, has_parent
    ):
        """
        Assign grouped ORM results back to the matching records,
        propagating counts up the parent hierarchy when applicable.

        :param grouped_data: Raw ``read_group`` result list
        :param group_field: Field that was grouped by
        :param agg_map: Dict mapping aggregate spec → destination field name
        :param has_parent: Whether ``self._fields`` has ``parent_id``
        :return: None
        """
        # Pre-compute ID set for O(1) membership checks
        self_ids = set(self.ids)

        for group in grouped_data:
            group_key = group.get(group_field)
            if not group_key:
                continue

            # many2one fields are returned as (id, display_name) tuples
            record_id = (
                group_key[0]
                if isinstance(group_key, (list, tuple))
                else group_key
            )
            record = self.browse(record_id)

            while record:
                if record.id in self_ids:
                    for agg_spec, dest_field in agg_map.items():
                        if not dest_field or dest_field not in record._fields:
                            continue
                        value = group.get(agg_spec, 0) or 0
                        record[dest_field] += value
                record = record.parent_id if has_parent else self.browse()

    # ------------------------------------------------------------------
    # Override hooks
    # ------------------------------------------------------------------

    def _compute_on(self):
        """
        Return the field name used to group dashboard data.

        By default, this delegates to the current user's dashboard
        configuration (``graph_data_field``).

        Override in specific modules when the grouping field differs
        per application context (e.g. ``team_id``, ``user_id``).

        :param config: Optional pre-resolved config dict
        :return: Field name string (e.g. ``"partner_id"``)
        """
        return self.env.user._get_graph_data_field()

    def _apply_context_domain(self, domain, model=None):
        """
        Hook to inject application-specific domain conditions.

        This method is called after the base domain is constructed
        and before the ORM query is executed.

        The base implementation returns the domain unchanged.
        Override this in specific application modules to inject
        context-based filters such as:
        - User-scoped data (``my_pipeline``, ``my_order``)
        - App-specific field conditions (website_id, pos_config_id)

        :param domain: Current ORM domain list
        :param model: Technical model name being queried (optional hint)
        :return: Modified ORM domain list
        """
        return domain
