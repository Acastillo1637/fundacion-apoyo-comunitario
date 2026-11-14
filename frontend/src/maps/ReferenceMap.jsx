import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import 'leaflet/dist/leaflet.css';

export default function ReferenceMap({ points = [], selected, onSelect, onPick }) {
  const host = useRef(null), instance = useRef(null), layer = useRef(null), actions = useRef({ onSelect, onPick });
  const lastBounds = useRef('');
  const [ready, setReady] = useState(false), [error, setError] = useState('');
  actions.current = { onSelect, onPick };
  useEffect(() => {
    let active = true, resize;
    Promise.all([import('leaflet'), api('maps/config/')]).then(([module, config]) => {
      if (!active || !host.current) return;
      const L = module.default || module;
      const map = L.map(host.current, { scrollWheelZoom: false }).setView([-33.45, -70.66], 10);
      instance.current = { map, L };
      resize = new ResizeObserver(() => map.invalidateSize());
      resize.observe(host.current);
      layer.current = L.layerGroup().addTo(map);
      L.tileLayer(config.tile_url, { maxZoom: config.max_zoom, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' })
        .on('tileerror', () => { if (active) setError('El fondo del mapa no está disponible. Los puntos, coordenadas y distancias siguen utilizables.'); }).addTo(map);
      map.on('click', event => actions.current.onPick?.({ latitude: event.latlng.lat, longitude: event.latlng.lng }));
      setReady(true);
      requestAnimationFrame(() => map.invalidateSize());
    }).catch(() => { if (active) setError('No se pudo cargar el mapa. Usa las coordenadas y el listado.'); });
    return () => { active = false; resize?.disconnect(); instance.current?.map.remove(); instance.current = null; };
  }, []);
  useEffect(() => {
    if (!ready || !instance.current) return;
    const { L, map } = instance.current;
    layer.current.clearLayers();
    const valid = points.filter(p => p.latitude !== null && p.longitude !== null && Number.isFinite(Number(p.latitude)) && Number.isFinite(Number(p.longitude)));
    valid.forEach(p => {
      const label = document.createElement('span');
      label.textContent = p.label || 'Referencia';
      L.circleMarker([Number(p.latitude), Number(p.longitude)], { radius: p.id === selected ? 12 : p.event ? 10 : 7,
        color: p.event ? '#b42318' : p.id === selected ? '#004ddd' : '#087c64', weight: 3, fillOpacity: 0.7 })
        .bindPopup(label).on('click', () => actions.current.onSelect?.(p.id)).addTo(layer.current);
    });
    const key = valid.map(p => `${p.id}:${p.latitude}:${p.longitude}`).join('|');
    if (valid.length && key !== lastBounds.current) {
      map.fitBounds(L.latLngBounds(valid.map(p => [Number(p.latitude), Number(p.longitude)])), { padding: [30, 30], maxZoom: 13 });
      lastBounds.current = key;
    }
  }, [points, selected, ready]);
  return <section className="reference-map" aria-label="Mapa de referencias geográficas"><div ref={host} className="map-canvas"/>{error && <p className="notice" role="status">{error}</p>}<small>© OpenStreetMap contributors · Ubicaciones de voluntarios aproximadas. No se representan rutas.</small></section>;
}
