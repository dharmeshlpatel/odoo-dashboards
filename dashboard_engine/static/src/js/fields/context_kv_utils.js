/** @odoo-module **/

/**
 * Parse / serialize dashboard action-context for the friendly KV UI.
 * Runtime still uses __de__ tokens; admins never edit raw JSON.
 */

export const VALUE_TYPES = [
    { value: "fixed", label: "Fixed Value" },
    { value: "record_id", label: "This Card’s ID" },
    { value: "group", label: "Set Value By Rule" },
];

/** How to pass the card record (stored key stays technical; UI shows labels). */
export const CARD_PASS_TARGETS = [
    { key: "active_id", label: "As the Active Record" },
    { key: "default_partner_id", label: "As the Customer on New Forms" },
    { key: "default_user_id", label: "As the Salesperson on New Forms" },
];

/**
 * One-click presets — plain language; keys are filled for the builder.
 * Labels use Odoo / Studio title case (same as Group By, Graph Title).
 */
export const CONTEXT_PRESETS = [
    {
        id: "card_id",
        label: "Open with This Record",
        help: "Use this card’s record when the action opens.",
        build: () => ({
            ...emptyRow(),
            key: "active_id",
            valueType: "record_id",
            asList: false,
        }),
    },
    {
        id: "search_filter",
        label: "Apply a Search Filter",
        help: "Turn on a filter from the target list when it opens.",
        build: () => ({
            ...emptyRow(),
            key: "search_default_",
            valueType: "fixed",
            fixedValue: "1",
        }),
    },
    {
        id: "create_default",
        label: "Prefill a Form Field",
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
        label: "Set Value By Rule",
        help: "Value changes by user group or card condition (first match wins).",
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
        return "Open with This Record";
    }
    if (purpose === "search_filter") {
        return "Apply a Search Filter";
    }
    if (purpose === "form_default") {
        return "Prefill a Form Field";
    }
    if (purpose === "group_setting") {
        return "Set Value By Rule";
    }
    return "Custom Setting";
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
        whenType: "group",
        groupXmlid: "",
        groupLabel: "",
        domain: "[]",
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

function domainToString(domain) {
    if (domain === null || domain === undefined) {
        return "[]";
    }
    if (typeof domain === "string") {
        return domain.trim() || "[]";
    }
    try {
        return JSON.stringify(domain);
    } catch {
        return "[]";
    }
}

function ruleFromMapEntry(entry) {
    const when = entry && typeof entry === "object" ? entry.when : null;
    const value =
        entry?.value === null || entry?.value === undefined
            ? ""
            : String(entry.value);
    if (when && typeof when === "object") {
        const wtype = when.type || "group";
        if (wtype === "record") {
            return {
                whenType: "record",
                groupXmlid: "",
                groupLabel: "",
                domain: domainToString(when.domain),
                value,
            };
        }
        const groups = when.groups || [];
        return {
            whenType: "group",
            groupXmlid: groups[0] || "",
            groupLabel: groups[0] || "",
            domain: "[]",
            value,
        };
    }
    const groups = entry?.groups || [];
    if (entry?.domain !== undefined && !groups.length) {
        return {
            whenType: "record",
            groupXmlid: "",
            groupLabel: "",
            domain: domainToString(entry.domain),
            value,
        };
    }
    return {
        whenType: "group",
        groupXmlid: groups[0] || "",
        groupLabel: groups[0] || "",
        domain: "[]",
        value,
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
    if (
        value &&
        typeof value === "object" &&
        !Array.isArray(value) &&
        (value.__de__ === "group_value" || value.__de__ === "rule_value")
    ) {
        row.valueType = "group";
        row.elseValue =
            value.default === null || value.default === undefined
                ? ""
                : String(value.default);
        const map = Array.isArray(value.map) ? value.map : [];
        row.groupRules = map.length
            ? map.map((entry) => ruleFromMapEntry(entry))
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
            const rules = row.groupRules || [];
            const hasRecord = rules.some(
                (rule) =>
                    (rule.whenType || "group") === "record" &&
                    (rule.domain || "[]").trim() &&
                    (rule.domain || "[]").trim() !== "[]"
            );
            const map = [];
            for (const rule of rules) {
                if ((rule.whenType || "group") === "record") {
                    const domain = (rule.domain || "[]").trim() || "[]";
                    if (domain === "[]") {
                        continue;
                    }
                    map.push({
                        when: { type: "record", domain },
                        value: coerceFixed(rule.value),
                    });
                    continue;
                }
                const xmlid = (rule.groupXmlid || "").trim();
                if (!xmlid) {
                    continue;
                }
                if (hasRecord) {
                    map.push({
                        when: { type: "group", groups: [xmlid] },
                        value: coerceFixed(rule.value),
                    });
                } else {
                    map.push({
                        groups: [xmlid],
                        value: coerceFixed(rule.value),
                    });
                }
            }
            obj[key] = {
                __de__: hasRecord ? "rule_value" : "group_value",
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
            if ((rule.whenType || "group") === "group" && rule.groupXmlid) {
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
