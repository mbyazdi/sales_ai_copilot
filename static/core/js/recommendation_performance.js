(function () {
    "use strict";

    const customerCode = window.customerCode || "";
    const tableWrap = document.getElementById("performanceTableWrap");
    const tableBody = document.getElementById("performanceTableBody");
    const loading = document.getElementById("performanceLoading");
    const errorBox = document.getElementById("performanceError");
    const emptyBox = document.getElementById("performanceEmpty");
    const refreshButton = document.getElementById("refreshRecommendationPerformance");

    const labels = {
        REPEAT_PURCHASE: "خرید مجدد",
        CROSS_SELL: "فروش مکمل",
        CATEGORY: "پیشنهاد دسته",
        SIMILAR_PRODUCT: "محصول مشابه",
        UP_SELL: "فروش ارتقایی",
        UPSELL: "فروش ارتقایی"
    };

    function number(value) {
        return new Intl.NumberFormat("fa-IR").format(Number(value || 0));
    }

    function money(value) {
        return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(Number(value || 0));
    }

    function percent(value) {
        return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(Number(value || 0))}%`;
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>\'"]/g, function (c) {
            return {"&":"&amp;", "<":"&lt;", ">":"&gt;", "\'":"&#39;", "\"":"&quot;"}[c];
        });
    }

    function setState(state, message = "") {
        if (loading) loading.style.display = state === "loading" ? "block" : "none";
        if (tableWrap) tableWrap.style.display = state === "ready" ? "block" : "none";
        if (emptyBox) emptyBox.style.display = state === "empty" ? "block" : "none";
        if (errorBox) {
            errorBox.style.display = state === "error" ? "block" : "none";
            errorBox.textContent = message;
        }
    }

    function renderSummary(summary) {
        document.getElementById("performancePresented").textContent = number(summary.presented);
        document.getElementById("performancePurchased").textContent = number(summary.purchased);
        document.getElementById("performanceInterested").textContent = number(summary.interested);
        document.getElementById("performanceRevenue").textContent = money(summary.revenue);
        document.getElementById("performanceConversion").textContent = percent(summary.conversion_rate);
        document.getElementById("performanceInterestRate").textContent = percent(summary.interest_rate);
    }

    function renderTable(items) {
        tableBody.innerHTML = "";
        if (!Array.isArray(items) || !items.length) {
            setState("empty");
            return;
        }
        items.forEach(function (item) {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td class="performance-type">${escapeHtml(labels[item.recommendation_type] || item.recommendation_type || "پیشنهاد")}</td>
                <td>${number(item.presented)}</td>
                <td>${number(item.purchased)}</td>
                <td>${number(item.interested)}</td>
                <td>${number(item.rejected)}</td>
                <td>${number(item.follow_up)}</td>
                <td class="performance-revenue">${money(item.revenue)}</td>
                <td class="performance-revenue">${money(item.average_revenue)}</td>
                <td class="performance-rate">${percent(item.conversion_rate)}</td>
                <td class="performance-rate">${percent(item.interest_rate)}</td>
            `;
            tableBody.appendChild(row);
        });
        setState("ready");
    }

    async function loadPerformance() {
        if (!customerCode) {
            setState("error", "کد مشتری برای دریافت عملکرد پیشنهادها پیدا نشد.");
            return;
        }

        setState("loading");
        try {
            const response = await fetch(
                `/api/recommendations/v1/customers/${encodeURIComponent(customerCode)}/performance/?_=${Date.now()}`,
                { method: "GET", headers: { "Accept": "application/json" }, cache: "no-store", credentials: "same-origin" }
            );
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || data.error || `خطا در دریافت عملکرد (${response.status})`);
            renderSummary(data.summary || {});
            renderTable(data.performance || []);
        } catch (error) {
            setState("error", error.message || "خطا در دریافت عملکرد پیشنهادها.");
        }
    }

    if (refreshButton) refreshButton.addEventListener("click", loadPerformance);
    loadPerformance();
})();
