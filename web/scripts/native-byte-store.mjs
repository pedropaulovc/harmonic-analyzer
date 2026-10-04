import { createHash, randomUUID } from 'node:crypto'
import { constants } from 'node:fs'
import { mkdir, mkdtemp, open, link, unlink, rmdir } from 'node:fs/promises'
import { join } from 'node:path'

const SHA256 = /^[a-f0-9]{64}$/
const RETENTIONS = new Set(['transient', 'static', 'reference', 'selected-case'])
const PREFIX = '/__native-qualification/'

class StoreError extends Error {
  constructor(code, status = 400) { super(code); this.code = code; this.status = status }
}
function checkSHA(sha) {
  if (typeof sha !== 'string' || !SHA256.test(sha)) throw new StoreError('invalid-sha256')
}
function checkRetention(retention) {
  if (!RETENTIONS.has(retention)) throw new StoreError('invalid-retention')
}
function digest(bytes) { return createHash('sha256').update(bytes).digest('hex') }
async function remove(path) {
  try { await unlink(path) } catch (error) { if (error.code !== 'ENOENT') throw error }
}

/**
 * Run-local binary CAS. Creation is synchronous; filesystem setup is awaited.
 * All methods except close reject after close starts. Unknown get/retain reject
 * with object-unavailable. release is idempotent; pinned objects survive release
 * until explicitly removed with close({ removeRetained: true }). retain upgrades
 * transient objects to selected-case. No earlier-run files are imported.
 */
