/* Canonical performance is server-rendered. Only localize existing numbers. */
(function () {
    "use strict";
    const formatter = new Intl.NumberFormat("fa-IR", {maximumFractionDigits: 2});
    document.querySelectorAll(".recommendation-workspace .manager-number[data-value]").forEach(element => {
        const value = Number(element.dataset.value);
        if (Number.isFinite(value)) element.textContent = formatter.format(value);
    });
}());
