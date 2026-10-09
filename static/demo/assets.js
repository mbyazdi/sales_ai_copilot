/* Failed local imagery restores the existing presentation fallback, without requests/mutations. */
(() => {
    'use strict';
    document.addEventListener('error', event => {
        const image = event.target;
        if (!image.matches?.('img[data-demo-image]')) return;
        const slot = image.closest('[data-demo-slot]');
        if (!slot) return;
        image.hidden = true;
        const fallback = slot.querySelector('[data-demo-fallback]');
        if (fallback) fallback.hidden = false;
        const scope = slot.closest('[data-demo-scope]');
        scope?.querySelectorAll('[data-demo-caption]').forEach(caption => { caption.hidden = true; });
    }, true);
})();
