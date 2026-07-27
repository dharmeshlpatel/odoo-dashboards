# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def pre_init_hook(env):
    """Drop soft-engine blueprints with the same key (no pack xmlid yet)."""
    cr = env.cr
    for key in {'warehouse_overview'}:
        cr.execute(
            """
            DELETE FROM dashboard_blueprint bp
             WHERE bp.key = %s
               AND NOT EXISTS (
                    SELECT 1 FROM ir_model_data d
                     WHERE d.model = 'dashboard.blueprint'
                       AND d.res_id = bp.id
                       AND d.module = %s
               )
            """,
            (key, 'warehouse_dashboard'),
        )


def post_init_hook(env):
    bp = env.ref('warehouse_dashboard.blueprint_warehouse_overview', raise_if_not_found=False)
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
