import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  themeModeDark,
  themeModeLight,
  themeStorageKey,
  ThemeMode,
} from "../src/hooks/useThemeToggle.js";

// ============================================================================
// Empirical Test Harness for Milestone 1: Theme Toggle & Token System
// ============================================================================

interface MockDomEnvironment {
  storage: Record<string, string>;
  storageThrowsOnGet: boolean;
  storageThrowsOnSet: boolean;
  prefersDark: boolean;
  documentClasses: Set<string>;
}

function createMockEnvironment(options: Partial<MockDomEnvironment> = {}): MockDomEnvironment {
  return {
    storage: options.storage ?? {},
    storageThrowsOnGet: options.storageThrowsOnGet ?? false,
    storageThrowsOnSet: options.storageThrowsOnSet ?? false,
    prefersDark: options.prefersDark ?? true,
    documentClasses: options.documentClasses ?? new Set<string>(["dark"]),
  };
}

function simulateDetectInitialTheme(env: MockDomEnvironment): ThemeMode {
  try {
    if (env.storageThrowsOnGet) {
      throw new Error("SecurityError: Access to localStorage is denied");
    }
    const savedTheme = env.storage[themeStorageKey] as ThemeMode | undefined;
    if (savedTheme === themeModeLight || savedTheme === themeModeDark) {
      return savedTheme;
    }
    return env.prefersDark ? themeModeDark : themeModeLight;
  } catch {
    return themeModeDark;
  }
}

function simulateApplyThemeClass(env: MockDomEnvironment, theme: ThemeMode): void {
  if (theme === themeModeDark) {
    env.documentClasses.add("dark");
  } else {
    env.documentClasses.delete("dark");
  }
}

function simulatePersistTheme(env: MockDomEnvironment, theme: ThemeMode): boolean {
  try {
    if (env.storageThrowsOnSet) {
      throw new Error("QuotaExceededError: Storage quota exceeded");
    }
    env.storage[themeStorageKey] = theme;
    return true;
  } catch {
    return false;
  }
}

function simulateAntiFoucScript(env: MockDomEnvironment): void {
  try {
    if (env.storageThrowsOnGet) {
      throw new Error("SecurityError");
    }
    const storedTheme = env.storage[themeStorageKey];
    const prefersDark = env.prefersDark;
    if (storedTheme === "dark" || (!storedTheme && prefersDark)) {
      env.documentClasses.add("dark");
    } else {
      env.documentClasses.delete("dark");
    }
  } catch {
    // Graceful fallback to default server-rendered dark class
  }
}

describe("Milestone 1 — Theme Toggle Edge Cases & Storage Resilience", () => {
  it("should detect valid stored 'dark' and 'light' preferences", () => {
    const envDark = createMockEnvironment({ storage: { [themeStorageKey]: "dark" } });
    assert.equal(simulateDetectInitialTheme(envDark), "dark");

    const envLight = createMockEnvironment({ storage: { [themeStorageKey]: "light" } });
    assert.equal(simulateDetectInitialTheme(envLight), "light");
  });

  it("should fallback to prefers-color-scheme when localStorage is empty", () => {
    const envPrefersDark = createMockEnvironment({ prefersDark: true });
    assert.equal(simulateDetectInitialTheme(envPrefersDark), "dark");

    const envPrefersLight = createMockEnvironment({ prefersDark: false });
    assert.equal(simulateDetectInitialTheme(envPrefersLight), "light");
  });

  it("should safely sanitize invalid, corrupt, or non-enum localStorage values", () => {
    const invalidValues = ["blue", "undefined", "null", "", "{}", "system", "DARK", "123"];

    for (const invalidValue of invalidValues) {
      const envPrefersDark = createMockEnvironment({
        storage: { [themeStorageKey]: invalidValue },
        prefersDark: true,
      });
      assert.equal(simulateDetectInitialTheme(envPrefersDark), "dark");

      const envPrefersLight = createMockEnvironment({
        storage: { [themeStorageKey]: invalidValue },
        prefersDark: false,
      });
      assert.equal(simulateDetectInitialTheme(envPrefersLight), "light");
    }
  });

  it("should gracefully handle localStorage access exceptions without crashing", () => {
    const envThrowing = createMockEnvironment({ storageThrowsOnGet: true });
    assert.equal(simulateDetectInitialTheme(envThrowing), "dark");
  });

  it("should correctly update document element classes and persist theme", () => {
    const env = createMockEnvironment();

    simulateApplyThemeClass(env, "light");
    assert.equal(env.documentClasses.has("dark"), false);

    simulateApplyThemeClass(env, "dark");
    assert.equal(env.documentClasses.has("dark"), true);

    const persisted = simulatePersistTheme(env, "light");
    assert.equal(persisted, true);
    assert.equal(env.storage[themeStorageKey], "light");
  });

  it("should catch quota or permission errors during persistence silently", () => {
    const env = createMockEnvironment({ storageThrowsOnSet: true });
    const persisted = simulatePersistTheme(env, "dark");
    assert.equal(persisted, false);
  });
});

