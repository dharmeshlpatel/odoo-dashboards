import { registry } from "@web/core/registry";
import { getColor, getCustomColor, getColors, lightenColor, darkenColor } from "@web/core/colors/colors";
import { formatMonetary } from "@web/views/fields/formatters";
import { cookie } from "@web/core/browser/cookie";

import { _t } from "@web/core/l10n/translation";

import { useService } from "@web/core/utils/hooks";
import { JournalDashboardGraphField } from "@web/views/fields/journal_dashboard_graph/journal_dashboard_graph_field";
import { useState, useEffect, useRef, onMounted, onWillStart, onWillUnmount, onWillUpdateProps } from "@odoo/owl";

const colorScheme = cookie.get("color_scheme");
const GRAPH_GRID_COLOR = getCustomColor(colorScheme, "#d8dadd", "#3C3E4B");
const GRAPH_LABEL_COLOR = getCustomColor(colorScheme, "#111827", "#E4E4E4");

/**
 * Return monetary formatted value if currency is provided.
 *
 * @param {number} value
 * @param {number|null} currencyId
 * @returns {string|number}
 */
function addAlpha(color, opacity) {
    if (color.startsWith('#')) {
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    } else if (color.startsWith('rgb')) {
        return color.replace('rgb', 'rgba').replace(')', `, ${opacity})`);
    }
    return color;
}

function formatValue(value, currencyId) {
    return currencyId
        ? formatMonetary(value, { currencyId })
        : value;
}

export const actionGraphStates = new WeakMap();

export class AnalyticDashboardGraphField extends JournalDashboardGraphField {
    static template = "AnalyticDashboardGraphField";

