import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

let vite, dom, root, host, Button, Contacts, clear, originalFetch;
let stored, actions, creations, opened, allowPopup, confirmation;
const timestamp = '2026-11-25T12:00:00Z';
const actor = {at:timestamp,actor:'Secretaría de prueba',actor_id:'test-secretary'};
before(async () => {
  dom = new JSDOM('<div id="root"></div>', {url:'http://localhost/matching'});
  globalThis.window=dom.window; globalThis.document=dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  originalFetch=globalThis.fetch;
  vite=await createServer({server:{middlewareMode:true,hmr:{port:24684}},appType:'custom'});
  const module=await vite.ssrLoadModule('/src/activities/Contacts.jsx');
  Button=module.ContactCandidateButton; Contacts=module.default;
  clear=(await vite.ssrLoadModule('/src/api.js')).clearPrivateData;
  host=document.querySelector('#root');
});
after(async()=>{if(root)await act(()=>root.unmount());globalThis.fetch=originalFetch;await vite?.close();dom?.window.close();});
function setup() {
  actions=[];creations=0;opened=[];allowPopup=true;confirmation=true;
  stored={id:7,profile_id:9,position_id:3,name:'Persona ficticia',position:'Apoyo',status:'pending_contact',revision:0,expires_at:'2099-01-01T00:00:00Z',history:[],delivery:{opened:null,sent:null,send_confirmed:false,can_confirm_send:false}};
  window.confirm=()=>confirmation;
  window.open=()=>allowPopup ? {opener:null,closed:false,location:{replace:url=>opened.push(url)},close(){this.closed=true;}} : null;
  globalThis.fetch=async(url,options={})=>{
    if(url==='/api/session/')return Response.json({csrf_token:'test'});
    if(options.method==='POST' && url==='/api/activities/operations/events/event/contacts/') {
      creations++;return Response.json(structuredClone(stored));
    }
    if(options.method==='POST') {
      const body=JSON.parse(options.body);actions.push(body.action);
      if(body.action==='start') {
        if(stored.status==='pending_contact')stored.status='contact_started';
        stored.delivery.opened=actor;stored.delivery.can_confirm_send=!stored.delivery.send_confirmed;
      } else if(body.action==='sent') {
        stored.status='sent';stored.delivery.sent=actor;stored.delivery.send_confirmed=true;stored.delivery.can_confirm_send=false;
      }
      stored.revision++;
      return Response.json({...structuredClone(stored),...(body.action==='start'?{whatsapp_url:'https://wa.me/56900000000?text=DEMO'}:{})});
    }
    return Response.json({results:[structuredClone(stored)],total:1,page:1});
  };
}
async function mount(component=Button) {
  if(root)await act(()=>root.unmount());clear();root=createRoot(host);
  await act(async()=>root.render(React.createElement(component,component===Button?{eventId:'event',positionId:3,profileId:9,contact:structuredClone(stored)}:{eventId:'event'})));
}
async function click(text) {
  const button=[...host.querySelectorAll('button')].find(node=>node.textContent===text);
  assert.ok(button,`Falta ${text}`);assert.equal(button.disabled,false);
  await act(async()=>button.click());
}

test('abrir y reabrir no confirman envío; el botón continúa habilitado al recargar',async()=>{
  setup();await mount();await click('Contactar por WhatsApp');
  assert.deepEqual(actions,['start']);assert.equal(stored.delivery.send_confirmed,false);
  assert.match(host.textContent,/Envío pendiente de confirmación/);
  await click('Volver a abrir WhatsApp');assert.equal(opened.length,2);
  assert.deepEqual(actions,['start','start']);assert.equal(stored.id,7);
  await mount();await click('Volver a abrir WhatsApp');
  assert.ok([...host.querySelectorAll('button')].find(node=>node.textContent==='Confirmar envío'));
  assert.equal(stored.delivery.send_confirmed,false);
});

test('solo Confirmar envío registra sent, conserva responsable y persiste después de recargar',async()=>{
  setup();await mount();await click('Contactar por WhatsApp');await click('Confirmar envío');
  assert.deepEqual(actions,['start','sent']);
  assert.match(host.textContent,/Envío confirmado manualmente/);
  assert.match(host.textContent,/Secretaría de prueba/);
  await mount();
  assert.equal([...host.querySelectorAll('button')].some(node=>node.textContent==='Confirmar envío'),false);
  await click('Volver a abrir WhatsApp');assert.equal(stored.status,'sent');
  assert.deepEqual(actions,['start','sent','start']);
});

test('cancelar la confirmación no registra el envío ni una aceptación',async()=>{
  setup();await mount();await click('Contactar por WhatsApp');confirmation=false;
  await click('Confirmar envío');assert.deepEqual(actions,['start']);
  assert.equal(stored.delivery.send_confirmed,false);
});

test('una ventana bloqueada conserva pendiente y permite reintentar',async()=>{
  setup();allowPopup=false;await mount();await click('Contactar por WhatsApp');
  assert.match(host.textContent,/Permite ventanas emergentes/);assert.equal(stored.delivery.send_confirmed,false);
  allowPopup=true;await click('Volver a abrir WhatsApp');assert.equal(opened.length,1);
  assert.deepEqual(actions,['start','start']);
});

test('el seguimiento recargado ofrece Confirmar envío sin confundirlo con Registrar aceptación',async()=>{
  setup();stored.status='contact_started';stored.delivery.opened=actor;stored.delivery.can_confirm_send=true;
  await mount(Contacts);
  const labels=[...host.querySelectorAll('button')].map(node=>node.textContent);
  assert.ok(labels.includes('Confirmar envío'));assert.ok(labels.includes('Registrar aceptación'));
  await click('Confirmar envío');assert.deepEqual(actions,['sent']);
  assert.match(host.textContent,/Envío confirmado manualmente/);
});
