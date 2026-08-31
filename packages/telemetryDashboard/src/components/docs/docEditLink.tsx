import React from "react";
import { FileEdit } from "lucide-react";
import { buildDocSourceUrl } from "@/constants/docsSourceConfig";

export interface DocEditLinkProps {
  readonly sourcePath: string;
}

const editLinkLabel = "Edit this page on GitHub";

export function DocEditLink({ sourcePath }: DocEditLinkProps): React.JSX.Element {
  return (
    <a
      href={buildDocSourceUrl(sourcePath)}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex items-center gap-1.5 text-[11px] text-textMuted transition-colors hover:text-accentPrimary"
    >
      <FileEdit className="h-3.5 w-3.5" />
      {editLinkLabel}
    </a>
  );
}
