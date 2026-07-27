# -*- coding: utf-8 -*-
"""Refresh existing salesperson seed rows after customer-parity expand.

noupdate XML creates new xmlids but does not rewrite existing ones — push
field updates for the thin Phase A slots/scopes/blueprint here.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env.ref(
        "crm_salesperson_dashboard.blueprint_crm_salespersons",
        raise_if_not_found=False,
    )
    if not bp:
        _logger.info("post-expand-salesperson-parity: blueprint missing, skip")
        return

    pipeline = env.ref(
        "crm_salesperson_dashboard.scope_crm_sp_pipeline",
        raise_if_not_found=False,
    )
    bp.write(
        {
            "primary_button_label": "Pipeline Analysis",
            "primary_label_alt": "Leads Analysis",
            "primary_label_alt_scope_id": pipeline.id if pipeline else False,
            "graph_data_field": "user_id",
            "graph_groupby": "stage_id",
            "include_child_records": False,
            "header_title_field": "name",
            "header_image_field": "image_128",
            "header_image_style": "avatar",
        }
    )

    open_slot = env.ref(
        "crm_salesperson_dashboard.slot_crm_sp_open", raise_if_not_found=False
    )
    if open_slot:
        open_slot.write(
            {
                "action_domain": (
                    "[('type', '=', 'opportunity'), ('probability', '<', 100),"
                    " ('active', '=', True), ('user_id', '=', '{{id}}')]"
                ),
                "action_context": (
                    '{"default_type": "opportunity", "default_user_id": {{id}}}'
                ),
                "module_depends": "crm",
            }
        )

    bottom = env.ref(
        "crm_salesperson_dashboard.slot_crm_sp_bottom", raise_if_not_found=False
    )
    if bottom:
        bottom.write(
            {
                "groups_xmlids": "sales_team.group_sale_salesman",
                "action_domain": (
                    "[('user_id', '=', '{{id}}'), ('type', '=', 'opportunity')]"
                ),
                "action_context": (
                    '{"search_default_user_id": [{{id}}],'
                    ' "default_user_id": {{id}}, "default_type": "opportunity"}'
                ),
                "module_depends": "crm,sales_team",
            }
        )

    view_opp = env.ref(
        "crm_salesperson_dashboard.slot_crm_sp_menu_opportunities",
        raise_if_not_found=False,
    )
    if view_opp:
        view_opp.write(
            {
                "sequence": 20,
                "action_domain": "[('user_id', '=', '{{id}}')]",
                "module_depends": "crm",
            }
        )

    for xmlid, vals in (
        (
            "crm_salesperson_dashboard.scope_crm_sp_pipeline",
            {
                "sequence": 20,
                "description": (
                    "Include opportunity-related records in the dashboard analysis."
                ),
            },
        ),
        (
            "crm_salesperson_dashboard.scope_crm_sp_leads",
            {
                "sequence": 30,
                "description": (
                    "Include lead-related records in the dashboard analysis."
                ),
            },
        ),
    ):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.write(vals)

    if bp.state == "published":
        bp._sync_generated_artifacts()

    _logger.info(
        "post-expand-salesperson-parity: refreshed blueprint %s (%s slots)",
        bp.key,
        len(bp.slot_ids),
    )
