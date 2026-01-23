import axios from 'axios';

/**
 * Shared axios instance for all API calls
 *
 * This provides a single source of truth for:
 * - Base URL configuration
 * - Request/response interceptors
 * - Error handling
 * - Authentication headers (future)
 *
 * All services should use this instance instead of creating their own.
 */
export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor for adding auth tokens (placeholder for future)
 */
apiClient.interceptors.request.use(
  (config) => {
    // Future: Add auth token
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor for consistent error handling
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Future: Add global error handling (toast notifications, etc.)
    return Promise.reject(error);
  }
);
