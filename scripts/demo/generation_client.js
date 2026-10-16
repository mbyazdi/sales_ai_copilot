/* Loaded only by the dedicated Demo middleware; no production/preview include. */
(function () {
    'use strict';
    const script = document.currentScript;
    const generation = script.dataset.demoGeneration, proof = script.dataset.demoProof;
    window.DemoGeneration = Object.freeze({
        bind(command) {
            // Only new commands are bound. Never upgrade a persisted/retried envelope.
            if (!Object.prototype.hasOwnProperty.call(command, 'demoGeneration')) {
                command.demoGeneration = Object.freeze({generation, proof});
            }
            return command;
        },
        headers(command) {
            return {'X-Demo-Generation-Proof': command.demoGeneration?.proof || ''};
        }
    });
    const original = window.fetch.bind(window);
    window.fetch = function (input, init = {}) {
        const url = new URL(typeof input === 'string' ? input : input.url, location.href);
        const method = (init.method || input?.method || 'GET').toUpperCase();
        if (url.origin !== location.origin || ['GET', 'HEAD', 'OPTIONS'].includes(method)) return original(input, init);
        const headers = new Headers(init.headers || input?.headers);
        let command = false;
        try { command = Boolean(JSON.parse(init.body).command_uuid); } catch (_) { /* Legacy form/lifecycle request. */ }
        // UUID mutations require their immutable envelope proof from the call site.
        // Unmarked old pending data gets no new-page proof and fails server-side.
        if (!command && !headers.has('X-Demo-Generation-Proof')) headers.set('X-Demo-Generation-Proof', proof);
        return original(input, {...init, headers});
    };
    function forms() {
        for (const form of document.querySelectorAll('form')) {
            if ((form.method || 'get').toLowerCase() === 'get' || form.querySelector('[name="_demo_generation_proof"]')) continue;
            const field = document.createElement('input'); field.type = 'hidden'; field.name = '_demo_generation_proof'; field.value = proof; form.append(field);
        }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', forms); else forms();
}());
