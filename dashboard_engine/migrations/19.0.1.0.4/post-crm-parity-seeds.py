# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Apply CRM seed-parity field updates that noupdate XML cannot change.

New slot/condition xmlids are created by data/seed_crm_parity.xml on upgrade.
This script only patches existing blueprint / condition rows.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env.ref(
        "dashboard_engine.blueprint_crm_customers", raise_if_not_found=False
    )
    if bp:
        vals = {}
        # Field renamed again in 19.0.1.0.74 (primary_action_label →
        # primary_button_label). Use the current API so long-jump upgrades
        # that run this post after 1.0.74 pre still work.
        if bp.primary_button_label == "Opportunities":
            vals["primary_button_label"] = "Pipeline Analysis"
        if bp.graph_groupby in (False, "create_date:month"):
            vals["graph_groupby"] = "stage_id"
        if vals:
            bp.write(vals)

    condition = env.ref(
        "dashboard_engine.condition_crm_default_type", raise_if_not_found=False
    )
    if condition and not condition.note:
        condition.note = (
            "Reserved for create defaults — do not AND onto View/Report domains."
        )
