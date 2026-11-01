let csrfToken = '';

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

export async function api(path, options = {}) {
  const response = await fetch(`/api/${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.method && options.method !== 'GET' ? { 'X-CSRFToken': csrfToken } : {}), ...options.headers },
  });
  const data = await response.json().catch(() => ({ detail: 'No fue posible leer la respuesta del servidor.' }));
  if (data.csrf_token) csrfToken = data.csrf_token;
  if (!response.ok) {
    const error = new Error(data.detail || describeError(data) || 'No fue posible completar la solicitud.');
    error.continueUrl = data.continue_url;
    throw error;
  }
  return data;
}
