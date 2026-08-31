"""Records the Python half of the mesh's public surface as JSON, for the docs drift checker.

Two artifacts land in packages/telemetryDashboard/generated/:

  httpApiReference.json    every route the three FastAPI services actually serve
  pythonSdkReference.json  every name razoragent_buyer_sdk exports, with its members

Neither needs a running service. FastAPI builds its OpenAPI document from the decorated route
functions, so importing the app object offline is enough -- verified against all three apps, none
of which opens a connection at import time.

The point is not documentation for its own sake. scripts/verifyDocSnippets.ts resolves every
symbol the guides mention against these tables, which is how a guide that documents a method
nobody implemented fails the build instead of shipping.

Regenerate with: python scripts/generateApiReference.py
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

repoRoot = Path(__file__).resolve().parent.parent
outputDirectory = repoRoot / "packages" / "telemetryDashboard" / "generated"
buyerSdkPyDirectory = repoRoot / "packages" / "buyerSdkPy"
seederPath = repoRoot / "scripts" / "seedTelemetryStream.py"

# (serviceId, module path, the module-level name holding the FastAPI instance). serviceId matches
# meshServiceRegistry.ts, so a documented localhost:<port> can be resolved to the service that
# actually answers there.
fastApiServices: Tuple[Tuple[str, str, str], ...] = (
    ("mandateEngine", "packages.mandateEngine.mandateApp", "mandateApp"),
    ("merchantApi", "packages.merchantApi.src.merchantApp", "merchantApp"),
    ("x402Gateway", "packages.x402Gateway.src.gatewayApp", "app"),
)

sdkPackageName = "razoragent_buyer_sdk"
eventTypePattern = re.compile(r'"eventType"\s*:\s*"([A-Z_]+)"')
bytesPerKilobyte = 1024


def describeHttpService(serviceId: str, modulePath: str, appVariable: str) -> Dict[str, Any]:
    """Reads one FastAPI app's routes out of its own OpenAPI document."""
    module = importlib.import_module(modulePath)
    application = getattr(module, appVariable)
    specification = application.openapi()

    operations: List[Dict[str, str]] = []
    for path, pathItem in specification["paths"].items():
        for method in pathItem:
            operations.append({"method": method.upper(), "path": path})

    operations.sort(key=lambda operation: (operation["path"], operation["method"]))
    return {
        "serviceId": serviceId,
        "title": specification["info"]["title"],
        "operations": operations,
    }


def renderSignature(value: Any) -> str:
    """Best-effort signature text. Builtins and C types have none; the name is enough there."""
    try:
        return f"{getattr(value, '__name__', 'value')}{inspect.signature(value)}"
    except (TypeError, ValueError):
        return type(value).__name__


def classifyExport(value: Any) -> str:
    if inspect.isclass(value):
        return "class"
    if inspect.isfunction(value) or inspect.isbuiltin(value):
        return "function"
    return "variable"


def publicMembersOf(value: Any) -> Dict[str, str]:
    """Every public attribute of a class, rendered as name -> signature."""
    members: Dict[str, str] = {}
    for name, member in inspect.getmembers(value):
        if name.startswith("_"):
            continue
        members[name] = renderSignature(member) if callable(member) else type(member).__name__

    for fieldName, field in getattr(value, "model_fields", {}).items():
        members[fieldName] = str(getattr(field, "annotation", "unknown"))
    return members


def externalBasesOf(value: Any) -> List[Any]:
    """Base classes that come from outside the SDK -- pydantic.BaseModel, Exception, object."""
    return [
        base
        for base in inspect.getmro(value)[1:]
        if not getattr(base, "__module__", "").startswith(sdkPackageName)
    ]


