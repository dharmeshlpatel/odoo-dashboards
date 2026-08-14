/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { makeContext } from "@web/core/context";
import { registry } from "@web/core/registry";
import { evaluateExpr } from "@web/core/py_js/py";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class DashboardHubAction extends Component {
    static template = "dashboard_engine.DashboardHubAction";
    static components = { View };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.selectionRequest = 0;
        // Phase 5: keep action/view metadata per blueprint for instant re-open
        // inside the same Hub session (no second /web/action/load).
        this._actionCache = new Map();
        this.state = useState({
            tree: [],
            activeBlueprintId: false,
            viewProps: null,
            loadingView: false,
            hubMenuId: false,
        });
        onWillStart(async () => {
            const hubMenuId = this.hubMenuId;
            this.state.hubMenuId = hubMenuId;
            const data = await this.orm.call(
                "dashboard.blueprint",
                "hub_get_initial_state",
                [],
                { hub_menu_id: hubMenuId || false }
            );
            this.state.tree = data.tree || [];
            if (data.active_blueprint_id) {
                await this.selectDashboard(data.active_blueprint_id, false);
            }
        });
    }

    /**
     * Open a host form from an embedded hub kanban.
     *
     * Standalone act_window dashboards get selectRecord from action_service.
     * The hub mounts <View> itself, so without this hook title / Configuration
     * (type="open") call the KanbanController default no-op.
     */
    openHostRecord(resModel, resId, { activeIds, readonly, newWindow } = {}) {
        if (!resModel || !resId) {
            return;
        }
        return this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: resModel,
                views: [[false, "form"]],
                target: "current",
            },
            {
                newWindow,
                props: { resId, resIds: activeIds, readonly },
            }
        );
    }

    /** Odoo empty-helper title (smiling face / empty folder). */
    get emptyTitle() {
        if (!this.state.tree.length) {
            return _t("No dashboards in the hub yet");
        }
        return _t("Select a dashboard from the list");
    }

    /** Extra line under the empty-helper title when the hub has no blueprints. */
    get emptyDescription() {
        return _t("Install a 360 dashboard pack to add a left link.");
    }

    /** Shared hub menu id from the client action context (optional). */
    get hubMenuId() {
        const ctx = this.props.action?.context || {};
        const raw = ctx.hub_menu_id || ctx.default_hub_menu_id || false;
        return raw ? Number(raw) : false;
    }

    /** Stable key so Owl never reuses a View across blueprint/model/viewId. */
    get viewKey() {
        const props = this.state.viewProps;
        if (!props) {
            return "empty";
        }
        return `${this.state.activeBlueprintId}-${props.resModel}-${props.viewId}`;
    }

    findDashboard(blueprintId) {
        for (const group of this.state.tree) {
            const dashboard = group.dashboards.find((dash) => dash.id === blueprintId);
            if (dashboard) {
                return dashboard;
            }
        }
        return null;
    }

    /** Control panel / breadcrumb title for the active left-side dashboard. */
    setHubDisplayName(name) {
        if (typeof this.env.config?.setDisplayName === "function") {
            this.env.config.setDisplayName(name || "");
        }
    }

    async selectDashboard(blueprintId, persist = true) {
        const request = ++this.selectionRequest;
        const dashboard = this.findDashboard(blueprintId);
        this.state.activeBlueprintId = dashboard ? blueprintId : false;
        // Destroy the embedded View before loading the next action. Otherwise
        // View.onWillUpdateProps may keep the old kanban arch (same resModel)
        // or reuse KanbanRecord instances across models (same record ids) and
        // crash with missing archInfo.fieldNodes[fieldId].
        this.state.viewProps = null;
        if (!dashboard || !dashboard.action_id) {
            this.state.loadingView = false;
            return;
        }
        // Embedded View inherits the hub client-action title (e.g. "360°").
        // Override it with the left-panel label so the control panel matches.
        this.setHubDisplayName(dashboard.name);
        this.state.loadingView = true;
        try {
            let cached = this._actionCache.get(blueprintId);
            if (!cached) {
                const action = await rpc("/web/action/load", {
                    action_id: dashboard.action_id,
                });
                if (request !== this.selectionRequest) {
                    return;
                }
                if (!action) {
                    return;
                }
                const kanban = (action.views || []).find(([, type]) => type === "kanban");
                const searchViewId = Array.isArray(action.search_view_id)
                    ? action.search_view_id[0]
                    : action.search_view_id || false;
                const context = makeContext(
                    [user.context, action.context || {}],
                    user.context
                );
                const domain =
                    typeof action.domain === "string"
                        ? evaluateExpr(
                              action.domain,
                              Object.assign({}, user.context, context)
                          )
                        : action.domain || [];
                cached = {
                    resModel: action.res_model,
                    viewId: kanban ? kanban[0] : false,
                    searchViewId,
                    context,
                    domain,
                };
                this._actionCache.set(blueprintId, cached);
            } else if (request !== this.selectionRequest) {
                return;
            }
            const { resModel, viewId, searchViewId, context, domain } = cached;
            this.state.viewProps = {
                resModel,
                type: "kanban",
                viewId,
                searchViewId,
                views: [
                    [viewId, "kanban"],
                    [searchViewId, "search"],
                    [false, "form"],
                ],
                context,
                domain,
                selectRecord: (resId, options = {}) =>
                    this.openHostRecord(resModel, resId, options),
            };
            if (persist && request === this.selectionRequest) {
                await this.orm.call(
                    "dashboard.blueprint",
                    "hub_set_last_opened",
                    [blueprintId],
                    { hub_menu_id: this.state.hubMenuId || false }
                );
            }
        } finally {
            if (request === this.selectionRequest) {
                this.state.loadingView = false;
            }
        }
    }
}

registry.category("actions").add("dashboard_engine.hub", DashboardHubAction);
