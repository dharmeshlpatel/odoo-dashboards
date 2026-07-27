# -*- coding: utf-8 -*-
import logging
import time
from odoo import models, api, tools
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Schema for config validation (dev mode only)
REQUIRED_CONFIG_KEYS = {
    "graph_model",
    "graph_data_field",
}
OPTIONAL_CONFIG_KEYS = {
    "graph_measure",
    "graph_groupby",
    "graph_filter",
    "graph_custom_filter",
    "graph_data_scope",
    "graph_config_form_view_ref",
    "graph_primary_button_title",
    "graph_my_data_field",
    "graph_with_analytics_field",
    "actions",
    "dashboard_graph_type",
    "extra_join_sql_conditions",
}


class BaseDashboardMixin(models.AbstractModel):
    _name = "base.dashboard.mixin"
    _description = "Base Dashboard Mixin"

    @property
    def initializer(self):
        """
        Resolve the active dashboard initializer configuration.

        The dashboard initializer determines which configuration set
        should be used for the current dashboard instance.

        Resolution order:
            1. Explicitly provided context key `initializer`
            2. Fallback to context key `module`
            3. Infer from the form view reference (module prefix)

        This mechanism allows multiple dashboards to reuse the same
        mixin while providing different behaviors and UI configurations
        through initializer-based dictionaries.

        :return: dict containing dashboard-specific configuration
        """
        # Read execution context to determine active dashboard initializer
        context = self.env.context
        # Determine initializer from context or infer it from form view reference
        return (
            context.get("initializer")
            or context.get("module")
            or (context.get("form_view_ref", "").split(".", 1)[0] or None)
        )

    def _dashboard_initializer(self):
        return {}

    def _dashboard_config_initializer(self):
        """
        Hook method returning all available dashboard initializer configurations.

        Each key in the returned dictionary represents a dashboard initializer
        name, and its value is a configuration dictionary defining:
            - graph model
            - graph measures
            - group-by behavior
            - filter fields and operators
            - UI-related options

        This method is intentionally designed to be overridden by
        dashboard-specific modules.

        :return: dict mapping initializer names to configuration dictionaries
        """
        return {}

    def _validate_config(self, config, initializer_name):
        """
        Validate config dict keys in dev mode only.

        Reports unknown and missing required keys as warnings
        to help catch typos during development.
        """
        if not tools.config.get("dev_mode"):
            return
        all_known = REQUIRED_CONFIG_KEYS | OPTIONAL_CONFIG_KEYS
        unknown = set(config.keys()) - all_known
        if unknown:
            _logger.warning(
                "Dashboard initializer %r has unknown " "config keys: %s",
                initializer_name,
                unknown,
            )
        missing = REQUIRED_CONFIG_KEYS - set(config.keys())
        if missing:
            _logger.warning(
                "Dashboard initializer %r is missing " "required keys: %s",
                initializer_name,
                missing,
            )

    def _get_dashboard_eval_context(self):
        """Evaluation context for dashboard-related expressions."""
        return {
            "self": self,
            "active_id": self.id,
            "active_ids": self.ids,
            "uid": self.env.user.id,
            "user": self.env.user,
            "env": self.env,
            "time": time,
        }

    def _normalize_dashboard_config_value(self, value):
        """
        Normalize dashboard configuration values.

        Supports:
        - Callable values (resolved by executing with self)
        - String expressions (evaluated safely using dashboard context)
        - Static values (returned as-is)
        """
        # Callable → execute safely
        if callable(value):
            try:
                return value(self)
            except Exception:
                return False

        # String → evaluate safely
        if isinstance(value, str):
            try:
                return safe_eval(value, self._get_dashboard_eval_context())
            except Exception:
                return value

        # Static value
        return value


    def _get_dashboard_config_initializer(self):
        """
        Resolve and merge dashboard configurations.

        Returns the configuration for the active initializer, but merges
        'actions' and 'user_prefs' from ALL available initializers on the
        model. This allows actions (buttons, links, reports) from one
        dashboard (e.g., Sales) to be accessible from another (e.g., CRM)
        automatically.
        """
        context = self.env.context
        initializer = self.initializer

        if not initializer:
            _logger.debug(
                "Dashboard initializer not found in context: %s",
                context,
            )

        # Gather all available initializers from the inheritance chain
        all_initializers = {
            **self._dashboard_initializer(),
            **self._dashboard_config_initializer(),
        }

        # Start with the active initializer's configuration
        active_config = all_initializers.get(initializer, {}).copy()

        # ── Cross-Dashboard Action Merging ────────────────────────────
        # We want actions from other dashboards to be visible/usable here.
        merged_actions = active_config.get("actions", {}).copy()
        merged_prefs = active_config.get("user_prefs", {}).copy()

        for init_name, other_cfg in all_initializers.items():
            if init_name == initializer:
                continue

            # Merge actions
            other_actions = other_cfg.get("actions", {})
            for section, section_cfg in other_actions.items():
                if not isinstance(section_cfg, dict):
                    continue

                if section not in merged_actions:
                    merged_actions[section] = section_cfg.copy()
                    continue

                if not isinstance(merged_actions[section], dict):
                    continue

                # Deep merge for specific nested sections (e.g., menu)
                if section == "menu":
                    for sub_sec, sub_cfg in section_cfg.items():
                        if not isinstance(sub_cfg, dict):
                            continue
                        if sub_sec not in merged_actions[section]:
                            merged_actions[section][sub_sec] = sub_cfg.copy()
                        elif isinstance(
                            merged_actions[section][sub_sec], dict
                        ):
                            # Merge individual menu items (views, new, reports)
                            for key, action_cfg in sub_cfg.items():
                                if key not in merged_actions[section][sub_sec]:
                                    merged_actions[section][sub_sec][
                                        key
                                    ] = action_cfg
                else:
                    # Shallow merge for other sections (primary_right, bottom_block)
                    for key, action_cfg in section_cfg.items():
                        if key not in merged_actions[section]:
                            merged_actions[section][key] = action_cfg

            # Merge user_prefs
            other_prefs = other_cfg.get("user_prefs", {})
            for pref_key, pref_cfg in other_prefs.items():
                if pref_key not in merged_prefs:
                    merged_prefs[pref_key] = pref_cfg

        active_config["actions"] = merged_actions
        active_config["user_prefs"] = merged_prefs

        # Validate config structure in dev mode
        if active_config:
            self._validate_config(active_config, initializer)

        return active_config

    def _get_dashboard_config_value(self, key, default=None):
        """
        Shortcut to fetch a specific dashboard initializer value.

        Args:
            key (str): Configuration key.
            default: Default value if key not found.

        Returns:
            Any: Configuration value.
        """
        return self._get_dashboard_config_initializer().get(key, default)

    @api.model
    def _get_dashboard_action_config(self, section, *keys):
        """
        Resolve a nested dashboard action/compute config.

        Traverses the ``actions`` config using *section*
        and optional *keys* to locate the right action node.

        **Nesting scheme**::

            actions/
            ├─ primary_left/
            │   └─ primary_button/
            │       ├─ crm_enterprise   ← 3 keys
            │       └─ report_crm_team
            ├─ primary_right/
            │   ├─ open_opportunity     ← 2 keys
            │   └─ overdue_opportunity
            ├─ bottom_block/
            │   ├─ crm_lead_opportunities
            │   └─ schedule_meetings
            └─ menu/
                ├─ views/
                │   ├─ lead             ← 3 keys
                │   └─ opportunity
                ├─ new/ ...
                └─ reports/ ...

        **Consumer usage**::

            # 2-key access
            self._get_dashboard_action(
                "primary_right", "open_opportunity"
            )
            # 3-key access
            self._get_dashboard_action(
                "menu", "reports", "lead"
            )

        :param section: Top-level section key
        :param keys: Sub-keys to traverse
        :return: Config dict or ``{}`` if not found
        """
        actions_cfg = self._get_dashboard_config_value("actions") or {}
        current = actions_cfg.get(section, {})
        # Traverse nested structure
        for key in keys:
            if not isinstance(current, dict):
                return {}
            current = current.get(key, {})
        return current if isinstance(current, dict) else {}

    @api.model
    def _get_graph_model(self):
        """
        Resolve the graph model name from the active dashboard initializer.

        Tries ``_get_dashboard_config_value("graph_model")`` — falls back
        to ``self._name`` if not configured.

        :return: Technical model name string
        """
        model = self._get_dashboard_config_value("graph_model")
        if not model:
            _logger.debug(
                "No graph_model configured for %s — using self._name",
                self._name,
            )
        return model or self._name

    def _get_graph_my_data_field(self):
        """Return the boolean field name controlling 'My Data' filtering."""
        return self._get_dashboard_config_value("graph_my_data_field")

    def _get_graph_with_analytics_field(self):
        """Return the boolean field name controlling 'With Analytics' filtering."""
        return self._get_dashboard_config_value("graph_with_analytics_field")

    def _get_my_data_domain(self):
        """
        Returns a domain that restricts records to those owned by
        the current user via the ``user_id`` field.
        """
        return [("user_id", "=", self.env.uid)]

    def _get_dashboard_hierarchy_domain(self, relation_field="id"):
        """
        Build a domain for expanding child IDs for hierarchy awareness.
        If the dashboard model has a parent_id field, return a domain
        to match records belonging to self and its children.

        Args:
            relation_field (str): The field on the target model to map the hierarchy to.
                                  Defaults to "id".
        """
        if "parent_id" in self._fields:
            return [(relation_field, "child_of", self.ids)]
        return []
