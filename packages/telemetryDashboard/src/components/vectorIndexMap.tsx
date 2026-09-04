"use client";

// The scatter itself. Inline SVG rather than a charting library: 64 circles and two arrows do
// not justify a dependency, and the shapes here carry meaning a generic scatter would not encode
// -- a hit ring whose radius is the cosine score, and a healing arrow between two specific points.

import React from "react";
import type { VectorIndexPoint } from "@/types/vectorIndexTypes";

// Colour is by category, and categories are discovered from the catalog rather than enumerated,
// so a merchant publishing into a new one does not fall off the legend.
//
// Only the largest few get a hue. The live catalog carries 28 categories against a palette the
// eye can separate at about six, and colouring all of them would produce 22 near-identical
// swatches -- a distinction the reader cannot actually make, which is worse than no distinction.
// The tail is drawn in grey and the legend says how many categories that covers, so nothing is
// hidden; hovering any point still names its own category exactly.
const categoryPalette: readonly string[] = [
  "#4C8DFF",
  "#F2994A",
  "#27AE60",
  "#BB6BD9",
  "#EB5757",
  "#2D9CDB"
];
const overflowCategoryColor = "#8A8F98";

export interface CategoryLegendEntry {
  readonly label: string;
  readonly color: string;
  readonly count: number;
  readonly isOverflow: boolean;
}

export interface HitAnnotation {
  readonly skuId: string;
  readonly score: number;
  readonly rank: number;
}

export interface HealAnnotation {
  readonly fromSkuId: string;
  readonly toSkuId: string;
  readonly cosineScore: number;
}

interface VectorIndexMapProps {
  readonly points: readonly VectorIndexPoint[];
  readonly hits: readonly HitAnnotation[];
  readonly heal: HealAnnotation | null;
  readonly selectedSkuId: string | null;
  readonly onSelect: (skuId: string | null) => void;
}

const viewBoxSize = 100;
const plotMargin = 6;
const basePointRadius = 1.15;
const selectedPointRadius = 2.1;

function countByCategory(points: readonly VectorIndexPoint[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const point of points) {
    counts.set(point.category, (counts.get(point.category) ?? 0) + 1);
  }
  return counts;
}

/**
 * Assigns a hue to the most populous categories, grey to the rest.
 *
 * Ranked by point count and then by name, so the ordering is stable across reloads: a legend
 * that reshuffles itself between takes is a legend a viewer stops trusting.
 */
export function categoryColorMap(
  points: readonly VectorIndexPoint[]
): ReadonlyMap<string, string> {
  const ranked = [...countByCategory(points).entries()].sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0])
  );
  return new Map(
    ranked.map(([category], index) => [
      category,
      index < categoryPalette.length ? categoryPalette[index] : overflowCategoryColor
    ])
  );
}

/** What to draw beside the map: the named categories, then one row for the grey tail. */
export function categoryLegend(
  points: readonly VectorIndexPoint[]
): readonly CategoryLegendEntry[] {
  const ranked = [...countByCategory(points).entries()].sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0])
  );

  const named = ranked.slice(0, categoryPalette.length).map(([label, count], index) => ({
    label,
    color: categoryPalette[index],
    count,
    isOverflow: false
  }));

  const tail = ranked.slice(categoryPalette.length);
  if (tail.length === 0) {
    return named;
  }

  return [
    ...named,
    {
      label: `${tail.length} smaller categories`,
      color: overflowCategoryColor,
      count: tail.reduce((total, [, count]) => total + count, 0),
      isOverflow: true
    }
  ];
}

function toPlot(value: number): number {
  return plotMargin + value * (viewBoxSize - 2 * plotMargin);
}

