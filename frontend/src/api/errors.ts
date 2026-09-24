import { ApiError } from './client.ts';

export interface UserFacingError {
  title: string;
  message: string;
  /** Whether trying the same action again could reasonably succeed. */
  retryable: boolean;
}

const GENERIC: UserFacingError = {
  title: 'Something went wrong',
  message: 'RepoPilot hit an unexpected error. Please try again.',
  retryable: true,
};

const UNREACHABLE: UserFacingError = {
  title: 'Cannot reach the RepoPilot API',
  message: 'Check that the backend is running and reachable, then try again.',
  retryable: true,
};

/**
 * Turn any thrown value into a message that is safe and useful to show. Backend `detail`
 * strings are fixed, user-facing messages, so they are shown as-is; anything else is replaced
 * with generic text.
 */
export function toUserFacingError(error: unknown): UserFacingError {
  if (!(error instanceof ApiError)) return GENERIC;
  const detail = error.detail;
  const wait =
    error.retryAfterSeconds !== null ? ` Try again in about ${error.retryAfterSeconds}s.` : '';

  // RepoPilot's own 5xx responses always carry a JSON detail. A 5xx without one comes from
  // something in front of the API (e.g. the dev proxy when the backend is down).
  if (error.status === 0 || (error.status >= 500 && detail === null)) return UNREACHABLE;

  switch (error.status) {
    case 404:
      return {
        title: 'Not found',
        message: detail ?? 'The requested item does not exist.',
        retryable: false,
      };
    case 422:
      return {
        title: 'Invalid request',
        message: 'Check the repository owner, name, and pull request number.',
        retryable: false,
      };
    case 429:
      return {
        title: 'GitHub rate limit reached',
        message: `${detail ?? 'GitHub is limiting requests.'}${wait}`,
        retryable: true,
      };
    case 502:
      return {
        title: 'Upstream service error',
        message: detail ?? 'A service RepoPilot depends on returned an error.',
        retryable: true,
      };
    case 503:
      return {
        title: 'Service unavailable',
        message: `${detail ?? 'RepoPilot cannot complete this request right now.'}${wait}`,
        retryable: true,
      };
    case 504:
      return {
        title: 'Review timed out',
        message: detail ?? 'The AI provider did not respond in time.',
        retryable: true,
      };
    default:
      return error.status >= 500 ? GENERIC : { ...GENERIC, message: detail ?? GENERIC.message };
  }
}

/** For lookups by ID: a malformed ID (422) means the same to the user as an unknown one. */
export function isMissingResource(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 422);
}
