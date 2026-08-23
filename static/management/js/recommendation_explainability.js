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

    const detailBackdrop =
        document.getElementById(
            "recommendationDetailBackdrop"
        );

    const detailDrawer =
        document.getElementById(
            "recommendationDetailDrawer"
        );

    const detailCloseButton =
        document.getElementById(
            "closeRecommendationDetail"
        );

    const detailLoading =
        document.getElementById(
            "recommendationDetailLoading"
        );

    const detailError =
        document.getElementById(
            "recommendationDetailError"
        );

    const detailContent =
        document.getElementById(
            "recommendationDetailContent"
        );

    const detailTitle =
        document.getElementById(
            "recommendationDetailTitle"
        );

    const detailSubtitle =
        document.getElementById(
            "recommendationDetailSubtitle"
        );

    const detailFinalScore =
        document.getElementById(
            "detailFinalScore"
        );

    const detailConfidence =
        document.getElementById(
            "detailConfidence"
        );

    const detailEvidence =
        document.getElementById(
            "detailEvidence"
        );

    const detailActiveSignals =
        document.getElementById(
            "detailActiveSignals"
        );

    const detailScoreBreakdown =
        document.getElementById(
            "detailScoreBreakdown"
        );

    const detailSignals =
        document.getElementById(
            "detailSignals"
        );

    const detailReason =
        document.getElementById(
            "detailReason"
        );

    const detailRecommendationId =
        document.getElementById(
            "detailRecommendationId"
        );

    const detailRank =
        document.getElementById(
            "detailRank"
        );

    const detailCustomerCode =
        document.getElementById(
            "detailCustomerCode"
        );

    const detailProductCode =
        document.getElementById(
            "detailProductCode"
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

    function setDetailState(
        state,
        message = ""
    ) {
        if (detailLoading) {
            detailLoading.hidden =
                state !== "loading";
        }

        if (detailError) {
            detailError.hidden =
                state !== "error";

            detailError.textContent =
                message;
        }

        if (detailContent) {
            detailContent.hidden =
                state !== "ready";
        }
    }


    function openDetailDrawer() {
        if (detailBackdrop) {
            detailBackdrop.hidden = false;
        }

        if (detailDrawer) {
            detailDrawer.hidden = false;
            detailDrawer.setAttribute(
                "aria-hidden",
                "false"
            );
        }

        document.body.classList.add(
            "recommendation-detail-open"
        );
    }


    function closeDetailDrawer() {
        if (detailBackdrop) {
            detailBackdrop.hidden = true;
        }

        if (detailDrawer) {
            detailDrawer.hidden = true;
            detailDrawer.setAttribute(
                "aria-hidden",
                "true"
            );
        }

        document.body.classList.remove(
            "recommendation-detail-open"
        );
    }


    function renderDetail(data) {
        const product =
            data.product || {};

        const breakdown =
            data.score_breakdown || {};

        const snapshot =
            data.explanation_snapshot || {};

        const signals =
            Array.isArray(snapshot.signals)
                ? snapshot.signals
                : [];

        if (detailTitle) {
            detailTitle.textContent =
                product.name
                || product.code
                || "جزئیات پیشنهاد";
        }

        if (detailSubtitle) {
            detailSubtitle.textContent =
                `${data.customer_code || "—"} / ${product.code || "—"}`;
        }

        if (detailFinalScore) {
            detailFinalScore.textContent =
                number(data.score);
        }

        if (detailConfidence) {
            detailConfidence.textContent =
                `${number(
                    data.confidence_score
                )}%`;
        }

        if (detailEvidence) {
            detailEvidence.textContent =
                evidenceLabels[
                    data.evidence_quality
                ]
                || data.evidence_quality
                || "—";
        }

        if (detailActiveSignals) {
            detailActiveSignals.textContent =
                number(
                    data.active_signal_count
                );
        }

        if (detailReason) {
            detailReason.textContent =
                data.reason || "—";
        }

        if (detailRecommendationId) {
            detailRecommendationId.textContent =
                number(data.id);
        }

        if (detailRank) {
            detailRank.textContent =
                number(data.rank);
        }

        if (detailCustomerCode) {
            detailCustomerCode.textContent =
                data.customer_code || "—";
        }

        if (detailProductCode) {
            detailProductCode.textContent =
                product.code || "—";
        }

        if (detailScoreBreakdown) {
            detailScoreBreakdown.innerHTML = "";

            Object.entries(breakdown).forEach(
                function ([key, value]) {
                    const item =
                        document.createElement(
                            "div"
                        );

                    item.className =
                        "recommendation-detail-list-item";

                    item.innerHTML = `
                        <span>
                            ${escapeHtml(key)}
                        </span>
                        <strong>
                            ${signedNumber(value)}
                        </strong>
                    `;

                    detailScoreBreakdown.appendChild(
                        item
                    );
                }
            );
        }

        if (detailSignals) {
            detailSignals.innerHTML = "";

            signals.forEach(
                function (signal) {
                    const item =
                        document.createElement(
                            "div"
                        );

                    item.className =
                        "recommendation-detail-list-item";

                    item.innerHTML = `
                        <span>
                            ${escapeHtml(
                                signal.name || "—"
                            )}
                        </span>
                        <strong>
                            ${signedNumber(
                                signal.score
                            )}
                            ${
                                signal.active
                                    ? "✓"
                                    : ""
                            }
                        </strong>
                    `;

                    detailSignals.appendChild(
                        item
                    );
                }
            );
        }
    }


    async function loadRecommendationDetail(
        recommendationId
    ) {
        openDetailDrawer();
        setDetailState("loading");

        try {
            const response =
                await fetch(
                    `/api/recommendations/v1/diagnostics/${recommendationId}/?_=${Date.now()}`,
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
                    `خطا در دریافت جزئیات (${response.status})`
                );
            }

            renderDetail(data);
            setDetailState("ready");

        } catch (error) {
            setDetailState(
                "error",
                error.message
                ||
                "خطا در دریافت جزئیات پیشنهاد."
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
                row.dataset.recommendationId =
                    item.id;

                row.classList.add(
                    "diagnostics-row"
                );

                row.tabIndex = 0;

                row.setAttribute(
                    "role",
                    "button"
                );

                row.setAttribute(
                    "aria-label",
                    `نمایش جزئیات پیشنهاد ${item.product_name || item.product_code || ""}`
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

    function handleDiagnosticsRowActivate(
        event
    ) {
        const row =
            event.target.closest(
                ".diagnostics-row"
            );

        if (!row) {
            return;
        }

        const recommendationId =
            row.dataset.recommendationId;

        if (!recommendationId) {
            return;
        }

        loadRecommendationDetail(
            recommendationId
        );
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

    if (tableBody) {
        tableBody.addEventListener(
            "click",
            handleDiagnosticsRowActivate
        );

        tableBody.addEventListener(
            "keydown",
            function (event) {
                if (
                    event.key !== "Enter"
                    &&
                    event.key !== " "
                ) {
                    return;
                }

                const row =
                    event.target.closest(
                        ".diagnostics-row"
                    );

                if (!row) {
                    return;
                }

                event.preventDefault();

                handleDiagnosticsRowActivate(
                    event
                );
            }
        );
    }

    if (detailCloseButton) {
        detailCloseButton.addEventListener(
            "click",
            closeDetailDrawer
        );
    }

    if (detailBackdrop) {
        detailBackdrop.addEventListener(
            "click",
            closeDetailDrawer
        );
    }

    document.addEventListener(
        "keydown",
        function (event) {
            if (
                event.key === "Escape"
                &&
                detailDrawer
                &&
                !detailDrawer.hidden
            ) {
                closeDetailDrawer();
            }
        }
    );

    if (refreshButton) {
        refreshButton.addEventListener(
            "click",
            loadDiagnostics
        );
    }


    loadDiagnostics();

})();