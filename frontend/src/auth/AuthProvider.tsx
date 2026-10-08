import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useMemo } from 'react'
import { apiGet, apiPost } from '../api/client'
import { onSessionExpired } from '../api/sessionEvents'
import { clearAssessment } from '../analysis/assessmentStore'
import { AuthContext, type SessionResponse, type SessionUser } from './context'
import { SESSION_KEY, deriveAuthStatus, dropSession, type SessionData } from './session'

/**
 * Authentication state for the app shell.
 *
 * The session token lives only in an HttpOnly cookie set by the backend;
 * this client never reads or stores it. On load we ask the backend who we
 * are (GET /auth/session). Any failure fails closed → unauthenticated, so
 * protected routes stay locked. The backend remains the authority.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const session = useQuery<SessionData>({
    queryKey: SESSION_KEY,
    queryFn: () => apiGet<SessionResponse>('/auth/session'),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const user: SessionUser | null = session.data?.user ?? null

  // The backend is the authority: a 401 on any protected call drops our local
  // session copy, which lets ProtectedRoute bounce the user to /login.
  useEffect(() => onSessionExpired(() => dropSession(queryClient)), [queryClient])

  const status = deriveAuthStatus(session)

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
      // Clearing local state is always safe: the cookie is HttpOnly and the
      // server clears it on logout; even a network error must not keep us signed in.
    } finally {
      // setQueryData(null), not removeQueries: an active observer must be
      // handed a value or the shell stays mounted (see auth/session.ts).
      dropSession(queryClient)
      clearAssessment()
    }
  }, [queryClient])

  const value = useMemo(
    () => ({ status, user, signIn, signUp, signOut }),
    [status, user, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
