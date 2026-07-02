/** API base URL: direct backend in local dev, nginx /api proxy in production. */
function resolveApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000';
    }
  }
  return '/api';
}

export const API_BASE_URL = resolveApiBaseUrl();
