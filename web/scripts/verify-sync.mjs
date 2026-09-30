#!/usr/bin/env node
import { mkdir, writeFile, stat } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { VIDEO_IDS, MODEL_SHA256, MODEL_COMMIT, PIXEL_LIMIT, CLOCK_LIMIT, loadReferences, frameViews, sourceNeedsMachine, requiredRuns, frameIndexAt, errorStats, jsonDigest } from './verify-reference.mjs'
import { distManifest, serveDist } from './verify-server.mjs'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
/** Independent DOM-letterbox cross-check of GPU marker canvas vs source coordinates, in CSS px. */
const VIEWPORT_MAPPING_LIMIT_PX = 0.75
/** Media identity only (rejects ads/wrong content); not a fidelity threshold. */
const NATIVE_DURATION_TOLERANCE_SECONDS = 1
/** A paused HTMLMediaElement may not advance more than this. */
const PAUSED_DRIFT_SECONDS = 0.1
/** Bounded wait for the official player's own seek/decode after reviewReferenceFrame resolves. */
const NATIVE_SEEK_TIMEOUT_MS = 15_000
const NATIVE_SEEK_POLL_MS = 50
/** Frame-identity window: a requested source time must be the nearest native exposure (half a frame). */
const seekToleranceSeconds = record => 0.5 / record.native.fps
/** Held poses are exact copies of an earlier required frame's observed camera. */
const CAMERA_TOLERANCE = 1e-7
/** No-machine samples must leave exploratory geometry/camera untouched. */
const UNCHANGED_TOLERANCE = 1e-9
/** Clock proof needs >=1 s of draws inside a required run with a CLOCK_LIMIT guard band at each end. */
const MIN_CLOCK_RUN_SECONDS = 1 + 2 * CLOCK_LIMIT + 0.5
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const delay = ms => new Promise(done => setTimeout(done, ms))
const finite = value => typeof value === 'number' && Number.isFinite(value)
const vec2 = value => Array.isArray(value) && value.length === 2 && value.every(finite)
function requireCondition(condition, message) { if (!condition) throw new Error(message) }
function fail(report, code, detail, extra = {}) { report.failures.push({ code, detail, ...extra }) }
function nearlyEqual(a, b, tolerance) {
  if (finite(a) && finite(b)) return Math.abs(a - b) <= tolerance
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((value, index) => nearlyEqual(value, b[index], tolerance))
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    const keys = Object.keys(a)
    return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) && nearlyEqual(a[key], b[key], tolerance))
  }
  return a === b
}
const sameCamera = (a, b) => !!a && !!b && nearlyEqual(a.positionMetres, b.positionMetres, CAMERA_TOLERANCE) && nearlyEqual(a.quaternion, b.quaternion, CAMERA_TOLERANCE) && nearlyEqual(a.verticalFovDegrees, b.verticalFovDegrees, CAMERA_TOLERANCE)

async function apiSnapshot(page) { return page.evaluate(() => window.harmonicAnalyzer.snapshot()) }
async function waitState(page, state, timeout = 20_000) {
  await page.waitForFunction(expected => window.harmonicAnalyzer?.snapshot().playerState === expected, state, { timeout })
}
function checkSnapshot(snapshot, id) {
  requireCondition(snapshot.videoId === id && snapshot.playerVideoId === id, `Actual YouTube/player route identity mismatch: ${snapshot.videoId}/${snapshot.playerVideoId}/${id}`)
  requireCondition(snapshot.modelState === 'ready' && Array.isArray(snapshot.missingBindings) && !snapshot.missingBindings.length, `Authentic articulated model is not ready or has missing bindings: ${JSON.stringify(snapshot.missingBindings)}`)
  const provenance = snapshot.modelProvenance
  requireCondition(provenance?.identity === 'matched' && provenance.observedSha256 === MODEL_SHA256 && provenance.expectedSha256 === MODEL_SHA256 && provenance.sourceCommit === MODEL_COMMIT, 'Rendered model bytes/source revision do not match the released CAD export')
  const physics = snapshot.physics
  requireCondition(Array.isArray(physics?.springForcesN) && physics.springForcesN.length === 20 && physics.springForcesN.every(value => finite(value) && value >= 0), 'All twenty actual spring forces must be available')
  requireCondition(Array.isArray(physics?.springLengthsM) && physics.springLengthsM.length === 20 && physics.springLengthsM.every(value => finite(value) && value > 0), 'All twenty actual spring lengths must be available')
  requireCondition(['equilibriumResidualNm', 'platenTravelM', 'summingAngleRad'].every(key => finite(physics[key])), 'Physical equilibrium/output data is unavailable')
}

/**
 * Reads the renderer's last ACTUAL GPU marker capture per view (a pure read, not a
 * rerender or CPU projection) plus the real #stage canvas geometry. #stage is
 * itself the canvas element.
 */
function readRenderedState(viewIds) {
  const api = window.harmonicAnalyzer
  if (typeof api?.renderedLandmarks !== 'function') throw new Error('Verification bridge lacks renderedLandmarks(viewId)')
  const copy = value => value == null ? null : Array.from(value)
  const captures = viewIds.map(viewId => {
    const capture = api.renderedLandmarks(viewId)
    return {
      viewId,
      capture: capture ? {
        method: capture.method, timeSeconds: capture.timeSeconds,
        landmarks: Array.isArray(capture.landmarks) ? capture.landmarks.map(item => ({ id: item.id, state: item.state, reason: item.reason ?? null, canvasPixels: copy(item.canvasPixels), sourcePixels: copy(item.sourcePixels), uncertaintyCanvasPixels: item.uncertaintyCanvasPixels ?? null })) : null,
      } : null,
    }
  })
  const canvas = document.querySelector('#stage')
  return { captures, canvas: { tag: canvas?.tagName ?? null, clientWidth: canvas?.clientWidth ?? 0, clientHeight: canvas?.clientHeight ?? 0, width: canvas?.width ?? 0, height: canvas?.height ?? 0, devicePixelRatio: window.devicePixelRatio } }
}

/** The real stage canvas must be visible and its backing store sized to its current layout. */
function stageGate(canvas) {
  requireCondition(canvas.tag === 'CANVAS', `#stage is not the rendered canvas element: ${canvas.tag}`)
  requireCondition(canvas.clientWidth > 0 && canvas.clientHeight > 0, 'Actual source-render canvas viewport is hidden/empty')
  requireCondition(Math.abs(canvas.width - canvas.clientWidth * canvas.devicePixelRatio) <= 1 && Math.abs(canvas.height - canvas.clientHeight * canvas.devicePixelRatio) <= 1, `Stale WebGL backing store ${canvas.width}×${canvas.height} for layout ${canvas.clientWidth}×${canvas.clientHeight}@${canvas.devicePixelRatio}`)
  const width = Math.min(canvas.clientWidth, canvas.clientHeight * 1920 / 1080), height = width * 1080 / 1920
  return { x: (canvas.clientWidth - width) / 2, y: (canvas.clientHeight - height) / 2, width, height }
}