    setup() {
        super.setup();
        
        // Use WeakMap keyed by env.config (which represents the current action instance)
        // This persists state during internal breadcrumb navigation but naturally resets 
        // when the action is closed/reopened from the menu (since env.config is re-created).
        const configStateKey = `_graph_${this.props.record.resId}`;
        let preservedState = {};
        
        if (this.env.config) {
            let actionState = actionGraphStates.get(this.env.config);
            if (!actionState) {
                actionState = {};
                actionGraphStates.set(this.env.config, actionState);
            }
            preservedState = actionState[configStateKey] || {};
        }

        this.state = useState({
            graphType: preservedState.graphType || this.props.graphType || "bar",
            stacked: preservedState.stacked !== undefined ? preservedState.stacked : true,
            sortOrder: preservedState.sortOrder !== undefined ? preservedState.sortOrder : null,
            cumulated: preservedState.cumulated || false,
            // Phase 9 (lazy-graph UX): data for every visible card is already
            // fetched in one batched read (flat query count regardless of
            // card count — see dashboard_blueprint.py's _build_graph_payloads).
            // What is NOT free is instantiating a Chart.js canvas for every
            // card up front: at 40-80 cards that is 40-80 animated canvases
            // built on first paint, most of them off-screen. Defer the
            // actual `new Chart(...)` call until the card scrolls near the
            // viewport; a lightweight CSS skeleton (GraphLoadingSkeleton)
            // stands in until then. See _setupLazyRender()/renderChart().
            isVisible: false,
        });

        this.rootRef = useRef("root");
        this.processedValues = this._getProcessedValues();

        onWillStart(async () => {
            // Pre-process values for the first render
        });

        onMounted(() => {
            this._setupLazyRender();
            this.syncPrimaryButton();
        });

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
            if (this._lazyObserver) {
                this._lazyObserver.disconnect();
                this._lazyObserver = null;
            }
        });

        onWillUpdateProps((nextProps) => {
            if (nextProps.graphType !== this.props.graphType) {
                this.state.graphType = nextProps.graphType;
            }
            this.processedValues = this._getProcessedValues();
        });

        useEffect(() => {
            if (this.env.config) {
                let actionState = actionGraphStates.get(this.env.config) || {};
                actionState[configStateKey] = {
                    graphType: this.state.graphType,
                    stacked: this.state.stacked,
                    sortOrder: this.state.sortOrder,
                    cumulated: this.state.cumulated,
                };
                actionGraphStates.set(this.env.config, actionState);
            }
            this.processedValues = this._getProcessedValues();
            this.renderChart();
            this.syncPrimaryButton();
        }, () => [
            this.state.graphType,
            this.state.stacked,
            this.state.sortOrder,
            this.state.cumulated,
            this.state.isVisible,
        ]);
    }

    /**
     * Phase 9 (lazy-graph UX): flip `state.isVisible` once, the first time
     * the card scrolls near the viewport, then stop watching — charts don't
     * need to be torn down again just because a card scrolls back off-screen,
     * that would thrash Chart.js for no real benefit.
     */
    _setupLazyRender() {
        const el = this.rootRef.el;
        if (!el || typeof IntersectionObserver === "undefined") {
            // No layout to observe (e.g. a detached/test render) — render
            // eagerly rather than leave the card stuck on its skeleton.
            this.state.isVisible = true;
            return;
        }
        this._lazyObserver = new IntersectionObserver(
            (entries) => {
                if (entries.some((entry) => entry.isIntersecting)) {
                    this.state.isVisible = true;
                    this._lazyObserver.disconnect();
                    this._lazyObserver = null;
                }
            },
            // Start rendering a little before the card is fully on-screen so
            // there is no visible pop-in while scrolling.
            { rootMargin: "200px 0px", threshold: 0.01 }
        );
        this._lazyObserver.observe(el);
    }

    /**
     * Get sorted and filtered values based on current state.
     */
    _getProcessedValues() {
        if (!this || !this.data || !this.data[0] || !this.data[0].values) {
            return [];
        }
        let values = [...this.data[0].values];

        if (this.state.sortOrder) {
            values.sort((a, b) => {
                const sumA = (a.value || a.y || []).reduce((acc, v) => acc + v, 0);
                const sumB = (b.value || b.y || []).reduce((acc, v) => acc + v, 0);
                return this.state.sortOrder === "desc" ? sumB - sumA : sumA - sumB;
            });
        }
        return values;
    }

    onTypeChanged(type) {
        if (!this || !this.state) {
            return;
        }
        this.state.graphType = type;
        // Pie chart doesn't support stacked mode
        if (type === "pie") {
            this.state.stacked = false;
        }
    }

    toggleStacked() {
        if (!this || !this.state || this.state.graphType === "pie") {
            return;
        }
        this.state.stacked = !this.state.stacked;
    }

    toggleCumulated() {
        if (!this || !this.state || this.state.graphType === "pie") {
            return;
        }
        this.state.cumulated = !this.state.cumulated;
    }

    onSortOrderChanged(order) {
        if (!this || !this.state || this.state.graphType === "pie") {
            return;
        }
        if (this.state.sortOrder === order) {
            this.state.sortOrder = null;
        } else {
            this.state.sortOrder = order;
        }
    }


    /**
     * Override parent renderChart to use internal state and custom configurations.
     *
     * No-ops until `state.isVisible` (see _setupLazyRender) — the canvas
     * itself does not exist in the DOM before then (GraphLoadingSkeleton
     * takes its place in the template), so there is nothing to attach to
     * even if this ran early.
     */
    renderChart() {
        if (!this.state.isVisible || !this.canvasRef.el) {
            return;
        }
        if (this.chart) {
            this.chart.destroy();
        }
        const config = this.chartConfig;
        if (config && this.canvasRef.el) {
            this.chart = new Chart(this.canvasRef.el, config);
        }
    }


    onGraphClicked(ev, elements) {
        if (!this || !this.state || !this.data || !this.data[0] || !elements.length || this.data[0].is_sample_data) {
            return;
        }
        const [activeElement] = this.chart.getElementsAtEventForMode(
            ev,
            "nearest",
            { intersect: true },
            false
        );
        if (!activeElement) return;

        const { datasetIndex, index } = activeElement;
        const dataset = this.chart.data.datasets[datasetIndex];
        const label = dataset.label;
        const domains = dataset.domains;
        const value = dataset.data[index] ?? 0;
        
        // Prevent drill-down/action opening for empty datapoints (gap-filled or truly 0).
        if (value === 0 || !domains || !domains[index] || domains[index].length === 0) {
            return;
        }

        // Universal zero-value guard: Always check the raw (non-cumulated) value.
        // If the original value at this exact point in time is 0, block navigation,
        // even if the displayed value is > 0 (e.g. cumulative running total).
        let rawVal = value;
        
        // We only need to deeply resolve the raw value for cumulative line charts.
        // For pie/bar/regular line charts, `value` is already the raw value.
        // Pie charts flatten the data matrix, so the deep lookup by `index` would fail anyway.
        if (this.state.cumulated && this.state.graphType === 'line') {
            const values = this.processedValues;
            if (label === _t("Sum")) {
                // For the Sum dataset, raw value is the sum of all raw values at this index
                const pointVals = values[index]?.y || values[index]?.value || [];
                rawVal = 0;
                for (let i = 0; i < pointVals.length; i++) {
                    rawVal += pointVals[i] ?? 0;
                }
            } else {
                // For standard datasets, find its index in the raw data matrix
                const allDatasets = this.chart.data.datasets;
                let seriesIdx = 0;
                for (let d = 0; d < allDatasets.length; d++) {
                    if (allDatasets[d] === dataset) {
                        seriesIdx = d;
                        break;
                    }
                }
                rawVal = (values[index]?.y || values[index]?.value || [])[seriesIdx] ?? 0;
            }
        }

        if (rawVal === 0) {
            return; // Block navigation for zero-value points
        }

        let finalDomain = domains[index];
        
        // For cumulative line charts, the domain should include all records up to this point
        if (this.state.cumulated && this.state.graphType === 'line') {
            finalDomain = [];
            for (let i = 0; i <= index; i++) {
                if (domains[i] && domains[i].length) {
                    if (finalDomain.length === 0) {
                        finalDomain = [...domains[i]];
                    } else {
                        finalDomain = ["|", ...finalDomain, ...domains[i]];
                    }
                }
            }
        }

        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            name: this.state.graphType === 'pie' ? this.chart.data.labels[index] : label,
            res_model: dataset.model || this.data[0].model || 'crm.lead',
            views: [[false, 'list'], [false, 'form']],
            domain: finalDomain,
            target: 'current',
            context: {
                ...this.env.context,
                active_id: this.props.record.resId,
            }
        });
    }

    /**
     * Override standard config getter to route based on state.
     */
    get chartConfig() {
        const { graphType } = this.state;
        let data;
        switch (graphType) {
            case "bar":
                data = this.getBarChartData();
                break;
            case "line":
                data = this.getLineChartData();
                break;
            case "pie":
                data = this.getPieChartData();
                break;
            default:
                data = this.getBarChartData();
        }
        const options = this.prepareOptions();
        return { data, options, type: graphType };
    }

    getAnimationOptions() {
        let delayed = false;
        const { graphType } = this.state;
        const labelsCount = this.processedValues.length;
        const gap = 350;
        const animationOptions = {};
        if (graphType === "pie") {
            animationOptions.offset = { duration: 200 };
        } else {
            animationOptions.duration = 600;
            animationOptions.onComplete = () => {
                delayed = true;
            };
            animationOptions.delay = (context) => {
                let delay = 0;
                if ((graphType === "bar" || graphType === "line") && !delayed) {
                    delay = context.dataIndex * (gap / labelsCount);
                }
                return delay;
            };
        }
        return animationOptions;
    }

    /**
     * Returns legend configuration matching Odoo standard graph_renderer.js behavior.
     * For pie charts: generates labels from chart.data.labels (one per slice).
     * For bar/line charts: generates labels from datasets (one per group).
     */
    _getLegendOptions(graphType) {
        const legendOptions = {
            display: true,
        };

        if (graphType === 'pie') {
            legendOptions.position = 'right';
            legendOptions.align = 'center';
            legendOptions.labels = {
                color: GRAPH_LABEL_COLOR,
                boxWidth: 12,
                boxHeight: 12,
                padding: 10,
                // Odoo standard: pie legends come from chart.data.labels, NOT datasets
                generateLabels: (chart) => {
                    return chart.data.labels.map((label, index) => {
                        const hidden = !chart.getDataVisibility(index);
                        const fillStyle = getColor(index, colorScheme, chart.data.labels.length);
                        return {
                            text: label,
                            fullText: label,
                            fillStyle,
                            hidden,
                            index,
                            fontColor: GRAPH_LABEL_COLOR,
                            lineWidth: 0,
                        };
                    });
                },
            };
        } else {
            legendOptions.position = 'top';
            legendOptions.align = 'end';
            const referenceColor = graphType === 'bar' ? 'backgroundColor' : 'borderColor';
            legendOptions.labels = {
                color: GRAPH_LABEL_COLOR,
                boxWidth: 12,
                boxHeight: 12,
                padding: 10,
                generateLabels: (chart) => {
                    const { data } = chart;
                    return data.datasets.map((dataset, index) => {
                        // For Sum or overlay lines on bar charts, use borderColor
                        const color = dataset.type === 'line' 
                            ? (dataset.pointBackgroundColor || dataset.borderColor)
                            : dataset[referenceColor];
                        return {
                            text: dataset.label,
                            fullText: dataset.label,
                            fillStyle: color,
                            hidden: !chart.isDatasetVisible(index),
                            strokeStyle: color,
                            lineWidth: dataset.borderWidth || 0,
                            datasetIndex: index,
                            fontColor: GRAPH_LABEL_COLOR,
                        };
                    });
                },
                sort: (a, b) => {
                    // Maintain array ordering so Sum is always last
                    return a.datasetIndex - b.datasetIndex;
                },
            };
        }
        return legendOptions;
    }

    prepareOptions() {
        const { graphType, stacked } = this.state;
        const options = {
            onClick: (ev, elements, chart) => this.onGraphClicked(ev, elements),
            maintainAspectRatio: false,
            scales: this.getScaleOptions(),
            plugins: {
                legend: this._getLegendOptions(graphType),
                tooltip: {
                    enabled: false,
                    position: "nearest",
                    external: (context) => this._renderExternalTooltip(context),
                },
            },
            animation: this.getAnimationOptions(),
            onHover: (ev, elements) => {
                ev.native.target.style.cursor = elements[0] ? "pointer" : "default";
            },
        };

        if (graphType === "line") {
            options.interaction = {
                mode: "index",
                intersect: false,
            };
        }
        if (graphType === "pie") {
            options.radius = "90%";
        }
        return options;
    }

    getScaleOptions() {
        const { graphType, stacked } = this.state;
        if (graphType === "pie") return {};

        const isLine = graphType === "line";
        return {
            y: {
                beginAtZero: true,
                stacked: isLine ? stacked : undefined,
                grid: { color: GRAPH_GRID_COLOR },
                ticks: {
                    color: GRAPH_LABEL_COLOR,
                    callback: (value) => new Intl.NumberFormat('en-US', { 
                        notation: 'compact', 
                        maximumFractionDigits: 2 
                    }).format(value),
                },
                border: { display: false }
            },
            x: {
                stacked: isLine ? stacked : undefined,
                grid: { display: false },
                ticks: { color: GRAPH_LABEL_COLOR },
                border: { color: GRAPH_GRID_COLOR }
            }
        };
    }

    _resolveGroupColor(colorKey, colorIndexByKey, colorCount) {
        return getColor(
            colorIndexByKey.get(colorKey) ?? 0,
            colorScheme,
            colorCount
        );
    }

    getBarChartData() {
        const values = this.processedValues;
        const labels = values.map(v => v.label || v.x);
        const maxValues = Math.max(...values.map(v => (v.value || v.y || []).length));
        const { stacked } = this.state;
        
        const allGroupKeys = new Set();
        values.forEach(pt => {
            (pt.group_color_keys || []).forEach(k => allGroupKeys.add(k));
        });
        const sortedColorKeys = Array.from(allGroupKeys);
        
        const datasets = [];
        for (let i = 0; i < maxValues; i++) {
            const datasetData = [];
            const groupNames = [];
            const domains = [];
            const seriesName = sortedColorKeys[i] || this.data[0].key;
            const itemColor = getColor(i, colorScheme, maxValues);

            values.forEach((pt) => {
                const val = (pt.value || pt.y || [])[i] ?? 0;
                datasetData.push(val);
                groupNames.push(pt.group_names?.[i] ?? "");
                domains.push(pt.domains?.[i] || []);
            });

            const dataset = {
                label: seriesName,
                data: datasetData,
                backgroundColor: itemColor,
                borderRadius: 4,
                group_names: groupNames,
                domains: domains,
                currencyId: this.data[0].currency_id,
                order: 1, // Explicitly place below Sum line
            };

            if (stacked) {
                dataset.stack = "stack-0";
            }

            datasets.push(dataset);
        }

        // Standard Odoo Sum line for Bar charts (Only visible in stacked mode)
        if (maxValues > 1 && !this.data[0].is_sample_data && this.state.stacked) {
            const sumData = labels.map((_, idx) => {
                let sum = 0;
                for (let i = 0; i < maxValues; i++) {
                    sum += (values[idx].y || values[idx].value || [])[i] ?? 0;
                }
                return sum;
            });
            
            // Generate combined domains for the Sum points.
            // Backend domains are mixed: they contain both prefix operators
            // ('&' for date ranges) and bare tuples (implicit AND).
            // To properly OR-join them using Odoo prefix notation, each group's
            // domain must be evaluated as a SINGLE operand. We count the top-level
            // operands in each domain using a stack approach, and prepend N-1 '&' ops.
            const makeSingleOperand = (dom) => {
                if (!dom || dom.length <= 1) return dom || [];
                let operandsCount = 0;
                let expectedArgs = 0;
                
                for (let i = 0; i < dom.length; i++) {
                    if (expectedArgs === 0) {
                        operandsCount++;
                        expectedArgs = 1;
                    }
                    const item = dom[i];
                    if (typeof item === 'string' && (item === '&' || item === '|')) {
                        expectedArgs += 1;
                    } else if (typeof item === 'string' && item === '!') {
                        expectedArgs += 0;
                    } else {
                        expectedArgs -= 1;
                    }
                }
                
                if (operandsCount <= 1) return dom;
                const andOps = Array(operandsCount - 1).fill('&');
                return [...andOps, ...dom];
            };

            const sumDomains = labels.map((_, idx) => {
                const groupDomains = [];
                for (let i = 0; i < maxValues; i++) {
                    const d = (values[idx].domains || [])[i];
                    if (d && d.length) {
                        groupDomains.push(makeSingleOperand(d));
                    }
                }
                if (groupDomains.length === 0) return [];
                if (groupDomains.length === 1) return groupDomains[0];
                
                // N single operands need N-1 '|' ops
                const orOps = Array(groupDomains.length - 1).fill('|');
                return [...orOps, ...groupDomains.flat()];
            });

            datasets.push({
                label: _t("Sum"),
                data: sumData,
                domains: sumDomains,
                type: 'line',
                borderColor: '#4b5563', // Slate gray for better visibility and matching tooltip
                borderWidth: 1.5,
                fill: false,
                pointRadius: 3,
                pointHoverRadius: 5,
                tension: 0, // Ensure Sum lines are perfectly straight
                order: 0, // Ensure it's rendered on top
                yAxisID: 'y',
                pointBackgroundColor: '#4b5563', // Solid color for both line and points
                currencyId: this.data[0].currency_id,
            });
        }

        return { labels, datasets };
    }

    getLineChartData() {
        const values = this.processedValues;
        const labels = values.map(v => v.label || v.x);
        const maxValues = Math.max(...values.map(v => (v.value || v.y || []).length));
        
        const allGroupKeys = new Set();
        values.forEach(pt => {
            (pt.group_color_keys || []).forEach(k => allGroupKeys.add(k));
        });
        const sortedColorKeys = Array.from(allGroupKeys);

        const datasets = [];
        for (let i = 0; i < maxValues; i++) {
            const itemColor = getColor(i, colorScheme, maxValues);
            const seriesName = sortedColorKeys[i] || this.data[0].key;
            // Standard Odoo line fill color
            const rgbaColor = getCustomColor(
                colorScheme,
                lightenColor(itemColor, 0.5),
                darkenColor(itemColor, 0.5)
            );

            let data = values.map(v => (v.y || v.value || [])[i] ?? 0);
            if (this.state.cumulated) {
                let sum = 0;
                data = data.map(v => {
                    sum += (v ?? 0);
                    return sum;
                });
            }

            datasets.push({
                label: seriesName,
                data: data,
                domains: values.map(v => (v.domains || [])[i] ?? []),
                backgroundColor: addAlpha(itemColor, 0.4), // Standard Odoo opacity
                borderColor: itemColor,
                pointBackgroundColor: itemColor,
                pointBorderColor: "rgba(0,0,0,0.1)",
                fill: this.state.stacked ? "origin" : false,
                borderWidth: 2,
                tension: 0.4, // Smooth curved lines
                pointRadius: 3,
                pointHoverRadius: 6,
                currencyId: this.data[0].currency_id,
                order: 1, // Ensure lines stay below potential overlays
            });
        }
        return { labels, datasets };
    }

    getPieChartData() {
        const values = this.processedValues;
        const labels = [];
        const data = [];
        const domains = [];
        
        // Flatten the data matrix for Pie Chart (Odoo standard behavior)
        values.forEach(v => {
            const yArr = v.value || v.y || [];
            const namesArr = v.group_names || [];
            const domainArr = v.domains || [];
            
            if (yArr.length <= 1 && namesArr.length === 0) {
                const val = yArr[0] ?? 0;
                if (val !== 0) {
                    labels.push(v.label || v.x);
                    data.push(val);
                    domains.push(domainArr[0] || []);
                }
            } else {
                yArr.forEach((val, i) => {
                    if (val !== 0) {
                        // Backend group_names already contain the full composite label
                        // (e.g. "2026-04-13 / Marc Demo / Won") — use directly
                        const label = namesArr[i] || (v.label || v.x || _t("None"));
                        labels.push(label);
                        data.push(val);
                        domains.push(domainArr[i] || []);
                    }
                });
            }
        });

        // Generate distinct colors for every flattened slice (only active ones)
        const colors = labels.map((_, i) => getColor(i, colorScheme, labels.length));

        return {
            labels,
            datasets: [{
                label: this.data[0].key || _t("Value"),
                data,
                backgroundColor: colors,
                hoverBackgroundColor: colors,
                borderColor: getCustomColor(colorScheme, "#ffffff", "#1e1e1e"),
                borderWidth: 1,
                hoverOffset: 10,
                domains: domains,
                currencyId: this.data[0] ? this.data[0].currency_id : null,
            }]
        };
    }

    _renderExternalTooltip(context) {
        let tooltipEl = document.getElementById('chartjs-tooltip');
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.id = 'chartjs-tooltip';
            tooltipEl.className = 'o_graph_custom_tooltip popover show position-absolute';
            Object.assign(tooltipEl.style, {
                opacity: 1,
                pointerEvents: 'none',
                zIndex: '1000',
                maxWidth: 'none' // Prevent standard popover max-width from truncating content
            });
            document.body.appendChild(tooltipEl);
        }

        const tooltipModel = context.tooltip;
        if (tooltipModel.opacity === 0) {
            tooltipEl.style.opacity = 0;
            return;
        }

        if (tooltipModel.body) {
            const { graphType } = this.state;
            
            let points = [...tooltipModel.dataPoints];
            
            // Tooltip title is always the Measure name (e.g., "Expected Revenue" or "Count")
            const title = this.data[0]?.key || _t("Value");

            let innerHtml = '<div class="px-2 py-1">';
            innerHtml += `<div class="o_tooltip_title mb-1" style="font-weight: 600; color: #111827; font-size: 13px;">${title}</div>`;

            innerHtml += '<table class="w-100 border-separate" style="border-spacing: 0 2px;">';
            innerHtml += '<tbody>';
            
            if (graphType !== 'pie') {
                points.sort((a, b) => {
                    const valA = (graphType === "line" || a.dataset.type === 'line') ? (a.dataset.data[a.dataIndex] ?? 0) : (a.parsed?.y ?? a.parsed ?? 0);
                    const valB = (graphType === "line" || b.dataset.type === 'line') ? (b.dataset.data[b.dataIndex] ?? 0) : (b.parsed?.y ?? b.parsed ?? 0);
                    return valB - valA;
                });
            }

            // Deduplicate based on the final generated label to guarantee no duplicates
            const seenLabels = new Set();

            points.forEach((dataPoint) => {
                const dataset = dataPoint.dataset;
                const idx = dataPoint.dataIndex;
                const val = (graphType === "line" || dataset.type === 'line') ? (dataset.data[idx] ?? 0) : (dataPoint.parsed?.y ?? dataPoint.parsed ?? 0);
                
                if (val === 0 && graphType === 'bar' && dataset.type !== 'line') return;

                let boxColor;
                let percentage = "";
                if (graphType === 'pie') {
                    boxColor = dataset.backgroundColor[idx];
                    const totalData = dataset.data.reduce((a, b) => a + b, 0);
                    percentage = totalData ? `(${(val * 100 / totalData).toFixed(1)}%)` : "";
                } else {
                    boxColor = (graphType === "bar" && dataset.type !== 'line') ? dataset.backgroundColor : dataset.borderColor;
                }
                
                // Odoo Standard Row Label Format
                let label;
                if (graphType === 'pie') {
                    // For pie charts, the title is the measure (e.g. "Value"), and the rows are the slice labels (e.g. "Gemini / Sales")
                    label = dataPoint.label;
                } else {
                    if (dataset.label === _t("Sum")) {
                        label = _t("Sum");
                    } else {
                        // For bar/line, the title is the X-axis label, and the rows are the dataset group names
                        label = dataset.group_names?.[idx] || dataset.label || _t("None");
                    }
                }

                // Skip if we already rendered this exact label in the tooltip
                if (seenLabels.has(label)) {
                    return;
                }
                seenLabels.add(label);

                const currencyId = dataset.currencyId || (this.data[0] ? this.data[0].currency_id : null);
                const formattedVal = formatMonetary(val, { currencyId });

                innerHtml += `
                    <tr>
                        <td class="pe-3" style="white-space: nowrap;">
                            <div style="display: flex; align-items: center;">
                                <span class="o_square badge rounded-0 align-middle me-2" style="display: inline-block; width: 10px; height: 10px; background-color: ${boxColor};"></span>
                                <small class="o_label d-inline-block text-truncate align-middle" style="color: #111827; font-size: 12px; max-width: 200px;">${label}</small>
                            </div>
                        </td>
                        <td class="text-end fw-bolder" style="white-space: nowrap; color: #111827; font-size: 12px;">
                            ${formattedVal} <t t-if="percentage"><small class="text-muted ms-1">${percentage}</small></t>
                        </td>
                    </tr>

                `;
            });
            innerHtml += '</tbody></table></div>';
            tooltipEl.innerHTML = innerHtml;
        }

        const position = context.chart.canvas.getBoundingClientRect();
        tooltipEl.style.opacity = 1;
        // Position tooltip to the side of the caret if it's too close to the top or centered normally
        tooltipEl.style.left = position.left + window.pageXOffset + tooltipModel.caretX + 'px';
        tooltipEl.style.top = position.top + window.pageYOffset + tooltipModel.caretY + 'px';
        tooltipEl.style.transform = 'translate(-50%, -110%)';
        
        // Ensure tooltip stays within window bounds
        const tooltipRect = tooltipEl.getBoundingClientRect();
        if (tooltipRect.left < 0) {
            tooltipEl.style.left = '10px';
            tooltipEl.style.transform = 'translate(0, -110%)';
        } else if (tooltipRect.right > window.innerWidth) {
            tooltipEl.style.left = (window.innerWidth - 10) + 'px';
            tooltipEl.style.transform = 'translate(-100%, -110%)';
        }
    }

    /**
     * Intercept the primary "Pipeline Analysis" button click to inject
     * the current graph state into the opened view context.
     */
    syncPrimaryButton() {
        if (!this.el) return;
        const recordEl = this.el.closest('.o_kanban_record');
        if (!recordEl) return;
        
        const primaryBtn = recordEl.querySelector('button[name="action_primary_button"]');
        if (!primaryBtn) return;

        if (primaryBtn._hasDashboardListener) return;
        
        primaryBtn.onclick = (ev) => {
            ev.stopPropagation();
            ev.preventDefault();
            const { graphType, stacked, sortOrder, cumulated } = this.state;
            
            this.env.services.action.doActionButton({
                name: "action_primary_button",
                type: "object",
                resId: this.props.record.resId,
                resModel: this.props.record.resModel,
                context: {
                    ...this.env.context,
                    graph_mode: graphType,
                    graph_stacked: stacked,
                    graph_order: sortOrder,
                    graph_cumulated: cumulated,
                    dashboard_rendering: true,
                },
            });
        };
        primaryBtn._hasDashboardListener = true;
    }
}

export const analyticDashboardGraphField = {
    component: AnalyticDashboardGraphField,
    supportedTypes: ["text"],
    extractProps: ({ attrs }) => ({
        graphType: attrs.graph_type,
    }),
};

registry.category("fields").add("analytic_dashboard_graph", analyticDashboardGraphField);