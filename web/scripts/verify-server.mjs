import { createServer } from 'node:http'
import { createReadStream } from 'node:fs'
import { readFile, readdir, stat } from 'node:fs/promises'
import { extname, join, resolve, sep } from 'node:path'
import { sha256File } from './verify-reference.mjs'

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.glb': 'model/gltf-binary', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2' }

export async function distManifest(distRoot) {
  const files = []
  async function visit(directory, relative = '') {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const name = join(relative, entry.name), path = join(directory, entry.name)
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
export async function serveDist(distRoot, { base, requests = [], signal } = {}) {
  const root = resolve(distRoot)
  const index = await readFile(join(root, 'index.html'), 'utf8')
  const basePath = buildBase(index, base)
  const sockets = new Set()
  const server = createServer(async (request, response) => {
    let pathname = '', path
    try {
      pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
      if (pathname !== basePath.slice(0, -1) && !pathname.startsWith(basePath)) { response.writeHead(404); response.end('Not under the built simulator base'); return }
      if (pathname === basePath.slice(0, -1)) { response.writeHead(308, { location: `${basePath}${new URL(request.url, 'http://localhost').search}` }); response.end(); return }
      const relative = pathname.slice(basePath.length) || 'index.html'
      path = resolve(root, relative)
      if (path !== root && !path.startsWith(`${root}${sep}`)) { response.writeHead(403); response.end(); return }
      const info = await stat(path)
      if (!info.isFile()) { response.writeHead(404); response.end(); return }
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
  await new Promise((ready, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', ready) })
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
