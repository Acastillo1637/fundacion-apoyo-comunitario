import { useEffect, useState } from 'react';
import { CalendarDays, MapPin, Users } from 'lucide-react';
import { api } from '../api';

export default function PublicEvents() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  useEffect(() => {
    setError('');
    api(`activities/public-events/?page=${page}`).then(setData).catch(err => setError(err.message));
  }, [page]);
  return <section className="panel"><h2>Oportunidades de voluntariado</h2><p className="section-description">Actividades publicadas por el equipo. La postulación y las invitaciones se incorporarán en el siguiente módulo; esta lista no confirma participación.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {!data && !error && <p role="status">Cargando actividades…</p>}
    {data?.results.length === 0 && <div className="empty-state"><p>No hay actividades futuras abiertas por ahora.</p></div>}
    <div className="event-grid">{data?.results.map(event => <article className="event-card" key={event.id}><span className="tag">Convocatoria abierta</span><h3>{event.title}</h3><p className="public-description">{event.public_description}</p><p className="event-meta"><CalendarDays size={16}/>{event.date.split('-').reverse().join('/')} · {event.start_time}–{event.end_time}</p><p className="event-meta"><MapPin size={16}/>{event.commune}</p><p className="event-meta"><Users size={16}/>{event.capacity} cupos definidos por función</p><ul className="position-list">{event.positions.map(position => <li key={position.id}><strong>{position.name}</strong> · {position.capacity} cupos{position.required_skills.length > 0 && <small>Habilidades: {position.required_skills.map(item => item.name).join(', ')}</small>}{[...position.required_documents, ...position.inherited_documents].length > 0 && <small>Documentos: {[...new Map([...position.required_documents, ...position.inherited_documents].map(item => [item.id, item])).values()].map(item => item.name).join(', ')}</small>}</li>)}</ul></article>)}</div>
    {data && data.total > 20 && <div className="form-actions"><button className="button secondary" disabled={page <= 1} onClick={() => setPage(current => current - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 20 >= data.total} onClick={() => setPage(current => current + 1)}>Siguiente</button></div>}
  </section>;
}
