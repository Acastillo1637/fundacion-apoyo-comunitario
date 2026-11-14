import { useEffect, useState } from 'react';
import { api } from '../api';
import LocationPicker from './LocationPicker';

export default function LocationSettings() {
  const [data, setData] = useState(null), [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { api('volunteer/location/').then(setData).catch(e => setError(e.message)); }, []);
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { setData(await api('volunteer/location/', { method:'PUT', body:JSON.stringify({ latitude:data.latitude, longitude:data.longitude, sector:data.sector, commune:data.commune, revision:data.revision }) })); setMessage('Referencia aproximada guardada.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Mi ubicación de referencia</h2><p>Solo tú y coordinación autorizada pueden consultarla. Otros voluntarios no pueden verla.</p>{error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}{!data && !error && <p role="status">Cargando…</p>}{data && <form onSubmit={save}><fieldset disabled={busy} className="form-fieldset"><div className="form-row"><label className="field">Comuna<input value={data.commune} maxLength={80} onChange={e => setData({ ...data, commune:e.target.value })}/></label><label className="field">Sector aproximado<input value={data.sector} maxLength={80} onChange={e => setData({ ...data, sector:e.target.value })}/></label></div><LocationPicker approximate value={data} onChange={setData}/><p className="help">{data.precision}</p><button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar referencia'}</button></fieldset></form>}</section>;
}

export function EventLocation({ event, onSaved }) {
  const [data, setData] = useState({ ...event.location, address:event.address, commune:event.commune }), [reason, setReason] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { setData({ ...event.location, address:event.address, commune:event.commune }); }, [event.id, event.revision]);
  async function save(e) {
    e.preventDefault();
    if (!window.confirm('¿Confirmas el cambio de ubicación? En una convocatoria abierta se notificará a sus participantes.')) return;
    setBusy(true); setError('');
    try { onSaved(await api(`activities/operations/events/${event.id}/location/`, { method:'PUT', body:JSON.stringify({ ...data, reason, revision:event.revision }) })); setReason(''); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Ubicación de la convocatoria</h2>{error && <p className="error" role="alert">{error}</p>}<form onSubmit={save}><fieldset className="form-fieldset" disabled={busy}><label className="checkbox"><input type="checkbox" checked={data.is_remote} onChange={e => setData({ ...data, is_remote:e.target.checked, latitude:null, longitude:null })}/>Actividad remota</label>{!data.is_remote && <><div className="form-row"><label className="field">Dirección del lugar<input value={data.address} maxLength={250} required onChange={e => setData({ ...data, address:e.target.value })}/></label><label className="field">Comuna<input value={data.commune} maxLength={80} required onChange={e => setData({ ...data, commune:e.target.value })}/></label></div><LocationPicker value={data} onChange={setData}/></>}<label className="field">Motivo del cambio<input value={reason} minLength={8} maxLength={1000} required onChange={e => setReason(e.target.value)}/></label><button className="button primary" disabled={busy || !['draft','open'].includes(event.status) || new Date(event.starts_at) <= new Date()}>Guardar ubicación</button></fieldset></form></section>;
}
