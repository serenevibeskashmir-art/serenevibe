const TOKEN_KEY = 'adminToken';

export function getAdminToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAdminToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAdminToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(extra = {}) {
  const token = getAdminToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

export async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
  return response;
}

export async function adminLogin(password) {
  const response = await fetch('/api/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || 'Login failed');
  }
  setAdminToken(result.token);
  return result;
}

export async function verifyAdminSession() {
  const token = getAdminToken();
  if (!token) return false;
  const response = await apiFetch('/api/admin/verify');
  return response.ok;
}

export async function sendItineraryEmailApi(itineraryData) {
  const response = await apiFetch('/api/email/send', {
    method: 'POST',
    body: JSON.stringify(itineraryData),
  });
  if (!response.ok) {
    throw new Error(`Server status: ${response.status}`);
  }
  return response.json();
}
