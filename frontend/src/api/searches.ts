import { apiGet, apiPost } from './client'
import type { SearchCapabilities, SearchResult, SearchRunInput } from '../types/search'

/**
 * Deterministic search API — mirrors /api/v1/searches/* (Part 7).
 *
 * The session cookie is the only authorization; no owner or budget ceiling is
 * ever supplied by the client beyond values the server already allowlists.
 */

export function fetchSearchCapabilities(): Promise<SearchCapabilities> {
  return apiGet<SearchCapabilities>('/searches/capabilities')
}

/**
 * One bounded search. The server enforces every budget, so the client never
 * needs to know a ceiling — it only reports what came back.
 */
export function runSearch(payload: SearchRunInput): Promise<SearchResult> {
  return apiPost<SearchResult>('/searches/run', payload)
}
