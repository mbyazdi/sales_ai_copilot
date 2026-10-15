/* Server-owned review/amounts; only a frozen uncertain command is stored locally. */
(() => {
    'use strict';
    const root = document.querySelector('[data-request-page]');
    if (!root) return;
    const el = id => document.getElementById(id), notice = el('requestNotice');
    const key = `sales-request-submit:v1:${root.dataset.actorId}:${root.dataset.customerCode}:${root.dataset.visitId}`;
    const number = value => new Intl.NumberFormat('fa-IR').format(value);
    const money = value => typeof value === 'string' && /^(0|[1-9]\d*)$/.test(value) ? number(BigInt(value)) : 'نامشخص';
    const reason = {PRICE_CHANGED:'قیمت تغییر کرده است. به سبد بازگردید، قیمت جدید را صریحاً تأیید کنید و دوباره مرور کنید.',
        REVIEW_CHANGED:'شرایط موجودی یا بازبینی تغییر کرده است؛ بازبینی جدید را دریافت و دوباره تأیید کنید.',
        REVISION_CONFLICT:'سبد تغییر کرده است؛ بازبینی جدید را دریافت کنید.',
        COMMAND_CONFLICT:'شناسه ثبت با فرمان دیگری تداخل دارد؛ وضعیت ثبت را بررسی کنید.',
        REQUEST_NOT_DRAFT:'درخواست قبلاً ثبت شده است؛ وضعیت ثبت را بررسی کنید.',
        INVENTORY_UNKNOWN:'موجودی نامشخص است؛ این قلم قابل ثبت نیست.', OUT_OF_STOCK:'محصول ناموجود است.',
        INSUFFICIENT_STOCK:'موجودی برای تعداد انتخاب‌شده کافی نیست؛ سبد را اصلاح کنید.',
        PRICE_UNAVAILABLE:'قیمت فعلی در دسترس نیست.', PRICE_CONFIGURATION_ERROR:'قیمت فعلی قابل استفاده نیست.',
        INACTIVE_PRODUCT:'محصول غیرفعال است.', DRAFT_INVALID:'اطلاعات ذخیره‌شده نیاز به بررسی دارد؛ به سبد بازگردید.',
        EMPTY_BASKET:'درخواست هیچ قلمی ندارد؛ از سبد محصول انتخاب کنید.',
        VISIT_NOT_ACTIVE:'ثبت فقط در ویزیت در حال انجام مجاز است.', ACCESS_DENIED:'نشست یا دسترسی معتبر نیست؛ دوباره وارد حساب شوید.'};
    function valid(body) {
        if (body.version !== 1 || body.currency !== 'TOMAN' || body.customer?.code !== root.dataset.customerCode || String(body.visit?.id) !== root.dataset.visitId || !Array.isArray(body.lines) || !body.request || !Number.isSafeInteger(body.request.id) || !Number.isSafeInteger(body.request.revision) || !['DRAFT','SUBMITTED'].includes(body.request.status)) throw Error('Invalid review');
        if (!Number.isSafeInteger(body.item_count) || !Number.isSafeInteger(body.total_units)) throw Error('Invalid count');
        if (body.request.status === 'DRAFT' && (typeof body.can_submit !== 'boolean' || !/^[0-9a-f]{64}$/.test(body.review_fingerprint) || !Array.isArray(body.validation?.issues))) throw Error('Invalid validation');
        if (body.request.status === 'SUBMITTED' && (!body.request.number || !body.request.submitted_at || !body.prepared_message_snapshot || !body.totals)) throw Error('Invalid submission');
        for (const line of body.lines) if (!Number.isSafeInteger(line.id) || !Number.isSafeInteger(line.quantity) || line.quantity < 1 || !line.product_snapshot?.name) throw Error('Invalid line');
        return body;
    }
    function render(body) {
        const list = el('requestLines'); list.replaceChildren();
        el('requestCount').textContent = `${number(body.item_count)} محصول · ${number(body.total_units)} عدد`;
        for (const line of body.lines) {
            const row = document.createElement('article'); row.className = 'sr-line';
            const title = document.createElement('h3'), identity = document.createElement('bdi'); identity.textContent = line.product_snapshot.name; title.append(identity);title.id=`request-line-${line.id}-title`;
            const facts = document.createElement('dl'), quote = line.pricing_snapshot; facts.className='sr-line-main';
            const entries = [['تعداد',number(line.quantity) + ' عدد'], ['قیمت واحد',money(quote?.final_unit_price) + ' تومان'],
                ['جمع نهایی قلم',money(quote?.line_total) + ' تومان']];
            for (const [label, value] of entries) { const group = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = label; dd.textContent = value; if(label === 'جمع نهایی قلم')group.className='sr-line-total'; group.append(dt,dd); facts.append(group); }
            const details=document.createElement('details'),summary=document.createElement('summary'),support=document.createElement('div'),supportFacts=document.createElement('dl');details.className='sr-line-details';support.className='sr-line-support';support.id=`request-line-${line.id}-support`;
            summary.textContent='جزئیات قیمت و موجودی';summary.setAttribute('aria-label',`جزئیات قیمت و موجودی ${line.product_snapshot.name}`);summary.setAttribute('aria-controls',support.id);
            for(const [label,value] of [['قیمت پایه واحد',money(quote?.base_unit_price)+' تومان'],['تخفیف',money(quote?.discount_percentage)+'٪ · '+money(quote?.line_discount)+' تومان']]){const group=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;group.append(dt,dd);supportFacts.append(group);}
            const inventory = line.current?.inventory || line.eligibility_snapshot, stock = document.createElement('p'); stock.className = 'sr-inventory';
            stock.textContent = body.request.status === 'SUBMITTED' ? 'موجودی در زمان ثبت: ' : 'موجودی فعلی: ';
            stock.textContent += !inventory || inventory.inventory_state === 'UNKNOWN' ? 'نامشخص' : inventory.available_quantity === 0 ? 'ناموجود' : number(inventory.available_quantity) + ' عدد قابل ارائه';
            support.append(supportFacts,stock);details.append(summary,support);row.append(title,facts,details); list.append(row);
            if(line.current?.quote && line.current.quote.quote_fingerprint !== quote?.quote_fingerprint) {
                const changed=document.createElement('p');changed.className='sr-caption';changed.textContent='قیمت فعلی واحد: '+money(line.current.quote.final_unit_price)+' تومان؛ تأیید قیمت جدید از سبد انجام می‌شود.';row.append(changed);
            }
        }
        const totals = body.saved_totals || body.totals;
        el('requestTotals').hidden = !totals;
        if(totals) { el('requestBase').textContent=money(totals.base)+' تومان'; el('requestDiscount').textContent=money(totals.discount)+' تومان'; el('requestFinal').textContent=money(totals.final); }
        if(el('requestIssues')) {
            el('requestIssueList').replaceChildren();
            for(const issue of body.validation?.issues || []) { const item=document.createElement('li'), line=body.lines.find(l=>l.id===issue.line_id); item.textContent=(line?line.product_snapshot.name+' — ':'')+(reason[issue.code] || 'شرایط این قلم نیاز به بررسی دارد.'); el('requestIssueList').append(item); }
            el('requestIssues').hidden = !body.validation?.issues.length;
        }
    }
    if(root.dataset.requestPage === 'result') {
        try { render(valid(JSON.parse(el('requestInitialState').textContent))); } catch(_) { notice.textContent='اطلاعات ثبت‌شده در دسترس نیست؛ صفحه را دوباره دریافت کنید.'; }
        el('requestCopy').addEventListener('click',async()=>{
            try { await navigator.clipboard.writeText(el('requestCustomerMessage').value); notice.textContent='متن پیام کپی شد؛ پیامی ارسال نشده است.'; }
            catch(_) { el('requestCustomerMessage').focus(); el('requestCustomerMessage').select(); notice.textContent='کپی خودکار در دسترس نیست؛ متن انتخاب‌شده را دستی کپی کنید.'; }
        });
        return;
    }
    let state=null, pending=null, plan=null, sending=false, reading=false, needsReview=false, storageInvalid=false;
    const dialog=el('requestConfirmDialog'), form=el('requestConfirmForm');
    try {
        const saved=JSON.parse(window.sessionStorage.getItem(key)||'null');
        if(saved) {
            const payload=JSON.parse(saved.wire);
            if(saved.version!==1 || saved.actor!==root.dataset.actorId || saved.visit!==root.dataset.visitId || payload.customer_code!==root.dataset.customerCode || !/^[0-9a-f-]{36}$/.test(payload.command_uuid) || !Number.isSafeInteger(payload.expected_request_revision) || !/^[0-9a-f]{64}$/.test(payload.accepted_review_fingerprint) || !payload.catalog_context || !Number.isSafeInteger(saved.requestId))throw Error('Invalid pending command');
            pending=saved;
        }
    } catch(_) { storageInvalid=true; }
    function endpoint(path, kind) {
        const url=new URL(path,window.location.origin);
        if(url.origin!==window.location.origin || url.pathname!==`/api/sales-requests/v1/visits/${root.dataset.visitId}/${kind}/`)throw Error('Invalid endpoint');
        return url.pathname+url.search;
    }
    function result() {
        const url=new URL(root.dataset.resultUrl,window.location.origin);
        if(url.origin!==window.location.origin || url.pathname!==`/customers/${encodeURIComponent(root.dataset.customerCode)}/visits/${root.dataset.visitId}/sales-request/result/`)throw Error('Invalid result route');
        window.location.assign(url.pathname+url.search);
    }
    function sync() {
        el('requestRecovery').hidden=!pending&&!storageInvalid;
        el('requestPrepare').disabled=!state?.can_submit || state.request.status!=='DRAFT' || !root.dataset.catalogContext || pending || sending || reading || needsReview || storageInvalid;
        for(const id of ['requestRefresh','requestRecover','requestRetry','requestConfirm','requestCancel'])el(id).disabled=sending||reading;
        el('requestRetry').hidden=!pending;
    }
    async function read() {
        if(sending||reading)return;
        reading=true;sync();notice.textContent='در حال دریافت وضعیت درخواست…';
        try {
            const response=await fetch(endpoint(root.dataset.reviewUrl,'review')+'?'+new URLSearchParams({customer_code:root.dataset.customerCode}),{method:'GET',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
            const body=await response.json();
            if(!response.ok)throw Error(body.code==='NOT_FOUND'?'EMPTY_BASKET':body.code||'ACCESS_DENIED');
            state=valid(body);
            if(state.request.status==='SUBMITTED') { result();return; }
            render(state);needsReview=false;
            notice.textContent=pending||storageInvalid?'هنوز ثبت قطعی تأیید نشده است. هیچ فرمانی خودکار ارسال نمی‌شود؛ وضعیت را بررسی یا همان فرمان را صریحاً دوباره ارسال کنید.':!root.dataset.catalogContext?'زمینه فروش همراه صفحه نیست؛ از سبد وارد مرور درخواست شوید.':state.can_submit?'اقلام و مبلغ را بررسی کنید؛ ثبت نیاز به تأیید شما دارد.':'پیش از ثبت، موارد مشخص‌شده را بررسی کنید.';
        } catch(error) { state=null;notice.textContent=reason[error.message]||'دریافت درخواست انجام نشد؛ اتصال و نشست را بررسی کنید.'; }
        finally {reading=false;sync();}
    }
    function open(command) {
        plan=command;
        el('confirmDescription').textContent=`${number(command.count)} محصول · مبلغ نهایی ${money(command.total)} تومان`;
        el('requestConfirmNotice').textContent=pending?'این تلاش از همان شناسه و محتوای فرمان قبلی استفاده می‌کند.':'';
        el('requestConfirm').textContent=pending?'تلاش دوباره همان ثبت':'ثبت درخواست فروش';
        dialog.showModal();el('requestConfirm').focus();
    }
    el('requestPrepare').addEventListener('click',()=>{
        if(el('requestPrepare').disabled)return;
        const payload={customer_code:root.dataset.customerCode,command_uuid:window.crypto.randomUUID(),expected_request_revision:state.request.revision,catalog_context:root.dataset.catalogContext,accepted_review_fingerprint:state.review_fingerprint};
        open({version:1,actor:root.dataset.actorId,visit:root.dataset.visitId,requestId:state.request.id,wire:JSON.stringify(payload),total:state.saved_totals.final,count:state.item_count});
    });
    form.addEventListener('submit',async event=>{
        event.preventDefault();if(sending||!plan)return;
        const command=pending||plan,retry=Boolean(pending),csrf=form.querySelector('input[name="csrfmiddlewaretoken"]').value;
        if(!csrf) {el('requestConfirmNotice').textContent='نشست معتبر نیست؛ صفحه را تازه کنید.';return;}
        try {window.sessionStorage.setItem(key,JSON.stringify(command));pending=command;}
        catch(_) {el('requestConfirmNotice').textContent='ذخیره فرمان انجام نشد؛ هیچ درخواستی ارسال نشد.';return;}
        sending=true;sync();el('requestConfirmNotice').textContent='در حال ثبت درخواست…';
        try {
            const response=await fetch(endpoint(root.dataset.submitUrl,'submit'),{method:'POST',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRFToken':csrf},body:command.wire});
            const body=await response.json();
            if(response.status===201) {
                valid(body);
                const payload=JSON.parse(command.wire);
                if(body.request.status!=='SUBMITTED'||body.request.id!==command.requestId||body.request.revision!==payload.expected_request_revision+1||body.totals.final!==command.total||body.item_count!==command.count)throw Error('Unconfirmed submission');
                window.sessionStorage.removeItem(key);pending=null;dialog.close();result();
            } else if([400,403,404,409].includes(response.status)&&!retry) {
                window.sessionStorage.removeItem(key);pending=null;plan=null;needsReview=true;dialog.close();
                notice.textContent=reason[body.code]||'ثبت تأیید نشد؛ نشست و شرایط درخواست را بررسی کنید.';
                if(body.review)render(valid(body.review));
            } else throw Error('Uncertain submission');
        } catch(_) {notice.textContent=el('requestConfirmNotice').textContent='نتیجه ثبت مشخص نیست؛ ارسال خودکار انجام نمی‌شود. وضعیت را بررسی یا همان فرمان را صریحاً دوباره ارسال کنید.';}
        finally {sending=false;sync();}
    });
    el('requestCancel').addEventListener('click',()=>{if(!sending){dialog.close();plan=null;}});
    dialog.addEventListener('cancel',event=>{if(sending)event.preventDefault();else plan=null;});
    el('requestRefresh').addEventListener('click',read);el('requestRecover').addEventListener('click',read);
    el('requestRetry').addEventListener('click',()=>{if(pending&&!sending&&!reading)open(pending);});
    sync();read();
})();
