import { useEffect, useState } from 'react';
import { Bell, Building2, CircleHelp, LogOut, Menu, Network, Search, ArrowRight, Award, CalendarDays, Check, ChevronRight, Clock3, FileCheck2, HeartHandshake, LayoutDashboard, MapPin, Settings2, UserRound, Users } from 'lucide-react';
import { api } from '../api';
import Qualifications from './Qualifications';
import Availability from './Availability';
import Documents, { DocumentReviewQueue } from './Documents';
import Operations from '../activities/Operations';
import PublicEvents from '../activities/PublicEvents';
import UserManagement, { VolunteerOnboarding } from '../accounts/UserManagement';
import '../accounts/styles.css';
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
  { id: 'documents', label: 'Mis documentos', icon: FileCheck2 },
  { id: 'opportunities', label: 'Oportunidades', icon: CalendarDays },
  { id: 'participations', label: 'Mis participaciones', icon: Users },
];

const portalNames = { administration: 'Administración general', operations: 'Secretaría y operaciones', volunteer: 'Voluntariado', requester: 'Solicitante de apoyo' };

export default function Dashboard({ user, setUser, initialPortal, initialTab, foundation = 'Fundación Apoyo Comunitario', onPublic, onSignOut }) {
  const portals = user.available_portals || [];
  const [selectedPortal, setPortal] = useState(initialPortal || portals[0]);
  const portal = portals.includes(selectedPortal) ? selectedPortal : portals[0];
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
      ...(portal === 'administration' && user.can_manage_users ? [{ id: 'users', label: 'Administrar usuarios', icon: Users }] : []),
      ...(portal === 'operations' && user.can_manage_activities ? [{ id: 'operations', label: 'Solicitudes y eventos', icon: CalendarDays }, { id: 'matching', label: 'Matching y convocatoria', icon: Network }] : []),
      ...(portal === 'operations' && user.can_manage_activities ? [{ id: 'participants', label: 'Participantes y asistencia', icon: Users }, { id: 'directory', label: 'Voluntarios', icon: UserRound }] : []),
      ...(portal === 'administration' && user.can_manage_catalogs ? [{ id: 'catalogs', label: 'Catálogos', icon: Award }] : []),
      ...(portal === 'operations' && user.can_review_documents ? [{ id: 'document-review', label: 'Revisión documental', icon: FileCheck2 }] : []),
    ];
  const navigation = [...baseNavigation, { id: 'notifications', label: 'Notificaciones', icon: Bell }, { id: 'help', label: 'Ayuda y coordinación', icon: CircleHelp }];
  const tab = navigation.some(item => item.id === selectedTab) ? selectedTab : navigation[0]?.id;
  useEffect(() => { api('activities/notifications/').then(data => setUnread(data.unread)).catch(() => {}); }, [selectedTab, portal]);
  function navigate(target, eventId = null) {
    if (['operations', 'participants', 'matching', 'document-review'].includes(target) && portal === 'administration' && portals.includes('operations')) setPortal('operations');
    setTab(target); setTargetEvent(eventId); setMobileNav(false);
  }
  if (!portal) return <section className="wrap panel"><h1>Cuenta sin espacio asignado</h1><p>Solicita al administrador que revise tus roles de acceso.</p></section>;
  return <div className="app-layout stitch-workspace"><aside className={`sidebar ${mobileNav ? 'is-open' : ''}`} aria-label="Navegación del espacio">
    <button className="workspace-brand" onClick={onPublic}><span className="brand-icon"><HeartHandshake size={23}/></span><span>{foundation}<small>RED DE VOLUNTARIADO</small></span></button>
    <span className="workspace-status"><ShieldIcon/> Espacio de coordinación <span className="dot"/></span>
    <span className="eyebrow">{portalNames[portal]}</span>
    {portals.length > 1 && <label className="field portal-switch">Cambiar de espacio<select value={portal} onChange={event => { setPortal(event.target.value); setTab(''); setMobileNav(false); }}>{portals.map(value => <option key={value} value={value}>{portalNames[value]}</option>)}</select></label>}
    {navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${tab === id ? 'active' : ''}`} aria-current={tab === id ? 'page' : undefined} onClick={() => navigate(id)}><Icon size={18}/>{label}</button>)}
    <div className="sidebar-note"><HeartHandshake size={23}/><strong>Personas que se unen.</strong><p>Comunidad, compromiso y tiempo para ayudar.</p><span className="sidebar-note-line"/></div>
    <a className="nav-item" href="/accounts/2fa/"><Settings2 size={18}/>Seguridad de cuenta</a>
    {onSignOut && <button className="nav-item" onClick={onSignOut}><LogOut size={18}/>Cerrar sesión</button>}
  </aside><header className="workspace-topbar"><button className="icon-btn workspace-menu" aria-label="Abrir menú del espacio" aria-expanded={mobileNav} onClick={() => setMobileNav(!mobileNav)}><Menu size={22}/></button><span className="foundation-chip"><Building2 size={17}/>{foundation}</span><form className="workspace-search" onSubmit={event => { event.preventDefault(); const match = navigation.find(item => item.label.toLocaleLowerCase('es').includes(sectionQuery.toLocaleLowerCase('es'))); if (match) { navigate(match.id); setSectionQuery(''); } }}><Search size={16}/><input aria-label="Buscar sección" list="workspace-sections" placeholder="Ir a una sección…" value={sectionQuery} onChange={event => setSectionQuery(event.target.value)}/><datalist id="workspace-sections">{navigation.map(item => <option key={item.id} value={item.label}/>)}</datalist><button aria-label="Ir a la sección" type="submit"><ArrowRight size={15}/></button></form><div className="workspace-top-actions"><button className="icon-btn notification-button" aria-label={`Notificaciones: ${unread} sin leer`} onClick={() => navigate('notifications')}><Bell size={20}/>{unread > 0 && <span>{unread > 99 ? '99+' : unread}</span>}</button><button className="icon-btn" aria-label="Ayuda" onClick={() => navigate('help')}><CircleHelp size={20}/></button><button className="workspace-user" onClick={() => navigate(portal === 'volunteer' ? (user.has_volunteer_profile ? 'profile' : 'onboarding') : portal === 'requester' ? 'requester-profile' : 'staff-profile')}><span><strong>{user.first_name} {user.last_name}</strong><small>{portalNames[portal]}</small></span><Avatar name={`${user.first_name} ${user.last_name}`}/></button></div></header><section className="dashboard">
    {!['staff-overview', 'overview'].includes(tab) && <PageHeading eyebrow={portalNames[portal]} title={navigation.find(item => item.id === tab)?.label || 'Mi espacio'} description={tab === 'matching' ? 'Encuentra personas con las habilidades, documentos y disponibilidad que necesita cada actividad.' : undefined}/>}
    {tab === 'help' && <section className="panel"><h2>Tu equipo y tu comunidad, en un mismo lugar</h2><p>Usa el menú lateral para revisar tus tareas. Si tienes varios roles, cambia de espacio para acceder a sus funciones.</p><div className="stitch-help-grid"><article><CalendarDays/><h3>Actividades e invitaciones</h3><p>Consulta fechas y requisitos. Un cupo queda confirmado cuando tu participación cambia a Confirmado.</p></article><article><FileCheck2/><h3>Documentos privados</h3><p>Carga tus antecedentes y consulta las observaciones del equipo autorizado.</p></article><article><Settings2/><h3>Acceso a tu cuenta</h3><p>Puedes recuperar tu contraseña desde Iniciar sesión y configurar un segundo factor en Seguridad de cuenta.</p></article></div></section>}
    {portal === 'requester' && !['notifications', 'help'].includes(tab) && <RequesterPortal key={portal} tab={tab} user={user} setUser={setUser} navigate={setTab}/>}
    {tab === 'staff-overview' && <OperationalOverview portal={portal} navigate={navigate} user={user}/>}
    {tab === 'staff-profile' && <StaffProfile user={user} setUser={setUser}/>}
    {tab === 'notifications' && <Notifications/>}
    {tab === 'catalogs' && user.can_manage_catalogs && <Catalogs/>}
    {['participants', 'matching'].includes(tab) && user.can_manage_activities && <Participants key={`${tab}-${targetEvent || ''}`} initialEventId={targetEvent} mode={tab}/>}
    {tab === 'directory' && user.can_manage_activities && <Directory/>}
    {portal === 'volunteer' && <>
      {tab === 'overview' && <VolunteerHome user={user} navigate={navigate}/>}
      {tab === 'onboarding' && <VolunteerOnboarding onComplete={updated => { setUser(updated); setTab('overview'); }}/>}
      {tab === 'profile' && <Profile setUser={setUser}/>}
      {tab === 'qualifications' && <Qualifications/>}
      {tab === 'availability' && <Availability/>}
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
      <label className="field">Teléfono<input name="phone" autoComplete="tel" placeholder="+56 9 1234 5678" defaultValue={profile.phone} maxLength={20}/></label>
      <label className="field">Comuna<input name="commune" defaultValue={profile.commune} maxLength={80}/></label>
      <button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar cambios'}<Check size={17}/></button>
    </fieldset></form>}
  </section>;
}

function ShieldIcon() { return <Check size={13}/>; }
