// <Snippet file="examples/typescript/mandateChain.ts" region="cart" /> -- prose quoting code that
// is compiled and executed rather than code that was pasted.
//
// The distinction matters more than it looks. A fenced block in a guide is a copy; nothing links
// it to the SDK, so it rots quietly and the reader finds out. A region is a view onto a program
// that CI runs on every push, so the same commit that would have made this prose wrong instead
// makes a job go red.
//
// Like <ApiEndpoint>, an unresolvable reference throws instead of rendering an empty box. Doc
// pages are statically generated, so the throw fails `next build` and names the file and region.

import React from "react";
import exampleSnippets from "@/../generated/exampleSnippets.json";
import { DocCodeGroup } from "@/components/docs/docCodeGroup";
import { findExampleRegion, type ExampleSource } from "@/lib/reference/exampleRegions";

const sources = exampleSnippets as readonly ExampleSource[];
const repositoryFilePrefix = "razoragentMesh/";

export interface SnippetProps {
  readonly file: string;
  readonly region: string;
  readonly children?: React.ReactNode;
}

export function Snippet({ file, region, children }: SnippetProps): React.JSX.Element {
  const resolved = findExampleRegion(sources, file, region);

  return (
    <div className="doc-widget my-4">
      {children ? (
        <div className="mb-2 text-body-sm leading-relaxed text-textSecondary">{children}</div>
      ) : null}

      <DocCodeGroup items={[{ language: resolved.language, code: resolved.code }]} />

      <p className="mt-1.5 text-[11px] text-textMuted">
        From{" "}
        <code className="font-mono text-textSecondary">
          {repositoryFilePrefix}
          {file}
        </code>{" "}
        (region <code className="font-mono text-textSecondary">{region}</code>) — compiled and run
        in CI.
      </p>
    </div>
  );
}
