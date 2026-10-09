/* Explicit feedback only. D1 owns authorization, selection, history and replay. */
(() => {
    'use strict';
    const root = document.getElementById('guidedCatalog');
    if (!root) return;
    const el = id => document.getElementById(id);
    const dialog = el('feedbackDialog'), form = el('feedbackForm'), reason = el('feedbackReason');
    const confirm = el('feedbackConfirm'), cancel = el('feedbackCancel'), message = el('feedbackMessage');
    const labels = Object.assign(Object.create(null), {NOT_INTERESTED: 'مشتری علاقه‌مند نبود', PRICE: 'قیمت مناسب نبود', STOCK: 'موجودی کافی نبود', NO_CURRENT_NEED: 'فعلاً نیاز ندارد', OTHER_BRAND: 'از برند یا مدل دیگری استفاده می‌کند', LATER: 'بعداً بررسی می‌کنم', OTHER: 'دلیل دیگر'});
    const key = `guided-feedback:v1:${root.dataset.actorId}:${root.dataset.customerCode}:${root.dataset.visitId}`;
    let state, choice, pending = null, sending = false;
    const field = (mount, name) => mount.querySelector(`[data-feedback-${name}]`);
    const compactReasons = {NOT_INTERESTED: 'عدم تمایل', PRICE: 'قیمت نامناسب', STOCK: 'موجودی ناکافی', NO_CURRENT_NEED: 'عدم نیاز فعلی', OTHER_BRAND: 'برند یا مدل دیگر', OTHER: 'دلیل دیگر'};
    const savedLabel = event => event.reason_code === 'LATER' ? 'بعداً بررسی می‌کنم' : `رد پیشنهاد · ${compactReasons[event.reason_code]}`;
    function decision(target, events) {
        target.events = events;
        target.hasDecision = events.length > 0;
        if (!target.hasDecision) return;
        const latest = events[events.length - 1];
        field(target.mount, 'summary').textContent = savedLabel(latest);
        field(target.mount, 'summary').setAttribute('aria-label', `${savedLabel(latest)} · مشاهده سوابق و جزئیات`);
        field(target.mount, 'history').textContent = 'سوابق ثبت‌شده';
        field(target.mount, 'history').hidden = false;
        const list = field(target.mount, 'history-list');
        list.replaceChildren();
        for (const event of events) {
            const row = document.createElement('li');
            row.textContent = event.reason_code === 'LATER' ? 'بعداً بررسی می‌کنم' : `رد پیشنهاد · ${labels[event.reason_code]}`;
            list.append(row);
        }
        list.hidden = false;
        target.changing = false;
    }
    try {
        const stored = window.sessionStorage.getItem(key);
        if (stored) {
            const value = JSON.parse(stored);
            if (value.payload.customer_code === root.dataset.customerCode && value.visitId === root.dataset.visitId && value.payload.command_uuid) pending = value;
        }
    } catch (_) { /* New commands must still be stored before any POST. */ }
    function controls() {
        el('feedbackRecovery').hidden = !pending;
        if (!state) return;
        for (const target of state.targets) {
            const active = state.ready && state.visitStatus === 'IN_PROGRESS' && (!state.request || state.request.status === 'DRAFT');
            field(target.mount, 'reject').disabled = !active || Boolean(pending) || target.selected;
            field(target.mount, 'later').disabled = !active || Boolean(pending) || target.selected;
            field(target.mount, 'options').hidden = Boolean(target.hasDecision) && !target.changing;
            field(target.mount, 'change').hidden = !target.hasDecision || target.changing || !active || target.selected;
            field(target.mount, 'change').disabled = !active || Boolean(pending) || target.selected;
            field(target.mount, 'guidance').textContent = target.selected ? 'محصول در درخواست انتخاب شده است؛ ابتدا آن را صریحاً حذف کنید.' : pending ? 'ابتدا نتیجه تصمیم قبلی را بررسی کنید.' : !state.ready ? state.readError || 'در حال بررسی امکان ثبت بازخورد…' : state.visitStatus !== 'IN_PROGRESS' ? 'ثبت بازخورد فقط در ویزیت در حال انجام امکان‌پذیر است.' : state.request?.status === 'SUBMITTED' ? 'درخواست ثبت‌شده قابل تغییر نیست.' : '';
            if (target.changing && active && !pending && !target.selected) field(target.mount, 'guidance').textContent = 'تصمیم تازه ثبت می‌شود؛ سوابق قبلی محفوظ می‌مانند.';
        }
    }
    function show(target, action) {
        if (sending) return;
        if (pending) {
            choice = {target, action: pending.payload.action};
            el('feedbackProduct').textContent = pending.name;
            reason.value = pending.payload.reason_code;
        } else {
            if (!state?.ready || state.visitStatus !== 'IN_PROGRESS' || target.selected || state.request?.status === 'SUBMITTED') return;
            choice = {target, action};
            el('feedbackProduct').textContent = target.name;
            reason.value = action === 'LATER' ? 'LATER' : '';
        }
        reason.disabled = Boolean(pending);
        el('feedbackReasonRow').hidden = choice.action === 'LATER';
        reason.required = choice.action === 'REJECTED';
        const later = choice.action === 'LATER' || reason.value === 'LATER';
        el('feedbackTitle').textContent = later ? 'بعداً بررسی می‌کنم' : 'رد پیشنهاد';
        el('feedbackDescription').textContent = later ? 'این تصمیم فقط ثبت می‌شود؛ پیگیری خودکار یا پایان ویزیت ایجاد نمی‌کند.' : 'دلیل را انتخاب کنید و سپس ثبت تصمیم را تأیید کنید.';
        confirm.textContent = pending ? 'بررسی دوباره نتیجه همین فرمان' : 'تأیید و ثبت تصمیم';
        cancel.textContent = 'انصراف';
        message.textContent = pending ? 'نتیجه فرمان قبلی مشخص نیست. بررسی دوباره از همان شناسه و تصمیم استفاده می‌کند.' : '';
        confirm.disabled = false; cancel.disabled = false;
        if (!dialog.open) dialog.showModal();
        (later || pending ? confirm : reason).focus();
    }
    cancel.addEventListener('click', () => { if (!sending) { dialog.close(); choice = null; } });
    dialog.addEventListener('cancel', event => { if (sending) event.preventDefault(); else choice = null; });
    reason.addEventListener('change', () => {
        if (choice && !pending) {
            el('feedbackTitle').textContent = reason.value === 'LATER' ? 'بعداً بررسی می‌کنم' : 'رد پیشنهاد';
            el('feedbackDescription').textContent = reason.value === 'LATER' ? 'این تصمیم فقط ثبت می‌شود؛ پیگیری خودکار ایجاد نمی‌کند.' : 'ثبت تصمیم نیاز به تأیید شما دارد.';
        }
    });
    el('feedbackResume').addEventListener('click', () => { if (pending) show(null, pending.payload.action); });
    function endpoint(context) {
        const url = new URL(context.apiUrl, window.location.origin);
        if (url.origin !== window.location.origin || url.pathname !== `/api/recommendations/v1/visits/${root.dataset.visitId}/feedback/`) throw new Error('Invalid endpoint');
        return url;
    }
    async function load(context, targets, {signal, isCurrent = () => true} = {}) {
        state = {context, targets: [], ready: false, visitStatus: '', request: null};
        for (const target of targets) {
            const actions = field(target.mount, 'actions');
            if (!target.recommendationId) { actions.remove(); continue; }
            actions.hidden = false;
            target.mount.querySelector('.gc-secondary-actions').prepend(actions);
            field(target.mount, 'reject').addEventListener('click', () => show(target, 'REJECTED'));
            field(target.mount, 'later').addEventListener('click', () => show(target, 'LATER'));
            field(target.mount, 'change').addEventListener('click', () => { target.changing = true; controls(); field(target.mount, 'reject').focus(); });
            state.targets.push(target);
        }
        const current = state;
        controls();
        if (!current.targets.length) return;
        try {
            const url = endpoint(context); let page = 1, pages = 1;
            const latest = new Map();
            do {
                url.search = new URLSearchParams({customer_code: root.dataset.customerCode, page: String(page)}).toString();
                const response = await fetch(url.pathname + url.search, {method: 'GET', credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store', signal});
                if (!isCurrent() || state !== current) return;
                if (!response.ok) throw new Error('History unavailable');
                const data = await response.json();
                if (!isCurrent() || state !== current) return;
                if (data.version !== 1 || data.customer?.code !== root.dataset.customerCode || String(data.visit?.id) !== root.dataset.visitId || !Array.isArray(data.events) || !Number.isSafeInteger(data.pages) || data.pages < page || data.page !== page) throw new Error('Invalid history');
                current.visitStatus = data.visit.status; current.request = data.request;
                for (const event of data.events) {
                    if (event.event_type !== 'REJECTED' || !labels[event.reason_code]) throw new Error('Invalid event');
                    if (!latest.has(event.recommendation_id)) latest.set(event.recommendation_id, []);
                    latest.get(event.recommendation_id).push(event);
                }
                pages = data.pages; page += 1;
            } while (page <= pages);
            if (!isCurrent() || state !== current) return;
            for (const target of current.targets) {
                decision(target, latest.get(target.recommendationId) || []);
            }
            current.ready = true; controls();
        } catch (error) {
            if (signal?.aborted || !isCurrent() || state !== current) return;
            current.readError = 'اطلاعات بازخورد در دسترس نیست؛ صفحه را تازه کنید و زمینه ویزیت را بررسی کنید.';
            controls();
        }
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (sending || !choice) return;
        if (!pending) {
            const code = choice.action === 'LATER' ? 'LATER' : reason.value;
            if (!labels[code]) { message.textContent = 'یک دلیل معتبر را انتخاب کنید.'; reason.focus(); return; }
            try {
                pending = {visitId: root.dataset.visitId, name: choice.target.name, productId: choice.target.productId,
                    payload: {customer_code: root.dataset.customerCode, recommendation_id: choice.target.recommendationId,
                        action: code === 'LATER' ? 'LATER' : 'REJECTED', reason_code: code, note: '', command_uuid: window.crypto.randomUUID(),
                        catalog_context: state.context.catalogContext, expected_request_revision: state.request?.revision ?? null}};
                window.sessionStorage.setItem(key, JSON.stringify(pending));
            } catch (_) { pending = null; message.textContent = 'آماده‌سازی فرمان انجام نشد؛ تنظیمات مرورگر را بررسی کنید.'; return; }
        }
        const command = pending, wasUncertain = command.sent === true;
        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
        if (!csrf) { message.textContent = 'نشست صفحه معتبر نیست؛ صفحه را تازه کنید.'; controls(); return; }
        sending = true; confirm.disabled = true; cancel.disabled = true; reason.disabled = true;
        form.setAttribute('aria-busy', 'true'); message.textContent = 'در حال ثبت تصمیم…'; controls();
        try {
            command.sent = true;
            window.sessionStorage.setItem(key, JSON.stringify(command));
            const url = endpoint(state.context);
            const response = await fetch(url.pathname, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': csrf}, cache: 'no-store', body: JSON.stringify(command.payload)});
            const data = await response.json();
            if (response.status === 201) {
                const feedback = data.feedback;
                if (data.version !== 1 || data.customer?.code !== command.payload.customer_code || String(data.visit?.id) !== command.visitId || feedback?.recommendation_id !== command.payload.recommendation_id || feedback.product_id !== command.productId || feedback.event_type !== 'REJECTED' || feedback.reason_code !== command.payload.reason_code || !Number.isSafeInteger(feedback.id) || feedback.id < 1) throw new Error('Unconfirmed result');
                const target = state.targets.find(target => target.recommendationId === feedback.recommendation_id);
                if (target) {
                    const events = [...(target.events || [])];
                    if (!events.some(event => event.id === feedback.id)) events.push(feedback);
                    decision(target, events);
                    field(target.mount, 'actions').open = false;
                }
                window.sessionStorage.removeItem(key); pending = null; choice = null;
                message.textContent = `${response.headers.get('Idempotent-Replayed') === 'true' ? 'نتیجه قبلی تأیید شد' : 'ثبت شد'}: ${savedLabel(feedback)}`;
                el('feedbackNotice').textContent = message.textContent;
                confirm.disabled = true; cancel.textContent = 'بستن';
                dialog.close();
                if (target) field(target.mount, 'summary').focus();
            } else if ([400, 403, 404, 409].includes(response.status)) {
                const messages = {PRODUCT_ALREADY_SELECTED: 'محصول در درخواست انتخاب شده است؛ ابتدا آن را صریحاً حذف کنید.', REVISION_CONFLICT: 'وضعیت درخواست تغییر کرده است؛ صفحه را تازه کنید.', CATALOG_CONTEXT_UNAVAILABLE: 'زمینه پیشنهادها منقضی یا تغییر کرده است؛ به نمای مشتری بازگردید.', VISIT_NOT_ACTIVE: 'این ویزیت برای ثبت تصمیم تازه فعال نیست.', REQUEST_NOT_DRAFT: 'درخواست ثبت‌شده قابل تغییر نیست.', COMMAND_CONFLICT: 'شناسه فرمان با تصمیم قبلی تداخل دارد؛ فرمان تازه‌ای ارسال نکنید.'};
                message.textContent = messages[data.code] || 'ثبت تصمیم تأیید نشد؛ دسترسی، نشست و زمینه ویزیت را بررسی کنید.';
                if (response.status === 409 && data.code !== 'PRODUCT_ALREADY_SELECTED') { state.ready = false; state.readError = message.textContent; }
                if (data.code === 'PRODUCT_ALREADY_SELECTED') { const target = state.targets.find(t => t.productId === command.productId); if (target) target.selected = true; }
                if ([403, 404].includes(response.status)) { state.ready = false; state.readError = 'دسترسی یا نشست بازخورد تأیید نشد؛ زمینه ویزیت را بررسی کنید.'; }
                if (wasUncertain && [403, 404].includes(response.status)) throw new Error('Prior result still unknown');
                window.sessionStorage.removeItem(key); pending = null; choice = null; confirm.disabled = true;
            } else throw new Error('Unknown application result');
        } catch (_) {
            message.textContent = 'نتیجه ثبت مشخص نیست؛ ارسال خودکار انجام نمی‌شود. فقط همین فرمان را برای بررسی دوباره ارسال کنید.';
            confirm.textContent = 'بررسی دوباره نتیجه همین فرمان'; confirm.disabled = false;
        } finally {
            sending = false; cancel.disabled = false; form.setAttribute('aria-busy', 'false'); controls();
        }
    });
    controls();
    window.GuidedFeedback = {load};
})();
