import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';
import { operationPath, eventStates, emptyFilters } from './activities/list-filters.js';

let vite, dom, host, root, Notifications, ListFilters, clear, originalFetch, contactExpired;
before(async () => {
  dom = new JSDOM('<div id="root"></div>', {url:'http://localhost/notificaciones'});
  globalThis.window = dom.window; globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  originalFetch = globalThis.fetch;
  vite = await createServer({server:{middlewareMode:true,hmr:{port:24683}},appType:'custom'});
  Notifications = (await vite.ssrLoadModule('/src/activities/Notifications.jsx')).default;
  ListFilters = (await vite.ssrLoadModule('/src/activities/ListFilters.jsx')).default;
  clear = (await vite.ssrLoadModule('/src/api.js')).clearPrivateData;
  contactExpired = (await vite.ssrLoadModule('/src/activities/Contacts.jsx')).contactExpired;
  host = document.querySelector('#root');
});
after(async () => { if(root) await act(()=>root.unmount()); globalThis.fetch=originalFetch; await vite?.close(); dom?.window.close(); });
async function mount(fetcher, props={}) {
  if(root) await act(()=>root.unmount()); clear();
  globalThis.fetch=async (url,options)=>url==='/api/session/' ? Response.json({csrf_token:'test'}) : fetcher(url,options);
  root=createRoot(host);
  await act(async()=>root.render(React.createElement(Notifications,props)));
}
async function click(text) { const button=[...host.querySelectorAll('button')].find(node=>node.textContent===text); assert.ok(button); await act(async()=>button.click()); }

test('la búsqueda codifica caracteres y conserva filtros al cambiar de página',()=>{
  const url=operationPath('events',2,{q:'Maipú & encuentro',status:'open',period:'upcoming'});
  const parameters=new URL('http://localhost/'+url).searchParams;
  assert.equal(parameters.get('q'),'Maipú & encuentro');
  assert.equal(parameters.get('page'),'2');
  assert.equal(parameters.get('status'),'open');
  assert.equal(parameters.get('period'),'upcoming');
});

test('una ronda de contacto vence exactamente en su plazo y no inventa vencimientos ausentes',()=>{
  const now=Date.parse('2026-11-21T12:00:00Z');
  assert.equal(contactExpired({expires_at:'2026-11-21T12:00:00Z'},now),true);
  assert.equal(contactExpired({expires_at:'2026-11-21T12:00:01Z'},now),false);
  assert.equal(contactExpired({expires_at:null},now),false);
});

test('la barra de filtros ofrece búsqueda, estado y período sin enviar mientras se escribe',()=>{
  const html=renderToStaticMarkup(React.createElement(ListFilters,{value:emptyFilters,states:eventStates,onApply(){}}));
  assert.match(html,/type="search"/); assert.match(html,/maxLength="120"/);
  assert.match(html,/Todos los estados/); assert.match(html,/Próximas/); assert.match(html,/Limpiar filtros/);
});

test('las notificaciones permiten abrir una página anterior a los últimos treinta avisos',async()=>{
  const calls=[];
  await mount(url=>{
    calls.push(url); const page=new URL('http://localhost'+url).searchParams.get('page');
    return Response.json({page:Number(page),page_size:30,total:31,unread:31,results:[{id:Number(page),message:'Página '+page,target:'',read_at:null,created_at:'2026-11-21T12:00:00Z'}]});
  });
  await click('Siguiente');
  assert.match(host.textContent,/Página 2 de 2/);
  assert.match(host.textContent,/Página 2/);
  assert.ok(calls.some(url=>url.includes('page=2')));
  await click('Anterior'); assert.match(host.textContent,/Página 1 de 2/);
});

test('marcar un aviso envía solo su ID y actualiza el contador del encabezado',async()=>{
  const writes=[],counts=[];
  await mount((url,options)=>{
    const body=options?.body ? JSON.parse(options.body) : null;
    if(body) writes.push(body);
    return Response.json({page:1,total:1,unread:body?0:1,results:[{id:17,message:'Aviso propio',target:'',read_at:body?'2026-11-21T12:00:00Z':null,created_at:'2026-11-21T12:00:00Z'}]});
  },{onUpdate:result=>counts.push(result.unread)});
  await click('Marcar leída');
  assert.deepEqual(writes,[{read_id:17}]); assert.deepEqual(counts,[1,0]);
  assert.match(host.textContent,/0 sin leer/);
  assert.equal([...host.querySelectorAll('button')].some(node=>node.textContent==='Marcar leída'),false);
});

test('el fallo de carga conserva el mensaje de error y permite volver a intentar',async()=>{
  let fail=true;
  await mount(()=>fail ? Response.json({detail:'No se pudo cargar.'},{status:503}) : Response.json({unread:0,total:0,page:1,results:[]}));
  assert.match(host.querySelector('[role="alert"]').textContent,/No se pudo cargar/);
  fail=false; await click('Actualizar');
  assert.equal(host.querySelector('[role="alert"]'),null);
  assert.match(host.textContent,/No tienes notificaciones/);
});
