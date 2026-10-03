/** Client-side validation helpers (UX only — the backend re-validates). */

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export function isValidEmail(value: string): boolean {
  return EMAIL_PATTERN.test(value.trim())
}

export interface LoginFields {
  email: string
  password: string
}

export function validateLogin(fields: LoginFields): Partial<Record<keyof LoginFields, string>> {
  const errors: Partial<Record<keyof LoginFields, string>> = {}
  if (!fields.email.trim()) errors.email = 'Email is required.'
  else if (!isValidEmail(fields.email)) errors.email = 'Enter a valid email address.'
  if (!fields.password) errors.password = 'Password is required.'
  return errors
}

export interface SignupFields {
  fullName: string
  email: string
  password: string
  confirmPassword: string
}

export function validateSignupStep1(
  fields: Pick<SignupFields, 'fullName' | 'email'>,
): Partial<Record<'fullName' | 'email', string>> {
  const errors: Partial<Record<'fullName' | 'email', string>> = {}
  const name = fields.fullName.trim()
  if (!name) errors.fullName = 'Full name is required.'
  else if (name.length < 2) errors.fullName = 'Name is too short.'
  else if (name.length > 120) errors.fullName = 'Name is too long.'
  if (!fields.email.trim()) errors.email = 'Email is required.'
  else if (!isValidEmail(fields.email)) errors.email = 'Enter a valid email address.'
  return errors
}

export function validateSignupStep2(
  fields: Pick<SignupFields, 'password' | 'confirmPassword'>,
): Partial<Record<'password' | 'confirmPassword', string>> {
  const errors: Partial<Record<'password' | 'confirmPassword', string>> = {}
  if (!fields.password) errors.password = 'Password is required.'
  else if (fields.password.length < 8) errors.password = 'Use at least 8 characters.'
  else if (fields.password.length > 128) errors.password = 'Password is too long.'
  if (fields.confirmPassword !== fields.password)
    errors.confirmPassword = 'Passwords do not match.'
  return errors
}
