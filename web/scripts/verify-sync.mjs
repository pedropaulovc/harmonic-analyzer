#!/usr/bin/env node
import { mkdir, writeFile, stat } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { VIDEO_IDS, MODEL_SHA256, MODEL_COMMIT, PIXEL_LIMIT, CLOCK_LIMIT, loadReferences, frameViews, sourceNeedsMachine, errorStats, jsonDigest } from './verify-reference.mjs'
import { distManifest, serveDist } from './verify-server.mjs'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const CRANK_ANCHOR = { partPath: 'harmonic-analyzer/drive-train/crank-handle-1', partLocalMetres: [0, 0, 0] }
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const delay = ms => new Promise(done => setTimeout(done, ms))
const finite = value => typeof value === 'number' && Number.isFinite(value)
function requireCondition(condition, message) { if (!condition) throw new Error(message) }
function fail(report, code, detail, extra = {}) { report.failures.push({ code, detail, ...extra }) }

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

async function nativeMedia(frame) {
  return frame.evaluate(() => {
    const video = document.querySelector('video')
    const control = document.querySelector('.ytp-play-button')
    const controls = document.querySelector('.ytp-chrome-bottom')
    const buttonRect = control?.getBoundingClientRect(), rect = controls?.getBoundingClientRect()
    return { mediaPresent: !!video, paused: video?.paused, muted: video?.muted, volume: video?.volume, mediaTime: video?.currentTime, controls: !!controls && !!control, controlsHeight: rect?.height ?? 0, playButtonWidth: buttonRect?.width ?? 0, playButtonHeight: buttonRect?.height ?? 0, error: document.querySelector('.ytp-error-content-wrap, .ytp-error')?.textContent?.trim() ?? '' }
  })
}

async function playbackProof(page, id, report) {
  const embed = await nativeFrame(page, id)
  const before = await apiSnapshot(page)
  if (before.playerState === 'playing') { await page.locator('#pause-video').click(); await waitState(page, 'paused') }
  await page.locator('#follow-video').click()
  // This is an actual browser click, not evaluate(playVideo), a fake clock or a seek.
  await page.locator('#pause-video').click()
  await waitState(page, 'playing')
  const samples = []
  report.playback = { samples, native: null, maxClockSkewSeconds: null, iframeSrc: embed.src, userGesture: '#pause-video click; no seek/review clock injection' }
  for (let index = 0; index < 12; index++) {
    await delay(250)
    const sample = await apiSnapshot(page)
    checkSnapshot(sample, id)
    requireCondition(sample.mode === 'following-video' && sample.playerState === 'playing', `Native playback stopped or left following mode at sample ${index}: ${sample.playerState}/${sample.mode}`)
    requireCondition(finite(sample.videoTime) && finite(sample.modelTime), 'Native/model clocks must be finite')
    const skewSeconds = Math.abs(sample.videoTime - sample.modelTime)
    samples.push({ videoTime: sample.videoTime, modelTime: sample.modelTime, skewSeconds, playerState: sample.playerState, referenceState: sample.referenceState, mode: sample.mode })
    report.playback.maxClockSkewSeconds = Math.max(report.playback.maxClockSkewSeconds ?? 0, skewSeconds)
    requireCondition(skewSeconds <= CLOCK_LIMIT, `Video/model clock error ${skewSeconds.toFixed(3)}s exceeds ${CLOCK_LIMIT}s`)
  }
  requireCondition(samples.at(-1).videoTime - samples[0].videoTime >= 1, 'Real YouTube getCurrentTime did not advance during user-gesture playback')
  const actual = await nativeMedia(embed.frame), snapshot = await apiSnapshot(page)
  report.playback.native = actual
  requireCondition(actual.mediaPresent && !actual.paused && !actual.muted && actual.volume > 0 && actual.controls && actual.controlsHeight > 0 && actual.playButtonWidth > 0, `Actual native media/audio/controls unavailable: ${JSON.stringify(actual)}`)
  requireCondition(finite(actual.mediaTime) && Math.abs(actual.mediaTime - snapshot.videoTime) <= CLOCK_LIMIT, 'Actual native HTML media clock disagrees with YouTube getCurrentTime; synthetic/ad/unavailable playback is not synchronization proof')
  requireCondition(snapshot.playerAudio?.state === 'audible' && snapshot.playerAudio.volume > 0, 'YouTube API reports muted/inaudible playback')
  return embed
}