async function nativeFrame(page, id) {
  const iframe = page.locator('#video-player iframe')
  requireCondition(await iframe.count() === 1, 'Exactly one visible native YouTube iframe is required')
  const src = await iframe.getAttribute('src')
  const url = new URL(src)
  requireCondition(/(^|\.)youtube(?:-nocookie)?\.com$/.test(url.hostname) && url.pathname === `/embed/${id}`, `Wrong/non-native YouTube embed: ${src}`)
  requireCondition(url.searchParams.get('controls') !== '0' && url.searchParams.get('mute') !== '1', 'Native controls/audio may not be disabled')
  const handle = await iframe.elementHandle(), frame = await handle.contentFrame()
  requireCondition(frame, 'Native YouTube frame did not load')
  return { iframe, handle, frame, src }
}

/** Reads YouTube's own main HTMLMediaElement inside the official iframe, never an app alias. */
async function nativeMedia(frame) {
  return frame.evaluate(() => {
    const player = document.querySelector('#movie_player')
    const video = player?.querySelector('video.html5-main-video') ?? null
    const control = document.querySelector('.ytp-play-button')
    const controls = document.querySelector('.ytp-chrome-bottom')
    const buttonRect = control?.getBoundingClientRect(), rect = controls?.getBoundingClientRect()
    return {
      mediaPresent: !!video, paused: video?.paused, seeking: video?.seeking, ended: video?.ended, muted: video?.muted, volume: video?.volume,
      mediaTime: video?.currentTime, duration: video?.duration, readyState: video?.readyState ?? 0, videoWidth: video?.videoWidth ?? 0, videoHeight: video?.videoHeight ?? 0,
      adShowing: !!player?.classList.contains('ad-showing'),
      controls: !!controls && !!control, controlsHeight: rect?.height ?? 0, playButtonWidth: buttonRect?.width ?? 0, playButtonHeight: buttonRect?.height ?? 0,
      error: document.querySelector('.ytp-error-content-wrap, .ytp-error')?.textContent?.trim() ?? '',
    }
  })
}

/** Proves the official player holds a decoded frame of this actual source, not an ad or placeholder. */
function requireNativeContent(actual, record, label) {
  requireCondition(actual.mediaPresent, `${label}: no actual YouTube main HTMLMediaElement`)
  requireCondition(!actual.error, `${label}: native YouTube error: ${actual.error}`)
  requireCondition(!actual.adShowing, `${label}: YouTube is showing an ad, not the source content`)
  requireCondition(actual.readyState >= 2 && actual.videoWidth > 0 && actual.videoHeight > 0, `${label}: native media has no decoded current frame (${JSON.stringify(actual)})`)
  requireCondition(finite(actual.duration) && Math.abs(actual.duration - record.native.durationSeconds) <= NATIVE_DURATION_TOLERANCE_SECONDS, `${label}: native media duration ${actual.duration}s is not the ${record.native.durationSeconds}s source`)
  requireCondition(finite(actual.mediaTime), `${label}: native media clock is not finite`)
}

async function pauseActual(page, embed) {
  const current = await apiSnapshot(page)
  if (current.playerState === 'playing' || current.playerState === 'buffering') await page.locator('#pause-video').click()
  await waitState(page, 'paused')
  const before = await nativeMedia(embed.frame)
  await delay(500)
  const after = await nativeMedia(embed.frame)
  requireCondition(before.paused === true && after.paused === true && finite(before.mediaTime) && finite(after.mediaTime) && Math.abs(after.mediaTime - before.mediaTime) <= PAUSED_DRIFT_SECONDS, 'Actual native HTMLMediaElement continues while paused')
}

/** Manual controls main.ts updateControlState enables only in ready exploration. */
async function explorationControls(page) {
  return page.evaluate(() => Object.fromEntries(['#drive-controls', '#channel-fieldset', '#fit-view'].map(selector => [selector, document.querySelector(selector)?.disabled === false])))
}

async function endReview(page) {
  await page.evaluate(async () => {
    const api = window.harmonicAnalyzer
    if (typeof api?.endReferenceReview !== 'function') throw new Error('Verification bridge lacks endReferenceReview()')
    await api.endReferenceReview()
  })
  const after = await apiSnapshot(page), controls = await explorationControls(page)
  requireCondition(after.mode === 'exploring' && after.playerState === 'paused', `endReferenceReview did not restore paused exploration: ${after.mode}/${after.playerState}`)
  requireCondition(Object.values(controls).every(Boolean), `endReferenceReview did not re-enable manual exploration controls: ${JSON.stringify(controls)}`)
  return after
}

/** Leaves reference review with paused exploration and usable controls, whatever state a failed review left. */
async function restoreExploration(page, embed) {
  const current = await apiSnapshot(page), controls = await explorationControls(page)
  if (current.mode === 'exploring' && current.playerState === 'paused' && Object.values(controls).every(Boolean)) return current
  if (current.playerState !== 'paused') await pauseActual(page, embed)
  return endReview(page)
}

const SEEK_OBSERVER_KEY = '__harmonicAnalyzerVerifySeekObserver'

/**
 * Registers listeners on YouTube's own main HTMLMediaElement BEFORE the bridge
 * commands a seek, so every seeking/seeked event the command causes is observed
 * and ordered after the recorded pre-command state.
 */
async function armSeekObserver(frame) {
  return frame.evaluate(key => {
    window[key]?.detach()
    const video = document.querySelector('#movie_player video.html5-main-video')
    if (!video) throw new Error('No actual YouTube main HTMLMediaElement to observe')
    const events = []
    const types = ['seeking', 'seeked', 'error', 'emptied', 'abort']
    const record = event => events.push({ type: event.type, mediaTime: video.currentTime, paused: video.paused, seeking: video.seeking, readyState: video.readyState })
    for (const type of types) video.addEventListener(type, record)
    const pre = { mediaTime: video.currentTime, paused: video.paused, seeking: video.seeking, ended: video.ended, readyState: video.readyState }
    const observer = {
      video, events, pre,
      detach() {
        for (const type of types) video.removeEventListener(type, record)
        if (window[key] === observer) delete window[key]
      },
    }
    window[key] = observer
    return pre
  }, SEEK_OBSERVER_KEY)
}

