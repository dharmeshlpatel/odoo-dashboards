/** @odoo-module **/

/**
 * Parse / serialize dashboard action-context for the friendly KV UI.
 * Runtime still uses __de__ tokens; admins never edit raw JSON.
 */

export const VALUE_TYPES = [
    { value: "fixed", label: "Always the same value" },
    { value: "record_id", label: "This card’s id" },
    { value: "group", label: "Depends on the user’s groups" },
];

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
    if (!rows.length) {
        rows.push(emptyRow());
    }
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
