import { useEffect, useState } from 'react';
import { Download, FileCheck2, RefreshCw, Upload } from 'lucide-react';
import { api } from '../api';

const statuses = { pending: 'Pendiente', validated: 'Validado', rejected: 'Rechazado', expired: 'Vencido' };
const formatDate = value => value ? new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', dateStyle: 'medium' }).format(new Date(value)) : '—';

export default function Documents() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true); setError('');
    try { setData(await api('documents/')); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  async function upload(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = new FormData(form);
    const file = payload.get('file');
    setError(''); setMessage('');
    if (!file?.size || file.size > data.max_file_bytes) {
      setError('Selecciona un archivo con contenido, de hasta 10 MB.'); return;
    }
    setBusy(true);
    try {
      await api('documents/', { method: 'POST', body: payload });
      form.reset();
      setData(await api('documents/'));
      setMessage('Documento cargado. El equipo debe revisar esta nueva versión.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const latest = new Map();
  data?.documents.forEach(document => {
    if (!latest.has(document.document_type) || latest.get(document.document_type).version < document.version) {
      latest.set(document.document_type, document);
    }
  });

  return <section className="document-space" aria-busy={busy}>
    <div className="panel">
      <div className="panel-heading"><h2>Mis documentos</h2><button type="button" className="text-button" disabled={busy} onClick={load}><RefreshCw size={15}/> Recargar</button></div>
      <p className="section-description">Tus archivos son privados. Solo tú y el personal con autorización documental pueden acceder a ellos.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="success" role="status">{message}</p>}
      {!data && !error && <p role="status">Cargando documentos…</p>}
      {data && <>
        {!data.antimalware_required && <div className="notice"><FileCheck2 size={19}/><p>Entorno de pruebas: los archivos pueden quedar sin análisis antimalware. Usa documentos ficticios. La validación del formato no acredita el contenido del certificado.</p></div>}
        <h3 className="document-heading">Requisitos de tu perfil</h3>
        {data.required_type_ids.length === 0 ? <p className="help">Tus habilidades y profesiones actuales no tienen requisitos documentales configurados.</p> : <ul className="requirement-list">{data.types.filter(type => data.required_type_ids.includes(type.id)).map(type => {
          const document = latest.get(type.id);
          return <li key={type.id}><span>{type.name}{!type.is_active && <small className="inactive-label">Tipo desactivado: consulta al equipo.</small>}</span><span className={`document-status ${document?.status || 'missing'}`}>{document ? statuses[document.status] : 'Falta cargar'}</span></li>;
        })}</ul>}
        <div className="upload-section"><h3 className="document-heading">Cargar documento o nueva versión</h3>
          <p className="help">PDF, JPEG o PNG · Hasta 10 MB · PDF sin cifrado y máximo 50 páginas. Cada nueva versión necesita revisión.</p>
          <p className="help">Espacio utilizado: {(data.used_bytes / 1024 / 1024).toFixed(1)} de {Math.round(data.quota_bytes / 1024 / 1024)} MB. Las versiones anteriores también ocupan espacio.</p>
          <form onSubmit={upload}><fieldset disabled={busy} className="form-fieldset">
            <label className="field">Tipo documental<select name="document_type" required defaultValue=""><option value="" disabled>Selecciona un tipo</option>{data.types.filter(type => type.is_active).map(type => <option key={type.id} value={type.id}>{type.name}</option>)}</select></label>
            <label className="field">Archivo<input type="file" name="file" required accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"/></label>
            <button className="button primary" disabled={busy || !data.types.some(type => type.is_active)}><Upload size={17}/>{busy ? 'Procesando…' : 'Cargar documento'}</button>
          </fieldset></form>
        </div>
      </>}
    </div>
    {data && <div className="panel"><h2>Historial de versiones</h2>
      {data.documents.length === 0 ? <div className="empty-state"><p>Aún no has cargado documentos.</p></div> : <div className="document-list">{data.documents.map(document => <article className="document-card" key={document.id}>
        <div className="panel-heading"><h3>{document.type_name}</h3><span className={`document-status ${document.status}`}>{statuses[document.status]}</span></div>
        <p className="help">Versión {document.version}{latest.get(document.document_type)?.id === document.id ? ' · Más reciente' : ' · Histórica'} · Cargada el {formatDate(document.uploaded_at)}</p>
        <p className="help">{document.scan_status === 'clean' ? 'Antimalware: sin detección en el momento de carga.' : 'Sin análisis antimalware.'}</p>
        {document.observation && <p className="review-observation">Observación: {document.observation}</p>}
        {document.expires_on && <p className="help">Válido hasta: {document.expires_on.split('-').reverse().join('/')}</p>}
        {document.reviewed_at && <p className="help">Revisado: {formatDate(document.reviewed_at)}</p>}
        <a className="button secondary small" href={document.download_url}><Download size={15}/> Descargar versión {document.version}</a>
      </article>)}</div>}
    </div>}
  </section>;
}

export function DocumentReviewQueue() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function load() {
    setBusy(true); setError('');
    try { setData(await api(`documents/review-queue/?page=${page}`)); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, [page]);

  async function review(event, document) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`documents/${document.id}/review/`, { method: 'POST', body: JSON.stringify({ decision: form.get('decision'), observation: form.get('observation'), expires_on: form.get('expires_on') || null }) });
      setData(await api(`documents/review-queue/?page=${page}`));
      setMessage('La revisión quedó registrada.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="panel" aria-busy={busy}>
    <div className="panel-heading"><h2>Revisión documental</h2><button type="button" className="text-button" disabled={busy} onClick={load}><RefreshCw size={15}/> Recargar</button></div>
    <p className="section-description">Revisa el archivo antes de decidir. Cada decisión se registra con tu cuenta y fecha; no puedes revisar tus propios documentos.</p>
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}
    {data?.results.length === 0 && <div className="empty-state"><p>No hay documentos pendientes en esta página.</p></div>}
    {data?.results.map(document => <article className="document-card" key={document.id}>
      <h3>{document.type_name} · Versión {document.version}</h3><p>{document.volunteer_name}</p>
      {document.scan_status !== 'clean' && <p className="help">Sin análisis antimalware: solo para pruebas locales.</p>}
      <a className="button secondary small" href={document.download_url}><Download size={15}/> Descargar para revisar</a>
      <form onSubmit={event => review(event, document)}><fieldset disabled={busy} className="form-fieldset">
        <label className="field">Decisión<select required name="decision" defaultValue=""><option value="" disabled>Selecciona una decisión</option><option value="validated">Validar</option><option value="rejected">Rechazar</option></select></label>
        <label className="field">Observación (obligatoria para rechazar)<textarea name="observation" maxLength={1000} rows={3}/></label>
        <label className="field">Válido hasta (si corresponde)<input type="date" name="expires_on"/></label>
        <button className="button primary" disabled={busy}>Registrar revisión</button>
      </fieldset></form>
    </article>)}
    {data && <div className="form-actions"><button type="button" className="button secondary" disabled={busy || page <= 1} onClick={() => setPage(current => current - 1)}>Anterior</button><span className="help">Página {page} · {data.total} pendientes</span><button type="button" className="button secondary" disabled={busy || page * data.page_size >= data.total} onClick={() => setPage(current => current + 1)}>Siguiente</button></div>}
  </section>;
}
