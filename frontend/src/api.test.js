import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { api } from './api.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

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
