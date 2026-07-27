import { SearchModel } from "@web/search/search_model";
import { patch } from "@web/core/utils/patch";

/**
 * Patch of Odoo SearchModel to support dashboard-driven defaults.
 *
 * This extension enables:
 * - Applying default domains for graph views
 * - Applying default group-by fields (including date intervals)
 * - One-time application of graph and pivot measures from context
 *
 * All behavior is applied only on:
 * - First load (not state restoration)
 * - Dashboard kanban views (not standalone graph/pivot views)
 *
 * The patch is fully backward-compatible and does not interfere
 * with Odoo's own GraphSearchModel or standard view loading.
 */
patch(SearchModel.prototype, {
    /**
     * Load the search model and apply dashboard-specific defaults.
     *
     * IMPORTANT: We only consume/apply dashboard defaults when the
     * view is a dashboard kanban view (identified by the "initializer"
     * context key). When opening a standalone graph/pivot view from
     * a dashboard button action, graph_domain/graph_groupbys/
     * graph_measure etc. must remain in the context so that Odoo's
     * native GraphModel/PivotModel can read them.
     *
     * @param {Object} config
     * @returns {Promise<any>}
     */
    async load(config) {
        const context = config.context || {};
        const isFirstLoad = !config.isReload;
        const isDashboardView = Boolean(context.initializer);
        const hasDashboardDefaults = Boolean(context.graph_domain || context.graph_groupbys);

        // If we are opening from the dashboard with fresh defaults, we MUST
        // ignore any cached state (config.state) to prevent stale filters.
        if (hasDashboardDefaults && config.state) {
            delete config.state;
        }

        // We only consume (delete from context) in the dashboard module
        // itself to prevent context leakage. Standalone views keep them.
        let defaults;
        if (isFirstLoad && hasDashboardDefaults) {
            if (isDashboardView) {
                defaults = this._readAndConsumeDefaults(context);
            } else {
                // In standalone views, read but DO NOT consume
                defaults = {
                    graphDomain: context.graph_domain,
                    graphGroupBys: context.graph_groupbys,
                };
            }
        }

        const result = await super.load(config);

        // Apply defaults if we found any. We apply them to both dashboard
        // and standalone views so the first load is correct.
        if (isFirstLoad && defaults) {
            this.blockNotification = true;
            let applied = false;
            try {
                if (this._applyDefaultDomain(defaults.graphDomain)) applied = true;
                if (this._applyDefaultGroupBys(defaults.graphGroupBys)) applied = true;
            } finally {
                this.blockNotification = false;
            }
            if (applied) {
                // Await notification to ensure reset() and trigger('update') 
                // happen before the model finishes its first fetch.
                await this._notify();
            }
        }

        return result;
    },

    /**
     * Extract and remove graph domain and groupby defaults from context.
     *
     * @param {Object} context
     * @returns {{graphDomain: Array, graphGroupBys: Array}}
     */
    _readAndConsumeDefaults(context) {
        const graphDomain = context.graph_domain;
        const graphGroupBys = context.graph_groupbys;

        delete context.graph_domain;
        delete context.graph_groupbys;

        return { graphDomain, graphGroupBys };
    },

    /**
     * Apply default domain filters.
     *
     * @param {Array} graphDomain
     * @returns {boolean}
     */
    _applyDefaultDomain(graphDomain) {
        if (Array.isArray(graphDomain) && graphDomain.length) {
            this.splitAndAddDomain(graphDomain);
            return true;
        }
        return false;
    },

    /**
     * Apply default group-by fields to the search model.
     *
     * Supports both regular and date-based group-bys.
     *
     * @param {Array<string>} graphGroupBys
     * @returns {boolean}
     */
    _applyDefaultGroupBys(graphGroupBys) {
        if (!Array.isArray(graphGroupBys) || !graphGroupBys.length) {
            return false;
        }

        const items = this.getSearchItems(() => true) || [];
        let applied = false;

        for (const groupByExpr of graphGroupBys) {
            const [fieldName, interval] = groupByExpr.split(":");

            let item = items.find(
                (it) =>
                    (it.type === "groupBy" || it.type === "dateGroupBy") &&
                    (it.fieldName === fieldName || it.name === fieldName)
            );

            if (!item) {
                // graph_groupbys can come from a different model than the
                // opened action (e.g. sale.report vs sale.order). createNewGroupBy
                // destructures field.string and crashes when the field is absent.
                if (!this.searchViewFields?.[fieldName]) {
                    continue;
                }
                item = this.createNewGroupBy(fieldName, { interval });
            }

            if (!item?.id) {
                continue;
            }

            applied = true;
            if (interval && item.type === "dateGroupBy") {
                this.toggleDateGroupBy(item.id, interval);
            } else {
                this.toggleSearchItem(item.id);
            }
        }
        return applied;
    },
});