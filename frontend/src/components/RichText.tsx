import styles from './RichText.module.css';

/**
 * Plain text where `backtick spans` become inline code. Model output often uses this Markdown
 * convention; nothing else is interpreted, and the text is never rendered as HTML.
 */
export function RichText({ text }: { text: string }) {
  const parts = text.split(/`([^`\n]+)`/);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <code key={index} className={styles.code}>
            {part}
          </code>
        ) : (
          part
        ),
      )}
    </>
  );
}
