// What the drift checker reads out of the guides, and what it reports back.

export type SnippetLanguage = "typescript" | "javascript" | "python";

export interface CodeFence {
  readonly slug: string;
  readonly sourcePath: string;
  // 1-based line of the opening fence in the .mdx file, so a finding is clickable.
  readonly line: number;
  readonly language: SnippetLanguage;
  readonly body: string;
}

// A name the guide uses, resolved back to where it came from. `receiver` is the variable or class
// the member was reached through -- `client` in `client.getLiveSkuQuote()`.
export interface SymbolReference {
  readonly name: string;
  readonly receiver?: string;
  readonly packageName?: string;
}

export interface SnippetFinding {
  readonly sourcePath: string;
  readonly line: number;
  readonly message: string;
}
