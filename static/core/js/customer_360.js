(function () {
    "use strict";


    /* =========================================================
       GLOBAL CONTEXT
    ========================================================= */

    const customerCode =
        (window.salesAiCopilot &&
            window.salesAiCopilot.customerCode) || "";

    const visitId =
        (window.salesAiCopilot &&
            window.salesAiCopilot.visitId) || null;


    /* =========================================================
       LABELS
    ========================================================= */

    const outcomeLabels = {
        PURCHASED: "خرید شد",
        INTERESTED: "علاقه‌مند شد",
        FOLLOW_UP: "نیاز به پیگیری",
        REJECTED: "رد شد",
        NOT_PRESENTED: "مطرح نشد"
    };


    const recommendationLabels = {
        REPEAT_PURCHASE: "خرید مجدد",
        CROSS_SELL: "فروش مکمل",
        CATEGORY: "پیشنهاد دسته",
        SIMILAR_PRODUCT: "محصول مشابه",
        UP_SELL: "فروش ارتقایی"
    };


    /* =========================================================
       HELPERS
    ========================================================= */

    function formatNumber(value) {

        return new Intl.NumberFormat("fa-IR")
            .format(Number(value || 0));
    }


    function formatMoney(value) {

        return new Intl.NumberFormat(
            "fa-IR",
            {
                maximumFractionDigits: 2
            }
        ).format(Number(value || 0));
    }


    function formatDate(value) {

        if (!value) {
            return "—";
        }

        const parts = String(value).split("-");

        if (parts.length === 3) {

            return (
                `${parts[2]} / ` +
                `${parts[1]} / ` +
                `${parts[0]}`
            );
        }

        return value;
    }


    function resultClass(outcome) {

        return String(outcome || "")
            .toLowerCase()
            .replaceAll("_", "-");
    }


    function escapeHtml(value) {

        return String(value ?? "")
            .replace(
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


    function getCsrfToken() {

        const name = "csrftoken";

        const cookies =
            document.cookie
                .split(";")
                .map(cookie => cookie.trim());

        for (const cookie of cookies) {

            if (cookie.startsWith(name + "=")) {

                return decodeURIComponent(
                    cookie.substring(name.length + 1)
                );
            }
        }

        return "";
    }


    /* =========================================================
       RECOMMENDATION STATUS
       
       این تابع خارج از Modal قرار دارد تا هم Modal
       و هم Sales History بتوانند از آن استفاده کنند.
    ========================================================= */

    function getRecommendationStatus(
        recommendationId
    ) {

        return document.querySelector(
            `.recommendation-outcome-status[data-outcome-status="${recommendationId}"]`
        );
    }


    function updateRecommendationStatus(
        recommendationId,
        outcome,
        quantity,
        amount
    ) {

        const statusBox =
            getRecommendationStatus(
                recommendationId
            );

        if (!statusBox) {
            return;
        }


        const statusValue =
            statusBox.querySelector(
                ".status-value"
            );

        if (!statusValue) {
            return;
        }


        let text =
            outcomeLabels[outcome] ||
            outcome ||
            "—";


        if (outcome === "PURCHASED") {

            if (
                Number(quantity || 0) > 0 ||
                Number(amount || 0) > 0
            ) {

                text +=
                    ` · تعداد ${formatNumber(quantity)}` +
                    ` · مبلغ ${formatMoney(amount)}`;
            }
        }


        statusValue.textContent = text;


        statusBox.classList.add(
            "has-outcome"
        );


        statusBox.dataset.outcome =
            outcome || "";


        statusBox.classList.remove(
            "status-purchased",
            "status-interested",
            "status-follow-up",
            "status-rejected",
            "status-not-presented"
        );


        const cssClass =
            resultClass(outcome);


        if (cssClass) {

            statusBox.classList.add(
                `status-${cssClass}`
            );
        }
    }


    /* =========================================================
       RESTORE LAST STATUS FOR EACH RECOMMENDATION
       
       تاریخچه ممکن است برای یک Recommendation چند رکورد داشته
       باشد. فقط آخرین رکورد همان Recommendation وضعیت فعلی
       کارت را تعیین می‌کند.
    ========================================================= */

    function restoreRecommendationStatuses(
        items
    ) {

        if (!Array.isArray(items)) {
            return;
        }


        const latestByRecommendation =
            new Map();


        items.forEach(function (item) {

            const recommendation =
                item.recommendation;


            if (
                !recommendation ||
                recommendation.id === undefined ||
                recommendation.id === null
            ) {

                return;
            }


            const recommendationId =
                Number(recommendation.id);


            const existing =
                latestByRecommendation.get(
                    recommendationId
                );


            if (!existing) {

                latestByRecommendation.set(
                    recommendationId,
                    item
                );

                return;
            }


            /*
             * created_at جدیدتر = وضعیت فعلی‌تر
             */

            const existingDate =
                new Date(
                    existing.created_at || 0
                ).getTime();


            const currentDate =
                new Date(
                    item.created_at || 0
                ).getTime();


            if (currentDate >= existingDate) {

                latestByRecommendation.set(
                    recommendationId,
                    item
                );
            }
        });


        latestByRecommendation.forEach(
            function (item, recommendationId) {

                updateRecommendationStatus(
                    recommendationId,
                    item.outcome,
                    item.quantity,
                    item.sales_amount
                );
            }
        );
    }


    /* =========================================================
       STAGE 7
       SALES OUTCOME MODAL
    ========================================================= */

    const modal =
        document.getElementById(
            "outcomeModal"
        );


    const form =
        document.getElementById(
            "outcomeForm"
        );


    if (modal && form) {

        const modalProduct =
            document.getElementById(
                "outcomeModalProduct"
            );


        const modalOutcome =
            document.getElementById(
                "outcomeModalOutcome"
            );


        const closeButton =
            document.getElementById(
                "outcomeModalClose"
            );


        const cancelButton =
            document.getElementById(
                "outcomeCancel"
            );


        const submitButton =
            document.getElementById(
                "outcomeSubmit"
            );


        const quantityInput =
            document.getElementById(
                "outcomeQuantity"
            );


        const salesAmountInput =
            document.getElementById(
                "outcomeSalesAmount"
            );


        const notesInput =
            document.getElementById(
                "outcomeNotes"
            );


        const errorBox =
            document.getElementById(
                "outcomeError"
            );


        const successBox =
            document.getElementById(
                "outcomeSuccess"
            );


        const statusBox =
            document.getElementById(
                "outcomeStatus"
            );


        let selectedRecommendationId = null;

        let selectedOutcome = null;

        let selectedButton = null;


        /* -----------------------------------------------------
           CLEAR MESSAGES
        ----------------------------------------------------- */

        function clearMessages() {

            if (errorBox) {

                errorBox.style.display =
                    "none";

                errorBox.textContent =
                    "";
            }


            if (successBox) {

                successBox.style.display =
                    "none";

                successBox.textContent =
                    "";
            }
        }


        /* -----------------------------------------------------
           OPEN MODAL
        ----------------------------------------------------- */

        function openModal(button) {

            selectedRecommendationId =
                button.dataset.recommendationId ||
                null;


            selectedOutcome =
                button.dataset.outcome ||
                null;


            selectedButton =
                button;


            const name =
                button.dataset.productName ||
                "";


            const code =
                button.dataset.productCode ||
                "";


            if (modalProduct) {

                modalProduct.textContent =
                    name +
                    (
                        code
                            ? " — " + code
                            : ""
                    );
            }


            if (modalOutcome) {

                modalOutcome.textContent =
                    outcomeLabels[
                        selectedOutcome
                    ] ||
                    selectedOutcome ||
                    "";
            }


            if (quantityInput) {

                quantityInput.value =
                    "0";
            }


            if (salesAmountInput) {

                salesAmountInput.value =
                    "0";
            }


            if (notesInput) {

                notesInput.value =
                    "";
            }


            clearMessages();


            document
                .querySelectorAll(
                    ".outcome-btn.selected"
                )
                .forEach(
                    function (button) {

                        button.classList.remove(
                            "selected"
                        );
                    }
                );


            button.classList.add(
                "selected"
            );


            modal.classList.add(
                "is-open"
            );


            modal.setAttribute(
                "aria-hidden",
                "false"
            );


            setTimeout(
                function () {

                    if (notesInput) {

                        notesInput.focus();
                    }

                },
                50
            );
        }


        /* -----------------------------------------------------
           CLOSE MODAL
        ----------------------------------------------------- */

        function closeModal() {

            modal.classList.remove(
                "is-open"
            );


            modal.setAttribute(
                "aria-hidden",
                "true"
            );


            if (selectedButton) {

                selectedButton.classList.remove(
                    "selected"
                );
            }


            selectedRecommendationId =
                null;


            selectedOutcome =
                null;


            selectedButton =
                null;


            clearMessages();


            if (submitButton) {

                submitButton.disabled =
                    false;

                submitButton.textContent =
                    "ثبت نتیجه جلسه";
            }
        }


        /* -----------------------------------------------------
           OUTCOME BUTTONS
        ----------------------------------------------------- */

        document
            .querySelectorAll(
                ".outcome-btn"
            )
            .forEach(
                function (button) {

                    button.addEventListener(
                        "click",
                        function () {

                            /*
                             * اطلاعات محصول را از کارت
                             * Recommendation می‌گیریم.
                             */

                            const card =
                                button.closest(
                                    ".recommendation-outcome-card"
                                );


                            if (card) {

                                if (
                                    !button.dataset.productName
                                ) {

                                    const productName =
                                        card.querySelector(
                                            ".recommendation-product-name"
                                        );


                                    if (productName) {

                                        button.dataset.productName =
                                            productName.textContent.trim();
                                    }
                                }


                                if (
                                    !button.dataset.productCode
                                ) {

                                    button.dataset.productCode =
                                        card.dataset.productCode ||
                                        "";
                                }
                            }


                            openModal(
                                button
                            );
                        }
                    );
                }
            );


        if (closeButton) {

            closeButton.addEventListener(
                "click",
                closeModal
            );
        }


        if (cancelButton) {

            cancelButton.addEventListener(
                "click",
                closeModal
            );
        }


        modal.addEventListener(
            "click",
            function (event) {

                if (
                    event.target === modal
                ) {

                    closeModal();
                }
            }
        );


        document.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Escape" &&
                    modal.classList.contains(
                        "is-open"
                    )
                ) {

                    closeModal();
                }
            }
        );


        /* -----------------------------------------------------
           SUBMIT OUTCOME
        ----------------------------------------------------- */

        form.addEventListener(
            "submit",
            async function (event) {

                event.preventDefault();

                clearMessages();


                if (!visitId) {

                    if (errorBox) {

                        errorBox.textContent =
                            "برای این مشتری جلسه فعالی ثبت نشده است.";

                        errorBox.style.display =
                            "block";
                    }

                    return;
                }


                if (
                    !selectedRecommendationId ||
                    !selectedOutcome
                ) {

                    if (errorBox) {

                        errorBox.textContent =
                            "محصول و نتیجه جلسه باید انتخاب شوند.";

                        errorBox.style.display =
                            "block";
                    }

                    return;
                }


                const quantity =
                    Number(
                        quantityInput?.value || 0
                    );


                const salesAmount =
                    Number(
                        salesAmountInput?.value || 0
                    );


                if (
                    quantity < 0 ||
                    salesAmount < 0
                ) {

                    if (errorBox) {

                        errorBox.textContent =
                            "تعداد و مبلغ فروش نمی‌توانند منفی باشند.";

                        errorBox.style.display =
                            "block";
                    }

                    return;
                }


                const payload = {

                    visit_id:
                        Number(visitId),

                    recommendation_id:
                        Number(
                            selectedRecommendationId
                        ),

                    outcome:
                        selectedOutcome,

                    quantity:
                        quantity,

                    sales_amount:
                        salesAmount,

                    notes:
                        notesInput
                            ? notesInput.value.trim()
                            : ""
                };


                if (submitButton) {

                    submitButton.disabled =
                        true;

                    submitButton.textContent =
                        "در حال ثبت...";
                }


                try {

                    const response =
                        await fetch(
                            "/api/visits/v1/outcomes/",
                            {
                                method: "POST",

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
                                    JSON.stringify(
                                        payload
                                    )
                            }
                        );


                    const data =
                        await response.json();


                    if (!response.ok) {

                        throw new Error(
                            data.detail ||
                            data.error ||
                            "ثبت نتیجه جلسه ناموفق بود."
                        );
                    }


                    if (successBox) {

                        successBox.textContent =
                            "✓ نتیجه جلسه با موفقیت ثبت شد.";

                        successBox.style.display =
                            "block";
                    }


                    if (submitButton) {

                        submitButton.textContent =
                            "ثبت شد";
                    }


                    /*
                     * وضعیت همان Recommendation
                     * را بلافاصله روی کارت تغییر می‌دهیم.
                     */

                    updateRecommendationStatus(
                        selectedRecommendationId,
                        selectedOutcome,
                        data.sales_outcome
                            ?.quantity ??
                            quantity,
                        data.sales_outcome
                            ?.sales_amount ??
                            salesAmount
                    );


                    /*
                     * تاریخچه را از Backend دوباره می‌خوانیم.
                     */

                    await loadSalesHistory();


                    setTimeout(
                        closeModal,
                        900
                    );


                }
                catch (error) {

                    if (errorBox) {

                        errorBox.textContent =
                            error.message ||
                            "خطایی در ثبت نتیجه رخ داد.";

                        errorBox.style.display =
                            "block";
                    }


                    if (submitButton) {

                        submitButton.disabled =
                            false;

                        submitButton.textContent =
                            "ثبت نتیجه جلسه";
                    }
                }
            }
        );


        /* -----------------------------------------------------
           MODAL STATUS
        ----------------------------------------------------- */

        function updateModalStatus(
            data
        ) {

            if (!statusBox) {
                return;
            }


            const outcome =
                data.sales_outcome &&
                data.sales_outcome.outcome
                    ? data.sales_outcome.outcome
                    : selectedOutcome;


            const quantity =
                data.sales_outcome &&
                data.sales_outcome.quantity !== undefined
                    ? data.sales_outcome.quantity
                    : Number(
                        quantityInput?.value || 0
                    );


            const amount =
                data.sales_outcome &&
                data.sales_outcome.sales_amount !== undefined
                    ? data.sales_outcome.sales_amount
                    : Number(
                        salesAmountInput?.value || 0
                    );


            statusBox.innerHTML =
                "<strong>آخرین نتیجه:</strong> " +
                (
                    outcomeLabels[outcome] ||
                    outcome
                ) +
                "<br><small>تعداد: " +
                formatNumber(quantity) +
                " · مبلغ فروش: " +
                formatMoney(amount) +
                "</small>";
        }
    }


    /* =========================================================
       STAGE 8
       SALES HISTORY + RECOMMENDATION FEEDBACK
    ========================================================= */

    const historyList =
        document.getElementById(
            "salesHistoryList"
        );


    const loadingBox =
        document.getElementById(
            "salesHistoryLoading"
        );


    const errorBox =
        document.getElementById(
            "salesHistoryError"
        );


    const emptyBox =
        document.getElementById(
            "salesHistoryEmpty"
        );


    const refreshButton =
        document.getElementById(
            "refreshSalesHistory"
        );


    const totalBox =
        document.getElementById(
            "feedbackTotal"
        );


    const purchasedBox =
        document.getElementById(
            "feedbackPurchased"
        );


    const interestedBox =
        document.getElementById(
            "feedbackInterested"
        );


    const revenueBox =
        document.getElementById(
            "feedbackRevenue"
        );


    const conversionBox =
        document.getElementById(
            "feedbackConversion"
        );


    const progressBar =
        document.getElementById(
            "feedbackProgressBar"
        );


    const countBox =
        document.getElementById(
            "salesHistoryCount"
        );


    const updatedBox =
        document.getElementById(
            "salesHistoryUpdated"
        );


    /* =========================================================
       RENDER HISTORY
    ========================================================= */

    function renderHistory(
        items
    ) {

        if (!historyList) {
            return;
        }


        historyList.innerHTML =
            "";


        if (!Array.isArray(items) ||
            !items.length) {

            if (emptyBox) {

                emptyBox.style.display =
                    "block";
            }

            return;
        }


        if (emptyBox) {

            emptyBox.style.display =
                "none";
        }


        items.forEach(
            function (item, index) {

                const outcome =
                    item.outcome || "";


                const type =
                    item.recommendation &&
                    item.recommendation.type
                        ? item.recommendation.type
                        : "";


                const quantity =
                    Number(
                        item.quantity || 0
                    );


                const amount =
                    Number(
                        item.sales_amount || 0
                    );


                const row =
                    document.createElement(
                        "div"
                    );


                row.className =
                    "history-row";


                const productName =
                    item.product?.name ||
                    "—";


                const productCode =
                    item.product?.code ||
                    "";


                const category =
                    item.product?.category ||
                    "";


                row.innerHTML = `

                    <div class="history-rank">
                        ${formatNumber(index + 1)}
                    </div>

                    <div class="history-product">

                        <div
                            class="history-product-name"
                            title="${escapeHtml(productName)}"
                        >
                            ${escapeHtml(productName)}
                        </div>

                        <div class="history-product-code">
                            ${escapeHtml(productCode)}
                            ${category ? " · " : ""}
                            ${escapeHtml(category)}
                        </div>

                    </div>

                    <div class="history-type">
                        ${escapeHtml(
                            recommendationLabels[type] ||
                            type ||
                            "پیشنهاد"
                        )}
                    </div>

                    <div class="history-date">
                        ${formatDate(item.visit_date)}
                    </div>

                    <div class="history-amount">

                        ${
                            amount > 0
                                ? formatMoney(amount)
                                : "—"
                        }

                        ${
                            quantity > 0
                                ? ` · ×${formatNumber(quantity)}`
                                : ""
                        }

                    </div>

                    <div>

                        <span
                            class="history-result ${resultClass(outcome)}"
                        >
                            ${escapeHtml(
                                outcomeLabels[outcome] ||
                                outcome ||
                                "—"
                            )}
                        </span>

                    </div>
                `;


                historyList.appendChild(
                    row
                );
            }
        );
    }


    /* =========================================================
       UPDATE FEEDBACK METRICS
    ========================================================= */

    function updateFeedback(
        items
    ) {

        const safeItems =
            Array.isArray(items)
                ? items
                : [];


        const total =
            safeItems.length;


        const purchased =
            safeItems.filter(
                function (item) {

                    return item.outcome ===
                        "PURCHASED";
                }
            ).length;


        const interested =
            safeItems.filter(
                function (item) {

                    return item.outcome ===
                        "INTERESTED";
                }
            ).length;


        const revenue =
            safeItems.reduce(
                function (sum, item) {

                    return (
                        sum +
                        Number(
                            item.sales_amount || 0
                        )
                    );
                },
                0
            );


        const conversion =
            total
                ? (
                    purchased /
                    total
                ) * 100
                : 0;


        if (totalBox) {

            totalBox.textContent =
                formatNumber(total);
        }


        if (purchasedBox) {

            purchasedBox.textContent =
                formatNumber(purchased);
        }


        if (interestedBox) {

            interestedBox.textContent =
                formatNumber(interested);
        }


        if (revenueBox) {

            revenueBox.textContent =
                formatMoney(revenue);
        }


        if (conversionBox) {

            conversionBox.textContent =
                `${conversion.toLocaleString(
                    "fa-IR",
                    {
                        maximumFractionDigits: 1
                    }
                )}%`;
        }


        if (progressBar) {

            progressBar.style.width =
                `${Math.min(
                    100,
                    conversion
                )}%`;
        }


        if (countBox) {

            countBox.textContent =
                `${formatNumber(total)} تعامل ثبت شده`;
        }


        if (updatedBox) {

            updatedBox.textContent =
                new Intl.DateTimeFormat(
                    "fa-IR",
                    {
                        hour: "2-digit",
                        minute: "2-digit"
                    }
                ).format(
                    new Date()
                );
        }
    }


    /* =========================================================
       LOAD SALES HISTORY
    ========================================================= */

    async function loadSalesHistory() {

        if (
            !historyList ||
            !customerCode
        ) {

            return;
        }


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


        if (emptyBox) {

            emptyBox.style.display =
                "none";
        }


        try {

            const url =
                `/api/visits/v1/customers/${encodeURIComponent(
                    customerCode
                )}/sales-outcomes/`;


            console.log(
                "Sales history API:",
                url
            );


            const response =
                await fetch(
                    url,
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


            console.log(
                "Sales history HTTP status:",
                response.status
            );


            const data =
                await response.json();


            console.log(
                "Sales history API response:",
                data
            );


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    data.error ||
                    "دریافت تاریخچه فروش ناموفق بود."
                );
            }


            const items =
                Array.isArray(
                    data.sales_outcomes
                )
                    ? data.sales_outcomes
                    : [];


            renderHistory(
                items
            );


            updateFeedback(
                items
            );


            /*
             * وضعیت فعلی هر Recommendation
             * از آخرین Outcome آن تعیین می‌شود.
             */

            restoreRecommendationStatuses(
                items
            );


            console.log(
                "Sales history rendered successfully."
            );


        }
        catch (error) {

            console.error(
                "Sales history error:",
                error
            );


            if (historyList) {

                historyList.innerHTML =
                    "";
            }


            if (errorBox) {

                errorBox.textContent =
                    error.message ||
                    "خطا در دریافت تاریخچه فروش";

                errorBox.style.display =
                    "block";
            }


        }
        finally {

            console.log(
                "Sales history loading finished."
            );


            if (loadingBox) {

                loadingBox.style.display =
                    "none";
            }
        }
    }


    /* =========================================================
       REFRESH BUTTON
    ========================================================= */

    if (refreshButton) {

        refreshButton.addEventListener(
            "click",
            function () {

                loadSalesHistory();
            }
        );
    }


    /* =========================================================
       INITIAL LOAD
    ========================================================= */

    loadSalesHistory();


})();