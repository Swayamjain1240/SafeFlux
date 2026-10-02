import { ApiError } from '../api/client'

/** Extract a safe, user-facing message from any thrown value. */
export function safeErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Something went wrong. Please try again.'
}
