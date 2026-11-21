import { useEffect, useState } from 'react';
import { api } from '../api';
import { Pagination } from './Participation';

export const contactExpired = (item, now = Date.now()) => Boolean(item.expires_at && new Date(item.expires_at).getTime() <= now);

const labels = { pending_contact:'Pendiente de contacto', contact_started:'Contacto iniciado', sent:'Envío confirmado manualmente', accepted:'Respuesta aceptada', declined:'Rechazada', no_response:'Sin respuesta', cancelled:'Cancelada' };

export function ContactCandidateButton({ eventId, positionId, profileId, disabled, onChanged }) {
  const [url, setUrl] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function start() {
    setBusy(true); setError(''); setUrl('');
    try {
      const contact = await api(`activities/operations/events/${eventId}/contacts/`, { method:'POST', body:JSON.stringify({ profile_id:profileId, position_id:Number(positionId) }) });
      const result = await api(`activities/operations/contacts/${contact.id}/action/`, { method:'POST', body:JSON.stringify({ action:'start', revision:contact.revision }) });
      setUrl(result.whatsapp_url); onChanged?.();
      window.open(result.whatsapp_url, '_blank', 'noopener,noreferrer');
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <span className="contact-action"><button type="button" className="button secondary small" disabled={disabled || busy} onClick={start}>{busy ? 'Preparando…' : 'Contactar por WhatsApp'}</button>{url && <><a href={url} target="_blank" rel="noreferrer">Abrir WhatsApp si no se abrió</a><small>Intento registrado. El envío y la recepción no están confirmados.</small></>}{error && <span className="error" role="alert">{error}</span>}</span>;
}

export function GeneralWhatsappButton({ profileId }) {
  const [url, setUrl] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function start() {
    setBusy(true); setError('');
    try { const result = await api(`operations/volunteers/${profileId}/whatsapp/`, { method:'POST', body:'{}' }); setUrl(result.whatsapp_url); window.open(result.whatsapp_url, '_blank', 'noopener,noreferrer'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div><button className="button primary small" disabled={busy} onClick={start}>{busy ? 'Preparando…' : 'Contactar por WhatsApp'}</button>{url && <p><a href={url} target="_blank" rel="noreferrer">Abrir WhatsApp</a> · Intento registrado; revisa y envía manualmente.</p>}{error && <p role="alert" className="error">{error}</p>}</div>;
}

export default function Contacts({ eventId, refreshKey = 0, onChanged }) {
  const [data, setData] = useState(null), [page, setPage] = useState(1), [notes, setNotes] = useState({}), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function load() { try { setData(await api(`activities/operations/events/${eventId}/contacts/?page=${page}`)); } catch (err) { setError(err.message); } }
  useEffect(() => { setData(null); setError(''); load(); }, [eventId, page, refreshKey]);
  async function action(item, value) {
    if (!window.confirm(value === 'confirm' ? '¿Confirmas que el voluntario aceptó y autorizó registrar su participación? Se volverán a revisar requisitos y cupos.' : '¿Confirmas que esta actualización representa lo ocurrido? El sistema no verifica el envío ni la recepción en WhatsApp.')) return;
    setBusy(true); setError('');
    try { const result = await api(`activities/operations/contacts/${item.id}/action/`, { method:'POST', body:JSON.stringify({ action:value, revision:item.revision, note:notes[item.id] || '' }) });
      if (result.whatsapp_url) window.open(result.whatsapp_url, '_blank', 'noopener,noreferrer');
      await load(); onChanged?.();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel contact-history"><h2>Seguimiento de contactos e invitaciones</h2><p>Abrir un enlace solo registra un intento. Indica manualmente lo enviado y la respuesta; no copies conversaciones ni datos sensibles. Registrar aceptación no confirma un cupo hasta ejecutar “Confirmar participación”.</p>{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando seguimiento…</p>}{data?.results.length === 0 && <p>Aún no hay contactos de esta convocatoria.</p>}{data?.results.map(item => <article className="contact-row" key={item.id}><h3>{item.name} · {item.position}</h3><span className="tag">{labels[item.status]}</span>{item.expires_at && <p>Vence: {new Date(item.expires_at).toLocaleString('es-CL', {timeZone:'America/Santiago'})}</p>}{contactExpired(item) && <p className="notice">Esta ronda venció. Inicia una nueva ronda con una justificación antes de volver a contactar o confirmar.</p>}{item.participation_status && <p>Participación: {item.participation_status}</p>}<label className="field">Referencia de la actualización<input maxLength={500} value={notes[item.id] || ''} onChange={e => setNotes({ ...notes, [item.id]:e.target.value })} placeholder="Ej.: aceptación recibida el 14/11 por WhatsApp"/></label><div className="actions">{['pending_contact','contact_started','no_response'].includes(item.status) && <button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'start')}>Abrir WhatsApp y registrar intento</button>}{['cancelled','declined','no_response'].includes(item.status) || (item.expires_at && new Date(item.expires_at) <= new Date()) || (item.status === 'accepted' && ['cancelled','declined','rejected'].includes(item.participation_status)) ? <button className="button secondary small" disabled={busy} onClick={() => action(item,'reopen')}>Nueva ronda de contacto</button> : null}{['contact_started','sent','no_response'].includes(item.status) && <>{item.status !== 'sent' && <button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'sent')}>Registrar envío manual</button>}<button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'accepted')}>Registrar aceptación</button><button className="button secondary small" disabled={busy} onClick={() => action(item,'declined')}>Registrar rechazo</button>{item.status !== 'no_response' && <button className="button secondary small" disabled={busy} onClick={() => action(item,'no_response')}>Sin respuesta</button>}</>}{item.status === 'accepted' && <button className="button primary small" disabled={busy || contactExpired(item) || item.participation_status === 'confirmed'} onClick={() => action(item,'confirm')}>Confirmar participación</button>}{!['cancelled','declined'].includes(item.status) && <button className="text-button" disabled={busy} onClick={() => action(item,'cancelled')}>Cancelar seguimiento</button>}</div><details><summary>Historial de contacto</summary>{item.history.map((row,index) => <p key={index}>{new Date(row.at).toLocaleString('es-CL')} · {row.actor} · {row.action} · {row.note || labels[row.to]}</p>)}</details></article>)}<Pagination data={data} page={page} setPage={setPage}/></section>;
}

export function CommunicationPreferences() {
  const [data,setData] = useState(null), [error,setError] = useState(''), [message,setMessage] = useState(''), [busy,setBusy] = useState(false);
  useEffect(() => { api('volunteer/contact-preferences/').then(setData).catch(e => setError(e.message)); }, []);
  async function save(e) { e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const { consent_at, ...values } = data; setData(await api('volunteer/contact-preferences/', { method:'PUT', body:JSON.stringify(values) })); setMessage('Preferencias guardadas. Puedes retirar tu autorización en cualquier momento.'); }
    catch(err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Preferencias de comunicación</h2>{error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}{data && <form onSubmit={save}><label className="field">Teléfono internacional<input maxLength={20} value={data.phone} onChange={e => setData({ ...data, phone:e.target.value })} placeholder="+56 9 1234 5678"/></label><label className="checkbox"><input type="checkbox" checked={data.whatsapp} onChange={e => setData({ ...data, whatsapp:e.target.checked })}/>Autorizo al equipo a contactarme por WhatsApp para coordinar voluntariados. Es opcional.</label><button className="button primary" disabled={busy}>Guardar preferencias</button></form>}</section>;
}
