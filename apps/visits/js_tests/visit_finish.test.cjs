const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../../static/visits/js/visit_finish.js'),'utf8');
class Element {
 constructor(){this.dataset={};this.listeners={};this.textContent='';this.hidden=false;this.disabled=false;this.open=false;}
 addEventListener(name,fn){this.listeners[name]=fn;}focus(){this.focused=true;}showModal(){this.open=true;}close(){this.open=false;}
 click(){if(!this.disabled)return this.listeners.click?.({preventDefault(){}});}
}
const settle=()=>new Promise(r=>setImmediate(r));
const key='visit-completion:v1:1:C:14';
const request=status=>status?{id:7,status,revision:3,number:status==='SUBMITTED'?'SR-00000007':null}:null;
const state=(selected=null,status='IN_PROGRESS',recorded=null)=>({version:1,customer:{code:'C'},visit:{id:14,status},request:request(selected),can_complete:status==='IN_PROGRESS',recorded_result:recorded});
const result=(payload,selected=null)=>({version:1,success:true,customer:{code:'C'},visit:{id:14,status:'COMPLETED'},command_uuid:payload.command_uuid,completed_at:'2026-10-15T09:00:00+00:00',request:request(selected),acknowledgement:selected==='SUBMITTED'?{id:9,sales_request_id:7,actor_id:2}:null});
function fixture({initial=state(),read,mutation,storage=new Map(),storageError=false,setError=false,csrf='masked-csrf',apiUrl='/api/visits/v1/visits/14/completion/'}={}){
 const ids=['main-content','finishNotice','finishDialog','finishForm','finishInitialState','finishPrepare','finishConfirm','finishCancel','finishRetry','finishRecover','finishRefresh','finishRecovery','finishReady','finishSuccess','finishUnavailable','finishDraftWarning','finishConfirmDraft','finishRequestText','finishResultText','finishSuccessTitle','finishDialogNotice','badge'];
 const els=Object.fromEntries(ids.map(id=>[id,new Element()]));const root=els['main-content'];root.dataset={actorId:'1',customerCode:'C',visitId:'14',apiUrl};
 els.finishInitialState.textContent=JSON.stringify(initial);els.finishForm.querySelector=()=>csrf?{value:csrf}:null;
 let current=initial,serial=0;const calls=[],events={};
 const window={location:{origin:'http://localhost'},crypto:{randomUUID:()=> '00000000-0000-4000-8000-'+String(++serial).padStart(12,'0')},sessionStorage:{getItem:k=>{if(storageError)throw Error('unavailable');return storage.get(k);},setItem:(k,v)=>{if(setError)throw Error('unavailable');storage.set(k,v);},removeItem:k=>storage.delete(k)},addEventListener:(name,fn)=>events[name]=fn};
 const fetch=async(url,options)=>{calls.push({url,options});if(options.method==='GET'){const response=read?await read(current):{status:200,body:current};return{ok:response.status<400,status:response.status,json:async()=>response.body};}const payload=JSON.parse(options.body);const response=mutation?await mutation(payload):{status:200,body:result(payload,current.request?.status)};return{status:response.status,json:async()=>response.body};};
 vm.runInNewContext(source,{window,document:{querySelector:s=>s==='[data-visit-finish]'?root:s==='.sr-context [data-status]'?els.badge:null,getElementById:id=>els[id]},fetch,URL,URLSearchParams});
 return{els,calls,storage,events,setState:value=>{current=value;},confirm:()=>els.finishForm.listeners.submit({preventDefault(){}})};
}
const posts=f=>f.calls.filter(c=>c.options.method==='POST');
test('all three request states use GET, clear context and an explicit confirmation with no initial POST',async()=>{
 for(const selected of [null,'DRAFT','SUBMITTED']){const f=fixture({initial:state(selected)});await settle();assert(!f.els.finishPrepare.disabled);assert.equal(posts(f).length,0);f.els.finishPrepare.click();assert(f.els.finishDialog.open);assert(f.els.finishCancel.focused);assert.equal(posts(f).length,0);assert.equal(f.els.finishDraftWarning.hidden,selected!=='DRAFT');assert.equal(f.els.finishConfirmDraft.hidden,selected!=='DRAFT');}
});
test('cancel closes the dialog without mutation or pending storage',async()=>{const f=fixture();await settle();f.els.finishPrepare.click();f.els.finishCancel.click();assert(!f.els.finishDialog.open);assert(f.els.finishPrepare.focused);assert.equal(posts(f).length,0);assert.equal(f.storage.size,0);});
test('confirmed completion uses only canonical UUID/customer payload, session and CSRF; success updates status',async()=>{
 const f=fixture({initial:state('SUBMITTED')});await settle();f.els.finishPrepare.click();await f.confirm();
 const post=posts(f)[0],payload=JSON.parse(post.options.body);assert.deepEqual(Object.keys(payload).sort(),['command_uuid','customer_code']);assert.equal(payload.customer_code,'C');assert.match(payload.command_uuid,/^[a-f0-9-]{36}$/);assert.equal(post.options.headers['X-CSRFToken'],'masked-csrf');assert.equal(post.options.credentials,'same-origin');assert.equal(post.options.cache,'no-store');assert.equal(f.storage.size,0);assert(!f.els.finishSuccess.hidden);assert(f.els.finishReady.hidden);assert.equal(f.els.badge.dataset.status,'COMPLETED');assert(f.els.finishSuccessTitle.focused);
});
test('pending confirmation never claims success, double submit and escape are blocked during POST',async()=>{
 let resolve;const f=fixture({mutation:()=>new Promise(r=>resolve=r)});await settle();f.els.finishPrepare.click();const applying=f.confirm();await f.confirm();assert(f.els.finishSuccess.hidden);assert.equal(posts(f).length,1);let prevented=false;f.els.finishDialog.listeners.cancel({preventDefault(){prevented=true;}});assert(prevented);assert(f.els.finishCancel.disabled);resolve({status:200,body:result(JSON.parse(posts(f)[0].options.body))});await applying;assert(!f.els.finishSuccess.hidden);
});
test('uncertain POST preserves exact wire payload across reload and retry requires explicit confirmation',async()=>{
 const f=fixture({mutation:()=>{throw Error('lost response');}});await settle();f.els.finishPrepare.click();await f.confirm();const wire=posts(f)[0].options.body;assert.equal(f.storage.size,1);assert.match(f.els.finishNotice.textContent,/خودکار/);
 const reload=fixture({storage:f.storage});await settle();assert.equal(posts(reload).length,0);assert(reload.els.finishPrepare.disabled);reload.els.finishRetry.click();assert(reload.els.finishDialog.open);assert.equal(posts(reload).length,0);await reload.confirm();assert.equal(posts(reload)[0].options.body,wire);assert.equal(reload.storage.size,0);
});
test('GET recovery recognizes matching durable receipt without POST',async()=>{
 const f=fixture({mutation:()=>{throw Error('lost');}});await settle();f.els.finishPrepare.click();await f.confirm();const saved=JSON.parse(f.storage.get(key)),body=result(JSON.parse(saved.wire),'DRAFT');
 const reload=fixture({initial:state('DRAFT','COMPLETED',body),storage:f.storage});await settle();assert.equal(posts(reload).length,0);assert.equal(reload.storage.size,0);assert(!reload.els.finishSuccess.hidden);assert.match(reload.els.finishResultText.textContent,/ثبت نشده/);assert(reload.els.finishRetry.hidden);
});
test('legacy or different-command completion is read-only and cannot discard uncertain receipt identity',async()=>{
 const f=fixture({mutation:()=>{throw Error('lost');}});await settle();f.els.finishPrepare.click();await f.confirm();
 for(const recorded of [null,result({command_uuid:'11111111-1111-4111-8111-111111111111'})]){const reload=fixture({initial:state(null,'COMPLETED',recorded),storage:new Map(f.storage)});await settle();assert(!reload.els.finishSuccess.hidden);assert(reload.els.finishPrepare.disabled);assert(reload.els.finishRetry.hidden);assert.equal(reload.storage.size,1);assert.equal(posts(reload).length,0);assert.match(reload.els.finishNotice.textContent,/رسید همین فرمان تأیید نشد/);}
});
test('PLANNED, CANCELLED and completed documents never offer a new mutation',async()=>{for(const status of ['PLANNED','CANCELLED','COMPLETED']){const f=fixture({initial:state(null,status)});await settle();assert(f.els.finishPrepare.disabled);f.els.finishPrepare.click();await f.confirm();assert.equal(posts(f).length,0);}});
test('known first-attempt errors require state refresh and never show success',async()=>{
 for(const [status,code] of [[400,'INVALID_INPUT'],[403,'ACCESS_DENIED'],[404,'NOT_FOUND'],[409,'COMMAND_CONFLICT'],[409,'VISIT_NOT_ACTIVE']]){const f=fixture({mutation:()=>({status,body:{code}})});await settle();f.els.finishPrepare.click();await f.confirm();assert(f.els.finishSuccess.hidden);assert(f.els.finishPrepare.disabled);assert.equal(f.storage.size,0);assert.equal(posts(f).length,1);await settle();assert.equal(posts(f).length,1);}
});
test('failed explicit retry retains the original uncertain command',async()=>{
 const first=fixture({mutation:()=>{throw Error('lost');}});await settle();first.els.finishPrepare.click();await first.confirm();const wire=posts(first)[0].options.body;
 const retry=fixture({storage:first.storage,mutation:()=>({status:409,body:{code:'COMMAND_CONFLICT'}})});await settle();retry.els.finishRetry.click();await retry.confirm();assert.equal(posts(retry)[0].options.body,wire);assert.equal(retry.storage.size,1);assert(retry.els.finishSuccess.hidden);assert(retry.els.finishRetry.disabled);
});
test('authorization and invalid state responses fail closed before mutations',async()=>{
 for(const response of [{status:403,body:{code:'ACCESS_DENIED'}},{status:200,body:{...state(),customer:{code:'OTHER'}}},{status:200,body:{...state(),visit:{id:99,status:'IN_PROGRESS'}}}]){const f=fixture({read:()=>response});await settle();assert(f.els.finishPrepare.disabled);assert.equal(posts(f).length,0);}
});
test('malformed pending storage or other-actor envelope never enables new commands',async()=>{
 for(const saved of ['broken',JSON.stringify({version:1,actor:'other',wire:'{}'})]){const f=fixture({storage:new Map([[key,saved]])});await settle();assert(f.els.finishPrepare.disabled);assert(!f.els.finishRecovery.hidden);assert.equal(posts(f).length,0);}
});
test('storage failures prevent POST rather than losing retry identity',async()=>{
 for(const options of [{storageError:true},{setError:true}]){const f=fixture(options);await settle();f.els.finishPrepare.click();await f.confirm();assert.equal(posts(f).length,0);assert(f.els.finishPrepare.disabled);}
});
test('foreign endpoint is rejected before fetch',async()=>{const f=fixture({apiUrl:'https://evil.example/api/visits/v1/visits/14/completion/'});await settle();assert.equal(f.calls.length,0);assert(f.els.finishPrepare.disabled);});
test('wrong or malformed successful receipt is treated as uncertain',async()=>{
 for(const mutation of [()=>({status:200,body:result({command_uuid:'11111111-1111-4111-8111-111111111111'})}),()=>({status:200,body:{success:true}})]){const f=fixture({mutation});await settle();f.els.finishPrepare.click();await f.confirm();assert(f.els.finishSuccess.hidden);assert.equal(f.storage.size,1);assert.match(f.els.finishNotice.textContent,/مشخص نیست/);}
});
test('missing CSRF prevents POST and never presents success',async()=>{const f=fixture({csrf:null});await settle();f.els.finishPrepare.click();await f.confirm();assert.equal(posts(f).length,0);assert(f.els.finishSuccess.hidden);});
test('BFcache restore only rereads canonical state',async()=>{const f=fixture();await settle();f.setState(state(null,'COMPLETED'));await f.events.pageshow({persisted:true});await settle();assert(!f.els.finishSuccess.hidden);assert.equal(posts(f).length,0);assert.equal(f.calls.length,2);});
