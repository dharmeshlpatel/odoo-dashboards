# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import babel.dates
from odoo import fields, models
from odoo.tools.misc import get_lang
from dateutil.relativedelta import relativedelta

# Static mapping of quarter period keys to quarter numbers (1–4).
PERIOD_QUARTER = {
    "fourth_quarter": 4,
    "third_quarter": 3,
    "second_quarter": 2,
    "first_quarter": 1,
}


def get_period_month():
    """
    Compute month period mapping relative to today.

    Returns fresh values on every call to avoid stale data
    when the server runs across month boundaries.
    """
    today = fields.Date.today()
    return {
        "month": today.month,
        "month-1": (today + relativedelta(months=-1)).month,
        "month-2": (today + relativedelta(months=-2)).month,
    }


def get_period_year():
    """
    Compute year period mapping relative to today.

    Returns fresh values on every call to avoid stale data
    when the server runs across year boundaries.
    """
    today = fields.Date.today()
    return {
        "year": today.year,
        "year-1": (today + relativedelta(years=-1)).year,
        "year-2": (today + relativedelta(years=-2)).year,
    }


def _get_period_display_name(env, period_key, mapping, name_getter):
    """
    Compute a localized display name for a given period key.

    This generic helper resolves a human-readable, localized name
    for a period based on:
        - the stored period key (e.g. 'month-1', 'first_quarter', 'year')
        - a mapping that converts keys into numeric values
        - a callable that converts numeric values into display labels

    It is reused across month, quarter, and year period models
    to avoid duplication.

    :param env: Odoo environment
    :param period_key: Key stored on the period record (name field)
    :param mapping: Dict mapping period keys to numeric values
    :param name_getter: Callable converting numeric value to display name
    :return: Localized display name or None if key is unsupported
    """
    # Unsupported period key → no display name
    if period_key not in mapping:
        return None
    # Convert mapped numeric value into a localized display label
    return name_getter(env, mapping.get(period_key))


def _to_wide_month_name(env, month_index):
    """
    Return the localized full month name for the given month index.

    Localization is based on the current user's language.
    """
    # Fetch localized month names using Babel
    return babel.dates.get_month_names("wide", locale=get_lang(env).code)[
        month_index
    ]


def _to_wide_quarter_name(env, quarter_index):
    """
    Return the localized abbreviated quarter name for the given quarter index.

    Localization is based on the current user's language.
    """
    # Fetch localized quarter names using Babel
    return babel.dates.get_quarter_names(
        "abbreviated", locale=get_lang(env).code
    )[quarter_index]


class PeriodMonthQuarter(models.Model):
    """
    Model representing selectable month and quarter periods.

    These records are used in dashboards and reports to allow users
    to filter data by relative months (current, previous, etc.)
    or by calendar quarters.
    """

    _name = "period.month.quarter"
    _description = "Period Month Quarter"
    _rec_name = "display_name"

    name = fields.Char()
    color = fields.Integer("Color Index")
    display_name = fields.Char(
        compute="_compute_display_name", search="_search_display_name"
    )

    def _compute_display_name(self):
        """
        Compute the localized display name for month and quarter periods.

        The method first attempts to resolve the period as a month.
        If no month match is found, it falls back to quarter resolution.
        """
        period_month = get_period_month()
        for period in self:
            # Try resolving the period as a month
            display_name = _get_period_display_name(
                self.env,
                period.name,
                period_month,
                _to_wide_month_name,
            )
            if not display_name:
                # Fallback: resolve the period as a quarter
                display_name = _get_period_display_name(
                    self.env,
                    period.name,
                    PERIOD_QUARTER,
                    _to_wide_quarter_name,
                )
            period.display_name = display_name


class PeriodYear(models.Model):
    """
    Model representing selectable year periods.

    These records allow dashboards and reports to filter data
    by relative years (current year, last year, etc.).
    """

    _name = "period.year"
    _description = "Period Year"
    _rec_name = "display_name"

    name = fields.Char()
    color = fields.Integer("Color Index")
    display_name = fields.Char(
        compute="_compute_display_name", search="_search_display_name"
    )

    def _compute_display_name(self):
        """
        Compute the display name for year periods.

        The display name is derived directly from the resolved
        numeric year value.
        """
        period_year = get_period_year()
        for period in self:
            # Convert resolved year value into string for display
            period.display_name = str(period_year.get(period.name))
