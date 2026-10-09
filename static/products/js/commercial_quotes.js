/* Server-authoritative read-only quotes. Formatting only: no price arithmetic. */
(() => {
    'use strict';
    const field = (mount, name) => mount.querySelector(`[data-quote-${name}]`);
    const money = value => {
        if (typeof value !== 'string' || !/^(0|[1-9]\d*)$/.test(value)) throw new Error('Invalid amount');
        return new Intl.NumberFormat('fa-IR').format(BigInt(value));
    };
    const reasons = {
        INVENTORY_UNKNOWN: 'موجودی نامشخص؛ فعلاً قابل افزودن نیست.',
        OUT_OF_STOCK: 'ناموجود؛ فعلاً قابل افزودن نیست.',
        INSUFFICIENT_STOCK: 'موجودی برای تعداد درخواستی کافی نیست.',
        PRICE_UNAVAILABLE: 'قیمت فعلی در دسترس نیست؛ فعلاً قابل افزودن نیست.',
        PRICE_CONFIGURATION_ERROR: 'قیمت قابل استفاده نیست؛ فعلاً قابل افزودن نیست.',
        VISIT_NOT_ACTIVE: 'فقط مشاهده؛ ویزیت هنوز شروع نشده است.',
    };
    function pending(mount) {
        const region = mount.querySelector('[data-commercial-quote]');
        region.setAttribute('aria-busy', 'true');
        region.dataset.state = 'LOADING';
        for (const name of ['base-row', 'discount-row', 'currency', 'demo']) field(mount, name).hidden = true;
        field(mount, 'final').textContent = 'در حال دریافت قیمت…';
        field(mount, 'availability').textContent = '';
    }
    function failed(mount, terminal = false) {
        pending(mount);
        const region = mount.querySelector('[data-commercial-quote]');
        region.setAttribute('aria-busy', 'false'); region.dataset.state = 'ERROR';
        field(mount, 'final').textContent = terminal ? 'قیمت این ویزیت در دسترس نیست؛ زمینه ویزیت را بررسی کنید.' : 'دریافت قیمت انجام نشد؛ صفحه را تازه کنید.';
    }
    function display(mount, item) {
        const region = mount.querySelector('[data-commercial-quote]'), price = item.pricing;
        let formatted;
        if (price.state === 'AVAILABLE') {
            const quote = price.quote;
            if (!quote || quote.currency !== 'TOMAN') throw new Error('Invalid quote');
            formatted = {
                base: money(quote.base_unit_price), discount: money(quote.discount_percentage),
                saving: money(quote.unit_discount), final: money(quote.final_unit_price),
            };
        } else if (!['UNAVAILABLE', 'CONFIGURATION_ERROR'].includes(price.state) || price.quote !== null) throw new Error('Invalid unavailable quote');
        pending(mount);
        region.dataset.state = price.state;
        if (formatted) {
            for (const name of ['base', 'discount', 'saving', 'final']) field(mount, name).textContent = formatted[name];
            for (const name of ['base-row', 'discount-row', 'currency', 'demo']) field(mount, name).hidden = false;
        } else field(mount, 'final').textContent = price.state === 'CONFIGURATION_ERROR' ? 'قیمت فعلی قابل استفاده نیست' : 'قیمت فعلی در دسترس نیست';
        const inventory = item.inventory;
        field(mount, 'stock').textContent = inventory.state === 'AVAILABLE' ? `موجودی قابل فروش: ${new Intl.NumberFormat('fa-IR').format(inventory.sellable_quantity)}` : inventory.state === 'UNAVAILABLE' ? 'ناموجود · فعلاً قابل افزودن نیست' : 'موجودی نامشخص · فعلاً قابل افزودن نیست';
        field(mount, 'stock').classList?.toggle('gc-stock--available', inventory.state === 'AVAILABLE');
        field(mount, 'stock').classList?.toggle('gc-stock--unavailable', inventory.state === 'UNAVAILABLE');
        field(mount, 'availability').textContent = item.can_add ? '' : (reasons[item.non_addable_reason] || 'فعلاً قابل افزودن نیست.');
        region.setAttribute('aria-busy', 'false');
    }
    async function load(context, targets, {signal, isCurrent = () => true} = {}) {
        if (!targets.length) return;
        for (const {mount} of targets) pending(mount);
        try {
            const endpoint = new URL(context.apiUrl, window.location.origin);
            if (endpoint.origin !== window.location.origin || endpoint.pathname !== `/api/sales-requests/v1/visits/${context.visitId}/quote/`) throw new Error('Invalid endpoint');
            // Catalog pages may contain 100 items; the API permits at most 50 per batch.
            const items = [];
            for (let start = 0; start < targets.length; start += 50) {
                const batch = targets.slice(start, start + 50);
                endpoint.search = new URLSearchParams({customer_code: context.customerCode,
                    items: JSON.stringify(batch.map(target => ({product_id: target.productId, quantity: 1}))),
                }).toString();
                const response = await fetch(endpoint.pathname + endpoint.search, {
                    method: 'GET', credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store', signal,
                });
                if (!isCurrent()) return;
                if (!response.ok) {
                    const error = new Error('Quote unavailable'); error.terminal = [400, 401, 403, 404, 409].includes(response.status); throw error;
                }
                const data = await response.json();
                if (!isCurrent()) return;
                if (data.version !== 1 || data.currency !== 'TOMAN' || data.customer?.code !== context.customerCode || String(data.visit?.id) !== String(context.visitId) || !Array.isArray(data.items) || data.items.length !== batch.length) throw new Error('Invalid context');
                const expected = new Set(batch.map(target => target.productId));
                for (const item of data.items) {
                    if (!expected.delete(item.product_id) || item.quantity !== 1 || !item.inventory || !item.pricing) throw new Error('Invalid product');
                    if (item.pricing.state === 'AVAILABLE' && (item.pricing.quote?.customer_id !== data.customer.id || item.pricing.quote?.product_id !== item.product_id || item.pricing.quote?.quantity !== 1)) throw new Error('Invalid quote identity');
                    items.push(item);
                }
            }
            if (!isCurrent() || signal?.aborted) return;
            const byProduct = new Map(items.map(item => [item.product_id, item]));
            for (const target of targets) display(target.mount, byProduct.get(target.productId));
        } catch (error) {
            if (!isCurrent() || signal?.aborted || error.name === 'AbortError') return;
            for (const {mount} of targets) failed(mount, error.terminal);
            // No automatic retry, persistent quote cache or mutation POST.
        }
    }
    window.CommercialQuotes = {load};
    for (const mount of document.querySelectorAll('[data-product-quote]')) {
        load({apiUrl: mount.dataset.quoteUrl, customerCode: mount.dataset.customerCode, visitId: mount.dataset.visitId},
            [{productId: Number(mount.dataset.productId), mount}]);
    }
})();
