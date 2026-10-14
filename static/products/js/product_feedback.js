/* Product Hero reuses Guided feedback commands; bootstrap reads never mutate. */
(() => {
    'use strict';
    const root = document.getElementById('productFeedback');
    if (!root || !window.GuidedFeedback) return;
    const status = document.getElementById('productFeedbackStatus');
    const selection = document.getElementById('productSelection');
    const actions = root.querySelector('[data-feedback-actions]');
    let summaryBeforeSelection = 'ثبت بازخورد';
    const id = value => /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value));
    async function read(path) {
        const url = new URL(path, window.location.origin);
        if (url.origin !== window.location.origin) throw Error('Invalid endpoint');
        const response = await fetch(url.pathname + url.search, {method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
        if (!response.ok) throw Error('Read denied');
        const body = await response.json();
        if (body.version !== 1 || body.customer?.code !== root.dataset.customerCode || String(body.visit?.id) !== root.dataset.visitId) throw Error('Invalid context');
        return body;
    }
    async function refreshSelection() {
        window.GuidedFeedback.setBasket(null, true);
        try {
            const basket = await read(`/api/sales-requests/v1/visits/${root.dataset.visitId}/basket/?${new URLSearchParams({customer_code: root.dataset.customerCode})}`);
            if (!Array.isArray(basket.lines) || typeof basket.editable !== 'boolean' || (basket.request && (!Number.isSafeInteger(basket.request.revision) || !['DRAFT','SUBMITTED'].includes(basket.request.status)))) throw Error('Invalid basket');
            const selected = basket.lines.find(row => row.product_id === Number(root.dataset.productId));
            const inDraft = Boolean(selected && basket.request?.status === 'DRAFT');
            const wasSelected = root.dataset.selected === 'true';
            root.dataset.selected = selected ? 'true' : 'false';
            selection.hidden = !selected;
            selection.textContent = selected ? inDraft ? 'در درخواست فروش' : 'در درخواست ثبت‌شده' : '';
            window.GuidedFeedback.setBasket(basket, false);
            if (selected) {
                status.textContent = inDraft ? 'برای ثبت تصمیم تازه، ابتدا محصول را از درخواست فروش حذف کنید.' : 'درخواست ثبت‌شده قابل تغییر نیست.';
                const summary = root.querySelector('[data-feedback-summary]');
                if (summary) {
                    if (!wasSelected) summaryBeforeSelection = summary.textContent;
                    summary.textContent = 'سوابق بازخورد';
                    summary.setAttribute('aria-label', 'مشاهده سوابق بازخورد؛ وضعیت فعلی محصول در درخواست جداگانه نمایش داده می‌شود.');
                    root.querySelector('[data-feedback-options]').hidden = true;
                    document.getElementById('productFeedbackEmptyHistory').hidden = !root.querySelector('[data-feedback-history-list]').hidden;
                }
            } else {
                const summary = root.querySelector('[data-feedback-summary]');
                if (wasSelected && summary) {
                    summary.textContent = summaryBeforeSelection;
                    summary.setAttribute('aria-label', `${summaryBeforeSelection} · مشاهده سوابق و جزئیات`);
                    document.getElementById('productFeedbackEmptyHistory').hidden = true;
                }
                if (root.dataset.recommendationId) status.textContent = basket.visit.status === 'IN_PROGRESS' ? 'بازخورد پس از تأیید سرور ثبت می‌شود؛ سوابق قبلی محفوظ می‌مانند.' : 'ثبت بازخورد فقط در ویزیت در حال انجام امکان‌پذیر است.';
            }
        } catch (_) {
            // Selection uncertainty never enables a fresh decision.
            window.GuidedFeedback.setBasket(null, true);
            status.textContent = 'اطلاعات درخواست در دسترس نیست؛ صفحه را تازه کنید.';
        }
    }
    window.ProductFeedback = {refreshSelection};
    async function init() {
        window.GuidedFeedback.setBasket(null, true);
        if (!id(root.dataset.visitId)) {
            if (root.dataset.recommendationId) status.textContent = 'ثبت بازخورد نیاز به ویزیت معتبر دارد.';
            return;
        }
        // Keep explicit recovery of an existing command possible even when the
        // current catalog has changed. Fresh controls remain disabled until reads succeed.
        await window.GuidedFeedback.load({apiUrl: root.dataset.feedbackUrl, catalogContext: ''}, []);
        try {
            let token = '', recommendationId = Number(root.dataset.recommendationId) || null;
            if (['IN_PROGRESS', 'PLANNED'].includes(root.dataset.visitStatus)) {
                const query = new URLSearchParams({customer_code: root.dataset.customerCode, visit_id: root.dataset.visitId, q: root.dataset.productCode});
                const saved = new URLSearchParams(window.location.search).get('catalog_context');
                if (saved) query.set('catalog_context', saved);
                if (root.dataset.catalogUrl !== '/api/products/v1/catalog/') throw Error('Invalid catalog endpoint');
                const catalog = await read(`${root.dataset.catalogUrl}?${query}`);
                if (!Array.isArray(catalog.items) || typeof catalog.catalog_context !== 'string' || !catalog.catalog_context) throw Error('Invalid catalog');
                const product = catalog.items.find(row => row.product_id === Number(root.dataset.productId));
                if (!product) throw Error('Product absent');
                const savedId = product.is_prioritized ? product.recommendation?.id : null;
                if (savedId !== recommendationId) throw Error('Recommendation context changed');
                token = catalog.catalog_context;
            }
            if (recommendationId) {
                await window.GuidedFeedback.load({apiUrl: root.dataset.feedbackUrl, catalogContext: token}, [{mount: root, productId: Number(root.dataset.productId), recommendationId, name: root.dataset.productName}]);
            } else {
                actions.remove();
                status.textContent = 'این محصول بدون اولویت ویژه است؛ بازخورد پیشنهاد برای آن ثبت نمی‌شود.';
            }
            if (recommendationId) status.textContent = root.dataset.visitStatus === 'IN_PROGRESS' ? 'بازخورد پس از تأیید سرور ثبت می‌شود؛ سوابق قبلی محفوظ می‌مانند.' : 'ثبت بازخورد فقط در ویزیت در حال انجام امکان‌پذیر است.';
            await refreshSelection();
        } catch (_) {
            // Selection/context uncertainty never enables a fresh decision.
            window.GuidedFeedback.setBasket(null, true);
            status.textContent = 'زمینه پیشنهاد یا درخواست در دسترس نیست؛ صفحه را تازه کنید یا به فروش هوشمند بازگردید.';
        }
    }
    init();
})();
