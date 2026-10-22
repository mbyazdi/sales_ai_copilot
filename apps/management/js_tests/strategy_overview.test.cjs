const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ui=require('../../../static/management/js/strategy_overview.js');
function fixture(){return {
    head:{schema_version:1,algorithm_version:'OVERLAY_TEST_V1',revision:9,version_count:4,comparison_count:7,active_version_id:2,draft_version_id:3,
        active_config:{schema_version:1,priority_rules:[{scope_type:'PRODUCT',scope_id:10,points:20},{scope_type:'BRAND',scope_id:20,points:0},{scope_type:'CATEGORY',scope_id:30,points:8}],target_weight:5,promotion_rules:[{promotion_id:40,points:4}]},
        selling_context_integration:true,impact_available:false,limitations_fa:'اثر واقعی بر فروش اندازه‌گیری نشده است.'},
    options:{schema_version:1,algorithm_version:'OVERLAY_TEST_V1',priority_scopes:['PRODUCT','BRAND','CATEGORY'],priority_bounds:[0,20],target_weight_bounds:[0,5],promotion_points_bounds:[0,5],adjustment_cap:30},
    history:{results:[{id:1,published:true,created_at:'2026-10-16T12:00:00Z',config_hash:'DO_NOT_RENDER',author_id:999},{id:2,published:true,created_at:'2026-10-16T13:00:00Z'},{id:3,published:false,created_at:'2026-10-16T14:00:00Z'}],next_after_id:3}
};}
class Element {
    constructor(tag='div'){this.tagName=tag;this.children=[];this.ownText='';this.hidden=false;this.disabled=false;this.attributes={};this.listeners={};this.dataset={};}
    set textContent(value){this.ownText=String(value);this.children=[];}
    get textContent(){return this.ownText+this.children.map(c=>c.textContent).join('');}
    set innerHTML(value){throw Error('Unsafe HTML');}
    append(...children){this.children.push(...children);}
    replaceChildren(...children){this.ownText='';this.children=children;}
    setAttribute(key,value){this.attributes[key]=value;}
    addEventListener(key,handler){this.listeners[key]=handler;}
}
function dom(){const root=new Element(),fields=new Map();root.querySelector=key=>{if(!fields.has(key))fields.set(key,new Element());return fields.get(key);};
    return {root,document:{createElement:tag=>new Element(tag)},fields};}
