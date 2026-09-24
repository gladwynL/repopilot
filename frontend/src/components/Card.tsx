import type { ReactNode } from 'react';
import styles from './Card.module.css';

interface CardProps {
  children: ReactNode;
  className?: string;
  as?: 'section' | 'div' | 'article';
  'aria-labelledby'?: string;
}

export function Card({ children, className, as: Tag = 'div', ...rest }: CardProps) {
  return (
    <Tag className={[styles.card, className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </Tag>
  );
}

interface SectionCardProps {
  id: string;
  title: string;
  /** Short text next to the title, e.g. a count. */
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}

/** A card with a titled header; the title labels the section for assistive tech. */
export function SectionCard({ id, title, meta, actions, children }: SectionCardProps) {
  return (
    <Card as="section" aria-labelledby={id}>
      <header className={styles.header}>
        <h2 id={id} className={styles.title}>
          {title}
          {meta !== undefined && <span className={styles.meta}>{meta}</span>}
        </h2>
        {actions && <div className={styles.actions}>{actions}</div>}
      </header>
      <div className={styles.body}>{children}</div>
    </Card>
  );
}
