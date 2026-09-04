import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { projectToPlane } from "../src/lib/vectorProjection.js";
import { visualiseSectionTabs } from "../src/constants/sidebarNavigationConfig.js";

// The Vector Index panel draws a claim: "these embeddings are near each other in the index".
// If the projection lies, the panel lies, and it lies persuasively -- a scatter plot reads as
// evidence. So the properties asserted here are the ones the picture depends on: structure in
// the data survives the reduction, the axes are reported honestly, and the same catalog always
// projects to the same picture so a rehearsed demo does not rearrange itself on stage.

function buildVector(dimension: number, fill: (index: number) => number): number[] {
  return Array.from({ length: dimension }, (_, index) => fill(index));
}

describe("Projecting catalog embeddings onto a plane", () => {
  it("keeps two separated clusters separated", () => {
    // Two groups differing along one axis. Any projection worth drawing must put a gap between
    // them that is wider than the spread inside either group.
    const dimension = 32;
    const clusterA = Array.from({ length: 8 }, (_, member) =>
      buildVector(dimension, (index) => (index === 0 ? 10 : member * 0.01 + index * 0.001))
    );
    const clusterB = Array.from({ length: 8 }, (_, member) =>
      buildVector(dimension, (index) => (index === 0 ? -10 : member * 0.01 + index * 0.001))
    );

    const { points } = projectToPlane([...clusterA, ...clusterB]);
    const first = points.slice(0, 8);
    const second = points.slice(8);

    const centroid = (group: typeof first): number =>
      group.reduce((total, point) => total + point.x, 0) / group.length;
    const spread = (group: typeof first): number =>
      Math.max(...group.map((point) => point.x)) - Math.min(...group.map((point) => point.x));

    const separation = Math.abs(centroid(first) - centroid(second));
    assert.ok(
      separation > spread(first) && separation > spread(second),
      `clusters merged: separation ${separation} did not exceed within-cluster spread`
    );
  });

  it("reports how much variance each drawn axis actually carries", () => {
    // A single dominant direction plus noise: the first component must claim most of the
    // variance and the second little. This is the figure the page prints beside the plot, and
    // it is the only thing stopping a viewer from over-reading the picture.
    const dimension = 16;
    const vectors = Array.from({ length: 20 }, (_, member) =>
      buildVector(dimension, (index) => (index === 0 ? member : (member % 3) * 0.001))
    );

    const { explainedVariance } = projectToPlane(vectors);
    assert.ok(explainedVariance[0] > 0.9, `PC1 carried only ${explainedVariance[0]}`);
    assert.ok(explainedVariance[1] < 0.1, `PC2 carried ${explainedVariance[1]}, expected near zero`);
    assert.ok(explainedVariance[0] >= explainedVariance[1], "components are not ordered");
  });

  it("produces the same picture every time", () => {
    // Power iteration starts from a fixed seed rather than Math.random precisely so that a
    // reloaded page, or a rehearsed demo, shows the map in the same arrangement.
    const vectors = Array.from({ length: 12 }, (_, member) =>
      buildVector(24, (index) => Math.sin(member * 1.7 + index * 0.3))
    );

    const first = projectToPlane(vectors);
    const second = projectToPlane(vectors);
    assert.deepEqual(first.points, second.points);
    assert.deepEqual(first.explainedVariance, second.explainedVariance);
  });

  it("holds every coordinate inside the drawable unit square", () => {
    const vectors = Array.from({ length: 30 }, (_, member) =>
      buildVector(48, (index) => Math.cos(member * 0.9) * (index + 1))
    );

    for (const point of projectToPlane(vectors).points) {
      assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y), "coordinate is not finite");
      assert.ok(point.x >= 0 && point.x <= 1, `x out of range: ${point.x}`);
      assert.ok(point.y >= 0 && point.y <= 1, `y out of range: ${point.y}`);
    }
  });

  it("survives a catalog too small to have a plane", () => {
    // A fresh mesh has an empty or one-item collection. That is a normal state, not an error,
    // and it must not put NaN into an SVG coordinate.
    assert.deepEqual(projectToPlane([]).points, []);

    const single = projectToPlane([[1, 2, 3]]);
    assert.equal(single.points.length, 1);
    assert.ok(Number.isFinite(single.points[0].x) && Number.isFinite(single.points[0].y));
  });

  it("survives a collection where every vector is identical", () => {
    // Degenerate input: zero variance in every direction, so there is no scale to divide by.
    const identical = Array.from({ length: 5 }, () => [0.4, 0.4, 0.4, 0.4]);
    for (const point of projectToPlane(identical).points) {
      assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y), "degenerate input made NaN");
    }
  });
});

describe("The Vector Index panel is reachable", () => {
  it("is registered as a Visualise tab, so the route is not orphaned", () => {
    // A page that no navigation names cannot be found during a demo. The tab strip is the only
    // way into the Visualise sub-pages -- see the note in sidebarNavigationConfig.
    assert.ok(
      visualiseSectionTabs.some((tab) => tab.route === "/visualise/vectors"),
      "Vector Index is not in the Visualise tab strip"
    );
  });
});
