import type { Metadata } from "next";
import React from "react";
import { Geist_Mono, Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-headline",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-mono",
  display: "swap",
});

const themeInitScriptContent = `(function(){try{var t=localStorage.getItem('razormesh-theme');var p=window.matchMedia('(prefers-color-scheme: dark)').matches;if(t==='dark'||(!t&&p)){document.documentElement.classList.add('dark');}else{document.documentElement.classList.remove('dark');}}catch(e){}})();`;

// The mark is declared rather than left to the browser's implicit /favicon.ico probe, so the SVG
// is preferred where it is supported and the tab icon matches the one in the sidebar.
export const metadata: Metadata = {
  title: "RazorAgent Mesh",
  description: "Live telemetry for autonomous agent purchases settled on Razorpay rails.",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.png", type: "image/png", sizes: "32x32" },
    ],
    shortcut: "/favicon.ico",
  },
};

export interface RootLayoutProps {
  readonly children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps): React.JSX.Element {
  return (
    <html
      lang="en"
      className={`dark ${plusJakartaSans.variable} ${inter.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          id="theme-init-script"
          dangerouslySetInnerHTML={{
            __html: themeInitScriptContent,
          }}
        />
      </head>
      <body className="bg-bgBase text-textPrimary font-body antialiased selection:bg-accentPrimary/20 selection:text-accentPrimary min-h-screen">
        {children}
      </body>
    </html>
  );
}
