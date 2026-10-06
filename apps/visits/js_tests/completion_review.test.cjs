/* Production controller exercised with isolated DOM/network fixtures. */
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/visits/js/completion_review.js'), 'utf8');
class Element {
    constructor() { this.listeners = {}; this.dataset = {}; this.hidden = false; this.disabled = false; this.open = false; }
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
    fire(type, extra = {}) { return Promise.all((this.listeners[type] || []).map(fn => fn({preventDefault(){}, ...extra}))); }
    setAttribute(name, value) { this[name] = value; }
    focus() { this.focused = true; }
    showModal() { this.open = true; }
    close() { this.open = false; this.fire('close'); }
}
const response = (status = 'IN_PROGRESS', ok = true) => ({ok, status:ok ? 200 : 400,
    json:async()=>({success:ok, visit:{id:14, customer_code:'FIXTURE', status}})});
function fixture({post = async()=>response('COMPLETED'), read = async()=>response(), initial = 'IN_PROGRESS'} = {}) {
    const nodes = new Map();
    for (const id of ['visitReview','finishVisitButton','confirmFinishVisit','cancelFinishVisit','finishVisitDialog',
        'reviewRefresh','finishPendingStatus','reviewError','finishDialogError','reviewVisitStatus','reviewPanel',
        'completionAcknowledgement','completionTitle','reviewReadStatus','visitCompletionForm']) nodes.set(id, new Element());
    nodes.get('visitReview').dataset = {status:initial, visitId:'14', customerCode:'FIXTURE', readUrl:'/canonical', completeUrl:'/complete'};
    nodes.get('visitCompletionForm').querySelector = () => ({value:'csrf-fixture'});
    const requests = []; let reads = 0, reloads = 0;
    const window = new Element(); window.location = {reload(){reloads++;}};
    vm.runInNewContext(source, {document:{getElementById:id=>nodes.get(id)}, window,
        fetch:async(url, options)=>{requests.push({url,...options});return options.method==='POST' ? post(options) : read(++reads);}});
    return {nodes,requests,window,reloads:()=>reloads,posts:()=>requests.filter(r=>r.method==='POST'),
        click:id=>nodes.get(id).fire('click')};
}
async function settle() { for(let i=0;i<30;i++) await Promise.resolve(); }
async function open(f) { await settle(); await f.click('finishVisitButton'); }
async function run() {
    const passive = fixture(); await open(passive);
    assert.equal(passive.nodes.get('finishVisitDialog').open, true);
    await passive.click('cancelFinishVisit');
    assert.equal(passive.posts().length, 0);
    assert.equal(passive.nodes.get('finishVisitButton').focused, true);
    console.log('PASS GET, opening and cancelling never complete the visit');

    let resolvePost;
    const pending = fixture({post:()=>new Promise(resolve=>{resolvePost=resolve;})}); await open(pending);
    const first = pending.click('confirmFinishVisit'), second = pending.click('confirmFinishVisit'); await settle();
    assert.equal(pending.posts().length, 1); assert.equal(pending.nodes.get('confirmFinishVisit').disabled, true);
    await pending.click('cancelFinishVisit'); assert.equal(pending.nodes.get('finishVisitDialog').open, true);
    resolvePost(response('COMPLETED')); await Promise.all([first,second]);
    assert.equal(pending.nodes.get('reviewPanel').hidden, true);
    assert.equal(pending.nodes.get('completionAcknowledgement').hidden, false);
    assert.equal(pending.posts()[0].headers['X-CSRFToken'], 'csrf-fixture');
    assert.deepEqual(JSON.parse(pending.posts()[0].body), {customer_code:'FIXTURE'});
    console.log('PASS confirmation-only POST, pending duplicate guard, CSRF/customer payload and acknowledgement');

    for (const [label,post] of [
        ['dropped',async()=>{throw new Error('lost response');}],
        ['repeated',async()=>response('COMPLETED',false)],
        ['malformed',async()=>({ok:true,json:async()=>{throw new SyntaxError('invalid');}})]]) {
        const f = fixture({post, read:async n=>response(n===1?'IN_PROGRESS':'COMPLETED')});
        await open(f); await f.click('confirmFinishVisit');
        assert.equal(f.posts().length, 1); assert.equal(f.requests.filter(r=>r.method==='GET').length, 2);
        assert.equal(f.nodes.get('completionAcknowledgement').hidden, false);
        assert.equal(f.nodes.get('confirmFinishVisit').disabled, true);
        console.log('PASS '+label+' completion response rereads status without POST retry');
    }

    const failed = fixture({post:async()=>response('IN_PROGRESS',false)}); await open(failed); await failed.click('confirmFinishVisit');
    assert.equal(failed.posts().length,1); assert.equal(failed.nodes.get('confirmFinishVisit').disabled,false);
    assert.equal(failed.nodes.get('finishDialogError').hidden,false);
    assert.equal(failed.nodes.get('reviewPanel').hidden,false);
    console.log('PASS rejected completion stays recoverable with explicit confirmation and visible error');

    const unknown = fixture({post:async()=>{throw Error('network');}, read:async n=>n===2?{ok:false,status:500}:response()});
    await open(unknown); await unknown.click('confirmFinishVisit');
    assert.equal(unknown.nodes.get('confirmFinishVisit').disabled,true);
    assert.equal(unknown.nodes.get('reviewRefresh').hidden,false);
    await unknown.click('reviewRefresh');
    assert.equal(unknown.nodes.get('confirmFinishVisit').disabled,false); assert.equal(unknown.posts().length,1);
    console.log('PASS unknown status blocks repeat completion until manual canonical GET succeeds');

    const denied = fixture({read:async()=>({ok:false,status:404})}); await open(denied);
    await denied.click('confirmFinishVisit'); assert.equal(denied.posts().length,0);
    const wrong = fixture({read:async()=>({ok:true,json:async()=>({visit:{id:99,customer_code:'FOREIGN',status:'IN_PROGRESS'}})})});
    await open(wrong); assert.equal(wrong.nodes.get('finishVisitButton').disabled,true);
    console.log('PASS denied or mismatched canonical context prevents completion');

    const done = fixture({initial:'COMPLETED'}); await settle();
    assert.equal(done.requests.length,0); assert.equal(done.nodes.get('confirmFinishVisit').disabled,true);
    await done.window.fire('pageshow',{persisted:true}); assert.equal(done.reloads(),1);
    console.log('PASS completed documents remain read-only and BFcache restores rerender canonical counts');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
