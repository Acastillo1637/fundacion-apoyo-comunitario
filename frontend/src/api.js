let csrfToken = '';

export async function api(path, options = {}) {
  const response = await fetch(`/api/${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.method && options.method !== 'GET' ? { 'X-CSRFToken': csrfToken } : {}), ...options.headers },
  });
  const data = await response.json().catch(() => ({ detail: 'No fue posible leer la respuesta del servidor.' }));
  if (data.csrf_token) csrfToken = data.csrf_token;
  if (!response.ok) {
    const error = new Error(data.detail || Object.entries(data).map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(' ') : errors}`).join(' · '));
    error.continueUrl = data.continue_url;
    throw error;
  }
  return data;
}
