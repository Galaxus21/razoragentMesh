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
        meshDarkBg: "#090d16",
        meshDarkSurface: "#0f172a",
        meshDarkCard: "#131d33",
        meshDarkBorder: "#1e293b",
        meshTealPrimary: "#06b6d4",
        meshTealGlow: "#22d3ee",
        meshPurplePrimary: "#8b5cf6",
        meshPurpleGlow: "#a78bfa",
        meshEmeraldSuccess: "#10b981",
        meshRoseAlert: "#f43f5e",
        meshAmberWarning: "#f59e0b",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      animation: {
        pulseFast: "pulse 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        glowPulse: "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(6, 182, 212, 0.2)" },
          "100%": { boxShadow: "0 0 20px rgba(6, 182, 212, 0.6)" },
        },
      },
    },
  },
  plugins: [],
};

export default tailwindConfig;
