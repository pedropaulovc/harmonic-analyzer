import { defineConfig } from 'vite'

// Served from a project page (https://<user>.github.io/harmonic-analyzer/), so
// asset URLs must be relative to that sub-path, not to the domain root.
export default defineConfig({
  base: process.env.SIMULATOR_BASE ?? '/harmonic-analyzer/',
  build: {
    target: 'es2022',
    // The GLB is large; don't let Rollup inline anything and don't warn about
    // three.js's own bundle size — it is expected.
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 1500,
  },
  server: { open: true },
})
