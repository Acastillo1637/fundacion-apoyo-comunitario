import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let server, CandidateScore, CandidateMap, PrivacyNotice, PrivacyRequests, FoundationLogo, Auth, candidatePoints;
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 24680 } }, appType: 'custom' });
  const candidates = await server.ssrLoadModule('/src/activities/CandidateMap.jsx');
  candidatePoints = candidates.candidatePoints;
  CandidateScore = candidates.CandidateScore; CandidateMap = candidates.default;
  const privacy = await server.ssrLoadModule('/src/accounts/PrivacyRequests.jsx');
  PrivacyNotice = privacy.PrivacyNotice; PrivacyRequests = privacy.default;
  Auth = (await server.ssrLoadModule('/src/design/Auth.jsx')).default;
  FoundationLogo = (await server.ssrLoadModule('/src/design/Brand.jsx')).FoundationLogo;
});
after(async () => { await server?.close(); });
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));

test('un perfil no elegible no presenta una puntuación de recomendación', () => {
  assert.equal(render(CandidateScore, { item: { eligible: false, score: 99 } }), '');
});
test('la puntuación distingue distancia geográfica de ruta y no promete un cupo', () => {
  const html = render(CandidateScore, { item: { eligible:true, score:85, distance_km:2.4, recommendation_reasons:['Habilidad coincidente'] } });
  assert.match(html, /2.4 km aprox. en línea recta/);
  assert.match(html, /ni asigna un cupo/);
  assert.match(html, /Habilidad coincidente/);
});
test('no inventa distancia cuando faltan coordenadas', () => {
  assert.match(render(CandidateScore, { item: { eligible:true, score:50, distance_km:null } }), /Sin distancia comparable/);
});
test('una actividad remota no monta el mapa de referencias personales', () => {
  const html = render(CandidateMap, { data: { event_location:{is_remote:true}, results:[] } });
  assert.match(html, /Actividad remota/);
  assert.doesNotMatch(html, /map-canvas/);
});
test('el aviso no inventa conservación y explica la bandeja para todos los administradores', () => {
  const html = render(PrivacyNotice, {});
  assert.match(html, /todos los administradores activos/);
  assert.match(html, /pendientes de aprobación/);
  assert.match(render(PrivacyNotice, {retentionNotice:'Plazo aprobado de prueba',development:false}), /Plazo aprobado de prueba/);
});
test('la bandeja propia no muestra controles de revisión administrativa ni eliminación automática', () => {
  const html = render(PrivacyRequests, {admin:false});
  assert.doesNotMatch(html, /Descargar mis datos|privacy\/export/);
  assert.match(html, /no borra automáticamente/);
  assert.doesNotMatch(html, /Rechazar con motivo/);
});
test('el logo conserva el recurso oficial y texto alternativo', () => {
  assert.match(render(FoundationLogo, {}), /brand\/fundacion-logo.png/);
  assert.match(render(FoundationLogo, {}), /Logo oficial/);
});


test('el registro no solicita verificar correo y el login presenta el éxito de creación', () => {
  const html=render(Auth,{mode:'register',brand:'Fundación',navigate(){},onLogin(){}});
  assert.doesNotMatch(html,/Verifica tu correo|Revisa tu correo|Activa tu acceso/);
  assert.match(html,/minLength="12"/);
  const login=render(Auth,{mode:'login',brand:'Fundación',notice:'Cuenta creada correctamente. Ya puedes iniciar sesión.',navigate(){},onLogin(){}});
  assert.match(login,/Cuenta creada correctamente/);
  assert.match(login,/Olvidaste tu contraseña/);
});


test('el mapa incluye puntos no elegibles al desactivar el filtro y no inventa ubicaciones', () => {
  const data={results:[
    {id:1,name:'Elegible',eligible:true,score:80,distance_km:2,location:{latitude:-33.45,longitude:-70.66}},
    {id:2,name:'Por revisar',eligible:false,score:null,distance_km:4,location:{latitude:-33.50,longitude:-70.70}},
    {id:3,name:'Sin ubicación',eligible:false,score:null,distance_km:null,location:null}],event_location:{latitude:-33.44,longitude:-70.65}};
  assert.deepEqual(candidatePoints(data).map(point=>point.id),[1,2,'event']);
  assert.deepEqual(candidatePoints(data,true).map(point=>point.id),[1,'event']);
  assert.match(candidatePoints(data)[1].label,/No elegible para esta función/);
  assert.doesNotMatch(candidatePoints(data)[1].label,/null\/100/);
  assert.deepEqual(candidatePoints({...data,event_location:{is_remote:true}}),[]);
});
