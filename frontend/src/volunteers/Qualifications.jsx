import { useEffect, useState } from 'react';
import { Award, BookOpen, Check, RefreshCw } from 'lucide-react';
import { api } from '../api';

export default function Qualifications() {
  const [catalogs, setCatalogs] = useState(null);
  const [selection, setSelection] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const [catalog, current] = await Promise.all([
        api('volunteer/catalogs/'), api('volunteer/qualifications/'),
      ]);
      setCatalogs(catalog);
      setSelection(current);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, []);

  function toggle(group, id) {
    setMessage('');
    setSelection(current => ({
      ...current,
      [group]: current[group].includes(id)
        ? current[group].filter(item => item !== id)
        : [...current[group], id],
    }));
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await api('volunteer/qualifications/', {
        method: 'PUT',
        body: JSON.stringify({
          revision: selection.revision,
          skills: selection.skills,
          professions: selection.professions,
        }),
      });
      setSelection(result);
      setMessage('Tus habilidades y profesiones se guardaron correctamente.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel qualifications-panel" aria-busy={busy}>
    <div className="panel-heading">
      <h2>Lo que puedes aportar</h2>
      <button className="text-button" type="button" disabled={busy} onClick={load}>
        <RefreshCw size={15}/> Recargar
      </button>
    </div>
    <p className="section-description">Selecciona tus habilidades y profesiones u oficios. Podrás modificarlos cuando lo necesites.</p>
    <div className="notice"><BookOpen size={19}/><p>La información es declarada por ti. Seleccionar una profesión o habilidad no la acredita: el equipo deberá revisar los documentos requeridos.</p></div>
    {busy && !selection && <p role="status">Cargando tu información…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status" className="success">{message}</p>}
    {selection && catalogs && <form onSubmit={save}>
      <fieldset disabled={busy} className="form-fieldset">
        <CatalogChoices title="Habilidades" icon={<Award size={19}/>} group="skills" entries={catalogs.skills} selected={selection.skills} onToggle={toggle}/>
        <CatalogChoices title="Profesiones y oficios" icon={<BookOpen size={19}/>} group="professions" entries={catalogs.professions} selected={selection.professions} onToggle={toggle}/>
        <div className="form-actions"><span className="help">Guardar actualiza tu declaración, no su validación documental.</span><button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar selección'}<Check size={17}/></button></div>
      </fieldset>
    </form>}
  </section>;
}

function CatalogChoices({ title, icon, group, entries, selected, onToggle }) {
  return <fieldset className="catalog-section">
    <legend>{icon}{title}</legend>
    {entries.length === 0 ? <div className="empty-state"><p>El equipo todavía no ha publicado opciones en este catálogo.</p></div> : <div className="catalog-grid">{entries.map(entry => {
      const checked = selected.includes(entry.id);
      return <label className={`catalog-option ${checked ? 'selected' : ''}`} key={entry.id}>
        <input type="checkbox" checked={checked} disabled={!entry.is_active && !checked} onChange={() => onToggle(group, entry.id)}/>
        <span><strong>{entry.name}</strong>{!entry.is_active && <span className="inactive-label">Desactivada: puedes conservarla o quitarla.</span>}{entry.description && <span className="help">{entry.description}</span>}{entry.required_documents.length > 0 && <span className="document-hint">Requiere: {entry.required_documents.map(document => document.name).join(', ')}.</span>}</span>
      </label>;
    })}</div>}
  </fieldset>;
}
