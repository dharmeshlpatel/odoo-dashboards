import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

/**
 * Kanban controller for dashboard engine blueprints.
 * Gear opens the blueprint builder (managers) or refreshes after dialog close.
 */
export class ConfigSettingsKanbanViewController extends KanbanController {
    static template = "dashboard_engine.ConfigSettingsKanbanView";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        user.updateContext({
            webclient_tz_offset: this._getTimezoneOffsetInSeconds(),
        });
    }

    _getTimezoneOffsetInSeconds() {
        return new Date().getTimezoneOffset() * 60;
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
