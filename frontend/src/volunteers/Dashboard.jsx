import { useCallback, useEffect, useState } from 'react';
import { Bell, Building2, CircleHelp, LogOut, Menu, Network, Search, ArrowRight, Award, CalendarDays, Check, ChevronRight, Clock3, FileCheck2, HeartHandshake, LayoutDashboard, MapPin, Settings2, UserRound, Users } from 'lucide-react';
import { api, readSnapshot } from '../api';
import { sectionURL } from '../routing';
import Qualifications from './Qualifications';
import Availability from './Availability';
import CommuneField from './CommuneField';
import WhatsAppPhoneField from './WhatsAppPhoneField';
import Documents, { DocumentReviewQueue } from './Documents';
import Operations from '../activities/Operations';
import PublicEvents from '../activities/PublicEvents';
import UserManagement, { VolunteerOnboarding } from '../accounts/UserManagement';
import '../accounts/styles.css';
import { FoundationLogo, slogan } from '../design/Brand';
import LocationSettings from '../maps/LocationSettings';
import MatchingConfiguration from '../activities/MatchingConfiguration';
import { CommunicationPreferences } from '../activities/Contacts';
import PrivacyRequests from '../accounts/PrivacyRequests';
import AccountMenu from '../accounts/AccountMenu';
import AccountSecurity from '../accounts/AccountSecurity';
import { ShieldCheck } from 'lucide-react';
import RequesterPortal from '../accounts/RequesterPortal';
import OperationalOverview, { Avatar, PageHeading } from '../design/Overview';
import VolunteerHome from '../design/VolunteerHome';
import Directory from '../design/Directory';
import Participants, { MyParticipations, Notifications } from '../activities/Participation';
import { Catalogs, StaffProfile, VolunteerDirectory, WorkspaceSummary } from '../accounts/Workspace';

const tabs = [
  { id: 'overview', label: 'Resumen', icon: LayoutDashboard },
  { id: 'profile', label: 'Mi perfil', icon: UserRound },
  { id: 'qualifications', label: 'Habilidades y profesión', icon: Award },
  { id: 'availability', label: 'Disponibilidad', icon: Clock3 },
  { id: 'location', label: 'Mi ubicación de referencia', icon: MapPin },
  { id: 'communication', label: 'Preferencias de comunicación', icon: Bell },
  { id: 'documents', label: 'Mis documentos', icon: FileCheck2 },
  { id: 'opportunities', label: 'Oportunidades', icon: CalendarDays },
  { id: 'participations', label: 'Mis participaciones', icon: Users },
];

const portalNames = { administration: 'Administración general', operations: 'Secretaría y operaciones', volunteer: 'Voluntario', requester: 'Solicitante de apoyo', account:'Cuenta' };

