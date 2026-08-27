(function () {

    "use strict";


    /* =========================================================
       CONFIG
    ========================================================= */

    const config =
        window.managementDashboardConfig
        || {};

    const apiUrl =
        config.apiUrl
        || "/api/management/v1/dashboard/";


    /* =========================================================
       DOM
    ========================================================= */

    const loadingBox =
        document.getElementById(
            "dashboardLoading"
        );

    const errorBox =
        document.getElementById(
            "dashboardError"
        );

    const qualityValue =
        document.getElementById(
            "dashboardQualityValue"
        );

    const kpiGrid =
        document.getElementById(
            "dashboardKpiGrid"
        );

    const trendPeriodSelector =
        document.getElementById(
            "trendPeriodSelector"
        );

    const conversionTrend =
        document.getElementById(
            "conversionTrend"
        );

    const revenueTrend =
        document.getElementById(
            "revenueTrend"
        );

    const performanceTabs =
        document.getElementById(
            "performanceTabs"
        );

    const performanceContent =
        document.getElementById(
            "performanceContent"
        );

    const teamSummaryGrid =
        document.getElementById(
            "teamSummaryGrid"
        );

    const salesTeamTableBody =
        document.getElementById(
            "salesTeamTableBody"
        );

    const executiveIntelligenceSection =
        document.getElementById(
            "executiveIntelligenceSection"
        );

    const executiveNarrative =
        document.getElementById(
            "executiveNarrative"
        );

    const executiveDataQuality =
        document.getElementById(
            "executiveDataQuality"
        );

    const executiveAiStatus =
        document.getElementById(
            "executiveAiStatus"
        );

    const executiveAiStatusText =
        document.getElementById(
            "executiveAiStatusText"
        );

    const executiveAiStatusDot =
        document.getElementById(
            "executiveAiStatusDot"
        );

    const executiveModel =
        document.getElementById(
            "executiveModel"
        );

    /* =========================================================
       STATE
    ========================================================= */

    let dashboardData = null;

    let activeTrendPeriod =
        "day";

    let activePerformanceSection =
        null;


    /* =========================================================
       LABELS
    ========================================================= */

    const kpiLabels = {
        conversion_rate:
            "نرخ تبدیل",

        total_revenue:
            "فروش حاصل",

        engagement_rate:
            "نرخ تعامل",

        presented:
            "پیشنهاد ارائه‌شده",

        purchased:
            "خرید موفق",

        average_revenue:
            "میانگین فروش",

        interest_rate:
            "نرخ علاقه‌مندی",

        data_quality:
            "کیفیت داده",
    };


    const sectionLabels = {
        recommendation_type:
            "نوع پیشنهاد",

        product:
            "محصول",

        category:
            "دسته‌بندی",

        brand:
            "برند",
    };


    const dataQualityLabels = {
        SUFFICIENT_DATA:
            "داده کافی",

        LIMITED_DATA:
            "داده محدود",

        INSUFFICIENT_DATA:
            "داده ناکافی",

        NO_PRESENTED_DATA:
            "بدون داده ارائه‌شده",
    };


    /* =========================================================
       FORMATTERS
    ========================================================= */

    function formatNumber(value) {

        return new Intl.NumberFormat(
            "fa-IR"
        ).format(
            Number(
                value
                || 0
            )
        );

    }


    function formatMoney(value) {

        return new Intl.NumberFormat(
            "fa-IR",
            {
                maximumFractionDigits: 2,
            }
        ).format(
            Number(
                value
                || 0
            )
        );

    }


    function formatPercent(value) {

        return (
            Number(
                value
                || 0
            ).toLocaleString(
                "fa-IR",
                {
                    maximumFractionDigits: 2,
                }
            )
            + "%"
        );

    }


    function formatKpiValue(item) {

        if (!item) {
            return "—";
        }

        if (
            item.format
            === "PERCENT"
        ) {

            return formatPercent(
                item.value
            );

        }

        if (
            item.format
            === "INTEGER"
        ) {

            return formatNumber(
                item.value
            );

        }

        if (
            item.format
            === "NUMBER"
        ) {

            return formatMoney(
                item.value
            );

        }

        if (
            item.format
            === "TEXT"
        ) {

            return (
                dataQualityLabels[
                    item.value
                ]
                || item.value
                || "—"
            );

        }

        return (
            item.value
            ?? "—"
        );

    }


    function normalizeClass(value) {

        return String(
            value
            || ""
        )
            .toLowerCase()
            .replaceAll(
                "_",
                "-"
            );

    }


    function formatDate(value) {

        if (!value) {
            return "—";
        }

        try {

            return new Date(
                value
            ).toLocaleDateString(
                "fa-IR"
            );

        } catch (error) {

            return value;

        }

    }


    /* =========================================================
       KPI CARDS
    ========================================================= */

    function renderKpis(kpis) {

        if (!kpiGrid) {
            return;
        }

        kpiGrid.innerHTML = "";

        if (
            !Array.isArray(kpis)
            || !kpis.length
        ) {

            kpiGrid.innerHTML = `
                <div class="dashboard-empty">
                    داده‌ای برای نمایش شاخص‌های مدیریتی وجود ندارد.
                </div>
            `;

            return;
        }

        kpis.forEach(
            function (item) {

                const card =
                    document.createElement(
                        "article"
                    );

                card.className =
                    "kpi-card";

                card.dataset.key =
                    item.key
                    || "";

                const label =
                    kpiLabels[
                        item.key
                    ]
                    || item.label
                    || item.key
                    || "—";

                card.innerHTML = `
                    <div class="kpi-label">
                        ${label}
                    </div>

                    <div class="kpi-value">
                        ${formatKpiValue(item)}
                    </div>

                    <div class="kpi-meta">
                        ${item.unit || ""}
                    </div>
                `;

                kpiGrid.appendChild(
                    card
                );

            }
        );

    }


    /* =========================================================
       QUALITY
    ========================================================= */

    function renderQuality(value) {

        if (!qualityValue) {
            return;
        }

        qualityValue.textContent =
            dataQualityLabels[
                value
            ]
            || value
            || "—";

    }

    function renderExecutiveIntelligence() {

        const executive =
            dashboardData
                ?.executive_intelligence
            || {};

        if (
            !executiveIntelligenceSection
            || !executive.ready
        ) {

            if (executiveIntelligenceSection) {
                executiveIntelligenceSection.hidden =
                    true;
            }

            return;
        }

        executiveIntelligenceSection.hidden =
            false;


        /* -----------------------------------------
           AUTHORITATIVE NARRATIVE
        ----------------------------------------- */

        if (executiveNarrative) {

            executiveNarrative.textContent =
                executive.narrative
                || "—";

        }


        /* -----------------------------------------
           DATA QUALITY
        ----------------------------------------- */

        const quality =
            executive
                ?.data_quality
                ?.status
            || "";

        if (executiveDataQuality) {

            executiveDataQuality.textContent =
                dataQualityLabels[
                    quality
                ]
                || quality
                || "—";

            executiveDataQuality.className =
                "data-quality-badge";

            if (quality) {

                executiveDataQuality.classList.add(
                    normalizeClass(
                        quality
                    )
                );

            }

        }


        /* -----------------------------------------
           OPTIONAL AI STATUS
        ----------------------------------------- */

        const llmStatus =
            executive.llm_status
            || {};

        const llmAvailable =
            llmStatus.available
            === true;

        if (executiveAiStatusText) {

            executiveAiStatusText.textContent =
                llmAvailable
                ? "AI Online"
                : "Backend Narrative";

        }

        if (executiveAiStatus) {

            executiveAiStatus.classList.toggle(
                "available",
                llmAvailable
            );

            executiveAiStatus.classList.toggle(
                "unavailable",
                !llmAvailable
            );

        }

        if (executiveAiStatusDot) {

            executiveAiStatusDot.classList.toggle(
                "available",
                llmAvailable
            );

            executiveAiStatusDot.classList.toggle(
                "unavailable",
                !llmAvailable
            );

        }


        /* -----------------------------------------
           MODEL LABEL
        ----------------------------------------- */

        if (executiveModel) {

            if (
                llmAvailable
                && llmStatus.model
            ) {

                executiveModel.textContent =
                    `AI Draft: ${llmStatus.model}`;

            } else {

                executiveModel.textContent =
                    "Deterministic Backend";

            }

        }

    }

    /* =========================================================
       TRENDS
    ========================================================= */

    function getActiveTrendItems() {

        const trends =
            dashboardData
                ?.kpi_trend
                ?.trends
            || {};

        return (
            trends[
                activeTrendPeriod
            ]
            || []
        );

    }


    function buildPeriodLabel(item) {

        const start =
            formatDate(
                item.period_start
            );

        const end =
            formatDate(
                item.period_end
            );

        if (
            item.period_end
            && item.period_start
            !== item.period_end
        ) {

            return (
                `${start} تا ${end}`
            );

        }

        return start;

    }

    /* =========================================================
       SVG TREND CHART
    ========================================================= */

    function formatTrendMetric(
        metricKey,
        value,
    ) {

        if (
            metricKey
            === "conversion_rate"
        ) {

            return formatPercent(
                value
            );

        }

        if (
            metricKey
            === "total_revenue"
        ) {

            return formatMoney(
                value
            );

        }

        return formatNumber(
            value
        );

    }


    function createSvgElement(
        name,
        attributes = {},
    ) {

        const element =
            document.createElementNS(
                "http://www.w3.org/2000/svg",
                name,
            );

        Object.entries(
            attributes
        ).forEach(
            function (
                [
                    key,
                    value,
                ]
            ) {

                element.setAttribute(
                    key,
                    value,
                );

            }
        );

        return element;

    }


    function renderTrendChart(
        container,
        items,
        metricKey,
    ) {

        if (!container) {
            return;
        }

        container.innerHTML = "";

        if (
            !Array.isArray(items)
            || !items.length
        ) {

            container.innerHTML = `
                <div class="dashboard-empty">
                    داده‌ای برای این بازه زمانی وجود ندارد.
                </div>
            `;

            return;
        }


        /* -----------------------------------------
           CHART SHELL
        ----------------------------------------- */

        const chart =
            document.createElement(
                "div"
            );

        chart.className =
            "management-chart";


        const chartBody =
            document.createElement(
                "div"
            );

        chartBody.className =
            "management-chart-body";


        const svg =
            createSvgElement(
                "svg",
                {
                    viewBox:
                        "0 0 760 260",

                    preserveAspectRatio:
                        "none",

                    role:
                        "img",
                }
            );

        svg.classList.add(
            "management-chart-svg"
        );


        /* -----------------------------------------
           SOURCE VALUES
        ----------------------------------------- */

        const values =
            items.map(
                function (item) {

                    return Number(
                        item[
                            metricKey
                        ]
                        || 0
                    );

                }
            );

        const maxValue =
            Math.max(
                ...values,
                0,
            );

        const minValue =
            Math.min(
                ...values,
                0,
            );

        const range =
            (
                maxValue
                - minValue
            )
            || 1;


        /*
         * These constants are only SVG presentation
         * dimensions. They are not business metrics.
         */

        const width =
            760;

        const height =
            260;

        const paddingLeft =
            46;

        const paddingRight =
            20;

        const paddingTop =
            24;

        const paddingBottom =
            46;

        const plotWidth =
            width
            - paddingLeft
            - paddingRight;

        const plotHeight =
            height
            - paddingTop
            - paddingBottom;


        /* -----------------------------------------
           GRID
        ----------------------------------------- */

        const gridGroup =
            createSvgElement(
                "g"
            );

        gridGroup.classList.add(
            "chart-grid"
        );

        const gridLines =
            4;

        for (
            let index = 0;
            index <= gridLines;
            index += 1
        ) {

            const y =
                paddingTop
                + (
                    plotHeight
                    * index
                    / gridLines
                );

            const line =
                createSvgElement(
                    "line",
                    {
                        x1:
                            paddingLeft,

                        y1:
                            y,

                        x2:
                            width
                            - paddingRight,

                        y2:
                            y,
                    }
                );

            gridGroup.appendChild(
                line
            );

        }

        svg.appendChild(
            gridGroup
        );


        /* -----------------------------------------
           POINT COORDINATES
        ----------------------------------------- */

        const points =
            items.map(
                function (
                    item,
                    index,
                ) {

                    let x;

                    if (
                        items.length
                        === 1
                    ) {

                        x =
                            paddingLeft
                            + (
                                plotWidth
                                / 2
                            );

                    } else {

                        x =
                            paddingLeft
                            + (
                                plotWidth
                                * index
                                / (
                                    items.length
                                    - 1
                                )
                            );

                    }


                    const value =
                        Number(
                            item[
                                metricKey
                            ]
                            || 0
                        );

                    const normalized =
                        (
                            value
                            - minValue
                        )
                        / range;

                    const y =
                        paddingTop
                        + plotHeight
                        - (
                            normalized
                            * plotHeight
                        );


                    return {
                        x,
                        y,
                        value,
                        item,
                    };

                }
            );


        /* -----------------------------------------
           AREA
        ----------------------------------------- */

        if (
            points.length
            > 1
        ) {

            const areaPath = [
                `M ${points[0].x} ${paddingTop + plotHeight}`,

                ...points.map(
                    function (point) {

                        return (
                            `L ${point.x} ${point.y}`
                        );

                    }
                ),

                `L ${points[
                    points.length - 1
                ].x} ${paddingTop + plotHeight}`,

                "Z",
            ].join(
                " "
            );

            const area =
                createSvgElement(
                    "path",
                    {
                        d:
                            areaPath,
                    }
                );

            area.classList.add(
                "chart-area"
            );

            svg.appendChild(
                area
            );

        }


        /* -----------------------------------------
           LINE
        ----------------------------------------- */

        if (
            points.length
            > 1
        ) {

            const linePoints =
                points.map(
                    function (point) {

                        return (
                            `${point.x},${point.y}`
                        );

                    }
                ).join(
                    " "
                );

            const polyline =
                createSvgElement(
                    "polyline",
                    {
                        points:
                            linePoints,

                        fill:
                            "none",
                    }
                );

            polyline.classList.add(
                "chart-line"
            );

            svg.appendChild(
                polyline
            );

        }


        /* -----------------------------------------
           TOOLTIP
        ----------------------------------------- */

        const tooltip =
            document.createElement(
                "div"
            );

        tooltip.className =
            "chart-tooltip";

        tooltip.hidden =
            true;


        /* -----------------------------------------
           POINTS
        ----------------------------------------- */

        points.forEach(
            function (point) {

                const circle =
                    createSvgElement(
                        "circle",
                        {
                            cx:
                                point.x,

                            cy:
                                point.y,

                            r:
                                5,

                            tabindex:
                                0,
                        }
                    );

                circle.classList.add(
                    "chart-point"
                );


                function showTooltip() {

                    tooltip.innerHTML = `
                        <div class="chart-tooltip-period">
                            ${buildPeriodLabel(
                                point.item
                            )}
                        </div>

                        <div class="chart-tooltip-value">
                            ${formatTrendMetric(
                                metricKey,
                                point.value,
                            )}
                        </div>
                    `;

                    tooltip.hidden =
                        false;

                }


                function hideTooltip() {

                    tooltip.hidden =
                        true;

                }


                circle.addEventListener(
                    "mouseenter",
                    showTooltip,
                );

                circle.addEventListener(
                    "mouseleave",
                    hideTooltip,
                );

                circle.addEventListener(
                    "focus",
                    showTooltip,
                );

                circle.addEventListener(
                    "blur",
                    hideTooltip,
                );


                svg.appendChild(
                    circle
                );

            }
        );


        /* -----------------------------------------
           X LABELS
        ----------------------------------------- */

        const labels =
            document.createElement(
                "div"
            );

        labels.className =
            "chart-x-labels";

        items.forEach(
            function (item) {

                const label =
                    document.createElement(
                        "span"
                    );

                label.textContent =
                    buildPeriodLabel(
                        item
                    );

                labels.appendChild(
                    label
                );

            }
        );


        chartBody.appendChild(
            svg
        );

        chartBody.appendChild(
            tooltip
        );

        chart.appendChild(
            chartBody
        );

        chart.appendChild(
            labels
        );

        container.appendChild(
            chart
        );

    }


    function renderTrends() {

        const items =
            getActiveTrendItems();

        renderTrendChart(
            conversionTrend,
            items,
            "conversion_rate",
        );

        renderTrendChart(
            revenueTrend,
            items,
            "total_revenue",
        );

    }

    function bindTrendSelector() {

        if (!trendPeriodSelector) {
            return;
        }

        const buttons =
            trendPeriodSelector
                .querySelectorAll(
                    "[data-period]"
                );

        buttons.forEach(
            function (button) {

                button.addEventListener(
                    "click",
                    function () {

                        activeTrendPeriod =
                            button.dataset.period
                            || "day";

                        buttons.forEach(
                            function (item) {

                                item.classList.remove(
                                    "active"
                                );

                            }
                        );

                        button.classList.add(
                            "active"
                        );

                        renderTrends();

                    }
                );

            }
        );

    }


    /* =========================================================
       PERFORMANCE
    ========================================================= */

    function getPerformanceSections() {

        return (
            dashboardData
                ?.performance
                ?.sections
            || []
        );

    }


    function getEntityLabel(
        section,
        item,
    ) {

        if (
            section.key
            === "recommendation_type"
        ) {

            return (
                item.recommendation_type
                || "—"
            );

        }

        if (
            section.key
            === "product"
        ) {

            return (
                item.product_name
                || item.product_code
                || "—"
            );

        }

        if (
            section.key
            === "category"
        ) {

            return (
                item.category_name
                || item.category_code
                || "—"
            );

        }

        if (
            section.key
            === "brand"
        ) {

            return (
                item.brand_name
                || item.brand_code
                || "—"
            );

        }

        return "—";

    }


    function renderPerformanceTabs(
        sections
    ) {

        if (!performanceTabs) {
            return;
        }

        performanceTabs.innerHTML = "";

        if (
            !Array.isArray(sections)
            || !sections.length
        ) {

            return;

        }

        if (!activePerformanceSection) {

            activePerformanceSection =
                sections[0].key;

        }

        sections.forEach(
            function (section) {

                const button =
                    document.createElement(
                        "button"
                    );

                button.type =
                    "button";

                button.className =
                    "performance-tab";

                if (
                    section.key
                    === activePerformanceSection
                ) {

                    button.classList.add(
                        "active"
                    );

                }

                button.textContent =
                    sectionLabels[
                        section.key
                    ]
                    || section.title
                    || section.key;

                button.addEventListener(
                    "click",
                    function () {

                        activePerformanceSection =
                            section.key;

                        renderPerformance();

                    }
                );

                performanceTabs.appendChild(
                    button
                );

            }
        );

    }


    function renderPerformanceContent(
        section
    ) {

        if (!performanceContent) {
            return;
        }

        performanceContent.innerHTML =
            "";

        if (
            !section
            || !Array.isArray(
                section.items
            )
            || !section.items.length
        ) {

            performanceContent.innerHTML = `
                <div class="dashboard-empty">
                    داده‌ای برای این بخش وجود ندارد.
                </div>
            `;

            return;
        }

        const summary =
            document.createElement(
                "div"
            );

        summary.className =
            "performance-summary";

        summary.innerHTML = `
            <span class="performance-chip">
                تعداد آیتم:
                ${formatNumber(
                    section.item_count
                )}
            </span>
        `;

        performanceContent.appendChild(
            summary
        );

        const rankingValues =
            Object.entries(
                section.ranking
                || {}
            )
            .filter(
                function (
                    [
                        key,
                        value,
                    ]
                ) {

                    return Boolean(
                        value
                    );

                }
            );

        if (
            rankingValues.length
        ) {

            const rankingBox =
                document.createElement(
                    "div"
                );

            rankingBox.className =
                "performance-ranking";

            rankingValues.forEach(
                function (
                    [
                        key,
                        value,
                    ]
                ) {

                    const chip =
                        document.createElement(
                            "span"
                        );

                    chip.className =
                        "ranking-chip";

                    if (
                        key.includes(
                            "conversion"
                        )
                    ) {

                        chip.textContent =
                            `بهترین تبدیل: ${value}`;

                    } else if (
                        key.includes(
                            "revenue"
                        )
                    ) {

                        chip.textContent =
                            `بیشترین فروش: ${value}`;

                    } else if (
                        key.includes(
                            "engagement"
                        )
                    ) {

                        chip.textContent =
                            `بهترین تعامل: ${value}`;

                    } else {

                        chip.textContent =
                            value;

                    }

                    rankingBox.appendChild(
                        chip
                    );

                }
            );

            performanceContent.appendChild(
                rankingBox
            );

        }

        const wrapper =
            document.createElement(
                "div"
            );

        wrapper.className =
            "table-wrapper";

        const table =
            document.createElement(
                "table"
            );

        table.className =
            "performance-table";

        table.innerHTML = `
            <thead>
                <tr>
                    <th>عنوان</th>
                    <th>ارائه</th>
                    <th>خرید</th>
                    <th>تبدیل</th>
                    <th>تعامل</th>
                    <th>فروش</th>
                    <th>کیفیت داده</th>
                </tr>
            </thead>

            <tbody></tbody>
        `;

        const tbody =
            table.querySelector(
                "tbody"
            );

        section.items.forEach(
            function (item) {

                const row =
                    document.createElement(
                        "tr"
                    );

                const quality =
                    item.data_quality
                    || "";

                row.innerHTML = `
                    <td class="performance-entity-cell">
                        ${getEntityLabel(
                            section,
                            item
                        )}
                    </td>

                    <td>
                        ${formatNumber(
                            item.presented
                        )}
                    </td>

                    <td>
                        ${formatNumber(
                            item.purchased
                        )}
                    </td>

                    <td>
                        ${formatPercent(
                            item.conversion_rate
                        )}
                    </td>

                    <td>
                        ${formatPercent(
                            item.engagement_rate
                        )}
                    </td>

                    <td>
                        ${formatMoney(
                            item.total_revenue
                        )}
                    </td>

                    <td>
                        <span
                            class="
                                data-quality-badge
                                ${normalizeClass(
                                    quality
                                )}
                            "
                        >
                            ${
                                dataQualityLabels[
                                    quality
                                ]
                                || quality
                                || "—"
                            }
                        </span>
                    </td>
                `;

                tbody.appendChild(
                    row
                );

            }
        );

        wrapper.appendChild(
            table
        );

        performanceContent.appendChild(
            wrapper
        );

    }


    function renderPerformance() {

        const sections =
            getPerformanceSections();

        renderPerformanceTabs(
            sections
        );

        const activeSection =
            sections.find(
                function (item) {

                    return (
                        item.key
                        === activePerformanceSection
                    );

                }
            )
            || sections[0];

        renderPerformanceContent(
            activeSection
        );

    }


    /* =========================================================
       SALES TEAM
    ========================================================= */

    function renderTeamSummary(
        summary
    ) {

        if (!teamSummaryGrid) {
            return;
        }

        teamSummaryGrid.innerHTML =
            "";

        const items = [
            {
                label:
                    "تعداد فروشندگان",

                value:
                    summary.salesperson_count,
            },

            {
                label:
                    "دارای داده تحلیلی",

                value:
                    summary.active_analytics_rows,
            },

            {
                label:
                    "بهترین نرخ تبدیل",

                value:
                    summary.best_conversion_salesperson_code
                    || "—",
            },

            {
                label:
                    "بیشترین فروش",

                value:
                    summary.best_revenue_salesperson_code
                    || "—",
            },
        ];

        items.forEach(
            function (item) {

                const card =
                    document.createElement(
                        "article"
                    );

                card.className =
                    "team-summary-card";

                card.innerHTML = `
                    <div class="team-summary-label">
                        ${item.label}
                    </div>

                    <div class="team-summary-value">
                        ${item.value ?? "—"}
                    </div>
                `;

                teamSummaryGrid.appendChild(
                    card
                );

            }
        );

    }


    function renderSalesTeam(
        salesTeam
    ) {

        if (!salesTeamTableBody) {
            return;
        }

        const leaderboard =
            salesTeam.leaderboard
            || [];

        renderTeamSummary(
            salesTeam.team_summary
            || {}
        );

        salesTeamTableBody.innerHTML =
            "";

        if (!leaderboard.length) {

            salesTeamTableBody.innerHTML = `
                <tr>
                    <td
                        colspan="7"
                        class="dashboard-empty"
                    >
                        داده‌ای برای تیم فروش وجود ندارد.
                    </td>
                </tr>
            `;

            return;
        }

        leaderboard.forEach(
            function (item) {

                const row =
                    document.createElement(
                        "tr"
                    );

                const quality =
                    item.data_quality
                    || "";

                row.innerHTML = `
                    <td class="salesperson-cell">
                        ${item.full_name || "—"}
                        <br>
                        <small>
                            ${item.employee_code || ""}
                        </small>
                    </td>

                    <td>
                        ${formatNumber(
                            item.presented
                        )}
                    </td>

                    <td>
                        ${formatNumber(
                            item.purchased
                        )}
                    </td>

                    <td>
                        ${formatPercent(
                            item.conversion_rate
                        )}
                    </td>

                    <td>
                        ${formatPercent(
                            item.engagement_rate
                        )}
                    </td>

                    <td>
                        ${formatMoney(
                            item.total_revenue
                        )}
                    </td>

                    <td>
                        <span
                            class="
                                data-quality-badge
                                ${normalizeClass(
                                    quality
                                )}
                            "
                        >
                            ${
                                dataQualityLabels[
                                    quality
                                ]
                                || quality
                                || "—"
                            }
                        </span>
                    </td>
                `;

                salesTeamTableBody.appendChild(
                    row
                );

            }
        );

    }


    /* =========================================================
       MAIN RENDER
    ========================================================= */

    function renderDashboard(
        data
    ) {

        dashboardData =
            data;

        renderQuality(
            data
                ?.kpi_trend
                ?.data_quality
        );

        renderKpis(
            data
                ?.kpi_trend
                ?.kpis
            || []
        );

        renderExecutiveIntelligence();

        renderTrends();

        renderPerformance();

        renderSalesTeam(
            data.sales_team
            || {}
        );

    }


    /* =========================================================
       LOAD
    ========================================================= */

    async function loadDashboard() {

        if (loadingBox) {

            loadingBox.hidden =
                false;

        }

        if (errorBox) {

            errorBox.hidden =
                true;

            errorBox.textContent =
                "";

        }

        try {

            const response =
                await fetch(
                    apiUrl,
                    {
                        method:
                            "GET",

                        headers: {
                            "Accept":
                                "application/json",
                        },

                        credentials:
                            "same-origin",
                    }
                );

            const raw =
                await response.text();

            let data;

            try {

                data =
                    JSON.parse(
                        raw
                    );

            } catch (error) {

                throw new Error(
                    "پاسخ API معتبر نیست."
                );

            }

            if (!response.ok) {

                throw new Error(
                    data.detail
                    || data.error
                    || "دریافت اطلاعات داشبورد ناموفق بود."
                );

            }

            renderDashboard(
                data
            );

        } catch (error) {

            console.error(
                "Management dashboard error:",
                error
            );

            if (errorBox) {

                errorBox.textContent =
                    error.message
                    || "خطا در دریافت اطلاعات داشبورد.";

                errorBox.hidden =
                    false;

            }

        } finally {

            if (loadingBox) {

                loadingBox.hidden =
                    true;

            }

        }

    }


    /* =========================================================
       INIT
    ========================================================= */

    bindTrendSelector();

    loadDashboard();


})();