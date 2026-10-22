const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {controller,validContext}=require('../../../static/management/js/strategy_comparison_create.js');
const command='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const selection={customer_id:11,salesperson_id:21,proposed_version_id:5,evaluation_date:'2026-10-16'};
const context={...selection,expected_revision:9,accepted_source_fingerprint:'a'.repeat(64)};
const success={operation:'PREVIEW',result:{comparison_id:72,policy_revision:9,source_fingerprint:context.accepted_source_fingerprint}};
function harness(overrides={}) {
    const data=new Map(),calls=[],destinations=[],changes=[];
    const storage={getItem:key=>data.get(key)||null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};
    const h={data,calls,destinations,changes,storage};
    h.handler=async(url,options)=>{
        const u=new URL(url,'http://localhost');
        if(u.pathname.endsWith('/overview/'))return {revision:9,draft_version_id:5};
        if(u.searchParams.has('customer_id'))return {preview_context:context};
        if(u.searchParams.get('kind')==='salespersons')return {results:[{id:21,employee_code:'SP'}],next_after_id:null};
        if(u.searchParams.get('kind')==='customers')return {results:[{id:11,name:'مشتری تخصیص‌یافته'}],next_after_id:null};
        if(u.pathname.includes('/commands/'))return success;
        if(options.method==='POST')return success;
        throw Error('Unexpected URL');
    };
    const dependencies={actor:'7',storage,csrf:()=> 'masked-test-csrf',makeUUID:()=>command,navigate:url=>destinations.push(url),change:s=>changes.push(s.phase),
        fetcher:async(url,options)=>{calls.push({url,options});const result=await h.handler(url,options);return {ok:true,status:200,json:async()=>result};},...overrides};
    h.app=controller(dependencies);h.dependencies=dependencies;return h;
}
async function prepared(h){await h.app.start();await h.app.customers(21,selection.evaluation_date);await h.app.prepare(selection);assert.equal(h.app.state.phase,'prepared');}
const http=status=>{const e=Error('HTTP');e.status=status;return e;};

test('Control Center handoff refuses a different or invalid requested draft',async()=>{
    for(const expectedDraft of [6,0,NaN]){
        const h=harness({expectedDraft});await h.app.start();assert.equal(h.app.state.phase,'error');
        await h.app.prepare(selection);await h.app.create();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);
    }
    const h=harness({expectedDraft:5});await prepared(h);assert.equal(h.app.state.phase,'prepared');
});

