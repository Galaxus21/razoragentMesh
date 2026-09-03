"""Pins that every shared package a service imports is importable INSIDE its image.

The audit's first finding was that `packages/vectorHealer` was in no Docker image, so Layer 3
could not have run in the mesh. Copying the package in turned out not to be enough, and the
reason is worth stating precisely because it is invisible to the whole test suite:

The tree imports shared packages under two spellings. `razoragentMesh.packages.mandateEngine`
resolves under pytest, which runs from the directory ABOVE the mesh root. `packages.mandateEngine`
resolves inside the images, which put the mesh root on `PYTHONPATH`. Both spellings appear in code
the images run. So a `razoragentMesh.`-spelled import passes every test and raises
ModuleNotFoundError in the container.

That is not a startup crash you would notice, either: `oosHealingRoute._loadHealer` catches
ImportError by design, so Layer 3 answered `vector_healer_unavailable` while the package sat in
the image, and nothing anywhere reported a problem.

These tests read the Dockerfiles and the shipped source, so they fail on the mismatch rather than
on a running container -- there is no Docker daemon in this suite.
"""

import re
from pathlib import Path
from typing import Dict, List, Set

import pytest

repoRoot = Path(__file__).resolve().parents[2]

# (serviceName, Dockerfile, the source trees that end up in the image).
pythonServices = [
    ("merchantApi", "packages/merchantApi/Dockerfile", ["packages/merchantApi/src"]),
    ("x402Gateway", "packages/x402Gateway/Dockerfile", ["packages/x402Gateway/src"]),
    ("mandateEngine", "packages/mandateEngine/Dockerfile", ["packages/mandateEngine"]),
]

sharedImportPattern = re.compile(
    r"^\s*(?:from|import)\s+(razoragentMesh\.)?packages\.([A-Za-z][A-Za-z0-9_]*)", re.MULTILINE
)
copyPattern = re.compile(r"^COPY\s+(\S+)\s+(\S+)", re.MULTILINE)
pythonPathPattern = re.compile(r"^ENV\s+PYTHONPATH=(\S+)", re.MULTILINE)
workdirPattern = re.compile(r"^WORKDIR\s+(\S+)", re.MULTILINE)


def _absolutePath(destination: str, workdir: str) -> str:
    """Resolves a COPY destination against WORKDIR the way Docker does."""
    if destination.startswith("/"):
        return destination.rstrip("/")
    return f"{workdir.rstrip('/')}/{destination.lstrip('./')}".rstrip("/")


def _readDockerfile(dockerfilePath: str) -> str:
    return (repoRoot / dockerfilePath).read_text(encoding="utf-8")


def _collectSharedImports(sourceTrees: List[str]) -> Dict[str, Set[str]]:
    """Maps each imported shared package to the spellings used for it.

    Follows into the copied packages too: `vectorHealer` importing the mandate engine is the
    image's problem just as much as the service's own imports are.
    """
    spellingsByPackage: Dict[str, Set[str]] = {}
    for tree in sourceTrees:
        for sourceFile in (repoRoot / tree).rglob("*.py"):
            if "__pycache__" in sourceFile.parts:
                continue
            for prefix, packageName in sharedImportPattern.findall(
                sourceFile.read_text(encoding="utf-8", errors="replace")
            ):
                spelling = "razoragentMesh" if prefix else "bare"
                spellingsByPackage.setdefault(packageName, set()).add(spelling)
    return spellingsByPackage


def _copiedPackages(dockerfile: str) -> Dict[str, str]:
    """Maps a copied shared package to the destination path it lands on."""
    destinations: Dict[str, str] = {}
    for source, destination in copyPattern.findall(dockerfile):
        match = re.search(r"packages/([A-Za-z][A-Za-z0-9_]*)", source)
        if match:
            destinations[match.group(1)] = destination.replace("\\", "/")
    return destinations


@pytest.mark.parametrize("serviceName,dockerfilePath,sourceTrees", pythonServices)
def testEveryImportedSharedPackageIsCopiedIntoTheImage(
    serviceName: str, dockerfilePath: str, sourceTrees: List[str]
) -> None:
    """A package the code imports but the image does not contain cannot run."""
    dockerfile = _readDockerfile(dockerfilePath)
    copied = _copiedPackages(dockerfile)
    imported = _collectSharedImports(sourceTrees)

    # A service always contains itself; only cross-package imports need a COPY.
    ownPackage = dockerfilePath.split("/")[1]
    missing = sorted(name for name in imported if name != ownPackage and name not in copied)
    assert not missing, (
        f"{serviceName} imports {missing} but its Dockerfile copies none of them, so those "
        f"imports raise ModuleNotFoundError in the image while passing under pytest"
    )


@pytest.mark.parametrize("serviceName,dockerfilePath,sourceTrees", pythonServices)
def testTheImageResolvesEverySpellingItsCodeUses(
    serviceName: str, dockerfilePath: str, sourceTrees: List[str]
) -> None:
    """Both import spellings have to resolve, because both are used.

    `razoragentMesh.packages.X` needs the directory ABOVE a `razoragentMesh/` package root on the
    path; `packages.X` needs that root itself. An image serving only one silently loses the other.
    """
    dockerfile = _readDockerfile(dockerfilePath)
    pythonPathMatch = pythonPathPattern.search(dockerfile)
    assert pythonPathMatch, f"{serviceName}'s Dockerfile sets no PYTHONPATH"
    pythonPathRoots = [root.rstrip("/") for root in pythonPathMatch.group(1).split(":")]
    workdirMatch = workdirPattern.search(dockerfile)
    workdir = workdirMatch.group(1) if workdirMatch else "/app"

    copied = _copiedPackages(dockerfile)
    imported = _collectSharedImports(sourceTrees)
    ownPackage = dockerfilePath.split("/")[1]

    for packageName, spellings in sorted(imported.items()):
        if packageName == ownPackage or packageName not in copied:
            continue
        destination = _absolutePath(copied[packageName], workdir)

        if "razoragentMesh" in spellings:
            assert "/razoragentMesh/packages/" in destination, (
                f"{serviceName} imports razoragentMesh.packages.{packageName}, but the image "
                f"copies it to {destination}, where that spelling cannot resolve"
            )
            # The directory holding `razoragentMesh/` is what makes that name importable.
            parentRoot = destination.split("/razoragentMesh/")[0]
            assert parentRoot in pythonPathRoots, (
                f"{serviceName} needs {parentRoot} on PYTHONPATH for the razoragentMesh spelling; "
                f"PYTHONPATH is {pythonPathRoots}"
            )

        if "bare" in spellings:
            packagesRoot = destination.rsplit("/packages/", 1)[0]
            assert packagesRoot in pythonPathRoots, (
                f"{serviceName} imports packages.{packageName}, which needs {packagesRoot} on "
                f"PYTHONPATH; PYTHONPATH is {pythonPathRoots}"
            )


def testTheMerchantImageCarriesBothProtocolLayersItHosts() -> None:
    """Layer 0 and Layer 3 both live in the Merchant API image, or they do not run.

    Named explicitly rather than left to the generic check above: these two are the packages the
    audit found absent, and a regression here is a protocol layer going quiet, not a crash.
    """
    dockerfile = _readDockerfile("packages/merchantApi/Dockerfile")
    copied = _copiedPackages(dockerfile)
    assert "vectorHealer" in copied, "Layer 3 (vector healer) is not in the Merchant API image"
    assert "catalogSanitizer" in copied, "Layer 0 (ingress shield) is not in the Merchant API image"
