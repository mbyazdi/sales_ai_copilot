/* Isolated DOM/fetch fixtures for the production interaction; no dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/core/js/recommendation_outcome.js'), 'utf8');
class Element {
    constructor() { this.dataset = {}; this.listeners = {}; this.hidden = false; this.disabled = false; this.value = ''; this.textContent = ''; this.classList = {add(){}, remove(){}}; }
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
    fire(type, extra = {}) { return Promise.all((this.listeners[type] || []).map(fn => fn({preventDefault(){}, target:this, ...extra}))); }
    setAttribute(name, value) { this[name] = value; }
    focus() { this.document.activeElement = this; }
    scrollIntoView() { this.scrolled = true; }
    getClientRects() { return this.hidden ? [] : [{}]; }
}
function fixture({post, preflight = true, manager = false, guided = false, unavailable = false} = {}) {
    const nodes = new Map(), element = id => { const node = new Element(); nodes.set(id, node); return node; };
    const root = element('workspace-recommendations'), region = element('visitOutcomeRegion');
    if(guided)root.dataset.guided='true';
    region.dataset = {readUrl:'/canonical', visitId:'14', customerCode:'FIXTURE'};
    for (const id of ['visitOutcomeReadStatus','visitOutcomeRefresh','outcomeModal','outcomeForm','outcomeSubmit','outcomeQuantity',
        'outcomeSalesAmount','outcomeModalProduct','outcomeModalOutcome','outcomeModalVisit','outcomeModalCurrent','outcomeFollowUpDateGroup',
        'outcomeFollowUpDate','outcomeNotes','outcomeError','outcomeSuccess','outcomeModalClose','outcomeCancel']) element(id);
    const form = nodes.get('outcomeForm'), modal = nodes.get('outcomeModal'), token = new Element(), values = new Element();
    token.value = 'fixture-csrf-token';
    form.reset = () => {};
    form.checkValidity = () => !nodes.get('outcomeFollowUpDate').required || !!nodes.get('outcomeFollowUpDate').value;
    form.reportValidity = () => {};
    form.querySelector = () => token;
    modal.querySelector = () => values;
    modal.querySelectorAll = () => [nodes.get('outcomeModalClose'), nodes.get('outcomeNotes'), nodes.get('outcomeSubmit')];
    modal.hidden = true;
    const card = new Element(), details = new Element(), statusBox = new Element(), statusValue = new Element(), title = new Element();
    card.id = 'recommendation-424'; card.dataset = {recommendationId:'424', productCode:'FIXTURE-P'};
    title.textContent = 'Fixture Product';
    card.querySelector = selector => selector === 'details' ? details : selector === '.recommendation-product-name' ? title : statusBox;
    statusBox.querySelector = () => statusValue;
    const buttons = ['PURCHASED','INTERESTED','FOLLOW_UP','REJECTED','NOT_PRESENTED'].map(outcome => {
        const button = new Element(); button.dataset = {outcome}; button.closest = () => card; return button;
    });
    if(unavailable)buttons.forEach(button=>{button.dataset.unavailable='true';});
    root.querySelectorAll = selector => selector === '.outcome-btn' ? buttons : [card];
    const doc = new Element(); doc.getElementById = id => manager && ['visitOutcomeRegion','outcomeModal','outcomeForm'].includes(id) ? null : nodes.get(id);
    doc.body = new Element(); doc.dispatchEvent = event => doc.fire(event.type);
    for (const node of [...nodes.values(), doc, doc.body, card, details, ...buttons]) node.document = doc;
    const requests = [];
    let current = [], gets = 0;
    const readResponse = () => ({ok:preflight || gets < 2, status:preflight || gets < 2 ? 200 : 404,
        json:async()=>({visit:{id:14,customer_code:'FIXTURE',visit_date:'2026-10-05'},can_record:true,recommendation_outcomes:current})});
    const fetch = async (url, options) => {
        requests.push({url, ...options});
        if(options.method === 'GET') { gets++; return readResponse(); }
        if(post) return post(options);
        current = [{recommendation_id:424, final_outcome:'PURCHASED', quantity:3, sales_amount:700}];
        return {ok:true,status:201,json:async()=>({success:true,sales_outcome:{quantity:0,sales_amount:0}})};
    };
    vm.runInNewContext(source, {document:doc,window:{addEventListener(){}},location:{hash:'#recommendation-424'},fetch,
        Intl,Number,Map,Promise,CustomEvent:class {constructor(type){this.type=type;}}});
    return {nodes,card,details,buttons,form,statusValue,requests,gets:()=>gets,doc};
}
async function settle() { for(let i=0;i<30;i++) await Promise.resolve(); }
async function run() {
    let resolvePost;
    const pendingPost = new Promise(resolve=>{resolvePost=resolve;});
    const f = fixture({post:()=>pendingPost});
    await settle();
    assert.equal(f.doc.activeElement, f.card); assert.equal(f.details.open,true); assert.equal(f.nodes.get('outcomeModal').hidden,true);
    await f.buttons[0].fire('click');
    const first = f.form.fire('submit'); const second = f.form.fire('submit');
    await settle();
    assert.equal(f.requests.filter(r=>r.method==='POST').length,1);
    assert.equal(f.nodes.get('outcomeSubmit').disabled,true);
    const request = f.requests.find(r=>r.method==='POST');
    assert.equal(request.headers['X-CSRFToken'],'fixture-csrf-token');
    assert.equal(JSON.parse(request.body).customer_code,'FIXTURE');
    resolvePost({ok:false,status:400,json:async()=>({detail:'invalid'})});
    await Promise.all([first,second]);
    assert.equal(f.nodes.get('outcomeSuccess').hidden,true);
    assert.equal(f.nodes.get('outcomeError').hidden,false);
    assert.equal(f.requests.filter(r=>r.method==='POST').length,1);
    console.log('PASS pending duplicate guard, CSRF/context payload and failed submission');

    const success = fixture(); await settle(); await success.buttons[0].fire('click'); await success.form.fire('submit');
    assert(success.statusValue.textContent.includes(new Intl.NumberFormat('fa-IR').format(700)));
    assert.equal(success.nodes.get('outcomeSubmit').disabled,true);
    await success.form.fire('submit');
    assert.equal(success.requests.filter(r=>r.method==='POST').length,1);
    console.log('PASS canonical read after success, no raw-event fallback or repeated saved submission');

    const network = fixture({post:async()=>{throw new Error('network');}}); await settle();
    await network.buttons[1].fire('click'); await network.form.fire('submit');
    assert.equal(network.nodes.get('outcomeSuccess').hidden,true);
    assert.equal(network.requests.filter(r=>r.method==='POST').length,1);
    console.log('PASS network failure never reports success or automatically retries POST');

    const revoked = fixture({preflight:false}); await settle(); await revoked.buttons[0].fire('click'); await revoked.form.fire('submit');
    assert.equal(revoked.requests.filter(r=>r.method==='POST').length,0);
    assert.equal(revoked.nodes.get('outcomeSuccess').hidden,true);
    console.log('PASS failed access preflight prevents submission');

    const readOnly = fixture({manager:true}); await settle();
    assert.equal(readOnly.requests.length,0); assert.equal(readOnly.details.open,true);
    console.log('PASS manager return focus is read-only and makes no operational reads');

    const guided=fixture({guided:true});await settle();
    assert.equal(guided.details.open,undefined);assert.equal(guided.nodes.get('outcomeModal').hidden,true);
    await guided.buttons[0].fire('click');await guided.form.fire('submit');
    assert(guided.statusValue.textContent.includes(new Intl.NumberFormat('fa-IR').format(700)));
    console.log('PASS guided return keeps explanation optional and preserves canonical outcome submission');

    const unavailable=fixture({guided:true,unavailable:true});await settle();
    assert(unavailable.buttons.every(button=>button.disabled));
    console.log('PASS unavailable product never enables outcome buttons');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
