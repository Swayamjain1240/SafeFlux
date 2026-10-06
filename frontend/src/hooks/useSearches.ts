import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchSearchCapabilities, runSearch } from '../api/searches'
import type { SearchResult, SearchRunInput } from '../types/search'

/**
 * Search hooks (Part 7).
 *
 * The capability query drives every control, so the browser can only offer
 * variables the server allowlists. The run is a mutation (not a query) because
 * it is an expensive, explicitly triggered action: react-query then gives the
 * pending state for free, which is what stops a double click from starting two
 * searches.
 */

export const searchKeys = {
  capabilities: ['searches', 'capabilities'] as const,
}

export function useSearchCapabilities() {
  return useQuery({
    queryKey: searchKeys.capabilities,
    queryFn: fetchSearchCapabilities,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}

export function useRunSearch() {
  return useMutation<SearchResult, unknown, SearchRunInput>({
    mutationFn: (payload: SearchRunInput) => runSearch(payload),
  })
}
