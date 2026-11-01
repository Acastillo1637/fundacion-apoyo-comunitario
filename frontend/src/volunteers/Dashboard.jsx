import { useEffect, useState } from 'react';
import { ArrowRight, Award, CalendarDays, Check, ChevronRight, Clock3, FileCheck2, HeartHandshake, LayoutDashboard, MapPin, Settings2, UserRound } from 'lucide-react';
import { api } from '../api';
import Qualifications from './Qualifications';
import Availability from './Availability';
import Documents, { DocumentReviewQueue } from './Documents';

const tabs = [
  { id: 'overview', label: 'Resumen', icon: LayoutDashboard },
  { id: 'profile', label: 'Mi perfil', icon: UserRound },
  { id: 'qualifications', label: 'Habilidades y profesión', icon: Award },
  { id: 'availability', label: 'Disponibilidad', icon: Clock3 },
  { id: 'documents', label: 'Mis documentos', icon: FileCheck2 },
];

export default function Dashboard({ user, setUser }) {
  const [tab, setTab] = useState(user.can_review_documents ? 'document-review' : 'overview');
  return <div className="app-layout">
    <aside className="sidebar">
      <span className="eyebrow">MI VOLUNTARIADO</span>
      {[...tabs, ...(user.can_review_documents ? [{ id: 'document-review', label: 'Revisión documental', icon: FileCheck2 }] : [])].map(({ id, label, icon: Icon }) => <button
        key={id} className={`nav-item ${tab === id ? 'active' : ''}`}
        aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}
      ><Icon size={18}/>{label}</button>)}
      <div className="sidebar-note"><HeartHandshake size={25}/><strong>Tu aporte importa</strong><p>Cuéntanos qué puedes aportar y cuándo puedes participar.</p></div>
      {user.can_manage_catalogs && <a className="nav-item" href="/admin/volunteers/"><Award size={18}/>Administrar catálogos</a>}
      <a className="nav-item" href="/accounts/2fa/"><Settings2 size={18}/>Seguridad de cuenta</a>
    </aside>
    <section className="dashboard">
      <div className="breadcrumb">Mi espacio <ChevronRight size={14}/>{tabs.find(item => item.id === tab)?.label || 'Revisión documental'}</div>
      <div className="dashboard-heading">
        <div><span className="eyebrow">TU ESPACIO EN LA COMUNIDAD</span><h1>Hola, {user.first_name || 'bienvenido'} <span className="wave">✦</span></h1><p>Todo empieza con las ganas de ayudar.</p></div>
        <span className="pill"><Check size={14}/> Correo verificado</span>
      </div>
      {tab === 'overview' && <Overview navigate={setTab}/>}
      {tab === 'profile' && <Profile setUser={setUser}/>}
      {tab === 'qualifications' && <Qualifications/>}
      {tab === 'availability' && <Availability/>}
      {tab === 'documents' && <Documents/>}
      {tab === 'document-review' && user.can_review_documents && <DocumentReviewQueue/>}
    </section>
  </div>;
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
    <section className="panel"><div className="panel-heading"><h2>Próximas actividades</h2><span className="tag">En desarrollo</span></div><div className="upcoming"><CalendarDays size={32}/><div><h3>Estamos preparando las oportunidades</h3><p>Las actividades y las invitaciones se incorporarán en los próximos módulos.</p></div></div></section>
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
