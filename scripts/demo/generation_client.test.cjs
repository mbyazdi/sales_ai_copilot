const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'generation_client.js'),'utf8');
function client(generation='g1',proof='signed-g1'){
 const sent=[],forms=[{method:'post',querySelector:()=>null,append(node){this.field=node}}];
 const document={currentScript:{dataset:{demoGeneration:generation,demoProof:proof}},readyState:'complete',querySelectorAll:()=>forms,createElement:()=>({})};
 const window={fetch:(input,init)=>{sent.push({input,init});return Promise.resolve({status:200})}};
 vm.runInNewContext(source,{window,document,location:new URL('http://localhost:8900/'),URL,Headers,Object,JSON});
 return {window,sent,forms,api:window.DemoGeneration};
}
test('new command stores proof outside wire payload and preserves UUID',()=>{
 const c=client(),command={payload:{command_uuid:'uuid-1',quantity:2}},before=JSON.stringify(command.payload);
 c.api.bind(command);assert.equal(JSON.stringify(command.payload),before);assert.equal(command.demoGeneration.proof,'signed-g1');
});
test('reload/retry retains old generation proof instead of restamping',()=>{
 const old=client(),command={wire:JSON.stringify({command_uuid:'uuid-1'})};old.api.bind(command);
 const pending=JSON.parse(JSON.stringify(command)),fresh=client('g2','signed-g2');fresh.api.bind(pending);
 assert.equal(fresh.api.headers(pending)['X-Demo-Generation-Proof'],'signed-g1');assert.equal(pending.wire,command.wire);
});
test('unmarked pending command does not acquire fresh document proof',async()=>{
 const c=client('g2','signed-g2'),pending={payload:{command_uuid:'old'}};
 await c.window.fetch('/api/visits/',{method:'POST',headers:c.api.headers(pending),body:JSON.stringify(pending.payload)});
 assert.equal(c.sent[0].init.headers.get('X-Demo-Generation-Proof'),'');
});
test('UUID POST without explicit envelope proof is never auto-upgraded',async()=>{
 const c=client();await c.window.fetch('/api/',{method:'POST',body:JSON.stringify({command_uuid:'old'})});
 assert.equal(c.sent[0].init.headers.get('X-Demo-Generation-Proof'),null);
});
test('legacy Start request carries fixed document proof and unchanged body',async()=>{
 const c=client();await c.window.fetch('/api/start/',{method:'POST',body:'{}'});
 assert.equal(c.sent[0].init.headers.get('X-Demo-Generation-Proof'),'signed-g1');assert.equal(c.sent[0].init.body,'{}');
});
test('GET and external requests unchanged; no automatic retry',async()=>{
 const c=client();const input={method:'GET'};await c.window.fetch('/api/',input);await c.window.fetch('https://example.invalid/',{method:'POST'});
 assert.equal(c.sent.length,2);assert.equal(c.sent[0].init,input);assert.equal(c.sent[1].init.headers,undefined);
});
test('normal form gains hidden proof without visual controls',()=>{
 const c=client();assert.equal(c.forms[0].field.type,'hidden');assert.equal(c.forms[0].field.name,'_demo_generation_proof');assert.equal(c.forms[0].field.value,'signed-g1');
});
