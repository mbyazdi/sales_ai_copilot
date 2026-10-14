/* Server-owned draft state and quotes. Browser stores only an uncertain command. */
(() => {
    'use strict';
    const root = document.getElementById('guidedCatalog');
    if (!root) return;
    const el = id => document.getElementById(id), field = (mount, name) => mount.querySelector(`[data-basket-${name}]`);
    const dialog = el('basketDialog'), form = el('basketForm'), notice = el('basketNotice');
    const key = `guided-basket:v1:${root.dataset.actorId}:${root.dataset.customerCode}:${root.dataset.visitId}`;
    const base = `/api/sales-requests/v1/visits/${root.dataset.visitId}/`;
    const number = value => new Intl.NumberFormat('fa-IR').format(value);
    const money = value => {
        if (typeof value !== 'string' || !/^(0|[1-9]\d*)$/.test(value)) throw Error('Invalid money');
        return number(BigInt(value));
    };
    const reasons = {INVENTORY_UNKNOWN: 'موجودی نامشخص است.', OUT_OF_STOCK: 'محصول ناموجود است.',
        PRICE_UNAVAILABLE: 'قیمت فعلی در دسترس نیست.', PRICE_CONFIGURATION_ERROR: 'قیمت قابل استفاده نیست.',
        INSUFFICIENT_STOCK: 'موجودی برای این تعداد کافی نیست.', INACTIVE_PRODUCT: 'محصول غیرفعال است.',
        INVALID_QUANTITY: 'تعداد باید عدد صحیح مثبت باشد.',
        REVISION_CONFLICT: 'درخواست تغییر کرده است؛ وضعیت فعلی را دریافت و دوباره تأیید کنید.',
        PRICE_CHANGED: 'قیمت تغییر کرده است؛ قیمت جدید را دریافت و دوباره تأیید کنید.',
        PRODUCT_ALREADY_SELECTED: 'محصول انتخاب شده است؛ تعداد قلم موجود را تغییر دهید.',
        LINE_NOT_SELECTED: 'این قلم دیگر انتخاب نشده است.', COMMAND_CONFLICT: 'شناسه فرمان با فرمان قبلی تداخل دارد.',
        CATALOG_CONTEXT_UNAVAILABLE: 'زمینه فروش معتبر نیست؛ به نمای مشتری بازگردید.',
        VISIT_NOT_ACTIVE: 'تغییر درخواست فقط در ویزیت در حال انجام مجاز است.', REQUEST_NOT_DRAFT: 'درخواست ثبت‌شده قابل تغییر نیست.'};
    let state, data = null, quotes = new Map(), pending = null, plan = null, sending = false, preparing = false, readVersion = 0;
    try {
        const saved = JSON.parse(window.sessionStorage.getItem(key) || 'null');
        if (saved && saved.visitId === root.dataset.visitId && saved.payload.customer_code === root.dataset.customerCode && saved.payload.command_uuid) pending = saved;
    } catch (_) { /* Commands must be durably stored before being sent. */ }
    function endpoint(path) {
        const url = new URL(path, window.location.origin);
        if (url.origin !== window.location.origin || !/^\/api\/sales-requests\/v1\/(visits\/\d+\/(basket\/|basket\/quote\/|lines\/|commands\/[0-9a-f-]+\/)|requests\/\d+\/lines\/\d+\/)$/.test(url.pathname)) throw Error('Invalid endpoint');
        return url.pathname + url.search;
    }
    async function read(path) {
        const response = await fetch(endpoint(path), {method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
        const body = await response.json();
        if (!response.ok) { const error = Error(body.code || 'READ_FAILED'); error.detail = reasons[body.code] || 'دریافت درخواست انجام نشد؛ نشست و دسترسی را بررسی کنید.'; throw error; }
        return body;
    }
    function valid(body) {
        if (body.version !== 1 || body.currency !== 'TOMAN' || body.customer?.code !== root.dataset.customerCode || String(body.visit?.id) !== root.dataset.visitId || !Array.isArray(body.lines) || typeof body.editable !== 'boolean') throw Error('Invalid basket');
        if (body.request && (!Number.isSafeInteger(body.request.id) || !Number.isSafeInteger(body.request.revision) || !['DRAFT','SUBMITTED'].includes(body.request.status))) throw Error('Invalid request');
        if (!Number.isSafeInteger(body.item_count) || !Number.isSafeInteger(body.total_units) || !body.current_quote || !Array.isArray(body.current_quote.items)) throw Error('Invalid state');
        const ids = new Set();
        for (const line of body.lines) {
            if (!Number.isSafeInteger(line.id) || !Number.isSafeInteger(line.product_id) || !Number.isSafeInteger(line.quantity) || line.quantity < 1 || ids.has(line.product_id) || !['ORDINARY','RECOMMENDATION'].includes(line.selection_source)) throw Error('Invalid line');
            ids.add(line.product_id);
        }
        if (body.saved_totals) for (const key of ['base', 'discount', 'final']) money(body.saved_totals[key]);
        return body;
    }
    function blocked() { return !data?.editable || sending || preparing || Boolean(pending) || !state?.ready || window.GuidedFeedback?.hasPending(); }
    function lineQuote(line) { return data.current_quote.items.find(item => item.product_id === line.product_id); }
    function editableLine(line) {
        const item = lineQuote(line);
        return item?.quote && item.inventory?.can_add && item.inventory.catalog_visible;
    }
    function quantityReason(input, stock) {
        let desired;
        try { desired = quantity(input); } catch (_) { return reasons.INVALID_QUANTITY; }
        return stock !== null && stock !== undefined && desired > stock ? reasons.INSUFFICIENT_STOCK : '';
    }
    function actionReason(target, line, quote, input, stock) {
        if (!state.ready) return state.readFailed ? 'دریافت وضعیت درخواست انجام نشد.' : 'در حال بررسی درخواست…';
        if (!data.editable) return data.request?.status === 'SUBMITTED' ? reasons.REQUEST_NOT_DRAFT : reasons.VISIT_NOT_ACTIVE;
        if (sending || preparing) return 'در حال بررسی یا ثبت تغییر…';
        if (pending || window.GuidedFeedback?.hasPending()) return 'ابتدا نتیجه فرمان قبلی را بررسی کنید.';
        if (!line && !quote) return 'قیمت و موجودی هنوز تأیید نشده است.';
        const item = line ? lineQuote(line) : quote;
        const eligible = line ? editableLine(line) : quote.can_add;
        if (!eligible) return reasons[line ? item?.reason_code : quote.non_addable_reason] || 'قیمت یا موجودی قابل استفاده نیست.';
        if (data.current_quote.items.some(item => item.product_id !== target.product_id && item.valid === false)) return 'ابتدا قیمت یا موجودی سایر اقلام درخواست را بررسی کنید.';
        if (input.deniedQuantity === input.value) return input.deniedReason || 'قیمت یا موجودی درخواست برای این تغییر تأیید نشد.';
        return quantityReason(input, stock);
    }
    function sync() {
        el('basketRecovery').hidden = !pending;
        window.GuidedFeedback?.setBasket(data, !state?.ready || sending || preparing || Boolean(pending));
        if (!state) return;
        for (const target of state.targets) {
            const line = data?.lines.find(row => row.product_id === target.product_id), quote = quotes.get(target.product_id);
            const input = field(target.mount, 'quantity'), button = field(target.mount, 'add');
            const eligible = line ? editableLine(line) : quote?.can_add;
            input.disabled = blocked() || !eligible;
            const stock = line ? lineQuote(line)?.inventory.available_quantity : quote?.inventory.sellable_quantity;
            const reason = actionReason(target, line, quote, input, stock);
            button.disabled = input.disabled || Boolean(reason);
            input.max = String(stock ?? 2147483647);
            input.setAttribute('aria-label', `تعداد محصول ${target.name}`);
            button.textContent = line ? 'ثبت تعداد' : 'افزودن';
            button.setAttribute('aria-label', `${line ? 'ثبت تعداد' : 'افزودن'} ${target.name}`);
            const guidance = target.mount.querySelector('[data-quote-availability]');
            if (guidance) {
                guidance.textContent = reason;
                guidance.id = `basket-action-reason-${target.product_id}`;
                button.setAttribute('aria-describedby', guidance.id);
                input.setAttribute('aria-describedby', guidance.id);
            }
            const label = field(target.mount, 'decision');
            label.hidden = !line || line.selection_source !== 'RECOMMENDATION';
            label.textContent = line?.selection_source === 'RECOMMENDATION' ? 'افزوده‌شده به درخواست' : '';
        }
    }
    function quantity(input) {
        if (!/^\d+$/.test(input.value) || !Number.isSafeInteger(Number(input.value)) || Number(input.value) < 1 || Number(input.value) > 2147483647) throw Error('INVALID_QUANTITY');
        return Number(input.value);
    }
    function showSummary() {
        el('basketSummary').textContent = `درخواست فروش · ${number(data.item_count)} محصول · تعداد کل ${number(data.total_units)} · ${data.saved_totals ? money(data.saved_totals.final) + ' تومان' : 'جمع قیمت نامشخص'}`;
        el('basketGuidance').textContent = !data.editable ? 'فقط مشاهده؛ تغییر درخواست در ویزیت در حال انجام امکان‌پذیر است.' : !data.current_quote.valid ? 'قیمت یا موجودی برخی اقلام تغییر کرده است؛ حذف اقلام همچنان امکان‌پذیر است.' : data.quote_changed ? 'قیمت فعلی با قیمت ذخیره‌شده تفاوت دارد؛ تغییر بعدی نیاز به تأیید قیمت جدید دارد.' : 'پیش‌نویس؛ هنوز درخواست فروش ثبت نهایی نشده است.';
        const list = el('basketLines'); list.replaceChildren();
        for (const line of data.lines) {
            const row = document.createElement('li'); row.className = 'gb-line';
            const title = document.createElement('bdi'); title.textContent = line.product_snapshot.name || `محصول ${line.product_id}`;
            const label = document.createElement('label'), input = document.createElement('input');
            input.type = 'number'; input.min = '1'; input.step = '1'; input.inputMode = 'numeric'; input.value = String(line.quantity);
            input.setAttribute('aria-label', `تعداد ${title.textContent}`); input.disabled = blocked() || !editableLine(line); input.max = String(lineQuote(line)?.inventory.available_quantity ?? 2147483647); label.append(input);
            const status = document.createElement('small'); status.textContent = lineQuote(line)?.reason_code ? reasons[lineQuote(line).reason_code] || 'قیمت یا موجودی این قلم نیاز به بررسی دارد.' : line.selection_source === 'RECOMMENDATION' ? 'افزوده‌شده به درخواست' : 'انتخاب عادی';
            const actions = document.createElement('div'); actions.className = 'gb-line-actions';
            const update = document.createElement('button'), remove = document.createElement('button');
            for (const button of [update, remove]) { button.type = 'button'; button.className = 'ds-button ds-button--quiet'; }
            update.textContent = 'ثبت تعداد'; update.disabled = input.disabled || Boolean(quantityReason(input, lineQuote(line)?.inventory.available_quantity));
            remove.textContent = 'حذف از درخواست'; remove.disabled = blocked();
            input.addEventListener('input', () => { delete input.deniedQuantity; delete input.deniedReason; update.disabled = blocked() || !editableLine(line) || Boolean(quantityReason(input, lineQuote(line)?.inventory.available_quantity)); });
            update.addEventListener('click', async () => { await prepare(line.product_id, title.textContent, input, line); update.disabled = blocked() || !editableLine(line) || input.deniedQuantity === input.value; });
            remove.addEventListener('click', () => prepare(line.product_id, title.textContent, null, line));
            actions.append(update, remove); row.append(title, label, status, actions); list.append(row);
        }
        for (const target of state.targets) {
            const line = data.lines.find(row => row.product_id === target.product_id);
            field(target.mount, 'quantity').value = String(line?.quantity ?? 1);
            delete field(target.mount, 'quantity').deniedQuantity;
            delete field(target.mount, 'quantity').deniedReason;
        }
        sync();
    }
    async function refresh() {
        const version = ++readVersion, current = state;
        if (!current) return;
        current.ready = false; current.readFailed = false; el('basketPanel').setAttribute('aria-busy', 'true');
        el('basketSummary').textContent = 'درخواست فروش · در حال دریافت…'; sync();
        try {
            const body = valid(await read(`${base}basket/?${new URLSearchParams({customer_code: root.dataset.customerCode})}`));
            if (version !== readVersion || state !== current || !current.isCurrent()) return;
            data = body; current.ready = true; showSummary(); el('basketRefresh').hidden = true;
            el('basketPanel').setAttribute('aria-busy', 'false');
        } catch (error) {
            if (version !== readVersion || state !== current || !current.isCurrent()) return;
            notice.textContent = error.detail || 'دریافت درخواست انجام نشد؛ دوباره وضعیت را بررسی کنید.';
            el('basketSummary').textContent = 'درخواست فروش · وضعیت فعلی در دسترس نیست';
            el('basketPanel').setAttribute('aria-busy', 'false');
            current.readFailed = true; el('basketRefresh').hidden = false; sync();
        }
    }
    async function prepare(productId, name, input, line = null) {
        if (blocked()) { notice.textContent = 'ابتدا نتیجه فرمان قبلی یا وضعیت درخواست را بررسی کنید.'; return; }
        let desired;
        try { desired = input ? quantity(input) : null; } catch (_) { notice.textContent = 'تعداد باید عدد صحیح مثبت باشد.'; input?.focus(); return; }
        preparing = true; sync(); plan = null; notice.textContent = 'در حال بررسی قیمت و موجودی…';
        const current = state;
        try {
            let quote = null;
            if (input) {
                quote = await read(`${base}basket/quote/?${new URLSearchParams({customer_code: root.dataset.customerCode, product_id: String(productId), quantity: String(desired)})}`);
                if (state !== current || !current.isCurrent()) return;
                if (quote.version !== 1 || quote.customer_code !== root.dataset.customerCode || String(quote.visit_id) !== root.dataset.visitId || !Array.isArray(quote.items)) throw Error('Invalid quote');
                if (!quote.items.some(item => item.product_id === productId && item.quantity === desired)) throw Error('Wrong product quote');
                if (!quote.editable || !quote.valid) { input.deniedQuantity = input.value; input.deniedReason = reasons[quote.items.find(item => !item.valid)?.reason_code] || 'قیمت یا موجودی درخواست برای این تغییر در دسترس نیست.'; notice.textContent = input.deniedReason; return; }
                if (quote.expected_request_revision !== (data.request?.revision ?? null)) { notice.textContent = reasons.REVISION_CONFLICT; await refresh(); return; }
                if (!/^[0-9a-f]{64}$/.test(quote.quote_fingerprint) || !quote.totals) throw Error('Invalid fingerprint');
                money(quote.totals.final);
            }
            const payload = {customer_code: root.dataset.customerCode, command_uuid: window.crypto.randomUUID(),
                expected_request_revision: data.request?.revision ?? null, catalog_context: current.context.catalogContext};
            if (input) { payload.quantity = desired; payload.accepted_quote_fingerprint = quote.quote_fingerprint; }
            if (!line) payload.product_id = productId;
            plan = {visitId: root.dataset.visitId, name, productId, lineId: line?.id ?? null,
                recommended: line ? line.selection_source === 'RECOMMENDATION' : Boolean(current.targets.find(t => t.product_id === productId)?.recommendation),
                method: line ? input ? 'PATCH' : 'DELETE' : 'POST',
                url: line ? `/api/sales-requests/v1/requests/${data.request.id}/lines/${line.id}/` : `${base}lines/`,
                payload, total: quote?.totals.final ?? null};
            open(plan); notice.textContent = '';
        } catch (error) { notice.textContent = error.detail || 'بررسی قیمت انجام نشد؛ اتصال و دسترسی را بررسی کنید.'; }
        finally { preparing = false; sync(); }
    }
    function open(command) {
        el('basketTitle').textContent = command.method === 'DELETE' ? 'حذف از درخواست فروش' : command.method === 'PATCH' ? 'ثبت تعداد محصول' : 'افزودن به درخواست فروش';
        el('basketDescription').textContent = `${command.name}${command.payload.quantity ? ' · تعداد ' + number(command.payload.quantity) : ''}`;
        el('basketQuoteTotal').textContent = command.total !== null ? `جمع درخواست پس از تغییر: ${money(command.total)} تومان` : 'حذف این قلم نیاز به تأیید شما دارد.';
        el('basketMessage').textContent = pending ? 'نتیجه قبلی نامشخص است؛ تلاش دوباره از همان شناسه و محتوای فرمان استفاده می‌کند.' : '';
        el('basketConfirm').textContent = pending ? 'تلاش دوباره همین فرمان' : 'تأیید تغییر';
        if (!dialog.open) dialog.showModal(); el('basketConfirm').focus();
    }
    function confirmed(command, body) {
        valid(body);
        if (body.request?.revision !== (command.payload.expected_request_revision ?? 0) + 1) throw Error('Invalid applied revision');
        const line = body.lines.find(row => row.product_id === command.productId);
        if (command.method === 'DELETE' ? Boolean(line) : !line || line.quantity !== command.payload.quantity) throw Error('Unconfirmed selection');
    }
    async function apply() {
        if (sending || (!pending && !plan)) return;
        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
        if (!csrf) { el('basketMessage').textContent = 'نشست صفحه معتبر نیست؛ صفحه را تازه کنید.'; return; }
        const command = pending || plan, uncertain = Boolean(command.sent);
        try { window.sessionStorage.setItem(key, JSON.stringify(command)); pending = command; }
        catch (_) { el('basketMessage').textContent = 'ذخیره امن فرمان انجام نشد؛ هیچ تغییری ارسال نشد.'; return; }
        sending = true; el('basketConfirm').disabled = true; el('basketCancel').disabled = true; sync(); if (data) showSummary();
        el('basketMessage').textContent = 'در حال ثبت تغییر…';
        try {
            command.sent = true; window.sessionStorage.setItem(key, JSON.stringify(command));
            const response = await fetch(endpoint(command.url), {method: command.method, credentials: 'same-origin', cache: 'no-store',
                headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: JSON.stringify(command.payload)});
            const body = await response.json();
            if (response.status === (command.method === 'POST' ? 201 : 200)) {
                confirmed(command, body);
                window.sessionStorage.removeItem(key); pending = null; plan = null; dialog.close();
                notice.textContent = command.method === 'DELETE' ? command.recommended ? 'محصول پیشنهادی از درخواست حذف شد؛ سابقه افزودن محفوظ است.' : 'محصول از درخواست حذف شد.' : command.method === 'POST' ? 'محصول به درخواست افزوده شد.' : 'تعداد محصول در درخواست ثبت شد.';
                await refresh(); state?.refreshQuotes();
            } else if ([400, 403, 404, 409].includes(response.status) && !uncertain) {
                window.sessionStorage.removeItem(key); pending = null; plan = null;
                notice.textContent = reasons[body.code] || 'تغییر تأیید نشد؛ نشست، دسترسی و زمینه ویزیت را بررسی کنید.';
                dialog.close(); await refresh(); state?.refreshQuotes();
            } else throw Error('Uncertain result');
        } catch (_) {
            notice.textContent = el('basketMessage').textContent = 'نتیجه تغییر مشخص نیست؛ ارسال خودکار انجام نمی‌شود. نتیجه فرمان را بررسی کنید یا همان فرمان را صریحاً دوباره ارسال کنید.';
        } finally { sending = false; el('basketConfirm').disabled = false; el('basketCancel').disabled = false; sync(); if (data && state?.ready) showSummary(); }
    }
    async function status() {
        if (!pending || sending) return;
        const command = pending;
        try {
            const body = await read(`${base}commands/${command.payload.command_uuid}/?${new URLSearchParams({customer_code: root.dataset.customerCode})}`);
            if (body.command_uuid !== command.payload.command_uuid || body.result?.http_status !== (command.method === 'POST' ? 201 : 200)) throw Error('Invalid receipt');
            confirmed(command, body.result.body);
            window.sessionStorage.removeItem(key); pending = null; plan = null;
            notice.textContent = 'نتیجه قبلی فرمان تأیید شد؛ وضعیت فعلی درخواست دریافت می‌شود.';
            dialog.close(); await refresh(); state?.refreshQuotes();
        } catch (_) { notice.textContent = 'نتیجه موفقی برای این فرمان تأیید نشد؛ این به معنی شکست قطعی نیست. ارسال خودکار انجام نمی‌شود.'; }
        sync();
    }
    function load(context, targets, {isCurrent = () => true, refreshQuotes = () => {}} = {}) {
        state = {context, targets, isCurrent, refreshQuotes, ready: false}; quotes = new Map();
        if (!pending && !sending) { plan = null; dialog.close(); }
        for (const target of targets) {
            const input = field(target.mount, 'quantity');
            input.addEventListener('input', () => { delete input.deniedQuantity; delete input.deniedReason; sync(); });
            field(target.mount, 'add').addEventListener('click', () => prepare(target.product_id, target.name,
                input, data?.lines.find(line => line.product_id === target.product_id)));
        }
        return refresh();
    }
    form.addEventListener('submit', event => { event.preventDefault(); apply(); });
    el('basketCancel').addEventListener('click', () => { if (!sending) { dialog.close(); plan = null; } });
    dialog.addEventListener('cancel', event => { if (sending) event.preventDefault(); else plan = null; });
    el('basketRefresh').addEventListener('click', async () => { await refresh(); state?.refreshQuotes(); });
    el('basketStatus').addEventListener('click', status);
    el('basketRetryCommand').addEventListener('click', () => { if (pending && !sending) open(pending); });
    window.GuidedBasket = {load, refresh, quotes: items => { quotes = new Map(items.map(item => [item.product_id, item])); sync(); },
        feedbackChanged: () => { sync(); if (data && state?.ready) showSummary(); }};
})();
