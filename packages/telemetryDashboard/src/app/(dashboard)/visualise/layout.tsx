import React from "react";
import { SectionTabs } from "@/components/sectionTabs";
import { visualiseSectionTabs } from "@/constants/sidebarNavigationConfig";

export default function VisualiseLayout({
  children,
}: {
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="space-y-4">
      <SectionTabs tabs={visualiseSectionTabs} />
      {children}
    </div>
  );
}
