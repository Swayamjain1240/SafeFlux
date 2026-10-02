import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../api/health'

/** Live backend health probe (cached briefly, refreshed for the status badge). */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
    staleTime: 5_000,
    retry: 1,
  })
}
