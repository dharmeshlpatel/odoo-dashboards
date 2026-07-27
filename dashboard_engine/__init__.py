# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Dynamic Dashboard Engine module initialization.
"""

from . import models  # noqa: F401

# Odoo discovers tests/ automatically when --test-tags / --test-enable is used.


def _ensure_soft_host_blueprints(env):
    """Legacy no-op — product/warehouse/POS/Website presets ship as Apps packs."""
    return


def _ensure_warehouse_blueprint(env):
    """ Backward-compatible alias. """
    _ensure_soft_host_blueprints(env)


def post_init_hook(env):
    """Sync published blueprints after engine install/upgrade."""
    Blueprint = env["dashboard.blueprint"].sudo()
    for bp in Blueprint.search([("state", "=", "published")]):
        bp._sync_generated_artifacts()


# Backwards-compatible alias used by legacy packs during migration window
POST_INIT_COMPUTE_METHODS = (
    "_compute_default_graph_measure",
    "_compute_default_graph_groupby",
)


def _post_init_hook(env, initializer):
    """Legacy per-app post-init (kept for temporary compatibility)."""
    fields_model = env["ir.model.fields"]
    graph_parameter_model = env["dashboard.graph_parameter"]
    users_env = env["res.users"].with_context(initializer=initializer).sudo()
    graph_model = users_env._get_graph_model()
    graph_parameter_model.set_param(graph_model)
    date_field_values = fields_model._get_date_field_values_from_field(graph_model)
    if date_field_values:
        created_fields = fields_model.create(date_field_values)
        fields_model._set_company_defaults(graph_model, created_fields)
    all_users = users_env.search([])
    for method_name in POST_INIT_COMPUTE_METHODS:
        getattr(all_users, method_name)()