const field=(root,name)=>root.querySelector('[data-overview-field="'+name+'"]');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function server(data=fixture()){
    return async url=>{
        if(url.endsWith('overview/'))return {ok:true,json:async()=>data.head};
        if(url.endsWith('options/?'))return {ok:true,json:async()=>data.options};
        if(url.includes('versions/'))return {ok:true,json:async()=>data.history};
        return {ok:true,json:async()=>({results:[]})};
    };
}
test('configuration and exact server counts are rendered separately from unavailable impact',()=>{
    const {head,options}=fixture(),{root,document}=dom(),original=structuredClone(head);
    ui.render(document,root,ui.validate(head,options),{products:[{id:10,name:'محصول نمونه'}],brands:[{id:20,name:'برند'}],categories:[{id:30,name:'گروه'}],promotions:[{id:40,name:'برنامه'}]});
    assert.equal(field(root,'comparisons').textContent,'۷');assert.equal(field(root,'revision').textContent,'۹');assert.equal(field(root,'versions').textContent,'۴');
    assert.equal(field(root,'active').textContent,'نسخهٔ ۲');assert.equal(field(root,'draft').textContent,'نسخهٔ ۳');assert.equal(field(root,'target').textContent,'۵ امتیاز');
    assert.match(root.querySelector('#overviewPriorities').textContent,/برند.*۰ امتیاز/);assert.match(root.querySelector('#overviewPromotions').textContent,/۴ امتیاز/);
    assert.match(root.querySelector('#promotionBounds').textContent,/۳۰ امتیاز/);assert.deepEqual(head,original);
});
test('neutral first-use state and no draft use actual empty facts without initializing anything',()=>{
    const {head,options}=fixture();Object.assign(head,{active_version_id:null,draft_version_id:null,version_count:0,comparison_count:0,revision:0});
    head.active_config={schema_version:1,priority_rules:[],target_weight:0,promotion_rules:[]};const {root,document}=dom();
    ui.render(document,root,ui.validate(head,options));assert.equal(field(root,'active').textContent,'سیاست خنثی');assert.equal(field(root,'draft').textContent,'پیش‌نویس ندارد');
    assert.equal(root.querySelector('#overviewPriorityEmpty').hidden,false);assert.equal(root.querySelector('#overviewPromotionEmpty').hidden,false);assert.equal(field(root,'comparisons').textContent,'۰');
});
test('missing reference titles use stable IDs and an explicit notice, never invented labels',()=>{
    const {head,options}=fixture(),{root,document}=dom();ui.render(document,root,ui.validate(head,options));
    assert.match(root.querySelector('#overviewPriorities').textContent,/محصول با شناسهٔ ۱۰/);assert.match(root.querySelector('#overviewPromotions').textContent,/شناسهٔ ۴۰/);
    assert.equal(root.querySelector('#overviewReferenceNotice').hidden,false);
});
test('API text is safe text; histories never display hashes, author IDs or raw configs',()=>{
    const {head,options,history}=fixture(),{root,document}=dom(),payload='<img src=x onerror=alert(1)>';
    ui.render(document,root,ui.validate(head,options),{products:[{id:10,name:payload}]});ui.renderHistory(document,root,head,history.results);
    assert.match(root.querySelector('#overviewPriorities').textContent,/<img/);assert.doesNotMatch(root.querySelector('#overviewHistory').textContent,/DO_NOT_RENDER|999|config_hash/);
    const source=fs.readFileSync(require.resolve('../../../static/management/js/strategy_overview.js'),'utf8');assert.doesNotMatch(source,/innerHTML|insertAdjacentHTML|eval\(|\.sort\(|parseFloat\(|method:\s*['"]POST/);
});
test('history distinguishes creation time, past publication, active and current draft',()=>{
    const {head,history}=fixture(),{root,document}=dom();ui.renderHistory(document,root,head,ui.historyPage(history).results);
    const rows=root.querySelector('#overviewHistory').children;
    assert.match(rows[0].textContent,/ایجاد نسخه.*سابقهٔ انتشار دارد/);assert.doesNotMatch(rows[0].textContent,/سیاست فعال/);
    assert.match(rows[1].textContent,/سیاست فعال/);assert.match(rows[2].textContent,/پیش‌نویس فعلی.*انتشاری ثبت نشده/);
    ui.renderHistory(document,root,head,[]);assert.equal(root.querySelector('#overviewHistoryEmpty').hidden,false);
});
test('missing counts, malformed config and incompatible evidence fail closed instead of zero-filling',()=>{
    for(const edit of [h=>delete h.revision,h=>h.comparison_count=null,h=>h.active_version_id='2',h=>h.active_config.target_weight=6,
        h=>h.active_config.priority_rules.push(h.active_config.priority_rules[0]),h=>h.active_config.promotion_rules[0].points=-1,h=>h.algorithm_version='other']){
        const {head,options}=fixture();edit(head);assert.throws(()=>ui.validate(head,options));
    }
    for(const history of [{results:[],next_after_id:1},{results:[{id:1,published:true,created_at:'bad'}],next_after_id:null}])assert.throws(()=>ui.historyPage(history));
});
for(const status of [401,403,404,409,503])test('HTTP '+status+' hides content and exposes Persian error with explicit GET retry only',async()=>{
    const {root,document}=dom();let calls=0;ui.attach(document,root,async(url,options)=>{calls++;assert.equal(options.method,'GET');return {ok:false,status};});await settle();
    assert.equal(calls,3);assert.equal(root.querySelector('#overviewContent').hidden,true);assert.equal(root.querySelector('#overviewError').hidden,false);
    assert.equal(root.querySelector('#overviewErrorText').textContent,ui.ERRORS[status]);assert.equal(root.querySelector('#overviewLogin').hidden,status!==401);
});
test('successful boot uses bounded read-only APIs and no command endpoints',async()=>{
    const {root,document}=dom(),calls=[],data=fixture();ui.attach(document,root,async(url,options)=>{calls.push(url);assert.equal(options.method,'GET');assert.equal(options.cache,'no-store');assert.equal(options.credentials,'same-origin');return server(data)(url);});
    await settle();assert.equal(root.querySelector('#overviewContent').hidden,false);assert.equal(calls.length,7);
    assert.ok(calls.every(url=>!url.includes('commands/') && !url.includes('publish/') && !url.includes('draft/')));
});
test('reference metadata failure degrades to IDs; authorization failure hides the entire dashboard',async()=>{
    for(const status of [503,403]){
        const {root,document}=dom(),normal=server();ui.attach(document,root,async url=>url.includes('kind=')?{ok:false,status}:normal(url));await settle();
        assert.equal(root.querySelector('#overviewContent').hidden,status===403);
        if(status===503)assert.equal(root.querySelector('#overviewReferenceNotice').hidden,false);
    }
});
test('history pagination preserves existing rows on failure and allows only explicit GET retry',async()=>{
    const {root,document}=dom(),normal=server();let more=0;const app=ui.attach(document,root,async url=>{
        if(url.includes('after_id=3&')){more++;return more===1?{ok:false,status:503}:{ok:true,json:async()=>({results:[{id:4,published:false,created_at:'2026-10-16T16:00:00Z'}],next_after_id:null})};}return normal(url);
    });await settle();await app.loadMore();assert.equal(root.querySelector('#overviewHistory').children.length,3);assert.equal(root.querySelector('#overviewHistoryError').hidden,false);assert.equal(more,1);
    await app.loadMore();assert.equal(root.querySelector('#overviewHistory').children.length,4);assert.equal(root.querySelector('#overviewMoreVersions').hidden,true);
});
test('late initial response never replaces a newer explicit refresh',async()=>{
    const {root,document}=dom(),normal=server();let finish,count=0;
    const app=ui.attach(document,root,url=>++count===1?new Promise(resolve=>finish=resolve):normal(url));
    await app.load();finish({ok:false,status:403});await settle();assert.equal(root.querySelector('#overviewError').hidden,true);assert.equal(root.querySelector('#overviewContent').hidden,false);
});
