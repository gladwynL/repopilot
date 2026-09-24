import { useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router';
import { useAuth } from '../features/auth/authContext.ts';
import styles from './AppShell.module.css';
import { BrandMark } from './BrandMark.tsx';
import { Button } from './Button.tsx';
import { Icon } from './Icon.tsx';

export const REPOSITORY_URL = 'https://github.com/gladwynL/repopilot';

const navClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.navLink} ${styles.active}` : styles.navLink;

function UserMenu() {
  const { state, signOut } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  if (state.status !== 'ready' || !state.user) return null;
  const { login, avatar_url: avatarUrl } = state.user;

  return (
    <div className={styles.user}>
      {avatarUrl && <img src={avatarUrl} alt="" width={24} height={24} className={styles.avatar} />}
      <span className={styles.login} title={`Signed in as ${login}`}>
        <span className="visually-hidden">Signed in as </span>
        {login}
      </span>
      <Button
        variant="ghost"
        size="sm"
        loading={signingOut}
        onClick={() => {
          setSigningOut(true);
          void signOut().finally(() => setSigningOut(false));
        }}
      >
        Sign out
      </Button>
    </div>
  );
}

export function AppShell() {
  return (
    <div className={styles.shell}>
      <a href="#main" className={styles.skipLink}>
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link to="/" className={styles.brand} aria-label="RepoPilot dashboard">
            <BrandMark />
            <span className={styles.brandName}>RepoPilot</span>
          </Link>
          <nav aria-label="Main" className={styles.nav}>
            <NavLink to="/" end className={navClassName}>
              Dashboard
            </NavLink>
            <NavLink to="/reviews" className={navClassName}>
              History
            </NavLink>
          </nav>
          <UserMenu />
          <a
            href={REPOSITORY_URL}
            className={styles.repoLink}
            target="_blank"
            rel="noreferrer"
            aria-label="RepoPilot on GitHub (opens in a new tab)"
          >
            <Icon name="github" size={18} />
          </a>
        </div>
      </header>
      <main id="main" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <p>
          RepoPilot produces AI-assisted review suggestions. Findings can be wrong or incomplete —
          verify before acting on them.
        </p>
      </footer>
    </div>
  );
}
