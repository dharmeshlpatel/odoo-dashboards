import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatCurrency } from "@web/core/currency";
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
 * Clicking an item calls the configured object method on the dashboard
 * record and executes the returned action.
 */
export class DashboardSlotsField extends Component {
    static template = "dashboard_engine.DashboardSlotsField";
    static props = {
        ...standardFieldProps,
        display: { type: String, optional: true },
        section: { type: String, optional: true },
    };

    setup() {
        this.action = useService("action");
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

    formatAmount(item) {
        return formatCurrency(item.amount, item.currency_id);
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
