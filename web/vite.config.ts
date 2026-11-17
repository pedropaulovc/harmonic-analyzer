import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    target: 'es2022',
    // The GLB is large; don't let Rollup inline anything and don't warn about
    // three.js's own bundle size — it is expected.
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 1500,
  },
  server: { open: true },
})
