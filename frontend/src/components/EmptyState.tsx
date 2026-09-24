import type { ReactNode } from 'react';
import styles from './EmptyState.module.css';
import { Icon, type IconName } from './Icon.tsx';

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  /** Use 'h1' when the empty state is the whole page. */
  titleAs?: 'p' | 'h1' | 'h2';
}

export function EmptyState({
  icon,
  title,
  children,
  action,
  compact = false,
  titleAs: Title = 'p',
}: EmptyStateProps) {
  return (
    <div className={`${styles.empty} ${compact ? styles.compact : ''}`}>
      {icon && (
        <span className={styles.icon}>
          <Icon name={icon} size={compact ? 16 : 20} />
        </span>
      )}
      <Title className={styles.title}>{title}</Title>
      {children && <div className={styles.body}>{children}</div>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