test('authoritative choices, revision and source evidence precede one explicit POST and navigation',async()=>{
    const h=harness();await prepared(h);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);
    await h.app.create();
    const posts=h.calls.filter(c=>c.options.method==='POST');assert.equal(posts.length,1);
    assert.deepEqual(JSON.parse(posts[0].options.body),{...context,command_uuid:command});
    assert.equal(posts[0].options.headers['X-CSRFToken'],'masked-test-csrf');assert.equal(posts[0].options.credentials,'same-origin');
    assert.deepEqual(h.destinations,['/management/strategy/comparisons/72/']);assert.equal(h.data.size,0);
    assert.ok(h.calls.some(c=>c.url.includes('kind=customers') && c.url.includes('salesperson_id=21') && c.url.includes('evaluation_date=2026-10-16')));
});
test('no draft is an honest read-only state with no hidden initialization or choice requests',async()=>{
    const h=harness();h.handler=async()=>({revision:4,draft_version_id:null});await h.app.start();
    assert.equal(h.app.state.phase,'no-draft');assert.match(h.app.state.status,/پیش‌نویس/);assert.equal(h.calls.length,1);
    await h.app.prepare(selection);await h.app.create();assert.equal(h.calls.length,1);
});
test('no assignment and invalid selection cannot acquire or create a comparison',async()=>{
    const h=harness(),original=h.handler;h.handler=async(u,o)=>u.includes('kind=customers')?{results:[],next_after_id:null}:original(u,o);
    await h.app.start();await h.app.customers(21,selection.evaluation_date);await h.app.prepare(selection);
    assert.equal(h.app.state.prepared,null);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);
});
test('changed revision/draft, stale source and malformed preparation fail closed',async()=>{
    for(const mutate of [data=>({...data,expected_revision:8}),data=>({...data,customer_id:12}),data=>({...data,accepted_source_fingerprint:null})]){
        const h=harness(),original=h.handler;h.handler=async(u,o)=>u.includes('customer_id=')?{preview_context:mutate(context)}:original(u,o);
        await h.app.start();await h.app.customers(21,selection.evaluation_date);await h.app.prepare(selection);assert.equal(h.app.state.prepared,null);
    }
    const h=harness();await h.app.start();await h.app.customers(21,selection.evaluation_date);
    h.handler=async()=>({revision:10,draft_version_id:6});await h.app.prepare(selection);assert.equal(h.app.state.phase,'ready');assert.match(h.app.state.error,/تغییر/);
});
test('uncertain POST is persisted before dispatch; reload never resends it and GET recovers',async()=>{
    const h=harness();await prepared(h);const original=h.handler;
    h.handler=async(u,o)=>{if(o.method==='POST'){assert.equal(h.data.size,1);throw Error('network lost after commit');}return original(u,o);};
    await h.app.create();assert.equal(h.app.state.phase,'pending');assert.equal(h.destinations.length,0);
    const calls=h.calls.length;
    const recovered=controller(h.dependencies);await recovered.start();assert.equal(h.calls.length,calls);assert.equal(recovered.state.phase,'pending');
    await recovered.recover();assert.equal(h.calls.at(-1).options.method,'GET');assert.deepEqual(h.destinations,['/management/strategy/comparisons/72/']);
    assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
});
test('404 recovery is uncertain and permits only explicit same UUID/payload retry',async()=>{
    const h=harness();await prepared(h);let first=true;const original=h.handler;
    h.handler=async(u,o)=>{if(o.method==='POST' && first){first=false;throw Error('offline');}if(u.includes('/commands/'))throw http(404);return original(u,o);};
    await h.app.create();const body=h.app.state.pending;await h.app.recover();assert.equal(h.app.state.retry,true);assert.equal(h.app.state.pending,body);
    assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);await h.app.retry();
    assert.equal(h.calls.filter(c=>c.options.method==='POST').length,2);assert.equal(h.calls.at(-1).options.body,body);
});
test('recovery rejects wrong operation, fingerprint or revision and preserves pending evidence',async()=>{
    for(const wrong of [{...success,operation:'PUBLISH'},{...success,result:{...success.result,source_fingerprint:'b'.repeat(64)}},{...success,result:{...success.result,policy_revision:8}}]){
        const h=harness();await prepared(h);h.handler=async(u,o)=>{if(o.method==='POST')throw Error('uncertain');return wrong;};
        await h.app.create();await h.app.recover();assert.equal(h.app.state.phase,'pending');assert.equal(h.destinations.length,0);assert.equal(h.data.size,1);
    }
});
test('storage failure or tampered pending data prevents all POSTs and automatic repair',async()=>{
    const h=harness();await prepared(h);h.storage.setItem=()=>{throw Error('denied');};await h.app.create();assert.equal(h.app.state.phase,'blocked');
    assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);
    h.data.set('strategy-comparison-command-v1:7','tampered');const next=controller(h.dependencies);const count=h.calls.length;await next.start();
    assert.equal(next.state.phase,'blocked');assert.equal(h.calls.length,count);assert.equal(h.data.size,1);
});
for(const status of [400,401,403,409])test('definitive initial HTTP '+status+' requires renewed preparation, no retry',async()=>{
    const h=harness();await prepared(h);h.handler=async()=>{throw http(status);};await h.app.create();
    assert.equal(h.app.state.prepared,null);assert.equal(h.app.state.pending,null);assert.equal(h.app.state.phase,'ready');
    assert.equal(h.destinations.length,0);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);
});
test('changing a selection invalidates evidence; duplicate clicks cannot send a second command',async()=>{
    const h=harness();await prepared(h);h.app.invalidated();await h.app.create();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);
    await h.app.prepare(selection);let finish;h.handler=()=>new Promise(resolve=>finish=resolve);
    const first=h.app.create();await h.app.create();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);finish(success);await first;
});
test('late assignment results cannot overwrite newer salesperson/date choices',async()=>{
    const h=harness();await h.app.start();let finish;const original=h.handler;
    h.handler=async(u,o)=>u.includes('salesperson_id=21')?new Promise(resolve=>finish=resolve):original(u,o);
    const old=h.app.customers(21,selection.evaluation_date);await h.app.customers(22,selection.evaluation_date);
    finish({results:[{id:99}],next_after_id:null});await old;assert.deepEqual(h.app.state.customers.map(c=>c.id),[11]);
});
test('strict frozen preparation and safe text sinks; no rank or price calculation',()=>{
    assert.equal(validContext(context),true);assert.equal(validContext({...context,extra:1}),false);
    const source=fs.readFileSync(require.resolve('../../../static/management/js/strategy_comparison_create.js'),'utf8');
    assert.doesNotMatch(source,/innerHTML|insertAdjacentHTML|eval\(|\.sort\(|parseFloat\(/);
    assert.match(source,/option\.textContent=label\(row\)/);
});
