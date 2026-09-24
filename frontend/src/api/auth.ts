import type { AuthStatus } from '../types/api.ts';
import { API_BASE_URL, apiRequest } from './client.ts';

export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiRequest<AuthStatus>('/api/auth/me', { signal });
}

export function logout(): Promise<void> {
  return apiRequest<void>('/api/auth/logout', { method: 'POST' });
}

/** Full-page navigation target that starts the GitHub sign-in, returning to `nextPath`. */
export function loginUrl(nextPath: string): string {
  return `${API_BASE_URL}/api/auth/login?next=${encodeURIComponent(nextPath)}`;
}
