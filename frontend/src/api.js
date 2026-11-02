let csrfToken = '';
const pendingReads = new Map();

export function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const shareable = method === 'GET' && Object.keys(options).every(key => key === 'method');
  // Share only simultaneous reads. Completed responses are never cached, and
  // mutations (including login/logout) prevent reuse of earlier requests.
  if (method !== 'GET') pendingReads.clear();
  if (!shareable) return sendRequest(path, options);
  if (pendingReads.has(path)) return pendingReads.get(path);
  const pending = sendRequest(path, options).finally(() => {
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
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.method && options.method !== 'GET' ? { 'X-CSRFToken': csrfToken } : {}), ...options.headers },
    });
  } catch {
    throw new Error('No hay conexión con el servidor. Comprueba que Django esté iniciado y vuelve a intentarlo.');
  }
  let data;
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
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
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
