/* Frozen evidence presentation only. Never rank, quote, publish or POST. */
(function (scope) {
    'use strict';
    const ERRORS = {
        401: 'نشست شما معتبر نیست؛ برای مشاهدهٔ مقایسه دوباره وارد شوید.',
        403: 'دسترسی مشاهدهٔ این مقایسه برای حساب شما مجاز نیست.',
        404: 'مقایسهٔ درخواستی پیدا نشد یا در دسترس نیست.',
        409: 'شواهد ذخیره‌شدهٔ مقایسه معتبر نیست؛ نمایش نتیجه متوقف شد.',
        503: 'زیرساخت راهبرد آماده نیست؛ کمی بعد دریافت دوباره را انتخاب کنید.'
    };
    const decimal = value => typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value);
    const id = value => Number.isSafeInteger(value) && value > 0;
    const present = value => value !== null && value !== undefined && value !== '';
    const format = value => present(value) ? String(value).replace(/[0-9.]/g, character =>
        character === '.' ? '٫' : '۰۱۲۳۴۵۶۷۸۹'[Number(character)]) : 'ثبت نشده';
    const text = value => typeof value === 'string' && value.trim() ? value : null;
    function requireValue(condition) { if (!condition) throw new Error('INVALID_FROZEN_COMPARISON'); }
    function validate(data, expectedId) {
        requireValue(data && data.comparison_id === expectedId && id(expectedId) && id(data.customer_id) && id(data.salesperson_id));
        requireValue(Number.isSafeInteger(data.policy_revision) && data.policy_revision >= 0 &&
            (data.before_version_id === null || id(data.before_version_id)) && id(data.after_version_id));
        requireValue(typeof data.evaluation_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(data.evaluation_date));
        requireValue(data.outputs && data.outputs.schema_version === 1 && data.outputs.simulation_only === true);
        const maps = {};
        for (const side of ['before', 'after']) {
            const result = data.outputs[side];
            requireValue(result && Array.isArray(result.rows) && Array.isArray(result.after_ids) && result.rows.length === result.after_ids.length);
            const rows = new Map();
            result.rows.forEach((row, index) => {
                requireValue(row && row.source && id(row.source.recommendation_id) && id(row.source.product_id) &&
                    id(row.source.saved_rank) && decimal(row.source.base_score) && row.product &&
                    row.product.product_id === row.source.product_id && text(row.product.product_code));
                requireValue(!rows.has(row.source.recommendation_id) && result.after_ids[index] === row.source.recommendation_id &&
                    row.after_rank === index + 1 && id(row.original_position));
                for (const field of ['base_priority', 'overlay_adjustment', 'effective_priority']) requireValue(decimal(row[field]));
                for (const field of ['priority', 'target', 'promotion']) requireValue(row[field] && decimal(row[field].points) && Array.isArray(row[field].reasons));
                rows.set(row.source.recommendation_id, row);
            });
            maps[side] = rows;
        }
        requireValue(maps.before.size === maps.after.size && Array.isArray(data.outputs.movements));
        maps.after.forEach((row, key) => {
            const before = maps.before.get(key);
            requireValue(before && before.source.product_id === row.source.product_id && before.product.product_code === row.product.product_code &&
                before.source.saved_rank === row.source.saved_rank && before.source.base_score === row.source.base_score);
        });
        const movements = new Map();
        data.outputs.movements.forEach(move => {
            requireValue(move && !movements.has(move.recommendation_id) && maps.before.has(move.recommendation_id) &&
                move.before_rank === maps.before.get(move.recommendation_id).after_rank &&
                move.after_rank === maps.after.get(move.recommendation_id).after_rank && Number.isSafeInteger(move.positions_gained));
            movements.set(move.recommendation_id, move);
        });
        requireValue(movements.size === maps.after.size);
        return {data, maps, movements};
    }
    function movement(move) {
        if (move.positions_gained > 0) return {className: 'up', label: '↑ ' + format(move.positions_gained) + ' رتبه صعود'};
        if (move.positions_gained < 0) return {className: 'down', label: '↓ ' + format(String(move.positions_gained).slice(1)) + ' رتبه نزول'};
        return {className: 'same', label: 'بدون تغییر رتبه'};
    }
    function availability(row) {
        const facts = row.source.commercial || {};
        if (row.product.is_active === false) return 'محصول در زمان ثبت غیرفعال بود';
        if (facts.stock_state === 'UNKNOWN') return 'موجودی نامشخص';
        if (facts.stock_state === 'UNAVAILABLE') return 'موجودی قابل فروش نداشت';
        if (facts.pricing_state === 'UNAVAILABLE') return 'قیمت در دسترس نبود';
        if (facts.pricing_state === 'CONFIGURATION_ERROR') return 'قیمت قابل استفاده نبود';
        if (facts.stock_state === 'AVAILABLE' && facts.pricing_state === 'AVAILABLE') return 'قیمت و موجودی در زمان ثبت موجود بود';
        return 'وضعیت تجاری کامل ثبت نشده است';
    }
    function label(model, row) {
        const labels = model.data.labels || {};
        const product = Array.isArray(labels.products) ? labels.products.find(item => item.id === row.source.product_id) : null;
        return {name: product && text(product.name) || row.product.product_code, code: row.product.product_code};
    }
    function version(value) { return value === null ? 'سیاست خنثی' : 'نسخهٔ ' + format(value); }
    function setupResponsiveComparison(document, root, media) {
        const tabs = root.querySelector('#comparisonTabs');
        const sides = ['before', 'after'];
        const buttons = sides.map(side => root.querySelector('#' + side + 'Tab'));
        const panels = sides.map(side => root.querySelector('#' + side + 'Panel'));
        const details = root.querySelector('#focusDetails');
        let selected = 1; // Mobile starts with the proposed-policy result.
        function update() {
            const active = document.activeElement;
            tabs.hidden = !media.matches;
            buttons.forEach((button, index) => {
                button.setAttribute('aria-selected', String(index === selected));
                button.tabIndex = index === selected ? 0 : -1;
                const panel = panels[index];
                panel.hidden = media.matches && index !== selected;
                if (media.matches) panel.setAttribute('role', 'tabpanel');
                else panel.removeAttribute('role');
                panel.setAttribute('aria-labelledby', sides[index] + (media.matches ? 'Tab' : 'Title'));
                if (panel.hidden && panel.contains(active)) buttons[selected].focus();
            });
            if (!media.matches && buttons.includes(active)) {
                const panel = panels[selected];
                panel.tabIndex = -1;
                panel.focus();
            }
        }
        buttons.forEach((button, index) => {
            button.addEventListener('click', () => { selected = index; update(); });
            button.addEventListener('keydown', event => {
                // In RTL the next tab is to the left. Automatic activation only
                // switches already-rendered evidence; it never fetches or ranks.
                const next = {ArrowLeft: (index + 1) % 2, ArrowRight: (index + 1) % 2, Home: 0, End: 1}[event.key];
                if (!media.matches || next === undefined) return;
                event.preventDefault(); selected = next; update(); buttons[next].focus();
            });
        });
        function resize() { details.open = !media.matches; update(); }
        media.addEventListener('change', resize);
        resize();
    }
    function render(document, root, model) {
        const {data} = model;
        const find = name => root.querySelector('[data-field="' + name + '"]');
        const put = (name, value) => { find(name).textContent = value; };
        const node = (tag, content, className) => {
            const result = document.createElement(tag);
            if (present(content)) result.textContent = String(content);
            if (className) result.className = className;
            return result;
        };
        const fact = (title, value) => {
            const cell = node('div'); cell.append(node('dt', title), node('dd', format(value))); return cell;
        };
        const labels = data.labels || {};
        const customer = labels.customer && labels.customer.id === data.customer_id ? labels.customer : {};
        const rep = labels.salesperson && labels.salesperson.id === data.salesperson_id ? labels.salesperson : {};
        put('customer-name', text(customer.name) || 'مشتری ' + format(data.customer_id));
        put('customer-code', text(customer.code) || 'شناسهٔ ' + format(data.customer_id));
        put('salesperson-name', text(rep.name) || 'فروشنده ' + format(data.salesperson_id));
        put('salesperson-code', text(rep.code) || 'شناسهٔ ' + format(data.salesperson_id));
        put('evaluation-date', format(data.evaluation_date.replaceAll('-', '/')));
        put('versions', version(data.before_version_id) + ' ← ' + version(data.after_version_id));
        put('revision', format(data.policy_revision));
        put('before-version', version(data.before_version_id)); put('after-version', version(data.after_version_id));
        const after = data.outputs.after.rows;
        // Highlight the largest movement reported by the server, without
        // recomputing any ranks. Ties retain the frozen After list's order.
        const focus = after.reduce((best, row) => !best || model.movements.get(row.source.recommendation_id).positions_gained >
            model.movements.get(best.source.recommendation_id).positions_gained ? row : best, null);
        const buttons = [];
        function select(key) {
            buttons.forEach(item => item.button.setAttribute('aria-pressed', String(item.id === key)));
            const row = model.maps.after.get(key);
            const move = model.movements.get(key);
            root.querySelector('#explanation').hidden = false;
            root.querySelector('#explanationTitle').textContent = label(model, row).name + ' · ' + row.product.product_code;
            put('focus-movement', 'رتبهٔ ' + format(move.before_rank) + ' به ' + format(move.after_rank) + ' · ' + movement(move).label);
            root.querySelector('#focusSummary').replaceChildren(
                fact('امتیاز ذخیره‌شدهٔ موتور', row.source.base_score), fact('اولویت مؤثر', row.effective_priority));
            root.querySelector('#focusRanks').replaceChildren(
                fact('رتبهٔ ذخیره‌شده', row.source.saved_rank), fact('رتبهٔ سیاست پیشین', move.before_rank), fact('رتبهٔ سیاست پیشنهادی', move.after_rank));
            root.querySelector('#focusFactors').replaceChildren(
                fact('امتیاز ذخیره‌شدهٔ موتور', row.source.base_score), fact('اولویت پایهٔ بازچینی', row.base_priority),
                fact('اولویت مدیریتی', row.priority.points), fact('سهم هدف فروش', row.target.points),
                fact('تأکید ترویجی', row.promotion.points), fact('تعدیل سیاست', row.overlay_adjustment), fact('اولویت مؤثر', row.effective_priority));
            const reasons = root.querySelector('#focusReasons'); reasons.replaceChildren();
            for (const [field, title] of [['priority', 'اولویت مدیریتی'], ['target', 'هدف فروش'], ['promotion', 'تأکید ترویجی']]) {
                const box = node('article', null, 'strategy-reason'); box.append(node('h3', title));
                const valid = row[field].reasons.filter(item => item && text(item.text_fa));
                valid.forEach(item => { const p = node('p', item.text_fa); if (text(item.code)) p.dataset.reasonCode = item.code; box.append(p); });
                if (!valid.length) box.append(node('p', 'توضیحی در شواهد ثبت نشده است.'));
                reasons.append(box);
            }
            const frozen = (data.quotes || {})[String(row.source.product_id)];
            const quote = frozen && frozen.state === 'AVAILABLE' && frozen.quote ? frozen.quote : {};
            const facts = row.source.commercial || {};
            const price = present(quote.final_unit_price) && quote.currency === 'TOMAN' ? format(quote.final_unit_price) + ' تومان' : 'ثبت نشده';
            const stock = facts.stock_state === 'UNKNOWN' ? 'نامشخص' : format(facts.sellable_quantity);
            const commercial = root.querySelector('#focusCommercial');
            const cell = (title, content) => { const item = node('div'); item.append(node('dt', title), node('dd', content)); return item; };
            commercial.replaceChildren(cell('قیمت نهایی یک واحد', price), cell('موجودی قابل فروش', stock),
                cell('وضعیت ثبت‌شده', availability(row)), cell('ماهیت شواهد', /DEMO|SYNTHETIC|ISOLATED/.test(quote.price_source || '') ? 'قیمت نمونهٔ آزمایشی' : 'قیمت زمان ثبت'));
        }
        for (const side of ['before', 'after']) {
            const list = root.querySelector(side === 'before' ? '#beforeRanking' : '#afterRanking'); list.replaceChildren();
            data.outputs[side].rows.forEach(row => {
                const li = node('li'); const button = node('button', null, 'strategy-rank-button'); button.type = 'button';
                button.dataset.recommendationId = String(row.source.recommendation_id); button.setAttribute('aria-pressed', 'false');
                button.setAttribute('aria-controls', 'explanation');
                button.append(node('span', format(row.after_rank), 'strategy-position'));
                const body = node('div'); const line = node('div', null, 'strategy-product-line'); const product = node('div');
                const identity = label(model, row); product.append(node('span', identity.name, 'strategy-product-name'), node('bdi', identity.code, 'strategy-code'));
                if (focus === model.maps.after.get(row.source.recommendation_id) && model.movements.get(row.source.recommendation_id).positions_gained > 0) {
                    product.append(node('span', 'بیشترین صعود در این مقایسه', 'strategy-focus-label'));
                }
                const move = movement(model.movements.get(row.source.recommendation_id));
                line.append(product, node('span', move.label, 'strategy-movement strategy-movement-' + move.className));
                const scores = node('div', null, 'strategy-score-line');
                const base = node('span', 'امتیاز موتور: '); base.append(node('strong', format(row.source.base_score)));
                const effective = node('span', 'اولویت مؤثر: ', 'strategy-effective'); effective.append(node('strong', format(row.effective_priority)));
                scores.append(base, effective);
                body.append(line, scores, node('span', availability(row), 'strategy-stock'));
                button.append(body); li.append(button); list.append(li);
                button.addEventListener('click', () => select(row.source.recommendation_id));
                buttons.push({id: row.source.recommendation_id, button});
            });
        }
        root.querySelector('#comparisonEmpty').hidden = after.length !== 0;
        root.querySelector('#explanation').hidden = after.length === 0;
        if (focus) select(focus.source.recommendation_id);
    }
    function attach(document, root, fetcher) {
        if (document.defaultView && document.defaultView.matchMedia) {
            setupResponsiveComparison(document, root, document.defaultView.matchMedia('(max-width: 600px)'));
        }
        const status = root.querySelector('#comparisonStatus');
        const error = root.querySelector('#comparisonError');
        const content = root.querySelector('#comparisonContent');
        const retry = root.querySelector('#comparisonRetry');
        const login = root.querySelector('#comparisonLogin');
        let serial = 0;
        async function load() {
            const request = ++serial;
            error.hidden = true; content.hidden = true; status.hidden = false; retry.disabled = true;
            content.setAttribute('aria-busy', 'true');
            try {
                requireValue(/^\/api\/management\/v1\/strategy\/comparisons\/[1-9]\d*\/$/.test(root.dataset.apiUrl));
                const response = await fetcher(root.dataset.apiUrl, {method: 'GET', credentials: 'same-origin', cache: 'no-store',
                    redirect: 'error', headers: {'Accept': 'application/json'}});
                if (request !== serial) return;
                if (!response.ok) { const failure = new Error('HTTP'); failure.status = response.status; throw failure; }
                const data = await response.json();
                if (request !== serial) return;
                render(document, root, validate(data, Number(root.dataset.comparisonId)));
                content.hidden = false;
            } catch (failure) {
                if (request !== serial) return;
                root.querySelector('#comparisonErrorText').textContent = ERRORS[failure.status] ||
                    'دریافت شواهد کامل نشد یا دادهٔ مقایسه معتبر نیست. برای تلاش دوباره، دکمهٔ دریافت را بزنید.';
                login.hidden = failure.status !== 401;
                error.hidden = false;
            } finally {
                if (request === serial) { status.hidden = true; retry.disabled = false; content.setAttribute('aria-busy', 'false'); }
            }
        }
        retry.addEventListener('click', load);
        load();
        return {load};
    }
    const exports = {validate, format, movement, availability, setupResponsiveComparison, render, attach, ERRORS};
    if (typeof module !== 'undefined' && module.exports) module.exports = exports;
    if (scope.document) {
        const root = scope.document.getElementById('strategyComparison');
        if (root && root.dataset.comparisonId) attach(scope.document, root, scope.fetch.bind(scope));
    }
})(typeof window !== 'undefined' ? window : globalThis);
