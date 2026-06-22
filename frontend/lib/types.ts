/**
 * TypeScript interfaces mirroring the Error Encyclopedia FastAPI Pydantic
 * models field-for-field. These define the wire contract consumed by the
 * typed API client in `lib/api.ts`.
 */

/** A single root cause as returned by the API. */
export interface RootCauseRead {
  id: number;
  description: string;
}

/** A single verified fix (before/after code + explanation). */
export interface VerifiedFixRead {
  id: number;
  before_code_snippet: string;
  after_code_snippet: string;
  explanation: string;
}

/** Lightweight error representation used in lists and related-error blocks. */
export interface ErrorSummary {
  slug: string;
  title: string;
  plain_english_explanation: string;
}

/** Full error detail including root causes, verified fixes, and related errors. */
export interface ErrorDetail {
  slug: string;
  title: string;
  plain_english_explanation: string;
  /** ISO 8601 datetime string (e.g. "2026-06-22T12:00:00Z"). */
  created_at: string;
  root_causes: RootCauseRead[];
  verified_fixes: VerifiedFixRead[];
  related: ErrorSummary[];
}

/** A single hit returned by the search endpoint. */
export interface SearchResultItem {
  slug: string;
  title: string;
  plain_english_explanation: string;
  root_cause_count: number;
  fix_count: number;
}

/** The envelope returned by the search endpoint. */
export interface SearchResponse {
  query: string;
  total: number;
  hits: SearchResultItem[];
  processing_time_ms: number;
}

/** A lightweight typeahead suggestion (slug + title only). */
export interface AutocompleteSuggestion {
  slug: string;
  title: string;
}

/** The envelope returned by the autocomplete endpoint. */
export interface AutocompleteResponse {
  query: string;
  suggestions: AutocompleteSuggestion[];
}

/** Payload for a single root cause when creating an error. */
export interface RootCauseCreate {
  description: string;
}

/** Payload for a single verified fix when creating an error. */
export interface VerifiedFixCreate {
  before_code_snippet: string;
  after_code_snippet: string;
  explanation: string;
}

/** Payload for creating an error with its root causes and verified fixes. */
export interface ErrorCreate {
  title: string;
  plain_english_explanation: string;
  /** Optional explicit slug; generated from the title server-side if omitted. */
  slug?: string | null;
  root_causes: RootCauseCreate[];
  verified_fixes: VerifiedFixCreate[];
}