export default function Dashboard({ user, setUser, initialPortal, initialTab, foundation = 'Fundación Apoyo Comunitario', onPublic, onSignOut, route, onRoute, confirmationToken, clearConfirmationURL }) {
  const portals = user.available_portals || [];
  const [selectedPortal, setPortal] = useState(initialPortal || portals[0]);
  const portal = route?.portal || (portals.includes(selectedPortal) ? selectedPortal : portals[0]) || 'account';
  const [selectedTab, setTab] = useState(initialTab || '');
  const [mobileNav, setMobileNav] = useState(false), [sectionQuery, setSectionQuery] = useState(''), [unread, setUnread] = useState(0), [targetEvent, setTargetEvent] = useState(null);
  const baseNavigation = portal === 'volunteer' ? (user.has_volunteer_profile ? tabs : [{ id: 'onboarding', label: 'Incorporación como voluntario', icon: UserRound }])
    : portal === 'requester' ? [
      { id: 'requester-overview', label: 'Resumen del solicitante', icon: LayoutDashboard },
      { id: 'requester-profile', label: 'Persona o entidad', icon: UserRound },
      ...(user.has_requester_profile ? [{ id: 'my-requests', label: 'Mis solicitudes', icon: FileCheck2 }, { id: 'new-request', label: 'Nueva solicitud', icon: CalendarDays }] : []),
    ] : [
      { id: 'staff-overview', label: 'Dashboard general', icon: LayoutDashboard },
      { id: 'staff-profile', label: 'Mi cuenta', icon: UserRound },
      ...(portal === 'administration' && user.can_manage_users ? [{ id: 'users', label: 'Administrar usuarios', icon: Users }, { id: 'matching-settings', label: 'Criterios de recomendación', icon: Settings2 }] : []),
      ...(portal === 'operations' && user.can_manage_activities ? [{ id: 'operations', label: 'Solicitudes y eventos', icon: CalendarDays }, { id: 'matching', label: 'Matching y convocatoria', icon: Network }] : []),
      ...(portal === 'operations' && user.can_manage_activities ? [{ id: 'participants', label: 'Participantes y asistencia', icon: Users }, { id: 'directory', label: 'Voluntarios', icon: UserRound }] : []),
      ...(portal === 'administration' && user.can_manage_catalogs ? [{ id: 'catalogs', label: 'Catálogos', icon: Award }] : []),
      ...(portal === 'operations' && user.can_review_documents ? [{ id: 'document-review', label: 'Revisión documental', icon: FileCheck2 }] : []),
    ];
  const navigation = [...baseNavigation, { id: 'notifications', label: 'Notificaciones', icon: Bell }, { id:'privacy-requests',label:'Solicitudes de privacidad',icon:ShieldCheck }, { id: 'help', label: 'Ayuda y coordinación', icon: CircleHelp }];
  const tab = route?.tab || (selectedTab === 'security' ? 'security' : navigation.some(item => item.id === selectedTab) ? selectedTab : navigation[0]?.id);
  const updateNotifications = useCallback(data => { setUnread(data.unread); }, []);
  useEffect(() => {
    let active = true;
    api('activities/notifications/').then(data => { if (active) updateNotifications(data); }).catch(() => {});
    return () => { active = false; };
  }, [portal, user.id, updateNotifications]);
  function navigate(target, eventId = null) {
    let nextPortal=portal;
    if(target==='privacy-requests' && user.can_manage_users && portals.includes('administration')) nextPortal='administration';
    if (['operations', 'participants', 'matching', 'document-review','directory'].includes(target) && portals.includes('operations')) nextPortal='operations';
    if (['users','catalogs','matching-settings'].includes(target) && portals.includes('administration')) nextPortal='administration';
    if (['my-requests','new-request','requester-profile'].includes(target) && portals.includes('requester')) nextPortal='requester';
    if (['documents','participations'].includes(target) && portals.includes('volunteer')) nextPortal='volunteer';
    setMobileNav(false);
    if(onRoute){onRoute(target,nextPortal,eventId);return;}
    setPortal(nextPortal);setTab(target);setTargetEvent(eventId);
  }
  if (!portal) return <section className="wrap panel"><h1>Cuenta sin espacio asignado</h1><p>Solicita al administrador que revise tus roles de acceso.</p></section>;
  return <div className="app-layout stitch-workspace"><aside className={`sidebar ${mobileNav ? 'is-open' : ''}`} aria-label="Navegación del espacio">
    <button className="workspace-brand" onClick={onPublic}><FoundationLogo/><span>{foundation}<small>{slogan}</small></span></button>
    <span className="workspace-status"><ShieldIcon/> Espacio de coordinación <span className="dot"/></span>
    <span className="eyebrow">{portalNames[portal]}</span>
    {portals.length > 1 && <label className="field portal-switch">Cambiar de espacio<select value={portal} onChange={event => { if(onRoute)onRoute('overview',event.target.value);else {setPortal(event.target.value);setTab('');} setMobileNav(false); }}>{portals.map(value => <option key={value} value={value}>{portalNames[value]}</option>)}</select></label>}
    {navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${tab === id ? 'active' : ''}`} aria-current={tab === id ? 'page' : undefined} onClick={() => navigate(id)}><Icon size={18}/>{label}</button>)}
    <div className="sidebar-note"><HeartHandshake size={23}/><strong>Personas que se unen.</strong><p>Comunidad, compromiso y tiempo para ayudar.</p><span className="sidebar-note-line"/></div>
  </aside><header className="workspace-topbar"><button className="icon-btn workspace-menu" aria-label="Abrir menú del espacio" aria-expanded={mobileNav} onClick={() => setMobileNav(!mobileNav)}><Menu size={22}/></button><span className="foundation-chip"><Building2 size={17}/>{foundation}</span><form className="workspace-search" onSubmit={event => { event.preventDefault(); const match = navigation.find(item => item.label.toLocaleLowerCase('es').includes(sectionQuery.toLocaleLowerCase('es'))); if (match) { navigate(match.id); setSectionQuery(''); } }}><Search size={16}/><input aria-label="Buscar sección" list="workspace-sections" placeholder="Ir a una sección…" value={sectionQuery} onChange={event => setSectionQuery(event.target.value)}/><datalist id="workspace-sections">{navigation.map(item => <option key={item.id} value={item.label}/>)}</datalist><button aria-label="Ir a la sección" type="submit"><ArrowRight size={15}/></button></form><div className="workspace-top-actions"><button className="icon-btn notification-button" aria-label={`Notificaciones: ${unread} sin leer`} onClick={() => navigate('notifications')}><Bell size={20}/>{unread > 0 && <span>{unread > 99 ? '99+' : unread}</span>}</button><button className="icon-btn" aria-label="Ayuda" onClick={() => navigate('help')}><CircleHelp size={20}/></button><AccountMenu user={user} role={portalNames[portal]} onProfile={() => navigate(portal === 'volunteer' ? (user.has_volunteer_profile ? 'profile' : 'onboarding') : portal === 'requester' ? 'requester-profile' : 'staff-profile')} onSecurity={()=>navigate('security')} onSignOut={onSignOut}/></div></header><section className="dashboard">
    {!['staff-overview', 'overview'].includes(tab) && <PageHeading eyebrow={portalNames[portal]} title={tab==='security'?'Seguridad de cuenta':navigation.find(item => item.id === tab)?.label || 'Mi espacio'} description={tab === 'matching' ? 'Encuentra personas con las habilidades, documentos y disponibilidad que necesita cada actividad.' : undefined}/>}
    {tab==='security'&&<AccountSecurity onUserChanged={setUser} confirmationToken={confirmationToken} clearConfirmationURL={clearConfirmationURL}/>}
    {tab === 'help' && <HelpNavigation user={user} portal={portal} navigate={navigate}/>}
    {portal === 'requester' && !['notifications', 'help','privacy-requests','security'].includes(tab) && <RequesterPortal key={portal} tab={tab} user={user} setUser={setUser} navigate={navigate}/>}
    {tab === 'staff-overview' && <OperationalOverview portal={portal} navigate={navigate} user={user}/>}
    {tab === 'staff-profile' && <StaffProfile user={user} setUser={setUser}/>}
    {tab === 'notifications' && <Notifications initialData={readSnapshot('activities/notifications/')} onUpdate={updateNotifications} onNavigate={navigate}/>}
    {tab === 'catalogs' && user.can_manage_catalogs && <Catalogs/>}
    {tab === 'matching-settings' && user.can_manage_users && <MatchingConfiguration/>}
    {tab === 'privacy-requests' && <PrivacyRequests admin={portal==='administration'&&user.can_manage_users}/>}
    {['participants', 'matching'].includes(tab) && user.can_manage_activities && <Participants key={`${tab}-${route?.eventId || targetEvent || ''}`} initialEventId={route?.eventId || targetEvent} mode={tab}/>}
    {tab === 'directory' && user.can_manage_activities && <Directory/>}
    {portal === 'volunteer' && <>
      {tab === 'overview' && <VolunteerHome user={user} navigate={navigate}/>}
      {tab === 'onboarding' && <VolunteerOnboarding onComplete={updated => { setUser(updated); navigate('overview'); }}/>}
      {tab === 'profile' && <Profile setUser={setUser}/>}
      {tab === 'qualifications' && <Qualifications/>}
      {tab === 'availability' && <Availability/>}
      {tab === 'location' && <LocationSettings/>}
      {tab === 'communication' && <CommunicationPreferences/>}
      {tab === 'documents' && <Documents/>}
      {tab === 'opportunities' && <PublicEvents canApply/>}
      {tab === 'participations' && <MyParticipations/>}
    </>}
    {tab === 'document-review' && user.can_review_documents && <DocumentReviewQueue/>}
    {tab === 'operations' && user.can_manage_activities && <Operations/>}
    {tab === 'users' && user.can_manage_users && <UserManagement onSelfChanged={setUser}/>}
  </section></div>;
}

function Profile({ setUser }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api('profile/').then(setProfile).catch(err => setError(err.message)); }, []);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await api('profile/', { method: 'PATCH', body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))) });
      setProfile(result);
      setUser(result);
      setMessage('Tu perfil se actualizó correctamente.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <section className="panel profile-panel">
    <h2>Tu información</h2><p>Mantén tus datos actualizados para facilitar la coordinación.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="success" role="status">{message}</p>}
    {!profile && !error && <p role="status">Cargando tu perfil…</p>}
    {profile && <form onSubmit={save}><fieldset disabled={busy} className="form-fieldset">
      <div className="form-row"><label className="field">Nombre<input name="first_name" required autoComplete="given-name" defaultValue={profile.first_name} maxLength={80}/></label><label className="field">Apellido<input name="last_name" required autoComplete="family-name" defaultValue={profile.last_name} maxLength={80}/></label></div>
      <WhatsAppPhoneField defaultValue={profile.phone}/>
      <CommuneField initialValue={profile.commune}/>
      <button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar cambios'}<Check size={17}/></button>
    </fieldset></form>}
  </section>;
}

function ShieldIcon() { return <Check size={13}/>; }

export function HelpNavigation({ user, portal, navigate }) {
  const cards = [];
  if (portal === 'volunteer' && user.has_volunteer_profile) {
    cards.push({ tab:'participations', title:'Actividades e invitaciones', text:'Consulta fechas, requisitos y el estado de tus participaciones.', Icon:CalendarDays });
    cards.push({ tab:'documents', title:'Documentos privados', text:'Carga tus antecedentes y consulta las observaciones del equipo autorizado.', Icon:FileCheck2 });
  } else if (portal === 'volunteer') {
    cards.push({ tab:'onboarding', title:'Completa tu incorporación', text:'Confirma tus datos para habilitar tu perfil de voluntario.', Icon:UserRound });
  } else if (portal === 'requester' && user.has_requester_profile) {
    cards.push({ tab:'my-requests', title:'Mis solicitudes', text:'Consulta el estado de tus solicitudes de apoyo.', Icon:CalendarDays });
  } else if (portal === 'operations') {
    if (user.can_manage_activities) cards.push({ tab:'participants', title:'Actividades e invitaciones', text:'Gestiona participantes, invitaciones y asistencia.', Icon:CalendarDays });
    if (user.can_review_documents) cards.push({ tab:'document-review', title:'Revisión documental', text:'Revisa los documentos pendientes y registra tu decisión.', Icon:FileCheck2 });
  } else if (portal === 'administration') {
    if (user.can_manage_users) cards.push({ tab:'users', title:'Administrar usuarios', text:'Gestiona cuentas, perfiles y permisos.', Icon:Users });
    if (user.can_manage_catalogs) cards.push({ tab:'catalogs', title:'Catálogos y documentos', text:'Consulta los tipos documentales y requisitos de la fundación.', Icon:FileCheck2 });
  }
  cards.push({ tab:'security', title:'Acceso a tu cuenta', text:'Administra tu contraseña y la seguridad de tu cuenta.', Icon:Settings2 });
  return <section className="panel"><h2>Tu equipo y tu comunidad, en un mismo lugar</h2><p>Selecciona una tarjeta para ir a la sección correspondiente.</p><div className="stitch-help-grid">{cards.map(({ tab, title, text, Icon }) => <a key={tab} className="help-card" href={sectionURL(tab, portal)} onClick={event => { if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate(tab); } }}><Icon/><h3>{title}</h3><p>{text}</p><span className="text-button">Ir a la sección <ArrowRight size={15}/></span></a>)}</div></section>;
}
