import { useEffect, useState } from 'react';
import { api } from '../api';
import { Pagination } from '../activities/Participation';

export function WorkspaceSummary({ portal, navigate }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  useEffect(() => { setData(null); setError(''); api(`workspace-summary/?portal=${portal}`).then(setData).catch(err => setError(err.message)); }, [portal]);
  return <section aria-label="Resumen del espacio">{error && <p className="error" role="alert">{error}</p>}{!data && !error && <p role="status">Cargando resumen…</p>}<div className="dashboard-cards">{data?.metrics.map(item => <article className="panel info-card" key={item.label}><span className="info-label">{item.label}</span><h2>{item.value}</h2><button className="text-button" onClick={() => navigate(item.target)}>Ver detalle →</button></article>)}</div></section>;
}

export function StaffProfile({ user, setUser }) {
  const [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    const body = { ...Object.fromEntries(new FormData(event.currentTarget)), revision: user.management_revision };
    try { const result = await api('account-profile/', { method: 'PATCH', body: JSON.stringify(body) }); setUser(result); setMessage('Datos actualizados.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel profile-panel"><h2>Mi cuenta</h2><p>{user.email}</p><p>Roles: {user.roles.join(', ')}</p>{error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}<form onSubmit={save}><fieldset className="form-fieldset" disabled={busy}><div className="form-row"><label className="field">Nombre<input name="first_name" defaultValue={user.first_name} maxLength={80} required/></label><label className="field">Apellido<input name="last_name" defaultValue={user.last_name} maxLength={80} required/></label></div><button className="button primary" disabled={busy}>Guardar datos</button></fieldset></form><p><a className="button secondary" href="/accounts/password/change/">Cambiar contraseña</a></p></section>;
}

export function Catalogs() {
  const [kind, setKind] = useState('skills'), [data, setData] = useState(null), [selected, setSelected] = useState(null), [editing, setEditing] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function load() { setError(''); try { setData(await api(`management/catalogs/${kind}/`)); } catch (err) { setError(err.message); } }
  useEffect(() => { setData(null); setEditing(false); load(); }, [kind]);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    const body = { name: form.get('name'), description: form.get('description'), is_active: form.has('is_active'), required_documents: form.getAll('required_documents').map(Number), ...(selected ? { id: selected.id } : {}) };
    try { await api(`management/catalogs/${kind}/`, { method: selected ? 'PUT' : 'POST', body: JSON.stringify(body) }); setEditing(false); await load(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><div className="panel-heading"><h2>Catálogos de la fundación</h2><button className="button primary" onClick={() => { setSelected(null); setEditing(true); }}>Nueva entrada</button></div><label className="field">Catálogo<select value={kind} onChange={e => setKind(e.target.value)}><option value="skills">Habilidades</option><option value="professions">Profesiones y oficios</option><option value="documents">Tipos de documento</option></select></label>{error && <p className="error" role="alert">{error}</p>}{editing ? <form onSubmit={save} key={`${kind}-${selected?.id || 'new'}`}><fieldset className="form-fieldset" disabled={busy}><label className="field">Nombre<input name="name" maxLength={100} defaultValue={selected?.name || ''} required/></label><label className="field">Descripción<textarea name="description" maxLength={500} defaultValue={selected?.description || ''}/></label><label className="checkbox"><input type="checkbox" name="is_active" defaultChecked={selected?.is_active ?? true}/>Disponible para nuevas selecciones</label>{kind !== 'documents' && <fieldset><legend>Documentos requeridos</legend>{data?.documents.map(item => <label className="checkbox" key={item.id}><input name="required_documents" type="checkbox" value={item.id} defaultChecked={selected?.required_documents.includes(item.id)}/>{item.name}</label>)}</fieldset>}<div className="actions"><button className="button primary" disabled={busy}>Guardar</button><button className="button secondary" type="button" onClick={() => setEditing(false)}>Cancelar</button></div></fieldset></form> : <>{data?.results.length === 0 && <p>Este catálogo todavía no tiene entradas.</p>}{data?.results.map(item => <article className="panel" key={item.id}><strong>{item.name}</strong><p>{item.description}</p><p>{item.is_active ? 'Activo' : 'Inactivo'}</p><button className="button secondary" onClick={() => { setSelected(item); setEditing(true); }}>Editar</button></article>)}</>}</section>;
}

export function VolunteerDirectory() {
  const [data, setData] = useState(null), [page, setPage] = useState(1), [query, setQuery] = useState(''), [search, setSearch] = useState(''), [selected, setSelected] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function load() { setError(''); try { setData(await api(`operations/volunteers/?page=${page}&q=${encodeURIComponent(search)}`)); } catch (err) { setError(err.message); } }
  useEffect(() => { load(); }, [page, search]);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { await api('operations/volunteers/', { method: 'POST', body: JSON.stringify({ id: selected.id, restricted: !selected.restricted, reason: form.get('reason') }) }); setSelected(null); await load(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Directorio de voluntarios</h2><p>Las restricciones impiden nuevas postulaciones, invitaciones y confirmaciones. Revisa por separado las participaciones que ya estaban confirmadas.</p><form className="actions" onSubmit={e => { e.preventDefault(); setPage(1); setSearch(query); }}><label className="field">Nombre o comuna<input value={query} maxLength={100} onChange={e => setQuery(e.target.value)}/></label><button className="button secondary">Buscar</button></form>{error && <p className="error" role="alert">{error}</p>}{selected && <form className="panel" onSubmit={save}><h3>{selected.restricted ? 'Retirar restricción' : 'Restringir participación'}: {selected.name}</h3><label className="field">Motivo<textarea name="reason" minLength={8} maxLength={1000} required/></label><div className="actions"><button className="button primary" disabled={busy}>Confirmar cambio</button><button type="button" className="button secondary" onClick={() => setSelected(null)}>Cancelar</button></div></form>}{data?.results.map(item => <article className="panel" key={item.id}><h3>{item.name}</h3><p>{item.commune || 'Sin comuna'} · {item.restricted ? 'Restringido' : 'Habilitado'}</p>{item.restricted && <p>Motivo: {item.reason}</p>}<button className="button secondary" onClick={() => setSelected(item)}>{item.restricted ? 'Retirar restricción' : 'Restringir'}</button></article>)}{data?.results.length === 0 && <p>No hay voluntarios para esta búsqueda.</p>}<Pagination data={data} page={page} setPage={setPage}/></section>;
}
