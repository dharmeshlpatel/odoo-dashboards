import { Component, onWillRender } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Generic dashboard slot renderer (client side).
 *
 * Renders the server-computed `dashboard_slots` JSON payload. One field,
 * three display modes selected through widget options:
 *
 *   <field name="dashboard_slots" widget="dashboard_slots"
 *          options="{'display': 'kpis'}"/>
 *   <field name="dashboard_slots" widget="dashboard_slots"
 *          options="{'display': 'buttons'}"/>
 *   <field name="dashboard_slots" widget="dashboard_slots"
 *          options="{'display': 'menu', 'section': 'views'}"/>
 *
 * Footer button rows (buttons / button_box) follow the form ButtonBox
 * pattern: show what fits, put the rest under a More dropdown.
 *
 * Clicking an item calls the configured object method on the dashboard
 * record and executes the returned action.
 */
export class DashboardSlotsField extends Component {
    static template = "dashboard_engine.DashboardSlotsField";
    static components = { Dropdown, DropdownItem };
    static props = {
        ...standardFieldProps,
        display: { type: String, optional: true },
        section: { type: String, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.ui = useService("ui");
        this.visibleItems = [];
        this.moreItems = [];
        onWillRender(() => this._splitOverflowButtons());
    }

    get payload() {
        return this.props.record.data[this.props.name] || {};
    }

    get items() {
        const payload = this.payload;
        if (this.props.display === "menu") {
            return (payload.menu && payload.menu[this.props.section]) || [];
        }
        if (this.props.display === "buttons") {
            return payload.buttons || [];
        }
        if (this.props.display === "button_box") {
            return payload.button_box || [];
        }
        return payload.kpis || [];
    }

    get usesOverflowMore() {
        return this.props.display === "buttons" || this.props.display === "button_box";
    }

    /**
     * Grouped kanban columns already wrap footer buttons in a 2-column grid
     * (see base_dashboard.scss). More is only for the wider ungrouped cards.
     */
    get isGroupedKanban() {
        const root = this.props.record?.model?.root;
        if (root && "isGrouped" in root) {
            return Boolean(root.isGrouped);
        }
        const groupBy = this.env.searchModel?.groupBy;
        return Boolean(groupBy && groupBy.length);
    }

    get moreLabel() {
        return _t("More");
    }

    /**
     * Mirror form ButtonBox: max visible slots for this UI size, reserving
     * one slot for More when there is overflow. Card footers stay tighter
     * than form sheets (kanban cards are narrower).
     */
    _maxVisibleButtons() {
        // XS/SM: 2 total slots; MD: 3; LG+: 4 (→ 3 stats + More when overflow).
        return [2, 2, 3, 4, 4, 4][this.ui.size] ?? 4;
    }

    _splitOverflowButtons() {
        if (!this.usesOverflowMore || this.isGroupedKanban) {
            this.visibleItems = this.items;
            this.moreItems = [];
            return;
        }
        const items = this.items;
        const maxVisible = this._maxVisibleButtons();
        if (items.length <= maxVisible) {
            this.visibleItems = items;
            this.moreItems = [];
        } else {
            const splitIndex = Math.max(maxVisible - 1, 0);
            this.visibleItems = items.slice(0, splitIndex);
            this.moreItems = items.slice(splitIndex);
        }
    }

    formatAmount(item) {
        return formatCurrency(item.amount, item.currency_id);
    }

    itemStyleClass(item) {
        if (item.style === "danger") {
            return "o_dashboard_stat_danger";
        }
        if (item.style === "warning") {
            return "o_dashboard_stat_warning";
        }
        return "";
    }

    onItemClick(item) {
        if (!item.method) {
            return;
        }
        this.action.doActionButton({
            name: item.method,
            type: "object",
            resId: this.props.record.resId,
            resModel: this.props.record.resModel,
            context: {
                ...(this.props.record.context || {}),
                ...(item.context || {}),
                dashboard_rendering: true,
            },
        });
    }
}

export const dashboardSlotsField = {
    component: DashboardSlotsField,
    supportedTypes: ["json"],
    // So SCSS can target the Field wrapper (type class is o_field_json).
    additionalClasses: ["o_field_dashboard_slots"],
    extractProps: ({ options }) => ({
        display: options.display,
        section: options.section,
    }),
};

registry.category("fields").add("dashboard_slots", dashboardSlotsField);
