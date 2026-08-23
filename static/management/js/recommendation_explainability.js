(function () {
    "use strict";

    const tableWrap =
        document.getElementById(
            "diagnosticsTableWrap"
        );

    const tableBody =
        document.getElementById(
            "diagnosticsTableBody"
        );

    const loading =
        document.getElementById(
            "diagnosticsLoading"
        );

    const errorBox =
        document.getElementById(
            "diagnosticsError"
        );

    const emptyBox =
        document.getElementById(
            "diagnosticsEmpty"
        );

    const refreshButton =
        document.getElementById(
            "refreshRecommendationDiagnostics"
        );


    const typeLabels = {
        REPEAT_PURCHASE: "خرید مجدد",
        CROSS_SELL: "فروش مکمل",
        CATEGORY: "پیشنهاد دسته",
        SIMILAR_PRODUCT: "محصول مشابه",
        UP_SELL: "فروش ارتقایی",
        UPSELL: "فروش ارتقایی"
    };


    const evidenceLabels = {
        HIGH: "قوی",
        MEDIUM: "متوسط",
        LOW: "محدود"
    };


    function escapeHtml(value) {
        return String(value ?? "").replace(
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


    function signedNumber(value) {
        const numericValue =
            Number(value || 0);

        const formatted =
            number(numericValue);

        if (numericValue > 0) {
            return `+${formatted}`;
        }

        return formatted;
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


    function renderTable(items) {
        if (!tableBody) {
            return;
        }

        tableBody.innerHTML = "";

        if (
            !Array.isArray(items)
            ||
            !items.length
        ) {
            setState("empty");
            return;
        }

        items.forEach(
            function (item) {

                const row =
                    document.createElement(
                        "tr"
                    );

                row.innerHTML = `
                    <td>
                        ${number(item.rank)}
                    </td>

                    <td>
                        <strong>
                            ${escapeHtml(
                                item.product_name
                                ||
                                item.product_code
                                ||
                                "—"
                            )}
                        </strong>

                        <div class="diagnostics-subtext">
                            ${escapeHtml(
                                item.customer_code
                                ||
                                ""
                            )}
                            /
                            ${escapeHtml(
                                item.product_code
                                ||
                                ""
                            )}
                        </div>
                    </td>

                    <td>
                        ${escapeHtml(
                            typeLabels[
                                item.recommendation_type
                            ]
                            ||
                            item.recommendation_type
                            ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${number(
                            item.score
                        )}
                    </td>

                    <td>
                        ${number(
                            item.confidence_score
                        )}%
                    </td>

                    <td>
                        ${escapeHtml(
                            evidenceLabels[
                                item.evidence_quality
                            ]
                            ||
                            item.evidence_quality
                            ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${number(
                            item.active_signal_count
                        )}
                    </td>

                    <td>
                        ${number(
                            item.rule_score
                        )}
                    </td>

                    <td>
                        ${signedNumber(
                            item.feedback_score
                        )}
                    </td>
                `;

                tableBody.appendChild(
                    row
                );
            }
        );

        setState("ready");
    }


    async function loadDiagnostics() {
        setState("loading");

        try {
            const response =
                await fetch(
                    `/api/recommendations/v1/diagnostics/?_=${Date.now()}`,
                    {
                        method: "GET",

                        headers: {
                            "Accept":
                                "application/json"
                        },

                        credentials:
                            "same-origin",

                        cache:
                            "no-store"
                    }
                );

            let data = {};

            try {
                data =
                    await response.json();
            } catch (error) {
                data = {};
            }

            if (!response.ok) {
                throw new Error(
                    data.detail
                    ||
                    data.error
                    ||
                    `خطا در دریافت Diagnostics (${response.status})`
                );
            }

            renderTable(
                data.results
                || []
            );

        } catch (error) {
            setState(
                "error",
                error.message
                ||
                "خطا در دریافت جزئیات Explainability."
            );
        }
    }


    if (refreshButton) {
        refreshButton.addEventListener(
            "click",
            loadDiagnostics
        );
    }


    loadDiagnostics();

})();