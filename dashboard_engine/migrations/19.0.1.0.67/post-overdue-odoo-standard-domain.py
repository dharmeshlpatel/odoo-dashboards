# -*- coding: utf-8 -*-
"""Align Overdue open opportunity with CRM's overdue_opp domain.

CRM uses::

    ['&', ('date_closed', '=', False), ('date_deadline', '<', 'today')]

We keep ``type = opportunity`` as well. Also recompute every condition's
domain Char so relative dates show as ``"today"`` (DomainSelector-safe).
"""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    condition = env.ref(
        "dashboard_engine.condition_crm_overdue_opportunity",
        raise_if_not_found=False,
    )
    if condition:
        # Match CRM overdue_opp + opportunity type.
        condition.domain_tree = [
            "&",
            "&",
            ["type", "=", "opportunity"],
            ["date_closed", "=", False],
            ["date_deadline", "<", {"__de__": "relative_date", "when": "today"}],
        ]
        # Fix rule operator if it was flipped to "is set" (!=).
        open_rules = condition.rule_ids.filtered(
            lambda r: r.field_name == "date_closed"
        )
        open_rules.write({"operator": "=", "value_type": "false"})
    # Refresh stored domain Char for all conditions (today vs context_today()).
    for rec in env["dashboard.condition"].search([]):
        rec._compute_domain()
