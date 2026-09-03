#!/usr/bin/env python3
"""
Measures two structural properties of the Python test suite: how much of it asserts
something specific, and how much of it is the same test shape written out again.

These are the two usual explanations for a large test count meaning little, and both
are cheap to check, so `docs/TEST_QUALITY_AUDIT.md` checks them rather than assuming.

Rule V-01 (verification-standards.md) requires the command beside the claim. Both
figures move with their definition, so the definitions are stated here and the
report cites this script rather than a bare percentage:

  weak assertion   the asserted expression is a bare name, an `is`/`is not None`
                   comparison, an `isinstance(...)` call, or a `len(...)` compared
                   against something -- each says "something came back" rather than
                   "this exact value came back"

  duplicate shape  two test functions whose bodies are identical once every
                   identifier, attribute name and constant is blanked; counted as
                   the copies beyond the first in each group

Neither is a defect on its own. A bare `assert isinstance(...)` after a specific
assertion is fine, and a duplicated shape is often parametrisation written longhand.
They are here to size the problem, not to name offenders.
"""

import argparse
import ast
import sys
from dataclasses import dataclass, field
from collections import Counter
from pathlib import Path
from typing import List, Tuple

# --- Constants ---------------------------------------------------------------

meshRoot: Path = Path(__file__).resolve().parent.parent

testRootPaths: Tuple[str, ...] = ("tests", "packages/buyerSdkPy/tests")
testFileGlob: str = "test*.py"
testFunctionPrefix: str = "test"

blankedName: str = "_"
blankedConstant: int = 0
isinstanceName: str = "isinstance"
lengthName: str = "len"


# --- Types -------------------------------------------------------------------


@dataclass
class ScanTotals:
    """Everything the scan counts, across every file it read."""

    fileCount: int = 0
    functionCount: int = 0
    assertCount: int = 0
    weakAssertCount: int = 0
    bodyShapes: Counter = field(default_factory=Counter)

    @property
    def duplicateCount(self) -> int:
        """Test bodies that repeat a shape already seen, beyond the first of each."""
        return sum(count - 1 for count in self.bodyShapes.values() if count > 1)

    def percentageOfAsserts(self, count: int) -> float:
        return 100.0 * count / self.assertCount if self.assertCount else 0.0

    def percentageOfFunctions(self, count: int) -> float:
        return 100.0 * count / self.functionCount if self.functionCount else 0.0


# --- Assertion strength ------------------------------------------------------


def isWeakAssertion(assertedExpression: ast.expr) -> bool:
    """True when the assertion pins existence or type rather than a value."""
    if isinstance(assertedExpression, ast.Name):
        return True
    if isinstance(assertedExpression, ast.Call):
        return (
            isinstance(assertedExpression.func, ast.Name)
            and assertedExpression.func.id == isinstanceName
        )
    if isinstance(assertedExpression, ast.Compare):
        return _isWeakComparison(assertedExpression)
    return False


def _isWeakComparison(comparison: ast.Compare) -> bool:
    """`x is None`, `x is not None`, and any comparison of a `len(...)`."""
    if any(isinstance(operator, (ast.Is, ast.IsNot)) for operator in comparison.ops):
        return any(
            isinstance(comparator, ast.Constant) and comparator.value is None
            for comparator in comparison.comparators
        )
    return (
        isinstance(comparison.left, ast.Call)
        and isinstance(comparison.left.func, ast.Name)
        and comparison.left.func.id == lengthName
    )


# --- Structural duplication --------------------------------------------------


class ShapeBlanker(ast.NodeTransformer):
    """Erases identifiers, attributes and constants, leaving only statement shape."""

    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.copy_location(ast.Name(id=blankedName, ctx=node.ctx), node)

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return ast.copy_location(ast.Constant(value=blankedConstant), node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        self.generic_visit(node)
        return ast.copy_location(
            ast.Attribute(value=node.value, attr=blankedName, ctx=node.ctx), node
        )


def bodyShape(functionNode: ast.AST) -> str:
    """A canonical string for a test body with every name and value removed."""
    bodyModule = ast.Module(body=list(functionNode.body), type_ignores=[])
    reparsed = ast.parse(ast.unparse(bodyModule))
    return ast.dump(ShapeBlanker().visit(reparsed))


# --- Scan --------------------------------------------------------------------


def scanTestTree() -> ScanTotals:
    """Reads every test module under the configured roots and counts both measures."""
    totals = ScanTotals()
    for testRoot in testRootPaths:
        for path in sorted((meshRoot / testRoot).rglob(testFileGlob)):
            totals.fileCount += 1
            _scanModule(ast.parse(path.read_text(encoding="utf-8")), totals)
    return totals


def _scanModule(tree: ast.AST, totals: ScanTotals) -> None:
    """Folds one parsed test module into the running totals."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            totals.assertCount += 1
            totals.weakAssertCount += int(isWeakAssertion(node.test))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith(testFunctionPrefix):
                totals.functionCount += 1
                totals.bodyShapes[bodyShape(node)] += 1


def renderReport(totals: ScanTotals) -> List[str]:
    """The measured lines, in the order the audit document quotes them."""
    duplicates = totals.duplicateCount
    return [
        f"test files scanned     : {totals.fileCount}",
        f"test functions         : {totals.functionCount}",
        f"assert statements      : {totals.assertCount}",
        f"weak assertions        : {totals.weakAssertCount} "
        f"({totals.percentageOfAsserts(totals.weakAssertCount):.1f}% of asserts)",
        f"duplicate-shape bodies : {duplicates} "
        f"({totals.percentageOfFunctions(duplicates):.1f}% of test functions)",
    ]


def main() -> int:
    argparse.ArgumentParser(
        description="Measure assertion strength and structural duplication."
    ).parse_args()
    for line in renderReport(scanTestTree()):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
