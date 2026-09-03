// The component set MDX prose is compiled against.
//
// Fenced code blocks are routed through the existing DocCodeGroup so the language toggle,
// highlighting and copy button survive the move from marked to MDX unchanged. Everything else
// inherits the `.markdown-content` rules in globals.css, so typography does not regress either.

import React from "react";
import Link from "next/link";
import { DocCodeGroup } from "@/components/docs/docCodeGroup";
import { ApiEndpoint } from "@/components/docs/apiEndpoint";
import { EventCatalog } from "@/components/docs/eventCatalog";
import { RunStep } from "@/components/docs/runStep";
import { Snippet } from "@/components/docs/snippet";
import { docsRoutePrefix } from "@/lib/docsLoader";

const defaultCodeLanguage = "text";
const languageClassPrefix = "language-";

interface CodeElementProps {
  readonly className?: string;
  readonly children?: React.ReactNode;
}

function readLanguage(className: string | undefined): string {
  if (!className) {
    return defaultCodeLanguage;
  }
  const token = className
    .split(/\s+/)
    .find((candidate) => candidate.startsWith(languageClassPrefix));
  return token ? token.slice(languageClassPrefix.length) : defaultCodeLanguage;
}

function flattenText(node: React.ReactNode): string {
  if (typeof node === "string") {
    return node;
  }
  if (Array.isArray(node)) {
    return node.map(flattenText).join("");
  }
  if (React.isValidElement(node)) {
    return flattenText((node.props as { children?: React.ReactNode }).children);
  }
  return "";
}

// MDX renders a fenced block as <pre><code class="language-x">. The code element carries both
// the language and the source, so the wrapper is unwrapped here rather than styled.
function MdxPre({ children }: { readonly children?: React.ReactNode }): React.JSX.Element {
  const codeElement = React.Children.toArray(children).find((child) =>
    React.isValidElement(child)
  ) as React.ReactElement<CodeElementProps> | undefined;

  if (!codeElement) {
    return <pre>{children}</pre>;
  }

  const language = readLanguage(codeElement.props.className);
  const source = flattenText(codeElement.props.children).replace(/\n$/, "");

  return <DocCodeGroup items={[{ language, code: source }]} />;
}

// Internal links go through next/link so navigating between guides does not reload the shell
// and lose the telemetry stream; external links open in a new tab.
function MdxAnchor({
  href,
  children,
}: {
  readonly href?: string;
  readonly children?: React.ReactNode;
}): React.JSX.Element {
  const target = href ?? "";
  const isInternal = target.startsWith("/") || target.startsWith("#");

  if (isInternal) {
    return <Link href={target}>{children}</Link>;
  }
  return (
    <a href={target} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  );
}

// Tables in these guides are wide (port maps, event catalogs, tax matrices). Without a scroll
// container they force the whole page to scroll sideways.
function MdxTable({ children }: { readonly children?: React.ReactNode }): React.JSX.Element {
  return (
    <div className="overflow-x-auto custom-scrollbar">
      <table>{children}</table>
    </div>
  );
}

// Beyond the HTML overrides above, prose can embed the mesh itself. Each of these reads from
// the same source the running system reads, so a guide that embeds one cannot describe
// something the code no longer does:
//   <ApiEndpoint service=".." path=".." />  -- host and port from meshServiceRegistry
//   <RunStep scenario=".." step=".." />     -- the step definition the driver executes
//   <EventCatalog />                        -- the whole TelemetryEventType union
//   <Snippet file=".." region=".." />       -- a region of a real, runnable program
export const mdxComponents = {
  pre: MdxPre,
  a: MdxAnchor,
  table: MdxTable,
  ApiEndpoint,
  EventCatalog,
  RunStep,
  Snippet,
};

export { docsRoutePrefix };
