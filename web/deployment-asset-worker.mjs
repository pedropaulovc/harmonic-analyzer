// Explicit codings override wildcard preferences, including explicit q=0.
export function negotiateCoding(header, variants) {
  if (header === null || header.trim() === '') return variants.identity ? 'identity' : null
  const preferences = new Map()
  for (const item of header.split(',')) {
    const [name, ...parameters] = item.toLowerCase().split(';').map(value => value.trim())
    let q = 1
    for (const parameter of parameters) {
      const [key, value] = parameter.split('=').map(value => value.trim())
      if (key === 'q') q = /^(?:0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$/.test(value ?? '') ? Number(value) : 0
    }
    // Conflicting duplicates are conservatively treated as refusal if any is 0.
    preferences.set(name, Math.min(preferences.get(name) ?? 1, q))
  }
  const quality = coding => preferences.get(coding) ?? (coding === 'identity'
    ? (preferences.get('*') === 0 ? 0 : 1) : (preferences.get('*') ?? 0))
  let selected = null
  let best = 0
  for (const coding of ['gzip', 'identity']) {
    const q = quality(coding)
    if (variants[coding] && q > best) { selected = coding; best = q }
  }
  return selected
}

async function fetchChunk(request, env, chunk) {
  const url = new URL(chunk.path, request.url)
  url.search = ''
  const response = await env.ASSETS.fetch(new Request(url, {
    method: 'GET', headers: { 'Accept-Encoding': 'identity' },
  }))
  const length = response.headers.get('content-length')
  const encoding = response.headers.get('content-encoding')
  if (response.status !== 200 || !response.body
    || (length !== null && length !== String(chunk.byteLength))
    || (encoding !== null && encoding.toLowerCase() !== 'identity')) {
    await response.body?.cancel()
    throw Object.assign(new Error(`Deployment chunk unavailable or wrong representation: ${chunk.path}`), {
      responseStatus: response.status, responseContentLength: length,
      responseContentEncoding: encoding, expectedContentLength: chunk.byteLength,
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
      responseStatus: error.responseStatus, responseContentLength: error.responseContentLength,
      responseContentEncoding: error.responseContentEncoding, expectedContentLength: error.expectedContentLength,
    }),
  }))
}

export function createAssetWorker(manifest) {
  return {
    async fetch(request, env) {
      const path = new URL(request.url).pathname
      const asset = manifest.assets[path]
      if (!asset) return env.ASSETS.fetch(request)
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } })
      }
      const coding = negotiateCoding(request.headers.get('accept-encoding'), asset.variants)
      if (!coding) return new Response(null, { status: 406, headers: { Vary: 'Accept-Encoding' } })
      const variant = asset.variants[coding]
      const headers = {
        'Content-Type': asset.contentType, 'Content-Length': String(variant.byteLength),
        ETag: `"${variant.sha256}"`, Vary: 'Accept-Encoding',
        // Preserve the sealed encoding; observed automatic zstd transforms of
        // reconstructed JS failed mid-stream in native browser controls.
        'Cache-Control': 'public, max-age=0, must-revalidate, no-transform',
        'X-Content-Type-Options': 'nosniff',
        ...(coding === 'identity' ? {} : { 'Content-Encoding': coding }),
      }
      const candidates = (request.headers.get('if-none-match') ?? '').split(',').map(value => value.trim())
      if (candidates.some(value => value === '*' || value === headers.ETag || value === `W/${headers.ETag}`)) {
        return new Response(null, { status: 304, headers: {
          ETag: headers.ETag, Vary: headers.Vary, 'Cache-Control': headers['Cache-Control'],
        } })
      }
      if (request.method === 'HEAD') return new Response(null, { headers, encodeBody: 'manual' })
      let first
      try { first = await fetchChunk(request, env, variant.chunks[0]) }
      catch (error) {
        reportChunkFailure(path, variant.chunks[0].path, error)
        return new Response('Deployment asset chunk is unavailable', { status: 502, headers: { Vary: 'Accept-Encoding', 'Cache-Control': 'no-store' } })
      }
      // No runtime compression, JS buffer transforms, or materialized arrays.
      // Only one native ASSETS stream is open at a time; fixed encoded length
      // detects truncation even when the binding omits per-piece lengths.
      const transport = new FixedLengthStream(variant.byteLength)
      let activeChunkPath = variant.chunks[0].path
      const pump = async () => {
        for (const [index, chunk] of variant.chunks.entries()) {
          activeChunkPath = chunk.path
          const response = index === 0 ? first : await fetchChunk(request, env, chunk)
          await response.body.pipeTo(transport.writable, { preventClose: true, preventAbort: true })
        }
        const writer = transport.writable.getWriter()
        try { await writer.close() } finally { writer.releaseLock() }
      }
      void pump().catch(async error => {
        reportChunkFailure(path, activeChunkPath, error)
        await transport.writable.abort(error).catch(() => {})
      })
      // Cloudflare must not gzip these already-encoded bytes a second time.
      return new Response(transport.readable, { headers, encodeBody: 'manual' })
    },
  }
}
