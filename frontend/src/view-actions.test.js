import {before, after, test} from 'node:test';
import assert from 'node:assert/strict';
import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {JSDOM} from 'jsdom';
import {createServer} from 'vite';

let vite, dom, root, host, Operations, Participants, clear;
const originalFetch=globalThis.fetch, originalFormData=globalThis.FormData;
const event={id:'event-qa',title:'Actividad de prueba',status:'open',date:'2099-12-04',start_time:'10:00',end_time:'12:00',
  starts_at:'2099-12-04T13:00:00Z',ends_at:'2099-12-04T15:00:00Z',commune:'En línea',address:'Actividad remota',
  public_description:'Descripción pública suficientemente extensa.',internal_notes:'',revision:0,can_edit_information:true,
  location:{is_remote:true,latitude:null,longitude:null},history:[],changes:[],positions:[101,202].map(id=>({id,name:`Función ${id}`,capacity:2,required_skills:[],required_documents:[],inherited_documents:[],desired_skills:[]}))};
before(async()=>{
  dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/'});
  globalThis.window=dom.window;globalThis.document=dom.window.document;globalThis.FormData=dom.window.FormData;
  globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  vite=await createServer({server:{middlewareMode:true,hmr:{port:24687}},appType:'custom'});
  Operations=(await vite.ssrLoadModule('/src/activities/Operations.jsx')).default;
  Participants=(await vite.ssrLoadModule('/src/activities/Participation.jsx')).default;
  clear=(await vite.ssrLoadModule('/src/api.js')).clearPrivateData;
  host=document.querySelector('#root');
});
after(async()=>{if(root)await act(()=>root.unmount());globalThis.fetch=originalFetch;globalThis.FormData=originalFormData;await vite?.close();dom?.window.close();});
async function mount(Component,props={},writes=[]){
  if(root)await act(()=>root.unmount());clear();
  globalThis.fetch=async(url,options={})=>{
    if(url==='/api/session/')return Response.json({csrf_token:'test'});
    if(options.body){writes.push({url,method:options.method,body:JSON.parse(options.body)});return Response.json(event);}
    if(url.includes('/options/'))return Response.json({skills:[],documents:[]});
    if(url.includes('/contacts/'))return Response.json({results:[],total:0});
    if(url.includes('/participants/'))return Response.json({results:url.includes('assignment=backup')?[{id:4,profile_id:22,position_id:202,position:'Función 202',name:'Respaldo QA',status:'declined',assignment:'backup',eligible:true,starts_at:event.starts_at}]:[],total:1,stats:{vacancies:[]}});
    if(url.includes('/events/event-qa/'))return Response.json(event);
    return Response.json({results:url.includes('/events/')?[event]:[],total:1});
  };
  root=createRoot(host);await act(async()=>root.render(React.createElement(Component,props)));
}
async function click(text){const button=[...host.querySelectorAll('button')].find(node=>node.textContent.trim()===text);assert.ok(button,`Botón ${text}`);await act(async()=>button.click());}
test('editar información publicada abre un formulario funcional y conserva los campos logísticos',async()=>{
  const writes=[];await mount(Operations,{},writes);await click('Eventos');await click('Ver detalle');await click('Editar información publicada');
  const form=host.querySelector('.published-information-editor form');assert.ok(form);
  assert.equal(form.querySelector('input[type="checkbox"]'),null);
  form.elements.reason.value='Corrección solicitada por coordinación';
  form.elements.title.value='Título público actualizado';
  await act(async()=>form.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true})));
  assert.equal(writes.length,1);assert.equal(writes[0].method,'PATCH');
  assert.deepEqual(Object.keys(writes[0].body).sort(),['internal_notes','public_description','reason','revision','title']);
  assert.equal(writes[0].body.title,'Título público actualizado');
  assert.equal([...host.querySelectorAll('button')].find(node=>node.textContent==='Finalizar actividad').disabled,true);
});
test('cancelar la edición no envía cambios',async()=>{
  const writes=[];await mount(Operations,{},writes);await click('Eventos');await click('Ver detalle');await click('Editar información publicada');await click('Cancelar edición');
  assert.equal(host.querySelector('.published-information-editor'),null);assert.equal(writes.length,0);
});
test('el editor de borrador conserva la ubicación remota al guardar',async()=>{
  const writes=[];event.status='draft';event.can_edit_information=false;
  try{
    await mount(Operations,{},writes);await click('Eventos');await click('Ver detalle');await click('Editar borrador');
    const form=host.querySelector('form.planning-form');assert.ok(form);
    assert.equal(form.querySelector('input[type="checkbox"]').checked,true);
    await act(async()=>form.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true})));
    assert.equal(writes[0].method,'PUT');assert.equal(writes[0].body.is_remote,true);
    assert.equal(writes[0].body.latitude,null);assert.equal(writes[0].body.commune,'En línea');
    assert.equal(writes[0].body.positions.length,2);
  }finally{event.status='open';event.can_edit_information=true;}
});
test('reinvitación de respaldo conserva su función aunque otra sea la primera del evento',async()=>{
  const writes=[];await mount(Participants,{initialEventId:event.id},writes);await click('Volver a invitar como respaldo');
  assert.deepEqual(writes[0].body,{profile_id:22,position_id:202,assignment:'backup'});
});
test('seleccionar y cambiar convocatoria notifica al router para conservar el destino al recargar',async()=>{
  const selected=[];await mount(Participants,{onEventChange:id=>selected.push(id)});await click('Administrar participantes');assert.deepEqual(selected,[event.id]);
  await mount(Participants,{initialEventId:event.id,onEventChange:id=>selected.push(id)});await click('Cambiar evento');assert.deepEqual(selected,[event.id,null]);
});
