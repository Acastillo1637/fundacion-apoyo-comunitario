import { useEffect, useState } from 'react';
import { ArrowRight, CalendarDays, ClipboardCheck, FileCheck2, MapPin, ShieldCheck, Users } from 'lucide-react';
import { api } from '../api';

const date = value => new Date(value).toLocaleString('es-CL', { timeZone: 'America/Santiago', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
const actionLabels = { 'account.login': 'Inicio de sesión', 'account.registered': 'Cuenta registrada', 'request.created': 'Solicitud recibida', 'request.approved': 'Solicitud aprobada', 'request.in_review': 'Solicitud en revisión', 'request.rejected': 'Solicitud rechazada', 'event.created': 'Evento planificado', 'event.open': 'Convocatoria publicada', 'event.cancelled': 'Actividad cancelada', 'event.finished': 'Actividad finalizada', 'participation.applied': 'Postulación recibida', 'participation.invited': 'Invitación registrada', 'participation.accept': 'Invitación aceptada', 'participation.confirm': 'Participación confirmada', 'participation.present': 'Asistencia registrada', 'catalog.updated': 'Catálogo actualizado' };

export function PageHeading({ eyebrow, title, description, children }) {
  return <div className="stitch-page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>{children && <div className="heading-actions">{children}</div>}</div>;
}

export function Avatar({ name = '', large = false }) {
  return <span className={`stitch-avatar ${large ? 'large' : ''}`} aria-hidden="true">{name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'AC'}</span>;
}

export default function OperationalOverview({ portal, navigate, user, snapshots }) {
  const [data, setData] = useState(snapshots?.[portal] || null), [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(true);
  useEffect(() => {
    let active = true;
    setData(snapshots?.[portal] || null); setError(''); setRefreshing(true);
    api(`workspace-summary/?portal=${portal}`).then(result => {
      if (!active) return;
      if (snapshots) snapshots[portal] = result;
      setData(result);
    }).catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setRefreshing(false); });
    return () => { active = false; };
  }, [portal, snapshots]);
  return <div className="operational-overview"><PageHeading eyebrow="CONSOLA CENTRAL · FUNDACIÓN APOYO COMUNITARIO" title={portal === 'administration' ? 'Centro de gestión y coordinación comunitaria' : 'Centro de operaciones y convocatorias'} description="Una vista de tus solicitudes, actividades y tareas de coordinación.">
    <span className="date-chip"><CalendarDays size={16}/>{new Date().toLocaleDateString('es-CL', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
    {user.can_manage_activities && <button className="button primary" onClick={() => navigate('operations')}><CalendarDays size={17}/> Planificar convocatoria</button>}
  </PageHeading>{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando el centro de operaciones…</p>}{data && refreshing && <p className="help" role="status">Actualizando datos…</p>}
    <div className="stitch-metrics">{data?.metrics.map((item, index) => <button className={`metric-card metric-${index % 4}`} key={item.label} onClick={() => navigate(item.target)}><span className="metric-name">{item.label}</span><span className="metric-icon">{index % 2 ? <ClipboardCheck size={23}/> : <Users size={23}/>}</span><strong>{item.value}</strong><span className="metric-link">Ver detalle <ArrowRight size={13}/></span></button>)}</div>
    {data && <div className="stitch-columns"><section className="overview-events"><div className="panel section-heading-inline"><div><h2><CalendarDays size={22}/> Próximas actividades y despliegue</h2><p>Convocatorias abiertas y cobertura de sus funciones.</p></div><span className="tag">{data.events.length} próximas</span></div>{data.events.length === 0 && <div className="panel empty-state"><CalendarDays size={30}/><h3>No hay actividades abiertas</h3><p>Las convocatorias publicadas aparecerán aquí para coordinar sus participantes.</p>{user.can_manage_activities && <button className="button secondary" onClick={() => navigate('operations')}>Revisar solicitudes</button>}</div>}{data.events.map(event => <article className="panel deployment-card" key={event.id}><span className="deployment-symbol"><Users size={28}/></span><div className="deployment-info"><small>{date(event.starts_at)}</small><h3>{event.title}</h3><p><MapPin size={14}/>{event.commune}</p></div><div className="deployment-coverage"><span>Confirmados: <strong>{event.confirmed}/{event.capacity}</strong></span><progress max={event.capacity || 1} value={event.confirmed}/><div><small>{event.backups || 0} respaldos · {event.waiting} en espera</small><button className="button secondary small" onClick={() => navigate('participants', event.id)}>Ver convocatoria</button></div></div></article>)}</section>
      <aside className="panel overview-validation"><h2><ShieldCheck size={21}/> Validaciones pendientes</h2>{data.reviews.length === 0 && <div className="empty-state"><FileCheck2 size={30}/><p>No tienes documentos pendientes en esta vista.</p></div>}{data.reviews.map(item => <article className="validation-preview" key={item.id}><span className="tag"><FileCheck2 size={13}/>{item.type_name}</span><h3>{item.name || 'Voluntario'}</h3><p>Recibido el {date(item.uploaded_at)}</p><button className="button primary small" onClick={() => navigate('document-review')}>Revisar documento</button></article>)}{user.can_review_documents && <button className="text-button" onClick={() => navigate('document-review')}>Ver cola de revisión <ArrowRight size={15}/></button>}</aside></div>}
    {data && <section className="panel audit-panel"><div className="panel-heading"><div><h2><ShieldCheck size={21}/> Trazabilidad y actividad reciente</h2><p>Registro de acciones realizadas en la plataforma.</p></div><span className="tag">Últimos {data.audit.length} registros</span></div><div className="table-scroll"><table className="stitch-table"><thead><tr><th>Fecha y hora</th><th>Responsable</th><th>Acción registrada</th><th>Referencia</th></tr></thead><tbody>{data.audit.map(item => <tr key={item.id}><td>{date(item.created_at)}</td><td><span className="table-person"><Avatar name={item.actor}/>{item.actor || 'Equipo de coordinación'}</span></td><td>{actionLabels[item.action] || item.action}</td><td><code>{item.resource || 'Cuenta'}</code></td></tr>)}</tbody></table>{data.audit.length === 0 && <p className="empty-state">Las acciones de coordinación aparecerán aquí a medida que uses la plataforma.</p>}</div></section>}
  </div>;
}
