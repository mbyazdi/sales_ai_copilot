/* Inactive draft editing only. Business validation, CAS and receipts stay server-side. */
(function (scope) {
    'use strict';
    const API='/api/management/v1/strategy/', ALGORITHM='SAVED_RANK_OVERLAY_V1';
    const positive=x=>Number.isSafeInteger(x)&&x>0;
    const revision=x=>Number.isSafeInteger(x)&&x>=0;
    const keys=(x,names)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===names.length&&names.every(k=>Object.hasOwn(x,k));
    const uuid=x=>typeof x==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(x);
    const digest=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
    const copy=x=>JSON.parse(JSON.stringify(x));
    const scopes={PRODUCT:'products',BRAND:'brands',CATEGORY:'categories'};
    function normalize(value) {
        if(!keys(value,['schema_version','priority_rules','target_weight','promotion_rules'])||value.schema_version!==1||
            !Array.isArray(value.priority_rules)||!Array.isArray(value.promotion_rules)||!Number.isInteger(value.target_weight)||value.target_weight<0||value.target_weight>5)
            throw Error('تنظیمات یا تأثیر هدف معتبر نیست؛ امتیاز هدف باید عدد صحیح بین ۰ و ۵ باشد.');
        const seen=new Set();
        for(const r of value.priority_rules){
            if(!keys(r,['scope_type','scope_id','points'])||!Object.hasOwn(scopes,r.scope_type)||!positive(r.scope_id)||!Number.isInteger(r.points)||r.points<0||r.points>20)
                throw Error('امتیاز اولویت باید عدد صحیح بین ۰ و ۲۰ و مرجع آن معتبر باشد.');
            const id=r.scope_type+':'+r.scope_id;
            if(seen.has(id))throw Error('برای این مورد قبلاً قاعده ثبت شده است.');seen.add(id);
        }
        seen.clear();
        for(const r of value.promotion_rules){
            if(!keys(r,['promotion_id','points'])||!positive(r.promotion_id)||!Number.isInteger(r.points)||r.points<0||r.points>5)
                throw Error('امتیاز ترویجی باید عدد صحیح بین ۰ و ۵ و مرجع آن معتبر باشد.');
            if(seen.has(r.promotion_id))throw Error('این برنامهٔ ترویجی تکراری است.');seen.add(r.promotion_id);
        }
        return {schema_version:1,priority_rules:value.priority_rules.map(r=>({scope_type:r.scope_type,scope_id:r.scope_id,points:r.points}))
            .sort((a,b)=>a.scope_type<b.scope_type?-1:a.scope_type>b.scope_type?1:a.scope_id-b.scope_id),target_weight:value.target_weight,
            promotion_rules:value.promotion_rules.map(r=>({promotion_id:r.promotion_id,points:r.points})).sort((a,b)=>a.promotion_id-b.promotion_id)};
    }
    const same=(a,b)=>JSON.stringify(normalize(a))===JSON.stringify(normalize(b));
    function message(error){
        if(error.status===401)return 'نشست معتبر نیست؛ دوباره وارد حساب کاربری شوید. فرمان قبلی را حفظ کنید.';
        if(error.status===403)return error.code==='CSRF_FAILED'?'اعتبار امنیتی درخواست معتبر نیست؛ صفحه را دوباره باز کنید.':'دسترسی ذخیره یا بازیابی سیاست مجاز نیست.';
        if(error.status===409)return 'سیاست یا پیش‌نویس تغییر کرده است؛ تغییرات شما حفظ شد. ابتدا نتیجهٔ فرمان و سپس وضعیت تازه را بررسی کنید.';
        if(error.status===400)return 'تنظیمات یا مراجع معتبر نیستند؛ قواعد را بازبینی کنید.';
        return 'دریافت یا تأیید اطلاعات ممکن نشد؛ هیچ فرمانی خودکار تکرار نمی‌شود.';
    }
    function controller({actor,environment,canEdit,storage,fetcher,csrf,makeUUID,navigate,change}) {
        const key='strategy-draft-command-v1:'+environment+':'+actor;
        const state={phase:'loading',status:'در حال دریافت سیاست و گزینه‌ها…',error:'',head:null,config:null,baseline:null,
            options:{},next:{},pending:null,retry:false,dirty:false,savedVersion:null};
        let busy=false;
        const emit=()=>change(state);
        const editable=()=>canEdit&&!busy&&!state.pending&&['ready','saved','conflict'].includes(state.phase);
        async function request(path,method='GET',body){
            const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),30000);
            try{
                const response=await fetcher(API+path,{method,credentials:'same-origin',cache:'no-store',redirect:'error',signal:abort.signal,
                    headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-CSRFToken':csrf()}: {})},...(body?{body}: {})});
                const data=await response.json();
                if(!response.ok)throw Object.assign(Error('API_ERROR'),{status:response.status,code:data.code});
                return data;
            }finally{clearTimeout(timer);}
        }
        function headValid(h){
            if(!h||h.schema_version!==1||h.algorithm_version!==ALGORITHM||!revision(h.revision)||
                ![h.active_version_id,h.draft_version_id].every(id=>id===null||positive(id)))throw Error('INVALID_HEAD');
            normalize(h.active_config);return h;
        }
        async function version(id){
            const data=await request('versions/?'+new URLSearchParams({after_id:id-1,limit:1}));
            const v=data.results?.[0];
            if(!v||v.id!==id||v.algorithm_version!==ALGORITHM||!digest(v.config_hash))throw Error('INVALID_VERSION');
            normalize(v.config);return v;
        }
        async function page(kind,after=0){
            const data=await request('options/?'+new URLSearchParams({kind,after_id:after,limit:100}));
            if(!Array.isArray(data.results)||data.results.length>100||!data.results.every((r,i)=>positive(r.id)&&r.id>(i?data.results[i-1].id:after))||
                !(data.next_after_id===null||(data.results.length&&data.next_after_id===data.results.at(-1).id)))throw Error('INVALID_OPTIONS');
            state.options[kind]=after?(state.options[kind]||[]).concat(data.results):data.results;
            state.next[kind]=data.next_after_id;
        }
        async function load(preserve=false){
            if(busy||state.pending||state.phase==='blocked')return;
            const old=preserve&&state.config?copy(state.config):null;
            busy=true;state.phase='loading';state.error='';emit();
            try{
                const h=headValid(await request('overview/')),bounds=await request('options/');
                if(bounds.algorithm_version!==ALGORITHM||bounds.schema_version!==1||JSON.stringify(bounds.priority_bounds)!=='[0,20]'||
                    JSON.stringify(bounds.target_weight_bounds)!=='[0,5]'||JSON.stringify(bounds.promotion_points_bounds)!=='[0,5]'||bounds.adjustment_cap!==30)throw Error('INCOMPATIBLE_OPTIONS');
                const config=h.draft_version_id?(await version(h.draft_version_id)).config:h.active_config;
                for(const kind of ['products','brands','categories','promotions'])await page(kind);
                const check=headValid(await request('overview/'));
                if(check.revision!==h.revision||check.active_version_id!==h.active_version_id||check.draft_version_id!==h.draft_version_id)throw {status:409};
                state.head=h;state.baseline=normalize(config);state.config=old||copy(state.baseline);state.dirty=!same(state.config,state.baseline);
                state.savedVersion=h.draft_version_id;state.phase='ready';
                state.status=old?'وضعیت تازه دریافت شد؛ تغییرات محلی حفظ شده‌اند. پیش از ذخیره دوباره مرور کنید.':h.draft_version_id?'پیش‌نویس فعلی برای مرور بارگذاری شد. ویرایش آن نسخهٔ جدیدی می‌سازد.':'پیش‌نویسی موجود نیست؛ کپی محلی سیاست فعال هنوز ذخیره نشده است.';
            }catch(error){state.phase=state.head?'conflict':'error';state.error=message(error);}
            finally{busy=false;emit();}
        }
        function edit(config){if(!editable())return;state.config=copy(config);state.savedVersion=null;state.dirty=true;if(state.phase!=='conflict')state.phase='ready';state.error='';emit();}
        function reset(){if(!editable()||!state.baseline)return;state.config=copy(state.baseline);state.dirty=false;state.savedVersion=state.head.draft_version_id;state.error='';emit();}
        async function more(kind){
            if(busy||state.pending||!Object.hasOwn(state.next,kind)||state.next[kind]===null)return;
            busy=true;state.phase='loading-options';emit();
            try{await page(kind,state.next[kind]);}catch(error){state.error=message(error);}
            finally{busy=false;state.phase='ready';emit();}
        }
        function persist(body){
            const envelope=JSON.stringify({schema:1,actor,environment,body});storage.setItem(key,envelope);
            if(storage.getItem(key)!==envelope)throw Error('STORAGE_VERIFICATION_FAILED');state.pending=body;
        }
        function clear(){storage.removeItem(key);if(storage.getItem(key)!==null)throw Error('STORAGE_REMOVAL_FAILED');state.pending=null;state.retry=false;}
        async function result(data){
            const body=JSON.parse(state.pending),r=data.result;
            if(data.operation!=='SAVE_DRAFT'||!r||r.kind!=='CONFIGURATION'||!positive(r.version_id)||!digest(r.config_hash)||
                r.policy_revision!==body.expected_revision+1)throw Error('RESULT_MISMATCH');
            const v=await version(r.version_id);
            if(v.config_hash!==r.config_hash||!same(v.config,body.config))throw Error('VERSION_MISMATCH');
            const h=headValid(await request('overview/'));
            clear();state.head=h;state.config=normalize(v.config);state.baseline=copy(state.config);state.dirty=false;
            state.savedVersion=r.version_id;state.phase='saved';state.error='';
            state.status=h.draft_version_id===r.version_id?'پیش‌نویس ذخیره شد؛ سیاست فعال با ذخیرهٔ پیش‌نویس تغییر نمی‌کند.':
                'ذخیرهٔ این نسخه تأیید شد، اما پیش‌نویس فعلی تغییر کرده است. برای مقایسه، وضعیت تازه را مرور کنید.';
        }
        async function post(uncertain){
            let accepted=false;
            busy=true;state.phase='sending';state.retry=false;state.error='';state.status='در حال ذخیره؛ نتیجه فقط پس از تأیید سرور نمایش داده می‌شود…';emit();
            try{const data=await request('draft/','POST',state.pending);accepted=true;await result(data);}
            catch(error){
                if(!uncertain&&!accepted&&error.code!=='COMMAND_INTENT_CONFLICT'&&[400,401,403,404,409].includes(error.status)){
                    try{clear();state.phase=error.status===409?'conflict':'ready';}catch{state.phase='blocked';}
                    state.status='ذخیره تأیید نشد؛ تغییرات فرم حفظ شده‌اند. وضعیت و تنظیمات را بازبینی کنید.';
                }else{state.phase='pending';state.status='نتیجهٔ فرمان نامشخص است؛ فقط بررسی نتیجه یا تکرار صریح همان فرمان مجاز است.';}
                state.error=message(error);
            }finally{busy=false;emit();}
        }
        async function save(){
            if(!editable()||state.phase==='conflict')return;
            let config;
            try{config=normalize(state.config);}catch(error){state.error=error.message;emit();return;}
            try{
                const command=makeUUID();if(!uuid(command))throw Error('UUID_REQUIRED');
                persist(JSON.stringify({command_uuid:command,expected_revision:state.head.revision,config}));
            }catch{state.phase='blocked';state.error='ذخیرهٔ قابل بازیابی فرمان ممکن نیست؛ هیچ درخواستی ارسال نشد. اطلاعات محلی را حذف نکنید.';emit();return;}
            await post(false);
        }
        async function recover(){
            if(!canEdit||busy||!state.pending)return;
            busy=true;state.phase='recovering';state.error='';state.retry=false;emit();
            try{await result(await request('commands/'+JSON.parse(state.pending).command_uuid+'/'));}
            catch(error){state.phase='pending';state.retry=error.status===404;
                state.error=message(error);state.status=state.retry?'نتیجهٔ قطعی یافت نشد؛ فرمان ممکن است در حال اجرا باشد. فقط تکرار صریح همان فرمان مجاز است.':'فرمان قبلی محفوظ است؛ تا تعیین نتیجه فرمان جدیدی ارسال نمی‌شود.';}
            finally{busy=false;emit();}
        }
        async function retry(){if(canEdit&&!busy&&state.pending&&state.retry)await post(true);}
        async function compare(){
            if(!canEdit||busy||state.pending||state.dirty||!state.savedVersion)return;
            busy=true;emit();
            try{
                const h=headValid(await request('overview/'));
                if(h.draft_version_id!==state.savedVersion||h.revision!==state.head.revision)throw {status:409};
                navigate('/management/strategy/comparisons/?expected_draft='+state.savedVersion);
            }catch(error){state.phase='conflict';state.error=message(error);}
            finally{busy=false;emit();}
        }
        function start(){
            if(!actor||!environment){state.phase='blocked';state.error='هویت محیط و کاربر قابل تأیید نیست.';emit();return;}
            if(canEdit)try{
                const stored=storage.getItem(key);
                if(stored){
                    const e=JSON.parse(stored),b=JSON.parse(e.body);
                    if(!keys(e,['schema','actor','environment','body'])||e.schema!==1||e.actor!==actor||e.environment!==environment||
                        !keys(b,['command_uuid','expected_revision','config'])||!uuid(b.command_uuid)||!revision(b.expected_revision))throw Error('INVALID_PENDING');
                    normalize(b.config);state.pending=e.body;state.config=b.config;state.phase='pending';
                    state.status='فرمان تعیین‌تکلیف‌نشده محفوظ است؛ ابتدا نتیجهٔ ذخیره را بررسی کنید.';emit();return;
                }
            }catch{state.phase='blocked';state.error='اطلاعات فرمان مرورگر قابل تأیید نیست؛ هیچ فرمانی ارسال نمی‌شود. اطلاعات محلی را حذف نکنید.';emit();return;}
            return load();
        }
        return {state,start,load,edit,reset,more,save,recover,retry,compare};
    }
    function navigationMode(nav,compact,active){
        const summary=nav.querySelector('summary'),current=nav.querySelector('[aria-current="page"]');
        if(compact&&active&&active!==summary&&nav.contains(active))summary.focus();
        if(!compact&&active===summary)current.focus();
        nav.open=!compact;
    }
    function attach(document,root,window){
        const find=id=>root.querySelector('#'+id),number=x=>new Intl.NumberFormat('fa-IR').format(x);
        const nav=find('controlNavigation'),navMedia=window.matchMedia('(max-width: 900px)');
        const updateNav=()=>navigationMode(nav,navMedia.matches,document.activeElement);
        navMedia.addEventListener('change',updateNav);updateNav();
        const canEdit=root.dataset.canEdit==='true',form=find('controlForm');
        function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
        let lastConfig=null,lastOptions=null;
        const sections=[['PRODUCT','اولویت محصولات'],['BRAND','اولویت برندها'],['CATEGORY','اولویت گروه‌ها'],['PROMOTION','تأکید برنامه‌های ترویجی']];
        function numeric(input){return /^(0|[1-9][0-9]*)$/.test(input.value)?Number(input.value):null;}
        function renderRules(s){
            const opened=new Map([...root.querySelectorAll('details[data-scope]')].map(d=>[d.dataset.scope,d.open]));
            find('prioritySections').replaceChildren();find('promotionSection').replaceChildren();
            if(!s.config)return;
            for(const [type,title] of sections){
                const promo=type==='PROMOTION',kind=promo?'promotions':scopes[type],rows=promo?s.config.promotion_rules:s.config.priority_rules.filter(r=>r.scope_type===type);
                const section=node('details',undefined,'control-surface');section.dataset.scope=type;section.open=opened.has(type)?opened.get(type):window.innerWidth>600||type==='PRODUCT';
                section.append(node('summary',title+' · '+number(rows.length)));
                section.append(node('p',promo?'تأکید مدیریتی، بدون تغییر تخفیف؛ واجد شرایط بودن در مقایسهٔ مشتری مشخص می‌شود.':'یک امتیاز اختصاصی؛ نه درصد و نه احتمال خرید.','control-help'));
                const list=node('ul',undefined,'control-rules');
                for(const row of rows){
                    const id=promo?row.promotion_id:row.scope_id,ref=(s.options[kind]||[]).find(r=>r.id===id);
                    const li=node('li',undefined,'control-rule'),identity=node('div',undefined,'control-rule-identity');
                    identity.append(node('strong',ref?.name||'شناسهٔ '+number(id)),node('small',ref?(ref.product_code||ref.code||'شناسهٔ '+number(id)):'عنوان در گزینه‌های دریافت‌شده موجود نیست؛ وضعیت مرجع تأیید نشده است.'));
                    const label=node('label','امتیاز','control-score'),input=node('input');input.type='number';input.min='0';input.max=promo?'5':'20';input.step='1';input.inputMode='numeric';
                    input.id='controlPoint'+type+id;
                    input.value=row.points===null?'':String(row.points);input.setAttribute('aria-label','امتیاز '+title+'، '+(ref?.name||'شناسهٔ '+id));
                    input.addEventListener('input',()=>{const c=copy(app.state.config),array=promo?c.promotion_rules:c.priority_rules;array.find(r=>(promo?r.promotion_id:r.scope_id)===id&&(promo||r.scope_type===type)).points=numeric(input);app.edit(c);});
                    label.append(input);li.append(identity,label);
                    if(canEdit){const remove=node('button','حذف قاعده','control-remove');remove.type='button';remove.setAttribute('aria-label','حذف قاعدهٔ '+title+'، شناسهٔ '+id);
                        remove.addEventListener('click',()=>{const c=copy(app.state.config);if(promo)c.promotion_rules=c.promotion_rules.filter(r=>r.promotion_id!==id);else c.priority_rules=c.priority_rules.filter(r=>!(r.scope_type===type&&r.scope_id===id));app.edit(c);refreshRules('controlAdd'+type);});li.append(remove);}
                    list.append(li);
                }
                section.append(list);
                if(!rows.length)section.append(node('p','قاعده‌ای تعریف نشده است.','control-help'));
                if(canEdit){
                    const choiceLabel={PRODUCT:'انتخاب محصول',BRAND:'انتخاب برند',CATEGORY:'انتخاب گروه',PROMOTION:'انتخاب برنامهٔ ترویجی'}[type];
                    const add=node('div',undefined,'control-add'),label=node('label',choiceLabel),select=node('select');select.setAttribute('aria-label',choiceLabel);select.append(new window.Option('انتخاب کنید',''));
                    for(const r of s.options[kind]||[]){if(rows.some(row=>(promo?row.promotion_id:row.scope_id)===r.id))continue;select.append(new window.Option((r.name||'شناسهٔ '+r.id)+' · '+(r.product_code||r.code||r.id),String(r.id)));}
                    label.append(select);add.append(label);const button=node('button','افزودن قاعده','ds-button ds-button--secondary');button.type='button';button.id='controlAdd'+type;
                    button.addEventListener('click',()=>{const id=Number(select.value);if(!positive(id))return;const c=copy(app.state.config);if(promo)c.promotion_rules.push({promotion_id:id,points:0});else c.priority_rules.push({scope_type:type,scope_id:id,points:0});app.edit(c);refreshRules('controlPoint'+type+id);});add.append(button);
                    if(s.next[kind]!==null&&s.next[kind]!==undefined){const more=node('button','گزینه‌های بیشتر','strategy-text-button');more.type='button';more.addEventListener('click',()=>app.more(kind));add.append(more);}
                    section.append(add);
                    if(!(s.options[kind]||[]).length)section.append(node('p','گزینه‌ای در پاسخ فعلی موجود نیست.','control-help'));
                }
                (promo?find('promotionSection'):find('prioritySections')).append(section);
            }
        }
        function refreshRules(focusId){lastConfig=JSON.stringify(app.state.config);lastOptions=JSON.stringify(app.state.options);renderRules(app.state);if(focusId)find(focusId)?.focus();}
        const app=controller({actor:root.dataset.actor,environment:root.dataset.environment,canEdit,
            storage:{getItem:k=>window.localStorage.getItem(k),setItem:(k,v)=>window.localStorage.setItem(k,v),removeItem:k=>window.localStorage.removeItem(k)},
            fetcher:window.fetch.bind(window),csrf:()=>form.querySelector('[name=csrfmiddlewaretoken]').value,makeUUID:()=>window.crypto.randomUUID(),navigate:url=>window.location.assign(url),
            change:s=>{
                find('controlStatus').textContent=s.status;find('controlError').textContent=s.error;find('controlError').hidden=!s.error;
                const busy=['loading','loading-options','sending','recovering','blocked','error'].includes(s.phase),locked=busy||!!s.pending;
                find('controlFields').disabled=locked||!canEdit;
                if(s.head){find('controlActive').textContent=s.head.active_version_id?'نسخهٔ '+number(s.head.active_version_id):'سیاست خنثی';find('controlDraft').textContent=s.head.draft_version_id?'نسخهٔ '+number(s.head.draft_version_id):'پیش‌نویس موجود نیست';find('controlRevision').textContent='بازبینی سیاست: '+number(s.head.revision);}
                if(s.config){find('controlTarget').value=s.config.target_weight===null?'':s.config.target_weight;}
                // Input edits retain focus; only structural/reference changes rebuild rows.
                if(lastConfig===null||lastOptions!==JSON.stringify(s.options)){lastConfig=JSON.stringify(s.config);lastOptions=JSON.stringify(s.options);renderRules(s);}
                find('controlDirty').textContent=s.pending?'فرمان محفوظ؛ در انتظار تأیید':s.dirty?'تغییرات ذخیره‌نشده':s.savedVersion?'نسخهٔ بارگذاری‌شده؛ سیاست فعال جداست':'کپی محلی؛ هنوز پیش‌نویسی ساخته نشده است';
                if(canEdit){find('controlSave').disabled=locked||!s.config||s.phase==='conflict';find('controlReset').disabled=locked||!s.baseline;
                    find('controlRecover').hidden=!s.pending;find('controlRecover').disabled=busy&&s.phase!=='blocked';
                    find('controlRetry').hidden=!s.retry;find('controlRetry').disabled=busy;}
                find('controlCompare').disabled=locked||!canEdit||s.dirty||!s.savedVersion||s.savedVersion!==s.head?.draft_version_id||s.phase==='conflict';
                find('controlRefresh').disabled=busy&&s.phase!=='error'||!!s.pending;
            }});
        find('controlCap').textContent='سقف ترکیب اثر هر پیشنهاد ۳۰ امتیاز است؛ جمع امتیاز همهٔ ردیف‌های فرم محدود به ۳۰ نیست.';
        form.addEventListener('submit',async event=>{event.preventDefault();if(app.state.head?.draft_version_id&&!window.confirm('ذخیره، نسخهٔ جدیدی می‌سازد و جای پیش‌نویس فعلی را می‌گیرد. تاریخچه حفظ می‌شود. ادامه می‌دهید؟'))return;await app.save();if(app.state.error)find('controlError').focus();});
        find('controlTarget').addEventListener('input',event=>{if(!app.state.config)return;const c=copy(app.state.config);c.target_weight=numeric(event.target);app.edit(c);});
        find('controlRefresh').addEventListener('click',async()=>{if(app.state.dirty&&!window.confirm('وضعیت تازه دریافت و تغییرات محلی شما حفظ می‌شود. پیش از ذخیره دوباره مرور خواهید کرد. ادامه می‌دهید؟'))return;await app.load(app.state.dirty);refreshRules();});
        if(canEdit){find('controlReset').addEventListener('click',()=>{if(window.confirm('تغییرات محلی به نسخهٔ بارگذاری‌شده برگردد؟ هیچ دادهٔ سروری حذف نمی‌شود.')){app.reset();refreshRules();}});
            find('controlRecover').addEventListener('click',async()=>{await app.recover();refreshRules();});find('controlRetry').addEventListener('click',()=>{if(window.confirm('فقط همان فرمان محفوظ، بدون تغییر، دوباره ارسال شود؟'))app.retry();});}
        find('controlCompare').addEventListener('click',()=>app.compare());
        app.start();
    }
    if(typeof module!=='undefined'&&module.exports)module.exports={controller,normalize,message,navigationMode};
    if(scope.document){const root=scope.document.getElementById('strategyControl');if(root)attach(scope.document,root,scope);}
})(typeof window!=='undefined'?window:globalThis);
