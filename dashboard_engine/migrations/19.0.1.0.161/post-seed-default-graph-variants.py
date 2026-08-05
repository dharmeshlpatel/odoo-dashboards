# -*- coding: utf-8 -*-
"""Backfill Default chart-model options for every blueprint that has a chart.

Registers ``ir.model.data`` xmlids matching each pack's ``seed_graph_variants.xml``
so later module upgrades do not create duplicate rows.

Also restores Pipeline ``primary_action_context`` on CRM / Customer 360 defaults
(older seeds used ``{}`` and sync wiped the blueprint context).
"""
import logging

_logger = logging.getLogger(__name__)

_LEAD_CTX = (
    '{"default_type": {"__de__": "group_value", "default": "opportunity", '
    '"map": [{"groups": ["crm.group_use_lead"], "value": "lead"}]}}'
)

# Historical xmlids (keep stable; do not rename).
_SPECIAL_XMLIDS = {
    ("crm_customer_dashboard.blueprint_crm_customers", "crm.lead"): (
        "crm_customer_dashboard",
        "graph_variant_crm_lead",
    ),
    ("crm_customer_dashboard.blueprint_crm_customers", "sale.order"): (
        "crm_customer_dashboard",
        "graph_variant_sale_order",
    ),
    ("customer_360_dashboard.blueprint_customer_360", "crm.lead"): (
        "customer_360_dashboard",
        "graph_variant_c360_lead",
    ),
    ("customer_360_dashboard.blueprint_customer_360", "sale.order"): (
        "customer_360_dashboard",
        "graph_variant_c360_sale",
    ),
}


def _variant_xmlid(bp_xmlid, graph_model):
    special = _SPECIAL_XMLIDS.get((bp_xmlid, graph_model))
    if special:
        return special
    module, local = bp_xmlid.split(".", 1)
    short = local.replace("blueprint_", "", 1)
    model_slug = (graph_model or "").replace(".", "_")
    return module, f"graph_variant_{short}_{model_slug}"


def _ensure_xmlid(env, module, name, record):
    Data = env["ir.model.data"].sudo()
    existing = Data.search(
        [("module", "=", module), ("name", "=", name)],
        limit=1,
    )
    if existing:
        if existing.model != record._name or existing.res_id != record.id:
            existing.write({"model": record._name, "res_id": record.id})
        return existing
    return Data.create(
        {
            "module": module,
            "name": name,
            "model": record._name,
            "res_id": record.id,
            "noupdate": True,
        }
    )


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception("default graph variants: cannot build environment")
        return

    Variant = env["dashboard.blueprint.graph.variant"].sudo()
    Blueprint = env["dashboard.blueprint"].sudo()

    created = 0
    bound = 0
    for bp in Blueprint.search([("graph_model", "!=", False)]):
        graph_model = (bp.graph_model or "").strip()
        action = (bp.primary_action_xmlid or "").strip()
        if not graph_model or not action:
            continue

        bp_xmlid = bp.get_external_id().get(bp.id)
        if not bp_xmlid:
            continue

        if not bp.graph_variant_ids:
            vals = {
                "blueprint_id": bp.id,
                "sequence": 10,
                "is_default": True,
                "graph_model": graph_model,
                "graph_data_field": bp.graph_data_field or False,
                "primary_button_label": bp.primary_button_label or "Open",
                "primary_action_xmlid": action,
                "primary_action_context": bp.primary_action_context or "{}",
            }
            # Prefer rich lead context when blueprint still has empty {}
            # but this is a known Pipeline board (CRM Customers / C360).
            if graph_model == "crm.lead" and (
                bp_xmlid.endswith(".blueprint_crm_customers")
                or bp_xmlid.endswith(".blueprint_customer_360")
            ):
                vals["primary_action_context"] = _LEAD_CTX
            variant = Variant.create(vals)
            created += 1
            module, name = _variant_xmlid(bp_xmlid, graph_model)
            _ensure_xmlid(env, module, name, variant)
            bound += 1
            continue

        # Bind xmlids on existing rows (migration/heal) so pack XML is stable.
        for variant in bp.graph_variant_ids:
            module, name = _variant_xmlid(bp_xmlid, variant.graph_model)
            if env.ref(f"{module}.{name}", raise_if_not_found=False):
                continue
            _ensure_xmlid(env, module, name, variant)
            bound += 1

        if not bp.graph_variant_ids.filtered("is_default"):
            match = bp.graph_variant_ids.filtered(
                lambda v: v.graph_model == bp.graph_model
            )[:1]
            target = match or bp.graph_variant_ids.sorted("sequence")[:1]
            if target:
                bp._studio_mark_default_graph_variant(target)

    healed_ctx = 0
    for module, name in (
        ("crm_customer_dashboard", "graph_variant_crm_lead"),
        ("customer_360_dashboard", "graph_variant_c360_lead"),
    ):
        variant = env.ref(f"{module}.{name}", raise_if_not_found=False)
        if not variant:
            continue
        if (variant.primary_action_context or "").strip() in ("", "{}"):
            variant.write({"primary_action_context": _LEAD_CTX})
            healed_ctx += 1
            if variant.is_default:
                variant.blueprint_id._sync_blueprint_from_default_variant()

    for bp in Blueprint.search([("graph_model", "=", "crm.lead")]):
        default = bp.graph_variant_ids.filtered("is_default")[:1]
        if not default:
            continue
        bp_ctx = (bp.primary_action_context or "").strip()
        var_ctx = (default.primary_action_context or "").strip()
        if bp_ctx and bp_ctx != "{}" and var_ctx in ("", "{}"):
            default.write({"primary_action_context": bp_ctx})
            bp._sync_blueprint_from_default_variant()
            healed_ctx += 1
        elif var_ctx and var_ctx != "{}" and bp_ctx in ("", "{}"):
            bp._sync_blueprint_from_default_variant()

    _logger.info(
        "default graph variants: created=%s xmlids_bound=%s healed_context=%s",
        created,
        bound,
        healed_ctx,
    )
