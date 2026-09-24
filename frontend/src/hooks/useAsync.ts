import { useCallback, useEffect, useEffectEvent, useState } from 'react';

export type AsyncState<T> =
  { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: unknown };

interface Settled<T> {
  key: string;
  result: { ok: true; data: T } | { ok: false; error: unknown };
}

/**
 * Load data whenever `key` changes; `retry()` loads again. In-flight requests are aborted when
 * the key changes or the component unmounts, so stale responses never overwrite newer ones.
 * Pass `enabled: false` to skip loading (the state then stays `loading`).
 */
export function useAsync<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: string,
  { enabled = true }: { enabled?: boolean } = {},
): AsyncState<T> & { retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const requestKey = `${key}#${attempt}`;
  const run = useEffectEvent((signal: AbortSignal) => load(signal));

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    run(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setSettled({ key: requestKey, result: { ok: true, data } });
      },
      (error: unknown) => {
        if (!controller.signal.aborted)
          setSettled({ key: requestKey, result: { ok: false, error } });
      },
    );
    return () => controller.abort();
  }, [requestKey, enabled]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  if (settled?.key !== requestKey) return { status: 'loading', retry };
  return settled.result.ok
    ? { status: 'success', data: settled.result.data, retry }
    : { status: 'error', error: settled.result.error, retry };
}
