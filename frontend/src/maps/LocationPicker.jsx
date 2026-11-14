import { useState } from 'react';
import { api } from '../api';
import ReferenceMap from './ReferenceMap';

export default function LocationPicker({ value, onChange, approximate = false }) {
  const [query, setQuery] = useState(''), [results, setResults] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function search() {
    setBusy(true); setError('');
    try { setResults((await api('maps/search/', { method:'POST', body:JSON.stringify({ query }) })).results); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  const update = (key, raw) => onChange({ ...value, [key]: raw === '' ? null : Number(raw) });
  return <section className="location-picker"><p>{approximate ? 'Marca una referencia de tu sector, nunca tu domicilio. Se guardará redondeada a 0,01 grados.' : 'Confirma el lugar público de la actividad. La dirección exacta queda restringida al personal autorizado y participantes confirmados.'}</p>
    <div className="form-row"><label className="field">Buscar comuna, sector o lugar público<input value={query} maxLength={150} onChange={e => setQuery(e.target.value)} placeholder="Ej.: Plaza de Maipú"/></label><button type="button" className="button secondary" disabled={busy || query.trim().length < 3} onClick={search}>{busy ? 'Buscando…' : 'Buscar lugar'}</button></div>
    <small>La búsqueda externa requiere activación administrativa. No envíes domicilios, nombres de personas ni datos confidenciales a este servicio. También puedes seleccionar el mapa directamente.</small>
    {error && <p className="error" role="alert">{error}</p>}{results.map((row, index) => <button type="button" className="place-result" key={index} onClick={() => { onChange({ ...value, latitude:row.latitude, longitude:row.longitude }); setResults([]); }}>{row.label}</button>)}
    <ReferenceMap points={value.latitude !== null && value.longitude !== null ? [{ id:'reference', ...value, label:approximate ? 'Referencia aproximada' : 'Actividad' }] : []} onPick={p => onChange({ ...value, ...p })}/>
    <div className="form-row"><label className="field">Latitud<input type="number" min="-90" max="90" step="any" value={value.latitude ?? ''} onChange={e => update('latitude', e.target.value)}/></label><label className="field">Longitud<input type="number" min="-180" max="180" step="any" value={value.longitude ?? ''} onChange={e => update('longitude', e.target.value)}/></label></div>
    <button type="button" className="text-button" onClick={() => onChange({ ...value, latitude:null, longitude:null })}>Eliminar referencia</button></section>;
}
