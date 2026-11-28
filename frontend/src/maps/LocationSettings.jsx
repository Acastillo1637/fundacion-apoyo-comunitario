import { useEffect, useState } from 'react';
import { api } from '../api';
import LocationPicker from './LocationPicker';
import CommuneField from '../volunteers/CommuneField';

export default function LocationSettings() {
  const [data, setData] = useState(null), [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false);
  const [address, setAddress] = useState(''), [consent, setConsent] = useState(false), [choices, setChoices] = useState([]), [manualOpen, setManualOpen] = useState(false);
  useEffect(() => { api('volunteer/location/').then(setData).catch(e => setError(e.message)); }, []);
  function changeAddress(value) { setAddress(value); setChoices([]); }
  async function calculate(e, choice) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const result = await api('volunteer/location/address/', { method:'POST', body:JSON.stringify({ address, commune:data.commune, sector:data.sector, revision:data.revision, consent, ...(choice ? { choice } : {}) }) });
      if (result.saved) { setData(result.location); setChoices([]); setAddress(''); setConsent(false); setMessage('Ubicación aproximada calculada y guardada. Ya puede utilizarse en el matching.'); }
      else { setChoices(result.choices); setMessage('Revisa las referencias encontradas. Confirma una solo si corresponde a tu sector; puedes corregir la dirección y buscar nuevamente.'); }
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function saveManual(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { setData(await api('volunteer/location/', { method:'PUT', body:JSON.stringify({ latitude:data.latitude, longitude:data.longitude, sector:data.sector, commune:data.commune, revision:data.revision }) })); setChoices([]); setMessage('Referencia aproximada guardada.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Mi ubicación de referencia</h2><p>Solo tú y coordinación autorizada pueden consultarla. Otros voluntarios no pueden verla.</p>
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}{!data && !error && <p role="status">Cargando…</p>}
    {data && <><form onSubmit={calculate}><fieldset disabled={busy} className="form-fieldset">
      <div className="form-row"><CommuneField value={data.commune} onChange={commune => { setData({ ...data, commune }); setChoices([]); }}/>
      <label className="field">Sector aproximado<input value={data.sector} maxLength={80} onChange={e => setData({ ...data, sector:e.target.value })}/></label></div>
      <label className="field">Dirección: calle y número<input autoComplete="off" value={address} required minLength={5} maxLength={250} onChange={e => changeAddress(e.target.value)}/></label>
      <p className="help">Al guardar, Geoapify recibirá esta dirección para calcular la ubicación. Nuestra base guarda solo una referencia redondeada a 0,01 grados, no el domicilio completo. El proveedor procesa solicitudes en sus servidores y puede conservar registros técnicos temporalmente. <a href="https://www.geoapify.com/privacy-policy/" target="_blank" rel="noopener noreferrer">Privacidad de Geoapify</a>.</p>
      <label className="checkbox"><input type="checkbox" checked={consent} required onChange={e => setConsent(e.target.checked)}/>Autorizo enviar esta dirección a Geoapify para calcular mi ubicación aproximada.</label>
      {!data.address_geocoding_enabled && <p role="status">El cálculo por dirección aún no está configurado. Puedes utilizar la referencia manual.</p>}
      <button className="button primary" disabled={busy || !consent || !data.address_geocoding_enabled}>{busy ? 'Calculando…' : 'Guardar y calcular ubicación'}</button>
      {choices.length > 0 && <div><h3>Confirmar referencia aproximada</h3>{choices.map(row => <p key={row.token}>{row.label} ({row.latitude}, {row.longitude}) <button type="button" className="button secondary" onClick={e => calculate(e, row.token)} disabled={!consent}>Confirmar este sector</button></p>)}</div>}
    </fieldset></form>
    <p className="help">{data.precision} {data.latitude != null && `Referencia actual: ${data.latitude}, ${data.longitude}.`}</p>
    <details onToggle={e => setManualOpen(e.currentTarget.open)}><summary>Ver mapa o elegir una referencia manual</summary>{manualOpen && <form onSubmit={saveManual}><fieldset disabled={busy} className="form-fieldset"><LocationPicker approximate value={data} onChange={value => { setData(value); setChoices([]); }}/><button className="button secondary">Guardar referencia manual</button></fieldset></form>}</details>
    <p className="help">Geocodificación: <a href="https://www.geoapify.com/" target="_blank" rel="noopener noreferrer">Geoapify</a> · © OpenStreetMap contributors.</p></>}
  </section>;
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
