# -*- coding: utf-8 -*-
"""Restore V1 primary-button field column names on dashboard_blueprint.

19.0.1.0.40 renamed these to primary_action_* / alternate_label_*. UI and
API now match V1 again (Button Label / Alternate Label / When this filter
is off), so columns move back.
"""
import logging

_logger = logging.getLogger(__name__)

# old_column (current DB at 1.0.73) -> new_column (V1 / 1.0.74+)
_COLUMN_RENAMES = (
    ("primary_action_label", "primary_button_label"),
    ("alternate_label", "primary_label_alt"),
    ("alternate_label_scope_id", "primary_label_alt_scope_id"),
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
        _logger.info(
            "pre-rename: %s.%s already exists, drop legacy %s", table, new, old
        )
        cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, old))
        return
    _logger.info("pre-rename: %s.%s -> %s", table, old, new)
    cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old, new))


def migrate(cr, version):
    for old, new in _COLUMN_RENAMES:
        _rename_column(cr, "dashboard_blueprint", old, new)
