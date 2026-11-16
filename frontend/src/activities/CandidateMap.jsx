import ReferenceMap from '../maps/ReferenceMap';

export function candidatePoints(data, eligibleOnly = false) {
  if (!data || data.event_location?.is_remote) return [];
  const points = data.results.filter(row => row.location && (!eligibleOnly || row.eligible)).map(row => ({ id:row.id, ...row.location, eligible:row.eligible,
    label:`${row.name}: ${row.eligible ? `${row.score}/100` : 'No elegible para esta función'} · ${row.distance_km === null ? 'distancia no disponible' : `${row.distance_km.toFixed(1)} km aprox. en línea recta`}` }));
  if (data.event_location?.latitude !== null && data.event_location?.latitude !== undefined) points.push({ id:'event', ...data.event_location, event:true, label:'Actividad' });
  return points;
}

export default function CandidateMap({ data, selected, onSelect, eligibleOnly = false }) {
  if (!data) return null;
  if (data.event_location?.is_remote) return <section className="panel"><p>Actividad remota: no se calculan distancias ni se muestran referencias personales.</p></section>;
  const missing = data.results.filter(row => (!eligibleOnly || row.eligible) && !row.location).length;
  return <section className="panel candidate-map"><h2>Referencias de candidatos</h2><p>{data.distance_notice}</p><ReferenceMap points={candidatePoints(data, eligibleOnly)} selected={selected} onSelect={onSelect}/>{missing > 0 && <p className="help">{missing} perfiles de esta página no tienen ubicación registrada y no pueden mostrarse en el mapa.</p>}<small>Verde: elegible. Ámbar: no elegible. Azul: seleccionado. Rojo: actividad. Se muestran los candidatos de esta página con ubicación registrada.</small></section>;
}

export function CandidateScore({ item }) {
  if (!item.eligible) return null;
  return <div className="candidate-score"><strong>{item.score}/100 · compatibilidad</strong><span>{item.distance_km === null ? 'Sin distancia comparable' : `${item.distance_km.toFixed(1)} km aprox. en línea recta`}</span><ul>{item.recommendation_reasons?.map(reason => <li key={reason}>{reason}</li>)}</ul><small>No es una probabilidad ni asigna un cupo. La selección corresponde a coordinación.</small></div>;
}
