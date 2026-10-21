import test from 'node:test';
import assert from 'node:assert/strict';
import { bearerHeaders } from '../src/auth-headers.js';

test('direct local clients retain standard bearer transport', () => {
    assert.deepEqual(bearerHeaders('opaque-token', undefined), {
        Authorization: 'Bearer opaque-token',
    });
});

test('proxy opt-in leaves Authorization available for browser Basic Auth', () => {
    const document = { querySelector(selector) {
        assert.equal(selector, 'meta[name="aila-bearer-header"]');
        return { content: 'X-App-Authorization' };
    } };
    assert.deepEqual(bearerHeaders('opaque-token', document), {
        'X-App-Authorization': 'Bearer opaque-token',
    });
});

test('missing or unrecognized proxy configuration cannot choose another header', () => {
    for (const meta of [null, { content: 'Cookie' }, { content: 'Authorization' }]) {
        assert.deepEqual(bearerHeaders('token', { querySelector: () => meta }), {
            Authorization: 'Bearer token',
        });
    }
});
