import styles from './Button.module.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
export type ButtonSize = 'md' | 'sm';

/** Button styling for elements that are not <button>, e.g. router links. */
export function buttonClassName(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md') {
  return [styles.button, styles[variant], styles[size]].join(' ');
}
