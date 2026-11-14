import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let server, CandidateScore, CandidateMap, PrivacyNotice, PrivacyRequests, FoundationLogo;
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 24680 } }, appType: 'custom' });
  const candidates = await server.ssrLoadModule('/src/activities/CandidateMap.jsx');
  CandidateScore = candidates.CandidateScore; CandidateMap = candidates.default;
  const privacy = await server.ssrLoadModule('/src/accounts/PrivacyRequests.jsx');
  PrivacyNotice = privacy.PrivacyNotice; PrivacyRequests = privacy.default;
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
  assert.match(html, /Descargar mis datos/);
  assert.match(html, /no borra automáticamente/);
  assert.doesNotMatch(html, /Rechazar con motivo/);
});
test('el logo conserva el recurso oficial y texto alternativo', () => {
  assert.match(render(FoundationLogo, {}), /brand\/fundacion-logo.png/);
  assert.match(render(FoundationLogo, {}), /Logo oficial/);
});
