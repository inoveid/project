import { useCallback, useRef } from "react";

/**
 * Debounced auto-save hook. Calls `saveFn` after `delayMs` of inactivity.
 * Returns a `schedule` function to trigger the debounce.
 * Call `flush` to save immediately (e.g. on blur).
 */
export function useAutoSave(saveFn: () => void, delayMs = 500) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveFnRef = useRef(saveFn);
  saveFnRef.current = saveFn;

  const cancel = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const schedule = useCallback(() => {
    cancel();
    timerRef.current = setTimeout(() => {
      saveFnRef.current();
      timerRef.current = null;
    }, delayMs);
  }, [cancel, delayMs]);

  const flush = useCallback(() => {
    if (timerRef.current !== null) {
      cancel();
      saveFnRef.current();
    }
  }, [cancel]);

  return { schedule, flush, cancel };
}
