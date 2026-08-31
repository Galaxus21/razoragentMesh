// Reads a TypeScript package's public surface with the TypeScript compiler itself.
//
// TypeDoc would also produce this, but it is a large dependency emitting a large document, and
// every field of it would be thrown away except the names. The compiler API is already installed
// -- it is what typechecks this repo -- and asking the checker directly means the surface recorded
// here is the surface the compiler resolves, not a second parser's opinion of it.

import ts from "typescript";
import type {
  ExportedSymbol,
  ExportedSymbolKind,
  PackageSurface,
  SymbolMember,
} from "@/types/referenceTypes";

const nonPublicModifiers = ts.ModifierFlags.Private | ts.ModifierFlags.Protected;

const compilerOptions: ts.CompilerOptions = {
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.NodeNext,
  moduleResolution: ts.ModuleResolutionKind.NodeNext,
  strict: true,
  skipLibCheck: true,
  noEmit: true,
};

function classifySymbol(symbol: ts.Symbol): ExportedSymbolKind {
  if (symbol.flags & ts.SymbolFlags.Class) {
    return "class";
  }
  if (symbol.flags & ts.SymbolFlags.Interface) {
    return "interface";
  }
  if (symbol.flags & ts.SymbolFlags.Function) {
    return "function";
  }
  if (symbol.flags & ts.SymbolFlags.Enum) {
    return "enum";
  }
  if (symbol.flags & ts.SymbolFlags.TypeAlias) {
    return "type";
  }
  return "variable";
}

function isPubliclyVisible(symbol: ts.Symbol): boolean {
  // An underscore prefix is the convention for "not part of the API" in both languages, and the
  // Python side of the reference applies the same rule -- so zod's _def and _parse are excluded
  // here for the same reason razoragent_buyer_sdk's _private helpers are excluded there.
  if (symbol.getName().startsWith("_")) {
    return false;
  }
  const declaration = symbol.declarations?.[0];
  if (!declaration) {
    return true;
  }
  // A `private` field is part of the type but not part of the documented surface: a guide that
  // reaches for one is wrong even though the compiler can resolve it.
  return (ts.getCombinedModifierFlags(declaration) & nonPublicModifiers) === 0;
}

// A `const` holding a string is not an object with 50 members; String.prototype is. Recording the
// intrinsic prototype of every primitive and array export inflated this file past 200 kB with
// rows no guide could ever be wrong about. Members are recorded for the things that declare a
// shape -- classes, interfaces, type aliases -- and for object-typed values, which do have a
// documented surface of their own.
function hasDocumentedMembers(checker: ts.TypeChecker, type: ts.Type): boolean {
  if ((type.flags & ts.TypeFlags.Object) === 0) {
    return false;
  }
  return !checker.isArrayType(type) && !checker.isTupleType(type);
}

function describeMembers(checker: ts.TypeChecker, type: ts.Type): readonly SymbolMember[] {
  return checker
    .getPropertiesOfType(type)
    .filter(isPubliclyVisible)
    .map((property) => {
      const declaration = property.declarations?.[0];
      const propertyType = declaration
        ? checker.getTypeOfSymbolAtLocation(property, declaration)
        : undefined;
      return {
        name: property.getName(),
        signature: propertyType ? checker.typeToString(propertyType) : "unknown",
      };
    })
    .sort((left, right) => left.name.localeCompare(right.name));
}

