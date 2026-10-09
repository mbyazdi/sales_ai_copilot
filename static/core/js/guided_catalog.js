/* Presentation only. Catalog order, eligibility and detail destinations come from the API. */
(() => {
    'use strict';
    const root = document.getElementById('guidedCatalog');
    if (!root) return;
    const byId = id => document.getElementById(id);
    const form = byId('catalogFilters'), search = byId('catalogSearch');
    const category = byId('catalogCategory'), priority = byId('catalogPriority');
    const status = byId('catalogStatus'), results = byId('catalogResults');
    const errorBox = byId('catalogError'), retry = byId('catalogRetry');
    const previous = byId('catalogPrevious'), next = byId('catalogNext');
    const numeral = value => new Intl.NumberFormat('fa-IR').format(value);
    const allowed = ['q', 'category_id', 'priority', 'page', 'page_size', 'catalog_context', 'product_id', 'recommendation_id'];
    let params = readLocation(), requestVersion = 0, controller;
    function readLocation() {
        const source = new URLSearchParams(window.location.search), selected = new URLSearchParams();
        for (const key of allowed) if (source.has(key)) selected.set(key, source.get(key));
        return selected;
    }
    function localDetail(value) {
        const url = new URL(value, window.location.origin);
        if (url.origin !== window.location.origin || !url.pathname.startsWith('/products/')) throw new Error('Invalid destination');
        return url.pathname + url.search + url.hash;
    }
    function writeLocation(push) {
        const url = new URL(window.location.href);
        url.search = params.toString();
        url.searchParams.set('visit_id', root.dataset.visitId);
        window.history[push ? 'pushState' : 'replaceState'](null, '', url.pathname + url.search + url.hash);
    }
    function busy(value) {
        root.setAttribute('aria-busy', String(value));
        for (const element of form.querySelectorAll('input, select, button')) element.disabled = value;
        previous.disabled = true; next.disabled = true; retry.disabled = value;
    }
    function card(item) {
        const node = byId('catalogCardTemplate').content.firstElementChild.cloneNode(true);
        node.id = `catalog-product-${item.product_id}`;
        node.dataset.productId = String(item.product_id);
        if (item.recommendation) node.dataset.recommendationId = String(item.recommendation.id);
        node.classList.toggle('gc-card--priority', item.is_prioritized);
        const field = name => node.querySelector(`[data-${name}]`);
        field('name').id = `${node.id}-title`;
        node.setAttribute('aria-labelledby', field('name').id);
        const name = document.createElement('bdi'); name.textContent = item.name;
        field('name').append(name);
        field('priority').textContent = item.is_prioritized ? `اولویت ${numeral(item.recommendation.rank)}` : item.priority_label;
        field('code').textContent = item.product_code;
        const brand = item.brand?.name || '', categoryName = item.category?.name || '';
        const identityText = item.name.toLocaleLowerCase();
        const showBrand = Boolean(brand) && !identityText.includes(brand.toLocaleLowerCase());
        const showCategory = Boolean(categoryName) && !identityText.includes(categoryName.toLocaleLowerCase());
        field('brand').textContent = brand;
        field('category').textContent = categoryName;
        field('brand').hidden = !showBrand;
        field('category').hidden = !showCategory;
        field('meta-separator').hidden = !showBrand || !showCategory;
        field('meta').hidden = !showBrand && !showCategory;
        if (item.is_prioritized) {
            const savedReason = item.recommendation?.short_reason || 'دلیل متنی برای این پیشنهاد ثبت نشده است.';
            // Select an existing complete sentence; never derive a new customer signal.
            const candidate = savedReason.split(/(?<=[.!؟])\s+/)[0];
            const firstSentence = /^[\d۰-۹\s.!؟]+$/.test(candidate) ? savedReason : candidate;
            field('cue-details').hidden = false;
            field('cue').textContent = firstSentence;
            field('reason').hidden = false;
            field('reason').textContent = savedReason;
            field('cue-details').title = savedReason;
        }
        const stock = field('stock');
        if (item.inventory_state === 'AVAILABLE') {
            const unitLabel = item.unit === 'PCS' ? 'عدد' : item.unit;
            stock.textContent = `موجود: ${numeral(item.available_quantity)} ${unitLabel}`;
            stock.classList.add('gc-stock--available');
        } else if (item.inventory_state === 'UNAVAILABLE') {
            stock.textContent = 'ناموجود · فعلاً قابل افزودن نیست';
            stock.classList.add('gc-stock--unavailable');
        } else stock.textContent = 'موجودی نامشخص · فعلاً قابل افزودن نیست';
        // Stage 2A supplies existence, not an amount. Never infer a quote or discount.
        // The fixed "قیمت پایه" caption identifies this slot; no amount is supplied.
        field('price').textContent = item.pricing?.has_demo_price ? 'ثبت شده است' : 'در دسترس نیست';
        field('detail').href = localDetail(item.brief_url);
        field('detail').setAttribute('aria-label', `جزئیات محصول ${item.name}`);
        if (item.image?.url) {
            const imageURL = new URL(item.image.url, window.location.origin);
            if (['http:', 'https:'].includes(imageURL.protocol)) {
                const image = field('image'), fallback = field('image-fallback');
                image.alt = item.image.label ? `${item.image.label} — ${item.name}` : item.name;
                image.hidden = false; fallback.hidden = true;
                const disclosure = field('image-disclosure'), credit = item.image.credit;
                if (item.image.label) {
                    disclosure.hidden = false;
                    field('image-label').textContent = item.image.label;
                    field('image-credit').textContent = [credit?.author, credit?.licence, credit?.changes].filter(Boolean).join(' · ');
                    for (const [name, value] of [['image-source', credit?.source_url], ['image-licence', credit?.licence_url], ['image-original', credit?.additional_source_url]]) {
                        const link = field(name);
                        link.hidden = !value;
                        if (value) {
                            const destination = new URL(value);
                            if (destination.protocol === 'https:') link.href = destination.href;
                            else link.hidden = true;
                        }
                    }
                }
                image.addEventListener('error', () => { image.hidden = true; fallback.hidden = false; disclosure.hidden = true; });
                image.src = imageURL.href;
            }
        }
        return node;
    }
    function render(data) {
        const smart = byId('catalogPrioritizedItems'), ordinary = byId('catalogOrdinaryItems');
        smart.replaceChildren(); ordinary.replaceChildren();
        for (const item of data.items) (item.is_prioritized ? smart : ordinary).append(card(item));
        byId('catalogPrioritized').hidden = !smart.children.length;
        byId('catalogOrdinary').hidden = !ordinary.children.length;
        category.replaceChildren();
        const all = document.createElement('option'); all.value = ''; all.textContent = 'همه دسته‌ها'; category.append(all);
        for (const choice of data.categories) {
            const option = document.createElement('option'); option.value = String(choice.id); option.textContent = choice.name; category.append(option);
        }
        const chips = byId('catalogCategoryChips');
        chips.replaceChildren();
        for (const choice of [{id: '', name: 'همه کالاها'}, ...data.categories]) {
            const button = document.createElement('button');
            button.type = 'button';
            button.dataset.categoryFilter = String(choice.id);
            button.textContent = choice.name;
            button.setAttribute('aria-pressed', String(String(choice.id) === String(data.filters.category_id ?? '')));
            button.addEventListener('click', () => { category.value = String(choice.id); applyFilters(); });
            chips.append(button);
        }
        search.value = data.filters.q;
        category.value = data.filters.category_id === null ? '' : String(data.filters.category_id);
        priority.value = data.filters.priority;
        byId('catalogAllCount').textContent = numeral(data.counts.overall.total);
        byId('catalogPriorityCount').textContent = numeral(data.counts.overall.prioritized);
        byId('catalogOrdinaryCount').textContent = numeral(data.counts.overall.ordinary);
        byId('catalogSmartGroupCount').textContent = numeral(data.counts.filtered.prioritized);
        byId('catalogOrdinaryGroupCount').textContent = numeral(data.counts.filtered.ordinary);
        for (const button of form.querySelectorAll('[data-priority-filter]')) {
            button.setAttribute('aria-pressed', String(button.dataset.priorityFilter === data.filters.priority));
        }
        const total = data.counts.overall.total, filtered = data.counts.filtered.total;
        byId('catalogSummary').textContent = `${numeral(filtered)} محصول از فهرست کامل ${numeral(total)} محصولی`;
        byId('catalogSummary').hidden = !data.filters.q && data.filters.category_id === null && data.filters.priority === 'all';
        byId('catalogNoPriority').hidden = data.counts.overall.prioritized !== 0 || total === 0;
        byId('catalogEmpty').hidden = data.items.length !== 0;
        byId('catalogEmptyText').textContent = total === 0 ? 'محصول فعالی برای نمایش موجود نیست. به نمای مشتری بازگردید.' : 'محصولی با این جستجو یا فیلتر پیدا نشد؛ فیلترها را پاک کنید.';
        byId('catalogPagination').hidden = data.pagination.pages <= 1;
        byId('catalogPageLabel').textContent = `صفحه ${numeral(data.pagination.page)} از ${numeral(data.pagination.pages)}`;
        previous.disabled = !data.pagination.has_previous;
        next.disabled = !data.pagination.has_next;
        status.textContent = `${numeral(data.items.length)} محصول نمایش داده شد.`;
        const selectedProduct = params.get('product_id'), selectedRec = params.get('recommendation_id');
        const selected = [...smart.children, ...ordinary.children].find(node =>
            selectedProduct ? node.dataset.productId === selectedProduct : selectedRec && node.dataset.recommendationId === selectedRec);
        if (selected) { selected.focus({preventScroll: true}); selected.scrollIntoView({block: 'center', behavior: 'auto'}); }
    }
    async function load(push = false) {
        const version = ++requestVersion;
        controller?.abort(); controller = new AbortController();
        busy(true); results.hidden = true; errorBox.hidden = true;
        status.textContent = 'در حال دریافت فهرست محصولات…';
        const query = new URLSearchParams(params);
        query.delete('product_id'); query.delete('recommendation_id');
        query.set('customer_code', root.dataset.customerCode); query.set('visit_id', root.dataset.visitId);
        try {
            const response = await fetch(`${root.dataset.apiUrl}?${query}`, {method: 'GET', credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store', signal: controller.signal});
            if (version !== requestVersion) return;
            if (!response.ok) {
                const terminal = [400, 403, 404, 409].includes(response.status);
                retry.hidden = terminal;
                byId('catalogErrorText').textContent = response.status === 409 ? 'پیشنهادهای این ویزیت تغییر کرده یا مهلت نمایش پایان یافته است. به نمای مشتری بازگردید.' : terminal ? 'فهرست این مشتری یا ویزیت در دسترس نیست؛ به نمای مشتری بازگردید و زمینه ویزیت را بررسی کنید.' : 'دریافت محصولات انجام نشد؛ اتصال را بررسی کنید و دوباره تلاش کنید.';
                throw new Error('Handled response');
            }
            const data = await response.json();
            if (version !== requestVersion) return;
            if (data.version !== 1 || !Array.isArray(data.items) || !data.catalog_context || String(data.visit?.id) !== root.dataset.visitId || data.customer?.code !== root.dataset.customerCode) throw new Error('Invalid response');
            // Accept the server's context; every later filter/page/detail read carries it.
            params.set('catalog_context', data.catalog_context);
            params.set('page', String(data.pagination.page)); params.set('page_size', String(data.pagination.page_size));
            busy(false); results.hidden = false; render(data); writeLocation(push);
        } catch (error) {
            if (version !== requestVersion || error.name === 'AbortError') return;
            if (error.message !== 'Handled response') {
                retry.hidden = false;
                byId('catalogErrorText').textContent = 'دریافت محصولات انجام نشد؛ اتصال را بررسی کنید و دوباره تلاش کنید.';
            }
            busy(false); previous.disabled = true; next.disabled = true;
            results.hidden = true; errorBox.hidden = false; status.textContent = '';
            // No automatic retry and no context reset, including a 409.
        }
    }
    function clearSelection() { params.delete('product_id'); params.delete('recommendation_id'); }
    function applyFilters() {
        clearSelection(); params.set('page', '1');
        params.set('q', search.value.trim()); params.set('category_id', category.value); params.set('priority', priority.value);
        load(true);
    }
    form.addEventListener('submit', event => {
        event.preventDefault(); applyFilters();
    });
    for (const button of form.querySelectorAll('[data-priority-filter]')) {
        button.addEventListener('click', () => { priority.value = button.dataset.priorityFilter; applyFilters(); });
    }
    byId('catalogFiltersToggle').addEventListener('click', () => {
        const options = byId('catalogFilterOptions');
        options.hidden = !options.hidden;
        byId('catalogFiltersToggle').setAttribute('aria-expanded', String(!options.hidden));
        if (!options.hidden) category.focus();
    });
    byId('catalogReset').addEventListener('click', () => {
        clearSelection(); for (const key of ['q', 'category_id', 'priority']) params.delete(key);
        params.set('page', '1'); load(true);
    });
    previous.addEventListener('click', () => { clearSelection(); params.set('page', String(Number(params.get('page')) - 1)); load(true); });
    next.addEventListener('click', () => { clearSelection(); params.set('page', String(Number(params.get('page')) + 1)); load(true); });
    retry.addEventListener('click', () => load());
    window.addEventListener('popstate', () => { params = readLocation(); load(); });
    window.addEventListener('pageshow', event => { if (event.persisted) { params = readLocation(); load(); } });
    load();
})();
