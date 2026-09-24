import { createContext, useContext } from 'react';
import type { AuthStatus, AuthUser } from '../../types/api.ts';

export type AuthState =
  | { status: 'loading' }
  | { status: 'error'; error: unknown }
  | { status: 'ready'; authEnabled: boolean; user: AuthUser | null };

export interface AuthContextValue {
  state: AuthState;
  retry: () => void;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}

export function toReadyState(status: AuthStatus): AuthState {
  return { status: 'ready', authEnabled: status.auth_enabled, user: status.user };
}
