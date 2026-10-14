const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../../static/core/js/guided_basket.js'),'utf8');
class Element {
 constructor(){this.dataset={};this.listeners={};this.children=[];this.attributes={};this.value='';this.hidden=false;this.disabled=false;this.textContent='';}
 addEventListener(name,fn){this.listeners[name]=fn;}setAttribute(name,value){this.attributes[name]=value;}
 append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}focus(){this.focused=true;}
 showModal(){this.open=true;}close(){this.open=false;}click(){if(!this.disabled)return this.listeners.click?.({preventDefault(){}});}
}
const settle=()=>new Promise(r=>setImmediate(r));
function target(id=1,recommended=true){const fields=Object.fromEntries(['quantity','add','decision','availability'].map(name=>[name,new Element()]));
 return {product_id:id,name:'<محصول>',recommendation:recommended?{id:100+id}:null,fields,mount:{querySelector:s=>s==='[data-quote-availability]'?fields.availability:fields[s.slice(13,-1)]}};}
function state({lines=[],revision=lines.length?1:null,editable=true,valid=true}={}){
 return {version:1,currency:'TOMAN',customer:{code:'C'},visit:{id:14,status:editable?'IN_PROGRESS':'PLANNED'},request:revision===null?null:{id:9,status:'DRAFT',revision},editable,lines,
 item_count:lines.length,total_units:lines.length?lines[0].quantity:0,saved_totals:{base:'315',discount:'30',final:'285'},quote_changed:false,
 current_quote:{valid,items:lines.map(l=>({product_id:l.product_id,quantity:l.quantity,quote:{quantity:l.quantity},inventory:{can_add:valid,catalog_visible:true,available_quantity:8},reason_code:valid?null:'PRICE_UNAVAILABLE'}))}};
}
function line(id=1,quantity=3,source='RECOMMENDATION'){return {id:20+id,product_id:id,quantity,selection_source:source,product_snapshot:{name:'محصول ذخیره‌شده'}};}
function fixture({initial=state(),mutation,quote,readError=false,readBasket,storage=new Map(),feedbackPending=false,receipt}={}){
 const ids=['basketPanel','guidedCatalog','basketDialog','basketForm','basketNotice','basketRecovery','basketSummary','basketGuidance','basketLines','basketRefresh','basketTitle','basketDescription','basketQuoteTotal','basketMessage','basketConfirm','basketCancel','basketStatus','basketRetryCommand'];
 const els=Object.fromEntries(ids.map(id=>[id,new Element()]));els.guidedCatalog.dataset={actorId:'1',customerCode:'C',visitId:'14'};els.basketForm.querySelector=()=>({value:els.csrf===undefined?'masked-csrf':els.csrf});
 let current=initial,serial=0;const calls=[],feedback=[];
 const window={location:new URL('http://localhost/'),crypto:{randomUUID:()=>`00000000-0000-4000-8000-${String(++serial).padStart(12,'0')}`},
  sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},GuidedFeedback:{hasPending:()=>feedbackPending,setBasket:(data,busy)=>feedback.push({data,busy})}};
 const fetch=async(url,options)=>{calls.push({url,options});const u=new URL(url,window.location);let body,status=200;
  if(options.method==='GET'){
   if(u.pathname.includes('/commands/')){body=receipt||{code:'NOT_FOUND'};status=receipt?200:404;}
   else if(u.pathname.endsWith('/basket/quote/')){body=quote||{version:1,customer_code:'C',visit_id:14,editable:true,valid:true,expected_request_revision:current.request?.revision??null,
     items:[{product_id:Number(u.searchParams.get('product_id')),quantity:Number(u.searchParams.get('quantity'))}],quote_fingerprint:'a'.repeat(64),totals:{final:'285'}};}
   else {if(readError)throw Error('offline');body=readBasket?await readBasket():current;}
  }else{const payload=JSON.parse(options.body);const result=await(mutation?mutation(payload,options):{body:state({lines:options.method==='DELETE'?[]:[line(payload.product_id||1,payload.quantity)],revision:(payload.expected_request_revision??0)+1}),status:options.method==='POST'?201:200});body=result.body;status=result.status; if(status<300)current=body;}
  return {ok:status<400,status,json:async()=>body,headers:{get:()=>null}};
 };
 vm.runInNewContext(source,{window,document:{getElementById:id=>els[id],createElement:()=>new Element()},fetch,URL,URLSearchParams,Intl});
 return {els,calls,storage,feedback,load:window.GuidedBasket.load,quotes:window.GuidedBasket.quotes,refresh:window.GuidedBasket.refresh,
  confirm:()=>els.basketForm.listeners.submit({preventDefault(){}}),setCurrent:data=>{current=data;}};
}
const context={catalogContext:'signed-original'};
const availability=(id=1,can_add=true)=>({product_id:id,can_add,inventory:{sellable_quantity:8}});
const mutations=f=>f.calls.filter(c=>c.options.method!=='GET');
async function ready(f,t=target()){await f.load(context,[t]);f.quotes([availability(t.product_id)]);return t;}
test('initial reads never create browser-authoritative basket and eligible slots activate',async()=>{
 const f=fixture(),t=await ready(f);assert(!t.fields.add.disabled);assert.equal(t.fields.quantity.value,'1');assert.equal(mutations(f).length,0);assert.match(f.els.basketSummary.textContent,/درخواست فروش/);assert(f.calls.every(c=>c.options.cache==='no-store'));
});
test('confirmed mutation refreshes visible server quote presentation without client arithmetic',async()=>{
 const f=fixture(),t=target();let refreshes=0;
 await f.load(context,[t],{refreshQuotes:()=>{refreshes++;}});f.quotes([availability()]);
 await t.fields.add.click();f.confirm();await settle();assert.equal(refreshes,1);assert.equal(mutations(f).length,1);
});
test('add quotes complete basket, explicitly confirms UUID/revision/fingerprint/CSRF, then GET refresh',async()=>{
 const f=fixture(),t=await ready(f);t.fields.quantity.value='3';await t.fields.add.click();assert(f.els.basketDialog.open);assert.equal(mutations(f).length,0);
 assert.match(f.els.basketQuoteTotal.textContent,/۲۸۵/);f.confirm();await settle();assert.equal(mutations(f).length,1);
 const c=mutations(f)[0],p=JSON.parse(c.options.body);assert.equal(p.quantity,3);assert.equal(p.expected_request_revision,null);assert.equal(p.accepted_quote_fingerprint,'a'.repeat(64));assert.equal(p.catalog_context,'signed-original');assert(p.command_uuid);assert.equal(c.options.headers['X-CSRFToken'],'masked-csrf');assert.equal(c.options.credentials,'same-origin');
 assert(!f.els.basketDialog.open);assert.match(t.fields.decision.textContent,/افزوده/);assert(!t.fields.decision.hidden);assert.equal(t.fields.add.textContent,'ثبت تعداد');assert(f.calls.at(-1).url.includes('/basket/?'));
});
test('quantity update uses PATCH absolute quantity and expected existing revision',async()=>{
 const f=fixture({initial:state({lines:[line()]})}),t=await ready(f);t.fields.quantity.value='4';await t.fields.add.click();f.confirm();await settle();
 const c=mutations(f)[0],p=JSON.parse(c.options.body);assert.equal(c.options.method,'PATCH');assert.match(c.url,/requests\/9\/lines\/21\//);assert.equal(p.quantity,4);assert.equal(p.expected_request_revision,1);assert(!('product_id'in p));
});
test('removal is explicit DELETE, no price requirement, and remaining invalid lines still removable',async()=>{
 const f=fixture({initial:state({lines:[line()],valid:false})}),t=await ready(f);assert(t.fields.add.disabled);
 const row=f.els.basketLines.children[0],remove=row.children.at(-1).children[1];assert(!remove.disabled);await remove.click();assert.equal(mutations(f).length,0);f.confirm();await settle();
 const c=mutations(f)[0],p=JSON.parse(c.options.body);assert.equal(c.options.method,'DELETE');assert(!('accepted_quote_fingerprint'in p));assert(!('quantity'in p));assert.match(f.els.basketNotice.textContent,/سابقه افزودن محفوظ/);
});
test('ordinary selection has no recommendation acceptance label',async()=>{
 const f=fixture({initial:state({lines:[line(2,3,'ORDINARY')]})}),t=await ready(f,target(2,false));assert(t.fields.decision.hidden);assert.equal(t.fields.decision.textContent,'');
});
test('eligible ordinary product uses the same add/quantity/remove contract without acceptance labels',async()=>{
 const f=fixture({mutation:(payload,options)=>({status:options.method==='POST'?201:200,body:state({lines:options.method==='DELETE'?[]:[line(2,payload.quantity,'ORDINARY')],revision:(payload.expected_request_revision??0)+1})})}),t=await ready(f,target(2,false));
 assert(!t.fields.add.disabled);assert.equal(t.fields.availability.textContent,'');
 t.fields.quantity.value='2';t.fields.quantity.listeners.input();await t.fields.add.click();f.confirm();await settle();
 assert.equal(t.fields.add.textContent,'ثبت تعداد');assert(t.fields.decision.hidden);
 t.fields.quantity.value='4';t.fields.quantity.listeners.input();await t.fields.add.click();f.confirm();await settle();
 const remove=f.els.basketLines.children[0].children.at(-1).children[1];await remove.click();f.confirm();await settle();
 assert.deepEqual(mutations(f).map(call=>call.options.method),['POST','PATCH','DELETE']);
 for(const call of mutations(f)){const p=JSON.parse(call.options.body);assert(p.command_uuid);assert.equal(p.catalog_context,'signed-original');assert.equal(call.options.headers['X-CSRFToken'],'masked-csrf');}
 assert(t.fields.decision.hidden);assert.equal(t.fields.decision.textContent,'');
});
test('ordinary products explain unknown/zero stock, missing price and read/Visit restrictions in the existing card area',async()=>{
 for(const [code,message] of [['INVENTORY_UNKNOWN',/نامشخص/],['OUT_OF_STOCK',/ناموجود/],['PRICE_UNAVAILABLE',/قیمت/],['PRICE_CONFIGURATION_ERROR',/قیمت/]]){
  const f=fixture(),t=await ready(f,target(2,false));f.quotes([{...availability(2,false),non_addable_reason:code}]);
  assert(t.fields.add.disabled);assert.match(t.fields.availability.textContent,message);assert(t.fields.add.attributes['aria-describedby']);assert.equal(mutations(f).length,0);
 }
 for(const settings of [{initial:state({editable:false})},{readError:true}]){const f=fixture(settings),t=await ready(f,target(2,false));assert(t.fields.add.disabled);assert(t.fields.availability.textContent);assert.equal(mutations(f).length,0);}
});
test('server stock limit disables Add for excessive/invalid desired quantity and re-enables a corrected quantity',async()=>{
 const f=fixture(),t=await ready(f,target(2,false));
 for(const value of ['9','0','1.5','']){t.fields.quantity.value=value;t.fields.quantity.listeners.input();assert(t.fields.add.disabled);assert.match(t.fields.availability.textContent,value==='9'?/موجودی/:/عدد صحیح/);}
 assert.equal(mutations(f).length,0);t.fields.quantity.value='8';t.fields.quantity.listeners.input();assert(!t.fields.add.disabled);assert.equal(t.fields.availability.textContent,'');
});
test('selected ordinary quantity above current stock remains reducible but cannot submit unchanged excess',async()=>{
 const data=state({lines:[line(2,9,'ORDINARY')]});data.current_quote.items[0].valid=false;data.current_quote.items[0].reason_code='INSUFFICIENT_STOCK';
 const f=fixture({initial:data}),t=await ready(f,target(2,false));assert(!t.fields.quantity.disabled);assert(t.fields.add.disabled);assert.match(t.fields.availability.textContent,/موجودی/);
 t.fields.quantity.value='8';t.fields.quantity.listeners.input();assert(!t.fields.add.disabled);
 const row=f.els.basketLines.children[0];assert(!row.children.at(-1).children[1].disabled);assert.equal(mutations(f).length,0);
});
test('known invalid other basket content blocks Add without disabling explicit removal',async()=>{
 const data=state({lines:[line(1,3)]});data.current_quote.items[0].valid=false;data.current_quote.items[0].reason_code='PRICE_UNAVAILABLE';
 const f=fixture({initial:data}),t=await ready(f,target(2,false));assert(t.fields.add.disabled);assert.match(t.fields.availability.textContent,/سایر اقلام/);
 assert(!f.els.basketLines.children[0].children.at(-1).children[1].disabled);assert.equal(mutations(f).length,0);
});
test('reload reads server-persisted selection/count/totals without browser basket authority',async()=>{
 const f=fixture({initial:state({lines:[line()]})}),t=await ready(f);assert.equal(t.fields.quantity.value,'3');assert.match(f.els.basketSummary.textContent,/۲۸۵/);assert.equal(mutations(f).length,0);
});
test('zero/unknown/missing price are gated by server quote; PLANNED/read errors never enable Add',async()=>{
 for(const options of [{initial:state({editable:false})},{readError:true}]){const f=fixture(options),t=await ready(f);assert(t.fields.add.disabled);assert(t.fields.quantity.disabled);assert.equal(mutations(f).length,0);}
 for(const reason of ['OUT_OF_STOCK','INVENTORY_UNKNOWN','PRICE_UNAVAILABLE']){const f=fixture(),t=await ready(f);f.quotes([{...availability(1,false),non_addable_reason:reason}]);assert(t.fields.add.disabled);}
});
test('invalid quantities and unavailable candidate basket never POST',async()=>{
 const f=fixture(),t=await ready(f);for(const value of ['0','-1','1.5','true','2147483648']){t.fields.quantity.value=value;await t.fields.add.click();}assert.equal(mutations(f).length,0);assert(!f.els.basketDialog.open);
 for(const reason of ['INSUFFICIENT_STOCK','PRICE_UNAVAILABLE','INVENTORY_UNKNOWN']){const g=fixture({quote:{version:1,customer_code:'C',visit_id:14,editable:true,valid:false,items:[{product_id:1,quantity:1,reason_code:reason,valid:false}]}}),p=await ready(g);await p.fields.add.click();assert.equal(mutations(g).length,0);assert(!g.els.basketDialog.open);assert(g.els.basketNotice.textContent);assert(p.fields.add.disabled);assert(!p.fields.quantity.disabled);p.fields.quantity.listeners.input();assert(!p.fields.add.disabled);}
});
test('no success before server response and double confirmation cannot duplicate mutation',async()=>{
 let resolve;const f=fixture({mutation:p=>new Promise(r=>{resolve=()=>r({body:state({lines:[line(1,p.quantity)]}),status:201});})}),t=await ready(f);t.fields.quantity.value='3';await t.fields.add.click();f.confirm();f.confirm();assert.equal(mutations(f).length,1);assert(t.fields.add.disabled);assert(t.fields.decision.hidden);resolve();await settle();assert(!t.fields.decision.hidden);
});
test('uncertain command survives reload, uses original context/UUID/payload, and never auto-retries',async()=>{
 const storage=new Map(),f=fixture({storage,mutation:()=>{throw Error('network');}}),t=await ready(f);t.fields.quantity.value='3';await t.fields.add.click();f.confirm();await settle();const original=mutations(f)[0].options.body;assert.equal(mutations(f).length,1);assert(!f.els.basketRecovery.hidden);
 const g=fixture({storage}),p=target();await g.load({catalogContext:'new-token'},[p]);g.quotes([availability()]);assert.equal(mutations(g).length,0);assert(p.fields.add.disabled);g.els.basketRetryCommand.click();g.confirm();await settle();assert.equal(mutations(g)[0].options.body,original);assert.equal(storage.size,0);
});
test('receipt recovery is GET-only and refreshes current rather than replayed old state',async()=>{
 const storage=new Map(),f=fixture({storage,mutation:()=>{throw Error('network');}}),t=await ready(f);t.fields.quantity.value='3';await t.fields.add.click();f.confirm();await settle();const command=JSON.parse([...storage.values()][0]);
 const receipt={command_uuid:command.payload.command_uuid,result:{http_status:201,body:state({lines:[line()],revision:1})}};
 const g=fixture({storage,receipt,initial:state({lines:[line(1,5)],revision:4})});await ready(g);await g.els.basketStatus.click();assert.equal(mutations(g).length,0);assert.equal(storage.size,0);assert.equal(g.els.basketLines.children[0].children[1].children[0].value,'5');
});
test('receipt 404 never infers definite failure or clears uncertain intent',async()=>{
 const storage=new Map(),f=fixture({storage,mutation:()=>{throw Error('network');}}),t=await ready(f);await t.fields.add.click();f.confirm();await settle();await f.els.basketStatus.click();assert.equal(mutations(f).length,1);assert.equal(storage.size,1);assert.match(f.els.basketNotice.textContent,/شکست قطعی نیست/);
});
test('definite conflicts refresh state without automatically retrying POST',async()=>{
 for(const code of ['REVISION_CONFLICT','PRICE_CHANGED','COMMAND_CONFLICT','PRODUCT_ALREADY_SELECTED','ACCESS_DENIED']){const f=fixture({mutation:()=>({status:code==='ACCESS_DENIED'?403:409,body:{code}})}),t=await ready(f);await t.fields.add.click();f.confirm();await settle();assert.equal(mutations(f).length,1);assert.equal(f.storage.size,0);assert(!f.els.basketDialog.open);assert(f.els.basketNotice.textContent);}
});
test('changed revision at quote boundary requires re-read and another explicit action',async()=>{
 const f=fixture({quote:{version:1,customer_code:'C',visit_id:14,editable:true,valid:true,expected_request_revision:2,items:[{product_id:1,quantity:1}],quote_fingerprint:'a'.repeat(64),totals:{final:'285'}}}),t=await ready(f);await t.fields.add.click();assert(!f.els.basketDialog.open);assert.equal(mutations(f).length,0);assert.match(f.els.basketNotice.textContent,/درخواست تغییر/);
});
test('unknown success payload stays uncertain and never displays selection',async()=>{
 const f=fixture({mutation:()=>({status:201,body:{version:1}})}),t=await ready(f);await t.fields.add.click();f.confirm();await settle();assert.equal(f.storage.size,1);assert(t.fields.decision.hidden);assert.match(f.els.basketNotice.textContent,/مشخص نیست/);
});
test('missing CSRF or unavailable command storage blocks mutation',async()=>{
 const f=fixture(),t=await ready(f);await t.fields.add.click();f.els.csrf='';f.confirm();await settle();assert.equal(mutations(f).length,0);
 const g=fixture({storage:{get:()=>null,set:()=>{throw Error('storage');}}}),p=await ready(g);await p.fields.add.click();g.confirm();await settle();assert.equal(mutations(g).length,0);
});
test('pending feedback blocks fresh basket action and selected lines notify feedback controller',async()=>{
 const f=fixture({feedbackPending:true}),t=await ready(f);assert(t.fields.add.disabled);assert.equal(mutations(f).length,0);
 const g=fixture({initial:state({lines:[line()]})});await ready(g);assert(g.feedback.some(call=>call.data?.lines[0]?.product_id===1));
});
test('filtered catalog reload ignores obsolete basket responses',async()=>{
 let resolve,reads=0;const old=new Promise(done=>{resolve=done;});
 const f=fixture({readBasket:()=>++reads===1?old:state({lines:[line(2,3,'ORDINARY')],revision:2})}),a=target(),b=target(2,false);
 const first=f.load(context,[a]);
 await f.load(context,[b],{isCurrent:()=>true});f.quotes([availability(2)]);
 resolve(state({lines:[line(1,1)],revision:1}));await first;
 assert.equal(b.fields.quantity.value,'3');assert.equal(b.fields.add.textContent,'ثبت تعداد');assert.equal(mutations(f).length,0);
});
test('authorization lost during uncertain retry preserves exact recovery command',async()=>{
 let attempt=0;const f=fixture({mutation:()=>{if(++attempt===1)throw Error('network');return{status:403,body:{code:'ACCESS_DENIED'}};}}),t=await ready(f);
 await t.fields.add.click();f.confirm();await settle();const original=mutations(f)[0].options.body;
 f.els.basketRetryCommand.click();f.confirm();await settle();assert.equal(mutations(f)[1].options.body,original);assert.equal(f.storage.size,1);assert(!f.els.basketRecovery.hidden);
});
