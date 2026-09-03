// Which package does the work at each stage of a run.
//
// The roster of "major packages" is derived from protocolLayerMap's `implementedBy` rather than
// hand-listed here, so a package added to a layer shows up in this view by existing. The per-run
// counts come from ProtocolStepRecord.implementedBy, which the driver already stamps on every
// step -- this file only groups what the driver reports, it never asserts that a package ran.

import { protocolLayerNodes } from "@/constants/protocolLayerMap";
import type { ProtocolStepRecord } from "@/types/protocolRunTypes";

export interface MeshPackageSummary {
  readonly packageName: string;
  readonly layerOrdinals: readonly number[];
  readonly layerTitles: readonly string[];
}

export interface PackageUsage {
  readonly packageName: string;
  readonly stepCount: number;
  readonly layerTitles: readonly string[];
}

const packagesPathPrefix = "packages/";
const pathSeparator = "/";

// "packages/mcpServer/src/tools/" -> "mcpServer". A path that is not under packages/ is returned
// unchanged rather than mangled, so an unexpected shape stays visible instead of collapsing to
// an empty chip.
export function extractPackageName(implementedBy: string): string {
  if (!implementedBy.startsWith(packagesPathPrefix)) {
    return implementedBy;
  }
  const remainder = implementedBy.slice(packagesPathPrefix.length);
  const separatorIndex = remainder.indexOf(pathSeparator);
  return separatorIndex === -1 ? remainder : remainder.slice(0, separatorIndex);
}

export function listMeshPackages(): readonly MeshPackageSummary[] {
  const ordinalsByPackage = new Map<string, number[]>();
  const titlesByPackage = new Map<string, string[]>();

  for (const layer of protocolLayerNodes) {
    for (const path of layer.implementedBy) {
      const packageName = extractPackageName(path);
      const ordinals = ordinalsByPackage.get(packageName) ?? [];
      const titles = titlesByPackage.get(packageName) ?? [];
      if (!ordinals.includes(layer.ordinal)) {
        ordinals.push(layer.ordinal);
        titles.push(layer.title);
      }
      ordinalsByPackage.set(packageName, ordinals);
      titlesByPackage.set(packageName, titles);
    }
  }

  return Array.from(ordinalsByPackage.keys())
    .sort((left, right) => left.localeCompare(right))
    .map((packageName) => ({
      packageName,
      layerOrdinals: ordinalsByPackage.get(packageName) ?? [],
      layerTitles: titlesByPackage.get(packageName) ?? [],
    }));
}

// Every known package is returned, including those with a zero count. A judge asking "did this
// run touch the healer?" is answered by a visible `vectorHealer x0`, not by absence.
export function summarisePackageUsage(
  steps: readonly ProtocolStepRecord[]
): readonly PackageUsage[] {
  const countsByPackage = new Map<string, number>();
  for (const step of steps) {
    const packageName = extractPackageName(step.implementedBy);
    countsByPackage.set(packageName, (countsByPackage.get(packageName) ?? 0) + 1);
  }

  const known = listMeshPackages().map((meshPackage) => ({
    packageName: meshPackage.packageName,
    stepCount: countsByPackage.get(meshPackage.packageName) ?? 0,
    layerTitles: meshPackage.layerTitles,
  }));

  // A step whose package is not in the layer map still has to appear, or the strip would
  // under-report what the run actually executed.
  const knownNames = new Set(known.map((entry) => entry.packageName));
  const unlisted = Array.from(countsByPackage.entries())
    .filter(([packageName]) => !knownNames.has(packageName))
    .map(([packageName, stepCount]) => ({ packageName, stepCount, layerTitles: [] }));

  return [...known, ...unlisted];
}
