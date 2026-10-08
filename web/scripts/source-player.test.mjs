import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { hasIdrAccessUnit } from './native-access-index.mjs'

// Native event/state decision controls only; actual original-byte proof is separate.
const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)), configFile: false, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, ws: false, watch: null }, appType: 'custom' })
after(() => server.close())
const { buildOriginalPresentationSamples, createSourceVideoPlayer, validateSourceAccessIndex, selectSourceExposure, browserSeekSeconds } = await server.ssrLoadModule('/src/source-player.ts')
const id = '6dW6VYXp9HM'
const metadata = () => ({ schemaVersion: 1, kind: 'original-h264-idr-access-index', source: { videoId: id, sha256: '5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52', bytes: 100 }, timeBase: [1, 30000], pts: [0, 1001, 2002, 3003], idrPts: [0] })

test('original presented-frame aliases retain author time only with identical source/pose/view policy', () => {
  const row = { timeSeconds: 48.298249999999996, decodedTimeSeconds: 48.256541666666664, shotId: 'operating', classification: 'machine',
    sourceImage: { frameIndex: 1157, sourceSha256: metadata().source.sha256, width: 1920, height: 1080, pixelFormat: 'gray8', sha256Gray8: 'a'.repeat(64) },
    views: [{ id: 'main', rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', camera: { position: [1, 2, 3] }, input: { crankTurns: 1 }, sourceAssembly: { mode: 'operating' } }] }
  assert.equal(buildOriginalPresentationSamples([row]).get(1157), row.timeSeconds)
  const alias = { ...structuredClone(row), timeSeconds: row.decodedTimeSeconds }
  assert.equal(buildOriginalPresentationSamples([row, alias]).get(1157), alias.timeSeconds)
  const bgrAlias = { ...structuredClone(alias), sourceImage: { frameIndex: 1157, sourceSha256: row.sourceImage.sourceSha256, width: 1920, height: 1080, pixelFormat: 'bgr8', sha256Bgr8: 'c'.repeat(64) } }
  assert.equal(buildOriginalPresentationSamples([row, bgrAlias]).get(1157), bgrAlias.timeSeconds, 'different original pixel representations of the same physical frame do not change its pose')
  for (const change of [
    frame => { frame.views[0].camera.position[0]++ },
    frame => { frame.views[0].input.crankTurns++ },
    frame => { frame.views[0].sourceAssembly = { mode: 'removed', removedParts: ['arm'] } },
    frame => { frame.views[0].rectSourcePixels[0]++ },
    frame => { frame.views[0].sourceVisibility = { status: 'qualified-unreadable' } },
    frame => { frame.sourceImage.sha256Gray8 = 'b'.repeat(64) },
    frame => { frame.decodedTimeSeconds += 1 },
  ]) { const contradictory = structuredClone(alias); change(contradictory); assert.throws(() => buildOriginalPresentationSamples([row, contradictory]), /contradictory authored pose/) }
})

function fixture(t) {
  class NativeVideo extends EventTarget {
    constructor() { super(); Object.assign(this, { style: {}, duration: 1, paused: true, ended: false, seeking: false, readyState: 4, HAVE_FUTURE_DATA: 3, volume: 1, muted: false, error: null, time: 0, seekRequests: [], callbacks: new Map(), serial: 0 }) }
    setAttribute() {}
    removeAttribute() {}
    load() {}
    remove() {}
    get currentSrc() { return this.src }
    get currentTime() { return this.time }
    set currentTime(value) {
      this.seekRequests.push(value); this.time = Math.trunc(value * 1e6) / 1e6; this.seeking = true
      queueMicrotask(() => { this.dispatchEvent(new Event('seeking')); this.seeking = false; this.dispatchEvent(new Event('seeked')) })
    }
    play() { this.paused = false; this.dispatchEvent(new Event('playing')); return Promise.resolve() }
    pause() { if (!this.paused) { this.paused = true; this.dispatchEvent(new Event('pause')) } }
    requestVideoFrameCallback(fn) { const key = ++this.serial; this.callbacks.set(key, fn); return key }
    cancelVideoFrameCallback(key) { this.callbacks.delete(key) }
    frame(pts) {
      this.time = pts / 30000
      const callbacks = [...this.callbacks.values()]; this.callbacks.clear()
      for (const fn of callbacks) fn(performance.now(), { mediaTime: Math.round(this.time * 1e6) / 1e6, presentedFrames: ++this.serial, presentationTime: performance.now() })
    }
  }
  const media = new NativeVideo(), timers = new Map(), states = []
  let nextTimer = 0
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(metadata())))
  const previousWindow = globalThis.window, previousDocument = globalThis.document
  globalThis.window = { setTimeout: fn => { timers.set(++nextTimer, fn); return nextTimer }, clearTimeout: key => timers.delete(key) }
  globalThis.document = { createElement: () => media }
  t.after(() => { globalThis.window = previousWindow; globalThis.document = previousDocument })
  const container = { replaceChildren: () => queueMicrotask(() => media.dispatchEvent(new Event('loadedmetadata'))) }
  return { media, timers, states, create: () => createSourceVideoPlayer(container, id, state => states.push(state)) }
}

test('source identity and monotonic rational presentation metadata fail closed', () => {
  assert.equal(validateSourceAccessIndex(metadata(), id).source.videoId, id)
  for (const mutate of [m => { m.source.sha256 = 'a'.repeat(64) }, m => { m.pts[1] = 0 }, m => { m.idrPts = [1001] }, m => { m.timeBase[1] = 0 }, m => { m.idrPts = [0, 2] }]) {
    const index = metadata(); mutate(index)
    assert.throws(() => validateSourceAccessIndex(index, id), /unsupported|bound/)
  }
})

test('browser microseconds ceil without replacing the original PTS authority', () => {
  const index = { ...metadata(), pts: [0, 5100095, 5101096], idrPts: [0] }
  assert.equal(browserSeekSeconds(index, 5100095), 170.003167)
  assert.equal(selectSourceExposure(index, 170.00316666666666).pts, 5100095)
  assert.equal(selectSourceExposure(index, 170.003167).frameIndex, 1)
  assert.equal(index.pts[1], 5100095)
})

test('compressed NAL5, not recovery/sync marking, defines verified IDR access', () => {
  const packet = type => Buffer.from([0, 0, 0, 2, type, 0])
  assert.equal(hasIdrAccessUnit(packet(0x65), 4), true)
  assert.equal(hasIdrAccessUnit(Buffer.concat([packet(0x06), packet(0x41)]), 4), false)
  assert.throws(() => hasIdrAccessUnit(Buffer.from([0, 0, 0, 4, 0x65]), 4), /Invalid/)
  assert.throws(() => hasIdrAccessUnit(packet(0x05), 4), /header/)
  assert.throws(() => hasIdrAccessUnit(Buffer.concat([packet(0x65), packet(0x41)]), 4), /mixed/)
})

test('native seek selects only the preceding IDR and finishes only on actual target presentation', async t => {
  const f = fixture(t), player = await f.create()
  const pending = player.seek(2002 / 30000, 'reference-review')
  await Promise.resolve()
  assert.equal(player.getState(), 'playing')
  assert.equal(player.getSeekState(), 'preroll')
  assert.deepEqual(f.media.seekRequests, [0])
  f.media.frame(0); f.media.frame(1001)
  assert.equal(player.getPresentation(), null)
  f.media.frame(2002)
  const actual = await pending
  assert.equal(actual.frameIndex, 2)
  assert.equal(actual.pts, 2002)
  assert.equal(actual.mediaTime, 0.066733)
  assert.equal(player.getState(), 'paused')
  assert.equal(player.getSeekState(), 'idle')
  assert.deepEqual(f.media.seekRequests, [0])
  player.destroy()
})

test('paused Restore identity follows real ordinary presentation and refuses cancelled/old-owner callbacks', async t => {
  const f = fixture(t), player = await f.create()
  player.play()
  f.media.frame(1001)
  player.pause()
  assert.equal(player.getPresentation().frameIndex, 1)
  player.play()
  assert.equal(player.getPresentation().frameIndex, 1, 'the same real displayed frame remains owned until a new presentation, not a guessed clock frame')
  player.pause()
  const oldFrame = [...f.media.callbacks.values()][0]
  const pending = player.seek(2002 / 30000)
  const rejection = assert.rejects(pending)
  await Promise.resolve()
  player.pause()
  await rejection
  oldFrame(performance.now(), { mediaTime: 2002 / 30000, presentedFrames: 999 })
  assert.equal(player.getPresentation(), null)
  player.play()
  f.media.frame(3003)
  player.pause()
  assert.equal(player.getPresentation().frameIndex, 3)
  f.media.src = '/another-original.mp4'
  assert.equal(player.getPresentation(), null)
  player.destroy()
})

test('a genuinely stationary owned paused exposure is a no-op, never a guessed clock or post-play receipt', async t => {
  const f = fixture(t), player = await f.create()
  f.media.frame(0)
  const actual = player.getPresentation()
  assert.equal(await player.seek(0), actual)
  assert.deepEqual(f.media.seekRequests, [])
  assert.equal(f.media.paused, true)
  player.play(); player.pause()
  const pending = player.seek(0)
  await Promise.resolve()
  assert.equal(player.getPresentation(), null)
  assert.equal(player.getSeekState(), 'awaiting-presentation')
  assert.deepEqual(f.media.seekRequests, [0])
  f.media.frame(0)
  assert.ok((await pending).presentedFrames > actual.presentedFrames)
  player.destroy()
})

test('a new seek cannot accept an older compositor count or pre-transaction target presentation', async t => {
  const f = fixture(t), player = await f.create()
  player.play(); f.media.frame(0); player.pause()
  const previous = player.getPresentation(), pending = player.seek(0)
  await Promise.resolve()
  const deliver = metadata => { const callbacks = [...f.media.callbacks.values()]; f.media.callbacks.clear(); for (const callback of callbacks) callback(performance.now(), metadata) }
  deliver({ mediaTime: 0, presentedFrames: previous.presentedFrames, presentationTime: performance.now() })
  assert.equal(player.getSeekState(), 'awaiting-presentation')
  deliver({ mediaTime: 0, presentedFrames: previous.presentedFrames + 1, presentationTime: previous.presentationTime })
  assert.equal(player.getSeekState(), 'awaiting-presentation')
  f.media.frame(0)
  const actual = await pending
  assert.ok(actual.presentedFrames > previous.presentedFrames)
  assert.ok(actual.presentationTime > previous.presentationTime)
  player.destroy()
})

test('native mute owns the genuine mute property independently of zero volume', async t => {
  const f = fixture(t), player = await f.create()
  player.setVolume(0)
  assert.equal(player.getAudio().state, 'muted')
  assert.equal(player.getMuted(), false)
  player.setMuted(true)
  assert.equal(f.media.muted, true)
  player.setMuted(false); player.setVolume(100)
  assert.equal(player.getAudio().state, 'audible')
  assert.equal(f.media.volume, 1)
  player.destroy()
})

test('a target that is itself an IDR still requires its actual presentation, not only seeked/currentTime', async t => {
  const f = fixture(t), player = await f.create(), pending = player.seek(0)
  await Promise.resolve()
  assert.equal(player.getPresentation(), null)
  assert.equal(player.getSeekState(), 'awaiting-presentation')
  assert.equal(f.media.paused, true, 'already-IDR target must not be advanced by unnecessary playback')
  f.media.frame(0)
  const receipt = await pending
  assert.equal(receipt.frameIndex, 0)
  assert.equal(player.getPresentation().pts, 0)
  assert.deepEqual(f.media.seekRequests, [0])
  player.destroy()
})

for (const failure of ['skipped', 'timeout', 'error', 'pause', 'destroy', 'superseded']) test(`native ${failure} refuses without retry or target clock assignment`, async t => {
  const f = fixture(t), player = await f.create(), pending = player.seek(2002 / 30000)
  const rejection = assert.rejects(pending)
  await Promise.resolve()
  if (failure === 'skipped') f.media.frame(3003)
  else if (failure === 'timeout') [...f.timers.values()][0]()
  else if (failure === 'error') { f.media.error = { message: 'actual native failure' }; f.media.dispatchEvent(new Event('error')) }
  else if (failure === 'pause') player.pause()
  else if (failure === 'destroy') player.destroy()
  else { f.media.currentTime = 0.01; await Promise.resolve() }
  await rejection
  assert.equal(player.getPresentation(), null)
  assert.deepEqual(f.media.seekRequests, failure === 'superseded' ? [0, 0.01] : [0])
  if (failure === 'error') assert.equal(player.getState(), 'error')
  player.destroy()
})
