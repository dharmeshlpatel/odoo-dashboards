from odoo import tools
from datetime import datetime, timedelta
from .date_utils import (
    _apply_tz_offset,
)


def _date_range_to_domain(field, start_date, end_date, tz_offset):
    """
    Convert a start/end datetime range into an Odoo domain fragment.

    The range is:
    - Adjusted using the web client timezone offset
    - Converted to server datetime string format
    - Inclusive of the full end date (minus 1 second)

    :param field: Datetime field name to apply the domain on
    :param start_date: Start datetime
    :param end_date: End datetime
    :param tz_offset: Web client timezone offset in seconds
    :return: List of domain conditions
    """
    return [
        [
            (
                field,
                ">=",
                datetime.strftime(
                    _apply_tz_offset(start_date, tz_offset),
                    tools.DEFAULT_SERVER_DATETIME_FORMAT,
                ),
            )
        ],
        [
            (
                field,
                "<=",
                datetime.strftime(
                    _apply_tz_offset(end_date, tz_offset)
                    - timedelta(seconds=1),
                    tools.DEFAULT_SERVER_DATETIME_FORMAT,
                ),
            )
        ],
    ]
