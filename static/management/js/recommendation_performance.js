(function () {

    "use strict";


    /* =========================================================
       API
    ========================================================= */

    const apiUrl =
        window.salesRecommendationPerformance?.apiUrl
        || "/api/visits/v1/recommendations/performance/";


    /* =========================================================
       DOM
    ========================================================= */

    const loadingBox =
        document.getElementById(
            "performanceLoading"
        );


    const errorBox =
        document.getElementById(
            "performanceError"
        );


    const tableBody =
        document.getElementById(
            "performanceTableBody"
        );


    const summaryPresented =
        document.getElementById(
            "summaryPresented"
        );


    const summaryPurchased =
        document.getElementById(
            "summaryPurchased"
        );


    const summaryInterested =
        document.getElementById(
            "summaryInterested"
        );


    const summaryRevenue =
        document.getElementById(
            "summaryRevenue"
        );


    const summaryConversion =
        document.getElementById(
            "summaryConversion"
        );


    const summaryInterest =
        document.getElementById(
            "summaryInterest"
        );


    /* =========================================================
       LABELS
    ========================================================= */

    const recommendationLabels = {

        REPEAT_PURCHASE:
            "خرید مجدد",

        CROSS_SELL:
            "فروش مکمل",

        CATEGORY:
            "پیشنهاد دسته",

        SIMILAR_PRODUCT:
            "محصول مشابه",

        UP_SELL:
            "فروش ارتقایی"

    };


    /* =========================================================
       FORMATTERS
    ========================================================= */

    function formatNumber(value) {

        return new Intl.NumberFormat(
            "fa-IR"
        ).format(
            Number(value || 0)
        );

    }


    function formatMoney(value) {

        return new Intl.NumberFormat(
            "fa-IR",
            {
                maximumFractionDigits: 2
            }
        ).format(
            Number(value || 0)
        );

    }


    function formatPercent(value) {

        return (
            Number(value || 0)
                .toLocaleString(
                    "fa-IR",
                    {
                        maximumFractionDigits: 2
                    }
                )
            + "%"
        );

    }


    /* =========================================================
       SUMMARY
    ========================================================= */

    function renderSummary(summary) {

        if (summaryPresented) {
            summaryPresented.textContent =
                formatNumber(
                    summary.presented
                );
        }


        if (summaryPurchased) {
            summaryPurchased.textContent =
                formatNumber(
                    summary.purchased
                );
        }


        if (summaryInterested) {
            summaryInterested.textContent =
                formatNumber(
                    summary.interested
                );
        }


        if (summaryRevenue) {
            summaryRevenue.textContent =
                formatMoney(
                    summary.revenue
                );
        }


        if (summaryConversion) {
            summaryConversion.textContent =
                formatPercent(
                    summary.conversion_rate
                );
        }


        if (summaryInterest) {
            summaryInterest.textContent =
                formatPercent(
                    summary.interest_rate
                );
        }

    }


    /* =========================================================
       PERFORMANCE TABLE
    ========================================================= */

    function renderPerformance(items) {

        if (!tableBody) {
            return;
        }


        tableBody.innerHTML = "";


        if (!items.length) {

            tableBody.innerHTML = `
                <tr>
                    <td
                        colspan="9"
                        class="table-empty"
                    >
                        هنوز داده‌ای برای
                        ارزیابی عملکرد پیشنهادها
                        ثبت نشده است.
                    </td>
                </tr>
            `;

            return;
        }


        items.forEach(function (item) {

            const row =
                document.createElement(
                    "tr"
                );


            const label =
                recommendationLabels[
                    item.recommendation_type
                ]
                || item.recommendation_type
                || "—";


            row.innerHTML = `

                <td class="recommendation-type">
                    ${label}
                </td>

                <td>
                    ${formatNumber(
                        item.presented
                    )}
                </td>

                <td class="purchased">
                    ${formatNumber(
                        item.purchased
                    )}
                </td>

                <td class="interested">
                    ${formatNumber(
                        item.interested
                    )}
                </td>

                <td>
                    ${formatNumber(
                        item.rejected
                    )}
                </td>

                <td>
                    ${formatNumber(
                        item.follow_up
                    )}
                </td>

                <td class="conversion">
                    ${formatPercent(
                        item.conversion_rate
                    )}
                </td>

                <td>
                    ${formatPercent(
                        item.interest_rate
                    )}
                </td>

                <td class="revenue">
                    ${formatMoney(
                        item.revenue
                    )}
                </td>

            `;


            tableBody.appendChild(row);

        });

    }


    /* =========================================================
       LOAD PERFORMANCE
    ========================================================= */

    async function loadPerformance() {

        if (loadingBox) {
            loadingBox.style.display =
                "block";
        }


        if (errorBox) {
            errorBox.style.display =
                "none";

            errorBox.textContent = "";
        }


        try {

            const response =
                await fetch(
                    apiUrl,
                    {
                        method: "GET",

                        headers: {
                            "Accept":
                                "application/json"
                        },

                        credentials:
                            "same-origin"
                    }
                );


            /*
             * ابتدا response را به text می‌خوانیم.
             *
             * دلیل:
             * اگر Django به هر دلیلی HTML برگرداند،
             * response.json() مستقیماً خطای
             * JSON.parse می‌دهد و تشخیص مشکل سخت می‌شود.
             */

            const rawResponse =
                await response.text();


            let data;


            try {

                data =
                    JSON.parse(
                        rawResponse
                    );

            } catch (jsonError) {

                throw new Error(
                    "پاسخ API JSON معتبر نیست. "
                    + "احتمالاً آدرس API اشتباه است "
                    + "یا Django به‌جای JSON یک صفحه HTML برگردانده است."
                );

            }


            if (!response.ok) {

                throw new Error(
                    data.detail
                    || data.error
                    || "دریافت اطلاعات عملکرد ناموفق بود."
                );

            }


            /*
             * ساختار مورد انتظار:
             *
             * {
             *     customer: ...,
             *     summary: {...},
             *     performance: [...]
             * }
             */

            renderSummary(
                data.summary || {}
            );


            renderPerformance(
                Array.isArray(
                    data.performance
                )
                    ? data.performance
                    : []
            );


        } catch (error) {

            console.error(
                "Recommendation performance error:",
                error
            );


            if (errorBox) {

                errorBox.textContent =
                    error.message
                    || "خطا در دریافت اطلاعات عملکرد.";

                errorBox.style.display =
                    "block";

            }

        } finally {

            if (loadingBox) {

                loadingBox.style.display =
                    "none";

            }

        }

    }


    /* =========================================================
       INIT
    ========================================================= */

    loadPerformance();


})();