async function readSeekObserver(frame) {
  return frame.evaluate(key => {
    const observer = window[key]
    if (!observer) return null
    const video = observer.video
    return {
      sameElement: video === document.querySelector('#movie_player video.html5-main-video') && video.isConnected,
      pre: observer.pre, events: observer.events.slice(),
      now: { mediaTime: video.currentTime, paused: video.paused, seeking: video.seeking, ended: video.ended, readyState: video.readyState, error: video.error ? (video.error.message || `code ${video.error.code}`) : null },
    }
  }, SEEK_OBSERVER_KEY)
}

async function disarmSeekObserver(frame) {
  await frame.evaluate(key => window[key]?.detach(), SEEK_OBSERVER_KEY).catch(() => {})
}

/**
 * Post-command settlement of the ACTUAL media element: paused, not seeking, a
 * decoded current frame, currentTime on the requested exposure, and either a
 * seeking event raised after the command at the target followed by seeked, or
 * a legitimate no-op where the settled pre-command frame already was the target.
 * A pre-command frame at a different (even adjacent) time can never satisfy this.
 */
function seekSettlement(observed, target, tolerance) {
  if (!observed) return { fatal: 'Seek observer vanished from the official player frame' }
  if (!observed.sameElement) return { fatal: 'YouTube replaced/detached the observed main media element during the seek' }
  if (observed.now.error || observed.events.some(event => event.type === 'error')) return { fatal: `Native media error during seek: ${observed.now.error ?? 'error event'}` }
  const { pre, events, now } = observed
  const onTarget = time => finite(time) && Math.abs(time - target) <= tolerance
  const settled = now.paused === true && !now.seeking && !now.ended && now.readyState >= 2 && onTarget(now.mediaTime)
  let lastSeeking = -1
  events.forEach((event, index) => { if (event.type === 'seeking') lastSeeking = index })
  if (lastSeeking >= 0) {
    const commanded = onTarget(events[lastSeeking].mediaTime) && events.slice(lastSeeking + 1).some(event => event.type === 'seeked')
    return { done: settled && commanded, proof: 'seeking-then-seeked-after-command' }
  }
  const noOp = pre.paused === true && !pre.seeking && !pre.ended && pre.readyState >= 2 && onTarget(pre.mediaTime)
  return { done: settled && noOp, proof: 'same-time-no-op' }
}

async function awaitNativeSeek(embed, target, tolerance) {
  const deadline = Date.now() + NATIVE_SEEK_TIMEOUT_MS
  for (;;) {
    const observed = await readSeekObserver(embed.frame)
    const verdict = seekSettlement(observed, target, tolerance)
    requireCondition(!verdict.fatal, `Official player seek to ${target}s failed: ${verdict.fatal}`)
    if (verdict.done) return { proof: verdict.proof, pre: observed.pre, events: observed.events, settled: observed.now }
    requireCondition(Date.now() < deadline, `Official player did not settle a decoded paused frame at ${target}s (±${tolerance.toFixed(4)}s) within ${NATIVE_SEEK_TIMEOUT_MS}ms after the command: ${JSON.stringify(observed)}`)
    await delay(NATIVE_SEEK_POLL_MS)
  }
}

/**
 * The bridge commands the ACTUAL official YouTube player to seek to t and draws
 * the source sample at t. The YouTube IFrame API cannot acknowledge the decode,
 * so the verifier independently observes the official iframe's HTMLMediaElement
 * (listeners armed before the command) until it settles on t, then reads the
 * last actual GPU capture.
 */
async function reviewAt(page, embed, record, timeSeconds, viewIds) {
  const tolerance = seekToleranceSeconds(record)
  await armSeekObserver(embed.frame)
  let snapshot, seek
  try {
    snapshot = await page.evaluate(async timeSeconds => {
      const api = window.harmonicAnalyzer
      await api.reviewReferenceFrame(timeSeconds)
      return api.snapshot()
    }, timeSeconds)
    seek = await awaitNativeSeek(embed, timeSeconds, tolerance)
  } finally { await disarmSeekObserver(embed.frame) }
  const ids = [...new Set([...viewIds, ...(snapshot.views ?? []).map(view => view.id)])]
  const response = { snapshot, ...await page.evaluate(readRenderedState, ids) }
  const native = await nativeMedia(embed.frame)
  checkSnapshot(response.snapshot, record.id)
  requireNativeContent(native, record, `Reviewed source ${timeSeconds}s`)
  requireCondition(response.snapshot.mode === 'reference-review' && response.snapshot.playerState === 'paused', `Static reference review must hold actual paused playback at ${timeSeconds}s: ${response.snapshot.mode}/${response.snapshot.playerState}`)
  requireCondition(native.paused === true && native.seeking === false && !native.ended, `Official player did not stay settled paused at ${timeSeconds}s: ${JSON.stringify(native)}`)
  requireCondition(Math.abs(native.mediaTime - timeSeconds) <= tolerance, `Official player native media is at ${native.mediaTime}s, not the reviewed source exposure ${timeSeconds}s (±${tolerance}s)`)
  return { ...response, native, seek: { proof: seek.proof, preMediaTime: seek.pre.mediaTime, settledMediaTime: seek.settled.mediaTime, events: seek.events.map(event => event.type) } }
}

/** Validates one view's last actual capture as a fresh GPU draw at the reviewed/played time. */
function freshCapture(entry, timeSeconds, nativeTimes, label) {
  const capture = entry?.capture
  requireCondition(capture?.method === 'gpu-readback' && Array.isArray(capture.landmarks) && finite(capture.timeSeconds), `${label}: no actual GPU-readback capture for view ${entry?.viewId}`)
  if (timeSeconds !== null) requireCondition(Math.abs(capture.timeSeconds - timeSeconds) <= 1e-6, `${label}: stale draw — captured ${capture.timeSeconds}s for ${timeSeconds}s`)
  const skewSeconds = Math.max(...nativeTimes.map(time => Math.abs(capture.timeSeconds - time)))
  requireCondition(skewSeconds <= CLOCK_LIMIT, `${label}: native media ${nativeTimes.join('/')}s vs captured draw ${capture.timeSeconds}s exceeds ${CLOCK_LIMIT}s`)
  return { capture, skewSeconds }
}

function longestRun(record) {
  const runs = requiredRuns(record.data).filter(run => run.endSeconds - run.startSeconds >= MIN_CLOCK_RUN_SECONDS)
  return runs.reduce((best, run) => !best || run.endSeconds - run.startSeconds > best.endSeconds - best.startSeconds ? run : best, null)
}

