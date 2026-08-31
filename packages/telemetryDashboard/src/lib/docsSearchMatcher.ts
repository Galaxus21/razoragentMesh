// Scores generated search-index entries against a query.
//
// Kept apart from the search box so the ranking can be asserted directly in tests: a matcher
// that only exists inside a React component can only be checked by rendering it, which is how
// ranking rules end up untested and then wrong.
//
// The rules are deliberately plain -- every term must appear (AND, not OR), and a hit in a
// heading outranks a hit in prose. For six guides that is enough; anything fuzzier would rank
// results by a similarity score no reader can predict.

import type { DocSearchEntry } from "@/types/docsTypes";

export const defaultResultLimit = 8;
export const minimumQueryLength = 2;

const headingPhraseScore = 100;
const headingTermScore = 25;
const titleTermScore = 8;
const bodyTermScore = 1;
const earlyMatchBonus = 5;
const earlyMatchThreshold = 80;

export interface DocSearchResult {
  readonly entry: DocSearchEntry;
  readonly score: number;
}

export function tokenizeQuery(query: string): readonly string[] {
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter((term) => term.length > 0);
}

function scoreEntry(entry: DocSearchEntry, terms: readonly string[], phrase: string): number {
  const heading = entry.headingText.toLowerCase();
  const title = entry.docTitle.toLowerCase();
  let score = 0;

  for (const term of terms) {
    const bodyIndex = entry.searchText.indexOf(term);
    // Every term must appear somewhere in the section, or the section is not a result at all.
    if (bodyIndex < 0) {
      return 0;
    }
    if (heading.includes(term)) {
      score += headingTermScore;
    } else if (title.includes(term)) {
      score += titleTermScore;
    } else {
      score += bodyTermScore;
    }
    if (bodyIndex < earlyMatchThreshold) {
      score += earlyMatchBonus;
    }
  }

  // A heading that contains the whole query verbatim is almost always the section the reader
  // meant, so it outranks any accumulation of scattered single-term hits.
  if (terms.length > 1 && heading.includes(phrase)) {
    score += headingPhraseScore;
  }
  return score;
}

export function searchDocs(
  index: readonly DocSearchEntry[],
  query: string,
  limit: number = defaultResultLimit
): readonly DocSearchResult[] {
  const trimmed = query.trim();
  if (trimmed.length < minimumQueryLength) {
    return [];
  }

  const terms = tokenizeQuery(trimmed);
  const phrase = trimmed.toLowerCase();

  return index
    .map((entry) => ({ entry, score: scoreEntry(entry, terms, phrase) }))
    .filter((result) => result.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}
