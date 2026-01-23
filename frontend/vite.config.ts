import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import { config as dotenvConfig } from 'dotenv'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load .env.dev from project root (standard for this project)
  dotenvConfig({ path: path.resolve(__dirname, '../.env.dev') })

  // Also load standard .env files for compatibility
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '')

  // Read ports from env (process.env from dotenv, env from loadEnv)
  const FRONTEND_PORT = parseInt(process.env.FRONTEND_PORT || env.FRONTEND_PORT || '5174', 10)
  const BACKEND_PORT = process.env.BACKEND_PORT || env.BACKEND_PORT || '8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: true,
      port: FRONTEND_PORT,
      proxy: {
        '/api': {
          // Use VITE_API_PROXY_TARGET env var for Docker compatibility
          // In Docker: http://backend:8000 (service name)
          // Local dev: http://localhost:{BACKEND_PORT} (backend port from .env)
          target: process.env.VITE_API_PROXY_TARGET || `http://localhost:${BACKEND_PORT}`,
          changeOrigin: true,
          // Follow redirects to avoid CORS errors when backend redirects (e.g., trailing slash removal)
          followRedirects: true,
        },
      },
    },
    test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    exclude: ['**/node_modules/**', '**/e2e/**', '**/*.spec.ts'],
    server: {
      deps: {
        inline: ['lightweight-charts'],
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        'src/types/',
        'e2e/',
        '**/*.test.{ts,tsx}',
        '**/*.spec.{ts,tsx}',
      ],
    },
    },
  }
})
