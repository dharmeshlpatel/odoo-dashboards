# -*- coding: utf-8 -*-
"""Idempotent column renames so intermediate migrations see new field APIs."""
import logging

_logger = logging.getLogger(__name__)

_COLUMN_RENAMES = (
    ("primary_button_label", "primary_action_label"),
    ("primary_label_alt", "alternate_label"),
    ("primary_label_alt_scope_id", "alternate_label_scope_id"),
    ("link_hierarchy", "include_child_records"),
)


def _rename_column(cr, table, old, new):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        (table, old),
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        (table, new),
    )
    if cr.fetchone():
        cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, old))
        return
    _logger.info("pre-rename(1.0.4): %s.%s -> %s", table, old, new)
    cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old, new))


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = 'dashboard_blueprint'
        """
    )
    if not cr.fetchone():
        return
    for old, new in _COLUMN_RENAMES:
        _rename_column(cr, "dashboard_blueprint", old, new)
