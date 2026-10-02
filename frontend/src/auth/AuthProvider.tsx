import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useMemo } from 'react'
import { apiGet, apiPost } from '../api/client'
import {
  AuthContext,
  type AuthStatus,
  type SessionResponse,
  type SessionUser,
} from './context'

const SESSION_KEY = ['auth', 'session'] as const

/**
 * Authentication state for the app shell.
 *
 * Part 1 note: /auth/* endpoints ship in Part 2. Until then every session
 * check fails closed → unauthenticated, so protected routes stay locked.
 * The backend remains the authority regardless of this client state.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const session = useQuery<SessionResponse>({
    queryKey: SESSION_KEY,
    queryFn: () => apiGet<SessionResponse>('/auth/session'),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const user: SessionUser | null = session.data?.user ?? null

  const status: AuthStatus = session.isPending
    ? 'loading'
    : session.isSuccess && session.data
      ? 'authenticated'
      : 'unauthenticated'

  const signIn = useCallback(
    async (email: string, password: string) => {
      const data = await apiPost<SessionResponse>('/auth/login', { email, password })
      queryClient.setQueryData(SESSION_KEY, data)
    },
    [queryClient],
  )

  const signUp = useCallback(
    async (fullName: string, email: string, password: string) => {
      const data = await apiPost<SessionResponse>('/auth/signup', { fullName, email, password })
      queryClient.setQueryData(SESSION_KEY, data)
    },
    [queryClient],
  )

  const signOut = useCallback(async () => {
    try {
      await apiPost('/auth/logout')
    } catch {
      // Clearing local state is always safe; backend sessions are handled in Part 2.
    } finally {
      queryClient.removeQueries({ queryKey: SESSION_KEY })
    }
  }, [queryClient])

  const value = useMemo(
    () => ({ status, user, signIn, signUp, signOut }),
    [status, user, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
