/* Real Edge + HTTP acceptance, only an enrolled disposable fixture supplied over stdin.
   No UAT password/session extraction, persistent preview access or fake successful API results. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {createHmac,timingSafeEqual}=require('node:crypto');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
assert.match(input.database,/^test_mc1_[0-9a-f]{32}$/);
const base=new URL(input.base);assert.equal(base.hostname,'localhost');assert.ok(![8900,8901,5432,5433].includes(Number(base.port)));
assert.equal(base.protocol,'http:');
const output=path.resolve(input.output),root=path.resolve(__dirname,'..');
assert.ok(output.startsWith(path.join(root,'venv','me4b-f2-artifacts')+path.sep));
const API='/api/management/v1/strategy/',PAGE='/management/strategy/control/';
let cdp,browser,stage='startup',failure=null;
const matrix=[],requests=[],errors=[],screenshots=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
class CDP{
 constructor(socket){this.socket=socket;this.pending=new Map();this.serial=0;this.events=[];
  socket.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){const p=this.pending.get(d.id);if(!p)return;this.pending.delete(d.id);clearTimeout(p.timer);d.error?p.reject(Error('CDP_ERROR')):p.resolve(d.result);}else this.events.forEach(f=>f(d));};
  socket.onclose=()=>{for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'));}this.pending.clear();};}
 send(method,params={}){return new Promise((resolve,reject)=>{const id=++this.serial,timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP_TIMEOUT'));},15000);this.pending.set(id,{resolve,reject,timer});this.socket.send(JSON.stringify({id,method,params}));});}
 async eval(expression){const v=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(v.exceptionDetails)throw Error('BROWSER_SCRIPT_ERROR');return v.result.value;}
}
async function until(expression){const end=Date.now()+15000;while(Date.now()<end){if(await cdp.eval(expression))return;await sleep(80);}throw Error('STATE_TIMEOUT');}
async function check(name,action){stage=name;await action();matrix.push({name,result:'PASS'});console.log('PASS '+name);}
async function go(){await cdp.send('Page.navigate',{url:input.base+PAGE});await until('Boolean(document.querySelector("#controlFields")&&!document.querySelector("#controlFields").disabled)');}
async function click(selector){const found=await cdp.eval(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return false;e.click();return true;})()`);assert.equal(found,true,'CONTROL_NOT_ACTIONABLE');}
async function key(key,code,vk,text){await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:vk,...(text?{text,unmodifiedText:text}: {})});await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:vk});}
async function type(selector,value){await cdp.eval(`document.querySelector(${JSON.stringify(selector)}).focus();true`);await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2});await cdp.send('Input.insertText',{text:value});}
async function section(scope){await cdp.eval(`document.querySelector('details[data-scope="${scope}"]').open=true;true`);}
async function add(scope,id){await section(scope);await cdp.eval(`(()=>{const s=document.querySelector('details[data-scope="${scope}"] select');s.value=${JSON.stringify(String(id))};s.dispatchEvent(new Event('change',{bubbles:true}));return s.value;})()`);await click('#controlAdd'+scope);}
async function api(route,method='GET',body){return cdp.eval(`(async()=>{const r=await fetch(${JSON.stringify(API+route)},{method:${JSON.stringify(method)},credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json',...( ${JSON.stringify(method)}==='POST'?{'X-CSRFToken':document.querySelector('#controlForm [name=csrfmiddlewaretoken]').value}:{})},${body?'body:'+JSON.stringify(JSON.stringify(body))+',':''}});return {status:r.status,replayed:r.headers.get('Idempotent-Replayed'),data:await r.json()};})()`);}
async function saved(){await until('document.querySelector("#controlStatus").textContent.includes("ذخیره شد")');}
async function shot(name,width){const m=await cdp.send('Page.getLayoutMetrics');const p=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height:Math.ceil(m.cssContentSize.height),scale:1}});fs.writeFileSync(path.join(output,name),Buffer.from(p.data,'base64'));screenshots.push(name);}
const draftPosts=()=>requests.filter(r=>r.path===API+'draft/'&&r.method==='POST');
async function run(){
 fs.mkdirSync(output,{recursive:true});
 const identity=await(await fetch(input.base+'/__f2_fixture_identity__/',{redirect:'error'})).json();
 assert.equal(identity.database,input.database);assert.equal(identity.role,input.runtime);
 const expected=createHmac('sha256',input.attestation_key).update(JSON.stringify({database:identity.database,role:identity.role})).digest('hex');
 assert.equal(timingSafeEqual(Buffer.from(expected,'hex'),Buffer.from(identity.attestation,'hex')),true);
 input.attestation_key=null;
 const edge='C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';assert.ok(fs.existsSync(edge));
 const profile=path.join(output,'browser-profile');
 browser=spawn(edge,['--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 let port;for(let n=0;n<100;n++){try{port=Number(fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0]);if(port)break;}catch{}await sleep(100);}assert.ok(port,'EDGE_STARTUP');
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});cdp=new CDP(socket);
 cdp.events.push(e=>{if(e.method==='Network.requestWillBeSent'){const r=e.params.request,u=new URL(r.url);assert.ok(u.origin===base.origin||['data:','about:'].includes(u.protocol),'UNAPPROVED_HTTP_TARGET');if(u.origin===base.origin&&!['GET','HEAD','OPTIONS'].includes(r.method))requests.push({path:u.pathname,method:r.method,...(u.pathname===API+'draft/'?{body:r.postData}: {})});}
  if(e.method==='Runtime.exceptionThrown')errors.push('browser exception');
  if(e.method==='Page.javascriptDialogOpening')cdp.send('Page.handleJavaScriptDialog',{accept:true}).catch(()=>{});
 });
 await cdp.send('Page.enable');await cdp.send('Runtime.enable');await cdp.send('Network.enable');await cdp.send('Emulation.setFocusEmulationEnabled',{enabled:true});
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:390,height:1000,deviceScaleFactor:1,mobile:true});
 await check('normal manager session login and CSRF',async()=>{
  await cdp.send('Page.navigate',{url:input.base+PAGE});await until('Boolean(document.querySelector("input[name=password]"))');
  await cdp.eval(`document.querySelector('[name=username]').value=${JSON.stringify(input.username)};document.querySelector('[name=password]').value=${JSON.stringify(input.password)};document.querySelector('form').requestSubmit();true`);
  input.password=null;await until('Boolean(document.querySelector("#controlFields")&&!document.querySelector("#controlFields").disabled)');
  const h=await api('overview/');assert.equal(h.status,200);assert.equal(h.data.draft_version_id,null);
  const csrf=await cdp.eval(`fetch('${API}draft/',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(async r=>({status:r.status,code:(await r.json()).code}))`);assert.deepEqual(csrf,{status:403,code:'CSRF_FAILED'});
 });
 await check('mobile native navigation keyboard Enter / Space / Tab',async()=>{
  assert.equal(await cdp.eval('document.querySelector("#controlNavigation").open'),false);
  await cdp.eval('document.querySelector("#controlNavigationSummary").focus();true');await key('Enter','Enter',13,'\r');
  await until('document.querySelector("#controlNavigation").open');
  await key('Tab','Tab',9);assert.equal(await cdp.eval('document.activeElement.getAttribute("href")'),'/management/strategy/');
  await cdp.eval('document.querySelector("#controlNavigationSummary").focus();true');await key(' ','Space',32,' ');await until('!document.querySelector("#controlNavigation").open');
 });
 await check('reference pagination and product / brand / category selections',async()=>{
  for(const scope of ['PRODUCT','BRAND','CATEGORY','PROMOTION']){await section(scope);const before=await cdp.eval(`document.querySelector('details[data-scope="${scope}"] select').options.length`);
   await click(`details[data-scope="${scope}"] .control-add > .strategy-text-button`);await until('!document.querySelector("#controlFields").disabled');
   assert.ok(await cdp.eval(`document.querySelector('details[data-scope="${scope}"] select').options.length>${before}`));}
  await add('PRODUCT',1);await add('BRAND',11);await add('CATEGORY',21);await add('PROMOTION',1);
  assert.equal(await cdp.eval('document.activeElement.id'),'controlPointPROMOTION1');
  assert.equal(await cdp.eval('document.querySelector("#controlCompare").disabled'),true);
 });
 await check('numeric edits / explicit zero / target / promotion / focus',async()=>{
  await type('#controlPointPRODUCT1','0');assert.equal(await cdp.eval('document.activeElement.id'),'controlPointPRODUCT1');
  await type('#controlPointBRAND11','20');await type('#controlPointCATEGORY21','15');await type('#controlTarget','4');await type('#controlPointPROMOTION1','5');
  assert.ok(await cdp.eval('document.querySelector("#controlDirty").textContent.includes("ذخیره‌نشده")'));
 });
 await check('invalid numbers produce Persian errors and zero POSTs',async()=>{
  for(const invalid of ['21','1.5','-1','']){const n=draftPosts().length;await type('#controlPointPRODUCT1',invalid);await click('#controlSave');await until('!document.querySelector("#controlError").hidden');assert.equal(draftPosts().length,n);assert.ok(await cdp.eval('document.querySelector("#controlError").textContent.includes("عدد صحیح")'));}
  await type('#controlPointPRODUCT1','0');
 });
 await check('duplicate choices excluded / tampered duplicates rejected',async()=>{
  assert.equal(await cdp.eval(`Boolean(document.querySelector('details[data-scope=PRODUCT] select').querySelector('option[value="1"]'))`),false);
  await cdp.eval('const s=document.querySelector("details[data-scope=PRODUCT] select");s.add(new Option("مرجع تکراری آزمایشی","1"));s.value="1";true');await click('#controlAddPRODUCT');
  const n=draftPosts().length;await click('#controlSave');await until('document.querySelector("#controlError").textContent.includes("قبلاً")');assert.equal(draftPosts().length,n);
  await click('#controlReset');await until('document.querySelectorAll(".control-rule").length===0');
 });
 await check('rule deletion / reset restores captured configuration',async()=>{
  await add('PRODUCT',1);await click('details[data-scope=PRODUCT] .control-remove');assert.equal(await cdp.eval('document.activeElement.id'),'controlAddPRODUCT');
  assert.equal(await cdp.eval('document.querySelectorAll(".control-rule").length'),0);
  await type('#controlTarget','3');await click('#controlReset');assert.equal(await cdp.eval('document.querySelector("#controlTarget").value'),'0');
 });
 await check('confirmed draft save / fresh reload / exact replay',async()=>{
  await add('PRODUCT',1);await type('#controlPointPRODUCT1','0');await add('BRAND',11);await type('#controlPointBRAND11','20');await add('CATEGORY',21);await add('PROMOTION',1);await type('#controlTarget','3');
  await click('#controlSave');await saved();const body=JSON.parse(draftPosts().at(-1).body);
  const replay=await api('draft/','POST',body);assert.equal(replay.status,200);assert.equal(replay.replayed,'true');
  await go();assert.equal(await cdp.eval('document.querySelector("#controlPointPRODUCT1").value'),'0');assert.equal(await cdp.eval('document.querySelector("#controlCompare").disabled'),false);
 });
 await check('390 / 768 / 1440 RTL, no overflow, keyboard resize focus',async()=>{
  for(const width of [390,768,1440]){await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width===390});await sleep(100);
   const layout=await cdp.eval('({rtl:document.documentElement.dir,scrollWidth:document.documentElement.scrollWidth,width:innerWidth,nav:document.querySelector("#controlNavigation").open})');assert.equal(layout.rtl,'rtl');assert.ok(layout.scrollWidth<=width);assert.equal(layout.nav,width>900);
   for(const sc of ['PRODUCT','BRAND','CATEGORY','PROMOTION'])await section(sc);
   const clipped=await cdp.eval('[...document.querySelectorAll("#controlForm input:not([type=hidden]),#controlForm select,#controlForm button")].filter(e=>e.getClientRects().length&&!e.hidden).some(e=>{const r=e.getBoundingClientRect();return r.width<40||r.x<0||r.right>innerWidth;})');assert.equal(clipped,false,'CLIPPED_FORM_CONTROL');
   await shot('01-Control-'+width+'.png',width);}
  await cdp.eval('document.querySelector("#controlNavigation [aria-current]").focus();true');await cdp.send('Emulation.setDeviceMetricsOverride',{width:390,height:1000,deviceScaleFactor:1,mobile:true});await sleep(100);
  assert.equal(await cdp.eval('document.activeElement.id'),'controlNavigationSummary');
 });
 await check('real stale revision / retained edits / explicit refresh',async()=>{
  const h=(await api('overview/')).data,v=(await api('versions/?after_id='+(h.draft_version_id-1)+'&limit=1')).data.results[0];
  const changed=await api('draft/','POST',{command_uuid:crypto.randomUUID(),expected_revision:h.revision,config:v.config});assert.equal(changed.status,201);
  await type('#controlTarget','4');await click('#controlSave');await until('document.querySelector("#controlError").textContent.includes("تغییر")');assert.equal(await cdp.eval('document.querySelector("#controlTarget").value'),'4');
  await click('#controlRefresh');await until('!document.querySelector("#controlFields").disabled');assert.equal(await cdp.eval('document.querySelector("#controlTarget").value'),'4');
  await click('#controlSave');await saved();
 });
 await check('committed POST response loss / reload / GET-only recovery',async()=>{
  let intercepted=false;const on=e=>{if(e.method==='Fetch.requestPaused'){intercepted=true;cdp.send('Fetch.failRequest',{requestId:e.params.requestId,errorReason:'ConnectionReset'}).catch(()=>{});}};cdp.events.push(on);
  await cdp.send('Fetch.enable',{patterns:[{urlPattern:input.base+API+'draft/',requestStage:'Response'}]});
  await type('#controlTarget','2');const n=draftPosts().length;await click('#controlSave');await until('!document.querySelector("#controlRecover").hidden&&!document.querySelector("#controlRecover").disabled');assert.equal(intercepted,true);await cdp.send('Fetch.disable');cdp.events=cdp.events.filter(f=>f!==on);
  await sleep(300);assert.equal(draftPosts().length,n+1);await cdp.send('Page.reload');await until('!document.querySelector("#controlRecover").hidden');assert.equal(draftPosts().length,n+1);
  await click('#controlRecover');await saved();assert.equal(draftPosts().length,n+1);await go();assert.equal(await cdp.eval('document.querySelector("#controlTarget").value'),'2');
 });
 await check('uncommitted request failure / 404 / explicit identical retry only',async()=>{
  let blocked=true;const on=e=>{if(e.method==='Fetch.requestPaused'){cdp.send(blocked?'Fetch.failRequest':'Fetch.continueRequest',blocked?{requestId:e.params.requestId,errorReason:'ConnectionReset'}:{requestId:e.params.requestId}).catch(()=>{});}};cdp.events.push(on);
  await cdp.send('Fetch.enable',{patterns:[{urlPattern:input.base+API+'draft/',requestStage:'Request'}]});await type('#controlTarget','1');await click('#controlSave');await until('!document.querySelector("#controlRecover").hidden&&!document.querySelector("#controlRecover").disabled');const body=draftPosts().at(-1).body;
  blocked=false;await cdp.send('Fetch.disable');cdp.events=cdp.events.filter(f=>f!==on);await click('#controlRecover');await until('!document.querySelector("#controlRetry").hidden');const n=draftPosts().length;await sleep(250);assert.equal(draftPosts().length,n);
  await click('#controlRetry');await saved();assert.equal(draftPosts().at(-1).body,body);
 });
 await check('unresolved existing ID retained / nonexistent reference rejected',async()=>{
  const h=(await api('overview/')).data,v=(await api('versions/?after_id='+(h.draft_version_id-1)+'&limit=1')).data.results[0];
  const cfg={...v.config,priority_rules:[{scope_type:'PRODUCT',scope_id:3900,points:0}]};assert.equal((await api('draft/','POST',{command_uuid:crypto.randomUUID(),expected_revision:h.revision,config:cfg})).status,201);
  await go();assert.ok(await cdp.eval('document.querySelector("details[data-scope=PRODUCT]").textContent.includes("وضعیت مرجع تأیید نشده")'));await click('#controlSave');await saved();
  await section('PRODUCT');await cdp.eval('const s=document.querySelector("details[data-scope=PRODUCT] select");s.add(new Option("مرجع ناموجود آزمایشی","999999"));s.value="999999";true');await click('#controlAddPRODUCT');await click('#controlSave');await until('document.querySelector("#controlError").textContent.includes("مراجع")');
  assert.ok(await cdp.eval('Boolean(document.querySelector("#controlPointPRODUCT999999"))'));await click('#controlReset');
 });
 await check('same UUID / different intent conflict retains pending recovery',async()=>{
  const original=JSON.parse(draftPosts().find(r=>{try{return JSON.parse(r.body).config.target_weight===3;}catch{return false;}}).body);
  await cdp.eval(`window.crypto.randomUUID=()=>${JSON.stringify(original.command_uuid)};true`);await type('#controlTarget','5');await click('#controlSave');await until('!document.querySelector("#controlRecover").hidden&&!document.querySelector("#controlRecover").disabled');
  const n=draftPosts().length;await click('#controlRecover');await until('document.querySelector("#controlStatus").textContent.includes("محفوظ")');assert.equal(draftPosts().length,n);assert.equal(await cdp.eval('document.querySelector("#controlFields").disabled'),true);
 });
 await check('normal logout / nonstaff permission rejection / no session bypass',async()=>{
  await cdp.eval('document.querySelector(".shell-logout").requestSubmit();true');await until('Boolean(document.querySelector("input[name=password]"))');
  await cdp.eval(`document.querySelector('[name=username]').value=${JSON.stringify(input.nonstaff)};document.querySelector('[name=password]').value=${JSON.stringify(input.nonstaff_password)};document.querySelector('form').requestSubmit();true`);
  input.nonstaff_password=null;
  await until('!document.querySelector("input[name=password]")');await cdp.send('Page.navigate',{url:input.base+PAGE});await until('document.body.textContent.includes("دسترسی مجاز نیست")');
  assert.equal(await cdp.eval(`fetch('${API}overview/',{credentials:'same-origin'}).then(r=>r.status)`),403);
  assert.equal(await cdp.eval('Boolean(document.querySelector("#strategyControl"))'),false);
 });
 assert.deepEqual(errors,[]);
}
run().catch(e=>{failure={stage,error:e.name,code:String(e.message).split('\n')[0].slice(0,160)};console.error('Browser acceptance failed at '+stage+' ('+e.name+')');}).finally(async()=>{
 if(cdp){try{await cdp.send('Browser.close');}catch{}cdp.socket.close();}else if(browser)browser.kill();
 const proof={passed:!failure,fixture:input.database,base:input.base,matrix,failure,browser_errors:errors,screenshots,
  draft_post_count:draftPosts().length,mutation_paths:[...new Set(requests.map(r=>r.path))]};
 fs.writeFileSync(path.join(output,'browser-proof.json'),JSON.stringify(proof,null,2));
 if(failure)process.exitCode=1;else console.log('Browser acceptance PASS; redacted report: '+path.join(output,'browser-proof.json'));
});
