/* Explicit Visit completion only. Server state and durable receipts are authoritative. */
(() => {
    'use strict';
    const root = document.querySelector('[data-visit-finish]');
    if (!root) return;
    const el = id => document.getElementById(id);
    const key = 'visit-completion:v1:' + root.dataset.actorId + ':' + root.dataset.customerCode + ':' + root.dataset.visitId;
    const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
    const statuses = {PLANNED:'برنامه‌ریزی‌شده',IN_PROGRESS:'در حال انجام',COMPLETED:'تکمیل‌شده',CANCELLED:'لغوشده'};
    const reason = {
        ACCESS_DENIED:'نشست یا دسترسی معتبر نیست؛ دوباره وارد حساب شوید.',
        NOT_FOUND:'زمینه مشتری یا ویزیت در دسترس نیست.',
        INVALID_INPUT:'اطلاعات فرمان معتبر نیست؛ وضعیت ویزیت را بررسی کنید.',
        COMMAND_CONFLICT:'این شناسه قبلاً برای فرمان دیگری استفاده شده است؛ وضعیت ثبت‌شده را بررسی کنید.',
        VISIT_NOT_ACTIVE:'ویزیت در حال انجام نیست؛ وضعیت فعلی را دریافت کنید.'
    };
    const dialog = el('finishDialog'), notice = el('finishNotice');
    let state = null, verified = false, pending = null, plan = null, sending = false, reading = false, storageInvalid = false;
    function endpoint() {
        const url = new URL(root.dataset.apiUrl, window.location.origin);
        if (url.origin !== window.location.origin || url.pathname !== '/api/visits/v1/visits/' + root.dataset.visitId + '/completion/' || url.search || url.hash) throw Error('Invalid endpoint');
        return url.pathname;
    }
    function validRequest(request) {
        if (request !== null && (!request || !Number.isSafeInteger(request.id) || request.id < 1 ||
            !Number.isSafeInteger(request.revision) || request.revision < 0 || !['DRAFT','SUBMITTED'].includes(request.status))) throw Error('Invalid request');
    }
    function validResult(body) {
        if (body?.version !== 1 || body.success !== true || body.customer?.code !== root.dataset.customerCode ||
            String(body.visit?.id) !== root.dataset.visitId || body.visit.status !== 'COMPLETED' ||
            !uuid(body.command_uuid) || typeof body.completed_at !== 'string' || !body.completed_at ||
            !Object.hasOwn(body,'request') || !Object.hasOwn(body,'acknowledgement')) throw Error('Unconfirmed completion');
        validRequest(body.request);
        if (body.acknowledgement !== null && (!Number.isSafeInteger(body.acknowledgement?.id) ||
            body.request?.status !== 'SUBMITTED' || body.acknowledgement.sales_request_id !== body.request.id)) throw Error('Invalid acknowledgement');
        return body;
    }
    function validState(body) {
        if (body?.version !== 1 || body.customer?.code !== root.dataset.customerCode ||
            String(body.visit?.id) !== root.dataset.visitId || !Object.hasOwn(statuses,body.visit.status) ||
            body.can_complete !== (body.visit.status === 'IN_PROGRESS') || !Object.hasOwn(body,'request') ||
            !Object.hasOwn(body,'recorded_result')) throw Error('Invalid state');
        validRequest(body.request);
        if (body.recorded_result !== null) validResult(body.recorded_result);
        return body;
    }
    function restore() {
        try {
            const saved = JSON.parse(window.sessionStorage.getItem(key) || 'null');
            if (!saved) return;
            const payload = JSON.parse(saved.wire);
            if (saved.version !== 1 || saved.actor !== root.dataset.actorId || saved.visit !== root.dataset.visitId ||
                saved.customer !== root.dataset.customerCode || payload.customer_code !== root.dataset.customerCode ||
                !uuid(payload.command_uuid) || Object.keys(payload).sort().join(',') !== 'command_uuid,customer_code') throw Error('Invalid pending');
            pending = saved;
        } catch (_) { storageInvalid = true; }
    }
    function clearPending() {
        try { window.sessionStorage.removeItem(key); pending = null; }
        catch (_) { storageInvalid = true; }
    }
    function sync() {
        const active = verified && state?.can_complete, busy = sending || reading;
        el('finishPrepare').disabled = !active || Boolean(pending) || storageInvalid || busy;
        el('finishRecovery').hidden = !pending && !storageInvalid;
        el('finishRetry').hidden = !pending || state?.visit.status === 'COMPLETED';
        el('finishRetry').disabled = !active || !pending || storageInvalid || busy;
        for (const id of ['finishRefresh','finishRecover','finishConfirm','finishCancel']) el(id).disabled = busy;
    }
    function render(body, focus = false) {
        const status = body.visit.status, selected = body.request?.status;
        el('finishReady').hidden = status !== 'IN_PROGRESS';
        el('finishSuccess').hidden = status !== 'COMPLETED';
        el('finishUnavailable').hidden = ['IN_PROGRESS','COMPLETED'].includes(status);
        el('finishDraftWarning').hidden = selected !== 'DRAFT';
        el('finishConfirmDraft').hidden = selected !== 'DRAFT';
        el('finishRequestText').textContent = selected === 'DRAFT' ? 'درخواست فروش این ویزیت هنوز پیش‌نویس است.' :
            selected === 'SUBMITTED' ? 'درخواست فروش ' + (body.request.number || '') + ' ثبت شده است و بدون تغییر باقی می‌ماند.' :
            'برای این ویزیت درخواست فروشی ثبت نشده است. می‌توانید ویزیت را بدون درخواست فروش پایان دهید.';
        el('finishResultText').textContent = selected === 'DRAFT' ? 'پیش‌نویس درخواست ثبت نشده است و فقط قابل مشاهده باقی می‌ماند.' :
            selected === 'SUBMITTED' ? 'درخواست فروش ثبت‌شده و سابقه تصمیم‌ها بدون تغییر باقی مانده‌اند.' : '';
        const badge = document.querySelector('.sr-context [data-status]');
        if (badge) { badge.dataset.status = status; badge.textContent = statuses[status]; }
        if (status !== 'IN_PROGRESS' && dialog.open) { dialog.close(); plan = null; }
        if (focus && status === 'COMPLETED') el('finishSuccessTitle').focus();
    }
    async function read() {
        if (sending || reading) return;
        reading = true; verified = false; sync(); notice.textContent = 'در حال بررسی وضعیت ویزیت…';
        try {
            const response = await fetch(endpoint() + '?' + new URLSearchParams({customer_code:root.dataset.customerCode}),
                {method:'GET',credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
            const body = await response.json();
            if (!response.ok) throw Error(body.code || 'ACCESS_DENIED');
            state = validState(body); verified = true;
            if (state.visit.status === 'COMPLETED') {
                const recorded = state.recorded_result;
                if (pending && recorded && recorded.command_uuid.toLowerCase() === JSON.parse(pending.wire).command_uuid.toLowerCase()) clearPending();
                notice.textContent = pending ? 'ویزیت تکمیل شده است؛ رسید همین فرمان تأیید نشد. پایان دوباره ارسال نمی‌شود.' : 'وضعیت تکمیل ویزیت از سرور تأیید شد.';
            } else notice.textContent = pending || storageInvalid ? 'نتیجه تلاش قبلی نیاز به بررسی دارد؛ ارسال خودکار انجام نمی‌شود.' :
                state.can_complete ? 'وضعیت ویزیت بررسی شد. برای پایان، تأیید صریح شما لازم است.' : 'پایان این ویزیت از وضعیت فعلی مجاز نیست.';
            render(state);
        } catch (error) {
            verified = false;
            notice.textContent = reason[error.message] || 'وضعیت ویزیت دریافت نشد؛ نشست و اتصال را بررسی و دوباره وضعیت را دریافت کنید.';
        } finally { reading = false; sync(); }
    }
    function open(command) {
        plan = command;
        el('finishDialogNotice').textContent = pending ? 'تلاش دوباره فقط با همان شناسه و اطلاعات قبلی انجام می‌شود.' : '';
        el('finishConfirm').textContent = pending ? 'تلاش دوباره همان فرمان' : 'تأیید پایان ویزیت';
        dialog.showModal(); el('finishCancel').focus();
    }
    el('finishPrepare').addEventListener('click', () => {
        if (el('finishPrepare').disabled) return;
        const wire = JSON.stringify({customer_code:root.dataset.customerCode,command_uuid:window.crypto.randomUUID()});
        open({version:1,actor:root.dataset.actorId,visit:root.dataset.visitId,customer:root.dataset.customerCode,wire});
    });
    el('finishForm').addEventListener('submit', async event => {
        event.preventDefault();
        if (sending || reading || !plan || !verified || !state?.can_complete) return;
        const command = plan, retry = Boolean(pending);
        if (!retry) {
            try {
                window.DemoGeneration?.bind(command);
                const envelope = JSON.stringify(command);
                window.sessionStorage.setItem(key,envelope);
                if (window.sessionStorage.getItem(key) !== envelope) throw Error('Storage failed');
                pending = command;
            } catch (_) {
                storageInvalid = true; dialog.close();
                notice.textContent = 'اطلاعات تلاش قابل نگهداری نیست؛ برای جلوگیری از ارسال نامطمئن هیچ فرمانی ارسال نشد.';
                sync(); return;
            }
        }
        sending = true; sync(); el('finishDialogNotice').textContent = 'در حال پایان ویزیت…';
        try {
            const csrf = el('finishForm').querySelector('[name=csrfmiddlewaretoken]')?.value;
            if (!csrf) throw Error('Missing CSRF');
            const response = await fetch(endpoint(),{method:'POST',credentials:'same-origin',cache:'no-store',
                headers:{Accept:'application/json','Content-Type':'application/json','X-CSRFToken':csrf,...window.DemoGeneration?.headers(command)},body:command.wire});
            const body = await response.json();
            if (response.status === 200) {
                validResult(body);
                if (body.command_uuid.toLowerCase() !== JSON.parse(command.wire).command_uuid.toLowerCase()) throw Error('Wrong receipt');
                state = {version:1,customer:body.customer,visit:body.visit,request:body.request,can_complete:false,recorded_result:body};
                clearPending(); verified = true; render(state,true);
                notice.textContent = 'ویزیت تکمیل شد. می‌توانید به برنامه روزانه بازگردید.';
            } else if ([400,403,404,409].includes(response.status)) {
                if (!retry) clearPending();
                verified = false;
                notice.textContent = reason[body.code] || 'پایان ویزیت تأیید نشد؛ نشست و وضعیت فعلی را بررسی کنید.';
            } else throw Error('Uncertain completion');
        } catch (_) {
            notice.textContent = 'نتیجه پایان ویزیت مشخص نیست؛ ارسال خودکار انجام نمی‌شود. وضعیت را بررسی کنید.';
        } finally {
            sending = false; if (dialog.open) dialog.close(); plan = null; sync();
        }
    });
    el('finishCancel').addEventListener('click', () => {
        if (!sending) { dialog.close(); plan = null; el('finishPrepare').focus(); }
    });
    dialog.addEventListener('cancel', event => {
        if (sending) event.preventDefault();
        else { plan = null; el('finishPrepare').focus(); }
    });
    el('finishRetry').addEventListener('click', () => { if (!el('finishRetry').disabled) open(pending); });
    el('finishRecover').addEventListener('click',read);
    el('finishRefresh').addEventListener('click',read);
    window.addEventListener('pageshow', event => { if (event.persisted) read(); });
    restore();
    try { render(validState(JSON.parse(el('finishInitialState').textContent))); } catch (_) { /* GET remains required. */ }
    sync(); read();
})();
