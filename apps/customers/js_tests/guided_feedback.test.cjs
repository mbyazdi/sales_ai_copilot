const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/core/js/guided_feedback.js'), 'utf8');
class Element {
    constructor() { this.dataset = {}; this.listeners = {}; this.hidden = false; this.disabled = false; this.value = ''; this.textContent = ''; this.attributes = {}; this.children = []; }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    setAttribute(name, value) { this.attributes[name] = value; }
    focus() { this.focused = true; }
    click() { if (!this.disabled) return this.listeners.click?.({preventDefault() {}}); }
    showModal() { this.open = true; }
    close() { this.open = false; }
    remove() { this.removed = true; }
    prepend(element) { this.prepended = element; }
    replaceChildren() { this.children = []; }
    append(element) { this.children.push(element); }
}
function target(id = 101, productId = 1) {
    const fields = {};
    for (const name of ['actions', 'summary', 'history', 'history-list', 'guidance', 'reject', 'later', 'change', 'options']) fields[name] = new Element();
    fields.summary.textContent = 'بازخورد'; fields.history.hidden = true;
    const actions = new Element();
    return {recommendationId: id, productId, name: '<محصول نمونه>', fields, mount: {querySelector(selector) { return selector === '.gc-secondary-actions' ? actions : fields[selector.slice(15, -1)]; }}};
}
function history({status = 'IN_PROGRESS', events = [], request = null, page = 1, pages = 1} = {}) {
    return {version: 1, customer: {code: 'C'}, visit: {id: 14, status}, events, request, page, pages};
}
function success(payload, replay = false) {
    return {status: 201, replay, body: {version: 1, customer: {code: 'C'}, visit: {id: 14}, feedback: {id: 7, product_id: 1, recommendation_id: payload.recommendation_id, event_type: 'REJECTED', action: payload.action, reason_code: payload.reason_code}}};
}
function fixture({read = () => history(), post = payload => success(payload), storage = new Map()} = {}) {
    const ids = ['guidedCatalog','feedbackDialog','feedbackForm','feedbackReason','feedbackConfirm','feedbackCancel','feedbackMessage','feedbackRecovery','feedbackResume','feedbackProduct','feedbackReasonRow','feedbackTitle','feedbackDescription','feedbackNotice'];
    const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
    elements.guidedCatalog.dataset = {actorId: '1', customerCode: 'C', visitId: '14'};
    elements.feedbackForm.querySelector = () => ({value: 'masked-csrf-token'});
    const calls = [];
    let serial = 0;
    const window = {location: new URL('http://localhost/'), crypto: {randomUUID: () => `00000000-0000-4000-8000-${String(++serial).padStart(12,'0')}`},
        sessionStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key,value), removeItem: key => storage.delete(key)}};
    const fetch = async (url, options) => {
        calls.push({url, options});
        const data = await (options.method === 'GET' ? read(url) : post(JSON.parse(options.body)));
        const status = data.status || 200;
        return {status, ok: status < 400, headers: {get: () => data.replay ? 'true' : 'false'}, json: async () => data.body || data};
    };
    vm.runInNewContext(source,{window, document: {getElementById: id => elements[id], createElement: () => new Element()}, fetch, URL, URLSearchParams});
    return {elements, calls, storage, load: window.GuidedFeedback.load,
        submit: () => elements.feedbackForm.listeners.submit({preventDefault() {}})};
}
const context = {apiUrl: '/api/recommendations/v1/visits/14/feedback/', catalogContext: 'signed-original'};
const posts = f => f.calls.filter(c => c.options.method === 'POST');
test('ordinary products have no controls and loading reads never POST', async () => {
    const f = fixture(), recommended = target(), ordinary = target(null,2);
    await f.load(context,[recommended,ordinary]);
    assert(ordinary.fields.actions.removed); assert(!recommended.fields.reject.disabled);
    assert.equal(posts(f).length,0); assert(f.calls.every(c=>c.options.cache==='no-store'));
});
test('PLANNED, completed and submitted-request states disable both decisions', async () => {
    for(const options of [{status:'PLANNED'},{status:'COMPLETED'},{request:{id:1,revision:0,status:'SUBMITTED'}}]) {
        const f=fixture({read:()=>history(options)}), t=target();await f.load(context,[t]);
        assert(t.fields.reject.disabled);assert(t.fields.later.disabled);assert(t.fields.guidance.textContent);assert.equal(posts(f).length,0);
    }
});
test('reject requires explicit reason and confirmation; opening/cancelling writes nothing', async () => {
    const f=fixture(),t=target();await f.load(context,[t]);t.fields.reject.click();
    assert(f.elements.feedbackDialog.open);assert(f.elements.feedbackReason.required);
    await f.submit();assert.equal(posts(f).length,0);assert.match(f.elements.feedbackMessage.textContent,/دلیل/);
    f.elements.feedbackCancel.click();assert(!f.elements.feedbackDialog.open);assert.equal(posts(f).length,0);
});
test('all seven reasons send exact codes with signed identity, UUID, revision and CSRF', async () => {
    for(const code of ['NOT_INTERESTED','PRICE','STOCK','NO_CURRENT_NEED','OTHER_BRAND','LATER','OTHER']) {
        const f=fixture({read:()=>history({request:{id:1,revision:3,status:'DRAFT'}})}), t=target();await f.load(context,[t]);
        t.fields.reject.click();f.elements.feedbackReason.value=code;await f.submit();
        assert.equal(posts(f).length,1);const call=posts(f)[0],body=JSON.parse(call.options.body);
        assert.equal(body.reason_code,code);assert.equal(body.catalog_context,'signed-original');assert.equal(body.recommendation_id,101);
        assert.equal(body.customer_code,'C');assert.equal(body.expected_request_revision,3);assert(body.command_uuid);
        assert.equal(call.options.headers['X-CSRFToken'],'masked-csrf-token');assert.equal(call.options.credentials,'same-origin');
    }
});
test('Later is explicitly confirmed and never displayed as rejected', async () => {
    const f=fixture(),t=target();await f.load(context,[t]);t.fields.later.click();
    assert(f.elements.feedbackReasonRow.hidden);assert.match(f.elements.feedbackTitle.textContent,/بعداً/);assert.equal(posts(f).length,0);
    await f.submit();assert.equal(JSON.parse(posts(f)[0].options.body).action,'LATER');
    assert.equal(t.fields.summary.textContent,'بعداً بررسی می‌کنم');assert(!f.elements.feedbackMessage.textContent.includes('رد'));
});
test('no optimistic success and double confirmation cannot send twice', async () => {
    let resolve;const f=fixture({post:payload=>new Promise(done=>{resolve=()=>done(success(payload));})}),t=target();await f.load(context,[t]);
    t.fields.later.click();const first=f.submit();await f.submit();assert.equal(posts(f).length,1);
    assert(f.elements.feedbackConfirm.disabled);assert(!t.fields.history.textContent);assert.match(f.elements.feedbackMessage.textContent,/در حال/);
    resolve();await first;assert.match(f.elements.feedbackMessage.textContent,/ثبت شد/);await f.submit();assert.equal(posts(f).length,1);
});
test('ambiguous network failure never auto-retries; manual retry preserves entire intent', async () => {
    let attempt=0;const f=fixture({post:payload=>{if(++attempt===1)throw Error('Network');return success(payload,true);}}),t=target();await f.load(context,[t]);
    t.fields.reject.click();f.elements.feedbackReason.value='PRICE';await f.submit();
    assert.equal(posts(f).length,1);assert.match(f.elements.feedbackMessage.textContent,/مشخص نیست/);assert(f.elements.feedbackReason.disabled);assert(!f.elements.feedbackRecovery.hidden);
    await f.submit();assert.equal(posts(f).length,2);assert.equal(posts(f)[0].options.body,posts(f)[1].options.body);assert.match(f.elements.feedbackMessage.textContent,/نتیجه قبلی/);
});
test('reload restores uncertain command without POST and reuses old signed context', async () => {
    const storage=new Map(),first=fixture({storage,post:()=>{throw Error('Network');}}),t=target();await first.load(context,[t]);t.fields.later.click();await first.submit();
    const original=posts(first)[0].options.body;
    const resumed=fixture({storage}),other=target();await resumed.load({...context,catalogContext:'new-context'},[other]);
    assert.equal(posts(resumed).length,0);resumed.elements.feedbackResume.click();await resumed.submit();assert.equal(posts(resumed)[0].options.body,original);
});
test('selected-product conflict disables actions and never reports success', async () => {
    const f=fixture({post:()=>({status:409,body:{code:'PRODUCT_ALREADY_SELECTED'}})}),t=target();await f.load(context,[t]);t.fields.later.click();await f.submit();
    assert(t.fields.reject.disabled);assert(t.fields.later.disabled);assert.match(f.elements.feedbackMessage.textContent,/انتخاب شده/);assert(!t.fields.history.textContent);
});
test('revision/context/command conflicts and authorization failures remain truthful', async () => {
    for(const code of ['REVISION_CONFLICT','CATALOG_CONTEXT_UNAVAILABLE','COMMAND_CONFLICT','VISIT_NOT_ACTIVE','REQUEST_NOT_DRAFT','ACCESS_DENIED']) {
        const f=fixture({post:()=>({status:code==='ACCESS_DENIED'?403:409,body:{code}})}),t=target();await f.load(context,[t]);t.fields.later.click();await f.submit();
        assert(!t.fields.history.textContent);assert(f.elements.feedbackConfirm.disabled);assert.equal(posts(f).length,1);
    }
});
test('history displays only saved records, including paginated Later without rejection wording', async () => {
    const f=fixture({read:url=>new URL(url,'http://localhost').searchParams.get('page')==='1'?history({page:1,pages:2,events:[{event_type:'REJECTED',recommendation_id:101,reason_code:'PRICE'}]}):history({page:2,pages:2,events:[{event_type:'REJECTED',recommendation_id:101,reason_code:'LATER'}]})}),t=target();
    await f.load(context,[t]);assert.equal(t.fields.summary.textContent,'بعداً بررسی می‌کنم');assert(!t.fields.history.textContent.includes('رد'));assert.equal(posts(f).length,0);
});
test('denied history keeps controls disabled; ordinary-only catalog does not read feedback', async () => {
    const f=fixture({read:()=>({status:403})}),t=target();await f.load(context,[t]);assert(t.fields.reject.disabled);assert.match(t.fields.guidance.textContent,/در دسترس نیست/);
    const plain=fixture();await plain.load(context,[target(null)]);assert.equal(plain.calls.length,0);
});
test('missing CSRF blocks POST, storage failures block fresh commands', async () => {
    const f=fixture(),t=target();await f.load(context,[t]);f.elements.feedbackForm.querySelector=()=>({value:''});t.fields.later.click();await f.submit();assert.equal(posts(f).length,0);
    const bad=fixture({storage:{get:()=>null,set:()=>{throw Error('Storage');}}}),other=target();await bad.load(context,[other]);other.fields.later.click();await bad.submit();assert.equal(posts(bad).length,0);
});
test('unrecognized prototype reason cannot substitute for one of seven choices', async () => {
    const f=fixture(),t=target();await f.load(context,[t]);t.fields.reject.click();f.elements.feedbackReason.value='constructor';await f.submit();assert.equal(posts(f).length,0);
});
test('unknown 201 payload is not success and remains recoverable with the same UUID', async () => {
    const f=fixture({post:()=>({status:201,body:{version:1,customer:{code:'FOREIGN'},visit:{id:14},feedback:{id:1}}})}),t=target();await f.load(context,[t]);t.fields.later.click();await f.submit();
    assert(!t.fields.history.textContent);assert(!f.elements.feedbackRecovery.hidden);assert.match(f.elements.feedbackMessage.textContent,/مشخص نیست/);
});
test('lost authorization after an ambiguous POST retains original recovery command', async () => {
    let attempt=0;const f=fixture({post:()=>{if(++attempt===1)throw Error('Network');return {status:403,body:{code:'ACCESS_DENIED'}};}}),t=target();await f.load(context,[t]);t.fields.later.click();await f.submit();await f.submit();
    assert.equal(posts(f)[0].options.body,posts(f)[1].options.body);assert(!f.elements.feedbackRecovery.hidden);assert(!t.fields.history.textContent);
});
test('confirmed rejection collapses dialog/options and includes every selected reason', async () => {
    for (const code of ['NOT_INTERESTED','PRICE','STOCK','NO_CURRENT_NEED','OTHER_BRAND','LATER','OTHER']) {
        const f=fixture(),t=target();await f.load(context,[t]);t.fields.actions.open=true;t.fields.reject.click();f.elements.feedbackReason.value=code;await f.submit();
        assert(!f.elements.feedbackDialog.open);assert.equal(t.fields.actions.open,false);assert(t.fields.options.hidden);assert(!t.fields.change.hidden);
        assert(t.fields.summary.focused);assert.equal(t.fields['history-list'].children.length,1);
        assert(t.fields['history-list'].children[0].textContent);assert(f.elements.feedbackNotice.textContent.startsWith('ثبت شد'));
        if(code==='LATER')assert.equal(t.fields.summary.textContent,'بعداً بررسی می‌کنم');
        else assert(t.fields.summary.textContent.startsWith('رد پیشنهاد · '));
    }
});
test('saved decisions hide redundant actions until explicit change, then append a fresh command', async () => {
    const prior={id:3,event_type:'REJECTED',recommendation_id:101,reason_code:'PRICE'};
    const f=fixture({read:()=>history({events:[prior]}),post:payload=>success(payload)}),t=target();await f.load(context,[t]);
    assert(t.fields.options.hidden);assert(!t.fields.change.hidden);assert.match(t.fields.summary.textContent,/قیمت نامناسب/);
    t.fields.change.click();assert(!t.fields.options.hidden);assert(t.fields.change.hidden);assert.equal(posts(f).length,0);
    t.fields.later.click();await f.submit();assert.equal(t.fields['history-list'].children.length,2);
    assert.match(t.fields['history-list'].children[0].textContent,/قیمت مناسب نبود/);assert.equal(t.fields['history-list'].children[1].textContent,'بعداً بررسی می‌کنم');
    assert.equal(prior.reason_code,'PRICE');assert(t.fields.options.hidden);assert.equal(posts(f).length,1);
    t.fields.change.click();t.fields.reject.click();f.elements.feedbackReason.value='OTHER';await f.submit();
    assert.notEqual(JSON.parse(posts(f)[0].options.body).command_uuid,JSON.parse(posts(f)[1].options.body).command_uuid);
});
test('PLANNED saved history remains accessible without a change action', async () => {
    const f=fixture({read:()=>history({status:'PLANNED',events:[{id:1,event_type:'REJECTED',recommendation_id:101,reason_code:'LATER'}]})}),t=target();await f.load(context,[t]);
    assert.equal(t.fields.summary.textContent,'بعداً بررسی می‌کنم');assert(!t.fields['history-list'].hidden);assert(t.fields.options.hidden);assert(t.fields.change.hidden);
    assert.equal(posts(f).length,0);
});
