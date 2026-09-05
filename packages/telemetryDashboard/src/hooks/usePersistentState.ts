import { Dispatch, SetStateAction, useEffect, useState } from "react";

/**
 * useState that survives leaving the screen and coming back.
 *
 * Every panel on this dashboard held its results in plain component state, so a click on another
 * Visualise tab discarded them: the Vector Index forgot its search, the two playgrounds forgot
 * the run they had just made, and the Merchant Studio forgot an entire authored SKU. That is
 * fine for a page someone reads once and painful for a demo that moves between screens and
 * comes back to the one it started on.
 *
 * sessionStorage rather than localStorage, deliberately. The scope is the tab: a reload or an
 * accidental navigation keeps the work, while a fresh tab still opens clean, so nobody inherits
 * a stranger's half-filled form. Nothing here is a recording either -- only the results of
 * actions someone actually performed in this tab are ever written.
 *
 * @param storageKey Stable, versioned key. Bump the version when the stored shape changes, so a
 *   value written by an older build is ignored rather than revived into a mismatched type.
 * @param initialValue Used when nothing is stored, or when the stored value cannot be parsed.
 * @param revive Optional normaliser applied to the stored value before it becomes state. Use it
 *   to clear anything that cannot be true on restore -- an in-flight request, for instance.
 */
export function usePersistentState<T>(
  storageKey: string,
  initialValue: T,
  revive?: (stored: T) => T
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(initialValue);

  // Hydration is deferred to an effect rather than done in the useState initialiser, because the
  // server render has no sessionStorage: reading it during render would make the first client
  // render disagree with the server's and trip React's hydration check.
  const [isHydrated, setIsHydrated] = useState<boolean>(false);

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(storageKey);
      if (raw !== null) {
        const parsed = JSON.parse(raw) as T;
        setValue(revive ? revive(parsed) : parsed);
      }
    } catch {
      // A private-mode browser, a cleared quota or a value written by an older build. Falling
      // back to initialValue is always correct, and a panel that cannot restore is not an error
      // worth showing anyone.
    }
    setIsHydrated(true);
    // revive is intentionally not a dependency: it is a normaliser, not an input, and callers
    // define it inline, so depending on it would re-read storage on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  useEffect(() => {
    // Skips the pass before hydration finishes. Without this, the first commit would write
    // initialValue over whatever was stored and defeat the whole hook.
    if (!isHydrated) {
      return;
    }
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(value));
    } catch {
      // Over quota or storage disabled. The panel keeps working in memory.
    }
  }, [storageKey, value, isHydrated]);

  return [value, setValue];
}
