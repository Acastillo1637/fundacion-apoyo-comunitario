import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';
import { readFile } from 'node:fs/promises';

let vite, dom, root, Qualifications, Auth, originalFetch;
before(async () => {
  dom = new JSDOM('<div id="root"></div>');
  globalThis.window = dom.window; globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  originalFetch = globalThis.fetch;
  vite = await createServer({ server: { middlewareMode: true, hmr: { port: 24686 } }, appType: 'custom' });
  Qualifications = (await vite.ssrLoadModule('/src/volunteers/Qualifications.jsx')).default;
  Auth = (await vite.ssrLoadModule('/src/design/Auth.jsx')).default;
});
after(async () => { if (root) await act(() => root.unmount()); globalThis.fetch = originalFetch; await vite?.close(); dom?.window.close(); });
test('Otro oficio queda al final, exige descripción y conserva Sin carrera universitaria al guardar', async () => {
  let saved;
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/session/') return Response.json({csrf_token:'test'});
    if (url === '/api/volunteer/catalogs/') return Response.json({skills:[],professions:[
      {id:1,name:'Otro oficio',kind:'other',is_active:true,required_documents:[]},
      {id:2,name:'Diseño gráfico',kind:'professional',is_active:true,required_documents:[]},
    ]});
    if (options.method === 'PUT') { saved = JSON.parse(options.body); return Response.json({...saved,revision:1}); }
    return Response.json({revision:0,skills:[],professions:[1],other_trade:'Carpintería',without_university_degree:true});
  };
  root = createRoot(document.querySelector('#root'));
  await act(async () => root.render(React.createElement(Qualifications)));
  assert.deepEqual([...document.querySelectorAll('.catalog-option strong')].map(el => el.textContent), ['Diseño gráfico','Otro oficio']);
  const text = document.querySelector('input[name="other_trade"]');
  assert.equal(text.required, true); assert.equal(text.value, 'Carpintería');
  await act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true})));
  assert.equal(saved.other_trade, 'Carpintería'); assert.equal(saved.without_university_degree, true);
});
test('los radios del registro conservan tamaño propio y permiten elegir el perfil', async () => {
  await act(() => root.unmount());
  root = createRoot(document.querySelector('#root'));
  await act(async () => root.render(React.createElement(Auth,{mode:'register',brand:'Fundación Apoyo Comunitario',navigate:()=>{},onLogin:()=>{}})));
  const css = await readFile(new URL('./design/stitch.css', import.meta.url), 'utf8');
  const style = document.createElement('style'); style.textContent = css; document.head.append(style);
  const radios = [...document.querySelectorAll('.account-type-picker input[type="radio"]')];
  assert.equal(radios.length, 2);
  for (const radio of radios) { const computed = window.getComputedStyle(radio); assert.equal(computed.width,'18px'); assert.equal(computed.height,'18px'); assert.equal(computed.position,'static'); }
  await act(async () => radios[1].click());
  assert.equal(radios[1].checked, true); assert.equal(radios[0].checked, false);
  assert.ok(document.querySelector('select[name="requester_type"]'));
});
