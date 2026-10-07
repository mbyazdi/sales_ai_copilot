/* Run the production UI against isolated DOM/API fixtures, with no business writes. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/core/js/guided_catalog.js'), 'utf8');
class Element {
    constructor() {
        this.dataset = {}; this.listeners = {}; this.children = []; this.attributes = {};
        this.hidden = false; this.disabled = false; this.value = ''; this.textContent = '';
        this.classes = new Set();
        this.classList = {add: value => this.classes.add(value), toggle: (value, on) => on ? this.classes.add(value) : this.classes.delete(value)};
    }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute(name, value) { this.attributes[name] = value; }
    append(child) { this.children.push(child); }
    replaceChildren() { this.children = []; }
    focus() { this.focused = true; }
    scrollIntoView() { this.scrolled = true; }
    querySelector(selector) { return this.fields[selector.slice(6, -1)]; }
    querySelectorAll(selector) {
        const controls = this.controls || [];
        return selector === '[data-priority-filter]' ? controls.filter(node => node.dataset.priorityFilter) : controls;
    }
    cloneNode() { return makeCard(); }
    click() { if (!this.disabled) this.listeners.click?.({}); }
}
function makeCard() {
    const card = new Element(); card.fields = {};
    for (const name of ['name', 'code', 'meta', 'brand', 'category', 'meta-separator', 'priority', 'reason', 'cue', 'cue-details', 'stock', 'price', 'detail', 'image', 'image-fallback']) card.fields[name] = new Element();
    card.fields.reason.hidden = true; card.fields['cue-details'].hidden = true; card.fields.image.hidden = true;
    return card;
}
function item(id, prioritized = false, stock = 'AVAILABLE') {
    return {product_id: id, product_code: `P-${id}`, name: `محصول ${id}`, unit: 'عدد', brand: {name: 'برند'}, category: {name: 'دسته'},
        is_prioritized: prioritized, priority_label: prioritized ? 'پیشنهاد اولویت‌دار' : 'بدون اولویت ویژه',
        recommendation: prioritized ? {id: id + 100, rank: id, short_reason: 'دلیل ذخیره‌شده'} : null,
        inventory_state: stock, available_quantity: stock === 'UNKNOWN' ? null : stock === 'UNAVAILABLE' ? 0 : 8,
        pricing: {has_demo_price: false, state: 'NOT_EVALUATED'}, image: {url: null},
        brief_url: `/products/P-${id}/?customer_code=C&visit_id=14&return_to=catalog&catalog_context=signed&page=1`};
}
function payload(items = [item(1, true), item(2, true), item(3), item(4), item(5), item(6)]) {
    const count = items.filter(row => row.is_prioritized).length;
    return {version: 1, customer: {code: 'C'}, visit: {id: 14}, catalog_context: 'signed', categories: [{id: 1, name: 'دسته'}],
        filters: {q: '', category_id: null, priority: 'all'}, counts: {overall: {total: items.length, prioritized: count, ordinary: items.length - count}, filtered: {total: items.length, prioritized: count, ordinary: items.length - count}},
        pagination: {page: 1, page_size: 20, pages: 1, has_next: false, has_previous: false}, items};
}
function fixture({query = '?visit_id=14', responses = [payload()]} = {}) {
    const ids = ['guidedCatalog', 'catalogFilters', 'catalogSearch', 'catalogCategory', 'catalogPriority', 'catalogStatus', 'catalogResults', 'catalogError', 'catalogRetry',
        'catalogPrevious', 'catalogNext', 'catalogReset', 'catalogApply', 'catalogErrorText', 'catalogPrioritizedItems', 'catalogOrdinaryItems', 'catalogPrioritized', 'catalogOrdinary',
        'catalogSummary', 'catalogNoPriority', 'catalogEmpty', 'catalogEmptyText', 'catalogPagination', 'catalogPageLabel', 'catalogCardTemplate',
        'catalogAllTab', 'catalogPriorityTab', 'catalogOrdinaryTab', 'catalogAllCount', 'catalogPriorityCount', 'catalogOrdinaryCount',
        'catalogSmartGroupCount', 'catalogOrdinaryGroupCount', 'catalogFiltersToggle', 'catalogFilterOptions', 'catalogCategoryChips'];
    const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
    elements.guidedCatalog.dataset = {apiUrl: '/api/products/v1/catalog/', customerCode: 'C', visitId: '14'};
    for (const [id, filter] of [['catalogAllTab', 'all'], ['catalogPriorityTab', 'prioritized'], ['catalogOrdinaryTab', 'ordinary']]) elements[id].dataset.priorityFilter = filter;
    elements.catalogFilterOptions.hidden = true;
    elements.catalogFilters.controls = ['catalogSearch', 'catalogCategory', 'catalogPriority', 'catalogApply', 'catalogReset', 'catalogAllTab', 'catalogPriorityTab', 'catalogOrdinaryTab', 'catalogFiltersToggle'].map(id => elements[id]);
    elements.catalogCardTemplate.content = {firstElementChild: makeCard()};
    const calls = [], history = [], listeners = {};
    let location = new URL('http://localhost/customers/C/recommendations/presentation/' + query);
    const window = {get location() { return location; }, addEventListener(name, callback) { listeners[name] = callback; }, history: {}};
    for (const method of ['pushState', 'replaceState']) window.history[method] = (_state, _title, url) => { history.push({method, url}); location = new URL(url, location); };
    const fetch = async (url, options) => {
        calls.push({url, options});
        const response = responses.shift();
        if (response instanceof Error) throw response;
        if (response instanceof Promise) return response;
        return {ok: !response?.status, status: response?.status || 200, json: async () => response};
    };
    vm.runInNewContext(source, {document: {getElementById: id => elements[id], createElement: () => new Element()}, window, fetch, URL, URLSearchParams, AbortController, Intl});
    return {elements, calls, history, listeners, get location() { return location; }, responses};
}
const settle = () => new Promise(resolve => setImmediate(resolve));
test('renders the complete server page, prioritized before ordinary, without a three-product limit', async () => {
    const f = fixture(); await settle();
    assert.equal(f.elements.catalogPrioritizedItems.children.length, 2);
    assert.equal(f.elements.catalogOrdinaryItems.children.length, 4);
    assert.equal(f.elements.catalogPrioritizedItems.children[0].dataset.productId, '1');
    assert.equal(f.elements.catalogOrdinaryItems.children[0].dataset.productId, '3');
    assert(!f.elements.catalogResults.hidden); assert.equal(f.elements.guidedCatalog.attributes['aria-busy'], 'false');
});
test('ordinary products are marked, remain browsable, and have no recommendation reason', async () => {
    const f = fixture(); await settle();
    const smart = f.elements.catalogPrioritizedItems.children[0], ordinary = f.elements.catalogOrdinaryItems.children[0];
    assert.equal(smart.fields.reason.textContent, 'دلیل ذخیره‌شده'); assert(!smart.fields.reason.hidden);
    assert.equal(ordinary.fields.priority.textContent, 'بدون اولویت ویژه'); assert(ordinary.fields.reason.hidden);
    assert(!ordinary.classes.has('gc-card--priority')); assert(ordinary.fields.detail.href.startsWith('/products/'));
});
test('zero and unknown stock remain visible with truthful price/image fallback', async () => {
    const f = fixture({responses: [payload([item(1, false, 'UNAVAILABLE'), item(2, false, 'UNKNOWN')])]}); await settle();
    const [zero, unknown] = f.elements.catalogOrdinaryItems.children;
    assert.match(zero.fields.stock.textContent, /ناموجود/); assert.match(unknown.fields.stock.textContent, /موجودی نامشخص/);
    assert.equal(zero.fields.price.textContent, 'در دسترس نیست'); assert(zero.fields.image.hidden);
    assert.equal(unknown.fields.detail.href.includes('return_to=catalog'), true);
});
test('a registered price indicates availability without fabricated amount, discount or final price', async () => {
    const product = item(1); product.pricing.has_demo_price = true; product.unit = 'PCS';
    const f = fixture({responses: [payload([product])]}); await settle();
    assert.equal(f.elements.catalogOrdinaryItems.children[0].fields.price.textContent, 'ثبت شده است');
    assert.match(f.elements.catalogOrdinaryItems.children[0].fields.stock.textContent, /عدد/);
});
test('search/category/priority use GET and keep signed context while resetting page', async () => {
    const f = fixture({responses: [payload(), payload()]}); await settle();
    f.elements.catalogSearch.value = ' شامپو '; f.elements.catalogCategory.value = '1'; f.elements.catalogPriority.value = 'ordinary';
    f.elements.catalogFilters.listeners.submit({preventDefault() {}}); await settle();
    const query = new URL(f.calls[1].url, f.location).searchParams;
    assert.equal(query.get('q'), 'شامپو'); assert.equal(query.get('category_id'), '1'); assert.equal(query.get('priority'), 'ordinary');
    assert.equal(query.get('catalog_context'), 'signed'); assert.equal(query.get('page'), '1');
    assert(f.calls.every(call => call.options.method === 'GET')); assert.equal(f.history.at(-1).method, 'pushState');
});
test('reset clears filters without losing the saved session', async () => {
    const f = fixture({query: '?visit_id=14&q=x&category_id=1&catalog_context=signed', responses: [payload(), payload()]}); await settle();
    f.elements.catalogReset.click(); await settle();
    const query = new URL(f.calls[1].url, f.location).searchParams;
    assert.equal(query.get('catalog_context'), 'signed'); assert.equal(query.get('q'), null); assert.equal(query.get('category_id'), null);
});
test('pagination follows server flags and keeps context and filters', async () => {
    const first = payload(); first.pagination.pages = 2; first.pagination.has_next = true;
    const second = payload(); second.pagination.page = 2; second.pagination.pages = 2; second.pagination.has_previous = true;
    const f = fixture({query: '?visit_id=14&q=محصول', responses: [first, second]}); await settle();
    assert(!f.elements.catalogPagination.hidden); f.elements.catalogNext.click(); await settle();
    const query = new URL(f.calls[1].url, f.location).searchParams;
    assert.equal(query.get('page'), '2'); assert.equal(query.get('q'), 'محصول'); assert.equal(query.get('catalog_context'), 'signed');
    assert(f.elements.catalogNext.disabled); assert(!f.elements.catalogPrevious.disabled);
});
test('no recommendations still shows ordinary catalog and a helpful message', async () => {
    const f = fixture({responses: [payload([item(1), item(2)])]}); await settle();
    assert(f.elements.catalogPrioritized.hidden); assert(!f.elements.catalogOrdinary.hidden); assert(!f.elements.catalogNoPriority.hidden);
});
test('empty search and empty catalog are distinct actionable states', async () => {
    const search = payload([]); search.counts.overall.total = 6;
    const f = fixture({responses: [search]}); await settle();
    assert(!f.elements.catalogEmpty.hidden); assert.match(f.elements.catalogEmptyText.textContent, /فیلترها را پاک/);
    const empty = fixture({responses: [payload([])]}); await settle();
    assert.match(empty.elements.catalogEmptyText.textContent, /محصول فعالی/);
});
test('stale and denied contexts do not retry or reset the token', async () => {
    for (const status of [400, 403, 404, 409]) {
        const f = fixture({query: '?visit_id=14&catalog_context=old', responses: [{status}]}); await settle();
        assert(!f.elements.catalogError.hidden); assert(f.elements.catalogRetry.hidden); assert.equal(f.calls.length, 1);
        assert.equal(new URL(f.calls[0].url, f.location).searchParams.get('catalog_context'), 'old');
    }
});
test('network failure allows only manual GET retry with the same context', async () => {
    const f = fixture({query: '?visit_id=14&catalog_context=signed', responses: [new Error('offline'), payload()]}); await settle();
    assert.equal(f.calls.length, 1); assert(!f.elements.catalogRetry.hidden); assert(f.elements.catalogResults.hidden);
    f.elements.catalogRetry.click(); await settle(); assert.equal(f.calls.length, 2);
    assert.equal(new URL(f.calls[1].url, f.location).searchParams.get('catalog_context'), 'signed');
});
test('ordinary Product Brief return restores filters/page and focuses selected product', async () => {
    const response = payload(); response.filters.q = 'محصول'; response.filters.category_id = 1; response.pagination.page = 2;
    const f = fixture({query: '?visit_id=14&catalog_context=signed&q=محصول&category_id=1&page=2&product_id=3', responses: [response]}); await settle();
    const product = f.elements.catalogOrdinaryItems.children[0]; assert(product.focused); assert(product.scrolled);
    assert.equal(f.elements.catalogSearch.value, 'محصول'); assert.equal(f.elements.catalogCategory.value, '1');
    assert.equal(f.location.searchParams.get('product_id'), '3'); assert.equal(f.location.searchParams.get('page'), '2');
});
test('legacy recommendation focus remains compatible', async () => {
    const f = fixture({query: '?visit_id=14&recommendation_id=101'}); await settle();
    assert(f.elements.catalogPrioritizedItems.children[0].focused);
});
test('text is inserted safely and external detail destinations are rejected', async () => {
    const product = item(1); product.name = '<script>bad()</script>';
    const f = fixture({responses: [payload([product])]}); await settle();
    assert.equal(f.elements.catalogOrdinaryItems.children[0].fields.name.children[0].textContent, product.name);
    product.brief_url = 'https://evil.invalid/products/x/';
    const unsafe = fixture({responses: [payload([product])]}); await settle(); assert(!unsafe.elements.catalogError.hidden);
});
test('BFCache and browser history recovery reread with saved context and never POST', async () => {
    const f = fixture({responses: [payload(), payload(), payload()]}); await settle();
    f.listeners.pageshow({persisted: true}); await settle(); f.listeners.popstate(); await settle();
    assert.equal(f.calls.length, 3); assert(f.calls.slice(1).every(call => new URL(call.url, f.location).searchParams.get('catalog_context') === 'signed'));
    assert(f.calls.every(call => call.options.method === 'GET'));
});
test('late responses cannot replace a newer catalog and pending filters are disabled', async () => {
    let resolve;
    const pending = new Promise(done => { resolve = done; });
    const f = fixture({responses: [pending, payload([item(9)])]});
    assert(f.elements.catalogSearch.disabled);
    f.listeners.popstate(); await settle();
    resolve({ok: true, json: async () => payload([item(1)])}); await settle();
    assert.equal(f.elements.catalogOrdinaryItems.children[0].dataset.productId, '9');
});
test('failed actual image reference restores intentional fallback', async () => {
    const product = item(1); product.image.url = '/media/approved.png';
    const f = fixture({responses: [payload([product])]}); await settle();
    const fields = f.elements.catalogOrdinaryItems.children[0].fields;
    assert(!fields.image.hidden); fields.image.listeners.error(); assert(fields.image.hidden); assert(!fields['image-fallback'].hidden);
});
test('priority chips show server counts/rank and filter with the existing saved context', async () => {
    const filtered = payload([item(1, true), item(2, true)]); filtered.filters.priority = 'prioritized';
    const f = fixture({responses: [payload(), filtered]}); await settle();
    assert.equal(f.elements.catalogAllCount.textContent, '۶');
    assert.equal(f.elements.catalogPriorityCount.textContent, '۲');
    assert.match(f.elements.catalogPrioritizedItems.children[0].fields.priority.textContent, /اولویت ۱/);
    f.elements.catalogPriorityTab.click(); await settle();
    const query = new URL(f.calls[1].url, f.location).searchParams;
    assert.equal(query.get('priority'), 'prioritized'); assert.equal(query.get('catalog_context'), 'signed');
    assert.equal(f.elements.catalogPriorityTab.attributes['aria-pressed'], 'true');
    assert.equal(f.elements.catalogAllTab.attributes['aria-pressed'], 'false');
});
test('filter disclosure is keyboard usable and never fetches or writes on opening', async () => {
    const f = fixture(); await settle();
    f.elements.catalogFiltersToggle.click();
    assert(!f.elements.catalogFilterOptions.hidden); assert(f.elements.catalogCategory.focused);
    assert.equal(f.elements.catalogFiltersToggle.attributes['aria-expanded'], 'true'); assert.equal(f.calls.length, 1);
    f.elements.catalogFiltersToggle.click(); assert(f.elements.catalogFilterOptions.hidden); assert.equal(f.calls.length, 1);
});
test('visible category chips use real categories and preserve all existing filter/context semantics', async () => {
    const filtered = payload([item(3)]); filtered.filters.category_id = 1; filtered.filters.q = 'محصول'; filtered.filters.priority = 'ordinary';
    const f = fixture({query: '?visit_id=14&q=محصول&priority=ordinary&catalog_context=signed', responses: [payload(), filtered, payload()]}); await settle();
    assert.equal(f.elements.catalogCategoryChips.children.length, 2);
    assert.equal(f.elements.catalogCategoryChips.children[1].textContent, 'دسته');
    // The live controls carry the existing filter selections into applyFilters.
    f.elements.catalogSearch.value = 'محصول'; f.elements.catalogPriority.value = 'ordinary';
    f.elements.catalogCategoryChips.children[1].click(); await settle();
    const query = new URL(f.calls[1].url, f.location).searchParams;
    assert.equal(query.get('category_id'), '1'); assert.equal(query.get('q'), 'محصول');
    assert.equal(query.get('priority'), 'ordinary'); assert.equal(query.get('page'), '1'); assert.equal(query.get('catalog_context'), 'signed');
    assert.equal(f.elements.catalogCategoryChips.children[1].attributes['aria-pressed'], 'true');
    f.elements.catalogCategoryChips.children[0].click(); await settle();
    assert.equal(new URL(f.calls[2].url, f.location).searchParams.get('category_id'), '');
    assert(f.calls.every(call => call.options.method === 'GET'));
});
test('code is independent of tertiary metadata and repeated identity text creates no noise', async () => {
    const first = item(1), second = item(2); second.name = 'برند دسته محصول';
    const f = fixture({responses: [payload([first, second])]}); await settle();
    const [one, two] = f.elements.catalogOrdinaryItems.children;
    assert.equal(one.fields.code.textContent, 'P-1'); assert.equal(one.fields.brand.textContent, 'برند'); assert.equal(one.fields.category.textContent, 'دسته');
    assert(!one.fields.meta.hidden); assert(two.fields.meta.hidden);
});
test('one cue is selected verbatim from saved reason and full supplied explanation stays available', async () => {
    const product = item(1, true); product.recommendation.short_reason = 'دلیل اول ثبت‌شده. دلیل دوم ثبت‌شده.';
    const f = fixture({responses: [payload([product])]}); await settle();
    const fields = f.elements.catalogPrioritizedItems.children[0].fields;
    assert.equal(fields.cue.textContent, 'دلیل اول ثبت‌شده.');
    assert.equal(fields.reason.textContent, product.recommendation.short_reason);
    assert(!fields['cue-details'].hidden); assert(!fields.reason.hidden);
    const ordinary = fixture({responses: [payload([item(2)])]}); await settle();
    assert(ordinary.elements.catalogOrdinaryItems.children[0].fields['cue-details'].hidden);
});
test('numbered saved prose is retained rather than reducing the cue to a number', async () => {
    const product = item(1, true); product.recommendation.short_reason = '۱. توضیح واقعی ثبت‌شده.';
    const f = fixture({responses: [payload([product])]}); await settle();
    assert.equal(f.elements.catalogPrioritizedItems.children[0].fields.cue.textContent, product.recommendation.short_reason);
});
