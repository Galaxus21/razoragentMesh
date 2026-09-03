"""The mutation catalogue and the machinery for applying one mutation at a time.

A deliberately generic operator set. It is NOT a list of the defects the audit
already found by reading -- seeding known bugs would flatter the score. These are
the standard operators, and they ask one question wherever they land: does any test
pin this comparison, this arithmetic step, this guard, this returned value?
"""

import ast
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --- Types -------------------------------------------------------------------


@dataclass(frozen=True)
class Mutant:
    """A single seeded defect: one operator applied at one site."""

    modulePath: str
    siteIndex: int
    lineNumber: int
    operatorName: str
    beforeText: str
    afterText: str


# --- Operator catalogue ------------------------------------------------------

comparisonSwaps: Dict[type, type] = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}

arithmeticSwaps: Dict[type, type] = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult,
    ast.Div: ast.Mult, ast.Mod: ast.FloorDiv,
    ast.Pow: ast.Mult,
}

booleanSwaps: Dict[type, type] = {ast.And: ast.Or, ast.Or: ast.And}

statementListFields: Tuple[str, ...] = ("body", "orelse", "finalbody")

opComparison: str = "comparison-flip"
opArithmetic: str = "arithmetic-swap"
opBoolean: str = "boolean-swap"
opNegateCondition: str = "negate-condition"
opConstantOffset: str = "constant-offset"
opBooleanConstant: str = "boolean-constant-flip"
opRemoveGuard: str = "remove-guard"
opReturnValue: str = "return-value-replacement"

snippetLengthLimit: int = 90

typeCheckingGuardName: str = "TYPE_CHECKING"

Candidate = Tuple[int, str, object]


# --- Enumeration -------------------------------------------------------------


def collectCandidates(tree: ast.AST) -> List[Candidate]:
    """Enumerates every mutation site in a stable order.

    `ast.walk` is breadth-first and deterministic, so a site is addressed by its
    index in that walk. Re-parsing the same source always reproduces the same
    indices, which is what lets one candidate be applied to an otherwise clean tree.
    """
    candidates: List[Candidate] = []
    for walkIndex, node in enumerate(ast.walk(tree)):
        candidates.extend(
            (walkIndex, operatorName, detail)
            for operatorName, detail in _expressionCandidates(node)
        )
        candidates.extend(
            (walkIndex, opRemoveGuard, detail) for detail in _guardCandidates(node)
        )
    return candidates


def _expressionCandidates(node: ast.AST) -> List[Tuple[str, object]]:
    """Mutation sites carried by the node itself."""
    if isinstance(node, ast.Compare):
        return [
            (opComparison, opIndex)
            for opIndex, op in enumerate(node.ops)
            if type(op) in comparisonSwaps
        ]
    if isinstance(node, ast.BinOp) and type(node.op) in arithmeticSwaps:
        return [(opArithmetic, None)]
    if isinstance(node, ast.BoolOp) and type(node.op) in booleanSwaps:
        return [(opBoolean, None)]
    if isinstance(node, ast.If):
        return [] if _isTypeCheckingGuard(node) else [(opNegateCondition, None)]
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return [(opBooleanConstant, None)]
        if isinstance(node.value, int):
            return [(opConstantOffset, None)]
    if isinstance(node, ast.Return) and node.value is not None:
        return [(opReturnValue, None)]
    return []


def _isTypeCheckingGuard(node: ast.If) -> bool:
    """True for `if TYPE_CHECKING:`, which carries no runtime behaviour to probe.

    Negating it forces the imports the module deliberately defers, which breaks the
    import rather than testing any assertion -- the suite then fails to collect at
    all. That is a mutant the suite always catches, so excluding it *removes* a
    guaranteed kill: the exclusion makes the score stricter, never kinder.
    """
    guardTest = node.test
    if isinstance(guardTest, ast.Attribute):
        return guardTest.attr == typeCheckingGuardName
    return isinstance(guardTest, ast.Name) and guardTest.id == typeCheckingGuardName


