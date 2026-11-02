import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { api } from './api.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('comparte lecturas simultáneas y vuelve a consultar después de completarlas', async () => {
  let calls = 0;
  globalThis.fetch = async () => { calls++; return Response.json({ value: calls }); };
  const [first, second] = await Promise.all([api('session/'), api('session/')]);
  assert.equal(calls, 1);
  assert.deepEqual(first, second);
  await api('session/');
  assert.equal(calls, 2);
});

test('una mutación impide reutilizar lecturas pendientes de la sesión anterior', async () => {
  let finish;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    if (calls === 1) return new Promise(resolve => { finish = () => resolve(Response.json({ old: true })); });
    return Response.json({ old: false });
  };
  const previous = api('session/');
  await api('logout/', { method: 'POST' });
  assert.deepEqual(await api('session/'), { old: false });
  finish();
  await previous;
  assert.equal(calls, 3);
});

test('el desafío MFA se muestra en el acceso de la web', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'Ingresa tu código.', mfa_required: true }, { status: 409 });
  await assert.rejects(api('login/'), error => error.mfaRequired === true && !error.continueUrl);
});

test('explica un rechazo CSRF cuando el proxy devuelve HTML', async () => {
  globalThis.fetch = async () => new Response('<html>Forbidden</html>', { status: 403 });
  await assert.rejects(api('register/', { method: 'POST' }), /seguridad de la sesión/);
});

test('una respuesta HTML exitosa no se interpreta como registro exitoso', async () => {
  globalThis.fetch = async () => new Response('<html>frontend</html>', { status: 200 });
  await assert.rejects(api('register/', { method: 'POST' }), /respuesta inesperada/);
});

test('distingue errores de conexión y errores del servidor', async () => {
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(api('register/'), /No hay conexión/);
  globalThis.fetch = async () => new Response('Server error', { status: 500 });
  await assert.rejects(api('register/'), /terminal de Django/);
});

test('conserva el mensaje JSON del backend', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'Recarga tu sesión.', code: 'csrf_failed' }, { status: 403 });
  await assert.rejects(api('register/'), /Recarga tu sesión/);
});

test('los archivos multipart conservan el boundary del navegador', async () => {
  const body = new FormData();
  body.append('file', new Blob(['archivo ficticio'], { type: 'application/pdf' }), 'prueba.pdf');
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/documents/');
    assert.equal(options.body, body);
    assert.equal(options.headers['Content-Type'], undefined);
    assert.ok(Object.hasOwn(options.headers, 'X-CSRFToken'));
    return Response.json({ status: 'pending' }, { status: 201 });
  };
  assert.equal((await api('documents/', { method: 'POST', body })).status, 'pending');
});
