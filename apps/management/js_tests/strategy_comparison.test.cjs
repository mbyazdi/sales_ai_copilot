const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ui = require('../../../static/management/js/strategy_comparison.js');
function fixture() {
    const row = (id, rank) => ({source: {recommendation_id: id, product_id: id, saved_rank: id,
        base_score: id === 3 ? '70.0000' : '40.0000', commercial: {stock_state: 'AVAILABLE', pricing_state: 'AVAILABLE', sellable_quantity: 10}},
        product: {product_id: id, product_code: 'P'+id, is_active: true}, after_rank: rank, original_position: id,
        base_priority: id === 3 ? '10.00' : '30.00', priority: {points: '20.00', reasons: [{code: 'PRIORITY_APPLIED', text_fa: 'اولویت مدیریتی اعمال شد.'}]},
        target: {points: '2.50', reasons: [{code: 'TARGET_APPLIED', text_fa: 'سهم هدف اعمال شد.'}]},
        promotion: {points: '5.00', reasons: [{code: 'PROMOTION_APPLIED', text_fa: 'قیمت تغییر نمی‌کند.'}]},
        overlay_adjustment: '27.50', effective_priority: id === 3 ? '37.50' : '30.00'});
    return {comparison_id: 2, customer_id: 1, salesperson_id: 7, policy_revision: 3, before_version_id: 1, after_version_id: 2,
        evaluation_date: '2026-10-16', labels: {customer: {id: 1, name: 'مشتری تاریخی', code: 'C1'}, salesperson: {id: 7, name: 'فروشنده تاریخی', code: 'SP1'},
            products: [1,2,3,4].map(id => ({id, name: 'محصول '+id, code: 'P'+id}))},
        outputs: {schema_version: 1, simulation_only: true, revenue_uplift: null,
            before: {after_ids: [1,2,3,4], rows: [1,2,3,4].map((id,index) => row(id,index+1))},
            after: {after_ids: [3,1,2,4], rows: [3,1,2,4].map((id,index) => row(id,index+1))},
            movements: [3,1,2,4].map(id => ({recommendation_id: id, before_rank: id, after_rank: [3,1,2,4].indexOf(id)+1,
                positions_gained: id-([3,1,2,4].indexOf(id)+1)}))},
        quotes: {'3': {state: 'AVAILABLE', quote: {final_unit_price: '90', currency: 'TOMAN', price_source: 'SYNTHETIC_TEST_ONLY'}}}};
}
class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this.dataset={}; this.attributes={}; this.listeners={}; this.hidden=false; this.disabled=false; this.ownText=''; }
    set textContent(value) { this.ownText=String(value); this.children=[]; }
    get textContent() { return this.ownText+this.children.map(c=>c.textContent).join(''); }
    set innerHTML(value) { throw new Error('Unsafe HTML sink'); }
    append(...items) { this.children.push(...items); }
    replaceChildren(...items) { this.ownText=''; this.children=items; }
    setAttribute(key,value) { this.attributes[key]=value; }
    removeAttribute(key) { delete this.attributes[key]; }
    contains(node) { return this===node || this.children.some(child=>child.contains(node)); }
    focus() { this.ownerDocument.activeElement=this; }
    addEventListener(key,handler) { this.listeners[key]=handler; }
    querySelector(key) { if (!this.fields.has(key)) { const node=new Element();node.ownerDocument=this.ownerDocument;this.fields.set(key,node); } return this.fields.get(key); }
}
function dom() { const root=new Element(); root.fields=new Map(); root.dataset={comparisonId:'2',apiUrl:'/api/management/v1/strategy/comparisons/2/'};
    const document={activeElement:null,createElement:tag=>{const node=new Element(tag);node.ownerDocument=document;return node;}};
    root.ownerDocument=document;return {root,document}; }
