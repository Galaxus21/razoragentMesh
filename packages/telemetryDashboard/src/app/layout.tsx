import type { Metadata } from "next";
import React from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "RazorAgent Mesh | Real-Time Telemetry & Settlement Enclave",
  description: "Autonomous M2M Settlement & Cryptographic Telemetry Enclave on Razorpay Rails",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.JSX.Element {
  return (
    <html lang="en" className="dark">
      <body className="bg-meshDarkBg text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
