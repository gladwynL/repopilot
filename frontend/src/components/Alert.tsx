import type { ReactNode } from 'react';
import styles from './Alert.module.css';
import { Icon } from './Icon.tsx';

interface AlertProps {
  tone?: 'info' | 'warning' | 'danger';
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}

export function Alert({ tone = 'info', title, children, actions }: AlertProps) {
  return (
    <div
      className={`${styles.alert} ${styles[tone]}`}
      role={tone === 'danger' ? 'alert' : 'status'}
    >
      <Icon name={tone === 'info' ? 'info' : 'alert'} className={styles.icon} />
      <div className={styles.content}>
        <p className={styles.title}>{title}</p>
        {children && <div className={styles.body}>{children}</div>}
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </div>
  );
}
