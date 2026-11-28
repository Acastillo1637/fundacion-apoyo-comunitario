import { useEffect, useState } from 'react';
import { api } from '../api';
import { Pagination } from './Participation';

export const contactExpired = (item, now = Date.now()) => Boolean(item.expires_at && new Date(item.expires_at).getTime() <= now);

const labels = { pending_contact:'Pendiente de contacto', contact_started:'Contacto iniciado', sent:'Envío confirmado manualmente', accepted:'Respuesta aceptada', declined:'Rechazada', no_response:'Sin respuesta', cancelled:'Cancelada' };

const formatContactDate = value => new Date(value).toLocaleString('es-CL', {timeZone:'America/Santiago'});
const actionLabels = {start:'Apertura de WhatsApp solicitada', sent:'Envío confirmado manualmente', created:'Seguimiento creado', reopen:'Nueva ronda de contacto', accepted:'Aceptación registrada', confirm:'Participación confirmada', declined:'Rechazo registrado', no_response:'Sin respuesta', cancelled:'Seguimiento cancelado'};
function reserveWindow() {
  const popup = window.open('about:blank', '_blank');
  if (popup) popup.opener = null;
  return popup;
}
function showWhatsapp(popup, url) {
  if (popup && !popup.closed) { popup.location.replace(url); return true; }
  return Boolean(window.open(url, '_blank', 'noopener,noreferrer'));
}
export function DeliveryStatus({ delivery }) {
  if (!delivery) return null;
  return <div className="help" role="status">{delivery.opened && <p>Apertura solicitada: {formatContactDate(delivery.opened.at)} · {delivery.opened.actor}</p>}{delivery.sent ? <p>Envío confirmado manualmente: {formatContactDate(delivery.sent.at)} · {delivery.sent.actor}</p> : <p>Envío pendiente de confirmación. Abrir WhatsApp no envía el mensaje.</p>}</div>;
}

export function ContactCandidateButton({ eventId, positionId, profileId, contact: initialContact = null, disabled, onChanged }) {
  const [contact, setContact] = useState(initialContact), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState(false);
  useEffect(() => { setContact(initialContact); setError(''); setBlocked(false); }, [eventId,positionId,profileId,initialContact]);
  async function start() {
    const popup = reserveWindow();
    setBusy(true); setError(''); setBlocked(false);
    try {
      const current = await api(`activities/operations/events/${eventId}/contacts/`, { method:'POST', body:JSON.stringify({ profile_id:profileId, position_id:Number(positionId) }) });
      const result = await api(`activities/operations/contacts/${current.id}/action/`, { method:'POST', body:JSON.stringify({ action:'start', revision:current.revision }) });
      setContact(result); setBlocked(!showWhatsapp(popup,result.whatsapp_url)); onChanged?.();
    } catch (err) { popup?.close(); setError(err.message); } finally { setBusy(false); }
  }
  async function confirmSend() {
    if (!window.confirm('¿Confirmas que enviaste el mensaje por WhatsApp? Esto solo registra el envío manual; no acepta la invitación ni asigna un cupo.')) return;
    setBusy(true); setError('');
    try {
      const result = await api(`activities/operations/contacts/${contact.id}/action/`, {method:'POST',body:JSON.stringify({action:'sent',revision:contact.revision})});
      setContact(result); onChanged?.();
    } catch(err) { setError(err.message); } finally { setBusy(false); }
  }
  const closed = ['accepted','declined','cancelled'].includes(contact?.status);
  return <div className="contact-action"><button type="button" className="button secondary small" disabled={disabled || busy || closed || contactExpired(contact || {})} onClick={start}>{busy ? 'Procesando…' : contact?.delivery?.opened ? 'Volver a abrir WhatsApp' : 'Contactar por WhatsApp'}</button>
    {contact?.delivery?.can_confirm_send && <button type="button" className="button secondary small" disabled={busy || contactExpired(contact)} onClick={confirmSend}>Confirmar envío</button>}
    <DeliveryStatus delivery={contact?.delivery}/>{contactExpired(contact || {}) && <small>Esta ronda venció. Inicia una nueva ronda desde Seguimiento de contactos antes de volver a abrir WhatsApp.</small>}{blocked && <small>No se pudo abrir la ventana. Permite ventanas emergentes y vuelve a abrir WhatsApp. El envío sigue sin confirmar.</small>}
    {error && <span className="error" role="alert">{error}</span>}</div>;
}

export function GeneralWhatsappButton({ profileId }) {
  const [opened, setOpened] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function start() {
    const popup = reserveWindow();
    setBusy(true); setError('');
    try { const result = await api(`operations/volunteers/${profileId}/whatsapp/`, { method:'POST', body:'{}' }); setOpened(true); if (!showWhatsapp(popup,result.whatsapp_url)) setError('Si WhatsApp no se abrió, permite las ventanas emergentes y vuelve a intentar.'); }
    catch (err) { popup?.close(); setError(err.message); } finally { setBusy(false); }
  }
  return <div><button className="button primary small" disabled={busy} onClick={start}>{busy ? 'Preparando…' : opened ? 'Volver a abrir WhatsApp' : 'Contactar por WhatsApp'}</button>{opened && <p>Intento registrado; revisa y envía manualmente. Este contacto general no asigna un cupo.</p>}{error && <p role="alert" className="error">{error}</p>}</div>;
}

