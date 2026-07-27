/**
 * Shared authentication utility helpers and constants.
 */

export const AUTH_TOKEN_KEY = 'gaiaos_admin_token';

/** Returns true if an admin JWT access token exists in localStorage. */
export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem(AUTH_TOKEN_KEY));
}
