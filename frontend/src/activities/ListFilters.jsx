import { useEffect, useState } from 'react';
import { emptyFilters } from './list-filters';

export default function ListFilters({ value, states, onApply, busy = false }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);
  return <form className="list-filters" role="search" onSubmit={e => { e.preventDefault(); onApply({...draft,q:draft.q.trim()}); }}>
    <fieldset className="form-fieldset" disabled={busy}><div className="form-row">
      <label className="field">Buscar por nombre, entidad o comuna<input type="search" maxLength={120} value={draft.q} onChange={e => setDraft({...draft,q:e.target.value})}/></label>
      <label className="field">Estado<select value={draft.status} onChange={e => setDraft({...draft,status:e.target.value})}><option value="">Todos los estados</option>{Object.entries(states).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label className="field">Fecha<select value={draft.period} onChange={e => setDraft({...draft,period:e.target.value})}><option value="">Todas las fechas</option><option value="upcoming">Próximas</option><option value="past">Finalizadas por horario</option></select></label>
    </div><div className="actions"><button className="button secondary" type="submit">Buscar</button><button className="text-button" type="button" onClick={() => { setDraft(emptyFilters); onApply(emptyFilters); }}>Limpiar filtros</button></div></fieldset>
  </form>;
}