export default function Contacts({ eventId, refreshKey = 0, onChanged }) {
  const [data, setData] = useState(null), [page, setPage] = useState(1), [notes, setNotes] = useState({}), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function load() { try { setData(await api(`activities/operations/events/${eventId}/contacts/?page=${page}`)); } catch (err) { setError(err.message); } }
  useEffect(() => { setData(null); setError(''); load(); }, [eventId, page, refreshKey]);
  async function action(item, value) {
    if (value !== 'start' && !window.confirm(value === 'sent' ? '¿Confirmas que enviaste el mensaje por WhatsApp? No registra aceptación ni asigna un cupo.' : value === 'confirm' ? '¿Confirmas que el voluntario aceptó y autorizó registrar su participación? Se volverán a revisar requisitos y cupos.' : '¿Confirmas que esta actualización representa lo ocurrido? El sistema no verifica el envío ni la recepción en WhatsApp.')) return;
    const popup = value === 'start' ? reserveWindow() : null;
    setBusy(true); setError('');
    try { const result = await api(`activities/operations/contacts/${item.id}/action/`, { method:'POST', body:JSON.stringify({ action:value, revision:item.revision, note:notes[item.id] || '' }) });
      if (result.whatsapp_url && !showWhatsapp(popup,result.whatsapp_url)) setError('Permite las ventanas emergentes y vuelve a abrir WhatsApp. El envío no fue confirmado.');
      await load(); onChanged?.();
    } catch (err) { popup?.close(); setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel contact-history"><h2>Seguimiento de contactos e invitaciones</h2><p>Abrir un enlace solo registra un intento. Indica manualmente lo enviado y la respuesta; no copies conversaciones ni datos sensibles. Registrar aceptación no confirma un cupo hasta ejecutar “Confirmar participación”.</p>{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando seguimiento…</p>}{data?.results.length === 0 && <p>Aún no hay contactos de esta convocatoria.</p>}{data?.results.map(item => <article className="contact-row" key={item.id}><h3>{item.name} · {item.position}</h3><span className="tag">{labels[item.status]}</span>{item.expires_at && <p>Vence: {new Date(item.expires_at).toLocaleString('es-CL', {timeZone:'America/Santiago'})}</p>}{contactExpired(item) && <p className="notice">Esta ronda venció. Inicia una nueva ronda con una justificación antes de volver a contactar o confirmar.</p>}<DeliveryStatus delivery={item.delivery}/>{item.participation_status && <p>Participación: {item.participation_status}</p>}<label className="field">Referencia de la actualización<input maxLength={500} value={notes[item.id] || ''} onChange={e => setNotes({ ...notes, [item.id]:e.target.value })} placeholder="Ej.: aceptación recibida el 14/11 por WhatsApp"/></label><div className="actions">{['pending_contact','contact_started','sent','no_response'].includes(item.status) && <button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'start')}>Abrir WhatsApp y registrar intento</button>}{['cancelled','declined','no_response'].includes(item.status) || (item.expires_at && new Date(item.expires_at) <= new Date()) || (item.status === 'accepted' && ['cancelled','declined','rejected'].includes(item.participation_status)) ? <button className="button secondary small" disabled={busy} onClick={() => action(item,'reopen')}>Nueva ronda de contacto</button> : null}{['contact_started','sent','no_response'].includes(item.status) && <>{item.delivery?.can_confirm_send && <button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'sent')}>Confirmar envío</button>}<button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'accepted')}>Registrar aceptación</button><button className="button secondary small" disabled={busy} onClick={() => action(item,'declined')}>Registrar rechazo</button>{item.status !== 'no_response' && <button className="button secondary small" disabled={busy} onClick={() => action(item,'no_response')}>Sin respuesta</button>}</>}{item.status === 'accepted' && item.delivery?.can_confirm_send && <button className="button secondary small" disabled={busy || contactExpired(item)} onClick={() => action(item,'sent')}>Confirmar envío</button>}{item.status === 'accepted' && <button className="button primary small" disabled={busy || contactExpired(item) || item.participation_status === 'confirmed'} onClick={() => action(item,'confirm')}>Confirmar participación</button>}{!['cancelled','declined'].includes(item.status) && <button className="text-button" disabled={busy} onClick={() => action(item,'cancelled')}>Cancelar seguimiento</button>}</div><details><summary>Historial de contacto</summary>{item.history.map((row,index) => <p key={index}>{formatContactDate(row.at)} · {row.actor} · {actionLabels[row.action] || row.action} · {row.note || labels[row.to]}</p>)}</details></article>)}<Pagination data={data} page={page} setPage={setPage}/></section>;
}

export function CommunicationPreferences() {
  const [data,setData] = useState(null), [error,setError] = useState(''), [message,setMessage] = useState(''), [busy,setBusy] = useState(false);
  useEffect(() => { api('volunteer/contact-preferences/').then(setData).catch(e => setError(e.message)); }, []);
  async function save(e) { e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const { consent_at, ...values } = data; setData(await api('volunteer/contact-preferences/', { method:'PUT', body:JSON.stringify(values) })); setMessage('Preferencias guardadas. Puedes retirar tu autorización en cualquier momento.'); }
    catch(err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Preferencias de comunicación</h2>{error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}{data && <form onSubmit={save}><label className="field">Teléfono internacional<input type="tel" required maxLength={12} value={data.phone} onChange={e => setData({ ...data, phone:e.target.value })} placeholder="+56912345678"/></label><label className="checkbox"><input type="checkbox" checked={data.whatsapp} onChange={e => setData({ ...data, whatsapp:e.target.checked })}/>Autorizo al equipo a contactarme por WhatsApp para coordinar voluntariados. Es opcional.</label><button className="button primary" disabled={busy}>Guardar preferencias</button></form>}</section>;
}
