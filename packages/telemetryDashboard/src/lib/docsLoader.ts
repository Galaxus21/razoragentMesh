import fs from "node:fs";
import path from "node:path";

export interface DocContent {
  readonly slug: string;
  readonly filename: string;
  readonly markdown: string;
  readonly title: string;
}

const docFilenameMap: Readonly<Record<string, string>> = {
  setup: "SETUP_GUIDE.md",
  onboarding: "DEVELOPER_ONBOARDING_GUIDE.md",
  "buyer-sdk": "BUYER_AGENT_SDK_GUIDE.md",
  "merchant-guide": "MERCHANT_ONBOARDING_GUIDE.md",
  telemetry: "TELEMETRY_OBSERVABILITY_GUIDE.md",
  "gstr1-invoice": "GSTR1_INVOICE_SPECIFICATION.md",
};

const defaultTitleMap: Readonly<Record<string, string>> = {
  setup: "System Setup & Environment Architecture",
  onboarding: "Developer Onboarding & Integration Guide",
  "buyer-sdk": "AI Buyer Agent SDK & AP2 Protocol Guide",
  "merchant-guide": "Merchant Onboarding & Universal SKU Studio",
  telemetry: "Telemetry & SSE Observability Guide",
  "gstr1-invoice": "GSTR-1 Statutory Tax Invoicing Specification",
};

// Package-local only: documentation rendered by this service must live inside the service
// directory. Parent-traversal lookups (`../docs`) break Docker build-context isolation.
function resolveDocsDirectory(): string {
  const currentWorkingDir = process.cwd();
  const candidatePaths = [
    path.resolve(currentWorkingDir, "docs"),
    path.resolve(currentWorkingDir, "src/docs"),
  ];

  for (const candidate of candidatePaths) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return path.resolve(currentWorkingDir, "docs");
}

function extractMarkdownTitle(markdown: string, fallbackTitle: string): string {
  const headingMatch = markdown.match(/^#\s+(.+)$/m);
  if (headingMatch && headingMatch[1]) {
    return headingMatch[1].trim();
  }
  return fallbackTitle;
}

export function loadDocContentSync(slug: string): DocContent {
  const filename = docFilenameMap[slug];
  const fallbackTitle = defaultTitleMap[slug] || "Documentation";

  if (!filename) {
    return {
      slug,
      filename: "not-found.md",
      markdown: "# Documentation Page Not Found\n\nThe requested documentation section does not exist.",
      title: fallbackTitle,
    };
  }

  const docsDir = resolveDocsDirectory();
  const targetPath = path.join(docsDir, filename);

  try {
    const rawMarkdown = fs.readFileSync(targetPath, "utf-8");
    const parsedTitle = extractMarkdownTitle(rawMarkdown, fallbackTitle);
    return {
      slug,
      filename,
      markdown: rawMarkdown,
      title: parsedTitle,
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return {
      slug,
      filename,
      markdown: `# Documentation Unavailable\n\nCould not load \`${filename}\`.\n\nError: ${errorMessage}`,
      title: fallbackTitle,
    };
  }
}

export async function loadDocContent(slug: string): Promise<DocContent> {
  return loadDocContentSync(slug);
}
