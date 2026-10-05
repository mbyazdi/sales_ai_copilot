/* Read-only evidence from existing diagnostics APIs; no scoring or narration. */
(function () {
    "use strict";
    const root = document.getElementById("recommendationDiagnosticsSection");
    if (!root) return;
    const byId = id => document.getElementById(id);
    const formatter = new Intl.NumberFormat("fa-IR", {maximumFractionDigits: 2});
    const number = value => value === null || value === undefined || value === "" ||
        !Number.isFinite(Number(value)) ? "—" : formatter.format(Number(value));
    const percent = value => number(value) === "—" ? "—" : number(value) + "٪";
    const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[character]));
    const types = {REPEAT_PURCHASE: "خرید مجدد", CROSS_SELL: "فروش مکمل", CATEGORY: "پیشنهاد دسته",
        SIMILAR_PRODUCT: "محصول مشابه", UP_SELL: "فروش ارتقایی", UPSELL: "فروش ارتقایی"};
    const evidence = {HIGH: "شواهد قوی", MEDIUM: "شواهد متوسط", LOW: "شواهد محدود"};
    const labels = {
        group_affinity: "تناسب گروه محصول", group_score: "تناسب گروه محصول",
        repurchase: "چرخه خرید مجدد", purchase_score: "چرخه خرید مجدد",
        association: "هم‌خریدی و فروش مکمل", association_score: "هم‌خریدی و فروش مکمل",
        upsell: "فروش ارتقایی", upsell_score: "فروش ارتقایی",
        customer_grade: "رتبه مشتری", grade_score: "رتبه مشتری",
        promotion: "ترویج فروش", promotion_score: "ترویج فروش",
        similar_product: "شباهت محصول", similar_score: "شباهت محصول",
        historical_feedback: "بازخورد تاریخی", feedback_score: "بازخورد تاریخی",
        rule_score: "امتیاز قواعد", final_score: "امتیاز نهایی"
    };
    const regions = {
        summary: {region: "diagnosticsSummaryRegion", loading: "diagnosticsSummaryLoading",
            error: "diagnosticsSummaryError", empty: "diagnosticsSummaryEmpty", ready: "diagnosticsSummary"},
        list: {region: "diagnosticsRegion", loading: "diagnosticsLoading",
            error: "diagnosticsError", empty: "diagnosticsEmpty", ready: "diagnosticsTableWrap"}
    };
    const revisions = {summary: 0, list: 0};
    function state(name, status, message = "") {
        const ids = regions[name];
        byId(ids.region).setAttribute("aria-busy", String(status === "loading"));
        ["loading", "error", "empty", "ready"].forEach(key => { byId(ids[key]).hidden = key !== status; });
        byId(ids.error).textContent = message;
    }
    async function read(url) {
        const response = await fetch(url, {method: "GET", headers: {Accept: "application/json"},
            credentials: "same-origin", cache: "no-store"});
        if (!response.ok) {
            throw new Error(response.status === 403 || response.status === 401 ?
                "دسترسی مجاز نیست یا نشست شما پایان یافته است. دوباره وارد شوید." :
                response.status === 404 ? "پیشنهاد فعال در دسترس نیست. فهرست را به‌روزرسانی کنید." :
                "دریافت شواهد ناموفق بود. دوباره تلاش کنید.");
        }
        return response.json();
    }
    function facts(items) {
        return '<dl class="rw-facts">' + items.map(([label, value]) =>
            '<div><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + '</dd></div>'
        ).join("") + "</dl>";
    }
    function list(items, empty) {
        return items.length ? '<ul class="rw-detail-list">' + items.map(([label, value]) =>
            "<li><span>" + escapeHtml(label) + "</span><strong>" + escapeHtml(value) + "</strong></li>"
        ).join("") + "</ul>" : '<p class="ds-caption ds-muted">' + escapeHtml(empty) + "</p>";
    }
    function renderDetail(target, data) {
        const snapshot = data.explanation_snapshot || {};
        const breakdown = data.score_breakdown || {};
        const signals = Array.isArray(snapshot.signals) ? snapshot.signals : [];
        target.replaceChildren();
        const reason = document.createElement("p");
        reason.className = "rw-reason";
        reason.textContent = data.reason || "دلیل متنی برای این پیشنهاد ثبت نشده است.";
        target.appendChild(reason);
        const sections = document.createElement("div");
        sections.innerHTML = facts([
            ["مشتری", data.customer_code || "—"],
            ["محصول", data.product?.name || data.product?.code || "—"],
            ["رتبه ثبت‌شده", number(data.rank)],
            ["امتیاز نهایی ثبت‌شده", number(data.score)],
            ["اطمینان ثبت‌شده", percent(data.confidence_score)],
            ["کیفیت شواهد", evidence[data.evidence_quality] || "ثبت نشده"],
            ["تعداد سیگنال فعال", number(snapshot.active_signal_count)]
        ]) + '<h4>شواهد و اثر آن‌ها</h4>' + list(signals.map(signal => [
            (labels[signal.name] || "شاهد ثبت‌شده") + (signal.active === true ? " · فعال" :
                signal.active === false ? " · غیرفعال" : ""),
            number(signal.score)
        ]), "شاهد تفصیلی برای این پیشنهاد ثبت نشده است.") +
            '<details><summary>ترکیب امتیاز ثبت‌شده</summary>' +
            list(Object.entries(breakdown).map(([key, value]) => [
                labels[key] || "شاخص ثبت‌شده", number(value)
            ]), "ترکیب امتیاز در دسترس نیست.") + "</details>";
        target.appendChild(sections);
        if (!data.reason && !signals.length && !Object.keys(breakdown).length) {
            const empty = document.createElement("p");
            empty.className = "ds-state ds-state--empty";
            empty.textContent = "توضیح و شواهد تفصیلی برای این پیشنهاد ثبت نشده است.";
            target.appendChild(empty);
        }
    }
    function createCard(item) {
        const card = document.createElement("article");
        card.className = "rw-evidence-card";
        const snapshot = item.explanation_snapshot || {};
        // Select an existing contribution for disclosure, never calculate strength.
        const activeSignals = (Array.isArray(snapshot.signals) ? snapshot.signals : []).filter(signal =>
            signal.active === true && signal.score !== null && signal.score !== undefined &&
            signal.score !== "" && Number.isFinite(Number(signal.score)));
        const mainSignal = activeSignals.reduce((current, signal) =>
            !current || Number(signal.score) > Number(current.score) ? signal : current, null);
        card.innerHTML = '<h3>' + escapeHtml(item.product_name || item.product_code || "محصول ثبت‌شده") +
            '</h3><p class="rw-identity">مشتری <bdi>' + escapeHtml(item.customer_code || "—") +
            '</bdi> · محصول <bdi>' + escapeHtml(item.product_code || "—") +
            '</bdi></p><div class="rw-card-status"><span class="ds-badge ds-badge--info">' +
            escapeHtml(types[item.recommendation_type] || "پیشنهاد فروش") +
            '</span><span>اطمینان <strong><bdi>' + escapeHtml(percent(item.confidence_score)) +
            '</bdi></strong></span><span>' + escapeHtml(evidence[item.evidence_quality] || "کیفیت شواهد ثبت نشده") +
            '</span></div><p class="rw-main-signal">' + (mainSignal ?
                '<span class="ds-muted">شاهد برجسته · </span><strong>' + escapeHtml(labels[mainSignal.name] || "شاهد ثبت‌شده") + '</strong>' :
                '<span class="ds-muted">شاهد برجسته در داده موجود نیست.</span>') +
            (snapshot.active_signal_count !== undefined && snapshot.active_signal_count !== null ?
                '<small class="ds-muted"> · ' + escapeHtml(number(snapshot.active_signal_count)) + ' سیگنال فعال ثبت‌شده</small>' : '') + '</p>';
        const details = document.createElement("details");
        details.dataset.recommendationId = String(item.id);
        const summary = document.createElement("summary");
        summary.textContent = "مشاهده دلیل و شواهد";
        const target = document.createElement("div");
        target.setAttribute("aria-live", "polite");
        let busy = false;
        let loaded = false;
        async function load() {
            if (busy || loaded) return;
            busy = true;
            target.setAttribute("aria-busy", "true");
            target.innerHTML = '<p class="ds-state ds-state--loading" role="status">در حال دریافت دلیل و شواهد…</p>';
            try {
                const data = await read("/api/recommendations/v1/diagnostics/" +
                    encodeURIComponent(item.id) + "/");
                if (data.id === undefined) throw new Error("پاسخ جزئیات معتبر نیست.");
                renderDetail(target, data);
                loaded = true;
            } catch (error) {
                target.replaceChildren();
                const message = document.createElement("p");
                message.className = "ds-state ds-state--error";
                message.setAttribute("role", "alert");
                message.textContent = error instanceof SyntaxError || error instanceof TypeError ?
                    "دریافت جزئیات ناموفق بود. دوباره تلاش کنید." : error.message;
                const retry = document.createElement("button");
                retry.type = "button";
                retry.className = "ds-button ds-button--secondary";
                retry.textContent = "تلاش دوباره";
                retry.addEventListener("click", load);
                target.append(message, retry);
            } finally {
                busy = false;
                target.setAttribute("aria-busy", "false");
            }
        }
        details.addEventListener("toggle", () => { if (details.open) load(); });
        details.append(summary, target);
        card.appendChild(details);
        return card;
    }
    function renderEvidenceOverview(data) {
        // Describe provided classifications/counts; do not assign an overall grade.
        const classes = [
            {key: "high", label: "قوی", count: data.evidence?.high},
            {key: "medium", label: "متوسط", count: data.evidence?.medium},
            {key: "low", label: "محدود", count: data.evidence?.low}
        ];
        const classified = classes.filter(item => Number.isInteger(item.count) && item.count > 0);
        const highest = classified.length ? Math.max(...classified.map(item => item.count)) : null;
        const leaders = classified.filter(item => item.count === highest);
        let description = "برای پیشنهادهای فعال، طبقه‌بندی شواهد در داده موجود نیست.";
        if (leaders.length === 1) {
            description = "بیشترین تعداد پیشنهادهای دارای طبقه‌بندی، با شواهد " + leaders[0].label +
                " ثبت شده‌اند (" + number(leaders[0].count) + " پیشنهاد).";
        } else if (leaders.length > 1) {
            description = "بیشترین تعداد پیشنهادهای دارای طبقه‌بندی، به‌طور برابر در سطح " +
                leaders.map(item => item.label).join(" و ") + " ثبت شده‌اند.";
        }
        const distribution = classified.length ?
            '<div class="rw-evidence-distribution"><div class="rw-evidence-bar" aria-hidden="true">' +
            classes.map(item => '<span class="rw-evidence-segment rw-evidence-segment--' + item.key +
                '" style="flex-grow:' + (Number.isInteger(item.count) && item.count > 0 ? item.count : 0) + '"></span>').join("") +
            '</div><ul class="rw-outcome-legend" role="list" aria-label="طبقه‌بندی شواهد ثبت‌شده">' +
            classes.map(item => '<li>شواهد ' + escapeHtml(item.label) + ' <strong>' + escapeHtml(number(item.count)) + '</strong></li>').join("") +
            '</ul></div>' : '';
        const flags = [["اطمینان پایین", number(data.quality_flags?.low_confidence)],
            ["بازخورد منفی", number(data.quality_flags?.negative_feedback)],
            ["حداکثر یک سیگنال ثبت‌شده", number(data.quality_flags?.single_signal)]];
        byId("diagnosticsSummary").innerHTML =
            '<div class="rw-evidence-overview"><div><h3>تصویر شواهد پیشنهادهای فعال</h3><p class="rw-evidence-narrative">' +
            escapeHtml(description) + '</p><p class="ds-caption ds-muted">این توزیع، طبقه‌بندی‌های ثبت‌شده را نشان می‌دهد و تضمین خرید نیست.</p></div>' +
            '<div class="rw-evidence-totals"><span>پیشنهاد فعال <strong>' + escapeHtml(number(data.total_recommendations)) +
            '</strong></span><span>میانگین اطمینان ثبت‌شده <strong><bdi>' + escapeHtml(percent(data.average_confidence)) +
            '</bdi></strong></span></div></div>' + distribution +
            '<details class="rw-quality-flags"><summary>نشانه‌های نیازمند بررسی</summary>' + facts(flags) + '</details>';
    }
    async function loadSummary() {
        const revision = ++revisions.summary;
        state("summary", "loading");
        try {
            const data = await read("/api/recommendations/v1/diagnostics/summary/");
            if (revision !== revisions.summary) return;
            if (typeof data.total_recommendations !== "number") throw new Error("پاسخ کیفیت شواهد معتبر نیست.");
            if (!data.total_recommendations) { state("summary", "empty"); return; }
            renderEvidenceOverview(data);
            state("summary", "ready");
        } catch (error) {
            if (revision === revisions.summary) state("summary", "error",
                error instanceof SyntaxError || error instanceof TypeError ?
                    "دریافت کیفیت شواهد ناموفق بود. به‌روزرسانی را دوباره بزنید." : error.message);
        }
    }
    async function loadList() {
        const revision = ++revisions.list;
        state("list", "loading");
        try {
            const data = await read("/api/recommendations/v1/diagnostics/");
            if (revision !== revisions.list) return;
            if (!Array.isArray(data.results)) throw new Error("پاسخ فهرست پیشنهادها معتبر نیست.");
            const cards = data.results.map(createCard);
            const container = byId("diagnosticsTableWrap");
            // Disclosure limits visual density only; preserve the API's order.
            container.replaceChildren(...cards.slice(0, 6));
            if (cards.length > 6) {
                const more = document.createElement("details");
                more.className = "rw-more-evidence";
                const heading = document.createElement("summary");
                heading.textContent = "سایر پیشنهادهای فعال (" + number(cards.length - 6) + ")";
                const remaining = document.createElement("div");
                remaining.className = "rw-evidence-grid";
                remaining.append(...cards.slice(6));
                more.append(heading, remaining);
                container.appendChild(more);
            }
            state("list", data.results.length ? "ready" : "empty");
        } catch (error) {
            if (revision === revisions.list) state("list", "error",
                error instanceof SyntaxError || error instanceof TypeError ?
                    "دریافت پیشنهادها ناموفق بود. به‌روزرسانی را دوباره بزنید." : error.message);
        }
    }
    function refresh() { loadSummary(); loadList(); }
    byId("refreshRecommendationDiagnostics").addEventListener("click", refresh);
    refresh();
}());
