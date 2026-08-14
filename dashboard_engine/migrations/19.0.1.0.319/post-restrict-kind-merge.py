# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Set restrict_kind / merge_noun on existing pack My Data rows."""

_KIND_NOUN = (
    ("crm_customer_dashboard.scope_crm_mine", "mine", "opportunities"),
    ("sales_customer_dashboard.scope_sale_mine", "mine", "sales orders"),
    ("pos_sales_customer_dashboard.scope_pos_mine", "mine", "POS orders"),
    ("pos_sales_customer_dashboard.scope_pos_cust_mine", "mine", "POS orders"),
)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, kind, noun in _KIND_NOUN:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.write({"restrict_kind": kind, "merge_noun": noun})