// The names a caller may pass. A single object-literal parameter -- the shape both SDK
// constructors use -- contributes its property names, because that is what a reader actually
// types. Anything else contributes its parameter names.
function describeConstructorParameters(
  checker: ts.TypeChecker,
  symbol: ts.Symbol,
  declaration: ts.Declaration
): readonly string[] {
  const construct = checker
    .getTypeOfSymbolAtLocation(symbol, declaration)
    .getConstructSignatures()[0];
  if (!construct) {
    return [];
  }

  const parameters = construct.getParameters();
  const soleParameter = parameters.length === 1 ? parameters[0] : undefined;
  const soleDeclaration = soleParameter?.valueDeclaration ?? soleParameter?.declarations?.[0];
  if (!soleParameter || !soleDeclaration) {
    return parameters.map((parameter) => parameter.getName());
  }

  // A sole options object contributes its keys, because that is what a caller writes. A sole
  // primitive contributes its own name: expanding `constructor(message: string)` recorded all
  // fifty String.prototype methods as the constructor's parameters, which is how three error
  // classes came to claim they were constructed with `trimStart` and `fontcolor`.
  const parameterType = checker.getTypeOfSymbolAtLocation(soleParameter, soleDeclaration);
  const properties = hasDocumentedMembers(checker, parameterType)
    ? checker.getPropertiesOfType(parameterType)
    : [];
  return properties.length > 0
    ? properties.map((property) => property.getName()).sort()
    : [soleParameter.getName()];
}

// Statics sit on the constructor, instance members on the declared type, and the guides use both
// forms -- AgentKeyManager.generate() beside client.getLiveSkuQuote(). They are recorded in one
// list because the checker's question is whether a name exists on the class at all; it does not
// track whether a given receiver is an instance or the class itself.
function describeClassMembers(
  checker: ts.TypeChecker,
  symbol: ts.Symbol,
  declaration: ts.Declaration
): readonly SymbolMember[] {
  const instanceMembers = describeMembers(checker, checker.getDeclaredTypeOfSymbol(symbol));
  const staticMembers = describeMembers(
    checker,
    checker.getTypeOfSymbolAtLocation(symbol, declaration)
  ).filter((member) => member.name !== "prototype");

  const byName = new Map(
    [...instanceMembers, ...staticMembers].map((member) => [member.name, member])
  );
  return [...byName.values()].sort((left, right) => left.name.localeCompare(right.name));
}

function describeSymbol(checker: ts.TypeChecker, symbol: ts.Symbol): ExportedSymbol {
  const resolved = symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
  const kind = classifySymbol(resolved);
  const declaration = resolved.valueDeclaration ?? resolved.declarations?.[0];

  // A class, interface or type alias is described by the type it declares -- the members a
  // caller reaches for. A const or function is described by the type of the value itself.
  const declaresAType = kind === "class" || kind === "interface" || kind === "type";
  const subjectType = declaresAType
    ? checker.getDeclaredTypeOfSymbol(resolved)
    : declaration
      ? checker.getTypeOfSymbolAtLocation(resolved, declaration)
      : undefined;

  return {
    name: symbol.getName(),
    kind,
    signature: subjectType ? checker.typeToString(subjectType) : "unknown",
    members:
      kind === "class" && declaration
        ? describeClassMembers(checker, resolved, declaration)
        : subjectType && hasDocumentedMembers(checker, subjectType)
          ? describeMembers(checker, subjectType)
          : [],
    constructorParameters:
      kind === "class" && declaration
        ? describeConstructorParameters(checker, resolved, declaration)
        : [],
  };
}

export function extractPackageSurface(entryPoint: string, packageName: string): PackageSurface {
  const program = ts.createProgram([entryPoint], compilerOptions);
  const sourceFile = program.getSourceFile(entryPoint);
  if (!sourceFile) {
    throw new Error(`Cannot read the SDK entry point: ${entryPoint}`);
  }

  const checker = program.getTypeChecker();
  const moduleSymbol = checker.getSymbolAtLocation(sourceFile);
  if (!moduleSymbol) {
    throw new Error(`${entryPoint} exports nothing the compiler can resolve`);
  }

  const exports = checker
    .getExportsOfModule(moduleSymbol)
    .map((symbol) => describeSymbol(checker, symbol))
    .sort((left, right) => left.name.localeCompare(right.name));

  return { packageName, entryPoint, exports };
}
