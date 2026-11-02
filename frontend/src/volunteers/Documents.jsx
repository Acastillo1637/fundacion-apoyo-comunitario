import { useEffect, useState } from 'react';
import { Download, FileCheck2, RefreshCw, Upload } from 'lucide-react';
import { api } from '../api';
import { Avatar } from '../design/Overview';

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
  const [data, setData] = useState(null), [page, setPage] = useState(1), [selectedId, setSelectedId] = useState(null), [filter, setFilter] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  async function load() { setBusy(true); setError(''); try { setData(await api(`documents/review-queue/?page=${page}`)); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  useEffect(() => { setSelectedId(null); load(); }, [page]);
  const rows = data?.results.filter(item => `${item.volunteer_name} ${item.type_name}`.toLocaleLowerCase('es').includes(filter.toLocaleLowerCase('es'))) || [];
  const selected = rows.find(item => item.id === selectedId) || rows[0];
  async function review(event, document) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError(''); setMessage('');
    try { await api(`documents/${document.id}/review/`, { method: 'POST', body: JSON.stringify({ decision: form.get('decision'), observation: form.get('observation'), expires_on: form.get('expires_on') || null }) }); await load(); setMessage('La revisión quedó registrada con tu cuenta y fecha.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="document-review-page" aria-busy={busy}><div className="review-stat-strip"><FileCheck2 size={30}/><strong>{data?.total || 0}</strong><div><h3>Pendientes de revisión</h3><small>Se revisa la versión más reciente de cada documento.</small></div><button type="button" className="text-button" disabled={busy} onClick={load}><RefreshCw size={15}/> Actualizar</button></div>
    <section className="panel directory-toolbar"><label className="field">Buscar en la página actual<input value={filter} maxLength={100} onChange={event => setFilter(event.target.value)} placeholder="Nombre o tipo de documento"/></label></section>
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}{!data && !error && <p role="status">Cargando expedientes…</p>}
    <div className="document-review-columns"><section><div className="section-heading-inline"><h2>Expedientes en espera</h2><span className="tag">{rows.length} en esta página</span></div>{rows.map(document => <button key={document.id} className={`document-queue-item ${selected?.id === document.id ? 'active' : ''}`} onClick={() => setSelectedId(document.id)}><Avatar name={document.volunteer_name}/><div><h3>{document.volunteer_name || 'Voluntario'}</h3><p>{document.type_name}</p><small>Versión {document.version} · {formatDate(document.uploaded_at)}</small></div></button>)}{data && rows.length === 0 && <div className="panel empty-state"><FileCheck2 size={30}/><p>No hay documentos pendientes con estos criterios.</p></div>}{data && <div className="form-actions"><button className="button secondary small" disabled={busy || page <= 1} onClick={() => setPage(page - 1)}>Anterior</button><small>Página {page}</small><button className="button secondary small" disabled={busy || page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>Siguiente</button></div>}</section>
    <section>{selected ? <><div className="panel"><div className="panel-heading"><h2><FileCheck2 size={22}/> Visor documental</h2><span className="tag">Versión {selected.version}</span></div><p>{selected.type_name} · {selected.volunteer_name}</p><a className="button secondary small" href={selected.download_url}><Download size={15}/> Descargar archivo</a>{selected.scan_status !== 'clean' && <p className="help">Entorno de pruebas: sin análisis antimalware.</p>}<DocumentPreview key={selected.id} document={selected}/></div><div className="panel review-decision-panel"><h2>Dictamen de revisión</h2><p>Revisa el documento antes de decidir. No puedes revisar archivos propios.</p><form key={selected.id} onSubmit={event => review(event, selected)}><fieldset className="form-fieldset" disabled={busy}><div className="form-row"><label className="field">Decisión<select name="decision" required defaultValue=""><option value="" disabled>Selecciona una decisión</option><option value="validated">Aprobar documento</option><option value="rejected">Observar / rechazar</option></select></label><label className="field">Válido hasta (si corresponde)<input type="date" name="expires_on"/></label></div><label className="field">Observación (obligatoria al rechazar)<textarea name="observation" rows={3} maxLength={1000}/></label><button className="button primary" disabled={busy}><FileCheck2 size={17}/> Registrar decisión</button></fieldset></form></div></> : <div className="panel document-preview-empty"><FileCheck2 size={45}/><h2>Tu próxima revisión empieza aquí</h2><p>Selecciona un expediente para consultar el archivo y registrar una decisión.</p></div>}</section></div></section>;
}

function DocumentPreview({ document }) {
  const [preview, setPreview] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController(); let objectUrl;
    fetch(document.download_url, { credentials: 'same-origin', signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('No se pudo cargar la vista previa. Usa la descarga para revisar el archivo.');
      const blob = await response.blob();
      if (!['application/pdf', 'image/png', 'image/jpeg'].includes(blob.type)) throw new Error('Vista previa no disponible para este formato.');
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob); setPreview({ url: objectUrl, type: blob.type });
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [document.download_url]);
  return <div style={{ marginTop: 20 }}>{error ? <p className="error" role="alert">{error}</p> : !preview ? <p role="status">Cargando archivo privado…</p> : preview.type === 'application/pdf' ? <iframe className="document-viewer" src={preview.url} title={`Documento: ${document.type_name}`}/> : <img className="document-image-preview" src={preview.url} alt={`Documento para revisión: ${document.type_name}`}/>}</div>;
}
