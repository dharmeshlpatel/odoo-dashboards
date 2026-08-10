/** @odoo-module **/

/**
 * Parse / serialize dashboard action-context for the friendly KV UI.
 * Runtime still uses __de__ tokens; admins never edit raw JSON.
 */

export const VALUE_TYPES = [
    { value: "fixed", label: "Fixed value" },
    { value: "record_id", label: "This card’s ID" },
    { value: "group", label: "Depends on user group" },
];

/** How to pass the card record (stored key stays technical; UI shows labels). */
export const CARD_PASS_TARGETS = [
    { key: "active_id", label: "As the open record" },
    { key: "default_partner_id", label: "As the customer on new forms" },
    { key: "default_user_id", label: "As the salesperson on new forms" },
];

/**
 * One-click presets — plain language; keys are filled for the builder.
 */
export const CONTEXT_PRESETS = [
    {
        id: "card_id",
        label: "Open with this card",
        help: "The opened screen uses this card’s record.",
        build: () => ({
            ...emptyRow(),
            key: "active_id",
            valueType: "record_id",
            asList: false,
        }),
    },
    {
        id: "search_filter",
        label: "Turn on a list filter",
        help: "A filter on the list/search view starts on.",
        build: () => ({
            ...emptyRow(),
            key: "search_default_",
            valueType: "fixed",
            fixedValue: "1",
        }),
    },
    {
        id: "create_default",
        label: "Prefill a form field",
        help: "When creating a record, start with this field filled.",
        build: () => ({
            ...emptyRow(),
            key: "default_",
            valueType: "fixed",
            fixedValue: "",
        }),
    },
    {
        id: "group_value",
        label: "Different value by role",
        help: "Value changes based on the user’s security group.",
        build: () => ({
            ...emptyRow(),
            key: "default_type",
            valueType: "group",
            elseValue: "",
            groupRules: [emptyGroupRule()],
        }),
    },
];

/** Purpose for friendly Studio rows (derived from key + value type). */
export function contextRowPurpose(row) {
    if (!row) {
        return "custom";
    }
    if (row.valueType === "record_id") {
        return "card_record";
    }
    if (row.valueType === "group") {
        return "group_setting";
    }
    const key = row.key || "";
    if (key.startsWith("search_default_")) {
        return "search_filter";
    }
    if (key.startsWith("default_")) {
        return "form_default";
    }
    return "custom";
}

export function contextRowTitle(row) {
    const purpose = contextRowPurpose(row);
    if (purpose === "card_record") {
        return "Open with this card";
    }
    if (purpose === "search_filter") {
        return "Turn on a list filter";
    }
    if (purpose === "form_default") {
        return "Prefill a form field";
    }
    if (purpose === "group_setting") {
        return "Different value by role";
    }
    return "Custom setting";
}

export function searchFilterShortName(key) {
    return String(key || "").replace(/^search_default_/, "");
}

export function formDefaultShortName(key) {
    return String(key || "").replace(/^default_/, "");
}

export function toSearchFilterKey(shortName) {
    const name = String(shortName || "")
        .trim()
        .replace(/^search_default_/, "");
    return name ? `search_default_${name}` : "search_default_";
}

export function toFormDefaultKey(shortName) {
    const name = String(shortName || "")
        .trim()
        .replace(/^default_/, "");
    return name ? `default_${name}` : "default_";
}

export function emptyGroupRule() {
    return {
        groupXmlid: "",
        groupLabel: "",
        value: "",
    };
}

function emptyRow() {
    return {
        key: "",
        valueType: "fixed",
        fixedValue: "",
        asList: false,
        elseValue: "",
        groupRules: [emptyGroupRule()],
    };
}

export function createContextPreset(presetId) {
    const preset = CONTEXT_PRESETS.find((p) => p.id === presetId);
    return preset ? preset.build() : emptyRow();
}

