# -*- coding: utf-8 -*-
"""Warehouse primary domain by warehouse (translated labels are jsonb)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint SET
            primary_button_label = jsonb_build_object('en_US', %s),
            primary_action_domain = %s
        WHERE key = 'warehouse_overview'
        """,
        (
            "Transfer Analysis",
            "[('picking_type_id.warehouse_id', '=', '{{id}}')]",
        ),
    )