async function compactProof(page, id, embed, report, outputDirectory) {
  const initial = await apiSnapshot(page)
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
  requireCondition(actual.controls && actual.controlsHeight > 0 && actual.playButtonWidth >= 20 && actual.playButtonHeight >= 20 && !actual.paused && !actual.muted && actual.volume > 0, `Compact native controls/audio unusable: ${JSON.stringify(actual)}`)
  await delay(1250)
  const after = await apiSnapshot(page)
  checkSnapshot(after, id)
  requireCondition(after.playerState === 'playing' && after.playerAudio?.state === 'audible' && after.playerAudio.volume > 0 && after.videoTime - initial.videoTime >= 0.5, 'Minimizing paused/muted/stalled actual playback')
  requireCondition(Math.abs(after.modelTime - after.videoTime) <= CLOCK_LIMIT, 'Compact native playback lost model synchronization')
  const screenshot = `${id}-compact.png`
  await page.screenshot({ path: resolve(outputDirectory, screenshot) })
  report.compact = { sameIframe: true, bounds: box, native: actual, elapsedVideoSeconds: after.videoTime - initial.videoTime, audio: after.playerAudio, screenshot }
  // Prove the shrunken native controls are hit-testable, not merely painted.
  await embed.frame.locator('.ytp-play-button').click()
  await waitState(page, 'paused')
  const paused = await apiSnapshot(page)
  await delay(350)
  requireCondition(Math.abs((await apiSnapshot(page)).videoTime - paused.videoTime) <= 0.1, 'Compact native pause control did not pause the real clock')
  await embed.iframe.hover()
  await embed.frame.locator('.ytp-play-button').click()
  await waitState(page, 'playing')
  report.compact.nativePauseResumeGestures = true
  await page.locator('#minimize-player').click()
  requireCondition(await page.locator('#video-dock').getAttribute('data-size') === 'expanded', 'Player did not restore expanded state')
}

async function pauseActual(page) {
  const current = await apiSnapshot(page)
  if (current.playerState === 'playing') await page.locator('#pause-video').click()
  await waitState(page, 'paused')
  const before = await apiSnapshot(page)
  await delay(500)
  const after = await apiSnapshot(page)
  requireCondition(Math.abs(after.videoTime - before.videoTime) <= 0.1, 'Actual native video clock continues while paused')
}