function responsive(matches) {
    const elements=dom();const media={matches,addEventListener(event,handler){assert.equal(event,'change');this.change=handler;}};
    ui.setupResponsiveComparison(elements.document,elements.root,media);return {...elements,media};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('server order, movement and default moved selection are retained without source mutation',()=>{
    const data=fixture(), original=structuredClone(data), {root,document}=dom(); ui.render(document,root,ui.validate(data,2));
    assert.deepEqual(root.querySelector('#beforeRanking').children.map(li=>li.children[0].dataset.recommendationId),['1','2','3','4']);
    assert.deepEqual(root.querySelector('#afterRanking').children.map(li=>li.children[0].dataset.recommendationId),['3','1','2','4']);
    assert.match(root.querySelector('#focusFactors').textContent,/۷۰٫۰۰۰۰/); assert.match(root.querySelector('#focusFactors').textContent,/۳۷٫۵۰/);
    assert.equal(root.querySelector('#focusSummary').children[0].textContent,'امتیاز ذخیره‌شدهٔ موتور۷۰٫۰۰۰۰');
    assert.equal(root.querySelector('#focusSummary').children[1].textContent,'اولویت مؤثر۳۷٫۵۰');
    assert.match(root.querySelector('[data-field="focus-movement"]').textContent,/۲ رتبه صعود/);
    assert.deepEqual(data,original);
});
test('Before uses captured active policy order even when it differs from saved rank',()=>{
    const data=fixture(); data.outputs.before=structuredClone(data.outputs.after);
    data.outputs.movements.forEach(m=>{m.before_rank=m.after_rank;m.positions_gained=0;});
    const {root,document}=dom(); ui.render(document,root,ui.validate(data,2));
    assert.equal(root.querySelector('#beforeRanking').children[0].children[0].dataset.recommendationId,'3');
    assert.match(root.querySelector('#focusRanks').textContent,/رتبهٔ ذخیره‌شده۳/);
    assert.match(root.querySelector('#focusRanks').textContent,/رتبهٔ سیاست پیشین۱/);
});
test('selection preserves the existing button node and keyboard focus target',()=>{
    const {root,document}=dom(); ui.render(document,root,ui.validate(fixture(),2));
    const button=root.querySelector('#beforeRanking').children[1].children[0];
    button.listeners.click();
    assert.equal(root.querySelector('#beforeRanking').children[1].children[0],button);
    assert.equal(button.attributes['aria-pressed'],'true'); assert.match(root.querySelector('#explanationTitle').textContent,/P2/);
});
test('API text is escaped by construction; no HTML parsing or current-data fetches',()=>{
    const data=fixture(); const payload='<img src=x onerror="globalThis.compromised=true">';
    data.labels.products[2].name=payload; data.labels.customer.name=payload;
    data.outputs.after.rows[0].priority.reasons[0].text_fa=payload;
    const {root,document}=dom(); ui.render(document,root,ui.validate(data,2));
    assert.match(root.querySelector('#explanationTitle').textContent,/<img/);
    assert.match(root.querySelector('#focusReasons').textContent,/<img/);
    assert.equal(globalThis.compromised,undefined);
    const source=fs.readFileSync(require.resolve('../../../static/management/js/strategy_comparison.js'),'utf8');
    assert.doesNotMatch(source,/innerHTML|insertAdjacentHTML|eval\(|\.sort\(|parseFloat\(/);
});
test('missing labels, stock and prices remain truthful, distinct and never invented zero',()=>{
    const data=fixture(); delete data.labels; delete data.quotes;
    data.outputs.after.rows[0].source.commercial={stock_state:'UNKNOWN',pricing_state:'UNAVAILABLE',sellable_quantity:null};
    const {root,document}=dom(); ui.render(document,root,ui.validate(data,2));
    assert.equal(root.querySelector('[data-field="customer-name"]').textContent,'مشتری ۱');
    assert.match(root.querySelector('#explanationTitle').textContent,/P3/);
    assert.match(root.querySelector('#focusCommercial').textContent,/نامشخص/);
    assert.match(root.querySelector('#focusCommercial').textContent,/ثبت نشده/);
    assert.equal(ui.format(null),'ثبت نشده'); assert.equal(ui.format('0'),'۰');
    assert.equal(ui.availability({...data.outputs.after.rows[0],source:{commercial:{stock_state:'UNAVAILABLE'}}}),'موجودی قابل فروش نداشت');
});
test('empty saved shortlist has an explicit state and no invented focused product',()=>{
    const data=fixture(); for(const side of ['before','after']) data.outputs[side]={rows:[],after_ids:[]}; data.outputs.movements=[];
    const {root,document}=dom(); ui.render(document,root,ui.validate(data,2));
    assert.equal(root.querySelector('#comparisonEmpty').hidden,false); assert.equal(root.querySelector('#explanation').hidden,true);
});
test('invalid identities/order/values fail closed',()=>{
    for(const edit of [d=>d.comparison_id=3,d=>d.outputs.after.after_ids.reverse(),d=>d.outputs.after.rows[0].source.base_score=null,
        d=>d.outputs.after.rows[0].effective_priority=37.5,d=>d.outputs.movements.pop(),d=>d.outputs.simulation_only=false]){
        const data=fixture();edit(data);assert.throws(()=>ui.validate(data,2));
    }
});
for(const status of [401,403,404,409,503]) test('HTTP '+status+' is a Persian accessible error, no automatic retry',async()=>{
    const {root,document}=dom();let calls=0;
    ui.attach(document,root,async(url,options)=>{calls++;assert.equal(options.method,'GET');return {ok:false,status};});
    await settle();assert.equal(calls,1);assert.equal(root.querySelector('#comparisonError').hidden,false);
    assert.equal(root.querySelector('#comparisonErrorText').textContent,ui.ERRORS[status]);
    assert.equal(root.querySelector('#comparisonLogin').hidden,status!==401);
});
test('network failure allows explicit GET retry only',async()=>{
    const {root,document}=dom();let calls=0;
    const app=ui.attach(document,root,async(url,options)=>{assert.equal(options.credentials,'same-origin');assert.equal(options.method,'GET');
        calls++;if(calls===1)throw new Error('offline');return {ok:true,json:async()=>fixture()};});
    await settle();assert.equal(calls,1);await app.load();assert.equal(calls,2);assert.equal(root.querySelector('#comparisonContent').hidden,false);
});
test('late responses never replace the newer read result',async()=>{
    const {root,document}=dom();let resolve;let count=0;
    const app=ui.attach(document,root,()=>++count===1?new Promise(r=>resolve=r):Promise.resolve({ok:true,json:async()=>fixture()}));
    await app.load();resolve({ok:false,status:403});await settle();assert.equal(root.querySelector('#comparisonError').hidden,true);
});
test('arbitrary URLs are rejected before fetch',async()=>{
    const {root,document}=dom();root.dataset.apiUrl='https://external.invalid/';let calls=0;
    ui.attach(document,root,async()=>{calls++;});await settle();assert.equal(calls,0);assert.equal(root.querySelector('#comparisonError').hidden,false);
});

test('mobile defaults to After, shows only one panel and leaves all frozen rows untouched',()=>{
    const {root,document}=responsive(true);const data=fixture(), original=structuredClone(data);
    ui.render(document,root,ui.validate(data,2));
    assert.equal(root.querySelector('#comparisonTabs').hidden,false);
    assert.equal(root.querySelector('#beforePanel').hidden,true);
    assert.equal(root.querySelector('#afterPanel').hidden,false);
    assert.equal(root.querySelector('#afterTab').attributes['aria-selected'],'true');
    assert.equal(root.querySelector('#afterTab').tabIndex,0);
    assert.equal(root.querySelector('#afterPanel').attributes.role,'tabpanel');
    assert.equal(root.querySelector('#afterPanel').attributes['aria-labelledby'],'afterTab');
    assert.equal(root.querySelector('#focusDetails').open,false);
    root.querySelector('#beforeTab').listeners.click();
    assert.equal(root.querySelector('#beforePanel').hidden,false);
    assert.equal(root.querySelector('#afterPanel').hidden,true);
    assert.deepEqual(data,original);
    assert.equal(root.querySelector('#beforeRanking').children.length,4);
});

test('mobile tabs support RTL arrow keys, Home/End and one tab stop',()=>{
    const {root,document}=responsive(true);
    for(const [from,key,to] of [['after','ArrowRight','before'],['before','ArrowLeft','after'],['after','Home','before'],['before','End','after']]) {
        let prevented=false;
        root.querySelector('#'+from+'Tab').listeners.keydown({key,preventDefault(){prevented=true;}});
        assert.equal(prevented,true);assert.equal(document.activeElement,root.querySelector('#'+to+'Tab'));
        assert.equal(root.querySelector('#'+to+'Tab').attributes['aria-selected'],'true');
        assert.equal(root.querySelector('#'+to+'Tab').tabIndex,0);
        assert.equal(root.querySelector('#'+from+'Tab').tabIndex,-1);
    }
    root.querySelector('#afterTab').listeners.keydown({key:'Tab',preventDefault(){throw new Error('Must not trap Tab');}});
});

test('desktop/tablet restore both panels without hiding the focused mobile tab',()=>{
    const {root,document,media}=responsive(true);
    root.querySelector('#afterTab').focus();media.matches=false;media.change();
    assert.equal(root.querySelector('#comparisonTabs').hidden,true);
    for(const side of ['before','after']){
        assert.equal(root.querySelector('#'+side+'Panel').hidden,false);
        assert.equal(root.querySelector('#'+side+'Panel').attributes.role,undefined);
        assert.equal(root.querySelector('#'+side+'Panel').attributes['aria-labelledby'],side+'Title');
    }
    assert.equal(document.activeElement,root.querySelector('#afterPanel'));
    assert.equal(root.querySelector('#focusDetails').open,true);
});

test('desktop-to-mobile resizing moves focus out of a panel that becomes hidden',()=>{
    const {root,document,media}=responsive(false);
    const button=document.createElement('button');root.querySelector('#beforePanel').append(button);button.focus();
    media.matches=true;media.change();
    assert.equal(document.activeElement,root.querySelector('#afterTab'));
    assert.equal(root.querySelector('#beforePanel').hidden,true);
});

test('explicit mobile disclosure choice survives product selection and safe read refresh',()=>{
    const {root,document}=responsive(true);const data=fixture();ui.render(document,root,ui.validate(data,2));
    root.querySelector('#focusDetails').open=true;
    root.querySelector('#afterRanking').children[1].children[0].listeners.click();
    assert.equal(root.querySelector('#focusDetails').open,true);
    assert.match(root.querySelector('#focusFactors').textContent,/اولویت پایهٔ بازچینی/);
    assert.match(root.querySelector('#focusReasons').textContent,/سهم هدف اعمال شد/);
    ui.render(document,root,ui.validate(data,2));assert.equal(root.querySelector('#focusDetails').open,true);
});

test('largest server-reported upward movement is highlighted without changing list order',()=>{
    const {root,document}=dom();ui.render(document,root,ui.validate(fixture(),2));
    for(const side of ['before','after']){
        const buttons=root.querySelector('#'+side+'Ranking').children.map(li=>li.children[0]);
        const highlighted=buttons.filter(button=>button.textContent.includes('بیشترین صعود'));
        assert.equal(highlighted.length,1);assert.equal(highlighted[0].dataset.recommendationId,'3');
    }
});
