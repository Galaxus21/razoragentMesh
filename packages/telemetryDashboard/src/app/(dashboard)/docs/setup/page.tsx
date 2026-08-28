import React from "react";
import { loadDocContentSync } from "@/lib/docsLoader";
import { MarkdownViewer } from "@/components/docs/markdownViewer";

const pageSlug = "setup";

export default function SetupDocsPage(): React.JSX.Element {
  const doc = loadDocContentSync(pageSlug);

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <MarkdownViewer markdown={doc.markdown} />
    </div>
  );
}
