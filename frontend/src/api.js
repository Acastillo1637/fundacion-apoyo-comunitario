let csrfToken = '';
const pendingReads = new Map();
const snapshots = new Map();
let generation = 0;

// Only initial display data: api() still fetches on every visit/refresh.
// Keep private responses in memory, bounded and cleared on every mutation.
export function readSnapshot(path) {
  const entry = snapshots.get(path);
  if (!entry || Date.now() - entry.at > 60000) { snapshots.delete(path); return null; }
  return structuredClone(entry.data);
}

function invalidateReads() {
  generation++;
  snapshots.clear();
  pendingReads.clear();
}

export function clearPrivateData() { invalidateReads(); }

export function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const shareable = method === 'GET' && Object.keys(options).every(key => key === 'method');
  // Share only simultaneous reads. Completed responses are never cached, and
  // mutations (including login/logout) prevent reuse of earlier requests.
  if (method !== 'GET') invalidateReads();
  if (!shareable) return method === 'GET' ? sendRequest(path, options) : sendRequest(path, options).finally(invalidateReads);
  if (pendingReads.has(path)) return pendingReads.get(path);
  const startedGeneration = generation;
  const pending = sendRequest(path, options).then(data => {
    if (generation === startedGeneration && path !== 'session/' && !path.startsWith('security/')) {
      if (snapshots.size >= 100) snapshots.delete(snapshots.keys().next().value);
      snapshots.set(path, { data: structuredClone(data), at: Date.now() });
    }
    return data;
  }).finally(() => {
    if (pendingReads.get(path) === pending) pendingReads.delete(path);
  });
  pendingReads.set(path, pending);
  return pending;
}

const labels = {
  skills: 'Habilidades', professions: 'Profesiones', slots: 'Franjas',
  weekday: 'Día', start_time: 'Inicio', end_time: 'Término',
  unavailable_dates: 'Fechas', revision: 'Versión', non_field_errors: '',
};

function describeError(value, prefix = '') {
  if (typeof value === 'string') return `${prefix}${value}`;
  if (Array.isArray(value)) return value.map(item => describeError(item, prefix)).filter(Boolean).join(' ');
  if (value && typeof value === 'object') return Object.entries(value)
    .map(([field, errors]) => describeError(errors, `${prefix}${labels[field] ?? field}${labels[field] === '' ? '' : ': '}`))
    .filter(Boolean).join(' · ');
  return '';
}

async function sendRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api/${path}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.method && options.method !== 'GET' ? { 'X-CSRFToken': csrfToken } : {}), ...options.headers },
    });
  } catch {
    throw new Error('No hay conexión con el servidor. Comprueba que Django esté iniciado y vuelve a intentarlo.');
  }
  let data;
  if ([401, 403].includes(response.status)) invalidateReads();
  try {
    data = await response.json();
  } catch {
    if (response.status === 403) {
      throw new Error('No se pudo validar la seguridad de la sesión. Recarga la página y vuelve a intentarlo.');
    }
    if (response.status >= 500) {
      throw new Error('El servidor no pudo completar la solicitud. Revisa la terminal de Django.');
    }
    throw new Error('El servidor devolvió una respuesta inesperada. Recarga la página y verifica que Django esté iniciado.');
  }
  if (!data || typeof data !== 'object' || (response.ok && Array.isArray(data))) {
    throw new Error('El servidor devolvió una respuesta inesperada. Recarga la página.');
  }
  if (data.csrf_token) csrfToken = data.csrf_token;
  if (!response.ok) {
    const error = new Error(data.detail || describeError(data) || 'No fue posible completar la solicitud.');
    error.continueUrl = data.continue_url;
    error.mfaRequired = data.mfa_required;
    throw error;
  }
  return data;
}
