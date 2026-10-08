import { createServer } from 'node:http'
import { createReadStream } from 'node:fs'
import { readFile, readdir, stat } from 'node:fs/promises'
import { extname, join, resolve, sep } from 'node:path'
import { sha256File, VIDEO_IDS } from './verify-reference.mjs'
import { originalAccessIndex, sameOriginalFile } from './native-access-index.mjs'

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.glb': 'model/gltf-binary', '.mp4': 'video/mp4', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2' }

export async function distManifest(distRoot) {
  const files = []
  async function visit(directory, relative = '') {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const name = relative ? `${relative}/${entry.name}` : entry.name, path = join(directory, entry.name)
      if (entry.isDirectory()) await visit(path, name)
      else if (entry.isFile()) { const info = await stat(path); files.push({ path: name, bytes: info.size, sha256: await sha256File(path) }) }
      else throw new Error(`Built dist contains unsupported symbolic/special asset: ${name}`)
    }
  }
  await visit(distRoot)
  return files.sort((a, b) => a.path.localeCompare(b.path))
}

/** Infer the base of the actual build, not the dev server or a guessed root. */
export function buildBase(indexHtml, requested = undefined) {
  const src = /<script\b[^>]*\bsrc=["']([^"']+)["']/i.exec(indexHtml)?.[1]
  if (!src) throw new Error('Built index.html has no module asset; run the production build first')
  let inferred
  if (src.startsWith('/')) inferred = src.slice(0, src.lastIndexOf('/assets/') + 1)
  else if (src.startsWith('./assets/') || src.startsWith('assets/')) inferred = '/'
  else throw new Error(`Unsupported built module URL: ${src}`)
  const base = requested ?? inferred
  if (!base.startsWith('/') || !base.endsWith('/') || base.includes('..') || /[?#\\]/.test(base)) throw new Error(`Invalid SIMULATOR_BASE: ${base}`)
  if (src.startsWith('/') && !src.startsWith(`${base}assets/`)) throw new Error(`SIMULATOR_BASE ${base} differs from actual built module ${src}`)
  return base
}

/** One owned ephemeral server. Never connects to, kills, or reuses a parent's dev service. */
export async function serveDist(distRoot, { base, requests = [], signal, referenceRoot, port = 0 } = {}) {
  const root = resolve(distRoot)
  const index = await readFile(join(root, 'index.html'), 'utf8')
  const basePath = buildBase(index, base)
  const sockets = new Set()
  // The compressed original scan finishes before listen(), never inside an HTTP request.
  const access = new Map()
  if (referenceRoot) for (const id of VIDEO_IDS) {
    const path = resolve(referenceRoot, 'videos', `${id}.mp4`)
    try {
      const prepared = await originalAccessIndex(path, id, { signal })
      access.set(id, { ...prepared, body: JSON.stringify(prepared.index) })
    } catch (error) { if (error.code !== 'ENOENT') throw error }
  }
  const server = createServer(async (request, response) => {
    let pathname = '', path
    try {
      pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
      if (pathname !== basePath.slice(0, -1) && !pathname.startsWith(basePath)) { response.writeHead(404); response.end('Not under the built simulator base'); return }
      if (pathname === basePath.slice(0, -1)) { response.writeHead(308, { location: `${basePath}${new URL(request.url, 'http://localhost').search}` }); response.end(); return }
      const relative = pathname.slice(basePath.length) || 'index.html'
      const indexRequest = /^reference-media\/([A-Za-z0-9_-]+)\.access.json$/.exec(relative)
      if (indexRequest) {
        const prepared = access.get(indexRequest[1])
        if (!prepared) { response.writeHead(404); response.end('Original safe-access index unavailable'); return }
        const current = await stat(resolve(referenceRoot, 'videos', `${indexRequest[1]}.mp4`))
        if (!sameOriginalFile(prepared.identity, current)) { response.writeHead(409); response.end('Original media changed after indexing'); return }
        response.writeHead(200, { 'content-type': MIME['.json'], 'cache-control': 'no-cache', 'content-length': Buffer.byteLength(prepared.body) })
        requests.push({ url: request.url, status: 200, path: relative, bytes: Buffer.byteLength(prepared.body) })
        response.end(request.method === 'HEAD' ? undefined : prepared.body)
        return
      }
      const media = /^reference-media\/([A-Za-z0-9_-]+)\.mp4$/.exec(relative)
      if (media) {
        if (!referenceRoot || !VIDEO_IDS.includes(media[1])) { response.writeHead(404); response.end('Original reference media unavailable'); return }
        path = resolve(referenceRoot, 'videos', `${media[1]}.mp4`)
      } else {
        path = resolve(root, relative)
        if (path !== root && !path.startsWith(`${root}${sep}`)) { response.writeHead(403); response.end(); return }
      }
      const info = await stat(path)
      if (!info.isFile()) { response.writeHead(404); response.end(); return }
      if (media && !sameOriginalFile(access.get(media[1])?.identity ?? {}, info)) { response.writeHead(409); response.end('Original media changed after indexing'); return }
      const headers = { 'content-type': MIME[extname(path)] ?? 'application/octet-stream', 'cache-control': 'no-cache', 'accept-ranges': 'bytes', 'referrer-policy': 'strict-origin-when-cross-origin' }
      let start = 0, end = info.size - 1, status = 200
      if (request.headers.range) {
        const match = /^bytes=(\d+)-(\d*)$/.exec(request.headers.range)
        if (!match) { response.writeHead(416, { 'content-range': `bytes */${info.size}` }); response.end(); return }
        start = Number(match[1]); end = match[2] ? Number(match[2]) : end
        if (start > end || start >= info.size || end >= info.size) { response.writeHead(416, { 'content-range': `bytes */${info.size}` }); response.end(); return }
        status = 206; headers['content-range'] = `bytes ${start}-${end}/${info.size}`
      }
      headers['content-length'] = Math.max(0, end - start + 1)
      requests.push({ url: request.url, status, path: relative, bytes: Number(headers['content-length']) })
      response.writeHead(status, headers)
      if (request.method === 'HEAD') response.end()
      else {
        const stream = createReadStream(path, { start, end })
        stream.on('error', error => response.destroy(error))
        response.on('close', () => stream.destroy())
        stream.pipe(response)
      }
    } catch (error) {
      requests.push({ url: request.url, status: 404, error: error.message, pathname })
      if (!response.headersSent) response.writeHead(404)
      response.end('Built asset not found')
    }
  })
  server.on('connection', socket => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)) })
  await new Promise((ready, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', ready) })
  const address = server.address()
  let closed = false
  const close = async () => {
    if (closed) return
    closed = true
    for (const socket of sockets) socket.destroy()
    await new Promise(resolveClosed => server.close(resolveClosed))
  }
  signal?.addEventListener('abort', () => void close(), { once: true })
  return { url: `http://127.0.0.1:${address.port}${basePath}`, base: basePath, close }
}
