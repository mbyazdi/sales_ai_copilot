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

        const summaryTotal =
            document.getElementById(
                "diagnosticsSummaryTotal"
            );

        const summaryConfidence =
            document.getElementById(
                "diagnosticsSummaryConfidence"
            );

        const summaryHigh =
            document.getElementById(
                "diagnosticsSummaryHigh"
            );

        const summaryMedium =
            document.getElementById(
                "diagnosticsSummaryMedium"
            );

        const summaryLow =
            document.getElementById(
                "diagnosticsSummaryLow"
            );

        const summaryLowConfidence =
            document.getElementById(
                "diagnosticsSummaryLowConfidence"
            );

        const summaryNegativeFeedback =
            document.getElementById(
                "diagnosticsSummaryNegativeFeedback"
            );

        const summarySingleSignal =
            document.getElementById(
                "diagnosticsSummarySingleSignal"
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

    function renderSummary(data) {
        const evidence =
            data.evidence || {};

        const qualityFlags =
            data.quality_flags || {};

        if (summaryTotal) {
            summaryTotal.textContent =
                number(
                    data.total_recommendations
                );
        }

        if (summaryConfidence) {
            summaryConfidence.textContent =
                `${number(
                    data.average_confidence
                )}%`;
        }

        if (summaryHigh) {
            summaryHigh.textContent =
                number(
                    evidence.high
                );
        }

        if (summaryMedium) {
            summaryMedium.textContent =
                number(
                    evidence.medium
                );
        }

        if (summaryLow) {
            summaryLow.textContent =
                number(
                    evidence.low
                );
        }

        if (summaryLowConfidence) {
            summaryLowConfidence.textContent =
                number(
                    qualityFlags.low_confidence
                );
        }

        if (summaryNegativeFeedback) {
            summaryNegativeFeedback.textContent =
                number(
                    qualityFlags.negative_feedback
                );
        }

        if (summarySingleSignal) {
            summarySingleSignal.textContent =
                number(
                    qualityFlags.single_signal
                );
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
            const [
                diagnosticsResponse,
                summaryResponse
            ] = await Promise.all([
                fetch(
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
                ),

                fetch(
                    `/api/recommendations/v1/diagnostics/summary/?_=${Date.now()}`,
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
                )
            ]);

            let diagnosticsData = {};
            let summaryData = {};

            try {
                diagnosticsData =
                    await diagnosticsResponse.json();
            } catch (error) {
                diagnosticsData = {};
            }

            try {
                summaryData =
                    await summaryResponse.json();
            } catch (error) {
                summaryData = {};
            }

            if (!diagnosticsResponse.ok) {
                throw new Error(
                    diagnosticsData.detail
                    ||
                    diagnosticsData.error
                    ||
                    `خطا در دریافت Diagnostics (${diagnosticsResponse.status})`
                );
            }

            if (!summaryResponse.ok) {
                throw new Error(
                    summaryData.detail
                    ||
                    summaryData.error
                    ||
                    `خطا در دریافت Summary (${summaryResponse.status})`
                );
            }

            renderSummary(
                summaryData
            );

            renderTable(
                diagnosticsData.results
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