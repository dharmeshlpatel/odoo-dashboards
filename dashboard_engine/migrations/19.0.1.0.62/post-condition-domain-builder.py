# -*- coding: utf-8 -*-
"""Fill stored ``domain`` Char from ``domain_tree`` for the domain builder UI."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'dashboard_condition'
           AND column_name = 'domain'
        """
    )
    if not cr.fetchone():
        return
    # Stored compute is filled on upgrade by the ORM; nothing else required.
    # Keep this hook as a no-op marker for the 19.0.1.0.62 ship.
    return
