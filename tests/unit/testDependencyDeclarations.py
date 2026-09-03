"""Every dependency a service declares must be the one its image installs.

Two sources describe the same Python dependencies and neither reads the other: the package's
pyproject.toml, and the pip line in its Dockerfile. They drifted once already -- all three
pyprojects asked for `uvicorn[standard]` while every Dockerfile installed plain `uvicorn`, so
uvloop and httptools were missing from every running container and nothing noticed, because a
plain uvicorn serves requests perfectly well.

These tests compare them mechanically, and compare the service images against each other. They
are deliberately narrow: a `>=` floor in pyproject against a `==` pin in a Dockerfile is the
normal library/application split and is not drift. What is drift is a declared package the image
never installs, a dropped extra, or two sources pinning versions that disagree.
"""

import re
import tomllib
from pathlib import Path
from typing import Dict, Optional, Tuple

import pytest

repoRoot: Path = Path(__file__).resolve().parent.parent.parent

# Only packages that are actually built into an image; the SDK and library packages have no
# Dockerfile and are installed by whoever consumes them.
serviceDockerfiles: Dict[str, str] = {
    "mandateEngine": "packages/mandateEngine/Dockerfile",
    "merchantApi": "packages/merchantApi/Dockerfile",
    "x402Gateway": "packages/x402Gateway/Dockerfile",
}

requirementPattern = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[(?P<extras>[^\]]*)\])?"
    r"(?:(?P<operator>[=><!~]=?)(?P<version>[0-9][0-9A-Za-z.*+!-]*))?"
)
pipInstallPattern = re.compile(r"pip install(?P<arguments>.+?)$", re.M)
pipOptionPrefix = "-"


def parseRequirement(token: str) -> Optional[Tuple[str, frozenset, Optional[str]]]:
    """Splits `name[extra1,extra2]==1.2.3` into its parts, or None if not a requirement."""
    token = token.strip().strip("\\").strip()
    if not token or token.startswith(pipOptionPrefix):
        return None
    match = requirementPattern.fullmatch(token)
    if not match:
        return None
    rawExtras = match.group("extras") or ""
    extras = frozenset(part.strip() for part in rawExtras.split(",") if part.strip())
    return match.group("name").lower(), extras, match.group("version")


def declaredDependencies(packageName: str) -> Dict[str, Tuple[frozenset, Optional[str]]]:
    """Runtime dependencies from a package's pyproject, keyed by lowercase name."""
    pyprojectPath = repoRoot / "packages" / packageName / "pyproject.toml"
    parsed = tomllib.loads(pyprojectPath.read_text(encoding="utf-8"))
    declared: Dict[str, Tuple[frozenset, Optional[str]]] = {}
    for entry in parsed.get("project", {}).get("dependencies", []):
        requirement = parseRequirement(entry)
        if requirement:
            name, extras, version = requirement
            declared[name] = (extras, version)
    return declared


def installedByPipLines(text: str) -> Dict[str, Tuple[frozenset, Optional[str]]]:
    """Every requirement named on any `pip install` line in the given file text."""
    installed: Dict[str, Tuple[frozenset, Optional[str]]] = {}
    for match in pipInstallPattern.finditer(text):
        for token in match.group("arguments").split():
            requirement = parseRequirement(token)
            if requirement:
                name, extras, version = requirement
                installed[name] = (extras, version)
    return installed


@pytest.mark.parametrize("packageName", sorted(serviceDockerfiles))
def testDockerfileInstallsEveryDeclaredDependency(packageName: str) -> None:
    declared = declaredDependencies(packageName)
    dockerfileText = (repoRoot / serviceDockerfiles[packageName]).read_text(encoding="utf-8")
    installed = installedByPipLines(dockerfileText)

    missing = sorted(name for name in declared if name not in installed)
    assert not missing, (
        f"{packageName} declares {missing} in pyproject.toml but its Dockerfile never installs "
        f"them, so the image runs without a dependency the package says it needs."
    )


@pytest.mark.parametrize("packageName", sorted(serviceDockerfiles))
def testDockerfileKeepsTheExtrasThePackageAsksFor(packageName: str) -> None:
    declared = declaredDependencies(packageName)
    dockerfileText = (repoRoot / serviceDockerfiles[packageName]).read_text(encoding="utf-8")
    installed = installedByPipLines(dockerfileText)

    for name, (declaredExtras, _) in sorted(declared.items()):
        if not declaredExtras:
            continue
        installedExtras = installed.get(name, (frozenset(), None))[0]
        dropped = sorted(declaredExtras - installedExtras)
        assert not dropped, (
            f"{packageName} declares {name}{sorted(declaredExtras)} but its Dockerfile installs "
            f"{name}{sorted(installedExtras)}. Dropping {dropped} silently removes optional "
            f"packages the service was specified to run with."
        )


def testServicesPinTheSameVersionOfEverySharedDependency() -> None:
    """Where two service images both pin a package, they must pin the same version.

    The services share Redis, httpx, pydantic and FastAPI. Nothing makes them agree, so
    one image can be upgraded and the others left behind -- and because each container
    starts perfectly well on its own version, the divergence is invisible until two
    services disagree about the shape of something they pass between them.
    """
    pinsByService = {
        packageName: installedByPipLines(
            (repoRoot / relativePath).read_text(encoding="utf-8")
        )
        for packageName, relativePath in sorted(serviceDockerfiles.items())
    }

    versionsByPackage: Dict[str, Dict[str, str]] = {}
    for serviceName, pins in pinsByService.items():
        for name, (extras, version) in pins.items():
            if version is None:
                continue
            descriptor = f"{version}{sorted(extras) if extras else ''}"
            versionsByPackage.setdefault(name, {})[serviceName] = descriptor

    disagreements = [
        f"{name}: " + ", ".join(f"{svc}=={ver}" for svc, ver in sorted(byService.items()))
        for name, byService in sorted(versionsByPackage.items())
        if len(set(byService.values())) > 1
    ]
    assert not disagreements, (
        "Service images pin different versions of the same dependency:\n  "
        + "\n  ".join(disagreements)
    )


@pytest.mark.parametrize("packageName", sorted(serviceDockerfiles))
def testDockerfilePinsSatisfyTheDeclaredFloor(packageName: str) -> None:
    """A `==` pin must not sit below the `>=` floor the package declares."""
    declared = declaredDependencies(packageName)
    dockerfileText = (repoRoot / serviceDockerfiles[packageName]).read_text(encoding="utf-8")
    installed = installedByPipLines(dockerfileText)

    def versionKey(version: str) -> tuple:
        return tuple(int(part) for part in re.findall(r"\d+", version)[:4])

    violations = []
    for name, (_, floor) in sorted(declared.items()):
        pinned = installed.get(name, (frozenset(), None))[1]
        if floor and pinned and versionKey(pinned) < versionKey(floor):
            violations.append(f"{name}: pinned {pinned} is below the declared floor {floor}")
    assert not violations, f"{packageName}: " + "; ".join(violations)
