import type { ReactNode } from 'react';
import { ErrorPanel } from '../../components/ErrorPanel.tsx';
import { Spinner } from '../../components/Spinner.tsx';
import { useAuth } from './authContext.ts';
import { SignInPage } from './SignInPage.tsx';
import styles from './Auth.module.css';

/** Shows the app only when auth is disabled or a user is signed in. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { state, retry } = useAuth();

  if (state.status === 'loading') {
    return (
      <div className={styles.center}>
        <Spinner size={20} label="Loading RepoPilot" />
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className={styles.center}>
        <div className={styles.panel}>
          <h1 className="visually-hidden">RepoPilot is unavailable</h1>
          <ErrorPanel error={state.error} onRetry={retry} />
        </div>
      </div>
    );
  }
  if (state.authEnabled && !state.user) return <SignInPage />;
  return <>{children}</>;
}