/** Seek the official player into a required run through reference review, end review, then press Play. */
async function playRequiredRun(page, embed, record, run) {
  await pauseActual(page, embed)
  const firstIndex = frameIndexAt(record.data.frames, run.startSeconds)
  const views = frameViews(record.data.frames[firstIndex]).map(view => view.id)
  const reviewed = await reviewAt(page, embed, record, run.startSeconds, views)
  requireCondition(reviewed.snapshot.referenceState === 'matched', `Required run start ${run.startSeconds}s is not physically matched: ${reviewed.snapshot.referenceState}`)
  await endReview(page)
  await page.locator('#pause-video').click()
  await waitState(page, 'playing')
  await page.waitForFunction(() => window.harmonicAnalyzer.snapshot().mode === 'following-video', undefined, { timeout: 5000 })
}

/**
 * Brackets the app's last actual GPU capture between two reads of YouTube's own
 * HTMLMediaElement. Only samples well inside a required run are clock evidence.
 */
async function clockSample(page, embed, record, run) {
  const before = await nativeMedia(embed.frame)
  const snapshot = await apiSnapshot(page)
  const app = { snapshot, ...await page.evaluate(readRenderedState, (snapshot.views ?? []).map(view => view.id)) }
  const after = await nativeMedia(embed.frame)
  checkSnapshot(app.snapshot, record.id)
  requireNativeContent(before, record, 'Playback'); requireNativeContent(after, record, 'Playback')
  requireCondition(!before.paused && !after.paused && !after.muted && after.volume > 0, `Actual native playback paused/muted: ${JSON.stringify(after)}`)
  requireCondition(app.snapshot.mode === 'following-video' && app.snapshot.playerState === 'playing', `Native playback left following mode: ${app.snapshot.playerState}/${app.snapshot.mode}`)
  const inRun = before.mediaTime - CLOCK_LIMIT >= run.startSeconds && after.mediaTime + CLOCK_LIMIT <= run.endSeconds
  const sample = { nativeBefore: before.mediaTime, nativeAfter: after.mediaTime, inRequiredRun: inRun, referenceState: app.snapshot.referenceState, captureTimeSeconds: null, skewSeconds: null }
  if (!inRun) return sample
  requireCondition(app.snapshot.referenceState === 'matched' && app.snapshot.views?.length > 0, `Required source not matched/drawn during actual playback at native ${before.mediaTime}s: ${app.snapshot.referenceState}`)
  const measured = app.captures.map(entry => freshCapture(entry, null, [before.mediaTime, after.mediaTime], `Playback at native ${before.mediaTime}s`))
  requireCondition(measured.every(item => item.capture.timeSeconds === measured[0].capture.timeSeconds), 'Views of one required-source draw carry different capture times')
  sample.captureTimeSeconds = measured[0].capture.timeSeconds
  sample.skewSeconds = Math.max(...measured.map(item => item.skewSeconds))
  return sample
}

function requireAdvancingDraws(samples, minimumCount, minimumAdvance, label) {
  const inRun = samples.filter(sample => sample.inRequiredRun)
  requireCondition(inRun.length >= minimumCount, `${label}: only ${inRun.length}/${minimumCount} samples measured required-source draws`)
  for (let index = 1; index < inRun.length; index++) requireCondition(inRun[index].captureTimeSeconds >= inRun[index - 1].captureTimeSeconds, `${label}: captured draw time went backwards`)
  requireCondition(inRun.at(-1).captureTimeSeconds - inRun[0].captureTimeSeconds >= minimumAdvance, `${label}: required-source GPU capture time is stale (advanced ${inRun.at(-1).captureTimeSeconds - inRun[0].captureTimeSeconds}s)`)
  requireCondition(inRun.at(-1).nativeAfter - inRun[0].nativeBefore >= minimumAdvance, `${label}: native HTMLMediaElement clock did not advance`)
  return Math.max(...inRun.map(sample => sample.skewSeconds))
}

async function playbackProof(page, record, run, report) {
  const embed = await nativeFrame(page, record.id)
  const before = await apiSnapshot(page)
  if (before.playerState === 'playing') { await page.locator('#pause-video').click(); await waitState(page, 'paused') }
  await page.locator('#follow-video').click()
  // Actual browser clicks on the public control, never evaluate(playVideo) or a fake clock.
  await page.locator('#pause-video').click()
  await waitState(page, 'playing')
  const samples = []
  report.playback = { samples, requiredRun: run, native: null, maxClockSkewSeconds: null, iframeSrc: embed.src, clockEvidence: null, userGesture: '#pause-video click; seeks only through the official player via reviewReferenceFrame' }
  const started = await nativeMedia(embed.frame)
  requireNativeContent(started, record, 'Initial playback')
  if (!run) {
    requireCondition(record.report.machineFrames === 0, `Required source frames exist but no contiguous required run >= ${MIN_CLOCK_RUN_SECONDS}s exists to measure the draw clock`)
    await delay(1250)
    const later = await nativeMedia(embed.frame)
    requireCondition(!later.paused && later.mediaTime - started.mediaTime >= 1, 'Actual native HTMLMediaElement did not advance during user-gesture playback')
    report.playback.clockEvidence = 'No required source frames in this video; no model draw clock is claimed'
  } else {
    await playRequiredRun(page, embed, record, run)
    for (let index = 0; index < 12; index++) {
      await delay(250)
      samples.push(await clockSample(page, embed, record, run))
    }
    report.playback.maxClockSkewSeconds = requireAdvancingDraws(samples, 4, 1, 'Playback')
    report.playback.clockEvidence = 'YouTube iframe HTMLMediaElement.currentTime bracketing renderedLandmarks(viewId).timeSeconds of required-source GPU captures'
  }
  const actual = await nativeMedia(embed.frame), snapshot = await apiSnapshot(page)
  report.playback.native = actual
  requireNativeContent(actual, record, 'Playback')
  requireCondition(!actual.paused && !actual.muted && actual.volume > 0 && actual.controls && actual.controlsHeight > 0 && actual.playButtonWidth > 0, `Actual native media/audio/controls unavailable: ${JSON.stringify(actual)}`)
  requireCondition(snapshot.playerAudio?.state === 'audible' && snapshot.playerAudio.volume > 0, 'YouTube API reports muted/inaudible playback')
  return embed
}

