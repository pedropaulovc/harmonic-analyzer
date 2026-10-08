import manifest from './.vite/deployment-assets.json' with { type: 'json' }

async function fetchChunk(request, env, chunk) {
  // Never forward Range/If-None-Match: each transport piece must be a full 200.
  const url = new URL(chunk.path, request.url)
  url.search = ''
  const response = await env.ASSETS.fetch(new Request(url, { method: 'GET' }))
  const length = response.headers.get('content-length')
  if (response.status !== 200 || !response.body
    || (length !== null && length !== String(chunk.byteLength))) {
    await response.body?.cancel()
    throw new Error(`Deployment chunk unavailable or wrong length: ${chunk.path}`)
  }
  return response
}

export default {
  async fetch(request, env) {
    const asset = manifest.assets[new URL(request.url).pathname]
    if (!asset) return env.ASSETS.fetch(request)
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } })
    }
    const headers = {
      'Content-Type': asset.contentType,
      'Content-Length': String(asset.byteLength),
      'ETag': `"${asset.sha256}"`,
      'Cache-Control': 'public, max-age=0, must-revalidate',
      'X-Content-Type-Options': 'nosniff',
    }
    const candidates = (request.headers.get('if-none-match') ?? '').split(',').map(value => value.trim())
    if (candidates.some(value => value === '*' || value === headers.ETag || value === `W/${headers.ETag}`)) {
      return new Response(null, {
        status: 304,
        headers: { ETag: headers.ETag, 'Cache-Control': headers['Cache-Control'] },
      })
    }
    if (request.method === 'HEAD') return new Response(null, { headers })
    let first
    try {
      first = await fetchChunk(request, env, asset.chunks[0])
    } catch {
      return new Response('Deployment asset chunk is unavailable', { status: 502 })
    }
    // A fixed-length stream preserves HTTP Content-Length without holding the
    // complete GLB or playback module in the isolate's 128 MiB heap.
    const transport = new FixedLengthStream(asset.byteLength)
    const pump = async () => {
      for (const [index, chunk] of asset.chunks.entries()) {
        const response = index === 0 ? first : await fetchChunk(request, env, chunk)
        let observed = 0
        const counter = new TransformStream({
          transform(bytes, controller) {
            observed += bytes.byteLength
            if (observed > chunk.byteLength) throw new Error(`Oversized deployment chunk: ${chunk.path}`)
            controller.enqueue(bytes)
          },
          flush() {
            if (observed !== chunk.byteLength) throw new Error(`Truncated deployment chunk: ${chunk.path}`)
          },
        })
        await response.body.pipeThrough(counter).pipeTo(transport.writable, { preventClose: true, preventAbort: true })
      }
      const writer = transport.writable.getWriter()
      try { await writer.close() } finally { writer.releaseLock() }
    }
    // The response stream owns the pump lifetime. On error/cancellation, abort
    // the downstream body, so clients never parse a silently shortened asset.
    void pump().catch(async error => {
      await transport.writable.abort(error).catch(() => {})
    })
    return new Response(transport.readable, { headers })
  },
}