def describeMembers(value: Any, inheritedTable: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """The members this class itself introduces.

    Every pydantic model carries the same ~28 inherited names (model_dump, construct, schema...)
    and every exception the same handful. Repeating them per class made the artifact 286 kB of
    almost entirely duplicated rows. They are recorded once under inheritedMembers and referenced
    by base name instead, so the table stays complete without storing the same list fifty times.
    """
    if not inspect.isclass(value):
        return []

    inheritedNames: set = set()
    for base in externalBasesOf(value):
        baseName = f"{base.__module__}.{base.__qualname__}"
        baseMembers = publicMembersOf(base)
        if not baseMembers:
            continue
        inheritedNames.update(baseMembers)
        inheritedTable.setdefault(
            baseName, [{"name": name, "signature": baseMembers[name]} for name in sorted(baseMembers)]
        )

    ownMembers = publicMembersOf(value)
    return [
        {"name": name, "signature": ownMembers[name]}
        for name in sorted(ownMembers)
        if name not in inheritedNames
    ]


def describeConstructorParameters(value: Any) -> List[str]:
    """The keyword arguments a constructor accepts -- what a guide's call must match."""
    if not inspect.isclass(value):
        return []

    fieldNames = sorted(getattr(value, "model_fields", {}))
    if fieldNames:
        return fieldNames

    try:
        parameters = inspect.signature(value).parameters
    except (TypeError, ValueError):
        return []
    return [name for name in parameters if name not in ("self", "args", "kwargs")]


def describeExport(
    name: str, value: Any, inheritedTable: Dict[str, List[Dict[str, str]]]
) -> Dict[str, Any]:
    inheritsFrom = (
        [f"{base.__module__}.{base.__qualname__}" for base in externalBasesOf(value)]
        if inspect.isclass(value)
        else []
    )
    return {
        "name": name,
        "kind": classifyExport(value),
        "signature": renderSignature(value) if callable(value) else repr(value),
        "members": describeMembers(value, inheritedTable),
        "inheritsFrom": [base for base in inheritsFrom if base in inheritedTable],
        "constructorParameters": describeConstructorParameters(value),
    }


def buildPythonSdkSurface() -> Dict[str, Any]:
    """Introspects the installed SDK package rather than parsing its source.

    Parsing would have to re-implement re-exports, decorators and pydantic's generated __init__.
    Importing asks the interpreter the same question a reader's code asks it.
    """
    sys.path.insert(0, str(buyerSdkPyDirectory))
    package = importlib.import_module(sdkPackageName)

    exportedNames = sorted(
        name for name in getattr(package, "__all__", dir(package)) if not name.startswith("_")
    )
    inheritedTable: Dict[str, List[Dict[str, str]]] = {}
    exports = [
        describeExport(name, getattr(package, name), inheritedTable) for name in exportedNames
    ]

    return {
        "packageName": sdkPackageName,
        "entryPoint": f"packages/buyerSdkPy/{sdkPackageName}/__init__.py",
        "exports": exports,
        "inheritedMembers": inheritedTable,
    }


def collectSeededEventTypes() -> List[str]:
    """Event types the offline seeder publishes.

    Read from the seeder specifically, not from a repo-wide scan: test fixtures publish invented
    types (SYSTEM_PING) that the dashboard is under no obligation to render.
    """
    source = seederPath.read_text(encoding="utf-8")
    return sorted(set(eventTypePattern.findall(source)))


def writeArtifact(fileName: str, payload: Dict[str, Any]) -> None:
    outputDirectory.mkdir(parents=True, exist_ok=True)
    target = outputDirectory / fileName
    contents = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    target.write_text(contents, encoding="utf-8")
    sizeKilobytes = len(contents.encode("utf-8")) / bytesPerKilobyte
    print(f"Wrote {target.relative_to(repoRoot)} ({sizeKilobytes:.1f} kB)")


def main() -> None:
    # The service modules import each other as `packages.<service>....`, so the repo root has to
    # be importable regardless of where this script is invoked from.
    sys.path.insert(0, str(repoRoot))

    services = [describeHttpService(*service) for service in fastApiServices]
    if not all(service["operations"] for service in services):
        raise SystemExit("A service reported no routes -- refusing to write an empty reference")

    writeArtifact(
        "httpApiReference.json",
        {"services": services, "telemetryEventTypes": collectSeededEventTypes()},
    )
    writeArtifact("pythonSdkReference.json", buildPythonSdkSurface())


if __name__ == "__main__":
    main()
