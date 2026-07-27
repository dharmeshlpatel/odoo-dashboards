# -*- coding: utf-8 -*-
"""Uninstall the deprecated many2many_ordered_tags shell after merge."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT id FROM ir_module_module
         WHERE name = 'many2many_ordered_tags'
           AND state IN ('installed', 'to upgrade', 'to remove')
        """
    )
    row = cr.fetchone()
    if not row:
        return
    # Mark uninstalled; assets/Python already live in dashboard_engine.
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled'
         WHERE name = 'many2many_ordered_tags'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency
         WHERE name = 'many2many_ordered_tags'
            OR module_id = %s
        """,
        (row[0],),
    )
    # Drop engine's former hard depend row if still present.
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency d
         USING ir_module_module m
         WHERE d.module_id = m.id
           AND m.name = 'dashboard_engine'
           AND d.name = 'many2many_ordered_tags'
        """
    )
    # Drop stale assets / views registered by the old module.
    cr.execute(
        """
        DELETE FROM ir_asset
         WHERE path LIKE 'many2many_ordered_tags/%'
            OR name LIKE '%many2many_ordered_tags%'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'many2many_ordered_tags'
        """
    )
    _logger.info(
        "merge-ordered-tags: marked many2many_ordered_tags uninstalled"
    )
