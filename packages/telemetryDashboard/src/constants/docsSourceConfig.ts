// Where the .mdx sources for these guides live, so a reader who spots an error can open the
// exact file rather than hunting for it.
//
// The repository URL is the one `git remote get-url origin` reports for this checkout. The
// branch defaults to the repository's default branch -- which is what an "edit this page" link
// should target, since that is where a correction has to land -- and can be pointed at a
// working branch with DOCS_SOURCE_BRANCH when previewing unmerged docs.

export const docsRepositoryUrl = "https://github.com/Galaxus21/razorAgentMesh";
export const docsDefaultBranch = "main";

export const docsSourceBranch = process.env.DOCS_SOURCE_BRANCH ?? docsDefaultBranch;

// sourcePath on a DocPage is already repository-relative (packages/telemetryDashboard/docs/..),
// so it slots straight into GitHub's blob URL without further joining.
export function buildDocSourceUrl(sourcePath: string): string {
  return `${docsRepositoryUrl}/blob/${docsSourceBranch}/${sourcePath}`;
}
