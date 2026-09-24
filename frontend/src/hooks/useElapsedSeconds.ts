import { useEffect, useState } from 'react';

/** Whole seconds since the component mounted (or since `running` became true). */
export function useElapsedSeconds(running = true): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => {
      window.clearInterval(timer);
      setElapsed(0);
    };
  }, [running]);

  return elapsed;
}
