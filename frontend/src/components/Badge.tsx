import type { ReactNode } from 'react';
import styles from './Badge.module.css';

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'severe' | 'danger';

interface BadgeProps {
  tone?: Tone;
  icon?: ReactNode;
  title?: string;
  children: ReactNode;
}

/** Colored label. Always pair color with text (and ideally an icon); never color alone. */
export function Badge({ tone = 'neutral', icon, title, children }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} title={title}>
      {icon}
      {children}
    </span>
  );
}
