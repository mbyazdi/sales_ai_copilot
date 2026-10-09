const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/products/js/commercial_quotes.js'), 'utf8');
function mount() {
    const fields = {};
    for (const name of ['commercial-quote', 'quote-base-row', 'quote-discount-row', 'quote-base', 'quote-discount', 'quote-saving', 'quote-final', 'quote-currency', 'quote-demo', 'quote-stock', 'quote-availability']) {
        fields[name] = {dataset: {}, hidden: false, textContent: '', attributes: {}, setAttribute(name, value) { this.attributes[name] = value; }};
    }
    return {fields, querySelector(selector) { return fields[selector.slice(6, -1)]; }};
}
const context = {apiUrl: '/api/sales-requests/v1/visits/14/quote/', customerCode: 'C', visitId: '14'};
function item(id = 1, overrides = {}) {
    return {product_id: id, quantity: 1, pricing: {state: 'AVAILABLE', quote: {customer_id: 9, product_id: id, quantity: 1, currency: 'TOMAN', base_unit_price: '105', discount_percentage: '10', unit_discount: '10', final_unit_price: '95'}},
        inventory: {state: 'AVAILABLE', sellable_quantity: 8}, can_add: true, non_addable_reason: null, ...overrides};
}
function payload(items) { return {version: 1, currency: 'TOMAN', customer: {id: 9, code: 'C'}, visit: {id: 14}, items}; }
function fixture(responder, detailMounts = []) {
    const calls = [], window = {location: new URL('http://localhost/')};
    const fetch = async (url, options) => {
        calls.push({url, options});
        const data = await responder(url, options);
        return data?.status ? {ok: false, status: data.status} : {ok: true, json: async () => data};
    };
    vm.runInNewContext(source, {window, document: {querySelectorAll: () => detailMounts}, fetch, URL, URLSearchParams, Intl});
    return {load: window.CommercialQuotes.load, calls};
}
test('Guided and Detail present identical server amounts, without recalculation or mutations', async () => {
    const f = fixture(() => payload([item()])), guided = mount(), detail = mount();
    for (const target of [guided, detail]) await f.load(context, [{productId: 1, mount: target}]);
    for (const name of Object.keys(guided.fields)) {
        for (const property of ['textContent', 'hidden', 'attributes', 'dataset']) assert.deepEqual(guided.fields[name][property], detail.fields[name][property]);
    }
    assert.equal(detail.fields['quote-base'].textContent, '۱۰۵');
    assert.equal(detail.fields['quote-discount'].textContent, '۱۰');
    assert.equal(detail.fields['quote-saving'].textContent, '۱۰');
    assert.equal(detail.fields['quote-final'].textContent, '۹۵');
    assert(!detail.fields['quote-demo'].hidden);
    assert(f.calls.every(c => c.options.method === 'GET' && c.options.cache === 'no-store' && c.options.credentials === 'same-origin'));
    assert(f.calls.every(c => JSON.parse(new URL(c.url, 'http://localhost').searchParams.get('items'))[0].quantity === 1));
});
test('Product Detail initializes the same read-only renderer from its context binding', async () => {
    const target = mount(); target.dataset = {quoteUrl: context.apiUrl, customerCode: 'C', visitId: '14', productId: '1'};
    const f = fixture(() => payload([item()]), [target]);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(f.calls.length, 1); assert.equal(target.fields['quote-final'].textContent, '۹۵');
});
test('explicit zero is displayed as a real quote, missing price is not zero', async () => {
    const zero = item(); Object.assign(zero.pricing.quote, {base_unit_price: '0', discount_percentage: '0', unit_discount: '0', final_unit_price: '0'});
    const f = fixture(() => payload([zero])), target = mount();
    await f.load(context, [{productId: 1, mount: target}]);
    assert.equal(target.fields['quote-final'].textContent, '۰'); assert(!target.fields['quote-currency'].hidden);
    const missing = fixture(() => payload([item(1, {pricing: {state: 'UNAVAILABLE', quote: null}, can_add: false, non_addable_reason: 'PRICE_UNAVAILABLE'})]));
    await missing.load(context, [{productId: 1, mount: target}]);
    assert.match(target.fields['quote-final'].textContent, /قیمت فعلی در دسترس نیست/);
    assert(target.fields['quote-currency'].hidden); assert(target.fields['quote-demo'].hidden);
    assert(target.fields['quote-base-row'].hidden);
});
test('unknown, zero, insufficient stock and inactive Visit stay separate from available price', async () => {
    for (const [state, quantity, reason, expected] of [
        ['UNKNOWN', null, 'INVENTORY_UNKNOWN', /موجودی نامشخص/],
        ['UNAVAILABLE', 0, 'OUT_OF_STOCK', /ناموجود/],
        ['AVAILABLE', 2, 'INSUFFICIENT_STOCK', /کافی نیست/],
        ['AVAILABLE', 8, 'VISIT_NOT_ACTIVE', /فقط مشاهده/],
    ]) {
        const f = fixture(() => payload([item(1, {inventory: {state, sellable_quantity: quantity}, can_add: false, non_addable_reason: reason})])), target = mount();
        await f.load(context, [{productId: 1, mount: target}]);
        assert.equal(target.fields['quote-final'].textContent, '۹۵');
        assert.match(target.fields['quote-availability'].textContent, expected);
        if (state === 'UNKNOWN') assert(!target.fields['quote-stock'].textContent.includes('۰'));
    }
});
test('configuration errors do not fabricate usable prices', async () => {
    const f = fixture(() => payload([item(1, {pricing: {state: 'CONFIGURATION_ERROR', quote: null}, can_add: false, non_addable_reason: 'PRICE_CONFIGURATION_ERROR'})])), target = mount();
    await f.load(context, [{productId: 1, mount: target}]);
    assert.equal(target.fields['quote-final'].textContent, 'قیمت فعلی قابل استفاده نیست');
    assert(target.fields['quote-currency'].hidden); assert(target.fields['quote-discount-row'].hidden);
});
test('one hundred visible products use two bounded batches without changing target order', async () => {
    const targets = Array.from({length: 100}, (_, index) => ({productId: 100 - index, mount: mount()}));
    const f = fixture(url => payload(JSON.parse(new URL(url, 'http://localhost').searchParams.get('items')).map(row => item(row.product_id))));
    await f.load(context, targets);
    assert.equal(f.calls.length, 2);
    assert(f.calls.every(c => JSON.parse(new URL(c.url, 'http://localhost').searchParams.get('items')).length === 50));
    assert.equal(targets[0].productId, 100); assert.equal(targets[99].productId, 1);
    assert(targets.every(t => t.mount.fields['quote-final'].textContent === '۹۵'));
});
test('unauthorized and wrong-customer/Visit/product quote results cannot be displayed', async () => {
    const wrongCustomer = payload([item()]); wrongCustomer.customer.code = 'FOREIGN';
    const wrongVisit = payload([item()]); wrongVisit.visit.id = 15;
    const wrongIdentity = item(); wrongIdentity.pricing.quote.customer_id = 999;
    for (const data of [{status: 403}, wrongCustomer, wrongVisit, payload([item(2)]), payload([wrongIdentity])]) {
        const f = fixture(() => data), target = mount();
        await f.load(context, [{productId: 1, mount: target}]);
        assert.equal(target.fields['commercial-quote'].dataset.state, 'ERROR');
        assert(target.fields['quote-base-row'].hidden); assert(target.fields['quote-currency'].hidden);
        assert.equal(f.calls.length, 1);
    }
});
test('network failures leave products browsable and never automatically retry', async () => {
    const f = fixture(() => { throw new Error('Network'); }), target = mount();
    await f.load(context, [{productId: 1, mount: target}]);
    assert.match(target.fields['quote-final'].textContent, /صفحه را تازه کنید/); assert.equal(f.calls.length, 1);
});
test('an obsolete quote response cannot replace the current filtered catalog', async () => {
    let resolve, current = true;
    const f = fixture(() => new Promise(done => { resolve = done; })), target = mount();
    const pending = f.load(context, [{productId: 1, mount: target}], {isCurrent: () => current});
    current = false; resolve(payload([item()])); await pending;
    assert.equal(target.fields['quote-final'].textContent, 'در حال دریافت قیمت…');
});
test('large whole TOMAN strings are formatted without floating-point loss', async () => {
    const product = item(); product.pricing.quote.final_unit_price = '9999999999999999';
    const f = fixture(() => payload([product])), target = mount();
    await f.load(context, [{productId: 1, mount: target}]);
    assert.equal(target.fields['quote-final'].textContent, new Intl.NumberFormat('fa-IR').format(9999999999999999n));
});
test('external endpoints and invalid amount strings fail without leaking a displayed quote', async () => {
    const f = fixture(() => payload([item()])), target = mount();
    await f.load({...context, apiUrl: 'https://foreign.invalid/api/sales-requests/v1/visits/14/quote/'}, [{productId: 1, mount: target}]);
    assert.equal(f.calls.length, 0);
    const invalid = item(); invalid.pricing.quote.final_unit_price = '<script>bad()</script>';
    const bad = fixture(() => payload([invalid])); await bad.load(context, [{productId: 1, mount: target}]);
    assert.equal(target.fields['commercial-quote'].dataset.state, 'ERROR');
    assert(!target.fields['quote-final'].textContent.includes('<script>'));
});
