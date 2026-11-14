import ReferenceMap from '../maps/ReferenceMap';

export default function CandidateMap({ data, selected, onSelect }) {
  if (!data) return null;
  if (data.event_location?.is_remote) return <section className="panel"><p>Actividad remota: no se calculan distancias ni se muestran referencias personales.</p></section>;
  const points = data.results.filter(row => row.eligible && row.location).map(row => ({ id:row.id, ...row.location,
    label:`${row.name}: ${row.score}/100 · ${row.distance_km === null ? 'distancia no disponible' : `${row.distance_km.toFixed(1)} km aprox. en línea recta`}` }));
  if (data.event_location?.latitude !== null && data.event_location?.latitude !== undefined) points.push({ id:'event', ...data.event_location, event:true, label:'Actividad' });
  return <section className="panel candidate-map"><h2>Referencias de candidatos elegibles</h2><p>{data.distance_notice}</p><ReferenceMap points={points} selected={selected} onSelect={onSelect}/><small>Verde: candidato elegible. Azul: candidato seleccionado. Rojo: actividad. Se muestran los candidatos de esta página.</small></section>;
}

export function CandidateScore({ item }) {
  if (!item.eligible) return null;
  return <div className="candidate-score"><strong>{item.score}/100 · compatibilidad</strong><span>{item.distance_km === null ? 'Sin distancia comparable' : `${item.distance_km.toFixed(1)} km aprox. en línea recta`}</span><ul>{item.recommendation_reasons?.map(reason => <li key={reason}>{reason}</li>)}</ul><small>No es una probabilidad ni asigna un cupo. La selección corresponde a coordinación.</small></div>;
}
