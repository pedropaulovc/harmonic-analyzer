import manifest from './.vite/deployment-assets.json' with { type: 'json' }
import { createAssetWorker, negotiateCoding } from './deployment-asset-worker.mjs'

const assets = createAssetWorker(manifest)

export default {
  async fetch(request, env) {
    // Temporary, parent-owned edge probe: remove after native negotiation
    // diagnostics. No asset body or unrelated request metadata is exposed.
    if (request.headers.get('x-transport-probe') === '1') {
      const asset = manifest.assets[new URL(request.url).pathname]
      const header = request.headers.get('accept-encoding')
      const client = request.cf?.clientAcceptEncoding
      const selected = asset ? negotiateCoding(client ?? header, asset.variants) : null
      const diagnostics = {
        workerProbe: 'transport-encoding-20261008',
        headerAcceptEncoding: header,
        clientAcceptEncoding: client ?? null,
        clientAcceptEncodingType: typeof client,
        selected,
        manifestRoute: Boolean(asset),
      }
      return new Response(request.method === 'HEAD' ? null : JSON.stringify(diagnostics), {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store, no-transform',
          'X-Transport-Probe': 'transport-encoding-20261008',
          'X-Transport-Header-Encoding': JSON.stringify(header),
          'X-Transport-Client-Encoding': JSON.stringify(client ?? null),
          'X-Transport-Selected-Encoding': selected ?? 'none',
          'X-Transport-Client-Encoding-Type': typeof client,
        },
      })
    }
    return assets.fetch(request, env)
  },
}
