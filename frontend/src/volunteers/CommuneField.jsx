import { useEffect, useId, useState } from 'react';
import { api } from '../api';

export function communeKey(value) {
  return value.trim().toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export default function CommuneField({ initialValue = '', value: controlledValue, onChange }) {
  const id = useId();
  const [localValue, setLocalValue] = useState(initialValue);
  const value = controlledValue ?? localValue;
  function setValue(next) { setLocalValue(next); onChange?.(next); }
  const [communes, setCommunes] = useState([]);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError('');
    api('communes/').then(data => {
      if (!Array.isArray(data.communes)) throw new Error('Catálogo no disponible');
      if (active) setCommunes(data.communes);
    })
      .catch(() => { if (active) setError('No se pudo cargar la lista de comunas.'); });
    return () => { active = false; };
  }, [attempt]);
  const match = communes.find(name => communeKey(name) === communeKey(value));
  const suggestions = communes.filter(name => communeKey(name).includes(communeKey(value)));
  const validity = !communes.length ? 'Espera a que se cargue la lista de comunas.'
    : value && !match ? 'Selecciona una comuna válida de la lista.' : '';
  return <label className="field">Comuna (obligatoria)
    <input name="commune" required autoComplete="off" list={id} value={value} maxLength={80}
      placeholder="Escribe para buscar, por ejemplo: ren" aria-describedby={`${id}-help`}
      ref={input => { if (input) input.setCustomValidity(validity); }}
      onChange={event => setValue(event.target.value)} onBlur={() => { if (match) setValue(match); }}/>
    <datalist id={id}>{suggestions.map(name => <option key={name} value={name}/>)}</datalist>
    <small id={`${id}-help`}>{error || (communes.length ? 'Escribe y selecciona tu comuna de la lista.' : 'Cargando comunas…')}</small>
    {error && <button type="button" className="button" onClick={() => setAttempt(attempt + 1)}>Reintentar cargar comunas</button>}
  </label>;
}
