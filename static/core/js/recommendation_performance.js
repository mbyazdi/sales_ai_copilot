(function () {
    "use strict";

    const customerCode =
        window.customerCode || "";

    const tableWrap =
        document.getElementById(
            "performanceTableWrap"
        );

    const tableBody =
        document.getElementById(
            "performanceTableBody"
        );

    const loading =
        document.getElementById(
            "performanceLoading"
        );

    const errorBox =
        document.getElementById(
            "performanceError"
        );

    const emptyBox =
        document.getElementById(
            "performanceEmpty"
        );

    const refreshButton =
        document.getElementById(
            "refreshRecommendationPerformance"
        );


    const labels = {
        REPEAT_PURCHASE: "خرید مجدد",
        CROSS_SELL: "فروش مکمل",
        CATEGORY: "پیشنهاد دسته",
        SIMILAR_PRODUCT: "محصول مشابه",
        UP_SELL: "فروش ارتقایی",
        UPSELL: "فروش ارتقایی"
    };


    const learningSignalLabels = {
        POSITIVE: "مثبت",
        PROMISING: "امیدبخش",
        WEAK: "ضعیف",
        NEUTRAL: "خنثی",
        INSUFFICIENT_DATA: "داده ناکافی"
    };


    const performanceLevelLabels = {
        HIGH: "بالا",
        MEDIUM: "متوسط",
        LOW: "پایین",
        UNKNOWN: "نامشخص"
    };


    const dataQualityLabels = {
        SUFFICIENT_DATA: "داده کافی",
        LIMITED_DATA: "داده محدود",
        INSUFFICIENT_DATA: "داده ناکافی"
    };


    function number(value) {

        return new Intl.NumberFormat(
            "fa-IR"
        ).format(
            Number(value || 0)
        );
    }


    function money(value) {

        return new Intl.NumberFormat(
            "fa-IR",
            {
                maximumFractionDigits: 2
            }
        ).format(
            Number(value || 0)
        );
    }


    function percent(value) {

        return (
            new Intl.NumberFormat(
                "fa-IR",
                {
                    maximumFractionDigits: 1
                }
            ).format(
                Number(value || 0)
            )
            + "%"
        );
    }


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


    function setText(
        id,
        value
    ) {

        const element =
            document.getElementById(
                id
            );

        if (element) {
            element.textContent = value;
        }
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


    function renderSummary(
        summary
    ) {

        setText(
            "performancePresented",
            number(
                summary.presented
            )
        );

        setText(
            "performancePurchased",
            number(
                summary.purchased
            )
        );

        setText(
            "performanceInterested",
            number(
                summary.interested
            )
        );

        setText(
            "performanceFollowUp",
            number(
                summary.follow_up
            )
        );

        setText(
            "performanceRejected",
            number(
                summary.rejected
            )
        );

        setText(
            "performanceRevenue",
            money(
                summary.revenue
            )
        );

        setText(
            "performanceAverageSales",
            money(
                summary.average_sales_amount
            )
        );

        setText(
            "performanceConversion",
            percent(
                summary.conversion_rate
            )
        );

        setText(
            "performanceInterestRate",
            percent(
                summary.interest_rate
            )
        );

        setText(
            "performanceFollowUpRate",
            percent(
                summary.follow_up_rate
            )
        );

        setText(
            "performanceRejectionRate",
            percent(
                summary.rejection_rate
            )
        );

        setText(
            "performanceEngagementRate",
            percent(
                summary.engagement_rate
            )
        );
    }


    function renderTable(
        items
    ) {

        if (!tableBody) {
            return;
        }


        tableBody.innerHTML =
            "";


        if (
            !Array.isArray(items) ||
            !items.length
        ) {

            setState(
                "empty"
            );

            return;
        }


        items.forEach(
            function (item) {

                const row =
                    document.createElement(
                        "tr"
                    );


                const learningSignal =
                    learningSignalLabels[
                        item.learning_signal
                    ]
                    || item.learning_signal
                    || "—";


                const performanceLevel =
                    performanceLevelLabels[
                        item.performance_level
                    ]
                    || item.performance_level
                    || "—";


                const dataQuality =
                    dataQualityLabels[
                        item.data_quality
                    ]
                    || item.data_quality
                    || "—";


                row.innerHTML = `
                    <td class="performance-type">
                        ${escapeHtml(
                            labels[
                                item.recommendation_type
                            ]
                            ||
                            item.recommendation_type
                            ||
                            "پیشنهاد"
                        )}
                    </td>

                    <td>
                        ${number(
                            item.presented
                        )}
                    </td>

                    <td>
                        ${number(
                            item.purchased
                        )}
                    </td>

                    <td>
                        ${number(
                            item.interested
                        )}
                    </td>

                    <td>
                        ${number(
                            item.rejected
                        )}
                    </td>

                    <td>
                        ${number(
                            item.follow_up
                        )}
                    </td>

                    <td class="performance-revenue">
                        ${money(
                            item.revenue
                        )}
                    </td>

                    <td class="performance-revenue">
                        ${money(
                            item.average_revenue
                        )}
                    </td>

                    <td class="performance-rate">
                        ${percent(
                            item.conversion_rate
                        )}
                    </td>

                    <td class="performance-rate">
                        ${percent(
                            item.interest_rate
                        )}
                    </td>

                    <td class="performance-rate">
                        ${percent(
                            item.engagement_rate
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            learningSignal
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            performanceLevel
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            dataQuality
                        )}
                    </td>
                `;


                tableBody.appendChild(
                    row
                );
            }
        );


        setState(
            "ready"
        );
    }


    async function loadPerformance() {

        if (!customerCode) {

            setState(
                "error",
                "کد مشتری برای دریافت عملکرد پیشنهادها پیدا نشد."
            );

            return;
        }


        setState(
            "loading"
        );


        try {

            const response =
                await fetch(
                    `/api/recommendations/v1/customers/${encodeURIComponent(
                        customerCode
                    )}/performance/?_=${Date.now()}`,
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
                    `خطا در دریافت عملکرد (${response.status})`
                );
            }


            renderSummary(
                data.summary || {}
            );


            renderTable(
                data.performance || []
            );

        }

        catch (error) {

            setState(
                "error",
                error.message
                ||
                "خطا در دریافت عملکرد پیشنهادها."
            );
        }
    }


    if (refreshButton) {

        refreshButton.addEventListener(
            "click",
            loadPerformance
        );
    }


    loadPerformance();

})();