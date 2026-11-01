import { useEffect, useState } from 'react';
import { CalendarDays, MapPin, Users } from 'lucide-react';
import { api } from '../api';

export default function PublicEvents({ canApply = false }) {
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  useEffect(() => {
    setError('');
    api(`activities/public-events/?page=${page}`).then(setData).catch(err => setError(err.message));
  }, [page]);
  async function apply(positionId) {
    setBusy(true); setError(''); setMessage('');
    try { await api('activities/participations/', { method: 'POST', body: JSON.stringify({ position_id: positionId }) }); setMessage('Postulación recibida. Revisa Mis participaciones para seguir su estado.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Oportunidades de voluntariado</h2><p className="section-description">Actividades publicadas por el equipo. Revisa las funciones y sus requisitos. La postulación no confirma un cupo; el equipo coordina la selección desde tu cuenta.</p>
    {message && <p className="success" role="status">{message}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {!data && !error && <p role="status">Cargando actividades…</p>}
    {data?.results.length === 0 && <div className="empty-state"><p>No hay actividades futuras abiertas por ahora.</p></div>}
    <div className="event-grid">{data?.results.map(event => <article className="event-card" key={event.id}><span className="tag">Convocatoria abierta</span><h3>{event.title}</h3><p className="public-description">{event.public_description}</p><p className="event-meta"><CalendarDays size={16}/>{event.date.split('-').reverse().join('/')} · {event.start_time}–{event.end_time}</p><p className="event-meta"><MapPin size={16}/>{event.commune}</p><p className="event-meta"><Users size={16}/>{event.capacity} cupos definidos por función</p><ul className="position-list">{event.positions.map(position => <li key={position.id}><strong>{position.name}</strong> · {position.capacity} cupos{position.required_skills.length > 0 && <small>Habilidades: {position.required_skills.map(item => item.name).join(', ')}</small>}{[...position.required_documents, ...position.inherited_documents].length > 0 && <small>Documentos: {[...new Map([...position.required_documents, ...position.inherited_documents].map(item => [item.id, item])).values()].map(item => item.name).join(', ')}</small>}{canApply && <button className="button primary small" disabled={busy} onClick={() => apply(position.id)}>Postular a esta función</button>}</li>)}</ul></article>)}</div>
    {data && data.total > 20 && <div className="form-actions"><button className="button secondary" disabled={page <= 1} onClick={() => setPage(current => current - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 20 >= data.total} onClick={() => setPage(current => current + 1)}>Siguiente</button></div>}
  </section>;
}
