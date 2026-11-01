import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let server, Dashboard;
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
  Dashboard = (await server.ssrLoadModule('/src/volunteers/Dashboard.jsx')).default;
});
after(async () => { await server?.close(); });

function render(portal, changes = {}, extra = {}) {
  const user = { available_portals: [portal], first_name: 'Persona', last_name: 'Prueba', roles: [], has_volunteer_profile: true, has_requester_profile: true, ...changes };
  return renderToStaticMarkup(React.createElement(Dashboard, { user, setUser() {}, ...extra }));
}

test('el voluntario ve su participación y no las funciones administrativas', () => {
  const html = render('volunteer');
  assert.match(html, /Mis participaciones/);
  assert.match(html, /Disponibilidad/);
  assert.doesNotMatch(html, /Administrar usuarios|Participantes y asistencia|Persona o entidad/);
});

test('el solicitante ve su entidad y solicitudes sin perfil de voluntario', () => {
  const html = render('requester');
  assert.match(html, /Persona o entidad/);
  assert.match(html, /Mis solicitudes/);
  assert.doesNotMatch(html, /Disponibilidad|Mis documentos|Mis participaciones/);
});

test('secretaría ve coordinación y revisión sin gestión de cuentas', () => {
  const html = render('operations', { can_manage_activities: true, can_review_documents: true });
  assert.match(html, /Participantes y asistencia/);
  assert.match(html, /Revisión documental/);
  assert.doesNotMatch(html, /Administrar usuarios|Mis documentos/);
});

test('administración usa catálogos dentro de la web', () => {
  const html = render('administration', { can_manage_users: true, can_manage_catalogs: true });
  assert.match(html, /Administrar usuarios/);
  assert.match(html, /Catálogos/);
  assert.doesNotMatch(html, /href="\/admin\/volunteers\/"|Disponibilidad/);
});

test('notificaciones no renderiza simultáneamente el resumen', () => {
  const html = render('volunteer', {}, { initialTab: 'notifications' });
  assert.match(html, /Marcar leídas/);
  assert.doesNotMatch(html, /Ayudemos al equipo a conocerte/);
});

test('una cuenta con varios roles dispone de cambio explícito de espacio', () => {
  assert.match(render('volunteer', { available_portals: ['volunteer', 'requester'] }), /Cambiar de espacio/);
});
