import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { onWillStart, useState } from "@odoo/owl";

/**
 * Kanban controller for dashboard engine blueprints.
 * Gear opens personal settings; Customize opens Dashboard Studio (Studio group).
 */
export class ConfigSettingsKanbanViewController extends KanbanController {
    static template = "dashboard_engine.ConfigSettingsKanbanView";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.uiState = useState({ canCustomize: false });
        user.updateContext({
            webclient_tz_offset: this._getTimezoneOffsetInSeconds(),
        });
        onWillStart(async () => {
            this.uiState.canCustomize = await user.hasGroup(
                "dashboard_engine.group_dashboard_engine_studio"
            );
        });
    }

    get canCustomize() {
        return this.uiState.canCustomize;
    }

    _getTimezoneOffsetInSeconds() {
        return new Date().getTimezoneOffset() * 60;
    }

    async onClickCustomize() {
        const key = this.props.context.dashboard_blueprint_key;
        if (!key) {
            return;
        }
        const action = await this.orm.call(
            "dashboard.blueprint",
            "action_open_studio_for_key",
            [key]
        );
        await this.actionService.doAction(action);
    }

    /**
     * Open this dashboard's settings for the current user.
     *
     * The blueprint is named in the action context, so the same gear serves
     * every generated dashboard. Without one there is nothing to configure
     * and the blueprint list is the useful fallback.
     */
    async onClickConfigSettingsLink() {
        const key = this.props.context.dashboard_blueprint_key;
        const action = key
            ? await this.orm.call(
                  "dashboard.blueprint",
                  "action_open_settings_for_key",
                  [key],
                  { context: this.props.context }
              )
            : "dashboard_engine.action_dashboard_blueprint";
        await this.actionService.doAction(action, {
            onClose: async () => {
                await this.model.load();
            },
        });
    }
}
