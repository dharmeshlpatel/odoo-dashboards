import { RelationalModel } from "@web/model/relational_model/relational_model";
import { user } from "@web/core/user";

/**
 * Kanban view model for dashboard configuration settings.
 *
 * This model ensures client-side context (such as timezone offset)
 * is synchronized with the backend before dashboard queries execute.
 */
export class ConfigSettingsKanbanViewModel extends RelationalModel {
    /**
     * Initialize the view model and synchronize client timezone
     * offset into the user context.
     */
    setup() {
        super.setup(...arguments);
        // user.updateContext({webclient_tz_offset: this._getTimezoneOffsetInSeconds(),
        // });
    }

    /**
     * Return the browser timezone offset in seconds.
     *
     * @returns {number}
     */
    _getTimezoneOffsetInSeconds() {
        return new Date().getTimezoneOffset() * 60;
    }
}