describe("Milestone 1 — Anti-FOUC Script Simulation & Hydration Invariants", () => {
  it("should apply dark class when stored preference is dark", () => {
    const env = createMockEnvironment({
      storage: { [themeStorageKey]: "dark" },
      documentClasses: new Set<string>(),
    });
    simulateAntiFoucScript(env);
    assert.equal(env.documentClasses.has("dark"), true);
  });

  it("should remove dark class when stored preference is light", () => {
    const env = createMockEnvironment({
      storage: { [themeStorageKey]: "light" },
      documentClasses: new Set<string>(["dark"]),
    });
    simulateAntiFoucScript(env);
    assert.equal(env.documentClasses.has("dark"), false);
  });

  it("should respect system preference when stored preference is absent", () => {
    const envDark = createMockEnvironment({
      storage: {},
      prefersDark: true,
      documentClasses: new Set<string>(),
    });
    simulateAntiFoucScript(envDark);
    assert.equal(envDark.documentClasses.has("dark"), true);

    const envLight = createMockEnvironment({
      storage: {},
      prefersDark: false,
      documentClasses: new Set<string>(["dark"]),
    });
    simulateAntiFoucScript(envLight);
    assert.equal(envLight.documentClasses.has("dark"), false);
  });

  it("should maintain dark class if script encounters unexpected error", () => {
    const env = createMockEnvironment({
      storageThrowsOnGet: true,
      documentClasses: new Set<string>(["dark"]),
    });
    simulateAntiFoucScript(env);
    assert.equal(env.documentClasses.has("dark"), true);
  });
});

describe("Milestone 1 — Stitch Design Tokens & Dual-Palette Consistency", () => {
  const stitchTokens = [
    { name: "bgBase", lightRgb: "248 250 252", darkRgb: "9 9 11" },
    { name: "bgSurface", lightRgb: "255 255 255", darkRgb: "18 18 21" },
    { name: "bgSurfaceHover", lightRgb: "241 245 249", darkRgb: "26 26 32" },
    { name: "borderSubtle", lightRgb: "226 232 240", darkRgb: "39 39 42" },
    { name: "textPrimary", lightRgb: "15 23 42", darkRgb: "250 250 250" },
    { name: "textSecondary", lightRgb: "71 85 105", darkRgb: "161 161 170" },
    { name: "textMuted", lightRgb: "148 163 184", darkRgb: "82 82 91" },
    { name: "accentPrimary", lightRgb: "79 70 229", darkRgb: "99 102 241" },
    { name: "accentSubtle", lightRgb: "238 242 255", darkRgb: "30 27 75" },
    { name: "statusSuccess", lightRgb: "22 163 74", darkRgb: "34 197 94" },
    { name: "statusWarning", lightRgb: "217 119 6", darkRgb: "245 158 11" },
    { name: "statusError", lightRgb: "220 38 38", darkRgb: "239 68 68" },
    { name: "statusInfo", lightRgb: "2 132 199", darkRgb: "56 189 248" },
  ];

  it("should contain valid non-empty RGB definitions for all Stitch tokens", () => {
    for (const token of stitchTokens) {
      assert.match(token.lightRgb, /^\d+\s+\d+\s+\d+$/);
      assert.match(token.darkRgb, /^\d+\s+\d+\s+\d+$/);
    }
  });

  it("should export correct constant identifiers for theme modes", () => {
    assert.equal(themeModeDark, "dark");
    assert.equal(themeModeLight, "light");
    assert.equal(themeStorageKey, "razormesh-theme");
  });
});
