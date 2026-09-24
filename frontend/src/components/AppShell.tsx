import { NavLink, Outlet, Link } from 'react-router';
import styles from './AppShell.module.css';
import { Icon } from './Icon.tsx';

export const REPOSITORY_URL = 'https://github.com/gladwynL/repopilot';

function BrandMark() {
  return (
    <svg className={styles.mark} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect width="24" height="24" rx="6" className={styles.markBg} />
      <g fill="none" strokeWidth="1.8" strokeLinecap="round" className={styles.markFg}>
        <circle cx="7.5" cy="6.5" r="1.9" />
        <circle cx="7.5" cy="17.5" r="1.9" />
        <circle cx="16.5" cy="17.5" r="1.9" />
        <path d="M7.5 8.4v7.2M16.5 15.6V11a3 3 0 0 0-3-3h-2.8m0 0 1.8-1.8M10.7 8l1.8 1.8" />
      </g>
    </svg>
  );
}

const navClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.navLink} ${styles.active}` : styles.navLink;

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
