import type { Severity } from '../../types/api.ts';

interface LevelGlyphProps {
  level: Severity | null;
  className?: string;
}

/**
 * A distinct shape per level (circle, triangle, filled triangle, octagon; dashed circle when
 * not assessed) so levels are distinguishable without relying on color.
 */
export function LevelGlyph({ level, className }: LevelGlyphProps) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
      {level === null && (
        <circle
          cx="8"
          cy="8"
          r="6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeDasharray="2.4 2"
        />
      )}
      {level === 'low' && (
        <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      )}
      {level === 'medium' && (
        <path
          d="M8 2 14.5 13.5h-13L8 2Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
      )}
      {level === 'high' && <path d="M8 1.5 15 14H1L8 1.5Z" fill="currentColor" />}
      {level === 'critical' && (
        <path d="M5.3 1.5h5.4l3.8 3.8v5.4l-3.8 3.8H5.3l-3.8-3.8V5.3l3.8-3.8Z" fill="currentColor" />
      )}
      {(level === 'high' || level === 'critical') && (
        <path
          d="M8 5.5v3.5M8 11.2v.1"
          stroke="var(--surface)"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}
