/* Presentation enhancement only: existing backend series remain authoritative. */
(function () {
    "use strict";
    const number = new Intl.NumberFormat("fa-IR", {maximumFractionDigits: 2});
    document.querySelectorAll(".manager-number").forEach(node => {
        const value = Number(node.dataset.value);
        if (Number.isFinite(value)) node.textContent = number.format(value);
    });
    const dataNode = document.getElementById("management-trends");
    const selector = document.getElementById("trend-period");
    if (!dataNode || !selector) return;
    const series = JSON.parse(dataNode.textContent);
    const ns = "http://www.w3.org/2000/svg";
    function svgNode(name, attrs, text) {
        const node = document.createElementNS(ns, name);
        Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
        if (text !== undefined) node.textContent = text;
        return node;
    }
    function dateLabel(value) {
        // Date-only source; no timezone conversion or invented missing periods.
        return String(value || "").replaceAll("-", "/");
    }
    function render(id, points, metric, label, percent) {
        const container = document.getElementById(id);
        container.replaceChildren();
        const usable = points.filter(point => point.presented > 0 && Number.isFinite(Number(point[metric])));
        if (usable.length < 2) {
            const state = document.createElement("p");
            state.className = "ds-state ds-muted";
            state.textContent = usable.length
                ? "فقط یک دوره دارای داده ارائه‌شده است؛ روند قابل مقایسه نیست. مقدار ثبت‌شده: " + number.format(usable[0][metric]) + (percent ? "٪" : "") + " · " + dateLabel(usable[0].period_start)
                : "داده ارائه‌شده‌ای برای نمایش روند موجود نیست.";
            container.append(state);
            return;
        }
        const scroll = document.createElement("div");
        scroll.className = "manager-chart-scroll";
        scroll.tabIndex = 0;
        scroll.setAttribute("role", "region");
        scroll.setAttribute("aria-label", label + "؛ مقادیر دقیق در جدول دوره‌ها");
        const width = Math.max(520, usable.length * 100 + 120);
        const height = 240, top = 30, baseline = 190, left = 100;
        const svg = svgNode("svg", {viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": label, dir: "ltr"});
        svg.style.minWidth = width + "px";
        svg.append(svgNode("title", {}, label + "؛ ستون‌های مستقل، بدون اتصال دوره‌های فاقد داده"));
        const maximum = percent ? 100 : Math.max(...usable.map(point => Number(point[metric])), 0);
        // Scaling changes only bar geometry, never KPI values.
        const scale = maximum || 1;
        [...new Set([0, maximum / 2, maximum])].forEach(value => {
            const y = baseline - value / scale * (baseline - top);
            svg.append(svgNode("line", {x1: left, x2: width - 10, y1: y, y2: y, class: "chart-axis"}));
            svg.append(svgNode("text", {x: left - 8, y: y + 4, "text-anchor": "end"}, number.format(value) + (percent ? "٪" : "")));
        });
        const step = (width - left - 10) / usable.length;
        usable.forEach((point, index) => {
            const x = left + step * index + step / 2;
            const value = Number(point[metric]);
            const y = baseline - value / scale * (baseline - top);
            const bar = svgNode("rect", {x: x - 16, y: Math.min(y, baseline), width: 32, height: Math.abs(baseline - y), class: "chart-bar"});
            bar.append(svgNode("title", {}, dateLabel(point.period_start) + " — " + dateLabel(point.period_end) + ": " + number.format(value) + (percent ? "٪" : "") + "؛ " + number.format(point.presented) + " ارائه‌شده"));
            svg.append(bar);
            svg.append(svgNode("text", {x, y: y - 7, "text-anchor": "middle"}, number.format(value) + (percent ? "٪" : "")));
            svg.append(svgNode("text", {x, y: baseline + 24, "text-anchor": "middle"}, dateLabel(point.period_start)));
        });
        scroll.append(svg);
        container.append(scroll);
    }
    function update() {
        const points = series[selector.value] || [];
        render("conversionTrend", points, "conversion_rate", "روند نرخ تبدیل", true);
        render("revenueTrend", points, "total_revenue", "روند فروش حاصل؛ واحد پول مشخص نشده", false);
    }
    selector.addEventListener("change", update);
    update();
})();
