# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from odoo import api, models


class DashboardGraphParameter(models.TransientModel):
    """
    Helper transient model to manage dashboard graph group-by models.

    This model stores and retrieves dashboard graph group-by
    models from ir.config_parameter in a safe and reusable way.
    """

    _name = "dashboard.graph_parameter"
    _description = "Dashboard Graph Parameter Helper"

    PARAM_KEY = "dashboard_graph_groupby_models"

    @api.model
    def _get_config_parameter(self):
        """
        Return ir.config_parameter record with sudo access.

        This ensures dashboard configuration parameters
        can be read and written regardless of user permissions.
        """
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def get_param(self):
        """
        Return the stored dashboard graph group-by models
        as a Python list.

        Fully defensive implementation:
        - Never passes non-strings to literal_eval
        - Safely handles cached Python objects
        - Gracefully recovers from malformed stored values
        """
        value = self._get_config_parameter().get_param(self.PARAM_KEY)

        if not value:
            return []

        # If value is already a Python list (cached or injected), return safely
        if isinstance(value, list):
            return value

        # Only evaluate if it is a string representation of a list
        if isinstance(value, str):
            try:
                parsed = literal_eval(value)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                # Corrupted or invalid value — auto-heal
                self._get_config_parameter().set_param(self.PARAM_KEY, "[]")
                return []

        # Fallback safety
        return []

    @api.model
    def set_param(self, value):
        """
        Append a value to the dashboard graph parameter list.

        Ensures:
        - input normalization
        - no duplicate entries
        - values are stored safely as strings
        """
        values = self.get_param()

        # Normalize input (avoid nested lists)
        if isinstance(value, (list, tuple)):
            value = value[0]

        if value not in values:
            values.append(value)

        # ir.config_parameter must always store strings
        self._get_config_parameter().set_param(self.PARAM_KEY, str(values))
