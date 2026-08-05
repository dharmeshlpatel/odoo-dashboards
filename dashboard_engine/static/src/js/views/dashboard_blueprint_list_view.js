/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

/**
 * Blueprint list: New opens the create wizard; row open is Studio
 * (via list ``action`` / ``type`` on the arch).
 */
export class DashboardBlueprintListController extends ListController {
    async createRecord() {
        return this.actionService.doAction(
            "dashboard_engine.action_dashboard_blueprint_create_wizard",
            {
                onClose: async () => {
                    await this.model.root.load();
                },
            }
        );
    }
}

registry.category("views").add("dashboard_blueprint_list", {
    ...listView,
    Controller: DashboardBlueprintListController,
});
