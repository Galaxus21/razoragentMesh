import type { Config } from "tailwindcss";

const tailwindConfig: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bgBase: "rgb(var(--bg-base) / <alpha-value>)",
        bgSurface: "rgb(var(--bg-surface) / <alpha-value>)",
        bgSurfaceHover: "rgb(var(--bg-surface-hover) / <alpha-value>)",
        borderSubtle: "rgb(var(--border-subtle) / <alpha-value>)",
        textPrimary: "rgb(var(--text-primary) / <alpha-value>)",
        textSecondary: "rgb(var(--text-secondary) / <alpha-value>)",
        textMuted: "rgb(var(--text-muted) / <alpha-value>)",
        accentPrimary: "rgb(var(--accent-primary) / <alpha-value>)",
        accentSubtle: "rgb(var(--accent-subtle) / <alpha-value>)",
        statusSuccess: "rgb(var(--status-success) / <alpha-value>)",
        statusWarning: "rgb(var(--status-warning) / <alpha-value>)",
        statusError: "rgb(var(--status-error) / <alpha-value>)",
        statusInfo: "rgb(var(--status-info) / <alpha-value>)",
        primary: "rgb(var(--primary) / <alpha-value>)",
        surfaceContainer: "rgb(var(--surface-container) / <alpha-value>)",
        surfaceContainerHigh: "rgb(var(--surface-container-high) / <alpha-value>)",
        onSurface: "rgb(var(--on-surface) / <alpha-value>)",
        onSurfaceVariant: "rgb(var(--on-surface-variant) / <alpha-value>)",
        outline: "rgb(var(--outline) / <alpha-value>)",
        outlineVariant: "rgb(var(--outline-variant) / <alpha-value>)",
      },
      fontFamily: {
        headline: ["var(--font-headline)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
        dataMono: ["var(--font-mono)", "monospace"],
      },
      fontSize: {
        "headline-lg": ["2rem", { lineHeight: "1.2", fontWeight: "600" }],
        "headline-md": ["1.5rem", { lineHeight: "1.3", fontWeight: "600" }],
        "headline-sm": ["1.125rem", { lineHeight: "1.4", fontWeight: "600" }],
        "body-lg": ["1rem", { lineHeight: "1.6", fontWeight: "400" }],
        "body-md": ["0.875rem", { lineHeight: "1.5", fontWeight: "400" }],
        "body-sm": ["0.8125rem", { lineHeight: "1.5", fontWeight: "400" }],
        "data-mono": ["0.875rem", { lineHeight: "1.5", fontWeight: "400" }],
        "label-caps": ["0.75rem", { lineHeight: "1", fontWeight: "600", letterSpacing: "0.05em" }],
        "label-sm": ["0.75rem", { lineHeight: "1", fontWeight: "500" }],
      },
      spacing: {
        sidebarWidth: "240px",
        sidebarCollapsed: "64px",
        topbarHeight: "56px",
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
        full: "9999px",
      },
      animation: {
        pulseFast: "pulse 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default tailwindConfig;
