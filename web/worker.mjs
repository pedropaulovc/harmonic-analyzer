import { DEPLOYMENT_MODEL, MODEL_RELEASE_URL, MODEL_ROUTE } from './deployment-model.mjs'

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname !== MODEL_ROUTE) return env.ASSETS.fetch(request)
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } })
    }
    let upstream
    try {
      upstream = await fetch(MODEL_RELEASE_URL, { method: request.method, redirect: 'follow' })
    } catch {
      return new Response('Approved model release is unavailable', { status: 502 })
    }
    const length = upstream.headers.get('content-length')
    if (upstream.status !== 200 || length !== String(DEPLOYMENT_MODEL.representation.byteLength)) {
      await upstream.body?.cancel()
      return new Response('Approved model release returned an unexpected status or byte length', { status: 502 })
    }
    // Do not buffer 39 MiB in a Worker isolate. The browser independently checks
    // SHA256 and byte length against its compiled approval before parsing the GLB.
    return new Response(request.method === 'HEAD' ? null : upstream.body, {
      headers: {
        'Content-Type': 'model/gltf-binary',
        'Content-Length': String(DEPLOYMENT_MODEL.representation.byteLength),
        'Cache-Control': 'public, max-age=3600',
        'ETag': `"${DEPLOYMENT_MODEL.representation.sha256}"`,
        'X-Content-Type-Options': 'nosniff',
      },
    })
  },
}
