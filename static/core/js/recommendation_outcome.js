/* Current visit results are backend resolved. No business formulas or POST retries. */
(function () {
    "use strict";
    const root = document.getElementById("workspace-recommendations");
    if (!root) return;
    const region = document.getElementById("visitOutcomeRegion");
    const byId = id => document.getElementById(id);
    const labels = {PURCHASED: "خرید شد", INTERESTED: "علاقه‌مند شد", FOLLOW_UP: "نیاز به پیگیری",
        REJECTED: "رد شد", NOT_PRESENTED: "مطرح نشد"};
    const formatter = new Intl.NumberFormat("fa-IR", {maximumFractionDigits: 2});
    const number = value => value === null || value === undefined || !Number.isFinite(Number(value)) ? "—" : formatter.format(Number(value));
    const cards = Array.from(root.querySelectorAll(".recommendation-outcome-card"));
    const buttons = Array.from(root.querySelectorAll(".outcome-btn"));
    const records = new Map();
    let ready = false, canRecord = false, visit = null, revision = 0;
    let pending = false, selected = null, returnFocus = null;
    const modal = byId("outcomeModal"), form = byId("outcomeForm"), submit = byId("outcomeSubmit");

    function focusRecommendation() {
        if (!/^#recommendation-\d+$/.test(location.hash)) return;
        const card = cards.find(item => "#" + item.id === location.hash);
        if (!card) return;
        let ancestor = card.parentElement;
        while (ancestor) {
            if (ancestor.tagName === "DETAILS") ancestor.open = true;
            ancestor = ancestor.parentElement;
        }
        const details = card.querySelector("details");
        if (details && root.dataset.guided !== "true") details.open = true;
        card.focus({preventScroll: true});
        card.scrollIntoView({block: "start"});
    }
    focusRecommendation();
    window.addEventListener("hashchange", focusRecommendation);
    // Manager inspection has no operational region/form and makes no visit reads.
    if (!region) return;

    function controls() {
        buttons.forEach(button => { button.disabled = !ready || !canRecord || pending || button.dataset.unavailable === "true"; });
    }
    function resultText(result) {
        if (!result) return root.dataset.guided === "true" ? "هنوز ثبت نشده" : "هنوز در این ویزیت نتیجه‌ای ثبت نشده است.";
        let text = labels[result.final_outcome] || "نتیجه ثبت‌شده";
        if (result.final_outcome === "PURCHASED") {
            text += " · تعداد " + number(result.quantity) + " · مبلغ ثبت‌شده " + number(result.sales_amount);
        }
        return text;
    }
    function readMessage(state, text) {
        const node = byId("visitOutcomeReadStatus");
        node.textContent = text;
        node.className = "ds-state" + (state === "error" ? " ds-state--error" :
            state === "loading" ? " ds-state--loading" : state === "empty" ? " ds-state--empty" : "");
        region.dataset.state = state;
        region.setAttribute("aria-busy", String(state === "loading"));
    }
    function cardStates(message) {
        cards.forEach(card => {
            const box = card.querySelector(".recommendation-outcome-status");
            if (!box) return;
            const result = records.get(card.dataset.recommendationId);
            box.querySelector(".status-value").textContent = message || resultText(result);
            box.dataset.outcome = ready && result ? result.final_outcome : "";
        });
    }
    async function read() {
        if (!region.dataset.readUrl) { controls(); return false; }
        const version = ++revision;
        ready = false;
        controls();
        readMessage("loading", "در حال دریافت نتیجه‌های همین ویزیت…");
        cardStates("در حال دریافت نتیجه همین ویزیت…");
        try {
            const response = await fetch(region.dataset.readUrl, {method: "GET", credentials: "same-origin",
                cache: "no-store", headers: {Accept: "application/json"}});
            if (!response.ok) throw new Error(response.status === 403 || response.status === 404 ?
                "زمینه ویزیت در دسترس نیست یا دسترسی شما تغییر کرده است." : "دریافت نتیجه ویزیت ناموفق بود. دوباره دریافت کنید.");
            const data = await response.json();
            if (!data.visit || String(data.visit.id) !== region.dataset.visitId ||
                data.visit.customer_code !== region.dataset.customerCode || !Array.isArray(data.recommendation_outcomes)) {
                throw new Error("پاسخ نتیجه ویزیت معتبر نیست.");
            }
            if (version !== revision) return false;
            visit = data.visit;
            records.clear();
            data.recommendation_outcomes.forEach(item => records.set(String(item.recommendation_id), item));
            ready = true;
            canRecord = data.can_record === true;
            readMessage(records.size ? "ready" : "empty", records.size ?
                "نتیجه‌های همین ویزیت دریافت شد؛ تاریخچه دیگر ویزیت‌ها جداگانه نمایش داده می‌شود." :
                "هنوز برای پیشنهادهای این ویزیت نتیجه‌ای ثبت نشده است.");
            cardStates();
            return true;
        } catch (error) {
            if (version !== revision) return false;
            records.clear();
            canRecord = false;
            readMessage("error", error instanceof SyntaxError || error instanceof TypeError ?
                "دریافت نتیجه ویزیت ناموفق بود. دوباره دریافت کنید." : error.message);
            cardStates("نتیجه این ویزیت در دسترس نیست.");
            return false;
        } finally {
            if (version === revision) controls();
        }
    }
    byId("visitOutcomeRefresh").addEventListener("click", read);
    document.addEventListener("sales-visit-state-changed", () => { Promise.resolve().then(read); });
    window.addEventListener("pageshow", event => { if (event.persisted) read(); });
    read();
    if (!modal || !form) return;

    function message(id, text) {
        const node = byId(id);
        node.textContent = text;
        node.hidden = !text;
    }
    function close() {
        if (pending) return;
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        modal.classList.remove("is-open");
        document.body.classList.remove("ri-dialog-open");
        selected = null;
        if (returnFocus) returnFocus.focus();
    }
    function open(button) {
        if (!ready || !canRecord || pending) return;
        const card = button.closest(".recommendation-outcome-card");
        if (!card || !labels[button.dataset.outcome]) return;
        selected = {id: card.dataset.recommendationId, outcome: button.dataset.outcome};
        returnFocus = button;
        form.reset();
        byId("outcomeQuantity").value = "0";
        byId("outcomeSalesAmount").value = "0";
        byId("outcomeModalProduct").textContent = card.querySelector(".recommendation-product-name").textContent.trim() + " · " + card.dataset.productCode;
        byId("outcomeModalOutcome").textContent = labels[selected.outcome];
        byId("outcomeModalVisit").textContent = "ویزیت " + number(visit.id) + " · " + visit.visit_date + " · در حال انجام";
        byId("outcomeModalCurrent").textContent = "نتیجه فعلی همین ویزیت: " + resultText(records.get(selected.id));
        modal.querySelector(".ri-value-fields").hidden = selected.outcome !== "PURCHASED";
        byId("outcomeFollowUpDateGroup").hidden = selected.outcome !== "FOLLOW_UP";
        byId("outcomeFollowUpDate").required = selected.outcome === "FOLLOW_UP";
        message("outcomeError", ""); message("outcomeSuccess", "");
        delete submit.dataset.saved;
        submit.disabled = false; submit.textContent = "ثبت نتیجه تعامل";
        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        modal.classList.add("is-open");
        document.body.classList.add("ri-dialog-open");
        (selected.outcome === "FOLLOW_UP" ? byId("outcomeFollowUpDate") :
            selected.outcome === "PURCHASED" ? byId("outcomeQuantity") : byId("outcomeNotes")).focus();
    }
    buttons.forEach(button => button.addEventListener("click", () => open(button)));
    byId("outcomeModalClose").addEventListener("click", close);
    byId("outcomeCancel").addEventListener("click", close);
    modal.addEventListener("click", event => { if (event.target === modal) close(); });
    modal.addEventListener("keydown", event => {
        if (event.key === "Escape") { event.preventDefault(); close(); }
        if (event.key !== "Tab") return;
        const focusable = Array.from(modal.querySelectorAll("button, input, textarea"))
            .filter(node => !node.disabled && node.type !== "hidden" && node.getClientRects().length);
        if (!focusable.length) { event.preventDefault(); return; }
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (pending || submit.dataset.saved === "true" || !selected || !ready || !canRecord) return;
        message("outcomeError", ""); message("outcomeSuccess", "");
        if (!form.checkValidity()) { form.reportValidity(); return; }
        const quantity = Number(byId("outcomeQuantity").value || 0);
        const amount = Number(byId("outcomeSalesAmount").value || 0);
        if (!Number.isFinite(quantity) || !Number.isFinite(amount) || quantity < 0 || amount < 0) {
            message("outcomeError", "تعداد و مبلغ واردشده معتبر نیستند."); return;
        }
        const selection = {...selected};
        pending = true;
        controls();
        const fields = ["outcomeQuantity", "outcomeSalesAmount", "outcomeFollowUpDate", "outcomeNotes"].map(byId);
        fields.forEach(field => { field.disabled = true; });
        submit.disabled = true; submit.textContent = "در حال ثبت…";
        form.setAttribute("aria-busy", "true");
        try {
            // A GET preflight is safe to retry manually; the POST is never retried.
            if (!await read() || !canRecord) {
                message("outcomeError", "ویزیت یا دسترسی فعلی اجازه ثبت نتیجه نمی‌دهد؛ نتیجه‌ای ارسال نشد."); return;
            }
            const token = form.querySelector("[name=csrfmiddlewaretoken]").value;
            const response = await fetch("/api/visits/v1/outcomes/", {method: "POST", credentials: "same-origin",
                headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": token},
                body: JSON.stringify({visit_id: visit.id, customer_code: region.dataset.customerCode,
                    recommendation_id: Number(selection.id), outcome: selection.outcome,
                    quantity, sales_amount: amount, notes: byId("outcomeNotes").value.trim(),
                    follow_up_date: selection.outcome === "FOLLOW_UP" ? byId("outcomeFollowUpDate").value : null})});
            const data = await response.json();
            if (!response.ok || data.success !== true) {
                message("outcomeError", response.status === 403 || response.status === 404 ?
                    "ویزیت یا پیشنهاد در دسترس نیست یا امکان ثبت نتیجه پایان یافته است." :
                    response.status === 400 ? "اطلاعات نتیجه معتبر نیست؛ مقادیر و تاریخ پیگیری را بررسی کنید." :
                    "ثبت نتیجه تأیید نشد؛ نتیجه فعلی را پیش از ارسال دوباره بررسی کنید.");
                return;
            }
            // Never display the raw POST event as the resolved current result.
            const refreshed = await read();
            message("outcomeSuccess", "نتیجه تعامل ثبت شد؛ سفارش یا فاکتوری ایجاد نشده است.");
            if (!refreshed) message("outcomeError", "ثبت انجام شد، اما دریافت نتیجه نهایی ناموفق بود؛ دوباره نتیجه را دریافت کنید.");
            else byId("outcomeModalCurrent").textContent = "نتیجه فعلی همین ویزیت: " + resultText(records.get(selection.id));
            submit.textContent = "ثبت شد";
            submit.dataset.saved = "true";
            document.dispatchEvent(new CustomEvent("recommendation-outcome-saved"));
        } catch (_) {
            message("outcomeError", "وضعیت ثبت نتیجه تأیید نشد. ارسال خودکار تکرار نمی‌شود؛ پیش از ثبت دوباره نتیجه همین ویزیت را دریافت کنید.");
            await read();
        } finally {
            pending = false;
            fields.forEach(field => { field.disabled = false; });
            form.setAttribute("aria-busy", "false");
            submit.disabled = submit.dataset.saved === "true";
            if (!submit.disabled) submit.textContent = "ثبت نتیجه تعامل";
            controls();
        }
    });
})();
