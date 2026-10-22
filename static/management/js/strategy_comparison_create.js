/* Explicit PREVIEW commands only. Rankings and commercial facts stay server-side. */
(function (scope) {
    'use strict';
    const API = '/api/management/v1/strategy/';
    const integer = value => Number.isSafeInteger(value) && value > 0;
    const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
    const fields = ['customer_id','salesperson_id','proposed_version_id','expected_revision','evaluation_date','accepted_source_fingerprint'];
    function validContext(value) {
        return value && Object.keys(value).length === fields.length && fields.every(key => Object.hasOwn(value,key)) &&
            ['customer_id','salesperson_id','proposed_version_id'].every(key => integer(value[key])) &&
            Number.isSafeInteger(value.expected_revision) && value.expected_revision >= 0 &&
            typeof value.evaluation_date==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value.evaluation_date) &&
            typeof value.accepted_source_fingerprint==='string' && /^[0-9a-f]{64}$/.test(value.accepted_source_fingerprint);
    }
    function message(error) {
        if (error.status === 401) return 'نشست معتبر نیست؛ دوباره وارد حساب کاربری شوید.';
        if (error.status === 403) return error.code === 'CSRF_FAILED' ? 'اعتبار امنیتی درخواست معتبر نیست؛ صفحه را دوباره باز کنید.' : 'دسترسی یا تخصیص مشتری تغییر کرده است؛ گزینه‌ها را دوباره دریافت کنید.';
        if (error.status === 409) return 'نسخهٔ سیاست یا داده‌های مبنا تغییر کرده است؛ گزینه‌ها و شواهد را دوباره آماده کنید.';
        if (error.status === 400) return 'انتخاب‌ها یا تاریخ معتبر نیست؛ اطلاعات را بررسی و دوباره آماده کنید.';
        return 'دریافت یا تأیید نتیجه ممکن نشد. وضعیت فرمان را بررسی کنید؛ هیچ تکرار خودکاری انجام نمی‌شود.';
    }
    function controller({actor,fetcher,storage,csrf,makeUUID,navigate,change,expectedDraft=null}) {
        const key = 'strategy-comparison-command-v1:' + actor;
        const state = {phase:'loading',status:'در حال دریافت وضعیت سیاست…',error:'',people:[],customers:[],draft:null,
            revision:null,prepared:null,pending:null,retry:false,peopleNext:null,customerNext:null};
        let choiceSerial = 0;
        const emit = () => change(state);
        const fail = error => { state.error=message(error);emit(); };
        function save(body) {
            const stored=JSON.stringify({schema:1,actor,body});storage.setItem(key,stored);
            if(storage.getItem(key)!==stored) throw new Error('PENDING_STORAGE_REQUIRED');
            state.pending=body;
        }
        function clear() { storage.removeItem(key);state.pending=null;state.retry=false; }
        async function request(path,method='GET',body) {
            const abort = new AbortController();const timer=setTimeout(()=>abort.abort(),30000);
            try {
                const response=await fetcher(API+path,{method,credentials:'same-origin',cache:'no-store',redirect:'error',signal:abort.signal,
                    headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-CSRFToken':csrf()}: {})},...(body?{body}: {})});
                let data;try{data=await response.json();}catch{throw new Error('UNREADABLE_RESPONSE');}
                if(!response.ok){const error=new Error('API_ERROR');error.status=response.status;error.code=data.code;throw error;}
                return data;
            } finally {clearTimeout(timer);}
        }
        function invalidated() {state.prepared=null;state.error='';if(!state.pending)state.phase=state.draft?'ready':'no-draft';emit();}
        function result(data) {
            const body=JSON.parse(state.pending);
            if(data.operation!=='PREVIEW' || !data.result || !integer(data.result.comparison_id) ||
                data.result.source_fingerprint!==body.accepted_source_fingerprint || data.result.policy_revision!==body.expected_revision) throw new Error('COMMAND_RESULT_MISMATCH');
            const destination='/management/strategy/comparisons/'+data.result.comparison_id+'/';
            clear();state.phase='success';state.status='مقایسه ثبت شد؛ در حال باز کردن نتیجه…';emit();navigate(destination);
        }
        async function page(kind,after=0,selection={}) {
            if(state.pending || state.phase==='blocked')return;
            const serial=kind==='customers'?++choiceSerial:null;
            if(!after){state[kind==='customers'?'customers':'people']=[];state[kind==='customers'?'customerNext':'peopleNext']=null;emit();}
            const query={kind,after_id:after,limit:100,...selection};
            try {
                const data=await request('options/?'+new URLSearchParams(query));
                if(serial!==null && serial!==choiceSerial)return;
                if(!Array.isArray(data.results) || !data.results.every(item=>integer(item.id)) ||
                    !(data.next_after_id===null || (integer(data.next_after_id) && data.next_after_id>after)))throw new Error('INVALID_OPTIONS');
                const collection=kind==='customers'?'customers':'people';
                state[collection]=after?state[collection].concat(data.results):data.results;
                state[kind==='customers'?'customerNext':'peopleNext']=data.next_after_id;
                state.status=kind==='customers' && !state.customers.length ? 'برای این فروشنده و تاریخ، مشتریِ تخصیص‌یافته‌ای موجود نیست.' : 'زمینه را انتخاب کنید؛ سپس شواهد مقایسه را آماده کنید.';emit();
            } catch(error){if(serial===null || serial===choiceSerial)fail(error);}
        }
        async function load() {
            if(state.pending || state.phase==='blocked')return;
            state.phase='loading';state.error='';state.prepared=null;state.draft=null;state.customers=[];state.people=[];emit();
            try {
                const head=await request('overview/');
                if(!Number.isSafeInteger(head.revision) || head.revision<0 || !(head.draft_version_id===null || integer(head.draft_version_id)))throw new Error('INVALID_OVERVIEW');
                state.revision=head.revision;state.draft=head.draft_version_id;
                if(expectedDraft!==null && (!integer(expectedDraft) || head.draft_version_id!==expectedDraft))throw {status:409};
                state.phase=state.draft?'ready':'no-draft';
                state.status=state.draft?'در حال دریافت فروشندگان…':'پیش‌نویس سیاستی موجود نیست. ایجاد مقایسه پس از تهیهٔ پیش‌نویس در دسترس خواهد بود؛ هیچ سیاستی خودکار ساخته نمی‌شود.';emit();
                if(state.draft)await page('salespersons');
            } catch(error){state.phase='error';fail(error);}
        }
        async function customers(salesperson,date,after=0) {
            invalidated();
            if(!integer(salesperson) || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {choiceSerial++;state.customers=[];state.customerNext=null;emit();return;}
            await page('customers',after,{salesperson_id:salesperson,evaluation_date:date});
        }
        async function prepare(selection) {
            if(state.pending || state.phase!=='ready')return;
            state.phase='preparing';state.error='';state.prepared=null;state.status='در حال تأیید نسخه و داده‌های مبنا…';emit();
            try {
                if(!state.people.some(p=>p.id===selection.salesperson_id) || !state.customers.some(p=>p.id===selection.customer_id) || selection.proposed_version_id!==state.draft)throw {status:400};
                const head=await request('overview/');
                if(expectedDraft!==null && head.draft_version_id!==expectedDraft)throw {status:409};
                if(head.revision!==state.revision || head.draft_version_id!==state.draft)throw {status:409};
                const query={...selection,expected_revision:head.revision};
                const data=await request('options/?'+new URLSearchParams(query));
                const context=data.preview_context;
                if(!validContext(context) || Object.keys(query).some(k=>query[k]!==context[k]))throw new Error('INVALID_PREPARATION');
                state.prepared=JSON.stringify(context);state.phase='prepared';state.status='شواهد آماده است. با «ایجاد مقایسه» نتیجهٔ ثابت جدید ثبت می‌شود؛ سیاست فعال تغییر نمی‌کند.';emit();
            } catch(error){state.phase='ready';fail(error);}
        }
        async function post(uncertain) {
            state.phase='sending';state.retry=false;state.error='';state.status='در حال ثبت مقایسه؛ نتیجه فقط پس از تأیید سرور نمایش داده می‌شود…';emit();
            try {result(await request('comparisons/','POST',state.pending));}
            catch(error) {
                if(!uncertain && [400,401,403,404,409].includes(error.status)) {
                    clear();state.prepared=null;state.phase='ready';state.status='فرمان تأیید نشد؛ گزینه‌ها را تازه و شواهد را دوباره آماده کنید.';
                } else {state.phase='pending';state.status='نتیجهٔ فرمان هنوز تأیید نشده است. فقط بررسی نتیجه یا تکرار صریح همان فرمان مجاز است.';}
                fail(error);
            }
        }
        async function create() {
            if(state.phase!=='prepared' || state.pending)return;
            try {
                const command=makeUUID();if(!uuid(command))throw new Error('UUID_REQUIRED');
                save(JSON.stringify({...JSON.parse(state.prepared),command_uuid:command}));
            } catch(error){state.phase='blocked';state.error='ذخیرهٔ امن فرمان در مرورگر ممکن نیست؛ هیچ درخواستی ارسال نشد.';emit();return;}
            await post(false);
        }
        async function recover() {
            if(!state.pending || state.phase==='sending' || state.phase==='recovering')return;
            state.phase='recovering';state.error='';state.retry=false;state.status='در حال بررسی فقط‌خواندنی نتیجه…';emit();
            try {result(await request('commands/'+JSON.parse(state.pending).command_uuid+'/'));}
            catch(error) {
                state.phase='pending';
                if(error.status===404){state.retry=true;state.status='نتیجهٔ قطعی یافت نشد؛ فرمان ممکن است هنوز در حال اجرا باشد. فقط با انتخاب شما همان فرمان بدون تغییر تکرار می‌شود.';}
                else {state.error=message(error);state.status='فرمان قبلی محفوظ است؛ ایجاد فرمان جدید تا تعیین نتیجه متوقف می‌ماند.';}
                emit();
            }
        }
        async function retry() {if(state.phase==='pending' && state.retry)await post(true);}
        function start() {
            try {
                const stored=storage.getItem(key);
                if(stored){
                    const envelope=JSON.parse(stored),body=JSON.parse(envelope.body),{command_uuid,...context}=body;
                    if(envelope.schema!==1 || envelope.actor!==actor || Object.keys(envelope).length!==3 || !uuid(command_uuid) || !validContext(context))throw new Error('INVALID_PENDING');
                    state.pending=envelope.body;state.phase='pending';state.status='فرمان تعیین‌تکلیف‌نشده از نشست قبلی محفوظ است؛ ابتدا نتیجه را بررسی کنید.';emit();return;
                }
            } catch(error){state.phase='blocked';state.error='شواهد فرمان ذخیره‌شده قابل تأیید نیست؛ عملیات متوقف شد. بدون بررسی، اطلاعات محلی را پاک نکنید.';emit();return;}
            return load();
        }
        return {state,start,load,customers,morePeople:()=>page('salespersons',state.peopleNext),prepare,create,recover,retry,invalidated};
    }
    function attach(document,root,window) {
        const find=id=>root.querySelector('#'+id), form=find('comparisonCreateForm'), person=find('creationSalesperson'), customer=find('creationCustomer'), day=find('creationDate'), draft=find('creationDraft');
        function options(select,rows,placeholder,label) {
            const old=select.value;const empty=document.createElement('option');empty.value='';empty.textContent=placeholder;
            select.replaceChildren(empty,...rows.map(row=>{const option=document.createElement('option');option.value=String(row.id);option.textContent=label(row);return option;}));
            if(rows.some(row=>String(row.id)===old))select.value=old;
        }
        const selection=()=>({salesperson_id:Number(person.value),customer_id:Number(customer.value),evaluation_date:day.value,proposed_version_id:Number(draft.value)});
        const requestedDraft=new URLSearchParams(window.location.search).get('expected_draft');
        const app=controller({actor:root.dataset.actorId,expectedDraft:requestedDraft===null?null:Number(requestedDraft),fetcher:window.fetch.bind(window),storage:{getItem:key=>window.localStorage.getItem(key),setItem:(key,value)=>window.localStorage.setItem(key,value),removeItem:key=>window.localStorage.removeItem(key)},
            csrf:()=>form.querySelector('[name=csrfmiddlewaretoken]').value,makeUUID:()=>window.crypto.randomUUID(),navigate:url=>window.location.assign(url),change:state=>{
                find('creationStatus').textContent=state.status;find('creationError').textContent=state.error;find('creationError').hidden=!state.error;
                const busy=['loading','preparing','sending','recovering'].includes(state.phase);
                find('creationFields').disabled=!state.draft || busy || !!state.pending || state.phase==='blocked';
                find('prepareComparison').disabled=state.phase!=='ready';
                find('createComparison').hidden=state.phase!=='prepared';
                find('recoverComparison').hidden=!state.pending;find('recoverComparison').disabled=busy;
                find('retryComparison').hidden=!state.retry;find('retryComparison').disabled=busy;
                find('reloadCreation').disabled=busy || !!state.pending || state.phase==='blocked';
                options(person,state.people,'انتخاب فروشنده',row=>[row.first_name,row.last_name,row.employee_code].filter(Boolean).join(' · '));
                options(customer,state.customers,'انتخاب مشتری',row=>[row.name,row.customer_code].filter(Boolean).join(' · '));
                customer.disabled=!state.customers.length;
                options(draft,state.draft?[{id:state.draft}]:[],'پیش‌نویسی در دسترس نیست',row=>'پیش‌نویس نسخهٔ '+row.id);
                if(state.draft)draft.value=String(state.draft);
                find('moreSalespersons').hidden=!state.peopleNext;find('moreCustomers').hidden=!state.customerNext;
                find('moreSalespersons').disabled=busy;find('moreCustomers').disabled=busy;
                const hint=document.getElementById('creationHint');hint.textContent=state.phase==='no-draft'?'پیش‌نویس موجود نیست':state.pending?'فرمان تعیین‌تکلیف‌نشده':'انتخاب زمینهٔ مقایسه';
            }});
        form.addEventListener('submit',event=>{event.preventDefault();if(form.reportValidity())app.prepare(selection());});
        person.addEventListener('change',()=>app.customers(Number(person.value),day.value));
        day.addEventListener('change',()=>app.customers(Number(person.value),day.value));
        customer.addEventListener('change',app.invalidated);draft.addEventListener('change',app.invalidated);
        find('createComparison').addEventListener('click',app.create);find('recoverComparison').addEventListener('click',app.recover);
        find('retryComparison').addEventListener('click',app.retry);find('reloadCreation').addEventListener('click',app.load);
        find('moreSalespersons').addEventListener('click',app.morePeople);
        find('moreCustomers').addEventListener('click',()=>app.customers(Number(person.value),day.value,app.state.customerNext));
        app.start();return app;
    }
    if(typeof module!=='undefined' && module.exports)module.exports={controller,validContext,message};
    if(scope.document){const root=scope.document.getElementById('strategyCreation');if(root)attach(scope.document,root,scope);}
})(typeof window!=='undefined'?window:globalThis);
