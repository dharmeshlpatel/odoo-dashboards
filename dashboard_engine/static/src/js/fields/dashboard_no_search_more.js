/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { RecordAutocomplete } from "@web/core/record_selectors/record_autocomplete";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { Many2One } from "@web/views/fields/many2one/many2one";
import {
    Many2OneField,
    buildM2OFieldDescription,
} from "@web/views/fields/many2one/many2one_field";
import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

/**
 * Same dropdown as stock Many2X, without "Search more...".
 *
 * Picking a row still calls update() → form onchange. Typing still searches.
 * searchLimit is raised so months/years and field lists fit the list.
 */
export class DashboardMany2XAutocomplete extends Many2XAutocomplete {
    static defaultProps = {
        ...Many2XAutocomplete.defaultProps,
        searchLimit: 80,
    };

    addSearchMoreSuggestion() {
        return false;
    }
}

export class DashboardMany2One extends Many2One {
    static components = {
        ...Many2One.components,
        Many2XAutocomplete: DashboardMany2XAutocomplete,
    };
}

export class DashboardMany2OneField extends Many2OneField {
    static components = { Many2One: DashboardMany2One };
}

export const dashboardMany2OneField = {
    ...buildM2OFieldDescription(DashboardMany2OneField),
    displayName: _t("Dashboard Many2one"),
};

registry.category("fields").add("dashboard_many2one", dashboardMany2OneField);

/**
 * Chart Measure picker: same field list as the graph Measures menu, plus
 * Count (empty many2one — same as the standard graph Count item).
 */
export class DashboardMeasureMany2XAutocomplete extends DashboardMany2XAutocomplete {
    async loadOptionsSource(request) {
        const countLabel = _t("Count");
        let search = request || "";
        if (search.trim().toLowerCase() === countLabel.toLowerCase()) {
            search = "";
        }
        const suggestions = await super.loadOptionsSource(search);
        if (this._showCountSuggestion(search)) {
            if (suggestions.length) {
                suggestions.push({
                    cssClass: "dropdown-divider p-0",
                    label: "",
                });
            }
            suggestions.push({
                label: countLabel,
                onSelect: () => this.props.update(false),
            });
        }
        return suggestions;
    }

    _showCountSuggestion(request) {
        const needle = (request || "").trim().toLowerCase();
        const label = _t("Count").toLowerCase();
        return !needle || label.includes(needle);
    }
}

export class DashboardMeasureMany2One extends DashboardMany2One {
    static components = {
        ...DashboardMany2One.components,
        Many2XAutocomplete: DashboardMeasureMany2XAutocomplete,
    };

    get displayName() {
        if (this.props.value) {
            return super.displayName;
        }
        return _t("Count");
    }
}

export class DashboardMeasureMany2OneField extends DashboardMany2OneField {
    static components = { Many2One: DashboardMeasureMany2One };
}

export const dashboardMeasureMany2OneField = {
    ...dashboardMany2OneField,
    component: DashboardMeasureMany2OneField,
    displayName: _t("Dashboard Measure"),
};

registry.category("fields").add("dashboard_measure_many2one", dashboardMeasureMany2OneField);

export class DashboardMany2ManyTagsField extends Many2ManyTagsField {
    static components = {
        ...Many2ManyTagsField.components,
        Many2XAutocomplete: DashboardMany2XAutocomplete,
    };
}

export const dashboardMany2ManyTagsField = {
    ...many2ManyTagsField,
    component: DashboardMany2ManyTagsField,
    displayName: _t("Dashboard Tags"),
};

registry.category("fields").add("dashboard_many2many_tags", dashboardMany2ManyTagsField);

/**
 * Studio RecordSelector / MultiRecordSelector: same idea, no Search More.
 */
export class DashboardRecordAutocomplete extends RecordAutocomplete {
    search(name, limit) {
        const domain = this.getDomain();
        const context = { ...(this.props.context || {}) };
        if (this.props.resModel === "ir.model.fields") {
            context.hide_model = true;
        }
        return this.orm.call(this.props.resModel, "name_search", [], {
            name,
            domain: domain,
            limit,
            context,
        });
    }
    async loadOptionsSource(name) {
        if (this.lastProm) {
            this.lastProm.abort(false);
        }
        this.lastProm = this.search(name, 80);
        const nameGets = (await this.lastProm).map(([id, label]) => [
            id,
            label ? label.split("\n")[0] : _t("Unnamed"),
        ]);
        this.addNames(nameGets);
        const options = nameGets.map(([id, label]) => ({
            data: {
                record: { id, display_name: label },
            },
            label,
            onSelect: () => this.props.update([id]),
        }));
        if (options.length === 0) {
            options.push({ label: _t("(no result)") });
        }
        return options;
    }
}

export class DashboardRecordSelector extends RecordSelector {
    static components = {
        ...RecordSelector.components,
        RecordAutocomplete: DashboardRecordAutocomplete,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async getDisplayNames(props) {
        const names = await fieldPickerDisplayNames(this.orm, props, this.getIds(props));
        return names || super.getDisplayNames(props);
    }
}

export class DashboardMultiRecordSelector extends MultiRecordSelector {
    static components = {
        ...MultiRecordSelector.components,
        RecordAutocomplete: DashboardRecordAutocomplete,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async getDisplayNames(props) {
        const names = await fieldPickerDisplayNames(this.orm, props, this.getIds(props));
        return names || super.getDisplayNames(props);
    }
}

async function fieldPickerDisplayNames(orm, props, ids) {
    if (props.resModel !== "ir.model.fields") {
        return null;
    }
    if (!ids.length) {
        return {};
    }
    const records = await orm.read("ir.model.fields", ids, ["display_name"], {
        context: { hide_model: true },
    });
    return Object.fromEntries(records.map((row) => [row.id, row.display_name]));
}

