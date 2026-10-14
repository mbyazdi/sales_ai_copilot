const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/products/js/product_feedback.js'), 'utf8');
const feedback = fs.readFileSync(path.resolve(__dirname, '../../../static/core/js/guided_feedback.js'), 'utf8');
class Element {
    constructor() { this.dataset = {}; this.hidden = false; this.disabled = false; this.listeners = {}; this.textContent = ''; this.children = []; this.value = ''; }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    setAttribute() {}
    focus() {}
    showModal() { this.open = true; }
    close() { this.open = false; }
    remove() { this.removed = true; }
    replaceChildren() { this.children = []; }
    append(element) { this.children.push(element); }
    click() { if (!this.disabled) this.listeners.click?.({preventDefault() {}}); }
}
async function fixture({recommended = true, selected = false, status = 'IN_PROGRESS', failed = '', stale = false, visit = '19', events = [], conflict = false, savedCommand = null} = {}) {
    const ids = ['productFeedback','productFeedbackStatus','productSelection','feedbackDialog','feedbackForm','feedbackReason',
        'feedbackConfirm','feedbackCancel','feedbackMessage','feedbackRecovery','feedbackResume','feedbackProduct','feedbackReasonRow','feedbackTitle','feedbackDescription','feedbackNotice','productFeedbackEmptyHistory'];
    const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
    const root = elements.productFeedback;
    root.dataset = {actorId: '1', customerCode: 'C0003', visitId: visit, visitStatus: status, productId: '6',
        productCode: 'PHI002', productName: 'محصول', recommendationId: recommended ? '101' : '',
        catalogUrl: '/api/products/v1/catalog/', feedbackUrl: '/api/recommendations/v1/visits/19/feedback/'};
    const fields = Object.fromEntries(['actions','summary','history','history-list','guidance','reject','later','change','options'].map(name => [name, new Element()]));
    fields.reject.disabled = fields.later.disabled = true;
    fields['history-list'].hidden = true;
    fields.summary.textContent = 'ثبت بازخورد';
    root.querySelector = selector => selector === '.gc-secondary-actions' || (fields.actions.removed && selector !== '[data-feedback-actions]') ? null : fields[selector.slice(15,-1)];
    elements.feedbackForm.querySelector = () => ({value: 'valid-masked-csrf'});
    const storage = new Map(), calls = [];
    if (savedCommand) storage.set('guided-feedback:v1:1:C0003:19', JSON.stringify(savedCommand));
    const window = {location: new URL('http://localhost/products/PHI002/?catalog_context=signed-entry'),
        crypto: {randomUUID: () => '00000000-0000-4000-8000-000000000001'},
        sessionStorage: {getItem: key => storage.get(key), setItem: (key,value) => storage.set(key,value), removeItem: key => storage.delete(key)}};
    const context = {version: 1, customer: {code: 'C0003'}, visit: {id: 19, status}};
    const fetch = async (url, options) => {
        calls.push({url, options});
        const isFailure = failed && url.includes(failed);
        let body;
        if (options.method === 'POST') {
            const command = JSON.parse(options.body);
            if (conflict) { selected = true; return {ok: false, status: 409, json: async () => ({code: 'PRODUCT_ALREADY_SELECTED'})}; }
            body = {...context, feedback: {id: 7, product_id: 6, recommendation_id: 101, event_type: 'REJECTED', reason_code: command.reason_code}};
        } else if (url.includes('/catalog/')) body = {...context, catalog_context: 'signed-entry', items: [{product_id: 6, is_prioritized: recommended, recommendation: recommended ? {id: stale ? 102 : 101} : null}]};
        else if (url.includes('/feedback/')) body = {...context, events, request: {id: 1, revision: 7, status: 'DRAFT'}, page: 1, pages: 1};
        else body = {...context, editable: status === 'IN_PROGRESS', request: {id: 1, revision: 7, status: 'DRAFT'}, lines: selected ? [{product_id: 6, selection_source: recommended ? 'RECOMMENDATION' : 'ORDINARY'}] : []};
        return {ok: !isFailure, status: isFailure ? 403 : options.method === 'POST' ? 201 : 200, headers: {get: () => null}, json: async () => body};
    };
    const environment = {window, document: {getElementById: id => elements[id], createElement: () => new Element()}, fetch, URL, URLSearchParams};
    vm.runInNewContext(feedback, environment);
    vm.runInNewContext(source, environment);
    await new Promise(resolve => setImmediate(resolve));
    return {elements, fields, calls, storage, submit: () => elements.feedbackForm.listeners.submit({preventDefault() {}})};
}