async function compactProof(page, record, embed, run, report, outputDirectory) {
  if (run) await playRequiredRun(page, embed, record, run)
  const initial = await nativeMedia(embed.frame)
  await page.locator('#minimize-player').click()
  requireCondition(await page.locator('#video-dock').getAttribute('data-size') === 'compact', 'Player did not enter visible compact state')
  requireCondition(await embed.handle.evaluate(element => element === document.querySelector('#video-player iframe') && element.isConnected), 'Minimization replaced/detached the native playing iframe')
  const box = await embed.iframe.boundingBox()
  requireCondition(box && box.width >= 200 && box.height >= 200, `Compact native YouTube viewport is below 200×200: ${JSON.stringify(box)}`)
  requireCondition(await embed.iframe.isVisible(), 'Compact player is hidden')
  const viewport = page.viewportSize()
  requireCondition(box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width + 1 && box.y + box.height <= viewport.height + 1, 'Compact player is clipped outside the visible browser viewport')
  await embed.iframe.hover()
  const actual = await nativeMedia(embed.frame)
  requireNativeContent(actual, record, 'Compact playback')
  requireCondition(actual.controls && actual.controlsHeight > 0 && actual.playButtonWidth >= 20 && actual.playButtonHeight >= 20 && !actual.paused && !actual.muted && actual.volume > 0, `Compact native controls/audio unusable: ${JSON.stringify(actual)}`)
  const samples = []
  if (run) {
    for (let index = 0; index < 5; index++) { await delay(250); samples.push(await clockSample(page, embed, record, run)) }
  } else await delay(1250)
  const after = await nativeMedia(embed.frame), snapshot = await apiSnapshot(page)
  checkSnapshot(snapshot, record.id)
  requireCondition(snapshot.playerState === 'playing' && snapshot.playerAudio?.state === 'audible' && snapshot.playerAudio.volume > 0 && !after.paused && !after.muted && after.mediaTime - initial.mediaTime >= 0.5, 'Minimizing paused/muted/stalled actual native playback')
  const maxClockSkewSeconds = run ? requireAdvancingDraws(samples, 2, 0.25, 'Compact playback') : null
  const screenshot = `${record.id}-compact.png`
  await page.screenshot({ path: resolve(outputDirectory, screenshot) })
  report.compact = { sameIframe: true, bounds: box, native: actual, elapsedNativeSeconds: after.mediaTime - initial.mediaTime, audio: snapshot.playerAudio, samples, maxClockSkewSeconds, screenshot }
  // Prove the shrunken native controls are hit-testable, not merely painted.
  await embed.frame.locator('.ytp-play-button').click()
  await waitState(page, 'paused')
  const paused = await nativeMedia(embed.frame)
  await delay(350)
  const still = await nativeMedia(embed.frame)
  requireCondition(paused.paused && still.paused && Math.abs(still.mediaTime - paused.mediaTime) <= PAUSED_DRIFT_SECONDS, 'Compact native pause control did not pause the actual HTMLMediaElement')
  await embed.iframe.hover()
  await embed.frame.locator('.ytp-play-button').click()
  await waitState(page, 'playing')
  report.compact.nativePauseResumeGestures = true
  await page.locator('#minimize-player').click()
  requireCondition(await page.locator('#video-dock').getAttribute('data-size') === 'expanded', 'Player did not restore expanded state')
}

