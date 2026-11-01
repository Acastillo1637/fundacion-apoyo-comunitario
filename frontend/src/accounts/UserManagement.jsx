import { useEffect, useState } from 'react';
import { ArrowLeft, Check, Mail, Plus, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { api } from '../api';

const roles = ['Voluntario', 'Solicitante', 'Secretaría', 'Administrador general'];
const actions = { participation_restriction: 'Restricción de participación actualizada', created_by_admin: 'Cuenta creada', updated_by_admin: 'Cuenta actualizada', access_email_sent: 'Enlace de acceso solicitado', access_email_failed: 'Falló el envío del enlace' };
const date = value => value ? new Date(value).toLocaleString('es-CL', { timeZone: 'America/Santiago' }) : 'Sin registros';

export default function UserManagement({ onSelfChanged }) {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [creating, setCreating] = useState(false);
  const [filters, setFilters] = useState({ q: '', active: '', role: '' });
  const [draftQuery, setDraftQuery] = useState('');
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function load() {
    setBusy(true); setError('');
    try { setData(await api(`management/users/?${new URLSearchParams({ ...filters, page })}`)); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, [filters, page]);

  async function open(id) {
    setBusy(true); setError(''); setMessage(''); setCreating(false);
    try { setSelected(await api(`management/users/${id}/`)); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function save(body, create) {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api(create ? 'management/users/' : `management/users/${selected.id}/`, {
        method: create ? 'POST' : 'PATCH', body: JSON.stringify(body),
      });
      setSelected(create ? result.user : result);
      setCreating(false);
      if (!create && result.is_self && onSelfChanged) onSelfChanged((await api('session/')).user);
      await load();
      if (create && !result.email_sent) setError(result.detail);
      else setMessage(create ? result.detail : 'Cambios guardados. Si cambió el acceso o el rol, las sesiones anteriores fueron invalidadas.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function email(reason) {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api(`management/users/${selected.id}/access-email/`, { method: 'POST', body: JSON.stringify({ reason }) });
      setMessage(result.detail);
      setSelected(await api(`management/users/${selected.id}/`));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <section className="user-management">
    <div className="panel"><div className="panel-heading"><h2>Administrar usuarios</h2><div className="operation-tabs"><button className="text-button" disabled={busy} onClick={() => { setSelected(null); setCreating(false); load(); }}><RefreshCw size={15}/> Recargar</button><button className="button primary small" disabled={busy} onClick={() => { setSelected(null); setCreating(true); setError(''); setMessage(''); }}><Plus size={16}/> Crear cuenta</button></div></div><p className="section-description">Gestiona acceso y roles con trazabilidad. El titular establece su propia contraseña y acepta sus consentimientos.</p></div>
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}
    {creating || selected ? <div className="panel"><button className="text-button" disabled={busy} onClick={() => { setCreating(false); setSelected(null); setError(''); }}><ArrowLeft size={16}/> Volver a usuarios</button><AccountEditor key={creating ? 'create' : `${selected.id}:${selected.revision}`} user={selected} creating={creating} busy={busy} onSave={save} onEmail={email}/></div> : <div className="panel">
      <form className="user-filters" onSubmit={event => { event.preventDefault(); setFilters(current => ({ ...current, q: draftQuery })); setPage(1); }}><label className="field">Buscar<input value={draftQuery} onChange={event => setDraftQuery(event.target.value)} placeholder="Nombre o correo" maxLength={100}/></label><label className="field">Estado<select value={filters.active} onChange={event => { setFilters(current => ({ ...current, active: event.target.value })); setPage(1); }}><option value="">Todos</option><option value="true">Activos</option><option value="false">Inactivos</option></select></label><label className="field">Rol<select value={filters.role} onChange={event => { setFilters(current => ({ ...current, role: event.target.value })); setPage(1); }}><option value="">Todos</option>{roles.map(role => <option key={role}>{role}</option>)}</select></label><button className="button secondary" disabled={busy}><Search size={16}/> Buscar</button></form>
      {busy && !data && <p role="status">Cargando usuarios…</p>}
      {data?.results.length === 0 && <div className="empty-state"><p>No hay usuarios con esos filtros.</p></div>}
      <div className="operation-list">{data?.results.map(user => <article className="operation-item" key={user.id}><div><h3>{[user.first_name, user.last_name].filter(Boolean).join(' ') || 'Sin nombre'} {user.is_self && <small>(tú)</small>}</h3><p>{user.email}</p><div className="account-badges"><span className={`document-status ${user.is_active ? 'validated' : 'rejected'}`}>{user.is_active ? 'Activo' : 'Inactivo'}</span>{user.roles.map(role => <span className="tag" key={role}>{role}</span>)}{user.protected && <span className="tag">Privilegios técnicos</span>}</div><small className="help">Correo {user.email_verified ? 'verificado' : 'pendiente'} · MFA {user.has_mfa ? 'configurado' : 'sin configurar'}</small></div><button className="button secondary small" disabled={busy} onClick={() => open(user.id)}>Administrar</button></article>)}</div>
      {data && <div className="form-actions"><button className="button secondary" disabled={busy || page <= 1} onClick={() => setPage(current => current - 1)}>Anterior</button><span className="help">{data.total} usuarios · Página {page}</span><button className="button secondary" disabled={busy || page * data.page_size >= data.total} onClick={() => setPage(current => current + 1)}>Siguiente</button></div>}
    </div>}
  </section>;
}

function AccountEditor({ user, creating, busy, onSave, onEmail }) {
  const [selectedRoles, setSelectedRoles] = useState(user?.roles.filter(role => roles.includes(role)) || ['Voluntario']);
  const [active, setActive] = useState(user?.is_active ?? true);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(null);
  const canEditIdentity = creating || user.can_edit_identity;
  const canEditAccess = creating || user.can_edit_access;
  function toggle(role) { setSelectedRoles(current => current.includes(role) ? current.filter(item => item !== role) : [...current, role]); }
  function prepare(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = { reason };
    if (canEditIdentity) { body.first_name = form.get('first_name'); body.last_name = form.get('last_name'); }
    if (creating) { body.email = form.get('email'); body.roles = selectedRoles; }
    else { body.revision = user.revision; if (canEditAccess) { body.roles = selectedRoles; body.is_active = active; } }
    setPending({ type: 'save', body });
  }
  function confirm() {
    if (pending.type === 'email') onEmail(reason);
    else onSave(pending.body, creating);
    setPending(null);
  }
  return <>
    <h2 className="detail-title">{creating ? 'Crear cuenta por invitación' : user.email}</h2>
    {!creating && <><div className="account-badges"><span className="tag">Alta: {date(user.date_joined)}</span><span className="tag">Último acceso: {date(user.last_login)}</span></div>{(user.protected || user.is_self) && <div className="notice"><ShieldCheck size={19}/><p>{user.is_self ? 'Puedes actualizar tu nombre; los cambios de tu propio rol o estado están bloqueados.' : 'Esta cuenta tiene privilegios técnicos. No se modifica desde esta sección.'}</p></div>}</>}
    {creating && <div className="notice"><Mail size={19}/><p>No se asignan contraseñas compartidas. Se envía un enlace al titular para que establezca la suya y verifique su correo. En desarrollo el mensaje aparece en la terminal de Django.</p></div>}
    <form onSubmit={prepare}><fieldset className="form-fieldset" disabled={busy || (!creating && !user.can_edit_identity)}>
      <div className="form-row"><label className="field">Nombre<input name="first_name" defaultValue={user?.first_name || ''} required maxLength={80}/></label><label className="field">Apellido<input name="last_name" defaultValue={user?.last_name || ''} required maxLength={80}/></label></div>
      {creating && <label className="field">Correo electrónico<input type="email" name="email" required maxLength={254}/></label>}
      <fieldset className="catalog-section" disabled={!canEditAccess}><legend>Roles</legend><div className="request-skills">{roles.map(role => <label className="checkbox" key={role}><input type="checkbox" checked={selectedRoles.includes(role)} onChange={() => toggle(role)}/>{role}</label>)}</div></fieldset>
      {!creating && <label className="checkbox"><input type="checkbox" checked={active} disabled={!canEditAccess} onChange={event => setActive(event.target.checked)}/>Cuenta activa</label>}
      <label className="field">Motivo del cambio o del envío<textarea value={reason} onChange={event => setReason(event.target.value)} minLength={8} maxLength={1000} rows={3} required placeholder="Motivo administrativo, sin contraseñas ni información sensible."/></label>
      <div className="operation-tabs"><button className="button primary" disabled={busy || (canEditAccess && selectedRoles.length === 0)}><Check size={17}/>{creating ? 'Revisar alta' : 'Revisar cambios'}</button>{!creating && !user.is_self && !user.protected && <button type="button" className="button secondary" disabled={busy || !user.is_active || reason.trim().length < 8} onClick={() => setPending({ type: 'email' })}><Mail size={16}/> Enviar enlace de acceso</button>}</div>
    </fieldset></form>
    {pending && <section className="account-confirmation" role="region" aria-label="Confirmación de administración"><h3>Confirma la acción</h3><p>{pending.type === 'email' ? 'Se enviará un enlace al correo del titular. No se cambiará la contraseña automáticamente.' : creating ? 'Se creará una cuenta con los roles seleccionados y se solicitará el envío de un enlace de acceso.' : 'Se aplicarán los cambios indicados. Cambiar roles o estado invalidará las sesiones anteriores.'}</p>{pending.body?.roles && <p>Roles: {pending.body.roles.join(', ')}</p>}{pending.body?.is_active !== undefined && <p>Estado resultante: {pending.body.is_active ? 'Activo' : 'Inactivo'}</p>}<div className="operation-tabs"><button className="button secondary" type="button" onClick={() => setPending(null)}>Cancelar</button><button className="button primary" type="button" disabled={busy} onClick={confirm}>Confirmar</button></div></section>}
    {!creating && <section className="history-section"><h3>Historial administrativo reciente</h3>{user.history.length === 0 ? <p className="help">Sin cambios registrados desde esta sección.</p> : <ol>{user.history.map((change, index) => <li key={index}><strong>{actions[change.action] || change.action}</strong><small>{date(change.created_at)} · {change.actor_name}</small><p>{change.reason}</p>{change.fields_changed.length > 0 && <small>Campos: {change.fields_changed.join(', ')}</small>}{change.after_access.roles && <small>Roles registrados: {change.after_access.roles.join(', ')} · {change.after_access.is_active ? 'Activo' : 'Inactivo'}</small>}</li>)}</ol>}</section>}
  </>;
}

export function VolunteerOnboarding({ onComplete }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try { onComplete(await api('profile/onboarding/', { method: 'POST', body: JSON.stringify({ adult: form.has('adult'), privacy: form.has('privacy'), whatsapp: form.has('whatsapp') }) })); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="panel"><h2>Completa tu incorporación</h2><p className="section-description">Tu cuenta fue creada por el equipo. Para habilitar tu perfil de voluntario necesitamos tu propia confirmación.</p>{error && <p className="error" role="alert">{error}</p>}<form onSubmit={submit}><fieldset disabled={busy} className="form-fieldset"><label className="checkbox"><input type="checkbox" name="adult" required/>Confirmo que tengo 18 años o más.</label><label className="checkbox"><input type="checkbox" name="privacy" required/>Acepto el tratamiento de mis datos para gestionar mi participación.</label><label className="checkbox"><input type="checkbox" name="whatsapp"/>Quiero recibir invitaciones manuales por WhatsApp. Es opcional.</label><p className="help">Entorno de desarrollo: usa datos ficticios. El aviso institucional definitivo está pendiente.</p><button className="button primary">{busy ? 'Guardando…' : 'Habilitar mi perfil'}</button></fieldset></form></section>;
}
