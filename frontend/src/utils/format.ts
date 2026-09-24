/** 0.934 → "93%". Whole percentages: more precision would overstate model calibration. */
export function formatConfidence(confidence: number): string {
  const clamped = Math.min(1, Math.max(0, confidence));
  return `${Math.round(clamped * 100)}%`;
}

/** `src/app.py`, `src/app.py:42`, or `src/app.py:42–48`. */
export function formatFileReference(
  file: string,
  lineStart: number | null,
  lineEnd: number | null,
): string {
  if (lineStart === null) return file;
  if (lineEnd === null || lineEnd === lineStart) return `${file}:${lineStart}`;
  return `${file}:${lineStart}–${lineEnd}`;
}

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : dateTimeFormat.format(date);
}

export function shortSha(sha: string): string {
  return sha.slice(0, 7);
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
