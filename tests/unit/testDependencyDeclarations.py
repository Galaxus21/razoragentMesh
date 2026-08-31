"""Every dependency a service declares must be the one its image installs.

Three sources describe the same Python dependencies and none of them read each other: the
package's pyproject.toml, the pip line in its Dockerfile, and the pip line in ci.yml. They drifted
once already -- all three pyprojects asked for `uvicorn[standard]` while every Dockerfile and CI
installed plain `uvicorn`, so uvloop and httptools were missing from every running container and
nothing noticed, because a plain uvicorn serves requests perfectly well.

These tests compare the three mechanically. They are deliberately narrow: a `>=` floor in
pyproject against a `==` pin in a Dockerfile is the normal library/application split and is not
drift. What is drift is a declared package the image never installs, a dropped extra, or two
sources pinning versions that disagree.
"""

import re
import tomllib
from pathlib import Path
from typing import Dict, Optional, Tuple

import pytest

repoRoot: Path = Path(__file__).resolve().parent.parent.parent
workflowPath: Path = repoRoot / ".github" / "workflows" / "ci.yml"

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


@pytest.mark.parametrize("packageName", sorted(serviceDockerfiles))
def testCiAndDockerfileAgreeOnEveryShardVersion(packageName: str) -> None:
    """Where CI and a Dockerfile both pin a package, the pin must be the same version."""
    dockerfileText = (repoRoot / serviceDockerfiles[packageName]).read_text(encoding="utf-8")
    dockerfilePins = installedByPipLines(dockerfileText)
    ciPins = installedByPipLines(workflowPath.read_text(encoding="utf-8"))

    disagreements = []
    for name, (dockerExtras, dockerVersion) in sorted(dockerfilePins.items()):
        if name not in ciPins or dockerVersion is None:
            continue
        ciExtras, ciVersion = ciPins[name]
        if ciVersion is not None and ciVersion != dockerVersion:
            disagreements.append(f"{name}: Dockerfile=={dockerVersion} vs ci.yml=={ciVersion}")
        if dockerExtras != ciExtras:
            disagreements.append(
                f"{name}: Dockerfile extras {sorted(dockerExtras)} vs ci.yml {sorted(ciExtras)}"
            )
    assert not disagreements, (
        f"{packageName}: CI would test against different versions than the image ships:\n  "
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
