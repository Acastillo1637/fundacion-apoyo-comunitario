import { useEffect, useRef, useState } from 'react';
import { api, readSnapshot } from '../api';

export default function Notifications({ onNavigate, initialData = null, onUpdate }) {
  const [data, setData] = useState(() => initialData || readSnapshot('activities/notifications/'));
  const [page, setPage] = useState(1), [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const requestId = useRef(0);
  const path = `activities/notifications/?page=${page}&unread_only=${unreadOnly ? '1' : '0'}`;
  async function load(body) {
    const version = ++requestId.current;
    setBusy(true); setError('');
    try {
      const result = await api(path, body ? {method:'POST',body:JSON.stringify(body)} : {});
      if (version !== requestId.current) return;
      setData(result); onUpdate?.(result);
      const last = Math.max(1, Math.ceil(result.total / 30));
      if (page > last) setPage(last);
    } catch (err) { if (version === requestId.current) setError(err.message); }
    finally { if (version === requestId.current) setBusy(false); }
  }
  useEffect(() => {
    setData(readSnapshot(path) || (page === 1 && !unreadOnly ? initialData : null));
    load();
    return () => { requestId.current++; };
  }, [path]);
  return <section className="panel" aria-busy={busy}><div className="panel-heading"><h2>Notificaciones {data ? `(${data.unread} sin leer)` : ''}</h2><div className="actions">
    <button className="button secondary" disabled={busy} onClick={() => load()}>Actualizar</button><button className="button secondary" disabled={busy || !data?.unread} onClick={() => load({read_all:true})}>Marcar todas leídas</button>
  </div></div><label className="checkbox"><input type="checkbox" checked={unreadOnly} disabled={busy} onChange={e => { setUnreadOnly(e.target.checked); setPage(1); }}/>Mostrar solo sin leer</label>
  {error && <p className="error" role="alert">{error}</p>}{busy && <p role="status" className="help">Actualizando notificaciones…</p>}
  {data?.results.length === 0 && <p>{unreadOnly ? 'No tienes notificaciones sin leer.' : 'No tienes notificaciones.'}</p>}
  {data?.results.map(item => <article className="panel" key={item.id}><strong>{!item.read_at ? 'Nueva · ' : ''}{item.message}</strong><p className="help">{new Date(item.created_at).toLocaleString('es-CL',{timeZone:'America/Santiago'})}</p><div className="actions">
    {!item.read_at && <button className="button secondary small" disabled={busy} onClick={() => load({read_id:item.id})}>Marcar leída</button>}
    {item.target && onNavigate && <button className="button secondary small" onClick={() => onNavigate(item.target)}>Ver detalle</button>}
  </div></article>)}
  {data && (data.total > 30 || page > 1) && <nav className="actions" aria-label="Páginas de notificaciones"><button className="button secondary" disabled={busy || page <= 1} onClick={() => setPage(page-1)}>Anterior</button><span>Página {page} de {Math.max(1,Math.ceil(data.total/30))} · {data.total} notificaciones</span><button className="button secondary" disabled={busy || page*30 >= data.total} onClick={() => setPage(page+1)}>Siguiente</button></nav>}
  </section>;
}
