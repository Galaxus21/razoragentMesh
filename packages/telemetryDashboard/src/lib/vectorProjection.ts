// Projects the catalog's real 384-dimensional embeddings onto a plane so they can be drawn.
//
// The honest framing matters more than the picture. A 2-D scatter of 384-D vectors is a lossy
// shadow: two points that look adjacent may be far apart along an axis the projection discarded.
// So this returns the explained-variance ratio of both components alongside the coordinates, and
// the page prints it -- a projection that keeps 18% of the variance should not be presented with
// the same confidence as one that keeps 80%.
//
// Principal components rather than t-SNE or UMAP for two reasons. It is deterministic, so the
// map does not rearrange itself between page loads and a demo can be rehearsed; and it is a
// linear map, so "these points are close" means something you can state precisely, whereas
// neighbour-embedding methods distort global distance by construction.

export interface ProjectedPoint {
  readonly index: number;
  readonly x: number;
  readonly y: number;
}

export interface ProjectionResult {
  readonly points: readonly ProjectedPoint[];
  // Fraction of total variance each drawn axis carries, in [0, 1].
  readonly explainedVariance: readonly [number, number];
  readonly dimension: number;
}

// Power iteration needs a starting vector that is not orthogonal to the component it is looking
// for. Math.random() would do, but it would also make the map different on every request. This
// is a fixed 32-bit LCG so the same catalog always projects to the same picture.
const seedMultiplier = 1_664_525;
const seedIncrement = 1_013_904_223;
const seedModulus = 2 ** 32;
const initialSeed = 20_260_904;

const powerIterations = 128;
const convergenceEpsilon = 1e-9;

function deterministicUnitVector(dimension: number): number[] {
  let state = initialSeed;
  const vector: number[] = new Array<number>(dimension);
  for (let i = 0; i < dimension; i += 1) {
    state = (state * seedMultiplier + seedIncrement) % seedModulus;
    vector[i] = state / seedModulus - 0.5;
  }
  return normalize(vector);
}

function normalize(vector: number[]): number[] {
  let sumOfSquares = 0;
  for (const component of vector) {
    sumOfSquares += component * component;
  }
  const magnitude = Math.sqrt(sumOfSquares);
  if (magnitude < convergenceEpsilon) {
    // A zero vector has no direction. Returning it unchanged would silently produce NaN
    // coordinates downstream, so fall back to a unit basis vector.
    const fallback = new Array<number>(vector.length).fill(0);
    fallback[0] = 1;
    return fallback;
  }
  return vector.map((component) => component / magnitude);
}

function dot(left: readonly number[], right: readonly number[]): number {
  let total = 0;
  for (let i = 0; i < left.length; i += 1) {
    total += left[i] * right[i];
  }
  return total;
}

/**
 * One power iteration step against the covariance, without ever forming the covariance matrix.
 *
 * Cov = Xᵀ X / (n - 1), so Cov·v = Xᵀ(X·v) / (n - 1). At 384 dimensions the explicit matrix is
 * only 147k floats and would also be fine, but the implicit form is O(n·d) per step instead of
 * O(d²) to build plus O(d²) to apply, and it keeps the code to one loop.
 */
function covarianceApply(centered: readonly (readonly number[])[], vector: readonly number[]): number[] {
  const dimension = vector.length;
  const result = new Array<number>(dimension).fill(0);
  for (const row of centered) {
    const scale = dot(row, vector);
    if (scale === 0) {
      continue;
    }
    for (let j = 0; j < dimension; j += 1) {
      result[j] += scale * row[j];
    }
  }
  return result;
}

function subtractProjection(vector: number[], basis: readonly number[]): number[] {
  const overlap = dot(vector, basis);
  return vector.map((component, index) => component - overlap * basis[index]);
}

/**
 * Finds the leading eigenvector of the covariance, kept orthogonal to everything already found.
 *
 * Deflating by re-orthogonalising every iteration rather than once at the start: floating-point
 * drift reintroduces a component along the earlier axis, and left unchecked the "second"
 * component converges back onto the first, which draws every point on a line.
 */
