import React from "react";

// No tab strip: Visualise's five screens are sidebar rows under their category, so the section's
// shape is visible from every page rather than only from inside it.
export default function VisualiseLayout({
  children,
}: {
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return <div className="space-y-4">{children}</div>;
}
