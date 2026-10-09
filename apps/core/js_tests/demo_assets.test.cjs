const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../../static/demo/assets.js'), 'utf8');

test('failed local image restores its own existing fallback and hides sample caption', () => {
    let listener;
    const fallback = {hidden: true}, caption = {hidden: false};
    const scope = {querySelectorAll: () => [caption]};
    const slot = {querySelector: () => fallback, closest: () => scope};
    const image = {hidden: false, matches: () => true, closest: () => slot};
    vm.runInNewContext(source, {document: {addEventListener(name, callback, capture) {
        assert.equal(name, 'error'); assert.equal(capture, true); listener = callback;
    }}});
    listener({target: image});
    assert(image.hidden); assert(!fallback.hidden); assert(caption.hidden);
});

test('unrelated image/error events are unaffected', () => {
    let listener;
    vm.runInNewContext(source, {document: {addEventListener(_name, callback) {listener = callback;}}});
    listener({target: {matches: () => false}});
    listener({target: {}});
});