function dominantDirection(
  centered: readonly (readonly number[])[],
  dimension: number,
  alreadyFound: readonly (readonly number[])[]
): { direction: number[]; eigenvalue: number } {
  let current = deterministicUnitVector(dimension);
  for (const found of alreadyFound) {
    current = normalize(subtractProjection(current, found));
  }

  let eigenvalue = 0;
  for (let iteration = 0; iteration < powerIterations; iteration += 1) {
    let next = covarianceApply(centered, current);
    for (const found of alreadyFound) {
      next = subtractProjection(next, found);
    }
    const magnitude = Math.sqrt(dot(next, next));
    if (magnitude < convergenceEpsilon) {
      break;
    }
    const normalized = next.map((component) => component / magnitude);
    const drift = 1 - Math.abs(dot(normalized, current));
    current = normalized;
    eigenvalue = magnitude;
    if (drift < convergenceEpsilon) {
      break;
    }
  }

  return { direction: current, eigenvalue };
}

/**
 * Projects vectors onto their two leading principal components.
 *
 * Returns coordinates in [0, 1] on both axes so the caller can scale to whatever viewport it
 * has without knowing the data's units. Fewer than two vectors has no plane to project onto and
 * returns them stacked at the centre rather than throwing -- an empty catalog is a normal state
 * for a fresh mesh, not an error.
 */
export function projectToPlane(vectors: readonly (readonly number[])[]): ProjectionResult {
  const dimension = vectors[0]?.length ?? 0;
  if (vectors.length < 2 || dimension === 0) {
    return {
      points: vectors.map((_, index) => ({ index, x: 0.5, y: 0.5 })),
      explainedVariance: [0, 0],
      dimension
    };
  }

  const mean = new Array<number>(dimension).fill(0);
  for (const vector of vectors) {
    for (let j = 0; j < dimension; j += 1) {
      mean[j] += vector[j];
    }
  }
  for (let j = 0; j < dimension; j += 1) {
    mean[j] /= vectors.length;
  }

  const centered = vectors.map((vector) => vector.map((component, j) => component - mean[j]));

  let totalVariance = 0;
  for (const row of centered) {
    totalVariance += dot(row, row);
  }

  const first = dominantDirection(centered, dimension, []);
  const second = dominantDirection(centered, dimension, [first.direction]);

  const rawX = centered.map((row) => dot(row, first.direction));
  const rawY = centered.map((row) => dot(row, second.direction));

  const points = rescale(rawX, rawY);

  return {
    points,
    explainedVariance: [
      totalVariance > 0 ? first.eigenvalue / totalVariance : 0,
      totalVariance > 0 ? second.eigenvalue / totalVariance : 0
    ],
    dimension
  };
}

/**
 * Maps both axes into [0, 1] with a shared scale.
 *
 * Scaling each axis independently would stretch the minor component to the same width as the
 * major one, which is exactly the distortion the explained-variance figure is there to warn
 * about -- the picture would contradict the caption. One scale for both keeps the aspect honest,
 * and a degenerate axis collapses to the centre line instead of dividing by zero.
 */
function rescale(rawX: readonly number[], rawY: readonly number[]): ProjectedPoint[] {
  const minX = Math.min(...rawX);
  const maxX = Math.max(...rawX);
  const minY = Math.min(...rawY);
  const maxY = Math.max(...rawY);

  const span = Math.max(maxX - minX, maxY - minY);
  if (span < convergenceEpsilon) {
    return rawX.map((_, index) => ({ index, x: 0.5, y: 0.5 }));
  }

  // Centre the narrower axis inside the square rather than pinning it to an edge.
  const offsetX = (span - (maxX - minX)) / 2;
  const offsetY = (span - (maxY - minY)) / 2;

  return rawX.map((value, index) => ({
    index,
    x: (value - minX + offsetX) / span,
    y: (rawY[index] - minY + offsetY) / span
  }));
}
