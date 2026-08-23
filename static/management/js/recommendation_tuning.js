(function () {
    "use strict";

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
                data.detail
                ||
                data.error
                ||
                "تغییر وضعیت پیشنهاد تنظیم ناموفق بود."
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
                data.detail
                ||
                data.error
                ||
                "اعمال پیشنهاد تنظیم ناموفق بود."
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
                data.detail
                ||
                data.error
                ||
                "بازگردانی پیشنهاد تنظیم ناموفق بود."
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
                        ${escapeHtml(
                            item.metric
                            || "—"
                        )}
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
                                    error.message
                                    ||
                                    "خطا در عملیات پیشنهاد تنظیم."
                                );
                            }
                        }
                    );
                }
            );
    }


    async function loadTuningSuggestions() {

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
                    data.detail
                    ||
                    data.error
                    ||
                    `خطا در دریافت پیشنهادهای تنظیم (${response.status})`
                );
            }


            renderTable(
                data.results
                || []
            );

        }

        catch (error) {

            setState(
                "error",
                error.message
                ||
                "خطا در دریافت پیشنهادهای تنظیم."
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


    loadTuningSuggestions();

})();