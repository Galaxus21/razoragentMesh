#!/usr/bin/env python3
"""
Verifies that every relative markdown link in documentation targets a file that
exists on disk. Resolves links in README.md, GUIDE.md, docs/*.md,
and packages/telemetryDashboard/docs/*.mdx.

Links are checked for file existence; anchors (path#section) are validated against
the file but not the section. Absolute http(s):// and mailto: links are skipped.

    python scripts/verifyDocLinks.py            # check and report
    python scripts/verifyDocLinks.py --check    # fail if any link is broken

This repository has no CI by choice; the commands above are run by hand.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

# --- Types -------------------------------------------------------------------


@dataclass(frozen=True)
class LinkIssue:
    filePath: Path
    lineNumber: int
    linkText: str
    targetPath: str
    issuekind: str  # "missing_file" or "invalid_path"


# --- Constants ---------------------------------------------------------------

meshRoot: Path = Path(__file__).resolve().parent.parent

documentPaths: List[Path] = [
    meshRoot / "README.md",
    meshRoot / "GUIDE.md",
]

docGlobPatterns: List[Tuple[Path, str]] = [
    (meshRoot / "docs", "*.md"),
    (meshRoot / "packages" / "telemetryDashboard" / "docs", "*.mdx"),
]

# Pattern to match markdown links: [text](url)
# Captures text in group 1, url in group 2
markdownLinkPattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# --- Entry point -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that every relative markdown link targets an existing file."
    )
    parser.add_argument(
        "--check", action="store_true", help="exit non-zero if any link is broken"
    )
    parsedArgs = parser.parse_args()

    allIssues = findBrokenLinks()

    if allIssues:
        for issue in allIssues:
            print(
                f"{issue.filePath}:{issue.lineNumber}: {issue.issuekind}: {issue.linkText} -> {issue.targetPath}",
                file=sys.stderr,
            )
        if parsedArgs.check:
            return 1
    else:
        print("OK: all relative markdown links target existing files.")
        return 0

    return 0


# --- Link checking -----------------------------------------------------------


def findBrokenLinks() -> List[LinkIssue]:
    """Find all broken links in all documentation files."""
    allIssues: List[LinkIssue] = []

    # Check explicit document paths
    for docPath in documentPaths:
        if docPath.exists():
            allIssues.extend(checkFile(docPath))

    # Check files matching glob patterns
    for globDir, globPattern in docGlobPatterns:
        if globDir.exists():
            for matchPath in globDir.glob(globPattern):
                allIssues.extend(checkFile(matchPath))

    return sorted(allIssues, key=lambda x: (x.filePath, x.lineNumber))


def checkFile(filePath: Path) -> List[LinkIssue]:
    """Check all markdown links in a single file."""
    issues: List[LinkIssue] = []

    try:
        content = filePath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"WARNING: could not read {filePath}: {e}", file=sys.stderr)
        return issues

    for lineNumber, line in enumerate(content.splitlines(), start=1):
        for match in markdownLinkPattern.finditer(line):
            linkText = match.group(1)
            url = match.group(2).strip()

            # Skip absolute URLs
            if url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:"):
                continue

            # Skip empty URLs
            if not url:
                continue

            issue = validateLink(filePath, lineNumber, linkText, url)
            if issue:
                issues.append(issue)

    return issues


def validateLink(
    filePath: Path, lineNumber: int, linkText: str, url: str
) -> Optional[LinkIssue]:
    """
    Validate a single link. Returns a LinkIssue if broken, None if OK.
    Handles anchors by checking only the file part.
    """
    # Split off anchor if present
    if "#" in url:
        filePart = url.split("#", 1)[0]
    else:
        filePart = url

    # Skip empty file part (bare anchor)
    if not filePart:
        return None

    # Resolve the target path relative to the document
    targetPath = (filePath.parent / filePart).resolve()

    # Check if target exists
    if not targetPath.exists():
        return LinkIssue(
            filePath=filePath.relative_to(meshRoot),
            lineNumber=lineNumber,
            linkText=linkText,
            targetPath=url,
            issuekind="missing_file",
        )

    return None


# --- Main ---

if __name__ == "__main__":
    sys.exit(main())
