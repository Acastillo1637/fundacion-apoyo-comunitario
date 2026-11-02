import { useEffect, useState } from 'react';
import { ArrowLeft, CalendarDays, Check, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '../api';
import { CalendarDays as ScheduleIcon, MessageSquare, MapPin, ShieldCheck } from 'lucide-react';

const requestLabels = { pending: 'Pendiente', in_review: 'En revisión', approved: 'Aprobada', rejected: 'Rechazada' };
const eventLabels = { draft: 'Borrador', open: 'Abierto', finished: 'Finalizado', cancelled: 'Cancelado' };

export default function Operations() {
  const [section, setSection] = useState('requests');
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [options, setOptions] = useState(null);
  const [mode, setMode] = useState('detail');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true); setError('');
    try {
      const [list, catalogs] = await Promise.all([
        api(`activities/operations/${section}/?page=${page}`), api('activities/operations/options/'),
      ]);
      setData(list); setOptions(catalogs);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { setSelected(null); setData(null); setMessage(''); load(); }, [section, page]);

  async function open(id) {
    setBusy(true); setError(''); setMode('detail'); setMessage('');
    try { setSelected(await api(`activities/operations/${section}/${id}/`)); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function transition(status, reason) {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api(`activities/operations/${section}/${selected.id}/transition/`, {
        method: 'POST', body: JSON.stringify({ status, reason, revision: selected.revision }),
      });
      setSelected(result);
      setMessage('Cambio de estado registrado.');
      setData(await api(`activities/operations/${section}/?page=${page}`));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveEvent(body) {
    setBusy(true); setError(''); setMessage('');
    try {
      const creating = section === 'requests';
      const url = creating ? `activities/operations/requests/${selected.id}/events/` : `activities/operations/events/${selected.id}/`;
      await api(url, { method: creating ? 'POST' : 'PUT', body: JSON.stringify(creating ? body : { ...body, revision: selected.revision }) });
      setSelected(null); setMode('detail'); setMessage(creating ? 'Evento creado como borrador. Puedes revisarlo y abrirlo en Eventos.' : 'Borrador actualizado.');
      await load();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <section className="operation-space">
    <div className="panel"><div className="panel-heading"><h2>Solicitudes y eventos</h2><button className="text-button" disabled={busy} onClick={() => { setSelected(null); load(); }}><RefreshCw size={15}/> Recargar</button></div><p className="section-description">La decisión y publicación corresponden al equipo. La información de contacto y la dirección exacta son privadas.</p><div className="operation-tabs"><button className={`button ${section === 'requests' ? 'primary' : 'secondary'}`} onClick={() => { setPage(1); setSection('requests'); }} disabled={busy}>Solicitudes</button><button className={`button ${section === 'events' ? 'primary' : 'secondary'}`} onClick={() => { setPage(1); setSection('events'); }} disabled={busy}>Eventos</button></div></div>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status" className="success">{message}</p>}
    {selected ? <div className={mode === 'editor' ? 'planning-wrapper' : 'panel'}><button className="text-button" disabled={busy} onClick={() => { setSelected(null); setMode('detail'); setError(''); }}><ArrowLeft size={16}/> Volver a la lista</button>
      {mode === 'editor' ? <EventEditor key={selected.id} source={selected} editing={section === 'events'} options={options} busy={busy} onSave={saveEvent}/> : section === 'requests' ? <RequestDetail item={selected} busy={busy} onTransition={transition} onCreate={() => setMode('editor')}/> : <EventDetail item={selected} busy={busy} onTransition={transition} onEdit={() => setMode('editor')}/>}
    </div> : <div className="panel">{busy && !data && <p role="status">Cargando…</p>}{data?.results.length === 0 && <div className="empty-state"><p>No hay registros en esta página.</p></div>}<div className="operation-list">{data?.results.map(item => <article className="operation-item" key={item.id}><div><span className="tag">{section === 'requests' ? requestLabels[item.status] : eventLabels[item.status]}</span><h3>{section === 'requests' ? item.organization || item.contact_name : item.title}</h3><p>{item.commune} · {item.date.split('-').reverse().join('/')} · {item.start_time}–{item.end_time}</p>{section === 'requests' && <small className="help">{item.email_verified ? 'Correo verificado' : 'Correo pendiente de verificación'}</small>}</div><button className="button secondary small" disabled={busy} onClick={() => open(item.id)}>Ver detalle</button></article>)}</div>{data && <div className="form-actions"><button className="button secondary" disabled={busy || page <= 1} onClick={() => setPage(current => current - 1)}>Anterior</button><span className="help">Página {page} · {data.total} registros</span><button className="button secondary" disabled={busy || page * 20 >= data.total} onClick={() => setPage(current => current + 1)}>Siguiente</button></div>}</div>}
  </section>;
}

function RequestDetail({ item, busy, onTransition, onCreate }) {
  const [reason, setReason] = useState('');
  return <><h2 className="detail-title">Solicitud de {item.contact_name}</h2><span className="tag">{requestLabels[item.status]}</span><dl className="detail-grid"><dt>Tipo</dt><dd>{{ person: 'Persona', company: 'Empresa', institution: 'Institución' }[item.requester_type]}</dd><dt>Organización</dt><dd>{item.organization || '—'}</dd><dt>Contacto privado</dt><dd>{item.email} · {item.phone}</dd><dt>Horario solicitado</dt><dd>{item.date} · {item.start_time}–{item.end_time} · Santiago</dd><dt>Dirección privada</dt><dd>{item.address}, {item.commune}</dd><dt>Voluntarios solicitados</dt><dd>{item.quantity}</dd><dt>Necesidad</dt><dd className="public-description">{item.description}</dd><dt>Habilidades</dt><dd>{item.skills.map(skill => skill.name).join(', ') || 'No especificadas'}</dd><dt>Observaciones</dt><dd className="public-description">{item.observations || 'Sin observaciones'}</dd></dl>
    {!item.email_verified && <div className="notice"><p>El correo no está verificado. No se puede aprobar todavía.</p></div>}
    <fieldset className="form-fieldset" disabled={busy}>
      {item.status === 'pending' && <button className="button primary" onClick={() => onTransition('in_review', '')}>Comenzar revisión</button>}
      {item.status === 'in_review' && <><label className="field">Justificación (obligatoria al rechazar)<textarea maxLength={1000} rows={3} value={reason} onChange={event => setReason(event.target.value)}/></label><div className="operation-tabs"><button className="button primary" disabled={!item.email_verified} onClick={() => onTransition('approved', reason)}><Check size={17}/> Aprobar solicitud</button><button className="button secondary" disabled={!reason.trim()} onClick={() => onTransition('rejected', reason)}>Rechazar</button></div></>}
      {item.status === 'approved' && <button className="button primary" onClick={onCreate}><Plus size={17}/> Crear evento</button>}
    </fieldset>
    <h3 className="form-section-title">Eventos relacionados</h3>{item.events.length ? <ul>{item.events.map(event => <li key={event.id}>{event.title} · {eventLabels[event.status]}</li>)}</ul> : <p className="help">Aún no se han creado eventos desde esta solicitud.</p>}
    <History rows={item.history} labels={requestLabels}/>
  </>;
}

function EventDetail({ item, busy, onTransition, onEdit }) {
  const [reason, setReason] = useState('');
  return <><h2 className="detail-title">{item.title}</h2><span className="tag">{eventLabels[item.status]}</span><p className="public-description">{item.public_description}</p><dl className="detail-grid"><dt>Fecha y horario</dt><dd>{item.date} · {item.start_time}–{item.end_time} · Santiago</dd><dt>Dirección privada</dt><dd>{item.address}, {item.commune}</dd><dt>Notas internas</dt><dd>{item.internal_notes || 'Sin notas'}</dd></dl><h3>Cupos por función</h3><ul className="position-list">{item.positions.map(position => <li key={position.id}><strong>{position.name}</strong> · {position.capacity} cupos<small>Habilidades: {position.required_skills.map(skill => skill.name).join(', ') || 'Sin requisitos específicos'}</small><small>Documentos: {[...new Map([...position.required_documents, ...position.inherited_documents].map(document => [document.id, document])).values()].map(document => document.name).join(', ') || 'Sin requisitos adicionales'}</small></li>)}</ul>
    <fieldset className="form-fieldset" disabled={busy}>
      {item.status === 'draft' && <div className="operation-tabs"><button className="button secondary" onClick={onEdit}>Editar borrador</button><button className="button primary" onClick={() => onTransition('open', '')}>Abrir convocatoria</button></div>}
      {item.status === 'open' && <button className="button primary" onClick={() => onTransition('finished', '')}>Finalizar actividad</button>}
      {['draft', 'open'].includes(item.status) && <><label className="field">Motivo de cancelación<textarea maxLength={1000} rows={2} value={reason} onChange={event => setReason(event.target.value)}/></label><button className="button secondary" disabled={!reason.trim()} onClick={() => onTransition('cancelled', reason)}>Cancelar actividad</button></>}
    </fieldset><History rows={item.history} labels={eventLabels}/>
  </>;
}

function History({ rows, labels }) {
  return <section className="history-section"><h3>Historial de estados</h3>{rows.length === 0 ? <p className="help">Sin cambios de estado.</p> : <ol>{rows.map((row, index) => <li key={index}><strong>{labels[row.from]} → {labels[row.to]}</strong><small>{new Date(row.at).toLocaleString('es-CL', { timeZone: 'America/Santiago' })}</small>{row.reason && <p>{row.reason}</p>}</li>)}</ol>}</section>;
}

function EventEditor({ source, editing, options, busy, onSave }) {
  const [preview, setPreview] = useState({ title: editing ? source.title : '', date: source.date, start_time: source.start_time, end_time: source.end_time, commune: source.commune });
  const [positions, setPositions] = useState(() => editing
    ? source.positions.map(position => ({ name: position.name, capacity: position.capacity, required_skills: position.required_skills.map(item => item.id), required_documents: position.required_documents.map(item => item.id) }))
    : [{ name: 'Apoyo general', capacity: source.quantity, required_skills: source.skills.filter(skill => options.skills.some(option => option.id === skill.id)).map(skill => skill.id), required_documents: [] }]);
  function change(index, field, value) { setPositions(current => current.map((position, at) => at === index ? { ...position, [field]: value } : position)); }
  function toggle(index, field, id) { const current = positions[index][field]; change(index, field, current.includes(id) ? current.filter(value => value !== id) : [...current, id]); }
  function submit(event) {
    event.preventDefault();
    onSave({ ...Object.fromEntries(new FormData(event.currentTarget)), positions });
  }
  return <form className="planning-form" onChange={event => setPreview(Object.fromEntries(new FormData(event.currentTarget)))} onSubmit={submit}><fieldset className="form-fieldset" disabled={busy}>
    <div className="panel"><span className="eyebrow">PLANIFICACIÓN DE VOLUNTARIADO</span><h2 className="detail-title">{editing ? 'Editar borrador de convocatoria' : 'Nueva planificación y convocatoria'}</h2><p>Configura el horario, las funciones y los requisitos antes de publicar.</p></div>
    <div className="request-stepper planning-stepper">{['Información', 'Funciones y cupos', 'Requisitos', 'Coordinación'].map((label, index) => <span key={label}><b>{index + 1}</b>{label}</span>)}</div>
    <div className="planning-layout"><div className="planning-content"><section className="panel"><h3><span>1</span> Información general de la actividad</h3>
    <label className="field">Título público<input name="title" defaultValue={editing ? source.title : ''} maxLength={150} required/></label>
    <label className="field">Descripción pública revisada<textarea name="public_description" defaultValue={editing ? source.public_description : ''} minLength={20} maxLength={2000} rows={4} required/></label><p className="help">No copies datos de contacto, dirección exacta ni información sensible de beneficiarios.</p>
    <div className="form-row"><label className="field">Fecha<input name="date" type="date" defaultValue={source.date} required/></label><label className="field">Comuna<input name="commune" defaultValue={source.commune} maxLength={80} required/></label></div>
    <div className="form-row"><label className="field">Inicio<input name="start_time" type="time" step={60} defaultValue={source.start_time} required/></label><label className="field">Término<input name="end_time" type="time" step={60} defaultValue={source.end_time} required/></label></div><p className="help">Hora de Santiago. Inicio y término dentro del mismo día.</p>
    <label className="field">Dirección privada<input name="address" defaultValue={source.address} maxLength={250} required/></label>
    <label className="field">Notas internas<textarea name="internal_notes" defaultValue={editing ? source.internal_notes : ''} maxLength={1500} rows={2}/></label>
    </section><section className="panel"><h3 className="form-section-title"><span>2</span> Funciones, cupos y requisitos</h3><p className="help">Hasta 20 funciones y 500 cupos en total. Los requisitos documentales de las habilidades también se considerarán al evaluar a los candidatos.</p>
    {positions.map((position, index) => <section className="position-editor" key={index}><div className="form-row"><label className="field">Nombre de la función<input required value={position.name} maxLength={100} onChange={event => change(index, 'name', event.target.value)}/></label><label className="field">Cupos<input required type="number" min={1} max={500} value={position.capacity} onChange={event => change(index, 'capacity', event.target.value === '' ? '' : Number(event.target.value))}/></label></div>
      <fieldset className="catalog-section"><legend>Habilidades obligatorias</legend><Choices options={options.skills} selected={position.required_skills} onToggle={id => toggle(index, 'required_skills', id)}/></fieldset>
      <fieldset className="catalog-section"><legend>Documentos adicionales</legend><Choices options={options.documents} selected={position.required_documents} onToggle={id => toggle(index, 'required_documents', id)}/></fieldset>
      <button className="text-button" type="button" disabled={positions.length <= 1} onClick={() => setPositions(current => current.filter((_, at) => at !== index))}><Trash2 size={15}/> Quitar función</button>
    </section>)}
    <button className="button secondary" type="button" disabled={positions.length >= 20} onClick={() => setPositions(current => [...current, { name: '', capacity: 1, required_skills: [], required_documents: [] }])}><Plus size={16}/> Agregar función</button>
    </section><section className="panel"><h3><span>3</span> Coordinación de la convocatoria</h3><p>Al abrir la convocatoria, los voluntarios podrán postular desde su espacio. La coordinación revisa los candidatos y confirma los cupos.</p><div className="notice"><ShieldCheck size={20}/><p>Las invitaciones vencen en 48 horas o al inicio de la actividad. El contacto por WhatsApp es manual y requiere autorización del voluntario.</p></div></section></div><aside className="planning-side"><section className="panel"><h3><MessageSquare size={19}/> Vista previa de convocatoria</h3><span className="tag">Información para el voluntario</span><div className="phone-preview"><div className="phone-header"><strong>Fundación Apoyo Comunitario</strong></div><div className="phone-conversation"><div className="message-bubble"><span className="eyebrow">NUEVA OPORTUNIDAD</span><h3>{preview.title || 'Título de la actividad'}</h3><p><ScheduleIcon size={14}/>{preview.date || 'Fecha por definir'} · {preview.start_time}–{preview.end_time}</p><p><MapPin size={14}/>{preview.commune || 'Comuna por definir'}</p><p>Revisa los requisitos y confirma tu disponibilidad desde tu espacio.</p></div></div></div></section><section className="panel"><h3>Resumen de la convocatoria</h3><div className="planning-summary-row"><span>Funciones</span><strong>{positions.length}</strong></div><div className="planning-summary-row"><span>Cupos definidos</span><strong>{positions.reduce((total, item) => total + Number(item.capacity || 0), 0)}</strong></div><div className="planning-summary-row"><span>Estado al guardar</span><strong>Borrador</strong></div><p className="help">La publicación y el envío de invitaciones son acciones posteriores del equipo.</p></section></aside></div>
    <div className="form-actions"><span className="help">Total: {positions.reduce((total, item) => total + Number(item.capacity || 0), 0)} cupos.</span><button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar borrador'}</button></div>
  </fieldset></form>;
}

function Choices({ options, selected, onToggle }) {
  const unavailable = selected.filter(id => !options.some(option => option.id === id));
  return <div className="request-skills">{options.map(option => <label key={option.id} className="checkbox"><input type="checkbox" checked={selected.includes(option.id)} onChange={() => onToggle(option.id)}/>{option.name}</label>)}{unavailable.map(id => <label className="checkbox" key={id}><input type="checkbox" checked onChange={() => onToggle(id)}/>Requisito desactivado #{id}: quítalo antes de guardar.</label>)}{options.length === 0 && unavailable.length === 0 && <p className="help">No hay opciones activas.</p>}</div>;
}
