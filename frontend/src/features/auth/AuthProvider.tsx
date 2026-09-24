import { useCallback, useEffect, useEffectEvent, useMemo, useState, type ReactNode } from 'react';
import { getAuthStatus, logout } from '../../api/auth.ts';
import { UNAUTHORIZED_EVENT } from '../../api/client.ts';
import type { AuthStatus } from '../../types/api.ts';
import { AuthContext, toReadyState, type AuthState } from './authContext.ts';

interface AuthProviderProps {
  children: ReactNode;
  /** Skip the initial request (tests, or when the status is already known). */
  initialStatus?: AuthStatus;
  loadStatus?: (signal: AbortSignal) => Promise<AuthStatus>;
}

export function AuthProvider({
  children,
  initialStatus,
  loadStatus = getAuthStatus,
}: AuthProviderProps) {
  const [state, setState] = useState<AuthState>(
    initialStatus ? toReadyState(initialStatus) : { status: 'loading' },
  );
  const [attempt, setAttempt] = useState(0);
  const load = useEffectEvent((signal: AbortSignal) => loadStatus(signal));

  useEffect(() => {
    if (initialStatus && attempt === 0) return;
    const controller = new AbortController();
    load(controller.signal).then(
      (status) => {
        if (!controller.signal.aborted) setState(toReadyState(status));
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setState({ status: 'error', error });
      },
    );
    return () => controller.abort();
  }, [attempt, initialStatus]);

  // Any 401 from the API means the session is gone: show the sign-in screen.
  useEffect(() => {
    const onUnauthorized = () =>
      setState((current) =>
        current.status === 'ready' && current.authEnabled ? { ...current, user: null } : current,
      );
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((n) => n + 1);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      // Even if the request fails, forget the user locally; the server session expires anyway.
      setState((current) => (current.status === 'ready' ? { ...current, user: null } : current));
    }
  }, []);

  const value = useMemo(() => ({ state, retry, signOut }), [state, retry, signOut]);
  return <AuthContext value={value}>{children}</AuthContext>;
}
