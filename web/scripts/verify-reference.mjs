import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { resolve, join } from 'node:path'
import { tmpdir } from 'node:os'

export const VIDEO_IDS = Object.freeze(['NAsM30MAHLg', '8KmVDxkia_w', '6dW6VYXp9HM', 'jfH-NbsmvD4', 'XPQwKRt4Y2k', '4mBuyixt22U'])
export const MODEL_SHA256 = '2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d'
export const MODEL_COMMIT = '1268c23d4a8fc741147c5e09d8d1e45247a71945'
export const PIXEL_LIMIT = 1920 * 0.02
export const CLOCK_LIMIT = 0.5
const EPSILON = 1e-6
const finite = value => typeof value === 'number' && Number.isFinite(value)
const vector = (value, size) => Array.isArray(value) && value.length === size && value.every(finite)
const text = value => typeof value === 'string' && value.trim().length > 0
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`
  return JSON.stringify(value)
}
export function jsonDigest(value) { return createHash('sha256').update(canonicalJson(value)).digest('hex') }
export async function sha256File(path) {
  const digest = createHash('sha256')
  for await (const chunk of createReadStream(path)) digest.update(chunk)
  return digest.digest('hex')
}

/** No shell, finite deadline, and the child is killed on timeout or interruption. */
export function runTool(binary, args, { timeoutMs = 120_000, signal, maxBytes = 64 * 1024 * 1024 } = {}) {
  return new Promise((resolveResult, reject) => {
    const child = spawn(binary, args, { stdio: ['ignore', 'pipe', 'pipe'], signal })
    const stdout = [], stderr = []
    let bytes = 0, failure = null
    const timer = setTimeout(() => { failure = new Error(`${binary} exceeded ${timeoutMs / 1000}s`); child.kill('SIGKILL') }, timeoutMs)
    child.stdout.on('data', chunk => {
      bytes += chunk.length
      if (bytes > maxBytes) { failure = new Error(`${binary} output exceeded ${maxBytes} bytes`); child.kill('SIGKILL') }
      else stdout.push(chunk)
    })
    child.stderr.on('data', chunk => { if (stderr.reduce((n, item) => n + item.length, 0) < 64 * 1024) stderr.push(chunk) })
    child.once('error', error => { clearTimeout(timer); reject(error) })
    child.once('close', code => {
      clearTimeout(timer)
      const errorText = Buffer.concat(stderr).toString()
      if (failure || code !== 0) reject(failure ?? new Error(`${binary} exited ${code}: ${errorText.trim()}`))
      else resolveResult({ stdout: Buffer.concat(stdout), stderr: errorText })
    })
  })
}

/**
 * Single requirement rule shared with the runtime timeline: a frame must be
 * physically matched when it shows the machine, when its shot declares a
 * corresponding machine (whatever its classification: transition, photograph,
 * overlay…), or when a transition/unobservable shot does not explicitly exempt
 * it. Only non-machine shots without a declared machine, or shots explicitly
 * declaring hasCorrespondingMachine=false, are exempt.
 */
export function sourceNeedsMachine(frame, shot) {
  if (frame.classification === 'machine' || shot?.hasCorrespondingMachine === true) return true
  if (frame.classification === 'non-machine' || shot?.hasCorrespondingMachine === false) return false
  return true
}
/** Index of the source frame governing time t (last frame at or before t), or -1. */
export function frameIndexAt(frames, time) {
  let lo = 0, hi = frames.length
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (frames[mid].timeSeconds <= time) lo = mid + 1; else hi = mid }
  return lo - 1
}
/** Contiguous source intervals governed only by required (physically matched) frames. */
export function requiredRuns(data) {
  const shots = new Map((data.shots ?? []).map(shot => [shot.id, shot]))
  const runs = []
  let current = null
  for (const frame of data.frames ?? []) {
    const required = sourceNeedsMachine(frame, shots.get(frame.shotId))
    if (required && !current) current = { startSeconds: frame.timeSeconds, endSeconds: null, frames: 0 }
    if (!required && current) { current.endSeconds = frame.timeSeconds; runs.push(current); current = null }
    if (current) current.frames++
  }
  if (current) { current.endSeconds = data.source.durationSeconds; runs.push(current) }
  return runs
}
export function frameViews(frame) {
  return frame.views ?? [{ id: 'main', rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', camera: frame.camera, mechanicalState: frame.mechanicalState }]
}
export function nearestPtsIndex(pts, time) {
  let lo = 0, hi = pts.length
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (pts[mid] < time) lo = mid + 1; else hi = mid }
  if (lo === 0) return 0
  if (lo === pts.length) return lo - 1
  return time - pts[lo - 1] <= pts[lo] - time ? lo - 1 : lo
}

/** Validates measured evidence, never the fitter's authored error summaries. */
export function inspectReference(data, expectedId, native = null) {
  const failures = []
  const fail = (code, detail, timeSeconds, viewId) => failures.push({ code, detail, ...(timeSeconds === undefined ? {} : { timeSeconds }), ...(viewId === undefined ? {} : { viewId }) })
  const source = data?.source, coverage = data?.coverage
  const summary = { videoId: expectedId, frameCount: 0, integerSecondsRequired: 0, integerSecondsPresent: 0, changeTimesRequired: 0, changeTimesPresent: 0, machineFrames: 0, exemptFrames: 0, requiredViews: 0, fitLandmarks: 0, checkLandmarks: 0, sourcePtsChecked: 0, maxDecodeSkewSeconds: 0, intervals: [], failures }
  if (data?.schemaVersion !== 1) fail('schema', 'schemaVersion must be 1')
  if (source?.videoId !== expectedId || !hash(source?.sha256) || source?.width !== 1920 || source?.height !== 1080 || !finite(source?.durationSeconds) || source.durationSeconds <= 0) {
    fail('source-identity', 'Expected this public video, its SHA256, 1920×1080 and a positive duration')
    return summary
  }
  if (data.model?.sha256 !== MODEL_SHA256 || data.model?.sourceCommit !== MODEL_COMMIT || data.model?.units !== 'metres' || data.model?.axes !== 'X-width/Y-height/Z-depth') fail('model-identity', 'Observations must target the authentic released metre CAD export')
  if (coverage?.status !== 'complete' || !Array.isArray(coverage?.blockers) || coverage.blockers.length) fail('blocked-coverage', JSON.stringify(coverage ?? null))
  if (coverage?.requiredEveryIntegerSecond !== true) fail('integer-census', 'All integer seconds must be required')
  const anchors = new Map()
  for (const anchor of data.anchors ?? []) {
    if (!text(anchor.id) || anchors.has(anchor.id) || !['physical-feature', 'section-center'].includes(anchor.kind) || !text(anchor.partPath) || !text(anchor.correspondenceEvidence) || !text(anchor.description)) fail('anchor-correspondence', `Invalid/duplicate anchor ${anchor.id}`)
    if (vector(anchor.partLocalMetres, 3) === vector(anchor.worldMetres, 3)) fail('anchor-point', `${anchor.id} needs exactly one finite local or world point`)
    // Fixed CAD-world points cannot serve as articulated moving-part observations.
    if (anchor.worldMetres && !anchor.partPath?.startsWith('harmonic-analyzer/frame/')) fail('unarticulated-anchor', `${anchor.id}: moving part points must use partLocalMetres`)
    anchors.set(anchor.id, anchor)
  }
  const shots = new Map(), duration = source.durationSeconds
  let end = 0
  for (const shot of data.shots ?? []) {
    if (!text(shot.id) || shots.has(shot.id) || !finite(shot.startSeconds) || !finite(shot.endSeconds) || shot.endSeconds <= shot.startSeconds || Math.abs(shot.startSeconds - end) > EPSILON || !text(shot.reason) || !['machine', 'non-machine', 'transition', 'unobservable'].includes(shot.classification)) fail('shot-census', `Invalid, overlapping, gapped or unordered shot ${shot.id}`)
    if (shot.classification === 'machine' && shot.hasCorrespondingMachine === false) fail('machine-exemption', `Physical-machine shot ${shot.id} cannot be exempted`)
    shots.set(shot.id, shot)
    summary.intervals.push({ id: shot.id, startSeconds: shot.startSeconds, endSeconds: shot.endSeconds, classification: shot.classification, hasCorrespondingMachine: shot.hasCorrespondingMachine, reason: shot.reason })
    end = shot.endSeconds
  }
  if (!shots.size || Math.abs(end - duration) > EPSILON) fail('shot-duration', 'Shot census must cover source start through its full duration')
  if (!Array.isArray(data.frames) || !data.frames.length) { fail('missing-frames', 'No actual decoded reference frames'); return summary }
  summary.frameCount = data.frames.length
  const times = [], nativeIndices = new Set()
  const allNative = coverage?.requiredEveryNativeFrame === true
  // A full native-frame census subsumes every change. Otherwise the explicit change
  // census is mandatory; chapter-only timestamps are not a motion/edit census.
  if (!allNative && (coverage?.requiredEveryChange !== true || !Array.isArray(coverage?.changeTimesSeconds) || !text(coverage?.changeCensusEvidence))) fail('change-census', 'Declare requiredEveryChange, measured changeTimesSeconds and changeCensusEvidence, or provide every native decoded frame')
  let previous = -Infinity
  const seeds = new Map()
  for (const frame of data.frames) {
    for (const item of frame.landmarks ?? []) if (item.method === 'manual') seeds.set(`${frame.timeSeconds}/${item.viewId ?? 'main'}/${item.anchorId}`, item)
  }
  for (const frame of data.frames) {
    const t = frame.timeSeconds
    if (!finite(t) || t <= previous || t < 0 || t > duration) fail('chronology', 'Frame times must be finite and strictly increasing within source duration', t)
    previous = t; times.push(t)
    const shot = shots.get(frame.shotId)
    if (!shot || t < shot.startSeconds - EPSILON || t >= shot.endSeconds + EPSILON || frame.classification !== shot.classification) { fail('shot-frame', 'Frame must belong to the declared actual-source shot/classification', t); continue }
    if (!finite(frame.decodedTimeSeconds)) fail('decoded-time', 'Missing finite decoded native timestamp', t)
    if (native && finite(frame.decodedTimeSeconds)) {
      const index = nearestPtsIndex(native.pts, frame.decodedTimeSeconds)
      const pt = native.pts[index]
      const mismatch = Math.abs(pt - frame.decodedTimeSeconds), skew = Math.abs(t - frame.decodedTimeSeconds)
      const localStep = Math.max(native.pts[Math.min(index + 1, native.pts.length - 1)] - pt, pt - native.pts[Math.max(index - 1, 0)], 1 / native.fps)
      if (mismatch > 0.001 || skew > localStep + 0.001) fail('source-pts', `Decoded time is not a native source exposure within one frame (${mismatch.toFixed(6)}s identity error)`, t)
      if (frame.decodedFrameIndex !== undefined && frame.decodedFrameIndex !== index) fail('source-frame-index', `Declared frame ${frame.decodedFrameIndex} differs from native ${index}`, t)
      nativeIndices.add(index); summary.sourcePtsChecked++; summary.maxDecodeSkewSeconds = Math.max(summary.maxDecodeSkewSeconds, skew)
      if (frame.sourceImage && frame.sourceImage.frameIndex !== index) fail('source-image-index', `Actual decoded image hash belongs to a different exposure than native ${index}`, t)
    }
    if (!sourceNeedsMachine(frame, shot)) {
      summary.exemptFrames++
      if ((frame.landmarks?.length ?? 0) > 0 || frame.views?.some(view => view.camera)) fail('non-machine-evidence', 'A no-corresponding-machine hold cannot conceal measured physical views', t)
      continue
    }
    summary.machineFrames++
    if (!Array.isArray(frame.landmarks) || !Array.isArray(frame.unavailable)) { fail('missing-landmarks', 'Missing actual-source landmark/unavailability arrays', t); continue }
    if (frame.landmarks.length && (!Number.isInteger(frame.sourceImage?.frameIndex) || frame.sourceImage.frameIndex < 0 || !hash(frame.sourceImage.sha256Bgr8) || frame.sourceImage.pixelFormat !== 'bgr8' || frame.sourceImage.width !== 1920 || frame.sourceImage.height !== 1080)) fail('source-image-identity', 'Measured pixels require an independently reproducible native decoded BGR8 frame SHA256', t)
    const views = frameViews(frame), viewIds = new Set()
    if (!views.length) fail('missing-views', 'Corresponding physical machine has no source view', t)
    for (const view of views) {
      const viewId = view.id
      if (!text(viewId) || viewIds.has(viewId)) fail('view-id', 'View IDs must be nonempty and distinct', t, viewId)
      viewIds.add(viewId); summary.requiredViews++
      const rect = view.rectSourcePixels
      if (!vector(rect, 4) || rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0 || rect[0] + rect[2] > 1920 || rect[1] + rect[3] > 1080 || !['native', 'horizontal-mirror'].includes(view.presentation)) fail('source-viewport', 'Invalid actual source ROI or mirror presentation', t, viewId)
      const camera = view.camera
      if (!camera || camera.status !== 'passed' || !vector(camera.positionMetres, 3) || !vector(camera.quaternion, 4) || Math.abs(Math.hypot(...camera.quaternion) - 1) > 0.002 || !finite(camera.verticalFovDegrees) || camera.verticalFovDegrees <= 0 || camera.verticalFovDegrees >= 179) fail('camera-state', 'Missing/failed/incomplete observed camera', t, viewId)
      const state = view.mechanicalState, input = state?.input
      if (state?.status !== 'observed' || state.visiblePoseCompleteness === 'partial' || !text(state.evidence) || !input || (state.unresolvedInputFields?.length ?? 0)) fail('mechanical-state', 'Corresponding visible mechanics need complete source-observed numeric input', t, viewId)
      if (input) {
        const setup = input.setup
        if (!finite(input.crankTurns) || !vector(input.amplitudes, 20) || input.amplitudes.some(value => value < -1 || value > 1) || !vector(input.phases, 20) || !['small-large', 'medium-medium', 'large-small'].includes(input.gearing) || !finite(input.magnification) || input.magnification <= 0 || !setup || !['meanLineAngleRad', 'platenOffsetM', 'wireFixtureOffsetM', 'coneSwingRad', 'pinionCamRad', 'heldChannelTurns', 'driveCrankOffsetTurns'].every(key => finite(setup[key])) || !(setup.counterHeightM === null || finite(setup.counterHeightM))) fail('mechanical-input', 'Incomplete physical twenty-channel input or setup (footage must state driveCrankOffsetTurns explicitly)', t, viewId)
      }
      for (const override of view.partOverrides ?? []) {
        if (!text(override.partPath) || !['visible', 'hidden'].includes(override.visibility) || (override.worldPositionMetres !== undefined && !vector(override.worldPositionMetres, 3)) || (override.worldQuaternion !== undefined && (!vector(override.worldQuaternion, 4) || Math.abs(Math.hypot(...override.worldQuaternion) - 1) > 0.002))) fail('part-override', 'Disassembly/setup must use qualified native part paths and finite observed poses', t, viewId)
      }
      if (view.anchorWorldMetres || frame.anchorWorldMetres) {
        if (!text(view.anchorPoseEvidence ?? frame.anchorPoseEvidence)) fail('posed-anchor-evidence', 'Posed CAD fitting points require independent mechanical pose evidence', t, viewId)
      }
      const landmarks = frame.landmarks.filter(item => (item.viewId ?? 'main') === viewId)
      const observed = new Set(), fitIds = new Set(), checkIds = new Set(), fitPixels = [], checkPixels = []
      for (const item of landmarks) {
        const anchor = anchors.get(item.anchorId)
        if (!anchor || observed.has(item.anchorId) || !['fit', 'check'].includes(item.role) || item.status !== 'observed' || !vector(item.pixel, 2) || item.pixel[0] < 0 || item.pixel[0] >= 1920 || item.pixel[1] < 0 || item.pixel[1] >= 1080 || !finite(item.uncertaintyPx) || item.uncertaintyPx < 0 || item.uncertaintyPx > PIXEL_LIMIT || !['manual', 'optical-flow', 'image-edge', 'template-match'].includes(item.method)) fail('source-measurement', `Invalid/duplicate/unmeasured source point ${item.anchorId}`, t, viewId)
        observed.add(item.anchorId)
        if (vector(rect, 4) && vector(item.pixel, 2) && (item.pixel[0] < rect[0] || item.pixel[1] < rect[1] || item.pixel[0] >= rect[0] + rect[2] || item.pixel[1] >= rect[1] + rect[3])) fail('landmark-roi', `${item.anchorId} lies outside its physical source view`, t, viewId)
        if (item.role === 'fit') { fitIds.add(item.anchorId); fitPixels.push(item.pixel); summary.fitLandmarks++ }
        if (item.role === 'check') { checkIds.add(item.anchorId); checkPixels.push(item.pixel); summary.checkLandmarks++ }
        if (item.method === 'optical-flow') {
          const evidence = item.trackingEvidence
          const seed = seeds.get(`${evidence?.seedTimeSeconds}/${viewId}/${item.anchorId}`)
          if (anchor?.kind !== 'physical-feature' || !seed || seed.role !== item.role || !finite(evidence?.forwardBackwardErrorPx) || evidence.forwardBackwardErrorPx > 1 || !finite(evidence?.seedPatchCorrelation) || evidence.seedPatchCorrelation < 0.80 || !finite(evidence?.adjacentPatchCorrelation) || evidence.adjacentPatchCorrelation < 0.90) fail('flow-provenance', `${item.anchorId}: no independent physical-feature seed/consistent actual-source track`, t, viewId)
        } else if (item.method === 'template-match') {
          const evidence = item.trackingEvidence
          const seed = seeds.get(`${evidence?.seedTimeSeconds}/${viewId}/${item.anchorId}`)
          if (!seed || seed.role !== item.role || evidence.reacquiredFromActualPixels !== true || !finite(evidence.wholeSourceViewCorrelation) || evidence.wholeSourceViewCorrelation < 0.998 || !finite(evidence.sourcePatchCorrelation) || evidence.sourcePatchCorrelation < 0.97) fail('template-provenance', `${item.anchorId}: independent seed and source-view/source-feature correlations must be retained`, t, viewId)
        } else if (item.method === 'image-edge' && !item.measurementEvidence) fail('edge-provenance', `${item.anchorId}: no actual source edge/search evidence`, t, viewId)
        if ((view.partOverrides ?? []).some(override => override.visibility === 'hidden' && (anchor?.partPath === override.partPath || anchor?.partPath?.startsWith(`${override.partPath}/`)))) fail('hidden-anchor', `${item.anchorId}: physical landmark belongs to a hidden native part`, t, viewId)
      }
      if (fitIds.size < 6 || checkIds.size < 2) fail('independent-check-count', `Need >=6 fitting and >=2 separately measured held-out anchors; observed ${fitIds.size}/${checkIds.size}`, t, viewId)
      if ([...checkIds].some(id => fitIds.has(id)) || checkPixels.some(pixel => fitPixels.some(fit => vector(pixel, 2) && vector(fit, 2) && Math.hypot(pixel[0] - fit[0], pixel[1] - fit[1]) < EPSILON))) fail('fit-check-leakage', 'A held-out anchor/pixel cannot also be a camera-fitting observation', t, viewId)
    }
    for (const item of frame.landmarks) if (!viewIds.has(item.viewId ?? 'main')) fail('unknown-landmark-view', `Unknown view for ${item.anchorId}`, t, item.viewId)
  }
  const present = time => Math.abs(times[nearestPtsIndex(times, time)] - time) <= EPSILON
  summary.integerSecondsRequired = Math.floor(duration) + 1
  for (let second = 0; second <= Math.floor(duration); second++) {
    if (present(second)) summary.integerSecondsPresent++
    else fail('missing-integer-second', `Missing required source second ${second}`, second)
  }
  const changes = new Set([...shots.values()].flatMap(shot => [shot.startSeconds, shot.endSeconds]).filter(time => time < duration))
  for (const time of coverage?.changeTimesSeconds ?? []) {
    if (!finite(time) || time < 0 || time >= duration) fail('change-time', 'Invalid measured source change time', time)
    else changes.add(time)
  }
  summary.changeTimesRequired = changes.size
  for (const time of changes) { if (present(time)) summary.changeTimesPresent++; else fail('missing-change', `Missing source shot/mechanical/camera change ${time}`, time) }
  if (native && allNative && nativeIndices.size !== native.pts.length) fail('missing-native-frame', `All-change census claims every native frame but supplies ${nativeIndices.size}/${native.pts.length}`)
  return summary
}

export async function probeSource(path, expected, { signal } = {}) {
  const observedSha256 = await sha256File(path)
  if (observedSha256 !== expected.sha256) throw new Error(`Source SHA256 mismatch: ${path}`)
  const { stdout } = await runTool('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_format', '-show_frames', '-show_entries', 'stream=width,height,avg_frame_rate,duration:format=duration:frame=best_effort_timestamp_time', '-of', 'json', path], { signal })
  const probe = JSON.parse(stdout), stream = probe.streams?.[0]
  const [numerator, denominator] = (stream?.avg_frame_rate ?? '').split('/').map(Number)
  const fps = numerator / denominator
  const declared = expected.fps
  let declaredFps = typeof declared === 'number' ? declared : declared?.numerator / declared?.denominator
  if (typeof declared === 'string') { const terms = declared.split('/').map(Number); declaredFps = terms.length === 2 ? terms[0] / terms[1] : Number(declared) }
  if (!finite(declaredFps) || Math.abs(declaredFps - fps) > 0.0001) throw new Error(`Actual source frame rate differs from observations: ${fps}/${declaredFps}`)
  const pts = (probe.frames ?? []).map(frame => Number(frame.best_effort_timestamp_time))
  if (stream?.width !== 1920 || stream?.height !== 1080 || !finite(fps) || fps <= 0 || !pts.length || pts.some((value, index) => !finite(value) || (index && value <= pts[index - 1]))) throw new Error(`Invalid actual decoded stream/PTS: ${path}`)
  const durationSeconds = Number(probe.format?.duration)
  if (Math.abs(durationSeconds - expected.durationSeconds) > 0.05) throw new Error(`Actual source duration differs from observations: ${durationSeconds}/${expected.durationSeconds}`)
  return { observedSha256, width: stream.width, height: stream.height, fps, durationSeconds, nativeFrameCount: pts.length, pts }
}

export async function loadReferences(webRoot, referenceRoot, { signal } = {}) {
  const metadata = JSON.parse(await readFile(resolve(referenceRoot, 'evidence/footage-metadata.json'), 'utf8'))
  const records = [], failures = []
  for (const id of VIDEO_IDS) {
    try {
      const data = JSON.parse(await readFile(resolve(webRoot, `content/${id}.observations.json`), 'utf8'))
      const entry = metadata.find(item => item.id === id)
      if (!entry || entry.sha256 !== data.source?.sha256) throw new Error('Measured source identity differs from independent acquisition metadata')
      // Keep paths relocatable without requiring original /tmp directories.
      const suffix = entry.path.split('/videos/')[1]
      if (!suffix) throw new Error('Source metadata lacks a videos-relative private filename')
      const sourcePath = resolve(referenceRoot, 'videos', suffix)
      const native = await probeSource(sourcePath, data.source, { signal })
      const report = inspectReference(data, id, native)
      if (!report.failures.length) report.sourceImageVerification = await verifyFrameImages(sourcePath, data.frames, { signal })
      records.push({ id, data, digest: jsonDigest(data), sourcePath, native, report })
    } catch (error) { failures.push({ videoId: id, code: 'source-prerequisite', detail: error.message }) }
  }
  return { records, failures }
}

export function errorStats(values) {
  if (!values.length) return { count: 0, maxPx: null, rmsPx: null }
  let maximum = 0, sumSquares = 0
  for (const value of values) { maximum = Math.max(maximum, value); sumSquares += value * value }
  return { count: values.length, maxPx: maximum, rmsPx: Math.sqrt(sumSquares / values.length) }
}

/** Re-decode genuine private footage; compare raw pixels, not hashes authored by the app. */
export async function verifyFrameImages(sourcePath, frames, { signal, timeoutMs = 180_000 } = {}) {
  const images = new Map()
  for (const frame of frames) {
    if (!(frame.landmarks?.length)) continue
    const image = frame.sourceImage
    if (!image || !Number.isInteger(image.frameIndex) || !hash(image.sha256Bgr8)) throw new Error('Missing actual decoded source-image identity')
    if (images.has(image.frameIndex) && images.get(image.frameIndex) !== image.sha256Bgr8) throw new Error(`Conflicting actual source hashes at native frame ${image.frameIndex}`)
    images.set(image.frameIndex, image.sha256Bgr8)
  }
  if (!images.size) return { count: 0, frameHashDigest: null, reason: 'No corresponding physical source view; no source pixels claimed' }
  const indices = [...images.keys()].sort((a, b) => a - b), spans = []
  let start = indices[0], last = start
  for (const index of indices.slice(1)) {
    if (index === last + 1) last = index
    else { spans.push(start === last ? `eq(n,${start})` : `between(n,${start},${last})`); start = last = index }
  }
  spans.push(start === last ? `eq(n,${start})` : `between(n,${start},${last})`)
  const directory = await mkdtemp(join(tmpdir(), 'harmonic-verify-framehash-'))
  try {
    const filter = join(directory, 'select.txt')
    await writeFile(filter, `select='${spans.join('+')}'`)
    const { stdout } = await runTool('ffmpeg', ['-v', 'error', '-threads', '2', '-i', sourcePath, '-an', '-filter_script:v', filter, '-frames:v', String(indices.length), '-fps_mode', 'passthrough', '-pix_fmt', 'bgr24', '-f', 'framehash', '-hash', 'sha256', 'pipe:1'], { signal, timeoutMs })
    const decoded = stdout.toString().split('\n').filter(line => line.trim() && !line.startsWith('#')).map(line => line.split(',').map(value => value.trim()))
    if (decoded.length !== indices.length) throw new Error(`Actual source framehash coverage ${decoded.length}/${indices.length}`)
    const digest = createHash('sha256')
    for (let i = 0; i < indices.length; i++) {
      const row = decoded[i], index = indices[i], actual = row[5]
      if (row.length !== 6 || Number(row[4]) !== 1920 * 1080 * 3 || actual !== images.get(index)) throw new Error(`Actual source BGR8 hash mismatch at frame ${index}: ${actual}/${images.get(index)}`)
      digest.update(`${index}:${actual}\n`)
    }
    return { count: indices.length, frameHashDigest: digest.digest('hex'), pixelFormat: 'bgr8', decoder: 'ffmpeg native select; passthrough timestamps; SHA256 over 6220800 actual BGR bytes' }
  } finally { await rm(directory, { recursive: true, force: true }) }
}
