import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

let vite, dom, root, Field, originalFetch;
before(async () => {
  dom = new JSDOM('<div id="root"></div>');
  globalThis.window = dom.window; globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  originalFetch = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ communes: ['Renca', 'Maipú', 'Ñuñoa'] });
  vite = await createServer({ server: { middlewareMode: true, hmr: { port: 24685 } }, appType: 'custom' });
  Field = (await vite.ssrLoadModule('/src/volunteers/CommuneField.jsx')).default;
});
after(async () => {
  if (root) await act(() => root.unmount());
  globalThis.fetch = originalFetch; await vite?.close(); dom?.window.close();
});
test('filtra ren a Renca y rechaza comunas inventadas o vacías', async () => {
  root = createRoot(document.querySelector('#root'));
  await act(async () => root.render(React.createElement(Field, { initialValue: 'ren' })));
  let input = document.querySelector('input');
  assert.deepEqual([...document.querySelectorAll('option')].map(option => option.value), ['Renca']);
  assert.equal(input.checkValidity(), false);
  for (const [value, valid] of [['Renca', true], ['juanita', false], ['', false], ['maipu', true]]) {
    await act(async () => root.render(React.createElement(Field, { key: value, initialValue: value })));
    input = document.querySelector('input');
    assert.equal(input.checkValidity(), valid, value);
  }
});
