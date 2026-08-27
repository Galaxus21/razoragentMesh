"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/appSidebar";
import { DashboardHeader } from "@/components/dashboardHeader";
import { TelemetryProvider, useTelemetry } from "@/context/telemetryContext";
import { useSidebarState } from "@/hooks/useSidebarState";
import { useThemeToggle } from "@/hooks/useThemeToggle";

interface DashboardShellProps {
  readonly children: React.ReactNode;
}

function DashboardShell({ children }: DashboardShellProps): React.JSX.Element {
  const pathname = usePathname();
  const { isCollapsed, toggleSidebar } = useSidebarState();
  const { theme, toggleTheme } = useThemeToggle();
  const telemetry = useTelemetry();

  return (
    <div className="flex min-h-screen bg-bgBase text-textPrimary antialiased">
      <AppSidebar
        isCollapsed={isCollapsed}
        onToggle={toggleSidebar}
        activeRoute={pathname}
      />
      <div className="flex flex-1 flex-col min-w-0 min-h-screen">
        <DashboardHeader
          connectionState={telemetry.connectionState}
          isConnected={telemetry.isConnected}
          totalEventsCount={telemetry.events.length}
          onClearEvents={telemetry.clearEvents}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export default function DashboardGroupLayout({
  children,
}: DashboardShellProps): React.JSX.Element {
  return (
    <TelemetryProvider>
      <DashboardShell>{children}</DashboardShell>
    </TelemetryProvider>
  );
}