async function referenceProof(page, record, report, outputDirectory) {
  await pauseActual(page)
  const builtReference = await page.evaluate(() => window.harmonicAnalyzer.referenceData())
  requireCondition(jsonDigest(builtReference) === record.digest, 'Actually loaded built reference observations differ from the independently checked content file')
  const errors = [], fitErrors = [], measurements = []
  const shots = new Map(record.data.shots.map(shot => [shot.id, shot]))
  const anchors = new Map(record.data.anchors.map(anchor => [anchor.id, anchor]))
  const canvasSize = await page.locator('#stage canvas').evaluate(canvas => ({ width: canvas.clientWidth, height: canvas.clientHeight }))
  const gateWidth = Math.min(canvasSize.width, canvasSize.height * 1920 / 1080)
  const gateHeight = gateWidth * 1080 / 1920
  const gateX = (canvasSize.width - gateWidth) / 2, gateY = (canvasSize.height - gateHeight) / 2
  requireCondition(gateWidth > 0 && gateHeight > 0, 'Actual source-render canvas viewport is hidden/empty')
  let viewCount = 0, matchedFrames = 0, heldFrames = 0, firstMachineScreenshot = null
  const expectedClock = (await apiSnapshot(page)).videoTime
  try {
    for (const frame of record.data.frames) {
      const needsMachine = sourceNeedsMachine(frame, shots.get(frame.shotId))
      const response = await page.evaluate(({ timeSeconds, views, landmarks }) => {
        const api = window.harmonicAnalyzer
        const snapshot = api.reviewReferenceFrame(timeSeconds)
        const projected = landmarks.map(item => {
          const result = api.projectAnchor(item.anchor, item.viewId ?? 'main')
          // The renderer deliberately reuses its hot-path output buffer. Capture
          // each actual result before another anchor/view mutates that buffer.
          const projection = result ? { sourcePixels: [...result.sourcePixels], viewportPixels: [...result.viewportPixels], visibility: result.visibility, depth: result.depth } : null
          return { anchorId: item.anchorId, viewId: item.viewId ?? 'main', role: item.role, pixel: item.pixel, projection }
        })
        return { snapshot, projected, views }
      }, { timeSeconds: frame.timeSeconds, views: frameViews(frame).map(view => ({ id: view.id, rectSourcePixels: view.rectSourcePixels, presentation: view.presentation })), landmarks: needsMachine ? frame.landmarks.map(item => ({ anchorId: item.anchorId, viewId: item.viewId, role: item.role, pixel: item.pixel, anchor: anchors.get(item.anchorId) })) : [] })
      const snapshot = response.snapshot
      checkSnapshot(snapshot, record.id)
      requireCondition(snapshot.mode === 'reference-review' && snapshot.playerState === 'paused', 'Static reference review must remain distinct from actual paused YouTube playback')
      requireCondition(Math.abs(snapshot.videoTime - expectedClock) <= 0.1, 'Reference review improperly seeks/fakes the real native video clock')
      if (!needsMachine) {
        requireCondition(snapshot.referenceState === 'held', `Unsupported no-mechanism hold at ${frame.timeSeconds}s: ${snapshot.referenceState}`)
        heldFrames++
        continue
      }
      requireCondition(snapshot.referenceState === 'matched' && Math.abs(snapshot.modelTime - frame.timeSeconds) <= 1e-6, `Visible physical-source sample unavailable/wrong at ${frame.timeSeconds}s`)
      requireCondition(Array.isArray(snapshot.views) && snapshot.views.length === response.views.length, `Rendered per-view scene missing at ${frame.timeSeconds}s`)
      for (const view of response.views) {
        const rendered = snapshot.views.find(candidate => candidate.id === view.id)
        requireCondition(rendered && jsonDigest(rendered.rectSourcePixels) === jsonDigest(view.rectSourcePixels) && rendered.presentation === view.presentation, `Actual ROI/mirror view mismatch at ${frame.timeSeconds}s/${view.id}`)
      }
      matchedFrames++; viewCount += response.views.length
      for (const item of response.projected) {
        const projection = item.projection
        if (!projection || projection.visibility !== 'visible' || !finite(projection.depth) || projection.depth <= 0 || !Array.isArray(projection.sourcePixels) || projection.sourcePixels.length !== 2 || !projection.sourcePixels.every(finite) || !Array.isArray(projection.viewportPixels) || projection.viewportPixels.length !== 2 || !projection.viewportPixels.every(finite)) {
          fail(report, 'unprojectable-rendered-anchor', 'Actual articulated native point missing/hidden/unprojectable', { timeSeconds: frame.timeSeconds, viewId: item.viewId, anchorId: item.anchorId, projection })
          continue
        }
        const expectedViewport = [gateX + projection.sourcePixels[0] / 1920 * gateWidth, gateY + projection.sourcePixels[1] / 1080 * gateHeight]
        const viewportMappingErrorPx = Math.hypot(projection.viewportPixels[0] - expectedViewport[0], projection.viewportPixels[1] - expectedViewport[1])
        if (viewportMappingErrorPx > 0.75) fail(report, 'actual-viewport-mapping', 'Projection is not through the actual source-letterboxed canvas viewport', { timeSeconds: frame.timeSeconds, viewId: item.viewId, anchorId: item.anchorId, viewportMappingErrorPx })
        const errorPx = Math.hypot(projection.sourcePixels[0] - item.pixel[0], projection.sourcePixels[1] - item.pixel[1])
        const measured = { timeSeconds: frame.timeSeconds, decodedTimeSeconds: frame.decodedTimeSeconds, viewId: item.viewId, anchorId: item.anchorId, role: item.role, observedSourcePixels: item.pixel, renderedSourcePixels: projection.sourcePixels, renderedViewportPixels: projection.viewportPixels, depthMetres: projection.depth, viewportMappingErrorPx, errorPx }
        measurements.push(measured)
        if (item.role === 'check') errors.push(errorPx); else fitErrors.push(errorPx)
        if (errorPx > PIXEL_LIMIT) fail(report, 'rendered-landmark-error', `Actual ${item.role} error ${errorPx.toFixed(3)}px exceeds ${PIXEL_LIMIT}px`, measured)
      }
      if (!firstMachineScreenshot) {
        firstMachineScreenshot = `${record.id}-matched.png`
        await page.screenshot({ path: resolve(outputDirectory, firstMachineScreenshot) })
      }
    }
  } finally {
    report.reference = { matchedFrames, heldFrames, renderedViewCount: viewCount, expectedMachineFrames: record.report.machineFrames, expectedViewCount: record.report.requiredViews, expectedChecks: record.report.checkLandmarks, heldOut: errorStats(errors), fitting: errorStats(fitErrors), firstMachineScreenshot, measurementsFile: `${record.id}-landmarks.json`, staticReviewIsPlaybackEvidence: false }
    await writeFile(resolve(outputDirectory, report.reference.measurementsFile), `${JSON.stringify(measurements, null, 2)}\n`)
  }
  requireCondition(matchedFrames === record.report.machineFrames && viewCount === record.report.requiredViews && errors.length === record.report.checkLandmarks, 'Actual-rendered reference measurement coverage is incomplete')
  requireCondition(!record.report.machineFrames || errors.length >= 2, 'No independent rendered check measurements exist')
  requireCondition(!report.failures.length, 'One or more actual source-to-render errors exceed the fidelity gate')
}

