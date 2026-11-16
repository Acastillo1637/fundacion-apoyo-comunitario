import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { api, readSnapshot, clearPrivateData } from './api.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('seguridad no conserva snapshots y el cierre limpia los datos anteriores', async () => {
  globalThis.fetch=async()=>Response.json({email:'demo@example.org',totp_enabled:true});
  await api('security/');
  assert.equal(readSnapshot('security/'),null);
  await api('private-dashboard/');
  assert.ok(readSnapshot('private-dashboard/'));
  clearPrivateData();
  assert.equal(readSnapshot('private-dashboard/'),null);
});

test('las copias en memoria no comparten cambios del formulario y no evitan la consulta nueva', async () => {
  let calls = 0;
  globalThis.fetch = async () => { calls++; return Response.json({ slots: [1] }); };
  await api('snapshot-test/');
  const previous = readSnapshot('snapshot-test/');
  previous.slots.push(2);
  assert.deepEqual(readSnapshot('snapshot-test/'), { slots: [1] });
  await api('snapshot-test/');
  assert.equal(calls, 2);
  await api('logout/', { method: 'POST' });
  assert.equal(readSnapshot('snapshot-test/'), null);
});

test('una lectura de una generación anterior no repuebla los datos después de guardar', async () => {
  let finish;
  globalThis.fetch = async url => url.endsWith('old-snapshot/')
    ? new Promise(resolve => { finish = () => resolve(Response.json({ old: true })); })
    : Response.json({ saved: true });
  const previous = api('old-snapshot/');
  await api('save/', { method: 'POST' });
  finish(); await previous;
  assert.equal(readSnapshot('old-snapshot/'), null);
});

test('guardar también descarta lecturas que terminaron durante la escritura', async () => {
  let finishSave;
  globalThis.fetch = async url => url.endsWith('save-in-progress/')
    ? new Promise(resolve => { finishSave = () => resolve(Response.json({ saved: true })); })
    : Response.json({ old: true });
  const save = api('save-in-progress/', { method: 'POST' });
  await api('during-save/');
  assert.deepEqual(readSnapshot('during-save/'), { old: true });
  finishSave(); await save;
  assert.equal(readSnapshot('during-save/'), null);
});

test('los datos conservados vencen y se descartan al denegarse el acceso', async () => {
  const originalNow = Date.now;
  try {
    Date.now = () => 100000;
    globalThis.fetch = async () => Response.json({ private: true });
    await api('expiring-snapshot/');
    Date.now = () => 160001;
    assert.equal(readSnapshot('expiring-snapshot/'), null);
    await api('protected-snapshot/');
    globalThis.fetch = async () => Response.json({ detail: 'Sin acceso' }, { status: 403 });
    await assert.rejects(api('protected-check/'), /Sin acceso/);
    assert.equal(readSnapshot('protected-snapshot/'), null);
  } finally { Date.now = originalNow; }
});

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

test('muestra errores de validación DRF en listas sin aceptar listas como respuesta exitosa',async()=>{
  globalThis.fetch=async()=>Response.json(['La contraseña actual no es correcta.'],{status:400});
  await assert.rejects(api('security/action/',{method:'POST'}),/La contraseña actual no es correcta/);
  globalThis.fetch=async()=>Response.json(['unexpected success']);
  await assert.rejects(api('security/'),/respuesta inesperada/);
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
