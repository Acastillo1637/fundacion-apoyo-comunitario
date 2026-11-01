import { useEffect, useState } from 'react';
import { ArrowRight, Award, CalendarDays, Check, ChevronRight, Clock3, FileCheck2, HeartHandshake, LayoutDashboard, MapPin, Settings2, UserRound, Users } from 'lucide-react';
import { api } from '../api';
import Qualifications from './Qualifications';
import Availability from './Availability';
import Documents, { DocumentReviewQueue } from './Documents';
import Operations from '../activities/Operations';
import PublicEvents from '../activities/PublicEvents';
import UserManagement, { VolunteerOnboarding } from '../accounts/UserManagement';
import '../accounts/styles.css';
import RequesterPortal from '../accounts/RequesterPortal';
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

export default function Dashboard({ user, setUser, initialPortal, initialTab }) {
  const portals = user.available_portals || [];
  const [selectedPortal, setPortal] = useState(initialPortal || portals[0]);
  const portal = portals.includes(selectedPortal) ? selectedPortal : portals[0];
  const [selectedTab, setTab] = useState(initialTab || '');
  const baseNavigation = portal === 'volunteer' ? (user.has_volunteer_profile ? tabs : [{ id: 'onboarding', label: 'Incorporación como voluntario', icon: UserRound }])
    : portal === 'requester' ? [
      { id: 'requester-overview', label: 'Resumen del solicitante', icon: LayoutDashboard },
      { id: 'requester-profile', label: 'Persona o entidad', icon: UserRound },
      ...(user.has_requester_profile ? [{ id: 'my-requests', label: 'Mis solicitudes', icon: FileCheck2 }, { id: 'new-request', label: 'Nueva solicitud', icon: CalendarDays }] : []),
    ] : [
      { id: 'staff-overview', label: 'Resumen', icon: LayoutDashboard },
      { id: 'staff-profile', label: 'Mi cuenta', icon: UserRound },
      ...(portal === 'administration' && user.can_manage_users ? [{ id: 'users', label: 'Administrar usuarios', icon: Users }] : []),
      ...(portal === 'operations' && user.can_manage_activities ? [{ id: 'operations', label: 'Solicitudes y eventos', icon: CalendarDays }] : []),
      ...(portal === 'operations' && user.can_manage_activities ? [{ id: 'participants', label: 'Participantes y asistencia', icon: Users }, { id: 'directory', label: 'Voluntarios', icon: UserRound }] : []),
      ...(portal === 'administration' && user.can_manage_catalogs ? [{ id: 'catalogs', label: 'Catálogos', icon: Award }] : []),
      ...(portal === 'operations' && user.can_review_documents ? [{ id: 'document-review', label: 'Revisión documental', icon: FileCheck2 }] : []),
    ];
  const navigation = [...baseNavigation, { id: 'notifications', label: 'Notificaciones', icon: FileCheck2 }];
  const tab = navigation.some(item => item.id === selectedTab) ? selectedTab : navigation[0]?.id;
  if (!portal) return <section className="wrap panel"><h1>Cuenta sin espacio asignado</h1><p>Solicita al administrador que revise tus roles de acceso.</p></section>;
  return <div className="app-layout"><aside className="sidebar">
    <span className="eyebrow">{portalNames[portal]}</span>
    {portals.length > 1 && <label className="field">Cambiar de espacio<select value={portal} onChange={event => { setPortal(event.target.value); setTab(''); }}>{portals.map(value => <option key={value} value={value}>{portalNames[value]}</option>)}</select></label>}
    {navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${tab === id ? 'active' : ''}`} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><Icon size={18}/>{label}</button>)}
    <div className="sidebar-note"><HeartHandshake size={25}/><strong>{portalNames[portal]}</strong><p>{portal === 'volunteer' ? 'Comparte tus habilidades y disponibilidad.' : portal === 'requester' ? 'Gestiona las necesidades de tu persona o entidad.' : 'Coordina la comunidad con los permisos de tu cuenta.'}</p></div>
    <a className="nav-item" href="/accounts/2fa/"><Settings2 size={18}/>Seguridad de cuenta</a>
  </aside><section className="dashboard">
    <div className="breadcrumb">{portalNames[portal]} <ChevronRight size={14}/>{navigation.find(item => item.id === tab)?.label}</div>
    <div className="dashboard-heading"><div><span className="eyebrow">{portalNames[portal]}</span><h1>Hola, {user.first_name || 'bienvenido'}</h1></div></div>
    {portal === 'requester' && tab !== 'notifications' && <RequesterPortal key={portal} tab={tab} user={user} setUser={setUser} navigate={setTab}/>}
    {tab === 'staff-overview' && <><WorkspaceSummary portal={portal} navigate={setTab}/><section className="panel"><h2>{portalNames[portal]}</h2><p>{portal === 'administration' ? 'Administra cuentas y catálogos desde este espacio. Usa el selector para entrar a operaciones.' : 'Revisa solicitudes y documentos, coordina participantes y registra la asistencia.'}</p></section></>}
    {tab === 'staff-profile' && <StaffProfile user={user} setUser={setUser}/>}
    {tab === 'notifications' && <Notifications/>}
    {tab === 'catalogs' && user.can_manage_catalogs && <Catalogs/>}
    {tab === 'participants' && user.can_manage_activities && <Participants/>}
    {tab === 'directory' && user.can_manage_activities && <VolunteerDirectory/>}
    {portal === 'volunteer' && <>
      {tab === 'overview' && <><WorkspaceSummary portal="volunteer" navigate={setTab}/><Overview navigate={setTab}/></>}
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

function Overview({ navigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([api('profile/'), api('volunteer/qualifications/'), api('volunteer/availability/')])
      .then(([profile, qualifications, availability]) => setData({ profile, qualifications, availability }))
      .catch(err => setError(err.message));
  }, []);

  return <>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="welcome-banner">
      <div><span className="eyebrow">TU TIEMPO Y TUS HABILIDADES CUENTAN</span><h2>Ayudemos al equipo a conocerte.</h2><p>Actualiza lo que sabes hacer y los horarios en los que puedes participar.</p><button className="button primary" onClick={() => navigate('qualifications')}>Mis habilidades <ArrowRight size={17}/></button></div>
      <HeartHandshake className="banner-icon" size={105} strokeWidth={1}/>
    </div>
    {!data && !error && <p role="status">Cargando tu resumen…</p>}
    {data && <div className="dashboard-cards">
      <SummaryCard icon={<Award/>} title="Habilidades y profesiones" value={`${data.qualifications.skills.length} habilidades · ${data.qualifications.professions.length} profesiones`} text="Declaradas por ti; acreditación documental pendiente." onClick={() => navigate('qualifications')}/>
      <SummaryCard icon={<Clock3/>} title="Disponibilidad semanal" value={`${data.availability.slots.length} franjas registradas`} text={`${data.availability.unavailable_dates.length} fechas no disponibles. Horarios de Santiago.`} onClick={() => navigate('availability')}/>
      <SummaryCard icon={<MapPin/>} title="Tu comunidad" value={data.profile.commune || 'Agrega tu comuna'} text="Solo necesitamos tu zona aproximada para coordinar." onClick={() => navigate('profile')}/>
    </div>}
    <section className="panel"><h2>Explora las actividades abiertas</h2><p className="section-description">Consulta fechas, funciones y requisitos, postula y sigue tus invitaciones en Mis participaciones.</p><button className="button secondary" onClick={() => navigate('opportunities')}>Ver oportunidades <ArrowRight size={16}/></button></section>
  </>;
}

function SummaryCard({ icon, title, value, text, onClick }) {
  return <article className="panel info-card"><div className="info-label"><span>{title}</span>{icon}</div><h3>{value}</h3><p>{text}</p><button className="text-button card-link" onClick={onClick}>Actualizar <ArrowRight size={14}/></button></article>;
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