async function referenceProof(page, embed, record, report, outputDirectory) {
  await pauseActual(page, embed)
  const builtReference = await page.evaluate(() => window.harmonicAnalyzer.referenceData())
  requireCondition(jsonDigest(builtReference) === record.digest, 'Actually loaded built reference observations differ from the independently checked content file')
  const errors = [], fitErrors = [], measurements = [], clockSkews = []
  const shots = new Map(record.data.shots.map(shot => [shot.id, shot]))
  const frames = record.data.frames
  const required = frames.map(frame => sourceNeedsMachine(frame, shots.get(frame.shotId)))
  // Exploratory state immediately before review; no-machine samples must leave it untouched.
  const exploratory = await apiSnapshot(page)
  let viewCount = 0, matchedFrames = 0, heldFrames = 0, noMachineFrames = 0, firstMachineScreenshot = null
  let lastRequired = -1, lastMatched = -1
  try {
    for (let index = 0; index < frames.length; index++) {
      const frame = frames[index], t = frame.timeSeconds
      const expectedViews = required[index] ? frameViews(frame) : lastRequired >= 0 ? frameViews(frames[lastRequired]) : []
      const response = await reviewAt(page, embed, record, t, expectedViews.map(view => view.id))
      const snapshot = response.snapshot, native = response.native
      if (!required[index]) {
        if (snapshot.referenceState === 'no-machine') {
          requireCondition(lastRequired < 0, `no-machine at ${t}s although required frame ${frames[lastRequired]?.timeSeconds}s precedes it; a calibrated hold is required`)
          requireCondition(Array.isArray(snapshot.views) && snapshot.views.length === 0, `no-machine at ${t}s drew source views`)
          requireCondition(nearlyEqual(snapshot.camera, exploratory.camera, UNCHANGED_TOLERANCE) && nearlyEqual(snapshot.input, exploratory.input, UNCHANGED_TOLERANCE), `no-machine at ${t}s replaced exploratory geometry/camera with an invented pose`)
          noMachineFrames++
        } else {
          requireCondition(snapshot.referenceState === 'held', `Unsupported exempt-source state at ${t}s: ${snapshot.referenceState}`)
          requireCondition(lastRequired >= 0 && lastMatched === lastRequired, `held at ${t}s without an actual preceding calibrated matched pose`)
          requireCondition(Array.isArray(snapshot.views) && snapshot.views.length === expectedViews.length && expectedViews.every(view => {
            const rendered = snapshot.views.find(candidate => candidate.id === view.id)
            return rendered && jsonDigest(rendered.rectSourcePixels) === jsonDigest(view.rectSourcePixels) && rendered.presentation === view.presentation && sameCamera(rendered.camera, view.camera)
          }), `held at ${t}s does not draw the exact views of the preceding matched frame ${frames[lastRequired].timeSeconds}s`)
          for (const view of expectedViews) clockSkews.push(freshCapture(response.captures.find(entry => entry.viewId === view.id), t, [native.mediaTime], `Held ${t}s`).skewSeconds)
          heldFrames++
        }
        continue
      }
      lastRequired = index
      requireCondition(snapshot.referenceState === 'matched' && Math.abs(snapshot.modelTime - t) <= 1e-6, `Required physical-source sample unavailable/wrong at ${t}s: ${snapshot.referenceState}`)
      requireCondition(Array.isArray(snapshot.views) && snapshot.views.length === expectedViews.length, `Rendered per-view scene missing at ${t}s`)
      for (const view of expectedViews) {
        const rendered = snapshot.views.find(candidate => candidate.id === view.id)
        requireCondition(rendered && jsonDigest(rendered.rectSourcePixels) === jsonDigest(view.rectSourcePixels) && rendered.presentation === view.presentation, `Actual ROI/mirror view mismatch at ${t}s/${view.id}`)
      }
      const gate = stageGate(response.canvas)
      const captured = new Map()
      for (const view of expectedViews) {
        const { capture, skewSeconds } = freshCapture(response.captures.find(entry => entry.viewId === view.id), t, [native.mediaTime], `Required ${t}s`)
        clockSkews.push(skewSeconds)
        captured.set(view.id, { capture, rect: view.rectSourcePixels, byId: new Map(capture.landmarks.map(item => [item.id, item])) })
      }
      lastMatched = index
      matchedFrames++; viewCount += expectedViews.length
      for (const item of frame.landmarks) {
        const viewId = item.viewId ?? 'main', view = captured.get(viewId)
        const landmark = view?.byId.get(item.anchorId) ?? null
        const context = { timeSeconds: t, viewId, anchorId: item.anchorId, role: item.role, captureTimeSeconds: view?.capture.timeSeconds ?? null, nativeMediaTime: native.mediaTime, landmark }
        if (!landmark || landmark.state !== 'rendered' || !vec2(landmark.sourcePixels) || !vec2(landmark.canvasPixels)) {
          fail(report, 'unrendered-gpu-landmark', 'Required landmark has no actual GPU-rendered marker pixel in this view', context)
          continue
        }
        const [rx, ry, rw, rh] = view.rect
        if (landmark.sourcePixels[0] < rx || landmark.sourcePixels[1] < ry || landmark.sourcePixels[0] > rx + rw || landmark.sourcePixels[1] > ry + rh) fail(report, 'rendered-outside-view', 'GPU marker lies outside its source view rectangle', context)
        const expectedCanvas = [gate.x + landmark.sourcePixels[0] / 1920 * gate.width, gate.y + landmark.sourcePixels[1] / 1080 * gate.height]
        const viewportMappingErrorPx = Math.hypot(landmark.canvasPixels[0] - expectedCanvas[0], landmark.canvasPixels[1] - expectedCanvas[1])
        if (viewportMappingErrorPx > VIEWPORT_MAPPING_LIMIT_PX) fail(report, 'actual-viewport-mapping', 'GPU marker canvas position is not on the source-letterboxed #stage gate', { ...context, viewportMappingErrorPx })
        const errorPx = Math.hypot(landmark.sourcePixels[0] - item.pixel[0], landmark.sourcePixels[1] - item.pixel[1])
        const measured = { timeSeconds: t, decodedTimeSeconds: frame.decodedTimeSeconds, nativeMediaTime: native.mediaTime, captureTimeSeconds: view.capture.timeSeconds, method: view.capture.method, viewId, anchorId: item.anchorId, role: item.role, observedSourcePixels: item.pixel, renderedSourcePixels: landmark.sourcePixels, renderedCanvasPixels: landmark.canvasPixels, uncertaintyCanvasPixels: landmark.uncertaintyCanvasPixels, viewportMappingErrorPx, errorPx }
        measurements.push(measured)
        if (item.role === 'check') errors.push(errorPx); else fitErrors.push(errorPx)
        if (errorPx > PIXEL_LIMIT) fail(report, 'rendered-landmark-error', `Actual GPU-rendered ${item.role} error ${errorPx.toFixed(3)}px exceeds ${PIXEL_LIMIT}px`, measured)
      }
      if (!firstMachineScreenshot) {
        firstMachineScreenshot = `${record.id}-matched.png`
        await page.screenshot({ path: resolve(outputDirectory, firstMachineScreenshot) })
      }
    }
  } finally {
    report.reference = { matchedFrames, heldFrames, noMachineFrames, renderedViewCount: viewCount, expectedMachineFrames: record.report.machineFrames, expectedExemptFrames: record.report.exemptFrames, expectedViewCount: record.report.requiredViews, expectedFits: record.report.fitLandmarks, expectedChecks: record.report.checkLandmarks, heldOut: errorStats(errors), fitting: errorStats(fitErrors), maxDrawClockSkewSeconds: clockSkews.length ? Math.max(...clockSkews) : null, pixelSource: 'renderedLandmarks(viewId) gpu-readback of the last actual renderViews draw', firstMachineScreenshot, measurementsFile: `${record.id}-landmarks.json`, staticReviewIsPlaybackEvidence: false }
    await writeFile(resolve(outputDirectory, report.reference.measurementsFile), `${JSON.stringify(measurements, null, 2)}\n`)
    try { await restoreExploration(page, embed) } catch (error) { fail(report, 'end-reference-review', error.message) }
  }
  requireCondition(matchedFrames === record.report.machineFrames && heldFrames + noMachineFrames === record.report.exemptFrames && viewCount === record.report.requiredViews && errors.length === record.report.checkLandmarks && fitErrors.length === record.report.fitLandmarks, 'Actual GPU-rendered reference measurement coverage is incomplete')
  requireCondition(!record.report.machineFrames || errors.length >= 2, 'No independent rendered check measurements exist')
  requireCondition(!report.failures.length, 'One or more actual source-to-render errors exceed the fidelity gate')
}