export function rowsFromContextRaw(raw) {
    let obj = {};
    try {
        const parsed = typeof raw === "string" ? JSON.parse(raw || "{}") : raw || {};
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            obj = parsed;
        }
    } catch {
        obj = {};
    }
    const rows = Object.entries(obj).map(([key, value]) => rowFromValue(key, value));
    return rows;
}

function rowFromValue(key, value) {
    const row = emptyRow();
    row.key = key;
    if (value === "{{id}}") {
        row.valueType = "record_id";
        row.asList = false;
        return row;
    }
    if (
        Array.isArray(value) &&
        value.length === 1 &&
        (value[0] === "{{id}}" || value[0] === "{{ id }}")
    ) {
        row.valueType = "record_id";
        row.asList = true;
        return row;
    }
    if (value && typeof value === "object" && !Array.isArray(value) && value.__de__ === "group_value") {
        row.valueType = "group";
        row.elseValue =
            value.default === null || value.default === undefined
                ? ""
                : String(value.default);
        const map = Array.isArray(value.map) ? value.map : [];
        row.groupRules = map.length
            ? map.map((entry) => {
                  const groups = entry.groups || [];
                  return {
                      groupXmlid: groups[0] || "",
                      groupLabel: groups[0] || "",
                      value:
                          entry.value === null || entry.value === undefined
                              ? ""
                              : String(entry.value),
                  };
              })
            : [emptyGroupRule()];
        return row;
    }
    row.valueType = "fixed";
    if (value === null || value === undefined) {
        row.fixedValue = "";
    } else if (typeof value === "object") {
        row.fixedValue = JSON.stringify(value);
    } else {
        row.fixedValue = String(value);
    }
    return row;
}

function coerceFixed(text) {
    const t = (text || "").trim();
    if (t === "") {
        return "";
    }
    if (t === "true") {
        return true;
    }
    if (t === "false") {
        return false;
    }
    if (/^-?\d+$/.test(t)) {
        return parseInt(t, 10);
    }
    if (/^-?\d+\.\d+$/.test(t)) {
        return parseFloat(t);
    }
    if ((t.startsWith("{") && t.endsWith("}")) || (t.startsWith("[") && t.endsWith("]"))) {
        try {
            return JSON.parse(t);
        } catch {
            /* keep string */
        }
    }
    return text;
}

export function serializeContextRows(rows) {
    const obj = {};
    for (const row of rows) {
        const key = (row.key || "").trim();
        if (!key) {
            continue;
        }
        if (row.valueType === "record_id") {
            obj[key] = row.asList ? ["{{id}}"] : "{{id}}";
            continue;
        }
        if (row.valueType === "group") {
            const map = [];
            for (const rule of row.groupRules || []) {
                const xmlid = (rule.groupXmlid || "").trim();
                if (!xmlid) {
                    continue;
                }
                map.push({
                    groups: [xmlid],
                    value: coerceFixed(rule.value),
                });
            }
            obj[key] = {
                __de__: "group_value",
                default: coerceFixed(row.elseValue),
                map,
            };
            continue;
        }
        obj[key] = coerceFixed(row.fixedValue);
    }
    return JSON.stringify(obj);
}

export function createEmptyContextRow() {
    return emptyRow();
}

export function collectGroupXmlids(rows) {
    const ids = new Set();
    for (const row of rows || []) {
        if (row.valueType !== "group") {
            continue;
        }
        for (const rule of row.groupRules || []) {
            if (rule.groupXmlid) {
                ids.add(rule.groupXmlid);
            }
        }
    }
    return [...ids];
}

export function applyGroupLabels(rows, labelByXmlid) {
    const map = labelByXmlid || {};
    for (const row of rows || []) {
        if (row.valueType !== "group") {
            continue;
        }
        for (const rule of row.groupRules || []) {
            if (rule.groupXmlid && map[rule.groupXmlid]) {
                rule.groupLabel = map[rule.groupXmlid];
            }
        }
    }
    return rows;
}
