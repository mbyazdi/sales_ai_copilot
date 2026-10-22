/* Genuine Edge CDP screenshots, normal login only, dedicated protected browser profile.
   No browser dependencies, forced sessions, business POSTs or persistent Demo access. */
const fs = require('node:fs');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const assert = require('node:assert/strict');
const ROOT = path.resolve(__dirname,'..');
const STATE = path.join(ROOT,'venv/management-preview-live');
const creation=process.argv.includes('--creation');
const overview=process.argv.includes('--overview');
const control=process.argv.includes('--control');
const OUT = path.join(STATE,control?'me4b-artifacts':overview?'me3-artifacts':creation?'me2-artifacts':'me1-1-artifacts');
const URL = 'http://localhost:8901/management/strategy/comparisons/2/';
const manualLogin=process.argv.includes('--manual-login');
let stage='verified health';
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
async function until(fn, attempts=150) { for(let n=0;n<attempts;n++){const value=await fn();if(value)return value;await sleep(200);}throw new Error('Browser readiness timeout'); }
class CDP {
    constructor(socket) { this.socket=socket;this.next=0;this.pending=new Map();this.events=[];
        socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const pending=this.pending.get(data.id);this.pending.delete(data.id);
            if(data.error)pending.reject(new Error('CDP command failed'));else pending.resolve(data.result);}
            else this.events.forEach(handler=>handler(data));};
        socket.onclose=()=>{this.pending.forEach(pending=>pending.reject(new Error('Browser closed')));this.pending.clear();}; }
    send(method,params={}) {return new Promise((resolve,reject)=>{const id=++this.next;this.pending.set(id,{resolve,reject});this.socket.send(JSON.stringify({id,method,params}));});}
    async evaluate(expression) {const value=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
        if(value.exceptionDetails)throw new Error('Browser script failed');return value.result.value;}
}
async function main() {
    const edge='C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
    assert.ok(Number(process.versions.node.split('.')[0])>=22 && typeof WebSocket==='function','Node 22+ with WebSocket is required');
    assert.ok(fs.existsSync(edge),'Microsoft Edge executable is missing');
    fs.mkdirSync(OUT,{recursive:true});
    console.log('Node '+process.version+'; Edge available; output directory: '+OUT);
    // Existing Python health verification checks the signed exact preview identity.
    execFileSync(path.join(ROOT,'venv/Scripts/python.exe'),['-B','scripts/management_preview.py','status'],{cwd:ROOT,windowsHide:true});
    console.log('Signed isolated preview health verified on localhost:8901.');
    // Credentials remain untouched. Never extract a protected password or reuse
    // browser cookies; the owner signs in through the normal Django login page.
    if(!manualLogin) {
        console.log('Diagnostics passed. To capture, run: node scripts/capture_management_comparison.cjs --manual-login');
        return;
    }
    const browserProfile=path.join(OUT,'browser-'+Date.now());
    const log=fs.openSync(path.join(OUT,'browser.log'),'a');
    const browser=spawn(edge,[
        '--disable-gpu','--no-first-run','--disable-extensions','--disable-background-networking',
        '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+browserProfile,'about:blank'
    ],{windowsHide:false,stdio:['ignore',log,log]});
    let launchError;browser.once('error',error=>{launchError=error;});
    let cdp;
    try {
        stage='browser startup';
        const port=await until(()=>{
            if(launchError)throw new Error('Edge launch failed: '+launchError.code);
            if(browser.exitCode!==null)throw new Error('Edge exited before opening its local debugger');
            try{return Number(fs.readFileSync(path.join(browserProfile,'DevToolsActivePort'),'utf8').split('\n')[0]);}catch{return false;}
        });
        const target=await (await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
        const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
        cdp=new CDP(socket);const writes=[],errors=[];
        stage='normal login';
        cdp.events.push(event=>{if(event.method==='Network.requestWillBeSent' && !['GET','HEAD','OPTIONS'].includes(event.params.request.method))
            writes.push({method:event.params.request.method,path:new globalThis.URL(event.params.request.url).pathname});
            if(event.method==='Runtime.exceptionThrown')errors.push('browser exception');});
        await cdp.send('Page.enable');await cdp.send('Runtime.enable');await cdp.send('Network.enable');
        await cdp.send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
        await cdp.send('Page.navigate',{url:URL});
        await until(()=>cdp.evaluate('Boolean(document.querySelector("input[name=username]"))'));
        await cdp.send('Page.bringToFront');
        await cdp.evaluate('document.querySelector("input[name=username]").value="manager";document.querySelector("input[name=password]").focus();true');
        console.log('Sign in as manager in the separate Edge window within 3 minutes. Enter the password ONLY there.');
        stage='waiting for owner login and frozen comparison (3-minute limit)';
        await until(()=>cdp.evaluate('Boolean(document.querySelector("#comparisonContent") && !document.querySelector("#comparisonContent").hidden)'),900);
        stage='frozen order';
        const evidence=await cdp.evaluate('fetch("/api/management/v1/strategy/comparisons/2/",{credentials:"same-origin",cache:"no-store"}).then(r=>r.json()).then(d=>({before:d.outputs.before.after_ids,after:d.outputs.after.after_ids,labels:d.labels,output_digest:d.output_digest}))');
        const order=await cdp.evaluate('JSON.stringify({before:[...document.querySelectorAll("#beforeRanking button")].map(b=>Number(b.dataset.recommendationId)),after:[...document.querySelectorAll("#afterRanking button")].map(b=>Number(b.dataset.recommendationId))})');
        const actual=JSON.parse(order);assert.deepEqual(actual.before,evidence.before);assert.deepEqual(actual.after,evidence.after);
        const dimensions=[];
        async function screenshot(name,width) {
            await cdp.evaluate('scrollTo(0,0);true');
            const metrics=await cdp.send('Page.getLayoutMetrics');
            const shot=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,
                clip:{x:0,y:0,width,height:Math.ceil(metrics.cssContentSize.height),scale:1}});
            const file=path.join(OUT,name);fs.writeFileSync(file,Buffer.from(shot.data,'base64'));
            console.log('Screenshot saved: '+file+' ('+fs.statSync(file).size+' bytes)');
        }
        for(const [width,name] of [[1440,'01-M04-Desktop-1440.png'],[768,'02-M04-Tablet-768.png'],[390,'03-M04-Mobile-390.png']]) {
            stage='layout '+width;
            await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width===390});
            await sleep(300);
            const layout=await cdp.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,panels:[...document.querySelectorAll(".strategy-panel")].map(n=>({hidden:n.hidden,x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y})),tabsHidden:document.querySelector("#comparisonTabs").hidden,detailsOpen:document.querySelector("#focusDetails").open,limitationsOpen:document.querySelector("#limitations").open,focus:document.querySelector("#focusSummary").textContent})');
            assert.ok(layout.scrollWidth<=width,'No horizontal overflow');assert.match(layout.focus,/۷۰٫۰۰۰۰/);assert.match(layout.focus,/۳۷٫۵۰/);
            if(width>600){assert.equal(layout.panels[0].y,layout.panels[1].y);assert.ok(layout.panels.every(p=>!p.hidden));}
            else {assert.equal(layout.panels[0].hidden,true);assert.equal(layout.panels[1].hidden,false);}
            assert.equal(layout.tabsHidden,width>600);assert.equal(layout.detailsOpen,width>600);assert.equal(layout.limitationsOpen,false);
            dimensions.push({width,scrollWidth:layout.scrollWidth,layout:width>600?'side-by-side':'After tab'});
            await screenshot(name,width);
        }
        stage='mobile tabs and disclosure keyboard';
        await cdp.evaluate('document.querySelector("#afterTab").focus();true');
        await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
        await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
        assert.equal(await cdp.evaluate('document.activeElement.id==="beforeTab" && !document.querySelector("#beforePanel").hidden && document.querySelector("#afterPanel").hidden'),true);
        await screenshot('04-M04-Mobile-Before-390.png',390);
        stage='keyboard product selection';
        await cdp.send('Page.bringToFront');
        await cdp.evaluate('document.querySelectorAll("#beforeRanking button")[1].focus();true');
        assert.equal(await cdp.evaluate('document.activeElement===document.querySelectorAll("#beforeRanking button")[1]'),true,'Visible ranking button must receive focus');
        await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
        await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await until(()=>cdp.evaluate('document.activeElement===document.querySelectorAll("#beforeRanking button")[1] && document.activeElement.getAttribute("aria-pressed")==="true"'),20);
        await cdp.evaluate('document.querySelector("#focusDetails summary").focus();true');
        await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
        await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await until(()=>cdp.evaluate('document.querySelector("#focusDetails").open'),20);
        await screenshot('05-M04-Mobile-Factors-390.png',390);
        await cdp.evaluate('document.querySelector(".strategy-commercial summary").focus();true');
        await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
        await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await until(()=>cdp.evaluate('document.querySelector(".strategy-commercial").open'),20);
        if(creation) {
            stage='creation entry and no-draft state';
            await cdp.send('Page.navigate',{url:'http://localhost:8901/management/strategy/comparisons/'});
            await until(()=>cdp.evaluate('Boolean(document.querySelector("#creationStatus") && document.querySelector("#creationStatus").textContent.includes("پیش‌نویس سیاستی موجود نیست"))'));
            assert.equal(await cdp.evaluate('document.querySelector("#creationFields").disabled && document.querySelector("#createComparison").hidden && !document.querySelector("#beforeRanking")'),true);
            for(const [width,name] of [[1440,'06-ME2-No-Draft-Desktop-1440.png'],[768,'07-ME2-No-Draft-Tablet-768.png'],[390,'08-ME2-No-Draft-Mobile-390.png']]){
                await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width===390});await sleep(200);
                assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true,'Creation panel must not overflow');
                await screenshot(name,width);
            }
        }
        if(overview) {
            stage='overview authoritative read-only dashboard';
            await cdp.send('Page.navigate',{url:'http://localhost:8901/management/strategy/'});
            await until(()=>cdp.evaluate('Boolean(document.querySelector("#overviewContent") && !document.querySelector("#overviewContent").hidden)'));
            const proof=await cdp.evaluate('(async()=>{const h=await fetch("/api/management/v1/strategy/overview/",{cache:"no-store"}).then(r=>r.json());const v=await fetch("/api/management/v1/strategy/versions/?after_id=0&limit=6",{cache:"no-store"}).then(r=>r.json());const digits=x=>String(x).replace(/[0-9]/g,c=>"۰۱۲۳۴۵۶۷۸۹"[Number(c)]);const field=n=>document.querySelector("[data-overview-field="+n+"]").textContent;return {countsMatch:field("comparisons")===digits(h.comparison_count)&&field("revision")===digits(h.revision)&&field("versions")===digits(h.version_count),targetMatch:field("target")===digits(h.active_config.target_weight)+" امتیاز",rulesMatch:document.querySelector("#overviewPriorities").children.length===h.active_config.priority_rules.length&&document.querySelector("#overviewPromotions").children.length===h.active_config.promotion_rules.length,historyMatch:JSON.stringify([...document.querySelectorAll("#overviewHistory li")].map(li=>Number(li.dataset.versionId)))===JSON.stringify(v.results.map(r=>r.id)),link:document.querySelector(".strategy-heading a").getAttribute("href")};})()');
            assert.equal(proof.countsMatch,true);assert.equal(proof.targetMatch,true);assert.equal(proof.rulesMatch,true);assert.equal(proof.historyMatch,true);assert.equal(proof.link,'/management/strategy/comparisons/');
            for(const [width,name] of [[1440,'06-M01-Overview-Desktop-1440.png'],[768,'07-M01-Overview-Tablet-768.png'],[390,'08-M01-Overview-Mobile-390.png']]){
                await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width===390});await sleep(200);
                assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true,'Overview must not overflow');
                await screenshot(name,width);
            }
        }
        if(control){
            stage='Control Center read-only browser verification';
            await cdp.send('Page.navigate',{url:'http://localhost:8901/management/strategy/control/'});
            await until(()=>cdp.evaluate('Boolean(document.querySelector("#controlFields") && !document.querySelector("#controlFields").disabled)'));
            const proof=await cdp.evaluate('(async()=>{const h=await fetch("/api/management/v1/strategy/overview/",{credentials:"same-origin",cache:"no-store"}).then(r=>r.json());return {draft:h.draft_version_id,active:h.active_version_id,hasSave:!!document.querySelector("#controlSave"),compareDisabled:document.querySelector("#controlCompare").disabled};})()');
            assert.equal(proof.draft,null,'Preserve live preview no-draft state');assert.equal(proof.hasSave,true);assert.equal(proof.compareDisabled,true);
            for(const [width,name] of [[1440,'01-M02-Control-Desktop-1440.png'],[768,'02-M02-Control-Tablet-768.png'],[390,'03-M02-Control-Mobile-390.png']]){
                await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width===390});await sleep(250);
                if(width===390)await cdp.evaluate('document.querySelectorAll("#prioritySections details").forEach((d,i)=>d.open=i===0);true');
                const layout=await cdp.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,error:document.querySelector("#controlError").textContent})');
                assert.ok(layout.scrollWidth<=width,'Control Center must not overflow');assert.equal(layout.error,'');dimensions.push({controlWidth:width,scrollWidth:layout.scrollWidth});await screenshot(name,width);
            }
            await cdp.evaluate('document.querySelector("#controlTarget").focus();true');
            assert.equal(await cdp.evaluate('document.activeElement.id'), 'controlTarget');
            await cdp.evaluate('const t=document.querySelector("#controlTarget");t.value="3";t.dispatchEvent(new Event("input",{bubbles:true}));true');
            assert.equal(await cdp.evaluate('document.querySelector("#controlDirty").textContent.includes("ذخیره‌نشده")'),true);
            console.log('Control Center verified at 1440/768/390; local editing only; no draft or policy mutation.');
        }
        await cdp.send('Page.navigate',{url:'http://localhost:8901/management/strategy/comparisons/999999/'});
        stage='not-found state';
        await until(()=>cdp.evaluate('Boolean(document.querySelector("#comparisonError") && !document.querySelector("#comparisonError").hidden)'));
        assert.equal(await cdp.evaluate('document.querySelector("#comparisonContent").hidden'),true);
        // Standard application logout; no session/cookie injection or auth bypass.
        await cdp.evaluate('document.querySelector(".shell-logout").requestSubmit();true');
        await until(()=>cdp.evaluate('Boolean(document.querySelector("input[name=password]"))'));
        assert.equal(errors.length,0);assert.ok(writes.every(item=>['/accounts/login/','/accounts/logout/'].includes(item.path)));
        const report={page:URL,dimensions,before:actual.before,after:actual.after,keyboard:true,disclosure:true,error404:true,
            businessPosts:0,writes,browserErrors:errors.length,creationNoDraft:creation,overviewVerified:overview,controlVerified:control,screenshots:['01-M04-Desktop-1440.png','02-M04-Tablet-768.png','03-M04-Mobile-390.png','04-M04-Mobile-Before-390.png','05-M04-Mobile-Factors-390.png',...(creation?['06-ME2-No-Draft-Desktop-1440.png','07-ME2-No-Draft-Tablet-768.png','08-ME2-No-Draft-Mobile-390.png']:[]),...(overview?['06-M01-Overview-Desktop-1440.png','07-M01-Overview-Tablet-768.png','08-M01-Overview-Mobile-390.png']:[]),...(control?['01-M02-Control-Desktop-1440.png','02-M02-Control-Tablet-768.png','03-M02-Control-Mobile-390.png']:[])]};
        fs.writeFileSync(path.join(OUT,'browser-proof.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify(report));
    } catch(error) {
        if(cdp && stage.startsWith('keyboard')) {
            const diagnostic=await cdp.evaluate('({activeTag:document.activeElement.tagName,activeId:document.activeElement.id,pressed:document.activeElement.getAttribute("aria-pressed"),pageFocused:document.hasFocus(),visiblePanels:[...document.querySelectorAll(".strategy-panel")].map(p=>({id:p.id,hidden:p.hidden}))})').catch(()=>({unavailable:true}));
            console.error('Keyboard diagnostic (no session data): '+JSON.stringify(diagnostic));
        }
        throw error;
    } finally {
        if(cdp){try{await cdp.send('Browser.close');}catch{}cdp.socket.close();}
        else if(browser.exitCode===null) browser.kill(); // Only this newly spawned, separate headless process.
        fs.closeSync(log);
    }
}
main().catch(error=>{console.error('Capture failed at '+stage+': '+error.name+': '+String(error.message).split('\n')[0]);
    console.error('No successful capture is claimed. Output directory: '+OUT);process.exitCode=1;});
