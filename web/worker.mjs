import manifest from './.vite/deployment-assets.json' with { type: 'json' }

async function fetchChunk(request, env, chunk) {
  // Never forward Range/If-None-Match: each transport piece must be a full 200.
  const url = new URL(chunk.path, request.url)
  url.search = ''
  const response = await env.ASSETS.fetch(new Request(url, {
    method: 'GET', headers: { 'Accept-Encoding': 'identity' },
  }))
  const length = response.headers.get('content-length')
  if (response.status !== 200 || !response.body
    || (length !== null && length !== String(chunk.byteLength))) {
    await response.body?.cancel()
    throw Object.assign(new Error(`Deployment chunk unavailable or wrong length: ${chunk.path}`), {
      responseStatus: response.status,
      responseContentLength: length,
      responseContentEncoding: response.headers.get('content-encoding'),
      expectedContentLength: chunk.byteLength,
    })
  }
  return response
}

function reportChunkFailure(path, chunkPath, error) {
  console.error(JSON.stringify({
    kind: 'deployment-asset-stream-abort', path, chunkPath,
    errorName: error instanceof Error ? error.name : 'UnknownError',
    errorMessage: error instanceof Error ? error.message : String(error),
    ...(error?.responseStatus === undefined ? {} : {
      responseStatus: error.responseStatus,
      responseContentLength: error.responseContentLength,
      responseContentEncoding: error.responseContentEncoding,
      expectedContentLength: error.expectedContentLength,
    }),
  }))
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname
    const asset = manifest.assets[path]
    if (!asset) return env.ASSETS.fetch(request)
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } })
    }
    const headers = {
      'Content-Type': asset.contentType,
      'Content-Length': String(asset.byteLength),
      'ETag': `"${asset.sha256}"`,
      // Native browser control: zstd-transformed reconstructed JS failed mid-
      // stream; identity completed with HTTP/3 unchanged. Prevent edge transforms
      // per https://developers.cloudflare.com/speed/optimization/content/compression/.
      'Cache-Control': 'public, max-age=0, must-revalidate, no-transform',
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
    } catch (error) {
      reportChunkFailure(path, asset.chunks[0].path, error)
      return new Response('Deployment asset chunk is unavailable', { status: 502 })
    }
    // A fixed-length stream preserves HTTP Content-Length without holding the
    // complete GLB or playback module in the isolate's 128 MiB heap.
    const transport = new FixedLengthStream(asset.byteLength)
    let activeChunkPath = asset.chunks[0].path
    const pump = async () => {
      for (const [index, chunk] of asset.chunks.entries()) {
        activeChunkPath = chunk.path
        const response = index === 0 ? first : await fetchChunk(request, env, chunk)
        // Producer checks seal each immutable ASSETS piece and reconstructed SHA.
        // Native ASSETS may omit Content-Length; validate it when visible, then
        // pipe directly without per-buffer JS transforms/materialized arrays.
        // The outer FixedLengthStream enforces actual whole-file byte length.
        await response.body.pipeTo(transport.writable, { preventClose: true, preventAbort: true })
      }
      const writer = transport.writable.getWriter()
      try { await writer.close() } finally { writer.releaseLock() }
    }
    // The response stream owns the pump lifetime. On error/cancellation, abort
    // the downstream body, so clients never parse a silently shortened asset.
    void pump().catch(async error => {
      reportChunkFailure(path, activeChunkPath, error)
      await transport.writable.abort(error).catch(() => {})
    })
    return new Response(transport.readable, { headers })
  },
}
