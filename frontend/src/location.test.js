import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

let vite, dom, host, root, LocationSettings, originalFetch;
before(async () => {
  dom = new JSDOM('<div id="root"></div>', { url:'http://localhost/perfil' });
  globalThis.window = dom.window; globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  vite = await createServer({ server:{ middlewareMode:true, hmr:{ port:24682 } }, appType:'custom' });
  LocationSettings = (await vite.ssrLoadModule('/src/maps/LocationSettings.jsx')).default;
  host = document.querySelector('#root'); originalFetch = globalThis.fetch;
});
after(async () => { globalThis.fetch = originalFetch; if (root) await act(() => root.unmount()); await vite?.close(); dom?.window.close(); });
const location = { latitude:-33.4, longitude:-70.6, commune:'Santiago', sector:'Centro', revision:0, address_geocoding_enabled:true, precision:'Referencia aproximada' };
async function mount(answer) {
  if (root) await act(() => root.unmount());
  const apiModule = await vite.ssrLoadModule('/src/api.js'); apiModule.clearPrivateData();
  globalThis.fetch = async (url, options) => {
    if (url === '/api/volunteer/location/address/') return answer(options);
    if (url === '/api/communes/') return Response.json({communes:['Santiago']});
    if (url === '/api/session/') return Response.json({csrf_token:'test'});
    return Response.json(location);
  };
  root = createRoot(host);
  await act(async () => { root.render(React.createElement(LocationSettings)); });
}
async function submit() { await act(async () => { host.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles:true, cancelable:true })); }); }

test('el formulario informa transferencia, pide consentimiento y no solicita coordenadas como entrada principal', async () => {
  await mount(() => Response.json({}));
  const form = host.querySelector('form');
  assert.match(form.textContent, /Geoapify recibirá esta dirección/);
  assert.ok(form.querySelector('input[type="checkbox"][required]'));
  assert.equal(form.querySelector('button').disabled, true);
  assert.equal(form.querySelectorAll('input[type="number"]').length, 0);
});

test('un error de geocodificación conserva la referencia y presenta el error del servidor', async () => {
  await mount(() => Response.json({detail:'Proveedor no disponible; referencia conservada.'}, {status:503}));
  await submit();
  assert.match(host.querySelector('[role="alert"]').textContent, /referencia conservada/);
  assert.match(host.textContent, /Referencia actual: -33.4, -70.6/);
});

test('un resultado ambiguo exige confirmar sector y no anuncia que guardó', async () => {
  await mount(() => Response.json({saved:false,choices:[{token:'signed',label:'Santiago',latitude:-33.45,longitude:-70.65}]}));
  await submit();
  assert.match(host.textContent, /Confirmar este sector/);
  assert.doesNotMatch(host.textContent, /calculada y guardada/);
  assert.match(host.textContent, /Referencia actual: -33.4, -70.6/);
});

test('el guardado exitoso actualiza la referencia persistida', async () => {
  await mount(() => Response.json({saved:true,location:{...location,latitude:-33.45,longitude:-70.65,revision:1}}));
  await submit();
  assert.match(host.textContent, /calculada y guardada/);
  assert.match(host.textContent, /Referencia actual: -33.45, -70.65/);
});

