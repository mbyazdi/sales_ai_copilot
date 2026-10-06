/* Confirmation-only completion POST; canonical GET resolves all ambiguous responses. */
(function () {
    "use strict";
    const root = document.getElementById("visitReview");
    if (!root) return;
    const byId = id => document.getElementById(id);
    const trigger = byId("finishVisitButton"), confirm = byId("confirmFinishVisit"), cancel = byId("cancelFinishVisit");
    const dialog = byId("finishVisitDialog"), refresh = byId("reviewRefresh");
    let pending = false, checking = false, ready = false, current = root.dataset.status, revision = 0;

    function controls() {
        trigger.disabled = pending || checking || !ready || current !== "IN_PROGRESS";
        confirm.disabled = pending || checking || !ready || current !== "IN_PROGRESS";
        cancel.disabled = pending;
        refresh.disabled = pending || checking;
        byId("finishPendingStatus").hidden = !pending;
        root.setAttribute("aria-busy", String(pending || checking));
    }
    function error(text) {
        ["reviewError", "finishDialogError"].forEach(id => { byId(id).textContent = text; byId(id).hidden = !text; });
    }
    function completed(fromSave = false) {
        current = "COMPLETED";
        root.dataset.status = current;
        byId("reviewVisitStatus").textContent = "تکمیل‌شده";
        byId("reviewPanel").hidden = true;
        byId("completionAcknowledgement").hidden = false;
        byId("completionTitle").textContent = fromSave ? "ویزیت با موفقیت پایان یافت" : "ویزیت پایان‌یافته است";
        if (dialog.open) dialog.close();
        controls();
    }
    async function readStatus() {
        const version = ++revision;
        checking = true; ready = false; controls();
        byId("reviewReadStatus").textContent = "در حال بررسی وضعیت فعلی ویزیت…";
        try {
            const response = await fetch(root.dataset.readUrl, {method: "GET", credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}});
            if (!response.ok) throw new Error(response.status === 403 || response.status === 404 ?
                "زمینه ویزیت در دسترس نیست یا دسترسی شما تغییر کرده است." : "دریافت وضعیت ویزیت ناموفق بود. دوباره دریافت کنید.");
            const data = await response.json();
            if (!data.visit || String(data.visit.id) !== root.dataset.visitId || data.visit.customer_code !== root.dataset.customerCode) throw new Error("پاسخ وضعیت ویزیت معتبر نیست.");
            if (version !== revision) return false;
            current = data.visit.status;
            byId("reviewVisitStatus").textContent = {IN_PROGRESS: "در حال انجام", PLANNED: "برنامه‌ریزی‌شده", COMPLETED: "تکمیل‌شده", CANCELLED: "لغوشده"}[current] || "وضعیت در دسترس نیست";
            ready = true;
            root.dataset.status = current;
            error(""); refresh.hidden = true;
            byId("reviewReadStatus").textContent = current === "IN_PROGRESS" ? "پایان نمایش پیشنهادها، ویزیت را تکمیل نکرده است." : "این ویزیت در حال انجام نیست؛ پایان ویزیت فعال نیست.";
            if (current === "COMPLETED") completed();
            return true;
        } catch (failure) {
            if (version !== revision) return false;
            error(failure instanceof TypeError || failure instanceof SyntaxError ? "دریافت وضعیت ویزیت ناموفق بود. دوباره دریافت کنید." : failure.message);
            refresh.hidden = false;
            byId("reviewReadStatus").textContent = "تا دریافت وضعیت معتبر، پایان ویزیت فعال نیست.";
            return false;
        } finally {
            if (version === revision) { checking = false; controls(); }
        }
    }
    trigger.addEventListener("click", () => {
        if (trigger.disabled) return;
        dialog.showModal(); cancel.focus();
    });
    cancel.addEventListener("click", () => { if (!pending) dialog.close(); });
    dialog.addEventListener("cancel", event => { if (pending) event.preventDefault(); });
    dialog.addEventListener("close", () => { if (current !== "COMPLETED") trigger.focus(); });
    refresh.addEventListener("click", readStatus);
    // Re-render all canonical counts/tasks when restoring an old review document.
    window.addEventListener("pageshow", event => { if (event.persisted) window.location.reload(); });
    confirm.addEventListener("click", async () => {
        if (!dialog.open || pending || checking || !ready || current !== "IN_PROGRESS") return;
        pending = true; controls(); error("");
        let confirmed = false;
        try {
            const token = byId("visitCompletionForm").querySelector("[name=csrfmiddlewaretoken]").value;
            const response = await fetch(root.dataset.completeUrl, {method: "POST", credentials: "same-origin",
                headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": token},
                body: JSON.stringify({customer_code: root.dataset.customerCode})});
            const data = await response.json();
            confirmed = response.ok && data.success === true && data.visit &&
                String(data.visit.id) === root.dataset.visitId && data.visit.status === "COMPLETED" &&
                data.visit.customer_code === root.dataset.customerCode;
        } catch (_) {
            // No retry: a dropped/malformed response may follow a successful write.
        }
        try {
            if (confirmed) completed(true);
            else {
                const read = await readStatus();
                if (read && current !== "COMPLETED") {
                    error("پایان ویزیت تأیید نشد. وضعیت فعلی دوباره دریافت شد؛ در صورت نیاز صریحاً دوباره تأیید کنید.");
                }
            }
        } finally {
            pending = false; controls();
        }
    });
    if (current === "COMPLETED") { ready = true; completed(); }
    else readStatus();
})();
