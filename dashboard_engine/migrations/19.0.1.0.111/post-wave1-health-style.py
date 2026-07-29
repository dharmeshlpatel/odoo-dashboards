# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Wave 1 health styling: when_positive on CRM/Sales overdue and to-invoice slots."""
from odoo import SUPERUSER_ID, api

SLOT_STYLE_BY_KEY = [
    ("overdue_opportunities", {"style": "danger", "style_mode": "when_positive"}),
    ("to_invoice", {"style": "warning", "style_mode": "when_positive"}),
    ("box_total_overdue", {"style": "danger", "style_mode": "when_positive"}),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Slot = env["dashboard.blueprint.slot"].sudo()
    for key, vals in SLOT_STYLE_BY_KEY:
        slots = Slot.search([("key", "=", key)])
        if slots:
            slots.write(vals)
