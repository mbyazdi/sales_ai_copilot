const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/core/js/customer_360.js'), 'utf8');

function fixture({status = 'PLANNED', authorizedLink = true, respond, sellingToken, existingContext} = {}) {
    const nodes = new Map(), requests = [], events = [], timers = [];
    function node(id) {
        const item = {id, hidden: false, disabled: false, dataset: {}, listeners: {}, attributes: {},
            classList: {add() {}, remove() {}},
            addEventListener(type, fn) { this.listeners[type] = fn; },
            setAttribute(key, value) { this.attributes[key] = value; },
            removeAttribute(key) { delete this.attributes[key]; }};
        nodes.set(id, item); return item;
    }
    node('currentVisitStatus').dataset.status = status;
    node('visitWorkflowMessage');
    if (status === 'PLANNED') node('startVisitButton');
    if (status === 'IN_PROGRESS') node('completeVisitButton');
    if (authorizedLink) {
        const link = node('visitFinishLink');
        link.dataset.finishUrl = '/customers/FIXTURE/visits/14/finish/';
        link.hidden = status !== 'IN_PROGRESS';
        if (!link.hidden) link.attributes.href = link.dataset.finishUrl;
    }
    const actions = {};
    let location = new URL('http://localhost/customers/?customer_code=FIXTURE&visit_id=14');
    if (existingContext) location.searchParams.set('catalog_context', existingContext);
    const navigation = [];
    const guided = node('guidedLink'); guided.href = '/customers/FIXTURE/recommendations/presentation/?visit_id=14';
    if (sellingToken) node('workspace-recommendations').dataset.sellingContext = sellingToken;
    Object.defineProperty(actions, 'innerHTML', {set(value) {
        if (value.includes('id="completeVisitButton"')) node('completeVisitButton');
    }});
    const document = {cookie: 'csrftoken=fixture-csrf', getElementById: id => nodes.get(id) || null,
        querySelector: selector => selector === '.visit-workflow-actions' ? actions : selector === '.c360-guided-link' ? guided : null,
        querySelectorAll: () => [], addEventListener() {}, dispatchEvent: event => events.push(event.type)};
    vm.runInNewContext(source, {document, window: {salesAiCopilot: {customerCode: 'FIXTURE', visitId: 14},
        addEventListener() {}, setTimeout: fn => timers.push(fn),
        history: {replaceState(_state, _title, value) { navigation.push(value); location = new URL(value, location); }},
        location: {get href() { return location.href; }, reload() { throw Error('Unexpected reload'); }}},
        fetch: async (url, options) => {
            requests.push({url, ...options});
            return respond ? respond(url) : {ok: true, json: async () => ({visit: {id: 14, status: 'IN_PROGRESS'}})};
        }, URL, Intl, console, CustomEvent: class {constructor(type) { this.type = type; }}});
    return {nodes, requests, events, timers, navigation, get location() { return location; }, start: () => nodes.get('startVisitButton').listeners.click()};
}

test('neutral selling context is retained for reload and Guided Sale without a mutation', () => {
    const f = fixture({sellingToken: 'signed-neutral'});
    assert.equal(f.location.searchParams.get('catalog_context'), 'signed-neutral');
    assert.equal(new URL(f.nodes.get('guidedLink').href, f.location).searchParams.get('catalog_context'), 'signed-neutral');
    assert.equal(f.requests.length, 0); assert.equal(f.navigation.length, 1);
});

test('existing context wins over any newly supplied browser context metadata', () => {
    const f = fixture({sellingToken: 'new-policy-context', existingContext: 'old-context'});
    assert.equal(f.location.searchParams.get('catalog_context'), 'old-context');
    assert.equal(new URL(f.nodes.get('guidedLink').href, f.location).searchParams.get('catalog_context'), 'old-context');
    assert.equal(f.navigation.length, 0); assert.equal(f.requests.length, 0);
});

test('PLANNED link is non-actionable and initial rendering sends no mutations', () => {
    const f = fixture(), link = f.nodes.get('visitFinishLink');
    assert.equal(link.hidden, true); assert.equal(link.attributes.href, undefined);
    assert.equal(f.requests.length, 0);
});

test('only matching server-confirmed Start exposes the unchanged Finish URL without reload', async () => {
    let resolve;
    const pending = new Promise(r => { resolve = r; });
    const f = fixture({respond: () => pending}), link = f.nodes.get('visitFinishLink');
    const action = f.start();
    assert.equal(link.hidden, true); assert.equal(link.attributes.href, undefined);
    assert.equal(f.requests.length, 1);
    assert.equal(f.requests[0].url, '/api/visits/v1/visits/14/start/');
    assert.equal(f.requests[0].method, 'POST');
    assert.equal(f.requests[0].headers['X-CSRFToken'], 'fixture-csrf');
    resolve({ok: true, json: async () => ({visit: {id: 14, status: 'IN_PROGRESS'}})});
    await action;
    assert.equal(link.hidden, false); assert.equal(link.attributes.href, link.dataset.finishUrl);
    assert(f.nodes.get('completeVisitButton').listeners.click);
    assert.deepEqual(f.events, ['sales-visit-state-changed']);
    assert.equal(f.requests.length, 1); assert.equal(f.timers.length, 0);
});

test('failed or unauthorized Start never exposes Finish and never automatically retries', async () => {
    for (const respond of [
        async () => ({ok: false, json: async () => ({detail: 'Denied'})}),
        async () => { throw Error('Network unavailable'); },
    ]) {
        const f = fixture({respond}); await f.start();
        assert.equal(f.nodes.get('visitFinishLink').hidden, true);
        assert.equal(f.nodes.get('visitFinishLink').attributes.href, undefined);
        assert.equal(f.nodes.get('startVisitButton').disabled, false);
        assert.equal(f.requests.length, 1);
    }
});

test('another Visit response cannot activate Finish navigation', async () => {
    const f = fixture({respond: async () => ({ok: true, json: async () => ({visit: {id: 99, status: 'IN_PROGRESS'}})})});
    await f.start();
    assert.equal(f.nodes.get('visitFinishLink').hidden, true);
    assert.equal(f.nodes.get('visitFinishLink').attributes.href, undefined);
});

test('server states other than IN_PROGRESS never activate Finish', async () => {
    for (const status of ['PLANNED', 'COMPLETED', 'CANCELLED']) {
        const f = fixture({respond: async () => ({ok: true, json: async () => ({visit: {id: 14, status}})})});
        await f.start();
        assert.equal(f.nodes.get('visitFinishLink').hidden, true);
        assert.equal(f.nodes.get('visitFinishLink').attributes.href, undefined);
    }
});

test('legacy completion hides and deactivates Finish before its unchanged scheduled reload', async () => {
    const f = fixture({status: 'IN_PROGRESS', respond: async () => ({ok: true, json: async () => ({visit: {id: 14, status: 'COMPLETED'}})})});
    await f.nodes.get('completeVisitButton').listeners.click();
    assert.equal(f.nodes.get('visitFinishLink').hidden, true);
    assert.equal(f.nodes.get('visitFinishLink').attributes.href, undefined);
    assert.equal(f.requests.length, 1); assert.equal(f.requests[0].url, '/api/visits/v1/visits/14/complete/');
    assert.equal(f.timers.length, 1);
});

test('no server-authorized placeholder means no Finish link is created by JavaScript', async () => {
    const f = fixture({authorizedLink: false}); await f.start();
    assert.equal(f.nodes.has('visitFinishLink'), false); assert.equal(f.requests.length, 1);
});
