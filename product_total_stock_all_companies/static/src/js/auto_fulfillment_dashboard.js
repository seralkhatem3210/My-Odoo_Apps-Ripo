/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class AutoFulfillmentDashboard extends Component {
    static template = "product_total_stock_all_companies.AutoFulfillmentDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.chartDestinationCompanyRef = useRef("chartDestinationCompany");
        this.chartTypePieRef = useRef("chartTypePie");
        this.chartStateDonutRef = useRef("chartStateDonut");


        this.state = useState({
            loading: true,
            filtersLoading: true,
            filters: {
                date_from: "",
                date_to: "",
                company_id: "",
                fulfillment_type: "",
                state: "",
            },
            options: {
                companies: [],
                types: [
                    { value: "", label: "All Types" },
                    { value: "internal", label: "Internal" },
                    { value: "intercompany", label: "Intercompany" },
                ],
                states: [
                    { value: "", label: "All States" },
                    { value: "done", label: "Done" },
                    { value: "failed", label: "Failed" },
                ],
            },
            data: {
                kpis: {},
                top_warehouses: [],
                top_products: [],
                top_destination_companies: [],
                daily_trend: [],
                recent_logs: [],
            },
        });

        this.chartWarehouseRef = useRef("chartWarehouse");
        this.chartProductRef = useRef("chartProduct");
        this.chartTrendRef = useRef("chartTrend");

        this.warehouseChart = null;
        this.productChart = null;
        this.trendChart = null;

        this.destinationCompanyChart = null;
        this.typePieChart = null;
        this.stateDonutChart = null;


        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadFilterOptions();
            await this.loadDashboard();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadFilterOptions() {
        this.state.filtersLoading = true;
        try {
            const result = await this.orm.call(
                "auto.fulfillment.dashboard",
                "get_filter_options",
                []
            );
            this.state.options.companies = [{ id: "", name: "All Companies" }, ...(result.companies || [])];
        } catch (error) {
            this.notification.add("Failed to load dashboard filters.", { type: "danger" });
        } finally {
            this.state.filtersLoading = false;
        }
    }

    // async loadDashboard() {
    //     this.state.loading = true;
    //     try {
    //         this.state.data = await this.orm.call(
    //             "auto.fulfillment.dashboard",
    //             "get_dashboard_data",
    //             [this.state.filters]
    //         );
    //     } catch (error) {
    //         this.notification.add("Failed to load dashboard data.", { type: "danger" });
    //     } finally {
    //         this.state.loading = false;
    //         requestAnimationFrame(() => this.renderCharts());
    //     }
    // }
    async loadDashboard() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "auto.fulfillment.dashboard",
                "get_dashboard_data",
                [this.state.filters]
            );
        } catch (error) {
            this.notification.add("Failed to load dashboard data.", { type: "danger" });
        } finally {
            this.state.loading = false;
            setTimeout(() => this.renderCharts(), 50);
        }
    }


    onFilterChange(ev) {
        const field = ev.target.name;
        this.state.filters[field] = ev.target.value;
    }

    async applyFilters() {
        await this.loadDashboard();
    }

    async resetFilters() {
        this.state.filters.date_from = "";
        this.state.filters.date_to = "";
        this.state.filters.company_id = "";
        this.state.filters.fulfillment_type = "";
        this.state.filters.state = "";
        await this.loadDashboard();
    }

    renderCharts() {
        if (this.state.loading || !window.Chart) {
            return;
        }

        this._destroyCharts();

        this.warehouseChart = this._renderBarChart(
            this.chartWarehouseRef.el,
            this.state.data.top_warehouses || [],
            "Top Source Warehouses",
            (index) => this.openLogsWithExtraDomain([
                ["source_warehouse_id", "!=", false],
            ])
        );

        this.productChart = this._renderBarChart(
            this.chartProductRef.el,
            this.state.data.top_products || [],
            "Top Products by Fulfilled Qty",
            (index) => this.openLogsWithExtraDomain([
                ["product_id", "!=", false],
            ])
        );

        this.destinationCompanyChart = this._renderBarChart(
            this.chartDestinationCompanyRef.el,
            this.state.data.top_destination_companies || [],
            "Top Destination Companies",
            (index) => this.openLogsWithExtraDomain([
                ["destination_company_id", "!=", false],
            ])
        );

        this.typePieChart = this._renderPieChart(
            this.chartTypePieRef.el,
            this.state.data.fulfillment_type_split || [],
            "Fulfillment Type Split"
        );

        this.stateDonutChart = this._renderDoughnutChart(
            this.chartStateDonutRef.el,
            this.state.data.state_split || [],
            "State Split"
        );

        this.trendChart = this._renderLineChart(
            this.chartTrendRef.el,
            this.state.data.daily_trend || [],
            "Daily Fulfillment Trend"
        );
    }

    _destroyCharts() {
        if (this.warehouseChart) {
            this.warehouseChart.destroy();
            this.warehouseChart = null;
        }
        if (this.productChart) {
            this.productChart.destroy();
            this.productChart = null;
        }
        if (this.trendChart) {
            this.trendChart.destroy();
            this.trendChart = null;
        }
        if (this.destinationCompanyChart) {
            this.destinationCompanyChart.destroy();
            this.destinationCompanyChart = null;
        }
        if (this.typePieChart) {
            this.typePieChart.destroy();
            this.typePieChart = null;
        }
        if (this.stateDonutChart) {
            this.stateDonutChart.destroy();
            this.stateDonutChart = null;
        }

    }

    // _renderBarChart(canvas, rows, label, onClickHandler = null) {
    //     if (!canvas) return null;
    //     const ctx = canvas.getContext("2d");

    //     return new window.Chart(ctx, {
    //         type: "bar",
    //         data: {
    //             labels: rows.map((r) => r.label),
    //             datasets: [{
    //                 label,
    //                 data: rows.map((r) => r.value),
    //                 borderRadius: 8,
    //                 maxBarThickness: 48,
    //             }],
    //         },
    //         options: {
    //             responsive: true,
    //             maintainAspectRatio: false,
    //             plugins: {
    //                 legend: { display: true },
    //             },
    //             onClick: (event, elements) => {
    //                 if (elements.length && onClickHandler) {
    //                     onClickHandler(elements[0].index);
    //                 }
    //             },
    //         },
    //     });
    // }
 

    _renderBarChart(canvas, rows, label, onClickHandler = null) {
        if (!canvas) return null;
        const ctx = canvas.getContext("2d");

        const safeRows = rows && rows.length ? rows : [{ label: "No Data", value: 0 }];

        return new window.Chart(ctx, {
            type: "bar",
            data: {
                labels: safeRows.map((r) => r.label),
                datasets: [{
                    label,
                    data: safeRows.map((r) => r.value),
                    borderRadius: 8,
                    maxBarThickness: 48,
                    backgroundColor: [
                        "#5B8FF9", "#61DDAA", "#65789B", "#F6BD16", "#7262FD",
                        "#78D3F8", "#9661BC", "#F6903D", "#008685", "#F08BB4"
                    ],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                    },
                },
                plugins: {
                    legend: { display: true },
                },
                onClick: (event, elements) => {
                    if (elements.length && onClickHandler) {
                        onClickHandler(elements[0].index);
                    }
                },
            },
        });
    }

    _renderLineChart(canvas, rows, label, onClickHandler = null) {
        if (!canvas) return null;
        const ctx = canvas.getContext("2d");

        const safeRows = rows && rows.length ? rows : [{ label: "No Data", value: 0 }];

        return new window.Chart(ctx, {
            type: "line",
            data: {
                labels: safeRows.map((r) => r.label),
                datasets: [{
                    label,
                    data: safeRows.map((r) => r.value),
                    tension: 0.35,
                    fill: false,
                    borderColor: "#3B82F6",
                    backgroundColor: "#3B82F6",
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                    },
                },
                plugins: {
                    legend: { display: true },
                },
                onClick: (event, elements) => {
                    if (elements.length && onClickHandler) {
                        onClickHandler(elements[0].index);
                    }
                },
            },
        });
    }


    _renderDoughnutChart(canvas, rows, label) {
        if (!canvas) return null;
        const ctx = canvas.getContext("2d");

        const safeRows = rows && rows.length ? rows : [{ label: "No Data", value: 1 }];

        return new window.Chart(ctx, {
            type: "doughnut",
            data: {
                labels: safeRows.map((r) => r.label),
                datasets: [{
                    label,
                    data: safeRows.map((r) => r.value),
                    backgroundColor: [
                        "#22C55E", "#EF4444", "#F59E0B", "#3B82F6", "#8B5CF6"
                    ],
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "60%",
                plugins: {
                    legend: { position: "bottom" },
                },
            },
        });
    }


    // _renderPieChart(canvas, rows, label) {
    //     if (!canvas) return null;
    //     const ctx = canvas.getContext("2d");
    //     return new window.Chart(ctx, {
    //         type: "pie",
    //         data: {
    //             labels: rows.map((r) => r.label),
    //             datasets: [{
    //                 label,
    //                 data: rows.map((r) => r.value),
    //             }],
    //         },
    //         options: {
    //             responsive: true,
    //             maintainAspectRatio: false,
    //         },
    //     });
    // }
    _renderPieChart(canvas, rows, label) {
        if (!canvas) return null;
        const ctx = canvas.getContext("2d");

        const safeRows = rows && rows.length ? rows : [{ label: "No Data", value: 1 }];

        return new window.Chart(ctx, {
            type: "pie",
            data: {
                labels: safeRows.map((r) => r.label),
                datasets: [{
                    label,
                    data: safeRows.map((r) => r.value),
                    backgroundColor: [
                        "#5B8FF9", "#61DDAA", "#65789B", "#F6BD16", "#7262FD",
                        "#78D3F8", "#9661BC", "#F6903D"
                    ],
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                },
            },
        });
    }


    _getBaseDomain() {
        const domain = [];

        if (this.state.filters.date_from) {
            domain.push(["create_date", ">=", this.state.filters.date_from]);
        }
        if (this.state.filters.date_to) {
            domain.push(["create_date", "<=", this.state.filters.date_to]);
        }
        if (this.state.filters.company_id) {
            domain.push(["destination_company_id", "=", parseInt(this.state.filters.company_id)]);
        }
        if (this.state.filters.fulfillment_type) {
            domain.push(["fulfillment_type", "=", this.state.filters.fulfillment_type]);
        }
        if (this.state.filters.state) {
            domain.push(["state", "=", this.state.filters.state]);
        }

        return domain;
    }

    openLogs() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Auto Fulfillment Logs",
            res_model: "auto.fulfillment.log",
            view_mode: "list,form,pivot,graph",
            domain: this._getBaseDomain(),
        });
    }

    openLogsWithExtraDomain(extraDomain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Auto Fulfillment Logs",
            res_model: "auto.fulfillment.log",
            view_mode: "list,form,pivot,graph",
            domain: [...this._getBaseDomain(), ...extraDomain],
        });
    }

    openKpi(type) {
        let extraDomain = [];
        if (type === "internal") {
            extraDomain = [["fulfillment_type", "=", "internal"]];
        } else if (type === "intercompany") {
            extraDomain = [["fulfillment_type", "=", "intercompany"]];
        } else if (type === "failed") {
            extraDomain = [["state", "=", "failed"]];
        }
        this.openLogsWithExtraDomain(extraDomain);
    }

    openLog(logId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "auto.fulfillment.log",
            res_id: logId,
            view_mode: "form",
            target: "current",
        });
    }
}

registry.category("actions").add(
    "auto_fulfillment_dashboard_tag",
    AutoFulfillmentDashboard
);