# -*- coding: utf-8 -*-
"""Merge legacy header field_name/field2_name into ordered field_names."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'dashboard_blueprint_header_item'
        """
    )
    cols = {row[0] for row in cr.fetchall()}
    if "field_names" not in cols:
        cr.execute(
            "ALTER TABLE dashboard_blueprint_header_item "
            "ADD COLUMN field_names VARCHAR"
        )
    if "field_name" not in cols and "field2_name" not in cols:
        _logger.info("header-field-names: nothing to merge")
        return
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET field_names = CASE
                WHEN COALESCE(field_name, '') != ''
                 AND COALESCE(field2_name, '') != ''
                    THEN field_name || ',' || field2_name
                WHEN COALESCE(field_name, '') != ''
                    THEN field_name
                WHEN COALESCE(field2_name, '') != ''
                    THEN field2_name
                ELSE field_names
           END
         WHERE COALESCE(field_names, '') = ''
        """
    )
    _logger.info("header-field-names: merged rows=%s", cr.rowcount)
