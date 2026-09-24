import { useLocation } from 'react-router';
import { loginUrl } from '../../api/auth.ts';
import { Alert } from '../../components/Alert.tsx';
import { BrandMark } from '../../components/BrandMark.tsx';
import { buttonClassName } from '../../components/buttonClassName.ts';
import { Icon } from '../../components/Icon.tsx';
import styles from './Auth.module.css';

const AUTH_ERRORS: Record<string, { title: string; message: string }> = {
  not_allowed: {
    title: 'This GitHub account is not allowed',
    message: 'Access to this RepoPilot deployment is limited to approved GitHub accounts.',
  },
  access_denied: {
    title: 'Sign-in was cancelled',
    message: 'GitHub did not authorize RepoPilot. You can try again.',
  },
  invalid_state: {
    title: 'Sign-in expired',
    message: 'The sign-in attempt expired or could not be verified. Please try again.',
  },
  github_error: {
    title: 'GitHub sign-in failed',
    message: 'RepoPilot could not verify your GitHub account. Please try again.',
  },
};

export function SignInPage() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const errorCode = params.get('auth_error');
  const error = errorCode ? (AUTH_ERRORS[errorCode] ?? AUTH_ERRORS.github_error) : null;
  params.delete('auth_error');
  const search = params.toString();
  const returnTo = `${location.pathname}${search ? `?${search}` : ''}`;

  return (
    <main className={styles.center}>
      <title>Sign in — RepoPilot</title>
      <div className={styles.panel}>
        <div className={styles.brand}>
          <BrandMark size={40} />
          <span>RepoPilot</span>
        </div>
        <h1 className={styles.title}>Sign in to RepoPilot</h1>
        <p className={styles.lead}>
          AI-assisted review of GitHub pull requests. Sign in with GitHub to run reviews and browse
          review history.
        </p>
        {error && (
          <div className={styles.alert}>
            <Alert tone="warning" title={error.title}>
              {error.message}
            </Alert>
          </div>
        )}
        <a href={loginUrl(returnTo)} className={`${buttonClassName('primary')} ${styles.cta}`}>
          <Icon name="github" size={18} />
          Sign in with GitHub
        </a>
        <p className={styles.note}>
          RepoPilot only reads your public GitHub profile to confirm who you are. Access is limited
          to approved accounts.
        </p>
      </div>
    </main>
  );
}