export default function VectorIndexMap({
  points,
  hits,
  heal,
  selectedSkuId,
  onSelect
}: VectorIndexMapProps): React.JSX.Element {
  const colors = categoryColorMap(points);
  const hitBySku = new Map(hits.map((hit) => [hit.skuId, hit]));
  const bySku = new Map(points.map((point) => [point.skuId, point]));

  const healFrom = heal ? bySku.get(heal.fromSkuId) : undefined;
  const healTo = heal ? bySku.get(heal.toSkuId) : undefined;

  return (
    <svg
      viewBox={`0 0 ${viewBoxSize} ${viewBoxSize}`}
      className="h-full w-full"
      role="img"
      aria-label={`Vector index: ${points.length} catalog embeddings projected onto their two leading principal components`}
    >
      <defs>
        <marker
          id="healArrowHead"
          markerWidth="4"
          markerHeight="4"
          refX="3.2"
          refY="2"
          orient="auto"
        >
          <path d="M0,0 L4,2 L0,4 Z" fill="rgb(var(--status-warning))" />
        </marker>
      </defs>

      {/* A faint grid, so the reader can see this is a coordinate space and not a picture of
          one. No tick labels: the axes are principal components, whose units are meaningless. */}
      {[0, 25, 50, 75, 100].map((tick) => (
        <g key={tick} stroke="rgb(var(--border-subtle))" strokeWidth="0.15" opacity="0.6">
          <line x1={tick} y1="0" x2={tick} y2={viewBoxSize} />
          <line x1="0" y1={tick} x2={viewBoxSize} y2={tick} />
        </g>
      ))}

      {healFrom && healTo && heal ? (
        <line
          x1={toPlot(healFrom.x)}
          y1={toPlot(healFrom.y)}
          x2={toPlot(healTo.x)}
          y2={toPlot(healTo.y)}
          stroke="rgb(var(--status-warning))"
          strokeWidth="0.5"
          strokeDasharray="1.5 1"
          markerEnd="url(#healArrowHead)"
        />
      ) : null}

      {points.map((point) => {
        const hit = hitBySku.get(point.skuId);
        const isSelected = point.skuId === selectedSkuId;
        const isHealSource = heal?.fromSkuId === point.skuId;
        const isHealTarget = heal?.toSkuId === point.skuId;
        const cx = toPlot(point.x);
        const cy = toPlot(point.y);

        return (
          <g key={point.pointId}>
            {/* The ring radius IS the cosine score, scaled -- a near-duplicate draws a wide
                halo and a weak match barely a rim, so relative confidence is visible without
                reading the numbers beside the map. */}
            {hit ? (
              <circle
                cx={cx}
                cy={cy}
                r={basePointRadius + hit.score * 4}
                fill="none"
                stroke="rgb(var(--accent-primary))"
                strokeWidth="0.35"
                opacity={0.35 + hit.score * 0.5}
              />
            ) : null}

            {isHealSource ? (
              <circle
                cx={cx}
                cy={cy}
                r={basePointRadius + 2.4}
                fill="none"
                stroke="rgb(var(--status-error))"
                strokeWidth="0.4"
              />
            ) : null}
            {isHealTarget ? (
              <circle
                cx={cx}
                cy={cy}
                r={basePointRadius + 2.4}
                fill="none"
                stroke="rgb(var(--status-warning))"
                strokeWidth="0.4"
              />
            ) : null}

            <circle
              cx={cx}
              cy={cy}
              r={isSelected ? selectedPointRadius : basePointRadius}
              fill={colors.get(point.category) ?? overflowCategoryColor}
              stroke={isSelected ? "rgb(var(--text-primary))" : "none"}
              strokeWidth="0.35"
              opacity={hits.length > 0 && !hit ? 0.3 : 0.9}
              className="cursor-pointer transition-opacity"
              onClick={() => onSelect(isSelected ? null : point.skuId)}
            >
              <title>
                {`${point.title}\n${point.skuId} · ${point.category}${
                  hit ? `\ncosine ${hit.score.toFixed(4)} (rank ${hit.rank})` : ""
                }`}
              </title>
            </circle>
          </g>
        );
      })}
    </svg>
  );
}
