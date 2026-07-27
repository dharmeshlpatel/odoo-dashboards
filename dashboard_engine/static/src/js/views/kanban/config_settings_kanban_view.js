/** @odoo-module **/

import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { ConfigSettingsKanbanViewController } from "./config_settings_kanban_view_controller";

export const ConfigSettingsKanbanView = {
    ...kanbanView,
    Controller: ConfigSettingsKanbanViewController,
};

registry
    .category("views")
    .add("analytic_dashboard_config_settings_kanban", ConfigSettingsKanbanView);
