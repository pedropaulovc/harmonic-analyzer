import { createReadStream } from 'node:fs'
import { appendFile, mkdir, readFile, rename, stat, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

const VIDEO_IDS: Record<string, true | undefined> = { '8KmVDxkia_w': true, '6dW6VYXp9HM': true }
const MAX_BODY = 64 * 1024
const setupFields: Record<string, true | undefined> = {
  counterHeightM: true, meanLineAngleRad: true, platenOffsetM: true, wireFixtureOffsetM: true,
  coneSwingRad: true, pinionCamRad: true, heldChannelTurns: true, driveCrankOffsetTurns: true,
}
type RecordValue = Record<string, unknown>
interface Manual { cameraKeys: RecordValue[]; segments: RecordValue[]; crank: RecordValue[] }
class BadRequest extends Error {}
function object(value: unknown): RecordValue {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new BadRequest('Expected an object')
  return value as RecordValue
}
function fields(value: RecordValue, allowed: readonly string[]): void {
  if (Object.keys(value).some(key => !allowed.includes(key))) throw new BadRequest('Unknown field')
}
function finite(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) }
function time(value: unknown): void { if (!finite(value) || value < 0) throw new BadRequest('Time must be finite and nonnegative') }
function identifier(value: unknown): void {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(value)) throw new BadRequest('Invalid identifier')
}
function vector(value: unknown, length: number): value is number[] { return Array.isArray(value) && value.length === length && value.every(finite) }
function validateSave(value: unknown): RecordValue {
  const request = object(value)
  fields(request, ['videoId', 'cameraKey', 'segment', 'crank'])
  if (typeof request.videoId !== 'string' || !Object.hasOwn(VIDEO_IDS, request.videoId)) throw new BadRequest('Unsupported videoId')
  if (request.cameraKey === undefined && request.segment === undefined && request.crank === undefined) throw new BadRequest('No save action')
  if (request.cameraKey !== undefined) {
    const key = object(request.cameraKey)
    fields(key, ['shotId', 'viewId', 't', 'camera'])
    identifier(key.shotId); identifier(key.viewId); time(key.t)
    const camera = object(key.camera)
    fields(camera, ['positionMetres', 'quaternion', 'verticalFovDegrees', 'principalPointViewportPixels'])
    if (!vector(camera.positionMetres, 3) || !vector(camera.quaternion, 4)
      || Math.abs(Math.hypot(...camera.quaternion) - 1) > 0.01
      || !finite(camera.verticalFovDegrees) || camera.verticalFovDegrees <= 0 || camera.verticalFovDegrees >= 180
      || (camera.principalPointViewportPixels !== undefined && !vector(camera.principalPointViewportPixels, 2))) throw new BadRequest('Invalid camera')
  }
  if (request.segment !== undefined) {
    const segment = object(request.segment)
    fields(segment, ['id', 'start', 'end', 'init'])
    identifier(segment.id); time(segment.start); time(segment.end)
    if ((segment.end as number) <= (segment.start as number)) throw new BadRequest('Segment end must follow start')
    const init = object(segment.init)
    fields(init, ['amplitudes', 'phases', 'gearing', 'magnification', 'setup'])
    for (const key of ['amplitudes', 'phases']) if (init[key] !== undefined && !vector(init[key], 20)) throw new BadRequest(`${key} must contain twenty finite numbers`)
    if (Array.isArray(init.amplitudes) && init.amplitudes.some((value: number) => Math.abs(value) > 1)) throw new BadRequest('Amplitudes must be in [-1, 1]')
    if (init.gearing !== undefined && !['small-large', 'medium-medium', 'large-small'].includes(String(init.gearing))) throw new BadRequest('Invalid gearing')
    if (init.magnification !== undefined && (!finite(init.magnification) || init.magnification <= 0)) throw new BadRequest('Invalid magnification')
    if (init.setup !== undefined) {
      const setup = object(init.setup)
      for (const [key, setting] of Object.entries(setup)) {
        if (!Object.hasOwn(setupFields, key) || !(finite(setting) || (key === 'counterHeightM' && setting === null))) throw new BadRequest('Invalid setup field')
      }
    }
  }
  if (request.crank !== undefined) {
    const crank = object(request.crank)
    fields(crank, ['t', 'turns']); time(crank.t)
    if (!finite(crank.turns)) throw new BadRequest('Invalid crank turns')
  }
  return request
}
function json(response: ServerResponse, status: number, value: unknown, head = false): void {
  const body = JSON.stringify(value)
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(body), 'Cache-Control': 'no-store' })
  response.end(head ? undefined : body)
}
async function body(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of request) {
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
    size += bytes.length
    if (size > MAX_BODY) throw new BadRequest('Request exceeds 64 KiB')
    chunks.push(bytes)
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown } catch { throw new BadRequest('Invalid JSON') }
}
async function manual(path: string): Promise<Manual> {
  try {
    const value = object(JSON.parse(await readFile(path, 'utf8')) as unknown)
    if (!Array.isArray(value.cameraKeys) || !Array.isArray(value.segments) || !Array.isArray(value.crank)) throw new Error('Invalid persisted manual data')
    return value as unknown as Manual
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return { cameraKeys: [], segments: [], crank: [] }
    throw error
  }
}
function replace(entries: RecordValue[], value: RecordValue, keys: string[]): void {
  const index = entries.findIndex(entry => keys.every(key => entry[key] === value[key]))
  if (index < 0) entries.push(value)
  else entries[index] = value
}

