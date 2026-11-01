import { useEffect, useState } from 'react';
import { api } from '../api';
import PublicRequest from '../activities/PublicRequest';
import { WorkspaceSummary } from './Workspace';

const types = { person: 'Persona natural', company: 'Empresa', institution: 'Institución' };
const statuses = { pending: 'Pendiente', in_review: 'En revisión', approved: 'Aprobada', rejected: 'Rechazada' };

export default function RequesterPortal({ tab, user, setUser, navigate }) {
  const [profile, setProfile] = useState(undefined);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [type, setType] = useState('person');
  useEffect(() => {
    api('requester/profile/').then(({ profile: data }) => { setProfile(data); setType(data?.requester_type || 'person'); }).catch(err => setError(err.message));
  }, []);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    const form = new FormData(event.currentTarget);
    const data = { ...Object.fromEntries(form), revision: profile?.revision || 0, adult: form.has('adult'), privacy: form.has('privacy'), authorized_representative: form.has('authorized_representative') };
    try {
      const result = await api('requester/profile/', { method: 'PUT', body: JSON.stringify(data) });
      setProfile(result); setUser(result); setMessage('Perfil de solicitante guardado.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  if (profile === undefined) return <p role={error ? 'alert' : 'status'}>{error || 'Cargando perfil de solicitante…'}</p>;
  if (profile && tab === 'new-request') return <PublicRequest requester={profile} navigate={() => navigate('my-requests')}/>;
  if (profile && tab === 'my-requests') return <OwnedRequests/>;
  if (profile && tab === 'requester-overview') return <><WorkspaceSummary portal="requester" navigate={navigate}/><section className="panel"><span className="eyebrow">{types[profile.requester_type]}</span><h2>{profile.organization || user.first_name}</h2><p>Representante o contacto: {profile.first_name} {profile.last_name}</p><p>Envía necesidades de apoyo y consulta su estado. La fundación evalúa cada solicitud antes de aprobarla.</p><div className="actions"><button className="button primary" onClick={() => navigate('new-request')}>Nueva solicitud</button><button className="button secondary" onClick={() => navigate('my-requests')}>Mis solicitudes</button></div></section></>;
  return <section className="panel profile-panel"><h2>{profile ? 'Perfil del solicitante' : 'Completa tu perfil de solicitante'}</h2><p>Registra tus datos de contacto y la entidad que representas. Cada cuenta representa a una persona o entidad.</p>
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}
    <form onSubmit={save}><fieldset className="form-fieldset" disabled={busy}>
      <label className="field">Tipo de solicitante<select name="requester_type" value={type} onChange={e => setType(e.target.value)}>{Object.entries(types).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {type !== 'person' && <label className="field">Nombre de la empresa o institución<input name="organization" defaultValue={profile?.organization || ''} maxLength={150} required/></label>}
      <div className="form-row"><label className="field">Nombre del contacto<input name="first_name" defaultValue={profile?.first_name || user.first_name} maxLength={80} required/></label><label className="field">Apellido<input name="last_name" defaultValue={profile?.last_name || user.last_name} maxLength={80} required/></label></div>
      <label className="field">Correo de la cuenta<input value={user.email} readOnly type="email"/></label>
      <div className="form-row"><label className="field">Teléfono<input name="phone" defaultValue={profile?.phone || ''} maxLength={20} required/></label><label className="field">Comuna<input name="commune" defaultValue={profile?.commune || ''} maxLength={80}/></label></div>
      <label className="checkbox"><input name="adult" type="checkbox" required/>Confirmo que tengo 18 años o más.</label>
      <label className="checkbox"><input name="privacy" type="checkbox" required/>Acepto el tratamiento de mis datos para gestionar la cuenta y sus solicitudes.</label>
      <p className="help">Entorno de desarrollo: usa datos ficticios. El aviso institucional definitivo está pendiente.</p>
      {type !== 'person' && <label className="checkbox"><input name="authorized_representative" type="checkbox" required/>Estoy autorizado para representar a esta entidad.</label>}
      <button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar perfil de solicitante'}</button>
    </fieldset></form></section>;
}

function OwnedRequests() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  useEffect(() => { setError(''); setData(null); api(`requester/requests/?page=${page}`).then(setData).catch(err => setError(err.message)); }, [page]);
  return <section className="panel"><h2>Mis solicitudes</h2><p>Solo aparecen las solicitudes enviadas desde esta cuenta. Las solicitudes públicas anteriores se mantienen separadas.</p>{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando solicitudes…</p>}{data?.results.length === 0 && <p>Todavía no has enviado solicitudes desde tu cuenta.</p>}{data?.results.map(item => <article className="panel" key={item.id}><span className="pill">{statuses[item.status] || item.status}</span><h3>{item.description}</h3><p>{new Date(item.starts_at).toLocaleString('es-CL', { timeZone: 'America/Santiago' })} · {item.commune} · {item.quantity} voluntarios</p><small>Referencia: {item.id}</small>{item.history.length > 0 && <ul>{item.history.map((entry, index) => <li key={index}>{statuses[entry.status]} · {new Date(entry.at).toLocaleDateString('es-CL')}</li>)}</ul>}</article>)}{data && <div className="actions"><button className="button secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 20 >= data.count} onClick={() => setPage(page + 1)}>Siguiente</button></div>}</section>;
}
