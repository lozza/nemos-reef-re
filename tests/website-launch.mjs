import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import test from 'node:test';

const sha = value => createHash('sha256').update(value).digest('hex');
const password = 'test-only-password-not-a-production-credential';
const session = sha('nrr-preview-session:' + password);
const source = (await readFile(new URL('../public/_worker.js', import.meta.url), 'utf8'))
  .replace(/const PASSWORD_HASH = '[a-f0-9]+';/, `const PASSWORD_HASH = '${sha(password)}';`)
  .replace(/const SESSION_HASH = '[a-f0-9]+';/, `const SESSION_HASH = '${sha(session)}';`);
const worker = (await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))).default;
const origin = 'https://reef.example';
const main = '<html><head></head><body>PRIVATE MAIN WEBSITE</body></html>';
const assets = {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    const content = path === '/index.html' ? main : path === '/launch.html' ? 'PUBLIC COUNTDOWN' : 'asset';
    return new Response(content, { headers: { 'Content-Type': 'text/html', 'Cache-Control': 'public, max-age=86400' } });
  }
};
const env = { ASSETS: assets, LAUNCH_AT: 'unset-for-test' };
const fetchSite = (path, init = {}, bindings = env) => worker.fetch(new Request(origin + path, init), bindings);
const form = value => ({ method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ password: value }) });
const cookie = { Cookie: '__Host-reef_preview=' + session };

test('anonymous visitors and direct index routes only receive the holding page', async () => {
  for (const path of ['/', '/index', '/index.html', '/launch.html', '/launch', '/coming-soon']) {
    const result = await fetchSite(path);
    assert.equal(await result.text(), 'PUBLIC COUNTDOWN');
    assert.match(result.headers.get('Cache-Control'), /no-store/);
  }
  assert.equal((await fetchSite('/_worker.js')).status, 404);
  assert.equal((await fetchSite('/server/nemo_server.py')).status, 404);
});
test('owner form is accessible and not indexed', async () => {
  const result = await fetchSite('/owner');
  assert.match(await result.text(), /type="password"/);
  assert.match(result.headers.get('X-Robots-Tag'), /noindex/);
});
test('wrong passwords and forged cookies never open the main website', async () => {
  assert.equal((await fetchSite('/owner', form('wrong'))).status, 401);
  assert.equal(await (await fetchSite('/', { headers: { Cookie: '__Host-reef_preview=' + '0'.repeat(64) } })).text(), 'PUBLIC COUNTDOWN');
  assert.equal(await (await fetchSite('/', { headers: { Cookie: '__Host-reef_preview=' + password } })).text(), 'PUBLIC COUNTDOWN');
});
test('valid login sets a secure derived cookie and redirects without leaking the password', async () => {
  const result = await fetchSite('/owner', form(password));
  assert.equal(result.status, 303);
  assert.equal(result.headers.get('Location'), '/');
  const value = result.headers.get('Set-Cookie');
  for (const expected of [session, 'HttpOnly', 'Secure', 'SameSite=Strict', 'Path=/', 'Max-Age=28800']) assert.ok(value.includes(expected));
  assert.ok(!value.includes(password));
});
test('authenticated preview is not cached or indexed and includes logout', async () => {
  const result = await fetchSite('/', { headers: cookie });
  const body = await result.text();
  assert.ok(body.includes('PRIVATE MAIN WEBSITE'));
  assert.ok(body.includes('Owner preview'));
  assert.ok(body.includes('/owner/logout'));
  assert.match(result.headers.get('Cache-Control'), /no-store/);
  assert.match(result.headers.get('X-Robots-Tag'), /noindex/);
  assert.equal(await (await fetchSite('/coming-soon', { headers: cookie })).text(), 'PUBLIC COUNTDOWN');
});
test('logout clears the browser cookie', async () => {
  const result = await fetchSite('/owner/logout', { method: 'POST', headers: { ...cookie, Origin: origin } });
  assert.equal(result.status, 303);
  assert.match(result.headers.get('Set-Cookie'), /Max-Age=0/);
});
test('cross-origin and malformed login requests are rejected', async () => {
  const crossOrigin = form(password);
  crossOrigin.headers.Origin = 'https://attacker.example';
  assert.equal((await fetchSite('/owner', crossOrigin)).status, 403);
  assert.equal((await fetchSite('/owner', { method: 'POST', body: 'x' })).status, 403);
  assert.equal((await fetchSite('/owner', { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: '{}' })).status, 415);
  assert.equal((await fetchSite('/owner', form('a'.repeat(2000)))).status, 413);
});
test('unset and invalid dates keep launch gated; status is based on server time', async () => {
  const result = await fetchSite('/launch-status');
  const status = await result.json();
  assert.equal(status.launchAt, null);
  assert.equal(status.launched, false);
  assert.ok(Number.isFinite(Date.parse(status.serverNow)));
  assert.equal(await (await fetchSite('/', {}, { ...env, LAUNCH_AT: 'bad-date' })).text(), 'PUBLIC COUNTDOWN');
});
test('future date stays gated; the launch boundary opens the original main page', async () => {
  const originalNow = Date.now;
  const date = '2030-11-07T18:00:00+00:00';
  const dateEnv = { ...env, LAUNCH_AT: date };
  try {
    Date.now = () => Date.parse(date) - 1;
    assert.equal(await (await fetchSite('/', {}, dateEnv)).text(), 'PUBLIC COUNTDOWN');
    Date.now = () => Date.parse(date);
    assert.equal(await (await fetchSite('/', {}, dateEnv)).text(), main);
    assert.equal((await (await fetchSite('/launch-status', {}, dateEnv)).json()).launched, true);
  } finally { Date.now = originalNow; }
});
test('HEAD requests have no response body', async () => {
  for (const path of ['/', '/owner', '/launch-status', '/coming-soon']) assert.equal(await (await fetchSite(path, { method: 'HEAD' })).text(), '');
});