test('recommended Product Detail binds real shared feedback and signed context using zero-write reads', async () => {
    const f = await fixture();
    assert(!f.fields.reject.disabled); assert(!f.fields.later.disabled);
    assert(f.calls.every(call => call.options.method === 'GET'));
    assert(f.calls[0].url.includes('catalog_context=signed-entry'));
    assert(f.calls.some(call => call.url.includes('/basket/')));
});
test('selected recommended product prominently displays current membership and exposes only separate history', async () => {
    const f = await fixture({selected: true});
    assert(f.fields.reject.disabled); assert(f.fields.later.disabled);
    assert.equal(f.elements.productSelection.textContent, 'در درخواست فروش');
    assert.equal(f.fields.summary.textContent, 'سوابق بازخورد');
    assert(f.fields.options.hidden);
    assert(!f.elements.productFeedbackEmptyHistory.hidden);
    assert.match(f.elements.productFeedbackStatus.textContent, /ابتدا.*حذف/);
    assert.match(f.fields.guidance.textContent, /ابتدا/);
});
test('ordinary product removes feedback controls and can display selected content without acceptance event', async () => {
    const f = await fixture({recommended: false, selected: true});
    assert(f.fields.actions.removed); assert(!f.calls.some(call => call.url.includes('/feedback/')));
    assert.equal(f.elements.productSelection.textContent, 'در درخواست فروش');
});
test('planned/completed visits are read-only and no-visit details perform no API reads', async () => {
    for (const status of ['PLANNED','COMPLETED']) {
        const f = await fixture({status});
        assert(f.fields.reject.disabled); assert(f.fields.later.disabled);
        assert(f.calls.every(call => call.options.method === 'GET'));
        if (status === 'COMPLETED') assert(!f.calls.some(call => call.url.includes('/catalog/')));
    }
    assert.equal((await fixture({visit: ''})).calls.length, 0);
});
test('unauthorized catalog/basket/history and stale saved recommendation never enable decisions', async () => {
    for (const options of [{failed: '/catalog/'},{failed: '/basket/'},{failed: '/feedback/'},{stale: true}]) {
        const f = await fixture(options);
        assert(f.fields.reject.disabled); assert(f.fields.later.disabled);
        assert(f.calls.every(call => call.options.method === 'GET'));
    }
});
test('all seven approved reasons use shared CSRF UUID revision contract with explicit confirmation', async () => {
    for (const reason of ['NOT_INTERESTED','PRICE','STOCK','NO_CURRENT_NEED','OTHER_BRAND','LATER','OTHER']) {
        const f = await fixture();
        f.fields.reject.click();
        assert(f.elements.feedbackDialog.open);
        assert(!f.calls.some(call => call.options.method === 'POST'));
        f.elements.feedbackReason.value = reason;
        await f.submit();
        const post = f.calls.find(call => call.options.method === 'POST');
        const payload = JSON.parse(post.options.body);
        assert.equal(payload.reason_code, reason); assert.equal(payload.catalog_context, 'signed-entry');
        assert.equal(payload.expected_request_revision, 7); assert(payload.command_uuid);
        assert.equal(post.options.headers['X-CSRFToken'], 'valid-masked-csrf');
        assert.equal(f.fields.actions.open, false);
    }
});
test('LATER history remains LATER and changing decision appends rather than edits', async () => {
    const f = await fixture({events: [{id: 1, recommendation_id: 101, event_type: 'REJECTED', reason_code: 'LATER'}]});
    assert.equal(f.fields.summary.textContent, 'بعداً بررسی می‌کنم');
    f.fields.change.click(); f.fields.later.click(); await f.submit();
    assert.equal(f.fields['history-list'].children.length, 2);
    assert.equal(f.fields.summary.textContent, 'بعداً بررسی می‌کنم');
});
test('selection conflict re-reads basket, disables feedback and never retries automatically', async () => {
    const f = await fixture({conflict: true});
    f.fields.later.click(); await f.submit();
    await new Promise(resolve => setImmediate(resolve));
    assert(f.fields.reject.disabled); assert(f.fields.later.disabled);
    assert.equal(f.elements.productSelection.textContent, 'در درخواست فروش');
    assert.equal(f.calls.filter(call => call.options.method === 'POST').length, 1);
    assert.equal(f.calls.filter(call => call.url.includes('/basket/')).length, 2);
});
test('uncertain command reload never POSTs automatically and manual recovery retains old intent despite catalog failure', async () => {
    const savedCommand = {visitId: '19', name: 'محصول', productId: 6, sent: true, payload: {customer_code: 'C0003',
        recommendation_id: 101, action: 'LATER', reason_code: 'LATER', note: '', expected_request_revision: 2,
        command_uuid: '00000000-0000-4000-8000-000000000009', catalog_context: 'old-signed-command'}};
    const f = await fixture({failed: '/catalog/', savedCommand});
    assert(f.fields.reject.disabled); assert.equal(f.calls.filter(call => call.options.method === 'POST').length, 0);
    f.elements.feedbackResume.click(); await f.submit();
    const post = f.calls.find(call => call.options.method === 'POST');
    assert.deepEqual(JSON.parse(post.options.body), savedCommand.payload);
    assert.equal(f.storage.size, 0);
});
test('current membership stays separate from prior rejection/LATER history without offering decision changes', async () => {
    for (const reason_code of ['PRICE','LATER']) {
        const f = await fixture({selected: true, events: [{id: 1, recommendation_id: 101, event_type: 'REJECTED', reason_code}]});
        assert.equal(f.elements.productSelection.textContent, 'در درخواست فروش');
        assert.equal(f.fields.summary.textContent, 'سوابق بازخورد');
        assert.equal(f.fields['history-list'].children.length, 1);
        assert.match(f.fields['history-list'].children[0].textContent, reason_code === 'LATER' ? /بعداً/ : /قیمت/);
        assert(f.fields.options.hidden); assert(f.fields.change.hidden);
        assert(f.elements.productFeedbackEmptyHistory.hidden);
        assert(f.calls.every(call => call.options.method === 'GET'));
    }
});
