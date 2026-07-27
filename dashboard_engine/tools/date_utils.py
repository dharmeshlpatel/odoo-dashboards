# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from ..models.dashboard_graph_periods import (
    get_period_month,
    PERIOD_QUARTER,
)


def _apply_tz_offset(dt, offset):
    """
    Apply the web client timezone offset to a datetime.

    This ensures consistency between server-side datetime values
    and the user's browser timezone.

    :param dt: Original datetime (UTC-based)
    :param offset: Timezone offset in seconds (from web client)
    :return: Timezone-adjusted datetime
    """
    return dt + timedelta(seconds=offset)


# Common helper to build a date range from a start datetime and a relativedelta
def _get_datetime_range(start_datetime, delta):
    """
    Build a date range from a start datetime and a relativedelta.

    :param start_datetime: datetime object representing the range start
    :param delta: relativedelta to calculate the end datetime
    :return: list [start_datetime, end_datetime]
    """
    return [start_datetime, start_datetime + delta]


def _get_month_dates(year, month):
    """
    Return start and end datetime for a given month.

    The end date is exclusive (start of the next month).

    :param year: int year (e.g. 2026)
    :param month: int month (1–12)
    :return: list [start_datetime, end_datetime]
    """
    start_datetime = datetime.datetime(year, month, 1)
    return _get_datetime_range(start_datetime, relativedelta(months=1))


def _get_quarter_dates(year, quarter):
    """
    Return start and end datetime for a given quarter.

    Quarter is expected to be between 1 and 4.
    The end date is exclusive.

    :param year: int year (e.g. 2026)
    :param quarter: int quarter (1–4)
    :return: list [start_datetime, end_datetime]
    """
    start_month = 1 + (quarter - 1) * 3
    start_datetime = datetime.datetime(year, start_month, 1)
    return _get_datetime_range(start_datetime, relativedelta(months=3))


def _get_year_dates(year):
    """
    Return start and end datetime for a given year.

    The end date is exclusive (start of the next year).

    :param year: int year (e.g. 2026)
    :return: list [start_datetime, end_datetime]
    """
    start_datetime = datetime.datetime(year, 1, 1)
    return _get_datetime_range(start_datetime, relativedelta(years=1))


def _get_period_dates(year, mq_periods):
    """
    Resolve month / quarter / year selections into concrete date ranges.

    If specific month or quarter periods are selected, only those
    ranges are generated. Otherwise, the full year range is used.

    :param year: Integer year (e.g. 2026)
    :param mq_periods: List of month or quarter identifiers
    :return: List of (start_date, end_date) tuples
    """
    ranges = []

    if mq_periods:
        period_month = get_period_month()
        for mq in mq_periods:
            if mq in period_month:
                ranges.append(_get_month_dates(year, period_month[mq]))
            elif mq in PERIOD_QUARTER:
                ranges.append(_get_quarter_dates(year, PERIOD_QUARTER[mq]))
    else:
        ranges.append(_get_year_dates(year))

    return ranges
