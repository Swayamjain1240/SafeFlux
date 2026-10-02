import { createContext, useContext } from 'react'

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

export interface SessionUser {
  id: string
  fullName: string
  email: string
}

export interface SessionResponse {
  user: SessionUser
}

export interface AuthContextValue {
  status: AuthStatus
  user: SessionUser | null
  signIn: (email: string, password: string) => Promise<void>
  signUp: (fullName: string, email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return context
}
