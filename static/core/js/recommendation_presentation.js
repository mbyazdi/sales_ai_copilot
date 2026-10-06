/* Navigation only. All target URLs/order/group transitions come from the server. */
(function () {
    "use strict";
    const dialog = document.getElementById("endPresentationDialog");
    if (!dialog) return;
    let origin;
    const requestEnd = button => {
        origin = button;
        dialog.showModal();
        document.getElementById("continuePresentation").focus();
    };
    document.getElementById("endAll").addEventListener("click", event => requestEnd(event.currentTarget));
    document.getElementById("endGroup").addEventListener("click", event => {
        const next = event.currentTarget.dataset.nextGroup;
        if (next) window.location.assign(next);
        else requestEnd(event.currentTarget);
    });
    document.getElementById("continuePresentation").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { if (origin) origin.focus(); });
    const image = document.querySelector("[data-product-image]");
    const fallback = () => {
        image.hidden = true;
        document.querySelector(".gs-image-fallback").hidden = false;
    };
    if (image) {
        image.addEventListener("error", fallback);
        if (image.complete && image.naturalWidth === 0) fallback();
    }
})();
