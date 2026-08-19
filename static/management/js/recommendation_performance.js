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


    const performanceLabels = {

        HIGH:
            "بالا",

        MEDIUM:
            "متوسط",

        LOW:
            "پایین",

        UNKNOWN:
            "نامشخص"

    };


    const learningLabels = {

        POSITIVE:
            "مثبت",

        PROMISING:
            "امیدبخش",

        NEUTRAL:
            "خنثی",

        WEAK:
            "ضعیف",

        INSUFFICIENT_DATA:
            "داده ناکافی"

    };


    const dataQualityLabels = {

        SUFFICIENT_DATA:
            "داده کافی",

        LIMITED_DATA:
            "داده محدود",

        INSUFFICIENT_DATA:
            "داده ناکافی"

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


    function normalizeClass(value) {

        return String(
            value || "UNKNOWN"
        )
            .toLowerCase()
            .replaceAll(
                "_",
                "-"
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


        /* -----------------------------------------------------
           EMPTY STATE
        ----------------------------------------------------- */

        if (!items.length) {

            tableBody.innerHTML = `
                <tr>
                    <td
                        colspan="13"
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


        /* -----------------------------------------------------
           PERFORMANCE ROWS
        ----------------------------------------------------- */

        items.forEach(function (item) {

            const row =
                document.createElement(
                    "tr"
                );


            const recommendationLabel =
                recommendationLabels[
                    item.recommendation_type
                ]
                || item.recommendation_type
                || "—";


            const performanceLabel =
                performanceLabels[
                    item.performance_level
                ]
                || item.performance_level
                || "—";


            const learningLabel =
                learningLabels[
                    item.learning_signal
                ]
                || item.learning_signal
                || "—";


            const dataQualityLabel =
                dataQualityLabels[
                    item.data_quality
                ]
                || item.data_quality
                || "—";


            row.innerHTML = `

                <td class="recommendation-type">

                    ${recommendationLabel}

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


                <td class="engagement">

                    ${formatPercent(
                        item.engagement_rate
                    )}

                </td>


                <td>

                    <span
                        class="
                            intelligence-badge
                            performance-${normalizeClass(
                                item.performance_level
                            )}
                        "
                    >

                        ${performanceLabel}

                    </span>

                </td>


                <td>

                    <span
                        class="
                            intelligence-badge
                            learning-${normalizeClass(
                                item.learning_signal
                            )}
                        "
                    >

                        ${learningLabel}

                    </span>

                </td>


                <td>

                    <span
                        class="
                            intelligence-badge
                            quality-${normalizeClass(
                                item.data_quality
                            )}
                        "
                    >

                        ${dataQualityLabel}

                    </span>

                </td>


                <td class="revenue">

                    ${formatMoney(
                        item.revenue
                    )}

                </td>

            `;


            tableBody.appendChild(
                row
            );

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

            errorBox.textContent =
                "";

        }


        try {

            const response =
                await fetch(
                    apiUrl,
                    {
                        method:
                            "GET",

                        headers: {
                            "Accept":
                                "application/json"
                        },

                        credentials:
                            "same-origin"
                    }
                );


            /*
             * ابتدا پاسخ به صورت text خوانده می‌شود.
             *
             * اگر Django به جای JSON یک HTML page
             * برگرداند، پیام خطای قابل فهم‌تری
             * خواهیم داشت.
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
                    + "یا Django به‌جای JSON "
                    + "یک صفحه HTML برگردانده است."
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
             * Expected API structure:
             *
             * {
             *     customer: ...,
             *
             *     summary: {
             *         presented,
             *         purchased,
             *         interested,
             *         revenue,
             *         conversion_rate,
             *         interest_rate
             *     },
             *
             *     performance: [
             *         {
             *             recommendation_type,
             *             presented,
             *             purchased,
             *             interested,
             *             rejected,
             *             follow_up,
             *             not_presented,
             *             revenue,
             *             average_revenue,
             *             conversion_rate,
             *             interest_rate,
             *             engagement_rate,
             *             performance_level,
             *             learning_signal,
             *             data_quality
             *         }
             *     ]
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