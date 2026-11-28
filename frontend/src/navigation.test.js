import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

let vite,AccountMenu,App,SessionScreen,HelpNavigation,dom,host,root;
before(async()=>{
  dom=new JSDOM('<div id="test-root"></div>',{url:'http://localhost/notificaciones',pretendToBeVisual:true});
  globalThis.window=dom.window;globalThis.document=dom.window.document;
  globalThis.HTMLElement=dom.window.HTMLElement;
  globalThis.requestAnimationFrame=dom.window.requestAnimationFrame.bind(dom.window);
  globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  vite=await createServer({server:{middlewareMode:true,hmr:{port:24681}},appType:'custom'});
  AccountMenu=(await vite.ssrLoadModule('/src/accounts/AccountMenu.jsx')).default;
  HelpNavigation=(await vite.ssrLoadModule('/src/volunteers/Dashboard.jsx')).HelpNavigation;
  const app=await vite.ssrLoadModule('/src/App.jsx');App=app.default;SessionScreen=app.SessionScreen;
  host=document.querySelector('#test-root');
});
after(async()=>{await vite?.close();dom?.window.close();});
const user={id:'demo',first_name:'Persona',last_name:'Prueba',email:'demo@example.org',roles:['Voluntario'],available_portals:['volunteer'],has_volunteer_profile:true};
async function renderMenu(props={}){
  if(root)await act(()=>root.unmount());
  root=createRoot(host);
  await act(()=>root.render(React.createElement(AccountMenu,{user,role:'Voluntario',...props})));
}
async function event(node,type,values={}){
  await act(()=>{
    const e=new dom.window.Event(type,{bubbles:true});
    Object.entries(values).forEach(([key,value])=>Object.defineProperty(e,key,{value}));
    node.dispatchEvent(e);
  });
}
test('F5 no presenta landing o dashboard mientras comprueba la sesión',()=>{
  const html=renderToStaticMarkup(React.createElement(MemoryRouter,{initialEntries:['/notificaciones']},React.createElement(App)));
  assert.match(html,/Comprobando tu sesión/);
  assert.doesNotMatch(html,/Centro de gestión|Conectamos necesidades|Cargando perfil/);
  assert.match(renderToStaticMarkup(React.createElement(SessionScreen,{signingOut:true})),/Cerrando tu sesión/);
});
test('el menú se abre con hover, se mantiene al entrar al panel y se cierra al salir',async()=>{
  await renderMenu();
  const trigger=host.querySelector('[aria-haspopup]');
  await event(trigger,'pointerover',{pointerType:'mouse',relatedTarget:null});
  assert.ok(host.querySelector('[role="menu"]'));
  await event(document.body,'keydown',{key:'Escape'});
  assert.equal(host.querySelector('[role="menu"]'),null);
  await event(trigger,'pointerover',{pointerType:'mouse',relatedTarget:null});
  assert.ok(host.querySelector('[role="menu"]'));
  const item=host.querySelector('[role="menuitem"]');
  await event(trigger,'pointerout',{pointerType:'mouse',relatedTarget:item});
  assert.ok(host.querySelector('[role="menu"]'));
  await event(item,'pointerout',{pointerType:'mouse',relatedTarget:document.body});
  assert.equal(host.querySelector('[role="menu"]'),null);
});
test('el menú permite clic táctil, Escape, navegación por teclado y ejecuta acciones',async()=>{
  let selected='';
  await renderMenu({onProfile:()=>selected='profile',onSecurity:()=>selected='security',onSignOut:()=>selected='logout'});
  const trigger=host.querySelector('[aria-haspopup]');
  await event(trigger,'pointerover',{pointerType:'touch'});await event(trigger,'click');
  assert.equal(trigger.getAttribute('aria-expanded'),'true');
  assert.match(host.textContent,/demo@example.org/);
  await event(trigger,'keydown',{key:'ArrowDown'});
  await new Promise(resolve=>requestAnimationFrame(resolve));
  assert.equal(document.activeElement.textContent,'Mi cuenta');
  await event(document.activeElement,'keydown',{key:'ArrowDown'});
  assert.equal(document.activeElement.textContent,'Seguridad de cuenta');
  await event(document.activeElement,'keydown',{key:'Escape'});
  assert.equal(host.querySelector('[role="menu"]'),null);
  assert.equal(document.activeElement,trigger);
  await event(trigger,'click');
  await event([...host.querySelectorAll('[role="menuitem"]')].find(node=>node.textContent==='Cerrar sesión'),'click');
  assert.equal(selected,'logout');assert.equal(host.querySelector('[role="menu"]'),null);
  await act(()=>root.unmount());root=null;
});

test('la caché de navegación no conserva el DOM privado y revalida la sesión antes de restaurarlo',async()=>{
  const original=globalThis.fetch;
  let checks=0,finishCheck;
  globalThis.fetch=async url=>{
    if(url==='/api/session/'){
      checks++;
      if(checks>1)return new Promise(resolve=>{finishCheck=()=>resolve(Response.json({user:null,csrf_token:'test'}));});
      return Response.json({user,foundation_name:'Fundación',csrf_token:'test'});
    }
    if(url==='/api/security/')return Response.json({email:user.email,email_verified:true,totp_enabled:false,mfa_enabled:false,recovery_remaining:0});
    return Response.json({unread:0,results:[]});
  };
  root=createRoot(host);
  try{
    await act(()=>root.render(React.createElement(MemoryRouter,{initialEntries:['/seguridad']},React.createElement(App))));
    assert.match(host.textContent,/Estado de seguridad/);
    await act(()=>window.dispatchEvent(new dom.window.PageTransitionEvent('pagehide',{persisted:true})));
    assert.match(host.textContent,/Comprobando tu sesión/);
    assert.doesNotMatch(host.textContent,/Estado de seguridad|demo@example.org/);
    await act(()=>window.dispatchEvent(new dom.window.PageTransitionEvent('pageshow',{persisted:true})));
    assert.match(host.textContent,/Comprobando tu sesión/);
    await act(()=>finishCheck());
    assert.match(host.textContent,/¡Hola de nuevo!/);
    assert.doesNotMatch(host.textContent,/Estado de seguridad/);
  }finally{await act(()=>root.unmount());root=null;globalThis.fetch=original;}
});


test('las tarjetas de ayuda del voluntario enlazan a participaciones, documentos y seguridad', async()=>{
  if(root)await act(()=>root.unmount());
  root=createRoot(host);
  const targets=[];
  await act(()=>root.render(React.createElement(HelpNavigation,{user,portal:'volunteer',navigate:tab=>targets.push(tab)})));
  const links=[...host.querySelectorAll('a.help-card')];
  assert.deepEqual(links.map(link=>link.getAttribute('href')),['/mis-participaciones','/documentos','/seguridad?espacio=volunteer']);
  for(const link of links)await act(()=>link.click());
  assert.deepEqual(targets,['participations','documents','security']);
  await act(()=>root.unmount());root=null;
});

test('ayuda ofrece solo secciones disponibles para el perfil actual',()=>{
  const html=renderToStaticMarkup(React.createElement(HelpNavigation,{user:{can_manage_activities:true},portal:'operations',navigate:()=>{}}));
  assert.match(html,/href="\/participantes"/);
  assert.doesNotMatch(html,/href="\/documentos"|href="\/revision-documental"/);
  const pending=renderToStaticMarkup(React.createElement(HelpNavigation,{user:{has_volunteer_profile:false},portal:'volunteer',navigate:()=>{}}));
  assert.match(pending,/href="\/incorporacion"/);
  assert.doesNotMatch(pending,/href="\/mis-participaciones"/);
});
