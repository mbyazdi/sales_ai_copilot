const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {controller,normalize,message,navigationMode}=require('../../../static/management/js/strategy_control.js');
const command='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',algorithm='SAVED_RANK_OVERLAY_V1';
const neutral=()=>({schema_version:1,priority_rules:[],target_weight:0,promotion_rules:[]});
const bounds={schema_version:1,algorithm_version:algorithm,priority_bounds:[0,20],target_weight_bounds:[0,5],promotion_points_bounds:[0,5],adjustment_cap:30};
const head=()=>({schema_version:1,algorithm_version:algorithm,revision:3,active_version_id:2,draft_version_id:null,active_config:neutral()});
const response={operation:'SAVE_DRAFT',result:{kind:'CONFIGURATION',version_id:4,policy_revision:4,config_hash:'a'.repeat(64)}};
const http=(status,code)=>Object.assign(Error('HTTP'),{status,code});
function harness(overrides={}){
 const data=new Map(),calls=[],destinations=[];const storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const h={data,calls,destinations,storage,current:head(),versionConfig:neutral()};
 h.handler=async(url,o)=>{
  const u=new URL(url,'http://localhost');
  if(u.pathname.endsWith('overview/'))return structuredClone(h.current);
  if(u.pathname.endsWith('versions/'))return {results:[{id:Number(u.searchParams.get('after_id'))+1,algorithm_version:algorithm,config_hash:'a'.repeat(64),config:h.versionConfig}]};
  if(u.pathname.endsWith('options/'))return u.searchParams.has('kind')?{results:[{id:1,name:'مرجع واقعی'}],next_after_id:null}:bounds;
  if(u.pathname.includes('/commands/'))return response;
  if(o.method==='POST'){assert.ok(data.size,'persist before POST');h.versionConfig=JSON.parse(o.body).config;h.current={...h.current,revision:4,draft_version_id:4};return response;}
  throw Error('Unexpected URL');
 };
 h.dependencies={actor:'7',environment:'localhost:8901:test-cookie',canEdit:true,storage,csrf:()=> 'masked',makeUUID:()=>command,navigate:u=>destinations.push(u),change:()=>{},
  fetcher:async(u,o)=>{calls.push({url:u,options:o});const d=await h.handler(u,o);return {ok:true,status:200,json:async()=>d};},...overrides};
 h.app=controller(h.dependencies);return h;
}
test('zero-write loading, neutral copy and authoritative bounds',async()=>{
 const h=harness();await h.app.start();assert.equal(h.app.state.phase,'ready');assert.deepEqual(h.app.state.config,neutral());
 assert.equal(h.app.state.savedVersion,null);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);assert.equal(h.data.size,0);
});
test('exact draft version is loaded and mismatched version fails closed',async()=>{
 const h=harness();h.current.draft_version_id=4;h.versionConfig={...neutral(),target_weight:5};await h.app.start();assert.equal(h.app.state.config.target_weight,5);
 const bad=harness();bad.current.draft_version_id=4;const orig=bad.handler;bad.handler=async(u,o)=>u.includes('versions/')?{results:[{id:8}]}:orig(u,o);
 await bad.app.start();assert.equal(bad.app.state.phase,'error');assert.equal(bad.app.state.config,null);
});
test('publication or draft change during loading fails closed',async()=>{
 const h=harness(),orig=h.handler;let n=0;h.handler=async(u,o)=>{const d=await orig(u,o);if(u.endsWith('overview/')&&++n===2)d.revision++;return d;};
 await h.app.start();assert.equal(h.app.state.phase,'error');assert.equal(h.app.state.config,null);
});
test('strict typed rules, overlaps, explicit zero, removal and no total-row cap',()=>{
 const c={...neutral(),priority_rules:[{scope_type:'PRODUCT',scope_id:1,points:0},{scope_type:'BRAND',scope_id:1,points:20},{scope_type:'CATEGORY',scope_id:1,points:20}]};
 assert.equal(normalize(c).priority_rules.length,3);assert.equal(normalize(c).priority_rules.find(r=>r.scope_type==='PRODUCT').points,0);
 const noRule={...c,priority_rules:c.priority_rules.slice(1)};assert.notDeepEqual(normalize(c),normalize(noRule));
 for(const value of [null,'0',true,1.2,-1,21])assert.throws(()=>normalize({...neutral(),priority_rules:[{scope_type:'PRODUCT',scope_id:1,points:value}]}));
 for(const value of [null,'0',true,1.2,-1,6])assert.throws(()=>normalize({...neutral(),target_weight:value}));
 assert.throws(()=>normalize({...neutral(),extra:1}));assert.throws(()=>normalize({...neutral(),priority_rules:[c.priority_rules[0],c.priority_rules[0]]}));
 assert.throws(()=>normalize({...neutral(),promotion_rules:[{promotion_id:1,points:0},{promotion_id:1,points:5}]}));
 assert.throws(()=>normalize({...neutral(),priority_rules:[{scope_type:'PRODUCT',scope_id:9007199254740992,points:2}]}));
});
test('bounded pagination appends options and rejects looping/unsorted evidence',async()=>{
 const h=harness(),orig=h.handler;h.handler=async(u,o)=>u.includes('kind=products')?{results:[{id:u.includes('after_id=0')?1:2}],next_after_id:u.includes('after_id=0')?1:null}:orig(u,o);
 await h.app.start();assert.equal(h.app.state.next.products,1);await h.app.more('products');assert.deepEqual(h.app.state.options.products.map(r=>r.id),[1,2]);
 h.app.state.next.products=2;h.handler=async()=>({results:[{id:2}],next_after_id:2});await h.app.more('products');assert.match(h.app.state.error,/تأیید/);
});
test('configured unresolved reference is preserved, not silently deleted',async()=>{
 const h=harness();h.current.active_config={...neutral(),priority_rules:[{scope_type:'PRODUCT',scope_id:999,points:0}]};await h.app.start();
 assert.equal(h.app.state.config.priority_rules[0].scope_id,999);await h.app.save();assert.equal(JSON.parse(h.calls.find(c=>c.options.method==='POST').options.body).config.priority_rules[0].scope_id,999);
});
test('explicit save uses session/CSRF and verifies immutable version before success',async()=>{
 const h=harness();await h.app.start();h.app.edit({...neutral(),target_weight:5});await h.app.save();assert.equal(h.app.state.phase,'saved');
 const posts=h.calls.filter(c=>c.options.method==='POST');assert.equal(posts.length,1);assert.equal(posts[0].options.headers['X-CSRFToken'],'masked');assert.equal(posts[0].options.credentials,'same-origin');
 assert.equal(JSON.parse(posts[0].options.body).expected_revision,3);assert.equal(h.app.state.head.active_version_id,2);assert.equal(h.data.size,0);
 await h.app.compare();assert.deepEqual(h.destinations,['/management/strategy/comparisons/?expected_draft=4']);
});
test('view-only mode cannot save, replay or create comparison',async()=>{
 const h=harness({canEdit:false});await h.app.start();h.app.edit({...neutral(),target_weight:5});await h.app.save();await h.app.recover();await h.app.retry();await h.app.compare();
 assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);assert.equal(h.data.size,0);assert.equal(h.app.state.config.target_weight,0);
});
test('uncertain save persists exact payload; reload does not POST and GET recovers',async()=>{
 const h=harness();await h.app.start();const orig=h.handler;h.handler=async(u,o)=>{if(o.method==='POST'){await orig(u,o);throw Error('lost after commit');}return orig(u,o);};
 await h.app.save();const body=h.app.state.pending;assert.equal(h.app.state.phase,'pending');const count=h.calls.length;
 const reloaded=controller(h.dependencies);await reloaded.start();assert.equal(h.calls.length,count);assert.equal(reloaded.state.pending,body);
 await reloaded.recover();assert.equal(reloaded.state.phase,'saved');assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
});
test('404 is not cancellation; retry is explicit with the same UUID and payload',async()=>{
 const h=harness();await h.app.start();const orig=h.handler;let fail=true;h.handler=async(u,o)=>{if(o.method==='POST'&&fail){fail=false;throw Error('offline');}if(u.includes('/commands/'))throw http(404);return orig(u,o);};
 await h.app.save();const payload=h.app.state.pending;await h.app.recover();assert.equal(h.app.state.retry,true);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
 await h.app.retry();assert.equal(h.calls.filter(c=>c.options.method==='POST').at(-1).options.body,payload);assert.equal(h.app.state.phase,'saved');
});
test('wrong operation/config/hash/revision never confirms a save',async()=>{
 for(const change of [r=>({...r,operation:'PUBLISH'}),r=>({...r,result:{...r.result,kind:'ROLLBACK_PREPARATION'}}),r=>({...r,result:{...r.result,policy_revision:8}}),r=>({...r,result:{...r.result,config_hash:'b'.repeat(64)}})]){
  const h=harness();await h.app.start();const orig=h.handler;h.handler=async(u,o)=>o.method==='POST'?change(await orig(u,o)):orig(u,o);
  await h.app.save();assert.equal(h.app.state.phase,'pending');assert.equal(h.data.size,1);
 }
 const h=harness();await h.app.start();const orig=h.handler;h.handler=async(u,o)=>{const r=await orig(u,o);if(u.includes('versions/'))r.results[0].config={...neutral(),target_weight:3};return r;};
 await h.app.save();assert.equal(h.app.state.phase,'pending');
});
test('read error after committed POST does not discard pending payload',async()=>{
 const h=harness();await h.app.start();const orig=h.handler;h.handler=async(u,o)=>u.includes('versions/')?Promise.reject(http(403)):orig(u,o);
 await h.app.save();assert.equal(h.app.state.phase,'pending');assert.equal(h.data.size,1);
});
test('storage denied, silent failure and tampered envelopes fail before POST',async()=>{
 for(const mode of ['throw','silent']){const h=harness();await h.app.start();h.storage.setItem=()=>{if(mode==='throw')throw Error('denied');};await h.app.save();assert.equal(h.app.state.phase,'blocked');assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);}
 const h=harness();h.data.set('strategy-draft-command-v1:localhost:8901:test-cookie:7','{"schema":1}');await h.app.start();assert.equal(h.app.state.phase,'blocked');assert.equal(h.calls.length,0);
});
test('storage removal failure preserves recovery and does not claim saved',async()=>{
 const h=harness();await h.app.start();h.storage.removeItem=()=>{};await h.app.save();assert.equal(h.app.state.phase,'pending');assert.equal(h.data.size,1);
});
test('actor/environment namespace cannot adopt another pending command',async()=>{
 const h=harness();await h.app.start();h.handler=async()=>{throw Error('offline');};await h.app.save();assert.equal(h.data.size,1);
 const second=harness({actor:'8',storage:h.storage});await second.app.start();assert.equal(second.app.state.pending,null);
 const other=harness({environment:'localhost:8901:other-cookie',storage:h.storage});await other.app.start();assert.equal(other.app.state.pending,null);
});
test('CAS conflict preserves edits until explicit refreshed review; no automatic merge',async()=>{
 const h=harness();await h.app.start();h.app.edit({...neutral(),target_weight:4});const orig=h.handler;
 h.handler=async(u,o)=>o.method==='POST'?Promise.reject(http(409,'STALE_POLICY_REVISION')):orig(u,o);
 await h.app.save();assert.equal(h.app.state.phase,'conflict');assert.equal(h.app.state.config.target_weight,4);
 h.app.edit({...neutral(),target_weight:3});await h.app.save();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
 h.current.revision=7;await h.app.load(true);assert.equal(h.app.state.head.revision,7);assert.equal(h.app.state.config.target_weight,3);assert.equal(h.app.state.dirty,true);
});
test('conflicting UUID retains recovery evidence; repeated clicks do not dispatch twice',async()=>{
 const h=harness();await h.app.start();h.handler=async()=>{throw http(409,'COMMAND_INTENT_CONFLICT');};await h.app.save();assert.equal(h.app.state.phase,'pending');assert.equal(h.data.size,1);
 const b=harness();await b.app.start();let release;const orig=b.handler;b.handler=async(u,o)=>{if(o.method==='POST')await new Promise(resolve=>release=resolve);return orig(u,o);};
 const first=b.app.save();await b.app.save();assert.equal(b.calls.filter(c=>c.options.method==='POST').length,1);release();await first;
});
test('changed draft at handoff is disclosed without navigating to another version',async()=>{
 const h=harness();await h.app.start();await h.app.save();h.current.draft_version_id=5;await h.app.compare();assert.equal(h.app.state.phase,'conflict');assert.equal(h.destinations.length,0);
});
test('invalid numeric editing makes no POST; reset restores captured data locally',async()=>{
 const h=harness();await h.app.start();h.app.edit({...neutral(),target_weight:null});await h.app.save();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);assert.match(h.app.state.error,/عدد صحیح/);
 h.app.reset();assert.deepEqual(h.app.state.config,neutral());assert.equal(h.app.state.dirty,false);
});
test('safe text sinks, Persian copy, native disclosures and scoped responsive CSS',()=>{
 const js=fs.readFileSync('static/management/js/strategy_control.js','utf8'),html=fs.readFileSync('templates/management/strategy_control.html','utf8'),css=fs.readFileSync('static/management/css/strategy_control.css','utf8');
 assert.doesNotMatch(js,/innerHTML|insertAdjacentHTML|eval\(/);assert.match(js,/textContent/);assert.match(html,/role="alert"/);assert.match(html,/<details/);
 assert.match(css,/@media\(max-width:600px\)/);assert.match(css,/:focus-visible/);assert.match(js,/وضعیت مرجع تأیید نشده/);assert.match(html,/قیمت، تخفیف و درخواست‌های فروش تغییر نمی‌کنند/);
 assert.ok(!js.includes("request('publish/"));assert.ok(!js.includes("request('rollback/"));
});
test('401/403/409 errors have explicit Persian guidance',()=>{for(const s of [401,403,409])assert.ok(message({status:s}).length>20);assert.match(message({status:403,code:'CSRF_FAILED'}),/امنیتی/);});

test('compact navigation closes safely and desktop restores its active destination',()=>{
 let focus='';const summary={focus:()=>focus='summary'},current={focus:()=>focus='current'},link={};
 const nav={open:true,querySelector:s=>s==='summary'?summary:current,contains:e=>e===link};
 navigationMode(nav,true,link);assert.equal(nav.open,false);assert.equal(focus,'summary');
 navigationMode(nav,false,summary);assert.equal(nav.open,true);assert.equal(focus,'current');
 focus='outside';navigationMode(nav,true,{});assert.equal(focus,'outside');assert.equal(nav.open,false);
});
test('explicit-zero draft survives confirmed save and a fresh editor reload',async()=>{
 const h=harness();await h.app.start();
 h.app.edit({...neutral(),priority_rules:[{scope_type:'PRODUCT',scope_id:1,points:0}]});
 await h.app.save();assert.equal(h.app.state.phase,'saved');
 const reloaded=controller(h.dependencies);await reloaded.start();
 assert.deepEqual(reloaded.state.config.priority_rules,[{scope_type:'PRODUCT',scope_id:1,points:0}]);
 assert.equal(reloaded.state.head.active_version_id,2);assert.equal(reloaded.state.dirty,false);
 assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
});
test('page-local navigation keeps destinations and row controls have compact accessible layout',()=>{
 const html=fs.readFileSync('templates/management/strategy_control.html','utf8'),css=fs.readFileSync('static/management/css/strategy_control.css','utf8');
 assert.match(html,/<details id="controlNavigation" class="control-navigation" open>/);
 assert.match(html,/<summary id="controlNavigationSummary">/);
 for(const route of ['strategy-overview','strategy-control','strategy-comparison-create'])assert.ok(html.includes("{% url '"+route+"' %}"));
 assert.match(html,/aria-current="page"/);assert.match(css,/@media\(max-width:900px\)/);
 assert.match(css,/"identity identity" "score remove"/);assert.match(css,/min-height:44px/);
});