async function interactionProof(page, embed, id, report, outputDirectory) {
  await pauseActual(page, embed)
  if ((await apiSnapshot(page)).mode === 'reference-review') await endReview(page)
  const ready = await apiSnapshot(page)
  requireCondition(ready.mode === 'exploring' && ready.playerState === 'paused', `Manual interaction requires paused exploration, found ${ready.mode}/${ready.playerState}`)
  await page.locator('#fit-view').click()
  const range = page.locator('#crank')
  requireCondition(await range.isEnabled(), 'Paused crank exploration control is disabled')
  // #stage IS the canvas element; there is no descendant canvas.
  const stage = page.locator('#stage')
  requireCondition(await stage.count() === 1 && await stage.evaluate(element => element instanceof HTMLCanvasElement), 'Exactly one real rendered #stage canvas is required')
  // Mask the overlaid native player so only mechanism canvas pixels are compared.
  const shot = () => stage.screenshot({ mask: [page.locator('#video-dock'), page.locator('#loading')], animations: 'disabled' })
  const before = await apiSnapshot(page)
  const nativeBefore = await nativeMedia(embed.frame)
  const pixelsBefore = await shot()
  const input = await range.evaluate(element => ({ value: Number(element.value), min: Number(element.min), max: Number(element.max), step: Number(element.step) || 0.01 }))
  requireCondition(input.max > input.min, 'Manual crank has no actual travel')
  const direction = input.value + 0.125 <= input.max ? 'ArrowRight' : 'ArrowLeft'
  const presses = Math.max(1, Math.round(0.125 / input.step))
  // Native range keyboard gestures; avoid whole-turn endpoints which can return to the same pose.
  await range.focus()
  for (let count = 0; count < presses; count++) await range.press(direction)
  await page.waitForFunction(initial => Math.abs(window.harmonicAnalyzer.snapshot().input.crankTurns - initial) > 1e-6, before.input.crankTurns, { timeout: 5000 })
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))))
  const after = await apiSnapshot(page)
  const pixelsAfter = await shot()
  const nativeAfter = await nativeMedia(embed.frame)
  requireCondition(after.mode === 'exploring' && after.playerState === 'paused' && nativeAfter.paused && Math.abs(nativeAfter.mediaTime - nativeBefore.mediaTime) <= PAUSED_DRIFT_SECONDS, 'Manual crank must explore geometry with the actual native video paused')
  requireCondition(jsonDigest(after.camera) === jsonDigest(before.camera), 'Manual crank proof moved camera instead of only articulating mechanism')
  requireCondition(digest(pixelsBefore) !== digest(pixelsAfter), 'Manual crank did not change actual rendered canvas pixels')
  const crankScreenshot = `${id}-manual-crank.png`
  await writeFile(resolve(outputDirectory, crankScreenshot), pixelsAfter)
  // Drag only where the canvas itself receives the pointer (not the overlaid player).
  const point = await stage.evaluate(canvas => {
    const rect = canvas.getBoundingClientRect()
    for (const [fx, fy] of [[0.6, 0.45], [0.4, 0.45], [0.5, 0.3], [0.3, 0.3], [0.5, 0.6], [0.25, 0.6], [0.7, 0.25]]) {
      const x = rect.left + rect.width * fx, y = rect.top + rect.height * fy, dx = Math.min(140, rect.width * 0.15)
      if (document.elementFromPoint(x, y) === canvas && document.elementFromPoint(x + dx, y + 45) === canvas) return { x, y, dx }
    }
    return null
  })
  requireCondition(point, 'No unobstructed #stage canvas region receives pointer input')
  await page.mouse.move(point.x, point.y); await page.mouse.down(); await page.mouse.move(point.x + point.dx, point.y + 45, { steps: 8 }); await page.mouse.up()
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))))
  const orbit = await apiSnapshot(page), pixelsOrbit = await shot(), nativeOrbit = await nativeMedia(embed.frame)
  requireCondition(jsonDigest(orbit.camera) !== jsonDigest(after.camera), 'Paused native canvas orbit did not change actual rendered camera')
  requireCondition(digest(pixelsAfter) !== digest(pixelsOrbit), 'Paused orbit did not change actual rendered scene pixels')
  requireCondition(orbit.playerState === 'paused' && nativeOrbit.paused && Math.abs(nativeOrbit.mediaTime - nativeBefore.mediaTime) <= PAUSED_DRIFT_SECONDS, 'Orbit restarted/faked video playback')
  const orbitScreenshot = `${id}-manual-orbit.png`
  await writeFile(resolve(outputDirectory, orbitScreenshot), pixelsOrbit)
  report.interaction = { actualCrankTurns: [before.input.crankTurns, after.input.crankTurns], crankCanvasSha256: [digest(pixelsBefore), digest(pixelsAfter)], orbitCamera: [after.camera, orbit.camera], orbitCanvasSha256: digest(pixelsOrbit), nativeMediaTime: nativeBefore.mediaTime, screenshots: [crankScreenshot, orbitScreenshot], pixelEvidence: '#stage canvas screenshots with the native player overlay masked' }
}

export async function webglPositiveControl(page) {
  return page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 4; canvas.height = 4
    const gl = canvas.getContext('webgl2') ?? canvas.getContext('webgl')
    if (!gl) throw new Error('Native Chromium cannot create WebGL; SwiftShader prerequisite unavailable')
    gl.clearColor(0.25, 0.5, 0.75, 1); gl.clear(gl.COLOR_BUFFER_BIT)
    const pixel = new Uint8Array(4); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel)
    if (Math.abs(pixel[0] - 64) > 1 || Math.abs(pixel[1] - 128) > 1 || Math.abs(pixel[2] - 191) > 1 || pixel[3] !== 255) throw new Error('Native WebGL framebuffer positive control did not render')
    const info = gl.getExtension('WEBGL_debug_renderer_info')
    const result = { pixel: Array.from(pixel), renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), vendor: gl.getParameter(gl.VENDOR), version: gl.getParameter(gl.VERSION) }
    gl.getExtension('WEBGL_lose_context')?.loseContext()
    return result
  })
}

