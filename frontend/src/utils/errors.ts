/**
 * Extract user-friendly error message from various error types
 *
 * Handles Axios error responses (with `response.data.detail`),
 * standard Error objects, and unknown error types.
 *
 * @param err - The caught error value
 * @param fallback - Default message when no specific message can be extracted
 * @returns A human-readable error string
 */
export const extractErrorMessage = (err: unknown, fallback = 'An unexpected error occurred'): string => {
  if (err && typeof err === 'object') {
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.message) {
      return axiosErr.message;
    }
  }
  return fallback;
};
