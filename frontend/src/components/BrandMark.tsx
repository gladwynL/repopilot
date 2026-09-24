import styles from './BrandMark.module.css';

/** RepoPilot logo: a pull-request glyph on a rounded tile. Decorative (label the parent). */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg
      className={styles.mark}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="24" height="24" rx="6" className={styles.bg} />
      <g fill="none" strokeWidth="1.8" strokeLinecap="round" className={styles.fg}>
        <circle cx="7.5" cy="6.5" r="1.9" />
        <circle cx="7.5" cy="17.5" r="1.9" />
        <circle cx="16.5" cy="17.5" r="1.9" />
        <path d="M7.5 8.4v7.2M16.5 15.6V11a3 3 0 0 0-3-3h-2.8m0 0 1.8-1.8M10.7 8l1.8 1.8" />
      </g>
    </svg>
  );
}
