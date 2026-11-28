import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';
import { readFile } from 'node:fs/promises';

let vite, dom, root, Qualifications, Auth, Preferences, originalFetch;
before(async () => {
  dom = new JSDOM('<div id="root"></div>');
  globalThis.window = dom.window; globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  originalFetch = globalThis.fetch;
  vite = await createServer({ server: { middlewareMode: true, hmr: { port: 24686 } }, appType: 'custom' });
  Qualifications = (await vite.ssrLoadModule('/src/volunteers/Qualifications.jsx')).default;
  Auth = (await vite.ssrLoadModule('/src/design/Auth.jsx')).default;
  Preferences = (await vite.ssrLoadModule('/src/activities/Contacts.jsx')).CommunicationPreferences;
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

test('el registro de voluntarios exige teléfono y comuna y carga la misma lista pública', async () => {
  await act(() => root.unmount());
  (await vite.ssrLoadModule('/src/api.js')).clearPrivateData();
  const requested = [];
  globalThis.fetch = async url => { requested.push(url); return Response.json({communes:['Renca','Maipú']}); };
  root = createRoot(document.querySelector('#root'));
  await act(async () => root.render(React.createElement(Auth,{mode:'register',brand:'Fundación',navigate:()=>{},onLogin:()=>{}})));
  const phone = document.querySelector('input[name="phone"]');
  const commune = document.querySelector('input[name="commune"]');
  assert.equal(phone.required, true); assert.equal(phone.maxLength, 12);
  assert.equal(document.querySelector('input[name="whatsapp"]').required, true);
  assert.equal(commune.required, true);
  assert.equal(phone.checkValidity(), false); assert.equal(commune.checkValidity(), false);
  phone.value = '912345678'; assert.equal(phone.checkValidity(), true);
  phone.value = '+12125550199'; assert.equal(phone.checkValidity(), false);
  assert.equal(document.querySelectorAll('input[name="phone"]').length, 1);
  assert.deepEqual([...document.querySelectorAll('datalist option')].map(el => el.value), ['Renca','Maipú']);
  assert.ok(requested.includes('/api/communes/'));
});

test('comunicación muestra el celular chileno sin prefijo y exige autorización', async () => {
  await act(() => root.unmount());
  (await vite.ssrLoadModule('/src/api.js')).clearPrivateData();
  globalThis.fetch = async () => Response.json({phone:'+56912345678',whatsapp:false,revision:0});
  root = createRoot(document.querySelector('#root'));
  await act(async () => root.render(React.createElement(Preferences)));
  const phone = document.querySelector('input[name="phone"]');
  assert.equal(phone.value, '912345678'); assert.equal(phone.required, true);
  const consent = document.querySelector('input[type="checkbox"]');
  assert.equal(consent.required, true); assert.equal(consent.checked, false);
  assert.equal(consent.checkValidity(), false);
  assert.doesNotMatch(document.querySelector('#root').textContent, /Teléfono internacional|Es opcional/);
});