def _guardCandidates(node: ast.AST) -> List[Tuple[str, int]]:
    """Raise statements in this node's statement lists, addressed for deletion."""
    details: List[Tuple[str, int]] = []
    for fieldName in statementListFields:
        statements = getattr(node, fieldName, None)
        if not isinstance(statements, list):
            continue
        details.extend(
            (fieldName, statementIndex)
            for statementIndex, statement in enumerate(statements)
            if isinstance(statement, ast.Raise)
        )
    return details


# --- Application -------------------------------------------------------------


def applyCandidate(tree: ast.AST, walkIndex: int, operatorName: str, detail: object) -> ast.AST:
    """Applies exactly one enumerated mutation to a freshly parsed tree."""
    node = list(ast.walk(tree))[walkIndex]

    if operatorName == opComparison:
        opIndex = int(detail)  # type: ignore[arg-type]
        node.ops[opIndex] = comparisonSwaps[type(node.ops[opIndex])]()
    elif operatorName == opArithmetic:
        node.op = arithmeticSwaps[type(node.op)]()
    elif operatorName == opBoolean:
        node.op = booleanSwaps[type(node.op)]()
    elif operatorName == opNegateCondition:
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    elif operatorName == opConstantOffset:
        node.value = node.value + 1
    elif operatorName == opBooleanConstant:
        node.value = not node.value
    elif operatorName == opReturnValue:
        node.value = _replacementReturnValue(node.value)
    elif operatorName == opRemoveGuard:
        fieldName, statementIndex = detail  # type: ignore[misc]
        getattr(node, fieldName)[statementIndex] = ast.Pass()
    else:
        raise ValueError(f"unknown mutation operator: {operatorName}")

    return ast.fix_missing_locations(tree)


def _replacementReturnValue(value: ast.expr) -> ast.expr:
    """Flips a returned boolean, and otherwise blanks the returned value."""
    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
        return ast.Constant(value=not value.value)
    return ast.Constant(value=None)


# --- Description and rendering -----------------------------------------------


def collapseWhitespace(text: str, limit: int = snippetLengthLimit) -> str:
    """Flattens a rendered snippet onto one line for the survivor report."""
    flattened = " ".join(text.split())
    return flattened if len(flattened) <= limit else flattened[: limit - 3] + "..."


def _renderSite(tree: ast.AST, walkIndex: int, operatorName: str, detail: object) -> Tuple[int, str]:
    """Returns the source line and a readable rendering of one site as it stands."""
    node = list(ast.walk(tree))[walkIndex]
    if operatorName == opRemoveGuard:
        fieldName, statementIndex = detail  # type: ignore[misc]
        target = getattr(node, fieldName)[statementIndex]
        return getattr(target, "lineno", 0), ast.unparse(target)
    if operatorName == opNegateCondition:
        return getattr(node.test, "lineno", 0), "if " + ast.unparse(node.test)
    return getattr(node, "lineno", 0), ast.unparse(node)


def generateMutants(modulePath: str, sourceText: str) -> List[Mutant]:
    """Builds every mutant for one module, each described by what it changed."""
    candidates = collectCandidates(ast.parse(sourceText))

    mutants: List[Mutant] = []
    for siteIndex, (walkIndex, operatorName, detail) in enumerate(candidates):
        lineNumber, beforeText = _renderSite(
            ast.parse(sourceText), walkIndex, operatorName, detail
        )
        mutatedTree = applyCandidate(ast.parse(sourceText), walkIndex, operatorName, detail)
        _, afterText = _renderSite(mutatedTree, walkIndex, operatorName, detail)
        if operatorName == opRemoveGuard:
            afterText = "pass"
        mutants.append(
            Mutant(
                modulePath=modulePath,
                siteIndex=siteIndex,
                lineNumber=lineNumber,
                operatorName=operatorName,
                beforeText=collapseWhitespace(beforeText),
                afterText=collapseWhitespace(afterText),
            )
        )
    return mutants


def renderMutantSource(sourceText: str, mutant: Mutant) -> str:
    """Re-derives the mutated module source from its stable site index."""
    walkIndex, operatorName, detail = collectCandidates(ast.parse(sourceText))[mutant.siteIndex]
    return ast.unparse(applyCandidate(ast.parse(sourceText), walkIndex, operatorName, detail))


def renderNormalisedSource(sourceText: str) -> str:
    """The module round-tripped through the parser with no mutation applied."""
    return ast.unparse(ast.parse(sourceText))
