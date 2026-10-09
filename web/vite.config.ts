import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import { syncDevMiddleware } from './sync/dev-middleware'

// Served from a project page (https://<user>.github.io/harmonic-analyzer/), so
// asset URLs must be relative to that sub-path, not to the domain root.
export default defineConfig({
  base: process.env.SIMULATOR_BASE ?? '/harmonic-analyzer/',
  plugins: [syncDevMiddleware()],
  build: {
    target: 'es2022',
    // The GLB is large; don't let Rollup inline anything and don't warn about
    // three.js's own bundle size — it is expected.
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        fit: fileURLToPath(new URL('./fit.html', import.meta.url)),
        align: fileURLToPath(new URL('./align.html', import.meta.url)),
      },
    },
  },
  server: { open: true },
})
