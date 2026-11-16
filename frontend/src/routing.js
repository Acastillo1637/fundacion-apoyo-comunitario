// Canonical URLs for the existing screens. Only common screens retain a space.
export const publicPaths = { home:'/', login:'/iniciar-sesion', 'login-registered':'/iniciar-sesion', register:'/registro', 'register-requester':'/registro/solicitante', request:'/solicitar-apoyo', privacy:'/privacidad', 'verify-request':'/confirmar-solicitud' };
export const sections = {
  '/dashboard':{common:'overview'}, '/mi-cuenta':{common:'profile'}, '/seguridad':{common:'security'},
  '/seguridad/verificar-correo':{common:'security'}, '/notificaciones':{common:'notifications'},
  '/solicitudes-privacidad':{common:'privacy-requests'}, '/ayuda':{common:'help'},
  '/usuarios':{portal:'administration',tab:'users',permission:'can_manage_users'},
  '/catalogos':{portal:'administration',tab:'catalogs',permission:'can_manage_catalogs'},
  '/criterios-recomendacion':{portal:'administration',tab:'matching-settings',permission:'can_manage_users'},
  '/solicitudes-eventos':{portal:'operations',tab:'operations',permission:'can_manage_activities'},
  '/matching':{portal:'operations',tab:'matching',permission:'can_manage_activities'},
  '/participantes':{portal:'operations',tab:'participants',permission:'can_manage_activities'},
  '/voluntarios':{portal:'operations',tab:'directory',permission:'can_manage_activities'},
  '/revision-documental':{portal:'operations',tab:'document-review',permission:'can_review_documents'},
  '/habilidades':{portal:'volunteer',tab:'qualifications'}, '/disponibilidad':{portal:'volunteer',tab:'availability'},
  '/ubicacion':{portal:'volunteer',tab:'location'}, '/comunicacion':{portal:'volunteer',tab:'communication'},
  '/documentos':{portal:'volunteer',tab:'documents'}, '/oportunidades':{portal:'volunteer',tab:'opportunities'},
  '/mis-participaciones':{portal:'volunteer',tab:'participations'}, '/incorporacion':{portal:'volunteer',tab:'onboarding'},
  '/mis-solicitudes':{portal:'requester',tab:'my-requests'}, '/nueva-solicitud':{portal:'requester',tab:'new-request'},
};

export function normalizePath(path) { return path.length>1 ? path.replace(/\/+$/,'') : path; }
export function resolveWorkspace(user, pathname, search='') {
  const rule=sections[normalizePath(pathname)];
  if (!rule) return null;
  if (!user) return {authenticated:false,allowed:false};
  const query=new URLSearchParams(search), portals=user.available_portals || [];
  const requested=query.get('espacio');
  const portal=rule.portal || requested || portals[0] || 'account';
  const allowed=(portal==='account' && !portals.length || portals.includes(portal)) && (!rule.permission || user[rule.permission]);
  let tab=rule.tab || rule.common;
  if (tab==='overview') tab=portal==='volunteer' ? (user.has_volunteer_profile?'overview':'onboarding') : portal==='requester'?'requester-overview':'staff-overview';
  if (tab==='profile') tab=portal==='volunteer' ? (user.has_volunteer_profile?'profile':'onboarding') : portal==='requester'?'requester-profile':'staff-profile';
  const profileOnly=['qualifications','availability','location','communication','documents','opportunities','participations'];
  const eventId=query.get('evento');
  return {authenticated:true,allowed:Boolean(allowed && (!profileOnly.includes(tab) || user.has_volunteer_profile)),
    portal,tab,eventId: eventId && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(eventId)?eventId:null};
}

export function sectionURL(tab, portal, eventId=null) {
  const common=['overview','staff-overview','requester-overview'].includes(tab)?'/dashboard':
    ['profile','staff-profile','requester-profile'].includes(tab)?'/mi-cuenta':
    Object.entries(sections).find(([path,rule])=>rule.common===tab && path!=='/seguridad/verificar-correo')?.[0];
  const path=common || Object.entries(sections).find(([,rule])=>rule.tab===tab)?.[0];
  if (!path) return '/no-encontrado';
  const query=new URLSearchParams();
  if (common && portal && portal!=='account') query.set('espacio',portal);
  if (eventId && ['matching','participants'].includes(tab)) query.set('evento',eventId);
  return path+(query.size?'?'+query:'');
}

export function safeReturnTo(user, value) {
  if (typeof value!=='string' || !value.startsWith('/') || value.startsWith('//')) return '/dashboard';
  const url=new URL(value,'https://internal.invalid');
  return resolveWorkspace(user,url.pathname,url.search)?.allowed?url.pathname+url.search:'/dashboard';
}
