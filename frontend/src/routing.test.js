import { test } from 'node:test';
import assert from 'node:assert/strict';
import { resolveWorkspace, safeReturnTo, sectionURL, sections } from './routing.js';

const staff={available_portals:['administration','operations','volunteer','requester'],has_volunteer_profile:true,has_requester_profile:true,
  can_manage_users:true,can_manage_catalogs:true,can_manage_activities:true,can_review_documents:true};
test('todas las secciones tienen URL propia y conservan su destino autorizado',()=>{
  for(const [path,rule] of Object.entries(sections)){
    const route=resolveWorkspace(staff,path);
    assert.equal(route.allowed,true,path);
    const generated=sectionURL(route.tab,route.portal);
    assert.ok(generated.startsWith('/'),path);
    const url=new URL(generated,'https://test.example');
    const actual=resolveWorkspace(staff,url.pathname,url.search);
    assert.equal(actual.tab,route.tab,path);
    assert.equal(actual.portal,route.portal,path);
  }
});
test('un voluntario no cae al dashboard si intenta abrir una sección administrativa',()=>{
  const user={available_portals:['volunteer'],has_volunteer_profile:true};
  assert.equal(resolveWorkspace(user,'/usuarios').allowed,false);
  assert.equal(resolveWorkspace(user,'/catalogos').allowed,false);
  assert.equal(resolveWorkspace(user,'/seguridad').allowed,true);
  assert.equal(resolveWorkspace(user,'/documentos').allowed,true);
  assert.equal(resolveWorkspace(user,'/no-existe'),null);
});
test('la URL conserva el espacio y el evento al abrir directamente y recargar',()=>{
  const id='e5b003b9-35c0-465f-ad46-a4d24c9c824f';
  const url=new URL(sectionURL('matching','operations',id),'https://test.example');
  assert.equal(resolveWorkspace(staff,url.pathname,url.search).eventId,id);
  const profile=new URL(sectionURL('profile','volunteer'),'https://test.example');
  assert.equal(resolveWorkspace(staff,profile.pathname,profile.search).tab,'profile');
  assert.equal(resolveWorkspace(staff,'/mi-cuenta','?espacio=unknown').allowed,false);
});
test('rutas privadas requieren sesión y el retorno nunca acepta destinos externos o prohibidos',()=>{
  assert.equal(resolveWorkspace(null,'/usuarios').authenticated,false);
  assert.equal(safeReturnTo(staff,'https://evil.example'),'/dashboard');
  assert.equal(safeReturnTo(staff,'//evil.example'),'/dashboard');
  assert.equal(safeReturnTo({available_portals:['volunteer']},'/usuarios'),'/dashboard');
  assert.equal(safeReturnTo(staff,'/matching?evento=e5b003b9-35c0-465f-ad46-a4d24c9c824f'),'/matching?evento=e5b003b9-35c0-465f-ad46-a4d24c9c824f');
});
test('un perfil incompleto solo permite sus pantallas correspondientes y seguridad',()=>{
  const user={available_portals:['volunteer'],has_volunteer_profile:false};
  assert.equal(resolveWorkspace(user,'/mi-cuenta').tab,'onboarding');
  assert.equal(resolveWorkspace(user,'/documentos').allowed,false);
  assert.equal(resolveWorkspace(user,'/seguridad').allowed,true);
});
