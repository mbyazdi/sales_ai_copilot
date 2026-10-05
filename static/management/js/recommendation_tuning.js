(function () {
    "use strict";

    const section = document.getElementById("recommendationTuningSection");
    if (!section) return;
    let loadRevision = 0;

    function metricLabel(metric) {
        const labels = {
            min_recommendation_score: "حداقل امتیاز پیشنهاد", max_recommendations: "حداکثر تعداد پیشنهاد",
            promotion_score: "امتیاز ترویج فروش", similar_product_score: "امتیاز محصول مشابه",
            association_max_score: "سقف امتیاز فروش مکمل", association_lift_max_score: "اثر هم‌خریدی",
            repurchase_no_cycle_score: "خرید مجدد بدون چرخه", repurchase_overdue_30_score: "خرید مجدد با تأخیر تا ۳۰ روز",
            repurchase_overdue_90_score: "خرید مجدد با تأخیر تا ۹۰ روز", repurchase_overdue_high_score: "خرید مجدد با تأخیر بیشتر",
            durable_previous_purchase_score: "خرید قبلی کالای بادوام", upsell_10_percent_score: "فروش ارتقایی تا ۱۰ درصد",
            upsell_25_percent_score: "فروش ارتقایی تا ۲۵ درصد", upsell_50_percent_score: "فروش ارتقایی تا ۵۰ درصد",
            upsell_high_score: "فروش ارتقایی بیشتر", grade_a_score: "رتبه مشتری A", grade_b_score: "رتبه مشتری B", grade_c_score: "رتبه مشتری C"
        };
        const category = /^category_rank_(\d+)_score$/.exec(metric || "");
        const association = /^association_evidence_(\d+)_score$/.exec(metric || "");
        return labels[metric] || (category ? "امتیاز دسته با رتبه " + number(category[1]) :
            association ? "امتیاز شواهد هم‌خریدی " + number(association[1]) : "پارامتر موتور");
    }

    function failureMessage(data, fallback) {
        const messages = {
            "Tuning suggestion must be approved before apply.": "پیشنهاد باید پیش از اعمال تأیید شود.",
            "Applied tuning suggestion cannot be changed.": "وضعیت پیشنهاد اعمال‌شده قابل تغییر نیست.",
            "Active RecommendationConfig not found.": "پیکربندی فعال در دسترس نیست.",
            "RecommendationConfig metric not found.": "پارامتر در پیکربندی فعال وجود ندارد.",
            "Suggested tuning value is required.": "مقدار پیشنهادی ثبت نشده است.",
            "Suggested tuning value is outside the allowed range.": "مقدار پیشنهادی خارج از محدوده مجاز است.",
            "Suggested tuning change exceeds the maximum allowed delta.": "اندازه تغییر از سقف مجاز بیشتر است.",
            "Tuning suggestion is stale because the active configuration value has changed.": "مقدار پیکربندی تغییر کرده و پیشنهاد تنظیم قدیمی شده است.",
            "Only applied tuning suggestions can be rolled back.": "فقط پیشنهاد اعمال‌شده قابل بازگردانی است.",
            "Previous applied value is not available for rollback.": "مقدار پیش از اعمال برای بازگردانی موجود نیست."
        };
        return messages[data.detail] || fallback;
    }

    const tableWrap =
        document.getElementById(
            "tuningTableWrap"
        );

    const tableBody =
        document.getElementById(
            "tuningTableBody"
        );

    const loading =
        document.getElementById(
            "tuningLoading"
        );

    const errorBox =
        document.getElementById(
            "tuningError"
        );

    const emptyBox =
        document.getElementById(
            "tuningEmpty"
        );

    const refreshButton =
        document.getElementById(
            "refreshRecommendationTuning"
        );

    const statusFilter =
        document.getElementById(
            "tuningStatusFilter"
        );

    const typeFilter =
        document.getElementById(
            "tuningTypeFilter"
        );

    const metricSearch =
        document.getElementById(
            "tuningMetricSearch"
        );

    const clearFiltersButton =
        document.getElementById(
            "clearTuningFilters"
        );

    const typeLabels = {
        REPEAT_PURCHASE: "خرید مجدد",
        CROSS_SELL: "فروش مکمل",
        CATEGORY: "پیشنهاد دسته",
        SIMILAR_PRODUCT: "محصول مشابه",
        UP_SELL: "فروش ارتقایی"
    };


    const statusLabels = {
        PENDING: "در انتظار بررسی",
        APPROVED: "تأیید شده",
        REJECTED: "رد شده",
        APPLIED: "اعمال شده",
        ROLLED_BACK: "بازگردانی شده"
    };


    const signalLabels = {
        POSITIVE: "مثبت",
        PROMISING: "امیدبخش",
        WEAK: "ضعیف",
        NEUTRAL: "خنثی",
        INSUFFICIENT_DATA: "داده ناکافی"
    };


    const qualityLabels = {
        SUFFICIENT_DATA: "داده کافی",
        LIMITED_DATA: "داده محدود",
        INSUFFICIENT_DATA: "داده ناکافی"
    };


    function escapeHtml(value) {

        return String(
            value ?? ""
        ).replace(
            /[&<>'"]/g,
            function (character) {

                return {
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    "'": "&#39;",
                    '"': "&quot;"
                }[character];
            }
        );
    }


    function number(value) {

        if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";

        return new Intl.NumberFormat(
            "fa-IR",
            {
                maximumFractionDigits: 2
            }
        ).format(
            Number(value || 0)
        );
    }

    function dateTime(value) {
        if (!value) {
            return "—";
        }

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return "—";
        }

        return new Intl.DateTimeFormat(
            "fa-IR",
            {
                dateStyle: "short",
                timeStyle: "short"
            }
        ).format(date);
    }

    function getCsrfToken() {

        const name = "csrftoken";

        const cookies =
            document.cookie
                .split(";")
                .map(
                    cookie =>
                        cookie.trim()
                );

        for (const cookie of cookies) {

            if (
                cookie.startsWith(
                    name + "="
                )
            ) {

                return decodeURIComponent(
                    cookie.substring(
                        name.length + 1
                    )
                );
            }
        }

        return "";
    }


    function setState(
        state,
        message = ""
    ) {

        document.getElementById("tuningRegion").setAttribute("aria-busy", String(state === "loading"));

        if (loading) {

            loading.style.display =
                state === "loading"
                    ? "block"
                    : "none";
        }


        if (tableWrap) {

            tableWrap.style.display =
                state === "ready"
                    ? "block"
                    : "none";
        }


        if (emptyBox) {

            emptyBox.style.display =
                state === "empty"
                    ? "block"
                    : "none";
        }


        if (errorBox) {

            errorBox.style.display =
                state === "error"
                    ? "block"
                    : "none";

            errorBox.textContent =
                message;
        }
    }


    async function updateStatus(
        suggestionId,
        newStatus
    ) {

        const response =
            await fetch(
                `/api/recommendations/v1/tuning-suggestions/${encodeURIComponent(
                    suggestionId
                )}/status/`,
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "Accept":
                            "application/json",

                        "X-CSRFToken":
                            getCsrfToken()
                    },

                    credentials:
                        "same-origin",

                    body:
                        JSON.stringify({
                            status:
                                newStatus
                        })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                failureMessage(data, "تغییر وضعیت پیشنهاد تنظیم ناموفق بود. دسترسی و اتصال را بررسی کنید.")
            );
        }


        return data;
    }


    async function applySuggestion(
        suggestionId
    ) {

        const response =
            await fetch(
                `/api/recommendations/v1/tuning-suggestions/${encodeURIComponent(
                    suggestionId
                )}/apply/`,
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "Accept":
                            "application/json",

                        "X-CSRFToken":
                            getCsrfToken()
                    },

                    credentials:
                        "same-origin",

                    body:
                        JSON.stringify({})
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                failureMessage(data, "اعمال پیشنهاد تنظیم ناموفق بود. دسترسی و اتصال را بررسی کنید.")
            );
        }


        return data;
    }

    async function rollbackSuggestion(
        suggestionId
    ) {

        const response =
            await fetch(
                `/api/recommendations/v1/tuning-suggestions/${encodeURIComponent(
                    suggestionId
                )}/rollback/`,
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "Accept":
                            "application/json",

                        "X-CSRFToken":
                            getCsrfToken()
                    },

                    credentials:
                        "same-origin",

                    body:
                        JSON.stringify({})
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                failureMessage(data, "بازگردانی پیشنهاد تنظیم ناموفق بود. دسترسی و اتصال را بررسی کنید.")
            );
        }


        return data;
    }

    function buildActions(
        item
    ) {

        if (item.status === "PENDING") {

            return `
                <div class="tuning-actions">

                    <button
                        type="button"
                        class="tuning-action-btn tuning-approve-btn"
                        data-tuning-action="approve"
                        data-suggestion-id="${item.id}"
                    >
                        تأیید
                    </button>

                    <button
                        type="button"
                        class="tuning-action-btn tuning-reject-btn"
                        data-tuning-action="reject"
                        data-suggestion-id="${item.id}"
                    >
                        رد
                    </button>

                </div>
            `;
        }


        if (item.status === "APPROVED") {
            if (item.status === "APPLIED") {
                return `
                    <div class="tuning-actions">
                        <button
                            type="button"
                            data-tuning-action="rollback"
                            data-suggestion-id="${item.id}"
                        >
                            بازگردانی
                        </button>
                    </div>
                `;
            }
            return `
                <div class="tuning-actions">

                    <button
                        type="button"
                        class="tuning-action-btn tuning-apply-btn"
                        data-tuning-action="apply"
                        data-suggestion-id="${item.id}"
                    >
                        اعمال
                    </button>

                </div>
            `;
        }

        if (item.status === "APPLIED") {

            return `
                <div class="tuning-actions">

                    <button
                        type="button"
                        class="tuning-action-btn tuning-rollback-btn"
                        data-tuning-action="rollback"
                        data-suggestion-id="${item.id}"
                    >
                        بازگردانی
                    </button>

                </div>
            `;
        }

        return `
            <span class="tuning-action-disabled">
                —
            </span>
        `;
    }

    function filterItems(
        items
    ) {

        const selectedStatus =
            statusFilter
                ? statusFilter.value
                : "";

        const selectedType =
            typeFilter
                ? typeFilter.value
                : "";

        const metricQuery =
            metricSearch
                ? metricSearch.value
                    .trim()
                    .toLowerCase()
                : "";

        return items.filter(
            function (item) {

                if (
                    selectedStatus
                    &&
                    item.status !== selectedStatus
                ) {
                    return false;
                }

                if (
                    selectedType
                    &&
                    item.recommendation_type
                    !== selectedType
                ) {
                    return false;
                }

                if (
                    metricQuery
                    &&
                    !String(
                        item.metric || ""
                    )
                        .toLowerCase()
                        .includes(
                            metricQuery
                        )
                ) {
                    return false;
                }

                return true;
            }
        );
    }

    function renderTable(
        items
    ) {

        if (!tableBody) {
            return;
        }

        const filteredItems =
            filterItems(
                Array.isArray(items)
                    ? items
                    : []
            );
        tableBody.innerHTML =
            "";


        if (!filteredItems.length) {

            setState(
                "empty"
            );

            return;
        }


        filteredItems.forEach(
            function (item) {

                const snapshot =
                    item.performance_snapshot
                    || {};


                const row =
                    document.createElement(
                        "tr"
                    );


                row.innerHTML = `
                    <td class="performance-type">
                        ${escapeHtml(
                            typeLabels[
                                item.recommendation_type
                            ]
                            ||
                            item.recommendation_type
                            ||
                            "عمومی"
                        )}
                    </td>

                    <td>
                        ${escapeHtml(metricLabel(item.metric))}
                        <details><summary>شناسه فنی و دلیل</summary><bdi dir="ltr">${escapeHtml(item.metric || "—")}</bdi><p>${escapeHtml(item.reason || "دلیل ثبت نشده است.")}</p></details>
                    </td>

                    <td>
                        ${number(
                            item.current_value
                        )}
                    </td>

                    <td>
                        ${number(
                            item.suggested_value
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            statusLabels[
                                item.status
                            ]
                            ||
                            item.status
                            ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            signalLabels[
                                snapshot.learning_signal
                            ]
                            ||
                            snapshot.learning_signal
                            ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            qualityLabels[
                                snapshot.data_quality
                            ]
                            ||
                            snapshot.data_quality
                            ||
                            "—"
                        )}
                    </td>
                    <td>
                        ${number(
                            item.applied_previous_value
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            dateTime(
                                item.reviewed_at
                            )
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            dateTime(
                                item.applied_at
                            )
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            dateTime(
                                item.rolled_back_at
                            )
                        )}
                    </td>
                    <td>
                        ${buildActions(
                            item
                        )}
                    </td>
                `;


                const headings = section.querySelectorAll("thead th");
                row.querySelectorAll("td").forEach((cell, index) => {
                    cell.dataset.label = headings[index].textContent;
                });
                tableBody.appendChild(
                    row
                );
            }
        );


        attachActionEvents();


        setState(
            "ready"
        );
    }


    function setButtonBusy(
        button,
        busy,
        busyText
    ) {

        if (!button) {
            return;
        }


        if (busy) {

            button.dataset.originalText =
                button.textContent;

            button.disabled =
                true;

            button.textContent =
                busyText;

        } else {

            button.disabled =
                false;

            button.textContent =
                button.dataset.originalText
                ||
                button.textContent;
        }
    }


    function attachActionEvents() {

        document
            .querySelectorAll(
                "[data-tuning-action]"
            )
            .forEach(
                function (button) {

                    button.addEventListener(
                        "click",
                        async function () {

                            const action =
                                button.dataset
                                    .tuningAction;

                            const suggestionId =
                                button.dataset
                                    .suggestionId;


                            if (
                                !action
                                ||
                                !suggestionId
                            ) {
                                return;
                            }


                            try {

                                if (
                                    action
                                    === "approve"
                                ) {

                                    setButtonBusy(
                                        button,
                                        true,
                                        "در حال تأیید..."
                                    );

                                    await updateStatus(
                                        suggestionId,
                                        "APPROVED"
                                    );

                                } else if (
                                    action
                                    === "reject"
                                ) {

                                    setButtonBusy(
                                        button,
                                        true,
                                        "در حال رد..."
                                    );

                                    await updateStatus(
                                        suggestionId,
                                        "REJECTED"
                                    );

                                } else if (
                                    action
                                    === "apply"
                                ) {

                                    setButtonBusy(
                                        button,
                                        true,
                                        "در حال اعمال..."
                                    );

                                    await applySuggestion(
                                        suggestionId
                                    );
                                } else if (
                                    action
                                    === "rollback"
                                ) {

                                    setButtonBusy(
                                        button,
                                        true,
                                        "در حال بازگردانی..."
                                    );

                                    await rollbackSuggestion(
                                        suggestionId
                                    );
                                }


                                await loadTuningSuggestions();

                            }

                            catch (error) {

                                setState(
                                    "error",
                                    error instanceof SyntaxError || error instanceof TypeError ?
                                        "عملیات پیشنهاد تنظیم ناموفق بود. دوباره تلاش کنید." : error.message
                                );
                            } finally {
                                setButtonBusy(button, false);
                            }
                        }
                    );
                }
            );
    }


    async function loadTuningSuggestions() {

        const revision = ++loadRevision;

        setState(
            "loading"
        );


        try {

            const response =
                await fetch(
                    `/api/recommendations/v1/tuning-suggestions/?_=${Date.now()}`,
                    {
                        method:
                            "GET",

                        headers: {
                            "Accept":
                                "application/json"
                        },

                        cache:
                            "no-store",

                        credentials:
                            "same-origin"
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    "دریافت پیشنهادهای تنظیم ناموفق بود. دسترسی و اتصال را بررسی کنید."
                );
            }


            if (revision !== loadRevision) return;
            if (!Array.isArray(data.results)) throw new Error("پاسخ پیشنهادهای تنظیم معتبر نیست.");
            renderTable(
                data.results
                || []
            );

        }

        catch (error) {

            if (revision !== loadRevision) return;

            setState(
                "error",
                error instanceof SyntaxError || error instanceof TypeError ?
                    "دریافت پیشنهادهای تنظیم ناموفق بود. به‌روزرسانی را دوباره بزنید." : error.message
            );
        }
    }

    if (statusFilter) {

        statusFilter.addEventListener(
            "change",
            loadTuningSuggestions
        );
    }


    if (typeFilter) {

        typeFilter.addEventListener(
            "change",
            loadTuningSuggestions
        );
    }


    if (metricSearch) {

        metricSearch.addEventListener(
            "input",
            function () {

                loadTuningSuggestions();
            }
        );
    }


    if (clearFiltersButton) {

        clearFiltersButton.addEventListener(
            "click",
            function () {

                if (statusFilter) {
                    statusFilter.value = "";
                }

                if (typeFilter) {
                    typeFilter.value = "";
                }

                if (metricSearch) {
                    metricSearch.value = "";
                }

                loadTuningSuggestions();
            }
        );
    }

    if (refreshButton) {

        refreshButton.addEventListener(
            "click",
            loadTuningSuggestions
        );
    }


    // The secondary admin area loads only when explicitly expanded.
    section.addEventListener("toggle", () => {
        if (section.open) loadTuningSuggestions();
    });
    if (section.open) loadTuningSuggestions();

})();