export function createNativeByteStore({ root, token, maxObjectBytes, allowedOrigin } = {}) {
  if (typeof root !== 'string' || root.length === 0) throw new TypeError('root is required')
  if (typeof token !== 'string' || token.length === 0 || token.length > 1024) throw new TypeError('opaque token is required')
  if (!Number.isSafeInteger(maxObjectBytes) || maxObjectBytes < 1) throw new TypeError('maxObjectBytes must be a positive safe integer')
  if (allowedOrigin !== undefined && (typeof allowedOrigin !== 'string' || new URL(allowedOrigin).origin !== allowedOrigin || allowedOrigin === 'null')) throw new TypeError('allowedOrigin must be an exact HTTP(S) origin')
  if (allowedOrigin !== undefined && !/^https?:\/\//.test(allowedOrigin)) throw new TypeError('allowedOrigin must be HTTP(S)')
  const endpoint = `${PREFIX}${encodeURIComponent(token)}/`
  const objects = new Map(), temporary = new Set(), active = new Set(), locks = new Map()
  let closed = false, closing, directory
  const ready = (async () => {
    await mkdir(root, { recursive: true })
    directory = await mkdtemp(join(root, 'native-bytes-'))
    return directory
  })()
  // Setup errors remain observable through every operation without an unhandled rejection.
  ready.catch(() => {})
  function run(fn) {
    if (closed) return Promise.reject(new StoreError('store-closed', 503))
    const operation = Promise.resolve().then(fn)
    active.add(operation)
    operation.then(() => active.delete(operation), () => active.delete(operation))
    return operation
  }
  async function locked(sha, fn) {
    const prior = locks.get(sha) ?? Promise.resolve()
    const next = prior.catch(() => {}).then(fn)
    locks.set(sha, next)
    try { return await next } finally { if (locks.get(sha) === next) locks.delete(sha) }
  }
  function metadata(entry) { return { sha256: entry.sha256, byteLength: entry.byteLength, retention: entry.retention } }
  async function ingest(chunks, { retention = 'transient', expectedSHA, expectedLength } = {}) {
    checkRetention(retention)
    await ready
    const path = join(directory, `${randomUUID()}.tmp`)
    const file = await open(path, 'wx', 0o600)
    temporary.add(path)
    let byteLength = 0
    const hash = createHash('sha256')
    try {
      for await (const chunk of chunks) {
        if (!(chunk instanceof Uint8Array)) throw new StoreError('binary-body-required', 415)
        byteLength += chunk.byteLength
        if (!Number.isSafeInteger(byteLength) || byteLength > maxObjectBytes) throw new StoreError('object-too-large', 413)
        hash.update(chunk)
        let offset = 0
        while (offset < chunk.byteLength) {
          const { bytesWritten } = await file.write(chunk, offset, chunk.byteLength - offset)
          if (bytesWritten === 0) throw new StoreError('write-failed', 500)
          offset += bytesWritten
        }
      }
      if (expectedLength !== undefined && byteLength !== expectedLength) throw new StoreError('body-length-mismatch')
      const sha256 = hash.digest('hex')
      if (expectedSHA !== undefined && sha256 !== expectedSHA) throw new StoreError('sha256-mismatch', 422)
      await file.close()
      return await locked(sha256, async () => {
        const existing = objects.get(sha256)
        if (existing) {
          // The incoming stream was still independently hashed. Do not copy it
          // over the existing immutable object or allocate its bytes in memory.
          if (existing.retention === 'transient') existing.retention = retention
          return metadata(existing)
        }
        const casPath = join(directory, sha256)
        // Atomic publication without overwriting even an unexpected foreign file.
        await link(path, casPath)
        const entry = { sha256, byteLength, retention, path: casPath }
        objects.set(sha256, entry)
        return metadata(entry)
      })
    } finally {
      await file.close().catch(() => {})
      if (temporary.has(path)) {
        await remove(path)
        temporary.delete(path)
      }
    }
  }
  const store = {
    endpoint,
    put(bytes, { retention = 'transient' } = {}) {
      return run(() => {
        if (!(bytes instanceof Uint8Array)) throw new StoreError('binary-body-required', 415)
        if (bytes.byteLength > maxObjectBytes) throw new StoreError('object-too-large', 413)
        return ingest([bytes], { retention })
      })
    },
    get(sha) {
      return run(async () => {
        checkSHA(sha)
        return locked(sha, async () => {
          const entry = objects.get(sha)
          if (!entry) throw new StoreError('object-unavailable', 404)
          const file = await open(entry.path, constants.O_RDONLY | constants.O_NOFOLLOW)
          try {
            const stat = await file.stat()
            if (!stat.isFile() || stat.size !== entry.byteLength || stat.size > maxObjectBytes) throw new StoreError('object-integrity-failed', 422)
            const bytes = Buffer.allocUnsafe(entry.byteLength)
            let offset = 0
            while (offset < bytes.byteLength) {
              const { bytesRead } = await file.read(bytes, offset, bytes.byteLength - offset, offset)
              if (bytesRead === 0) throw new StoreError('object-integrity-failed', 422)
              offset += bytesRead
            }
            if ((await file.stat()).size !== entry.byteLength || digest(bytes) !== sha) throw new StoreError('object-integrity-failed', 422)
            return bytes
          } finally { await file.close() }
        })
      })
    },
    has(sha) { return run(() => { checkSHA(sha); return locked(sha, () => objects.has(sha)) }) },
    retain(sha) {
      return run(() => {
        checkSHA(sha)
        return locked(sha, () => {
          const entry = objects.get(sha)
          if (!entry) throw new StoreError('object-unavailable', 404)
          if (entry.retention === 'transient') entry.retention = 'selected-case'
          return metadata(entry)
        })
      })
    },
    release(sha) {
      return run(() => {
        checkSHA(sha)
        return locked(sha, async () => {
          const entry = objects.get(sha)
          if (!entry || entry.retention !== 'transient') return
          await remove(entry.path)
          objects.delete(sha)
        })
      })
    },
    close({ removeRetained = false } = {}) {
      if (closing) return closing
      closed = true
      closing = (async () => {
        await Promise.allSettled([...active])
        await ready
        for (const path of temporary) { await remove(path); temporary.delete(path) }
        for (const [sha, entry] of objects) {
          if (entry.retention === 'transient' || removeRetained) await remove(entry.path)
          objects.delete(sha)
        }
        // Never recursively remove a root or a foreign file added to our directory.
        try { await rmdir(directory) } catch (error) { if (!['ENOENT', 'ENOTEMPTY'].includes(error.code)) throw error }
      })()
      return closing
    },
    async handleRequest(req, res) {
      if (typeof req.url !== 'string' || !req.url.startsWith(PREFIX)) return false
      function send(status, body) {
        if (res.destroyed || res.writableEnded) return
        res.statusCode = status
        res.setHeader('Content-Type', 'application/json; charset=utf-8')
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('X-Content-Type-Options', 'nosniff')
        res.end(JSON.stringify(body))
      }
      try {
        if (!req.url.startsWith(endpoint)) throw new StoreError('endpoint-not-found', 404)
        const sha = req.url.slice(endpoint.length)
        checkSHA(sha) // Raw path only: no decoding, queries, slashes or traversal.
        const origin = req.headers.origin
        const protocol = req.socket.encrypted ? 'https' : 'http'
        let expectedOrigin = allowedOrigin
        if (expectedOrigin === undefined) {
          // Only the actual socket address is authoritative. Host/Origin cannot
          // select an alias. Separate hosts/proxies must supply allowedOrigin.
          const localAddress = req.socket.localAddress?.replace(/^::ffff:/, '')
          if (!localAddress) throw new StoreError('origin-not-approved', 403)
          const socketHost = localAddress.includes(':') ? `[${localAddress}]` : localAddress
          expectedOrigin = new URL(`${protocol}://${socketHost}:${req.socket.localPort}`).origin
          let authority
          try { authority = new URL(`${protocol}://${req.headers.host}`) } catch { throw new StoreError('origin-not-approved', 403) }
          if (!req.headers.host || authority.username || authority.password || authority.pathname !== '/' || authority.search || authority.hash || authority.origin !== expectedOrigin) throw new StoreError('origin-not-approved', 403)
        }
        if (origin !== undefined && origin !== expectedOrigin) throw new StoreError('origin-not-approved', 403)
        if (origin !== undefined) {
          res.setHeader('Access-Control-Allow-Origin', expectedOrigin)
          res.setHeader('Vary', 'Origin')
        }
        if (req.method === 'OPTIONS') {
          res.setHeader('Access-Control-Allow-Methods', 'POST')
          res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Native-Retention')
          send(204, undefined)
          return true
        }
        if (req.method !== 'POST') { res.setHeader('Allow', 'POST, OPTIONS'); throw new StoreError('method-not-allowed', 405) }
        if (req.headers['content-type'] !== 'application/octet-stream' || (req.headers['content-encoding'] !== undefined && req.headers['content-encoding'] !== 'identity')) throw new StoreError('binary-body-required', 415)
        const retention = req.headers['x-native-retention'] ?? 'transient'
        checkRetention(retention)
        const length = req.headers['content-length']
        let expectedLength
        if (length !== undefined) {
          if (typeof length !== 'string' || !/^(0|[1-9][0-9]*)$/.test(length)) throw new StoreError('invalid-content-length')
          expectedLength = Number(length)
          if (!Number.isSafeInteger(expectedLength) || expectedLength > maxObjectBytes) throw new StoreError('object-too-large', 413)
        }
        // Keep the socket alive on early oversize rejection so the caller gets
        // the HTTP error; the catch drains the remaining request without buffering.
        const result = await run(() => ingest(req.iterator({ destroyOnReturn: false }), { retention, expectedSHA: sha, expectedLength }))
        send(201, result)
      } catch (error) {
        // Finish consuming the framed request before completing its response.
        // This keeps an early boundary rejection from racing body delivery and
        // reuse of the same HTTP connection. Discard chunks without retaining.
        if (!req.readableEnded && !req.destroyed) {
          await new Promise(resolve => {
            function done() {
              req.off('end', done)
              req.off('close', done)
              req.off('error', done)
              resolve()
            }
            req.once('end', done)
            req.once('close', done)
            req.once('error', done)
            req.resume()
          })
        }
        send(error instanceof StoreError ? error.status : (req.aborted ? 400 : 500), { error: error instanceof StoreError ? error.code : (req.aborted ? 'body-truncated' : 'byte-store-error') })
      }
      return true
    },
  }
  return store
}