async function interactionProof(page, id, report, outputDirectory) {
  await pauseActual(page)
  await page.locator('#fit-view').click()
  const range = page.locator('#crank')
  requireCondition(await range.isEnabled(), 'Paused crank exploration control is disabled')
  const stage = page.locator('#stage canvas')
  requireCondition(await stage.count() === 1, 'Exactly one real rendered mechanism canvas is required')
  const before = await apiSnapshot(page)
  const projectionBefore = await page.evaluate(anchor => window.harmonicAnalyzer.projectAnchor(anchor), CRANK_ANCHOR)
  const pixelsBefore = await stage.screenshot()
  const input = await range.evaluate(element => ({ value: Number(element.value), min: Number(element.min), max: Number(element.max), step: Number(element.step) || 0.01 }))
  requireCondition(input.max > input.min, 'Manual crank has no actual travel')
  const direction = input.value + 0.125 <= input.max ? 'ArrowRight' : 'ArrowLeft'
  const presses = Math.max(1, Math.round(0.125 / input.step))
  // Native range keyboard gestures use the public control's documented turns.
  // Avoid whole-turn endpoints which can legitimately return to the same pose.
  await range.focus()
  for (let count = 0; count < presses; count++) await range.press(direction)
  await page.waitForFunction(initial => Math.abs(window.harmonicAnalyzer.snapshot().input.crankTurns - initial) > 1e-6, before.input.crankTurns, { timeout: 5000 })
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))))
  const after = await apiSnapshot(page)
  const projectionAfter = await page.evaluate(anchor => window.harmonicAnalyzer.projectAnchor(anchor), CRANK_ANCHOR)
  const pixelsAfter = await stage.screenshot()
  requireCondition(after.mode === 'exploring' && after.playerState === 'paused' && Math.abs(after.videoTime - before.videoTime) <= 0.1, 'Manual crank must explore geometry with the real video paused')
  requireCondition(jsonDigest(after.camera) === jsonDigest(before.camera), 'Manual crank proof moved camera instead of only articulating mechanism')
  requireCondition(projectionBefore && projectionAfter && Math.hypot(projectionAfter.sourcePixels[0] - projectionBefore.sourcePixels[0], projectionAfter.sourcePixels[1] - projectionBefore.sourcePixels[1]) > 1, 'Actual native crank-handle transform did not visibly move')
  requireCondition(digest(pixelsBefore) !== digest(pixelsAfter), 'Manual crank did not change actual rendered canvas pixels')
  const crankScreenshot = `${id}-manual-crank.png`
  await writeFile(resolve(outputDirectory, crankScreenshot), pixelsAfter)
  const box = await stage.boundingBox()
  const x = box.x + box.width * 0.6, y = box.y + box.height * 0.45
  await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + Math.min(140, box.width * 0.15), y + 45, { steps: 8 }); await page.mouse.up()
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))))
  const orbit = await apiSnapshot(page), pixelsOrbit = await stage.screenshot()
  requireCondition(jsonDigest(orbit.camera) !== jsonDigest(after.camera), 'Paused native canvas orbit did not change actual rendered camera')
  requireCondition(digest(pixelsAfter) !== digest(pixelsOrbit), 'Paused orbit did not change actual rendered scene pixels')
  requireCondition(orbit.playerState === 'paused' && Math.abs(orbit.videoTime - before.videoTime) <= 0.1, 'Orbit restarted/faked video playback')
  const orbitScreenshot = `${id}-manual-orbit.png`
  await writeFile(resolve(outputDirectory, orbitScreenshot), pixelsOrbit)
  report.interaction = { actualCrankTurns: [before.input.crankTurns, after.input.crankTurns], crankProbePixels: [projectionBefore.sourcePixels, projectionAfter.sourcePixels], crankCanvasSha256: [digest(pixelsBefore), digest(pixelsAfter)], orbitCamera: [after.camera, orbit.camera], orbitCanvasSha256: digest(pixelsOrbit), screenshots: [crankScreenshot, orbitScreenshot] }
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
  const report = { startedAt, finishedAt: null, status: 'failed', limits: { sourceLandmarkPx: PIXEL_LIMIT, videoModelClockSeconds: CLOCK_LIMIT, compactViewportPixels: [200, 200] }, outputDirectory, failures: [], sources: [], videos: [], builtAssets: [], serverRequests: [], browserLog: [], verificationMode: 'actual built scene and native YouTube; no mocks, source seeks, synthetic clocks or skip-green' }
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
    requireCondition(references.records.length === VIDEO_IDS.length && !report.failures.length, 'Independent full-seven source prerequisites/coverage failed; see report.json. No camera/timeline self-grading or external-media skip is permitted.')
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
        requireCondition(links.length === 7 && new Set(links).size === 7, 'All seven direct video navigation links must be present and distinct')
        const embed = await playbackProof(page, record.id, video)
        await compactProof(page, record.id, embed, video, outputDirectory)
        await referenceProof(page, record, video, outputDirectory)
        if (record.report.machineFrames && !report.videos.some(item => item.interaction)) await interactionProof(page, record.id, video, outputDirectory)
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
    requireCondition(report.videos.length === 7 && report.videos.every(video => video.status === 'passed') && report.videos.some(video => video.interaction), 'Native full-seven verification or actual paused interaction proof failed')
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
    const clockMeasurements = report.videos.map(video => video.playback?.maxClockSkewSeconds).filter(finite)
    const summary = { status: report.status, videoCount: report.videos.length, sourceCount: report.sources.length, failureCount: report.failures.length, report: resolve(outputDirectory, 'report.json'), maxClockSkewSeconds: clockMeasurements.length ? Math.max(...clockMeasurements) : null, heldOut }
    console.log(JSON.stringify(summary, null, 2))
  }
  return report.status === 'passed' ? 0 : 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--help')) console.log('Usage: npm run verify:sync\nRequires an existing production dist, all seven private source MP4s/complete independent observations, playwright and native /usr/bin/google-chrome.\nEnvironment: HARMONIC_REFERENCE_ROOT (default /tmp/harmonic-web-reference), SIMULATOR_BASE (must match build), HARMONIC_CHROME, HARMONIC_HEADLESS=1 (default headed).\nOutput: web/.vite/verification-output/<timestamp>/report.json and actual native screenshots/measurements. External YouTube restrictions fail; nothing is mocked or skipped.')
  else process.exitCode = await verifySync()
}