export async function verifySync() {
  const startedAt = new Date().toISOString()
  const outputDirectory = resolve(WEB_ROOT, '.vite/verification-output', startedAt.replace(/[:.]/g, '-'))
  await mkdir(outputDirectory, { recursive: true })
  const report = { startedAt, finishedAt: null, status: 'failed', limits: { sourceLandmarkPx: PIXEL_LIMIT, videoModelClockSeconds: CLOCK_LIMIT, viewportMappingPx: VIEWPORT_MAPPING_LIMIT_PX, compactViewportPixels: [200, 200] }, outputDirectory, failures: [], sources: [], videos: [], builtAssets: [], serverRequests: [], browserLog: [], verificationMode: 'Built app in native Chromium; landmark pixels from GPU-readback markers of the last actual renderViews draw (depth test off: no occlusion claim); clock from the official YouTube iframe HTMLMediaElement.currentTime versus captured required-source draw time; seeks only through the official player; no mocks, CPU projections, synthetic clocks or skip-green' }
  const abort = new AbortController()
  const interrupt = () => abort.abort(new Error('Verification interrupted'))
  process.once('SIGINT', interrupt); process.once('SIGTERM', interrupt)
  let server, browser, context, page
  try {
    const referenceRoot = resolve(process.env.HARMONIC_REFERENCE_ROOT ?? '/tmp/harmonic-web-reference')
    const references = await loadReferences(WEB_ROOT, referenceRoot, { signal: abort.signal })
    report.sources = references.records.map(record => ({ ...record.report, observationDigest: record.digest, source: { sha256: record.native.observedSha256, width: record.native.width, height: record.native.height, durationSeconds: record.native.durationSeconds, fps: record.native.fps, nativeFrameCount: record.native.nativeFrameCount } }))
    report.failures.push(...references.failures)
    for (const source of report.sources) for (const failure of source.failures) report.failures.push({ videoId: source.videoId, ...failure })
    requireCondition(references.records.length === VIDEO_IDS.length && !report.failures.length, `Independent all-${VIDEO_IDS.length} source prerequisites/coverage failed; see report.json. No camera/timeline self-grading or external-media skip is permitted.`)
    const dist = resolve(WEB_ROOT, 'dist')
    await stat(resolve(dist, 'index.html'))
    report.builtAssets = await distManifest(dist)
    requireCondition(report.builtAssets.find(asset => asset.path === 'models/harmonic-analyzer.glb')?.sha256 === MODEL_SHA256, 'Built authentic GLB is missing or does not match measured source/model identity')
    server = await serveDist(dist, { base: process.env.SIMULATOR_BASE, requests: report.serverRequests, signal: abort.signal })
    report.baseUrl = server.url
    const { chromium } = await import('playwright')
    const executablePath = process.env.HARMONIC_CHROME ?? '/usr/bin/google-chrome'
    browser = await chromium.launch({ executablePath, headless: process.env.HARMONIC_HEADLESS === '1', timeout: 30_000, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox', '--disable-dev-shm-usage'] })
    abort.signal.addEventListener('abort', () => void browser.close(), { once: true })
    context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
    context.setDefaultTimeout(20_000)
    page = await context.newPage()
    page.on('console', message => { if (message.type() === 'error' || message.type() === 'warning') report.browserLog.push({ type: message.type(), text: message.text(), location: message.location() }) })
    page.on('pageerror', error => report.browserLog.push({ type: 'pageerror', text: error.message }))
    page.on('requestfailed', request => report.browserLog.push({ type: 'requestfailed', url: request.url(), failure: request.failure() }))
    report.browserVersion = browser.version()
    report.webglPositiveControl = await webglPositiveControl(page)
    for (const record of references.records) {
      const video = { videoId: record.id, failures: [] }
      report.videos.push(video)
      try {
        const route = new URL(server.url); route.searchParams.set('video', record.id); route.searchParams.set('verify', '1')
        video.route = route.href
        const response = await page.goto(route.href, { waitUntil: 'domcontentloaded', timeout: 30_000 })
        requireCondition(response?.ok(), `Built direct route failed HTTP ${response?.status()}`)
        await page.waitForFunction(id => window.harmonicAnalyzer?.snapshot().videoId === id && window.harmonicAnalyzer.snapshot().modelState !== 'loading', record.id, { timeout: 90_000 })
        // YouTube may not publish getVideoData until the first gesture. Wait for
        // the real resolved player's public control, then verify identity while
        // actually playing rather than gating the very gesture that loads it.
        await page.waitForFunction(() => { const button = document.querySelector('#pause-video'); return button && !button.disabled }, undefined, { timeout: 25_000 })
        const snapshot = await apiSnapshot(page)
        requireCondition(snapshot.modelState === 'ready', 'Actual articulated model is unavailable; no missing-GLB green path')
        requireCondition(snapshot.playerState !== 'error', `Native YouTube external-media prerequisite failed for ${record.id}`)
        const links = await page.locator('#videos a').evaluateAll(elements => elements.map(element => new URL(element.href).searchParams.get('video')))
        requireCondition(links.length === VIDEO_IDS.length && new Set(links).size === VIDEO_IDS.length, `All ${VIDEO_IDS.length} direct video navigation links must be present and distinct`)
        const run = longestRun(record)
        video.requiredClockRun = run
        const embed = await playbackProof(page, record, run, video)
        await compactProof(page, record, embed, run, video, outputDirectory)
        await referenceProof(page, embed, record, video, outputDirectory)
        if (record.report.machineFrames && !report.videos.some(item => item.interaction)) await interactionProof(page, embed, record.id, video, outputDirectory)
        video.status = 'passed'
      } catch (error) {
        video.status = 'failed'
        fail(video, 'native-verification', error.message)
        try {
          video.failureDiagnostics = await page.evaluate(() => {
            const visibleText = selector => document.querySelector(selector)?.textContent?.trim() ?? ''
            let snapshot = null
            try { snapshot = window.harmonicAnalyzer?.snapshot() ?? null } catch (error) { snapshot = { error: error.message } }
            return { videoError: visibleText('#video-error'), sourceError: visibleText('#source-error'), modelStatus: visibleText('#model-status'), status: visibleText('#status'), snapshot }
          })
        } catch (diagnosticError) { video.diagnosticError = diagnosticError.message }
        try { video.failureScreenshot = `${record.id}-failed.png`; await page.screenshot({ path: resolve(outputDirectory, video.failureScreenshot) }) } catch (screenshotError) { video.screenshotError = screenshotError.message }
        report.failures.push(...video.failures.map(failure => ({ videoId: record.id, ...failure })))
      }
    }
    requireCondition(report.videos.length === VIDEO_IDS.length && report.videos.every(video => video.status === 'passed') && report.videos.some(video => video.interaction), `Native all-${VIDEO_IDS.length} verification or actual paused interaction proof failed`)
    requireCondition(!report.browserLog.some(item => item.type === 'pageerror'), 'Native browser has unhandled page errors')
    report.status = 'passed'
  } catch (error) { fail(report, 'verification-prerequisite', error.message) }
  finally {
    try { await page?.close() } catch (error) { fail(report, 'page-cleanup', error.message) }
    try { await context?.close() } catch (error) { fail(report, 'context-cleanup', error.message) }
    try { await browser?.close() } catch (error) { fail(report, 'browser-cleanup', error.message) }
    try { await server?.close() } catch (error) { fail(report, 'server-cleanup', error.message) }
    process.removeListener('SIGINT', interrupt); process.removeListener('SIGTERM', interrupt)
    report.finishedAt = new Date().toISOString()
    if (report.failures.length) report.status = 'failed'
    await writeFile(resolve(outputDirectory, 'report.json'), `${JSON.stringify(report, null, 2)}\n`)
    const heldOut = { count: 0, maxPx: null, rmsPx: null }
    let squared = 0
    for (const video of report.videos) {
      const stats = video.reference?.heldOut
      if (!stats?.count) continue
      heldOut.count += stats.count; heldOut.maxPx = Math.max(heldOut.maxPx ?? 0, stats.maxPx); squared += stats.count * stats.rmsPx * stats.rmsPx
    }
    if (heldOut.count) heldOut.rmsPx = Math.sqrt(squared / heldOut.count)
    const clockMeasurements = report.videos.flatMap(video => [video.playback?.maxClockSkewSeconds, video.compact?.maxClockSkewSeconds, video.reference?.maxDrawClockSkewSeconds]).filter(finite)
    const summary = { status: report.status, videoCount: report.videos.length, sourceCount: report.sources.length, failureCount: report.failures.length, report: resolve(outputDirectory, 'report.json'), maxClockSkewSeconds: clockMeasurements.length ? Math.max(...clockMeasurements) : null, heldOut }
    console.log(JSON.stringify(summary, null, 2))
  }
  return report.status === 'passed' ? 0 : 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--help')) console.log(`Usage: npm run verify:sync\nRequires an existing production dist, all ${VIDEO_IDS.length} private source MP4s/complete independent observations (${VIDEO_IDS.join(', ')}), playwright and native /usr/bin/google-chrome.\nEnvironment: HARMONIC_REFERENCE_ROOT (default /tmp/harmonic-web-reference), SIMULATOR_BASE (must match build), HARMONIC_CHROME, HARMONIC_HEADLESS=1 (default headed).\nOutput: web/.vite/verification-output/<timestamp>/report.json and actual native screenshots/measurements. External YouTube restrictions fail; nothing is mocked or skipped.`)
  else process.exitCode = await verifySync()
}
