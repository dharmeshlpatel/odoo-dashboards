# -*- coding: utf-8 -*-
"""Rename stored blueprint columns to match professional field APIs."""
import logging

_logger = logging.getLogger(__name__)

# old_column -> new_column on dashboard_blueprint
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
        _logger.info("pre-rename: %s.%s already exists, drop legacy %s", table, new, old)
        cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, old))
        return
    _logger.info("pre-rename: %s.%s -> %s", table, old, new)
    cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old, new))


def migrate(cr, version):
    for old, new in _COLUMN_RENAMES:
        _rename_column(cr, "dashboard_blueprint", old, new)
