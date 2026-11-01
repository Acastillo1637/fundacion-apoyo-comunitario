import { useEffect, useState } from 'react';
import { api } from '../api';

export const participationLabels = { applied: 'Postulación pendiente', invited: 'Invitación pendiente', confirmed: 'Confirmado', waitlisted: 'Lista de espera', declined: 'Invitación rechazada', cancelled: 'Cancelado', rejected: 'No seleccionado', expired: 'Invitación vencida' };
const formatDate = value => new Date(value).toLocaleString('es-CL', { timeZone: 'America/Santiago' });

export function MyParticipations() {
  const [data, setData] = useState(null), [page, setPage] = useState(1), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function load() { setError(''); try { setData(await api(`activities/participations/?page=${page}`)); } catch (err) { setError(err.message); } }
  useEffect(() => { load(); }, [page]);
  async function decide(item, action) {
    setBusy(true); setError('');
    try { await api(`activities/participations/${item.id}/decision/`, { method: 'POST', body: JSON.stringify({ revision: item.revision, action }) }); await load(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><div className="panel-heading"><h2>Mis participaciones e invitaciones</h2><button className="button secondary" onClick={load} disabled={busy}>Actualizar</button></div><p>Las invitaciones vencen en 48 horas o al inicio del evento. Los cupos se asignan al confirmar; si se completan, pasarás a lista de espera.</p>{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando participaciones…</p>}{data?.results.length === 0 && <p>Aún no tienes postulaciones o invitaciones. Revisa las oportunidades abiertas.</p>}{data?.results.map(item => <article className="panel" key={item.id}><span className="pill">{participationLabels[item.status]}</span><h3>{item.title}</h3><p>{item.position} · {formatDate(item.starts_at)} · {item.commune}</p>{item.address && <p>Dirección: {item.address}</p>}{item.event_status === 'cancelled' && <p className="error">El evento fue cancelado.</p>}{item.expires_at && item.status === 'invited' && <p>Responde antes de {formatDate(item.expires_at)}</p>}{item.attendance && <p>Asistencia: {item.attendance === 'present' ? 'Presente' : 'Ausente'}</p>}{item.event_status === 'open' && new Date(item.starts_at) > new Date() && <div className="actions">{item.status === 'invited' && <><button className="button primary" disabled={busy} onClick={() => decide(item, 'accept')}>Aceptar invitación</button><button className="button secondary" disabled={busy} onClick={() => decide(item, 'decline')}>Rechazar</button></>}{['applied', 'confirmed', 'waitlisted'].includes(item.status) && <button className="button secondary" disabled={busy} onClick={() => decide(item, 'withdraw')}>Retirar participación</button>}</div>}</article>)}<Pagination data={data} page={page} setPage={setPage}/></section>;
}

export function Notifications() {
  const [data, setData] = useState(null), [error, setError] = useState('');
  async function load(mark = false) { setError(''); try { setData(await api('activities/notifications/', mark ? { method: 'POST', body: JSON.stringify({ read_all: true }) } : {})); } catch (err) { setError(err.message); } }
  useEffect(() => { load(); }, []);
  return <section className="panel"><div className="panel-heading"><h2>Notificaciones {data ? `(${data.unread} sin leer)` : ''}</h2><div className="actions"><button className="button secondary" onClick={() => load()}>Actualizar</button><button className="button secondary" disabled={!data?.unread} onClick={() => load(true)}>Marcar leídas</button></div></div>{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando…</p>}{data?.results.length === 0 && <p>No tienes notificaciones.</p>}{data?.results.map(item => <article className="panel" key={item.id}><strong>{!item.read_at ? 'Nueva · ' : ''}{item.message}</strong><p className="help">{formatDate(item.created_at)}</p></article>)}</section>;
}

export default function Participants() {
  const [events, setEvents] = useState(null), [event, setEvent] = useState(null), [position, setPosition] = useState('');
  const [participants, setParticipants] = useState(null), [candidates, setCandidates] = useState(null), [page, setPage] = useState(1), [candidatePage, setCandidatePage] = useState(1);
  const [eventPage, setEventPage] = useState(1), [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { api(`activities/operations/events/?page=${eventPage}`).then(setEvents).catch(err => setError(err.message)); }, [eventPage]);
  async function open(id) {
    setBusy(true); setError('');
    try { const result = await api(`activities/operations/events/${id}/`); setEvent(result); setPosition(String(result.positions[0]?.id || '')); setPage(1); setCandidatePage(1); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function load() {
    if (!event) return;
    setError('');
    try { setParticipants(await api(`activities/operations/events/${event.id}/participants/?page=${page}`)); }
    catch (err) { setError(err.message); }
  }
  async function loadCandidates() {
    if (!event || !position) return;
    try { setCandidates(await api(`activities/operations/events/${event.id}/positions/${position}/candidates/?page=${candidatePage}`)); }
    catch (err) { setError(err.message); }
  }
  useEffect(() => { setParticipants(null); load(); }, [event?.id, page]);
  useEffect(() => { setCandidates(null); loadCandidates(); }, [event?.id, position, candidatePage]);
  async function invite(profileId) {
    setBusy(true); setError(''); setMessage('');
    try { await api(`activities/operations/events/${event.id}/participants/`, { method: 'POST', body: JSON.stringify({ profile_id: profileId, position_id: Number(position) }) }); setMessage('Invitación creada. La persona puede responder desde su cuenta.'); await load(); await loadCandidates(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function decide(item, action) {
    setBusy(true); setError(''); setMessage('');
    try { const result = await api(`activities/participations/${item.id}/decision/`, { method: 'POST', body: JSON.stringify({ revision: item.revision, action }) }); setMessage(`Participación actualizada: ${participationLabels[result.status]}.`); await load(); await loadCandidates(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Participantes, invitaciones y asistencia</h2>{error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}{!event ? <><p>Selecciona una actividad para revisar postulaciones y coordinar sus funciones.</p>{events?.results.map(item => <article className="panel" key={item.id}><h3>{item.title}</h3><p>{item.date} · {item.commune} · {item.status}</p><button className="button primary" disabled={busy} onClick={() => open(item.id)}>Administrar participantes</button></article>)}{events?.results.length === 0 && <p>Todavía no hay eventos.</p>}<Pagination data={events} page={eventPage} setPage={setEventPage}/></> : <><div className="panel-heading"><h3>{event.title}</h3><button className="button secondary" onClick={() => { setEvent(null); setError(''); setMessage(''); }}>Volver a eventos</button></div><p>La confirmación verifica requisitos, disponibilidad, cruces de horario y cupos. La lista de espera se confirma manualmente cuando se libera un cupo.</p><h3>Postulaciones y participantes</h3>{participants?.results.length === 0 && <p>Aún no hay participaciones.</p>}{participants?.results.map(item => <article className="panel" key={item.id}><strong>{item.name || item.email}</strong><p>{item.position} · {participationLabels[item.status]}{item.attendance && ` · ${item.attendance === 'present' ? 'Presente' : 'Ausente'}`}</p><div className="actions">{event.status === 'open' && new Date(item.starts_at) > new Date() && <>{['applied', 'waitlisted'].includes(item.status) && <><button className="button primary" disabled={busy || !item.eligible} onClick={() => decide(item, 'confirm')}>Confirmar cupo</button><button className="button secondary" disabled={busy} onClick={() => decide(item, 'reject')}>No seleccionar</button></>}{['applied', 'invited', 'confirmed', 'waitlisted'].includes(item.status) && <button className="button secondary" disabled={busy} onClick={() => decide(item, 'cancel')}>Cancelar participación</button>}{item.status === 'invited' && item.whatsapp_url && <a className="button secondary" href={item.whatsapp_url} target="_blank" rel="noreferrer">Preparar WhatsApp</a>}</>}{['open', 'finished'].includes(event.status) && item.status === 'confirmed' && new Date(item.starts_at) <= new Date() && <><button className="button secondary" disabled={busy} onClick={() => decide(item, 'present')}>Presente</button><button className="button secondary" disabled={busy} onClick={() => decide(item, 'absent')}>Ausente</button></>}</div></article>)}<Pagination data={participants} page={page} setPage={setPage}/>{event.status === 'open' && <><h3>Candidatos por función</h3><label className="field">Función<select value={position} onChange={e => { setPosition(e.target.value); setCandidatePage(1); }}>{event.positions.map(item => <option key={item.id} value={item.id}>{item.name} · {item.capacity} cupos</option>)}</select></label><p className="help">Proximidad aproximada: coincidencia de comuna, sin almacenar domicilios del voluntario.</p>{candidates?.results.map(item => <article className="panel" key={item.id}><strong>{item.name}</strong><p>{item.commune || 'Sin comuna'}{item.nearby && ' · Misma comuna'}</p><p>{item.eligible ? 'Cumple requisitos y disponibilidad' : item.reasons.join(' · ')}</p><button className="button primary" disabled={busy || !item.eligible || item.already_registered} onClick={() => invite(item.id)}>{item.already_registered ? 'Ya registrado' : 'Invitar'}</button></article>)}<Pagination data={candidates} page={candidatePage} setPage={setCandidatePage}/></>}</>}</section>;
}

export function Pagination({ data, page, setPage }) {
  if (!data || data.total <= 20) return null;
  return <div className="actions"><button className="button secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 20 >= data.total} onClick={() => setPage(page + 1)}>Siguiente</button></div>;
}
