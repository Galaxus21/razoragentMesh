// Tests for the search_catalog request schema.
//
// The point of this file is the leniency. Moving a hand-rolled normalizer behind zod is exactly
// the kind of change that silently tightens a contract: a plain z.object would have started
// rejecting the `queryText` spelling and any out-of-range limit, both of which agents send today
// and both of which work. Each is asserted here so a future tidy-up cannot quietly break them.

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  catalogSearchRequestSchema,
  type CatalogSearchRequest
} from "../src/schemas/catalogSearchSchema.js";
import {
  defaultSearchLimit,
  errorEmptyQueryText,
  maxSearchLimit
} from "../src/constants/catalogSearchConstants.js";

function parse(raw: unknown): CatalogSearchRequest {
  return catalogSearchRequestSchema.parse(raw) as CatalogSearchRequest;
}

describe("catalogSearchRequestSchema", () => {
  it("accepts the snake_case spelling the tool manifest advertises", () => {
    assert.deepEqual(parse({ query_text: "office chair" }), {
      queryText: "office chair",
      limit: defaultSearchLimit
    });
  });

  it("accepts the camelCase spelling too, because agents send it", () => {
    // merchantApi's own endpoint is camelCase, so both spellings reach this tool in practice.
    assert.deepEqual(parse({ queryText: "office chair" }), {
      queryText: "office chair",
      limit: defaultSearchLimit
    });
  });

  it("prefers query_text when both spellings are present", () => {
    assert.equal(parse({ query_text: "snake", queryText: "camel" }).queryText, "snake");
  });

  it("trims the query before deciding whether it is empty", () => {
    assert.equal(parse({ query_text: "  office chair  " }).queryText, "office chair");
  });

  it("clamps an over-large limit instead of rejecting the call", () => {
    // Asking for 500 hits is a reasonable thing for an agent to do. Refusing it outright would
    // fail a request that has an obvious correct answer.
    assert.equal(parse({ query_text: "chair", limit: 500 }).limit, maxSearchLimit);
  });

  it("clamps a zero or negative limit up to one", () => {
    assert.equal(parse({ query_text: "chair", limit: 0 }).limit, 1);
    assert.equal(parse({ query_text: "chair", limit: -7 }).limit, 1);
  });

  it("truncates a fractional limit rather than failing an integer check", () => {
    assert.equal(parse({ query_text: "chair", limit: 3.9 }).limit, 3);
  });

  it("falls back to the default for a non-numeric limit", () => {
    assert.equal(parse({ query_text: "chair", limit: "many" as never }).limit, defaultSearchLimit);
  });

  it("falls back to the default for NaN, which used to serialise as null on the wire", () => {
    // NaN is a number by typeof, so it previously survived Math.trunc/max/min unchanged and went
    // out as `"limit": null`, which the catalog endpoint rejects. No working input changes.
    assert.equal(parse({ query_text: "chair", limit: Number.NaN }).limit, defaultSearchLimit);
  });

  it("rejects an empty or whitespace-only query with the wording agents already see", () => {
    for (const raw of [{}, { query_text: "" }, { query_text: "   " }, { queryText: "\t" }]) {
      assert.throws(
        () => parse(raw),
        (error: Error) => error.message === errorEmptyQueryText,
        `expected the verbatim empty-query error for ${JSON.stringify(raw)}`
      );
    }
  });

  it("treats a missing argument object as an empty query rather than crashing", () => {
    assert.throws(
      () => parse(undefined),
      (error: Error) => error.message === errorEmptyQueryText
    );
  });

  it("ignores unknown fields instead of refusing the search", () => {
    const parsed = parse({ query_text: "chair", somethingElse: true });
    assert.deepEqual(parsed, { queryText: "chair", limit: defaultSearchLimit });
  });
});