/** Private originals and manual editing are deliberately available only on the dev server. */
export function syncDevMiddleware(): Plugin {
  let queue: Promise<void> = Promise.resolve()
  return {
    name: 'harmonic-sync-private-dev',
    apply: 'serve',
    configureServer(server) {
      const manualPath = (id: string) => join(server.config.root, 'sync', 'videos', id, 'manual.json')
      const dataRoot = resolve(process.env.HARMONIC_SYNC_DATA ?? join(homedir(), 'data', 'harmonic-analyzer-sync'))
      server.middlewares.use((request, response, next) => {
        const pathname = (request.url ?? '').split('?')[0] ?? ''
        if (!pathname.startsWith('/__sync/')) { next(); return }
        void (async () => {
          const origin = request.headers.origin
          if ((origin && new URL(origin).host !== request.headers.host) || request.headers['sec-fetch-site'] === 'cross-site') throw new BadRequest('Same-origin requests only')
          if (pathname === '/__sync/save') {
            if (request.method !== 'POST') { json(response, 405, { error: 'POST required' }); return }
            if (!/^application\/json(?:\s*;|$)/i.test(request.headers['content-type'] ?? '')) throw new BadRequest('application/json required')
            const declaredLength = request.headers['content-length']
            if (declaredLength && (!/^\d+$/.test(declaredLength) || Number(declaredLength) > MAX_BODY)) throw new BadRequest('Request exceeds 64 KiB')
            const started = performance.now()
            const save = validateSave(await body(request))
            const id = save.videoId as string
            const task = queue.then(async () => {
              const path = manualPath(id)
              const existing = await manual(path)
              if (save.cameraKey !== undefined) replace(existing.cameraKeys, object(save.cameraKey), ['shotId', 'viewId', 't'])
              if (save.segment !== undefined) replace(existing.segments, object(save.segment), ['id'])
              if (save.crank !== undefined) replace(existing.crank, object(save.crank), ['t'])
              await mkdir(dirname(path), { recursive: true })
              const temporary = `${path}.${process.pid}.tmp`
              await writeFile(temporary, `${JSON.stringify(existing, null, 2)}\n`)
              await rename(temporary, path)
              const event = { at: new Date().toISOString(), action: 'manual-save', elapsedMs: performance.now() - started, ...save }
              const logPath = save.cameraKey !== undefined
                ? join(dataRoot, id, object(save.cameraKey).shotId as string, 'manual-saves.jsonl')
                : join(dataRoot, id, 'manual-saves.jsonl')
              await mkdir(dirname(logPath), { recursive: true })
              await appendFile(logPath, `${JSON.stringify(event)}\n`)
              process.stderr.write(`[harmonic-sync] ${JSON.stringify(event)}\n`)
            })
            queue = task.catch(() => {})
            await task
            json(response, 200, { ok: true }); return
          }
          const match = /^\/__sync\/(video|manual)\/([A-Za-z0-9_-]+)(\.mp4)?$/.exec(pathname)
          if (!match || !match[2] || !Object.hasOwn(VIDEO_IDS, match[2]) || (match[1] === 'video') !== (match[3] === '.mp4')) { json(response, 404, { error: 'Unknown sync resource' }); return }
          if (request.method !== 'GET' && request.method !== 'HEAD') { json(response, 405, { error: 'GET or HEAD required' }); return }
          const head = request.method === 'HEAD'
          if (match[1] === 'manual') {
            await queue
            json(response, 200, await manual(manualPath(match[2])), head); return
          }
          const path = join(homedir(), 'data', 'harmonic-analyzer-videos', `${match[2]}.mp4`)
          const info = await stat(path)
          if (!info.isFile()) { json(response, 404, { error: 'Video not found' }, head); return }
          let start = 0
          let end = info.size - 1
          const range = request.headers.range
          if (range !== undefined) {
            const parsed = /^bytes=(\d*)-(\d*)$/.exec(range)
            const left = parsed?.[1] ?? ''
            const right = parsed?.[2] ?? ''
            if (!parsed || (!left && !right) || (left !== '' && !Number.isSafeInteger(Number(left))) || (right !== '' && !Number.isSafeInteger(Number(right)))) {
              response.writeHead(416, { 'Content-Range': `bytes */${info.size}`, 'Content-Length': 0 }); response.end(); return
            }
            if (left) { start = Number(left); end = right ? Math.min(Number(right), end) : end }
            else { start = Math.max(0, info.size - Number(right)) }
            if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end || start >= info.size || (!left && Number(right) === 0)) {
              response.writeHead(416, { 'Content-Range': `bytes */${info.size}`, 'Content-Length': 0 }); response.end(); return
            }
          }
          response.writeHead(range ? 206 : 200, {
            'Content-Type': 'video/mp4', 'Accept-Ranges': 'bytes', 'Content-Length': Math.max(0, end - start + 1),
            ...(range ? { 'Content-Range': `bytes ${start}-${end}/${info.size}` } : {}),
          })
          if (head || info.size === 0) { response.end(); return }
          const stream = createReadStream(path, { start, end })
          response.on('close', () => stream.destroy())
          stream.on('error', error => response.destroy(error))
          stream.pipe(response)
        })().catch((error: unknown) => {
          if (response.headersSent) { response.destroy(); return }
          const missing = (error as NodeJS.ErrnoException).code === 'ENOENT'
          const invalid = error instanceof BadRequest || error instanceof TypeError
          if (!missing && !invalid) process.stderr.write(`[harmonic-sync] ${String(error)}\n`)
          json(response, missing ? 404 : invalid ? 400 : 500, { error: missing ? 'File not found' : invalid ? (error as Error).message : 'Sync persistence failed' }, request.method === 'HEAD')
        })
      })
    },
  }
}
