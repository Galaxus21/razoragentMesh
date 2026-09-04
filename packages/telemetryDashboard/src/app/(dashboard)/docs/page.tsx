// The documentation landing page.
//
// /docs had no route at all: the sidebar only ever linked to individual guides, so the bare path
// -- the one a person types, and the one every "see the docs" link in a README wants to point at
// -- returned a 404. Every documentation site worth imitating answers that URL with a map.
//
// The map is built from the same generated manifest the sidebar reads, so a new .mdx file appears
// here by existing. It is grouped by the frontmatter `section` rather than listed flat, because
// the first question a reader has is which of these they are: someone booting the stack, someone
// integrating against it, or someone looking up an exact argument.

import React from "react";
import Link from "next/link";
import type { Metadata } from "next";
import { ArrowRight, BookOpen } from "lucide-react";
import { docsManifest } from "@/generated/docsManifest";
import { groupChildrenBySection } from "@/constants/sidebarNavigationConfig";
import { panelClass } from "@/constants/playgroundConstants";

const pageTitle = "Documentation";
const pageDescription =
  "Everything needed to run the mesh, point an agent at it, sell into it, and look up the exact " +
  "shape of a call. The reference is generated from the schemas the server actually serves.";

/** What each group is for, so the headings are signposts rather than labels. */
const sectionBlurbs: Record<string, string> = {
  "Get started": "Boot the stack and drive a real signed purchase through it.",
  Guides: "Integrate against the protocol as a buyer agent or as a merchant.",
  Reference: "Exact schemas, event shapes and statutory rules. Look-up material, not reading.",
};

export const metadata: Metadata = {
  title: `${pageTitle} — RazorAgent Mesh`,
  description: pageDescription,
};

export default function DocsIndexPage(): React.JSX.Element {
  const groups = groupChildrenBySection(
    docsManifest.map((entry) => ({
      route: entry.route,
      label: entry.navLabel,
      description: entry.navDescription,
      section: entry.section,
    }))
  );

  const byRoute = new Map(docsManifest.map((entry) => [entry.route, entry]));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-accentPrimary" />
          <h2 className="text-headline-sm text-textPrimary">{pageTitle}</h2>
        </div>
        <p className="max-w-3xl text-body-sm leading-relaxed text-textSecondary">
          {pageDescription}
        </p>
      </header>

      {groups.map((group) => (
        <section key={group.section} className="space-y-3">
          <div>
            <h3 className="text-label-caps uppercase tracking-wider text-textMuted">
              {group.section}
            </h3>
            {sectionBlurbs[group.section] && (
              <p className="mt-0.5 text-body-sm text-textSecondary">
                {sectionBlurbs[group.section]}
              </p>
            )}
          </div>

          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {group.items.map((item) => {
              const entry = byRoute.get(item.route);
              return (
                <li key={item.route}>
                  <Link
                    href={item.route}
                    className={`${panelClass} group flex h-full flex-col p-4 transition-colors hover:border-accentPrimary/50`}
                  >
                    <span className="text-label-sm font-semibold text-textPrimary">
                      {item.label}
                    </span>
                    <span className="mt-1 flex-1 text-body-sm text-textSecondary">
                      {entry?.description ?? item.description}
                    </span>
                    <span className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-accentPrimary">
                      Read
                      <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {/* Named so a reader can tell the generated pages from the written ones before trusting
          either. Documentation that claims to be authoritative should say where it came from. */}
      <p className="text-[11px] text-textMuted">
        {groups.length} sections · {docsManifest.length} pages. The Tool
        Reference is generated from the MCP manifest the server returns from{" "}
        <code className="font-mono">tools/list</code>; the rest are written.
      </p>
    </div>
  );
}
