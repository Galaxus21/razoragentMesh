"use client";

import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "light" | "dark";

export interface UseThemeToggleReturn {
  readonly theme: ThemeMode;
  readonly isDark: boolean;
  readonly toggleTheme: () => void;
  readonly setTheme: (theme: ThemeMode) => void;
}

export const themeStorageKey = "razormesh-theme";
export const themeModeLight: ThemeMode = "light";
export const themeModeDark: ThemeMode = "dark";
const colorSchemeDarkQuery = "(prefers-color-scheme: dark)";
const htmlDarkClassName = "dark";

export function useThemeToggle(): UseThemeToggleReturn {
  const [theme, setThemeState] = useState<ThemeMode>(themeModeDark);

  useEffect(() => {
    const initialTheme = detectInitialTheme();
    setThemeState(initialTheme);
    applyThemeClass(initialTheme);
  }, []);

  const setTheme = useCallback((newTheme: ThemeMode) => {
    setThemeState(newTheme);
    applyThemeClass(newTheme);
    persistTheme(newTheme);
  }, []);

  const toggleTheme = useCallback(() => {
    const targetTheme: ThemeMode = theme === themeModeDark ? themeModeLight : themeModeDark;
    setTheme(targetTheme);
  }, [theme, setTheme]);

  return {
    theme,
    isDark: theme === themeModeDark,
    toggleTheme,
    setTheme,
  };
}

function detectInitialTheme(): ThemeMode {
  try {
    const savedTheme = localStorage.getItem(themeStorageKey) as ThemeMode | null;
    if (savedTheme === themeModeLight || savedTheme === themeModeDark) {
      return savedTheme;
    }
    const prefersDark = window.matchMedia(colorSchemeDarkQuery).matches;
    return prefersDark ? themeModeDark : themeModeLight;
  } catch {
    return themeModeDark;
  }
}

function applyThemeClass(theme: ThemeMode): void {
  if (typeof document === "undefined") {
    return;
  }
  const rootElement = document.documentElement;
  if (theme === themeModeDark) {
    rootElement.classList.add(htmlDarkClassName);
  } else {
    rootElement.classList.remove(htmlDarkClassName);
  }
}

function persistTheme(theme: ThemeMode): void {
  try {
    localStorage.setItem(themeStorageKey, theme);
  } catch {
    // Graceful degradation when localStorage is blocked or restricted
  }
}
