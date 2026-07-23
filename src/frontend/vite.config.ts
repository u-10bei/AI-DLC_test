/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend base URL is externalised (NFR-M05 / NFR-M03). In dev, requests to the
// API paths are proxied to the backend; in production the built bundle is served by
// the backend itself (U08-H4) so same-origin relative URLs just work.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Every backend route the frontend calls. Same-origin in production.
      '/sessions': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/masters': 'http://localhost:8000',
      '/optimizations': 'http://localhost:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    css: false,
  },
})
