#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { VIDEO_IDS, MODEL_SHA256, MODEL_COMMIT, CLOCK_LIMIT, probeSource, verifyFrameImages, claimedSourceImages, nearestPtsIndex, sourceNeedsMachine, frameViews, sourceLayoutForViews, sourcePointUnmasked, jsonDigest } from './verify-reference.mjs'
import { distManifest, serveDist } from './verify-server.mjs'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const STAGES = [50, 20, 10, 5]
const VIDEO_SLUGS = ['intro-history', 'synthesis', 'analysis', 'operation', 'machine-spin', 'rocker-arms']
const SOURCE_HASHES = [
  '595b0ec7b1e1a0b3523d72d33f6e0950bd97dda5ab7032bf91c3e5b9fb7d225d',
  'a7ac177e0c6eecdfe9b5817716eeb570c43b4590888f007c2cb6de8229ce1725',
  '5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52',
  'ec0dcdef13700bab2f318f74f9be5591c89b409ae5c5028be468b727284410e3',
  '52caae2e9d617934ae9eb80d6a3d2b1679b31eb9c71e9da741152e84e2d68505',
  '351bdf54ae64475645ee4904df43af979629c7dab62c47765276faea05adbf4a',
]
const finite = value => typeof value === 'number' && Number.isFinite(value)
const point = value => Array.isArray(value) && value.length === 2 && value.every(finite)
const assert = (condition, reason) => { if (!condition) throw new Error(reason) }
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const delay = ms => new Promise(done => setTimeout(done, ms))
const maximumField = (rows, field) => rows.reduce((maximum, row) => finite(row[field]) ? Math.max(maximum ?? 0, row[field]) : maximum, null)
const HELP = `Usage: npm --prefix web run verify:sync -- [--stage 50|20|10|5] [--video <id|slug>] [--from seconds --to seconds | --times t,t,...] [--player local|youtube|both] [--headless|--headed] [--output directory]\nDefault: ALL SIX videos, final 5% of the 1920px frame width = 96px, timing <=0.5s, headless Chromium.\nStages 50/20/10/5 are ERROR tolerances (960/384/192/96px), never coverage fractions.\nPer-video and time-scoped runs measure available samples without an all-six preflight. A time-scoped report is partial, NEVER a whole-video stage pass. Stage 5 requires actual official YouTube playback/audio/compact checks; coarse stages default to byte-identical local original playback.\nRequires built dist, original MP4s in HARMONIC_REFERENCE_ROOT/videos (default web/.vite/reference-root), ffprobe/ffmpeg and Playwright Chromium. No attempt cap. Old certification code remains in git history; retained private diagnostic evidence is unchanged.\nExamples:\n  npm --prefix web run verify:sync -- --stage 50 --video analysis --times 117,118,119\n  npm --prefix web run verify:sync -- --stage 20 --video machine-spin\n  npm --prefix web run verify:sync\n`

export function parseOptions(args) {
  const options = { stage: 5, videos: [], from: null, to: null, times: null, player: null, headed: process.env.HARMONIC_HEADLESS === '0', output: null }
  for (let index = 0; index < args.length; index++) {
    const option = args[index]
    if (option === '--help') return { help: true }
    if (option === '--headed') { options.headed = true; continue }
    if (option === '--headless') { options.headed = false; continue }
    assert(['--stage', '--video', '--from', '--to', '--times', '--player', '--output'].includes(option), `Unknown option ${option}`)
    const value = args[++index]
    assert(value !== undefined && !value.startsWith('--'), `${option} requires a value`)
    if (option === '--stage') options.stage = Number(value)
    else if (option === '--video') {
      const videoIndex = VIDEO_IDS.includes(value) ? VIDEO_IDS.indexOf(value) : VIDEO_SLUGS.indexOf(value)
      assert(videoIndex >= 0, `Unknown retained video ${value}`)
      if (!options.videos.includes(VIDEO_IDS[videoIndex])) options.videos.push(VIDEO_IDS[videoIndex])
    } else if (option === '--times') {
      assert(value.split(',').every(term => term.trim().length > 0), '--times cannot contain empty sample times')
      options.times = value.split(',').map(Number)
    }
    else if (option === '--from') options.from = Number(value)
    else if (option === '--to') options.to = Number(value)
    else options[option.slice(2)] = value
  }
  assert(STAGES.includes(options.stage), 'Stage must be one of 50,20,10,5')
  for (const key of ['from', 'to']) assert(options[key] === null || (finite(options[key]) && options[key] >= 0), `${key} must be finite and nonnegative`)
  assert(options.from === null || options.to === null || options.from <= options.to, '--from must not exceed --to')
  assert(options.times === null || (options.times.length > 0 && options.times.every(time => finite(time) && time >= 0)), '--times needs finite nonnegative source times')
  assert(options.times === null || (options.from === null && options.to === null), '--times cannot be combined with --from/--to')
  options.player ??= options.stage === 5 ? 'both' : 'local'
  assert(['local', 'youtube', 'both'].includes(options.player), '--player must be local, youtube or both')
  if (!options.videos.length) options.videos = [...VIDEO_IDS]
  options.scoped = options.times !== null || options.from !== null || options.to !== null
  return options
}

function nearestFrame(frames, time, field = 'timeSeconds') {
  let low = 0, high = frames.length
  while (low < high) { const middle = (low + high) >>> 1; if (frames[middle][field] < time) low = middle + 1; else high = middle }
  if (!low) return frames[0]
  if (low === frames.length) return frames[low - 1]
  return time - frames[low - 1][field] <= frames[low][field] - time ? frames[low - 1] : frames[low]
}

export function sourcePtsInShot(frame, shot) {
  return Boolean(shot && finite(frame.decodedTimeSeconds) && shot.startSeconds <= frame.decodedTimeSeconds && frame.decodedTimeSeconds < shot.endSeconds)
}

/** Renames need identical declared source support; equal-sized crossfade layers are ambiguous. */
function compactSourceViewId(original, sourceViewId, views) {
  if (views.some(view => view.id === sourceViewId)) return { viewId: sourceViewId }
  const sourceView = frameViews(original).find(view => view.id === sourceViewId)
  if (!sourceView) return { reason: `Original source view ${sourceViewId} has no declared layout for compact-view mapping` }
  if (!Array.isArray(sourceView.rectSourcePixels) || sourceView.rectSourcePixels.length !== 4 || !sourceView.rectSourcePixels.every(finite)) return { reason: `Original source view ${sourceViewId} has no measured support for compact-view mapping` }
  const candidates = views.filter(view => Array.isArray(view.rectSourcePixels) && jsonDigest(view.rectSourcePixels) === jsonDigest(sourceView.rectSourcePixels)
    && view.presentation === sourceView.presentation
    && (view.composite?.mode ?? 'opaque') === (sourceView.composite?.mode ?? 'opaque'))
  const sourcePeers = frameViews(original).filter(view => Array.isArray(view.rectSourcePixels) && jsonDigest(view.rectSourcePixels) === jsonDigest(sourceView.rectSourcePixels)
    && view.presentation === sourceView.presentation && (view.composite?.mode ?? 'opaque') === (sourceView.composite?.mode ?? 'opaque'))
  if (sourcePeers.length !== 1) return { reason: `Ambiguous original source view ${sourceViewId} mapping would merge distinct explicit source perspectives` }
  if (candidates.length !== 1) return { reason: `${candidates.length ? 'Ambiguous' : 'Unavailable'} original source view ${sourceViewId} mapping to declared compact views` }
  return { viewId: candidates[0].id, sourceViewId, evidence: 'Identical original/compact source ROI, presentation and compositing mode' }
}

function compactSourceViewRequirement(original, sourceViewId, views) {
  const sourceView = original.views?.find(view => view.id === sourceViewId)
  const declared = views.filter(view => view.sourceViewIds?.includes(sourceViewId))
  if (sourceView && Array.isArray(sourceView.rectSourcePixels) && declared.length > 1 && declared.every(view => Array.isArray(view.sourceViewIds) && view.sourceViewIds.length === 1
    && typeof view.sourceViewMappingEvidence === 'string' && view.sourceViewMappingEvidence.trim()
    && jsonDigest(view.rectSourcePixels) === jsonDigest(sourceView.rectSourcePixels) && view.presentation === sourceView.presentation
    && view.composite?.mode === 'crossfade' && view.composite.groupId === declared[0].composite?.groupId
    && typeof view.composite.imageLayerId === 'string' && view.composite.imageLayerId.trim())
    && new Set(declared.map(view => view.composite.imageLayerId)).size === declared.length) {
    return { viewIds: declared.map(view => view.id), evidence: declared.map(view => view.sourceViewMappingEvidence) }
  }
  const mapping = compactSourceViewId(original, sourceViewId, views)
  return { ...mapping, viewIds: [mapping.viewId ?? sourceViewId] }
}

function compactSourceLandmarks(original, views, observations = original.landmarks ?? []) {
  const landmarks = [], unavailable = []
  for (const observed of observations) {
    const sourceViewId = observed.viewId ?? 'main', mapping = compactSourceViewId(original, sourceViewId, views)
    if (!mapping.viewId) { unavailable.push({ anchorId: observed.anchorId, viewId: sourceViewId, reason: mapping.reason }); continue }
    landmarks.push(mapping.sourceViewId ? { ...observed, viewId: mapping.viewId, originalViewId: sourceViewId, viewMappingEvidence: mapping.evidence } : observed)
  }
  return { landmarks, unavailable }
}

/** Source census is retained separately from authored camera/input candidates. */
export function sourceCensus(observations, track, native, options) {
  const times = new Map(), sourceShots = track.shots ?? observations.shots
  const originalShots = new Map(observations.shots.map(shot => [shot.id, shot]))
  const compactShots = new Map(sourceShots.map(shot => [shot.id, shot]))
  const add = (time, reason) => {
    if (!finite(time) || time < 0 || time >= native.durationSeconds) return
    const key = time.toFixed(6), row = times.get(key) ?? { timeSeconds: time, reasons: [] }
    if (!row.reasons.includes(reason)) row.reasons.push(reason)
    times.set(key, row)
  }
  for (let time = 0; time < native.durationSeconds; time++) add(time, 'every-second')
  for (const time of track.coverage?.changeTimesSeconds ?? []) add(time, 'authored-change-point')
  for (const shot of sourceShots) { add(shot.startSeconds, 'shot-start'); add(shot.endSeconds, 'shot-end') }
  for (const frame of track.frames) add(frame.timeSeconds, 'authored-sample')
  // Preserve real view membership/cut changes, not every exposure of continuous motion.
  let precedingLayout = null
  const framesByShot = new Map()
  for (const frame of observations.frames) {
    const layout = JSON.stringify([frame.shotId, frame.classification, frame.sourceMachineRequirement, frame.views?.map(view => [view.id, view.presentation])])
    if (precedingLayout !== layout) add(frame.timeSeconds, 'retained-layout-change')
    precedingLayout = layout
    const shot = compactShots.get(frame.shotId) ?? originalShots.get(frame.shotId)
    if (!sourcePtsInShot(frame, shot)) continue
    if (!framesByShot.has(frame.shotId)) framesByShot.set(frame.shotId, [])
    framesByShot.get(frame.shotId).push(frame)
  }
  for (const pool of framesByShot.values()) pool.sort((a, b) => a.decodedTimeSeconds - b.decodedTimeSeconds)
  for (let index = 0; index < track.frames.length - 1; index++) {
    const from = track.frames[index], to = track.frames[index + 1], gap = to.timeSeconds - from.timeSeconds
    if (from.shotId !== to.shotId || gap < 0.125 || gap > 2) continue
    const pool = (framesByShot.get(from.shotId) ?? []).filter(frame => frame.decodedTimeSeconds > from.timeSeconds + 1e-6
      && frame.decodedTimeSeconds < to.timeSeconds - 1e-6 && frame.landmarks?.some(item => item.status === 'observed' && point(item.pixel)))
    const original = nearestFrame(pool, (from.timeSeconds + to.timeSeconds) / 2, 'decodedTimeSeconds')
    // Extra interpolation probes are diagnostic, at actual observed exposures,
    // not arithmetic midpoints that create an uncollectable mandatory oracle.
    if (original) add(original.decodedTimeSeconds, 'mid-interval')
  }
  for (const time of options.times ?? []) add(time, 'requested-sample')
  const rows = [...times.values()].sort((a, b) => a.timeSeconds - b.timeSeconds).map(row => {
    const diagnosticOnly = row.reasons.every(reason => reason === 'mid-interval')
    const shot = sourceShots.find(shot => shot.startSeconds <= row.timeSeconds && row.timeSeconds < shot.endSeconds)
    const original = nearestFrame(framesByShot.get(shot?.id) ?? [], row.timeSeconds, 'decodedTimeSeconds')
    const authored = nearestFrame(track.frames, row.timeSeconds)
    let left = -1, right = track.frames.length
    while (left + 1 < right) { const middle = (left + right) >>> 1; if (track.frames[middle].timeSeconds <= row.timeSeconds) left = middle; else right = middle }
    const from = track.frames[left], to = track.frames[left + 1]
    const governing = from?.shotId === shot?.id ? from : authored?.shotId === shot?.id ? authored : null
    const originalRequired = original ? sourceNeedsMachine(original, originalShots.get(original.shotId)) : !shot || shot.hasCorrespondingMachine !== false && shot.classification !== 'non-machine'
    const compactRequired = governing ? sourceNeedsMachine(governing, shot) : originalRequired
    const required = originalRequired || compactRequired
    // frameViews' implicit main is a legacy convenience, not an independently
    // declared source perspective. All explicit source views remain required.
    const sourceViewMappings = originalRequired && original?.views ? original.views.map(view => ({ originalViewId: view.id, ...compactSourceViewRequirement(original, view.id, governing?.views ?? []) })) : []
    const expectedViewIds = [...new Set([...sourceViewMappings.flatMap(mapping => mapping.viewIds), ...(compactRequired ? governing?.views?.map(view => view.id) ?? [] : [])])]
    const tolerance = row.reasons.includes('every-second') ? 1e-5 : 1 / native.fps + 0.001
    let frame = authored && Math.abs(authored.timeSeconds - row.timeSeconds) <= tolerance && authored.shotId === shot?.id ? authored : null
    let unavailableReason = frame ? null : 'Missing authored sample at retained every-second/change-point source time'
    const between = from && to && from.shotId === shot?.id && to.shotId === shot.id && row.timeSeconds > from.timeSeconds + 1e-6 && row.timeSeconds < to.timeSeconds - 1e-6
    if (between && (row.reasons.includes('mid-interval') || row.reasons.includes('requested-sample'))) {
      if (original && original.decodedTimeSeconds > from.timeSeconds && original.decodedTimeSeconds < to.timeSeconds
        && Math.abs(original.decodedTimeSeconds - row.timeSeconds) <= 1 / native.fps + 0.001) {
        const mapped = compactSourceLandmarks(original, from.views ?? [])
        frame = { timeSeconds: row.timeSeconds, decodedTimeSeconds: original.decodedTimeSeconds, shotId: shot.id, classification: original.classification, landmarks: mapped.landmarks, viewMappingUnavailable: mapped.unavailable, views: from.views ?? [], measuredInterpolation: true, interpolationInterval: [from.timeSeconds, to.timeSeconds], ...(original.sourceImage ? { sourceImage: original.sourceImage } : {}) }
        unavailableReason = null
      } else { frame = null; unavailableReason = 'No independent same-shot source observation within one native frame of the interpolation sample; oracle pixels are never interpolated' }
    }
    if (frame && finite(frame.decodedTimeSeconds) && !sourcePtsInShot(frame, shot)) { frame = null; unavailableReason = 'Observed source PTS lies outside its own half-open source shot' }
    if (frame && !frame.measuredInterpolation && frame.landmarks?.some(item => !frame.views?.some(view => view.id === (item.viewId ?? 'main')))) {
      const source = nearestFrame(framesByShot.get(frame.shotId) ?? [], frame.decodedTimeSeconds, 'decodedTimeSeconds')
      if (source && Math.abs(source.decodedTimeSeconds - frame.decodedTimeSeconds) <= 0.001) {
        const mapped = compactSourceLandmarks(source, frame.views ?? [], frame.landmarks)
        frame = { ...frame, landmarks: mapped.landmarks, viewMappingUnavailable: mapped.unavailable }
      } else {
        frame = { ...frame, viewMappingUnavailable: [{ reason: 'Original landmark view identity has no same-exposure source layout for compact-view mapping' }] }
      }
    }
    return { ...row, diagnosticOnly, required, sourceShotId: shot?.id ?? original?.shotId ?? null, originalTimeSeconds: original?.timeSeconds ?? null, expectedViewIds, sourceViewMappings, frame, unavailableReason }
  })
  const selected = rows.filter(row => options.times ? options.times.some(time => Math.abs(time - row.timeSeconds) < 1e-5) : (options.from === null || row.timeSeconds >= options.from) && (options.to === null || row.timeSeconds <= options.to))
  for (const time of options.times ?? []) if (time >= native.durationSeconds) selected.push({ timeSeconds: time, reasons: ['requested-sample'], diagnosticOnly: false, required: true, expectedViewIds: [], frame: null, unavailableReason: 'Requested time is outside the original source duration' })
  return { rows, selected }
}

async function loadRecord(id, referenceRoot, signal) {
  const track = JSON.parse(await readFile(resolve(WEB_ROOT, `content/${id}.source-track.json`), 'utf8'))
  const observations = JSON.parse(await readFile(resolve(WEB_ROOT, `content/${id}.observations.json`), 'utf8'))
  assert(track.kind === 'compact-source-track' && track.schemaVersion === 1, 'Expected the compact source-track contract')
  const expectedHash = SOURCE_HASHES[VIDEO_IDS.indexOf(id)]
  assert(track.source?.videoId === id && track.source.sha256 === expectedHash && observations.source?.sha256 === expectedHash, 'Compact/source census identity differs from retained original MP4 SHA256')
  assert(track.model?.sha256 === MODEL_SHA256 && track.model.sourceCommit === MODEL_COMMIT && track.model.units === 'metres', 'Compact track must use the full unchanged native CAD model')
  assert(Array.isArray(track.frames) && track.frames.length && track.frames.every((frame, index) => finite(frame.timeSeconds) && (finite(frame.decodedTimeSeconds) || (frame.decodedTimeSeconds === null && frame.sourceSampleUnavailable === true && !frame.views?.length && !frame.landmarks?.length && !frame.sourceImage)) && (!index || frame.timeSeconds > track.frames[index - 1].timeSeconds)), 'Compact samples must have finite increasing source times and native PTS, or explicit unavailable source-clock rows')
  assert(Array.isArray(track.anchors) && new Set(track.anchors.map(anchor => anchor.id)).size === track.anchors.length, 'Compact native anchors must have unique identities')
  const sourcePath = resolve(referenceRoot, 'videos', `${id}.mp4`)
  const native = await probeSource(sourcePath, track.source, { signal })
  return { id, track, observations, sourcePath, native, digest: jsonDigest(track) }
}

/** A bad diagnostic identity cannot erase independent successful exposures in the same decode batch. */
export function diagnosticReplayOutcome(imageDigests, result) {
  const verified = new Set(result.verifiedImageDigests ?? []), failures = new Map((result.imageFailures ?? []).map(item => [item.imageDigest, item.reason]))
  const unavailable = imageDigests.filter(identity => failures.has(identity) || !verified.has(identity))
  return unavailable.length
    ? { status: 'unavailable', reason: unavailable.map(identity => `${identity}: ${failures.get(identity) ?? 'Declared diagnostic source-image identity was not independently verified'}`).join('; ') }
    : { status: 'passed', proof: 'Additional declared diagnostic source-image identities independently replayed' }
}

async function replayCensusImages(record, census, staticControls, video, signal) {
  const source = record.track.source, replayOptions = { signal, native: record.native, source }
  const mandatoryData = { frames: census.selected.filter(row => !row.diagnosticOnly).map(row => row.frame).filter(Boolean), staticPhaseImages: staticControls.phaseImages, source }
  const verifiedImages = new Set()
  try {
    video.source.imageReplay = await verifyFrameImages(record.sourcePath, mandatoryData, replayOptions)
    for (const { image } of claimedSourceImages(mandatoryData)) verifiedImages.add(jsonDigest(image))
  } catch (error) { video.failures.push({ code: 'source-image-replay', reason: error.message }) }
  const rows = census.selected.filter(row => row.diagnosticOnly && row.frame), additionalImages = new Map(), additionalRows = []
  const diagnostics = { status: rows.length ? 'passed' : 'not-required', additionalDeclaredIdentities: 0, reusedSamples: 0, unavailableSamples: 0, failures: [] }
  const unavailable = (row, reason) => {
    row.sourceImageReplay = { status: 'unavailable', reason }
    row.frame = null
    row.unavailableReason = reason
    diagnostics.failures.push({ timeSeconds: row.timeSeconds, reason })
  }
  for (const row of rows) {
    const frame = row.frame, image = frame.sourceImage, nativePts = record.native.pts[image?.frameIndex]
    if (!image || !finite(nativePts) || !finite(frame.decodedTimeSeconds) || Math.abs(nativePts - frame.decodedTimeSeconds) > 0.001) {
      unavailable(row, 'Diagnostic exposure lacks a replayable source image bound to its actual native PTS')
      continue
    }
    const declared = claimedSourceImages({ frames: [frame] }), extra = declared.filter(({ image }) => !verifiedImages.has(jsonDigest(image)))
    if (!extra.length) {
      row.sourceImageReplay = { status: 'passed', proof: 'Exact declared source-image identities already independently replayed with mandatory samples' }
      diagnostics.reusedSamples++
    } else {
      for (const { image } of extra) additionalImages.set(jsonDigest(image), image)
      additionalRows.push({ row, imageDigests: extra.map(({ image }) => jsonDigest(image)) })
    }
  }
  diagnostics.additionalDeclaredIdentities = additionalImages.size
  if (additionalImages.size) {
    try {
      // Replay only new declared identities, with the existing decoder. Review
      // separately checks each diagnostic sample's exact source PTS/image index.
      diagnostics.result = await verifyFrameImages(record.sourcePath, { frames: [], diagnosticImages: [...additionalImages.values()], source }, { ...replayOptions, failureMode: 'attribute' })
      for (const { row, imageDigests } of additionalRows) {
        const outcome = diagnosticReplayOutcome(imageDigests, diagnostics.result)
        if (outcome.status === 'passed') row.sourceImageReplay = outcome
        else unavailable(row, `Diagnostic source image replay unavailable: ${outcome.reason}`)
      }
    } catch (error) {
      for (const { row } of additionalRows) unavailable(row, `Diagnostic source image replay unavailable: ${error.message}`)
    }
  }
  diagnostics.unavailableSamples = rows.filter(row => !row.frame).length
  if (diagnostics.unavailableSamples) diagnostics.status = 'unavailable'
  video.source.diagnosticImageReplay = diagnostics
}

/** Admit only the retained Spin source family, never a free-form static assertion. */
async function staticSourceControls(record) {
  if (record.id !== 'XPQwKRt4Y2k') return { shots: new Map(), phaseImages: [], diagnostics: [] }
  const shots = new Map(), diagnostics = [], phaseImages = []
  const allowed = ['opening-fade', 'whole-machine', 'whole-machine-credit', 'whole-closeup-crossfade', 'closeup-sweep']
  for (const family of record.track.sourceMotionFamilies ?? []) {
    try {
      const rig = record.observations.sourceCameraRigs?.find(rig => rig.id === family.id)
      assert(family.kind === 'retained-source-photographic-rig' && family.id === 'spin-photographic-71-phase-loop' && family.videoId === record.id && family.sourceSha256 === record.native.observedSha256, 'Static source family is not the retained Spin photographic rig')
      assert(rig && rig.phaseCount === 71 && jsonDigest(family.phaseImages) === jsonDigest(rig.phaseImages), 'Static family reference photos differ from the71 retained independent source-image identities')
      const evidence = rig.independentLoopEvidence
      assert(evidence?.sourceSha256 === family.sourceSha256 && evidence.uniqueImageCount === 71 && family.independentLoopEvidence?.sourceSha256 === evidence.sourceSha256 && jsonDigest(family.independentLoopEvidence.periodPixelComparison) === jsonDigest(evidence.periodPixelComparison), 'Static family lacks the retained source-only period/adjacent-phase controls')
      assert(Array.isArray(family.shotIds) && family.shotIds.length === allowed.length && allowed.every(id => family.shotIds.includes(id)), 'Static source family cannot exempt montage/endcard or unrelated operation shots')
      const mapPath = resolve(WEB_ROOT, '.vite/verification-output/spin-witness/rig-replay/actual-phase-map.json')
      const bytes = await readFile(mapPath), map = JSON.parse(bytes)
      assert(digest(bytes) === family.independentSourcePhaseMap?.sha256 && map.rigId === rig.id && map.sourceFrameMap?.length === family.independentSourcePhaseMap.sourceExposureIdentityCount, 'Independent actual-source phase-map identity differs from declared controls')
      assert(jsonDigest(map.references) === jsonDigest(rig.phaseImages) && map.sourceFrameMap.every(row => row.independentPeriodIndexAgreement === true && row.sourceImage?.sourceSha256 === family.sourceSha256 && jsonDigest(row.referenceSourceImage) === jsonDigest(rig.phaseImages[row.referencePhaseIndex]?.sourceImage) && Math.abs(record.native.pts[row.frameIndex] - row.nativePtsSeconds) <= 0.001), 'Independent source-exposure/phase controls are unavailable or disagree')
      const fixed = new Set(record.track.anchors.filter(anchor => anchor.motion === 'fixed').map(anchor => anchor.id))
      assert(Array.isArray(family.fixedCheckAnchorIds) && new Set(family.fixedCheckAnchorIds).size >= 2 && family.fixedCheckAnchorIds.every(id => fixed.has(id)), 'Static source family has no distributed actual fixed CHECK correspondences')
      phaseImages.push(...rig.phaseImages)
      for (const shot of record.track.shots.filter(shot => allowed.includes(shot.id))) {
        const original = record.observations.shots.find(original => original.id === shot.id), claim = shot.internalMotionSourceEvidence
        assert(original && Math.abs(shot.startSeconds - original.startSeconds) <= 1e-6 && Math.abs(shot.endSeconds - original.endSeconds) <= 1e-6 && shot.internalMechanismMotion === 'static' && claim?.familyId === family.id && claim.kind === family.kind && claim.sourceSha256 === family.sourceSha256 && claim.independentSourcePhaseMapSha256 === family.independentSourcePhaseMap.sha256 && jsonDigest(claim.phaseImageFrameIndices) === jsonDigest(rig.phaseImages.map(phase => phase.sourceImage.frameIndex)), `Static source shot controls/interval differ for ${shot.id}`)
        shots.set(shot.id, { status: 'source-controls-verified', familyId: family.id, sourceSha256: family.sourceSha256, independentSourcePhaseMapSha256: family.independentSourcePhaseMap.sha256, actualSourceExposures: map.sourceFrameMap.length, fixedCheckAnchorIds: family.fixedCheckAnchorIds })
      }
    } catch (error) { diagnostics.push({ familyId: family.id, reason: error.message }) }
  }
  return { shots, phaseImages, diagnostics }
}

async function snapshot(page) { return page.evaluate(() => window.harmonicAnalyzer.snapshot()) }
function requireModel(actual, id) {
  assert(actual.videoId === id && actual.playerVideoId === id, 'Rendered route/player identity mismatch')
  assert(actual.modelState === 'ready' && !actual.missingBindings?.length, 'Full native model is unavailable or has unresolved bindings')
  const provenance = actual.modelProvenance
  assert(provenance?.identity === 'matched' && provenance.observedSha256 === MODEL_SHA256 && provenance.expectedSha256 === MODEL_SHA256 && provenance.sourceCommit === MODEL_COMMIT, 'Actual model bytes/source commit mismatch')
  assert(actual.physics?.springForcesN?.length === 20 && actual.physics.springForcesN.every(value => finite(value) && value >= 0) && actual.physics.springLengthsM?.length === 20 && actual.physics.springLengthsM.every(value => finite(value) && value > 0) && finite(actual.physics.equilibriumResidualNm), 'Actual native physical solve is unavailable')
}
async function openRoute(page, url, record, player) {
  const route = new URL(url)
  route.searchParams.set('video', record.id); route.searchParams.set('verify', '1')
  if (player === 'local') route.searchParams.set('referenceMedia', '1')
  const response = await page.goto(route.href, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  assert(response?.ok(), `Built route returned HTTP ${response?.status()}`)
  await page.waitForFunction(id => window.harmonicAnalyzer?.snapshot().videoId === id && window.harmonicAnalyzer.snapshot().modelState !== 'loading', record.id, { timeout: 120_000 })
  await page.waitForFunction(() => !document.querySelector('#pause-video')?.disabled, undefined, { timeout: 30_000 })
  const actual = await snapshot(page)
  requireModel(actual, record.id)
  const data = await page.evaluate(() => window.harmonicAnalyzer.compactData())
  assert(jsonDigest(data) === record.digest, 'Built runtime compact track differs from the measured content file; rebuild first')
  const selectors = await page.locator('#videos a').evaluateAll(links => links.map(link => new URL(link.href).searchParams.get('video')))
  assert(selectors.length === 6 && new Set(selectors).size === 6, 'All six retained direct video routes must remain available')
  if (player === 'local') {
    await page.locator('#video-player video').waitFor({ state: 'visible', timeout: 30_000 })
    const src = await page.locator('#video-player video').getAttribute('src')
    assert(new URL(src, route).pathname === `${new URL(url).pathname}reference-media/${record.id}.mp4`, 'Local player is not using the retained original MP4 route')
    return { route: route.href, frame: page, selector: '#video-player video', player }
  }
  const iframe = page.locator('#video-player iframe')
  await iframe.waitFor({ state: 'visible', timeout: 30_000 })
  const src = new URL(await iframe.getAttribute('src'))
  assert(/(^|\.)youtube(?:-nocookie)?\.com$/.test(src.hostname) && src.pathname === `/embed/${record.id}` && src.searchParams.get('controls') !== '0' && src.searchParams.get('mute') !== '1', 'Official original YouTube embed/controls/audio are not intact')
  const frame = await (await iframe.elementHandle()).contentFrame()
  assert(frame, 'Official YouTube frame unavailable')
  return { route: route.href, frame, selector: '#movie_player video.html5-main-video', player }
}
async function media(embed) {
  return embed.frame.evaluate(selector => {
    const video = document.querySelector(selector), player = document.querySelector('#movie_player')
    return { present: video instanceof HTMLVideoElement, paused: video?.paused, seeking: video?.seeking, ended: video?.ended, mediaTime: video?.currentTime, duration: video?.duration, muted: video?.muted, volume: video?.volume, readyState: video?.readyState, width: video?.videoWidth, height: video?.videoHeight, adShowing: !!player?.classList.contains('ad-showing'), error: video?.error?.message ?? document.querySelector('.ytp-error-content-wrap')?.textContent?.trim() ?? null }
  }, embed.selector)
}
function requireMedia(actual, record) {
  assert(actual.present && !actual.error && !actual.adShowing && actual.readyState >= 2 && actual.width > 0 && actual.height > 0 && finite(actual.mediaTime), `Actual original media has no decoded source content: ${JSON.stringify(actual)}`)
  assert(finite(actual.duration) && Math.abs(actual.duration - record.native.durationSeconds) <= 1, 'Actual player duration differs from retained source; ads/placeholders cannot pass')
}
async function pause(page, embed) {
  const actual = await snapshot(page)
  if (['playing', 'buffering'].includes(actual.playerState)) await page.locator('#pause-video').click()
  await page.waitForFunction(() => window.harmonicAnalyzer.snapshot().playerState === 'paused', undefined, { timeout: 20_000 })
  const before = await media(embed); await delay(300); const after = await media(embed)
  assert(before.paused && after.paused && finite(before.mediaTime) && Math.abs(after.mediaTime - before.mediaTime) <= 0.1, 'Pause must stop the actual original media clock')
}
/** Independently observes native seeking/seeked AFTER the bridge commands a seek. */
export function seekSettlement(observed, target, tolerance) {
  if (!observed?.sameElement) return { fatal: 'Observed original media element was replaced/detached' }
  if (observed.now.error || observed.events.some(event => event.type === 'error')) return { fatal: 'Actual original media failed during seek' }
  const onTarget = time => finite(time) && Math.abs(time - target) <= tolerance
  const settled = observed.now.paused && !observed.now.seeking && observed.now.readyState >= 2 && onTarget(observed.now.mediaTime)
  const lastSeeking = observed.events.findLastIndex(event => event.type === 'seeking')
  if (lastSeeking >= 0) return { done: settled && onTarget(observed.events[lastSeeking].mediaTime) && observed.events.slice(lastSeeking + 1).some(event => event.type === 'seeked'), proof: 'native-seeking-then-seeked-after-command' }
  return { done: settled && observed.pre.paused && !observed.pre.seeking && observed.pre.readyState >= 2 && onTarget(observed.pre.mediaTime), proof: 'already-decoded-same-time-no-op' }
}
async function observedSeek(embed, target, command, fps) {
  assert(finite(target), 'Source sample PTS is unavailable')
  await embed.frame.evaluate(selector => {
    const video = document.querySelector(selector)
    if (!(video instanceof HTMLVideoElement)) throw new Error('Actual original media element is unavailable')
    window.__harmonicCompactSeek?.detach()
    const read = () => ({ mediaTime: video.currentTime, paused: video.paused, seeking: video.seeking, readyState: video.readyState, error: video.error?.message ?? null })
    const events = [], pre = read(), types = ['seeking', 'seeked', 'error']
    const record = event => events.push({ type: event.type, ...read() })
    for (const type of types) video.addEventListener(type, record)
    window.__harmonicCompactSeek = { video, pre, events, read, detach() { for (const type of types) video.removeEventListener(type, record); delete window.__harmonicCompactSeek } }
  }, embed.selector)
  try {
    await command()
    const deadline = Date.now() + 15_000
    for (;;) {
      const observed = await embed.frame.evaluate(selector => {
        const observer = window.__harmonicCompactSeek
        if (!observer) return null
        return { sameElement: observer.video === document.querySelector(selector) && observer.video.isConnected, pre: observer.pre, events: observer.events.slice(), now: observer.read() }
      }, embed.selector)
      const verdict = seekSettlement(observed, target, 0.5 / fps + 0.005)
      assert(!verdict.fatal, verdict.fatal)
      if (verdict.done) return { proof: verdict.proof, targetSourcePtsSeconds: target, preMediaTime: observed.pre.mediaTime, settledMediaTime: observed.now.mediaTime, events: observed.events.map(event => event.type) }
      assert(Date.now() < deadline, `Actual original video never decoded/settled the commanded source PTS ${target}s`)
      await delay(50)
    }
  } finally { await embed.frame.evaluate(() => window.__harmonicCompactSeek?.detach()).catch(() => {}) }
}


/** Preserve observed timing counterexamples even when the native model state is stale. */
export function requirePausedReview(actual, native, frame, required = true) {
  assert(actual.mode === 'reference-review' && actual.playerState === 'paused' && native.paused && !native.seeking, 'Source review did not hold a decoded paused original frame')
  const clockSkewSeconds = Math.abs(actual.modelTime - native.mediaTime)
  try {
    assert(!finite(clockSkewSeconds) || clockSkewSeconds <= CLOCK_LIMIT, 'Actual original media/model clock exceeds the0.5s timing bound')
    assert((required ? ['approximate'] : ['no-machine', 'approximate']).includes(actual.referenceState) && Math.abs(actual.modelTime - frame.timeSeconds) <= 1e-6, 'Source sample has no current native draw or legitimate no-machine hold')
  } catch (error) {
    if (finite(clockSkewSeconds)) Object.assign(error, { clockSkewSeconds, nativeMediaTime: native.mediaTime })
    throw error
  }
}

/** Capture actual framebuffer-marker readback; no CPU projection or old source certificates. */
async function review(page, embed, record, frame, required = true) {
  const shot = record.track.shots.find(shot => shot.id === frame.shotId)
  assert(sourcePtsInShot(frame, shot), 'Observed source PTS lies outside its own half-open source shot; adjacent-shot images/cameras cannot pass')
  const before = await media(embed)
  const seek = await observedSeek(embed, frame.decodedTimeSeconds, () => page.evaluate(async sample => window.harmonicAnalyzer.reviewReferenceFrame(sample.timeSeconds, sample.decodedTimeSeconds), { timeSeconds: frame.timeSeconds, decodedTimeSeconds: frame.decodedTimeSeconds }), record.native.fps)
  const actual = await snapshot(page), native = await media(embed)
  requireModel(actual, record.id); requireMedia(native, record)
  requirePausedReview(actual, native, frame, required)
  assert(Math.abs(native.mediaTime - frame.decodedTimeSeconds) <= 0.5 / record.native.fps + 0.005 && Math.abs(native.mediaTime - frame.timeSeconds) <= CLOCK_LIMIT + 1e-6, 'Actual original media is not on the observed source exposure within the0.5s timing bound')
  const expectedIndex = nearestPtsIndex(record.native.pts, frame.decodedTimeSeconds)
  assert(Math.abs(record.native.pts[expectedIndex] - frame.decodedTimeSeconds) <= 0.001 && Math.abs(frame.decodedTimeSeconds - frame.timeSeconds) <= CLOCK_LIMIT + 1e-6, 'Authored sample is not a retained native source PTS within0.5s')
  if (frame.sourceImage) assert(frame.sourceImage.frameIndex === expectedIndex, 'Source image frame index differs from declared native PTS')
  const rendered = await page.evaluate(ids => {
    const canvas = document.querySelector('#stage')
    return { captures: ids.map(viewId => ({ viewId, capture: window.harmonicAnalyzer.renderedLandmarks(viewId), mechanism: window.harmonicAnalyzer.renderedMechanism(viewId) })), canvas: { tag: canvas?.tagName, width: canvas?.width, height: canvas?.height, clientWidth: canvas?.clientWidth, clientHeight: canvas?.clientHeight, devicePixelRatio: window.devicePixelRatio } }
  }, (frame.views ?? []).map(view => view.id))
  return { actual, native, seek, beforeMediaTime: before.mediaTime, ...rendered }
}
export function sourceSeedIndex(frames) {
  const seeds = new Map()
  for (const frame of frames) {
    if (!finite(frame.decodedTimeSeconds) || !Number.isInteger(frame.sourceImage?.frameIndex) || frame.sourceImage.frameIndex < 0 || !frame.sourceImage?.sourceSha256) continue
    for (const item of frame.landmarks ?? []) {
      if (item.method !== 'manual' || item.status !== 'observed' || !point(item.pixel) || !['fit', 'check'].includes(item.role)) continue
      const seed = { ...item, sourceImage: frame.sourceImage, decodedTimeSeconds: frame.decodedTimeSeconds }
      // The producer records nominal seed time; both declared times identify the
      // same exact image and original view, never a nearest-time/tolerance alias.
      for (const time of new Set([frame.timeSeconds, frame.decodedTimeSeconds].filter(finite))) {
        const key = `${time}/${item.originalViewId ?? item.viewId ?? 'main'}/${item.anchorId}`, prior = seeds.get(key)
        // Contradictory declarations do not pick a winner, even on later repeats.
        if (seeds.has(key) && (!prior || jsonDigest(prior.sourceImage) !== jsonDigest(seed.sourceImage)
          || prior.role !== seed.role || jsonDigest(prior.pixel) !== jsonDigest(seed.pixel))) seeds.set(key, null)
        else seeds.set(key, seed)
      }
    }
  }
  return seeds
}

/** Only method/provenance rejection is excludable; missing pixels/native bodies are not. */
function sourceMethodIssue(observed, anchor, frame, seeds, viewId) {
  if (!['manual', 'optical-flow', 'image-edge', 'template-match'].includes(observed.method)) return { code: 'source-method', reason: 'Source measurement method is not an admitted independent pixel technique' }
  const evidence = observed.trackingEvidence, seed = seeds.get(`${evidence?.seedTimeSeconds}/${observed.originalViewId ?? viewId}/${observed.anchorId}`)
  const seedBound = seed && seed.sourceImage?.sourceSha256 && seed.sourceImage.sourceSha256 === frame.sourceImage?.sourceSha256
    && (!Object.hasOwn(evidence, 'seedDecodedFrameIndex') || evidence.seedDecodedFrameIndex === seed.sourceImage.frameIndex)
    && (!evidence.seedSourceImage || jsonDigest(evidence.seedSourceImage) === jsonDigest(seed.sourceImage))
  if (observed.method === 'template-match' && (!seedBound || seed.role !== observed.role || evidence?.reacquiredFromActualPixels !== true
    || !finite(evidence.wholeSourceViewCorrelation) || evidence.wholeSourceViewCorrelation < 0.998
    || !finite(evidence.sourcePatchCorrelation) || evidence.sourcePatchCorrelation < 0.97)) {
    return { code: 'template-provenance', reason: 'Independent manual seed and actual source-view/source-feature reacquisition correlations must be retained' }
  }
  if (observed.method === 'optical-flow' && (anchor?.kind !== 'physical-feature' || !seedBound || seed.role !== observed.role
    || !finite(evidence?.forwardBackwardErrorPx) || evidence.forwardBackwardErrorPx > 1
    || !finite(evidence?.seedPatchCorrelation) || evidence.seedPatchCorrelation < 0.80
    || !finite(evidence?.adjacentPatchCorrelation) || evidence.adjacentPatchCorrelation < 0.90)) {
    return { code: 'flow-provenance', reason: 'Independent physical-feature seed and consistent actual-source flow evidence must be retained' }
  }
  const edgeEvidence = observed.measurementEvidence
  if (observed.method === 'image-edge' && !(typeof edgeEvidence === 'string' && edgeEvidence.trim() || edgeEvidence && typeof edgeEvidence === 'object' && !Array.isArray(edgeEvidence) && Object.keys(edgeEvidence).length)) return { code: 'edge-provenance', reason: 'Actual source edge/search measurement evidence is missing' }
  const binding = observed.measurementEvidence ?? evidence
  if (binding && typeof binding === 'object' && (binding.sourceImage && jsonDigest(binding.sourceImage) !== jsonDigest(frame.sourceImage ?? null)
    || Object.hasOwn(binding, 'sourceSha256Bgr8') && binding.sourceSha256Bgr8 !== frame.sourceImage?.sha256Bgr8
    || Object.hasOwn(binding, 'sourceSha256Gray8') && binding.sourceSha256Gray8 !== frame.sourceImage?.sha256Gray8)) {
    return { code: 'measurement-image-binding', reason: 'Source measurement provenance belongs to a different exposure/image hash' }
  }
  return null
}

function distributedLandmarkFloor(measured) {
  if (measured.length < 3 || !measured.some(item => item.role === 'check')) return false
  for (let a = 0; a < measured.length - 2; a++) for (let b = a + 1; b < measured.length - 1; b++) for (let c = b + 1; c < measured.length; c++) {
    const points = [measured[a], measured[b], measured[c]]
    if (new Set(points.map(item => item.anchorId)).size !== 3 || !points.some(item => item.role === 'check')) continue
    const [p, q, r] = points.map(item => item.sourcePixels)
    const distances = [Math.hypot(p[0] - q[0], p[1] - q[1]), Math.hypot(q[0] - r[0], q[1] - r[1]), Math.hypot(r[0] - p[0], r[1] - p[1])]
    const uncertainty = Math.max(1, points.reduce((sum, item) => sum + item.sourceUncertaintyPx, 0))
    const twiceArea = Math.abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]))
    // Three resolvably separated, non-collinear actual features, not duplicate
    // samples or a cluster smaller than its declared source uncertainty.
    if (Math.min(...distances) > uncertainty && twiceArea / Math.max(...distances) > uncertainty) return true
  }
  return false
}

export function measureView(view, response, frame, observations, tolerancePx, anchors, seeds = new Map()) {
  const entry = response.captures.find(item => item.viewId === view.id), capture = entry?.capture, mechanism = entry?.mechanism
  const rendered = response.actual.views?.find(item => item.id === view.id)
  assert(capture?.method === 'gpu-readback' && capture.status === 'captured' && capture.visibilityMode === 'depth-off-landmark-projection' && capture.viewId === view.id && finite(capture.timeSeconds) && Math.abs(capture.timeSeconds - frame.timeSeconds) <= 1e-6, 'Missing/stale actual GPU landmark readback')
  assert(mechanism?.method === 'actual-native-mechanism-solve' && mechanism.status === 'rendered' && mechanism.viewId === view.id && mechanism.timeSeconds === capture.timeSeconds && Number.isInteger(mechanism.sourceDrawRevision) && mechanism.sourceDrawRevision > 0 && mechanism.channelAnglesRad?.length === 20 && mechanism.channelAnglesRad.every(finite), 'Missing/stale native full physical solve')
  assert(rendered && jsonDigest(mechanism.input) === jsonDigest(rendered.input) && jsonDigest(mechanism.sourceLayout) === jsonDigest(capture.sourceLayout) && jsonDigest(mechanism.resolvedImagePlaneWarp) === jsonDigest(capture.resolvedImagePlaneWarp), 'Readback and native input/layout/warp do not belong to the same rendered source view')
  assert(jsonDigest(rendered.rectSourcePixels) === jsonDigest(view.rectSourcePixels) && rendered.presentation === view.presentation, 'Rendered source view ROI/orientation differs from sample')
  const near = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((value, index) => finite(value) && Math.abs(value - b[index]) <= 1e-7)
  if (frame.measuredInterpolation) {
    const sampling = rendered.sourceSampling, [fromTime, toTime] = frame.interpolationInterval
    assert(sampling && sampling.fromTimeSeconds === fromTime && (sampling.selection === 'continuous' ? sampling.toTimeSeconds === toTime && Math.abs(sampling.mix - (frame.timeSeconds - fromTime) / (toTime - fromTime)) <= 1e-7 : sampling.selection === 'decoded-exposure' && sampling.toTimeSeconds === fromTime && sampling.mix === 0), 'Intermediate source sample has no correctly bound actual interpolation/explicit held-pose receipt')
  } else {
    assert(near(rendered.camera?.positionMetres, view.camera.positionMetres) && (near(rendered.camera?.quaternion, view.camera.quaternion) || near(rendered.camera?.quaternion, view.camera.quaternion.map(value => -value))) && Math.abs(rendered.camera.verticalFovDegrees - view.camera.verticalFovDegrees) <= 1e-7 && jsonDigest(rendered.input) === jsonDigest(view.input), 'GPU sample did not draw the authored camera and complete chosen physical input')
  }
  const canvas = response.canvas
  assert(canvas.tag === 'CANVAS' && canvas.clientWidth > 0 && canvas.clientHeight > 0 && Math.abs(canvas.width - canvas.clientWidth * canvas.devicePixelRatio) <= 1 && Math.abs(canvas.height - canvas.clientHeight * canvas.devicePixelRatio) <= 1, 'Actual WebGL canvas backing store is hidden/empty/stale')
  const width = Math.min(canvas.clientWidth, canvas.clientHeight * 1920 / 1080), height = width * 1080 / 1920
  const gate = { x: (canvas.clientWidth - width) / 2, y: (canvas.clientHeight - height) / 2, width, height }
  const layoutIndex = capture.sourceLayout?.findIndex(item => item.viewId === view.id)
  assert(layoutIndex >= 0, 'Actual GPU capture has no current ordered source support')
  const required = observations.filter(item => (item.viewId ?? 'main') === view.id)
  assert(required.length > 0, 'Required source view has no independently observed landmarks')
  const measured = [], unavailable = [], excluded = []
  if (!required.some(item => item.role === 'check')) unavailable.push({ viewId: view.id, status: 'source-unavailable', reason: 'Required source view has no independent CHECK landmarks; FIT residuals are diagnostic only' })
  for (const observed of required) {
    const anchor = anchors.get(observed.anchorId), marker = capture.landmarks?.find(item => item.id === observed.anchorId)
    const context = { viewId: view.id, anchorId: observed.anchorId, role: observed.role, motion: anchor?.motion ?? 'unknown', sourcePixels: observed.pixel }
    if (!anchor?.partPath || (!anchor.partLocalMetres && !anchor.worldMetres) || !anchor.correspondenceEvidence) { unavailable.push({ ...context, status: 'unmeasured-native', reason: 'Source landmark lacks native physical-feature correspondence' }); continue }
    if (observed.status !== 'observed' || !['fit', 'check'].includes(observed.role) || !point(observed.pixel) || !finite(observed.uncertaintyPx) || observed.uncertaintyPx < 0) { unavailable.push({ ...context, status: 'source-unavailable', reason: 'Independent source landmark pixel/measurement is unavailable' }); continue }
    const sourceIssue = sourceMethodIssue(observed, anchor, frame, seeds, view.id)
    if (marker?.state !== 'rendered' || !point(marker.sourcePixels) || !point(marker.canvasPixels) || !finite(marker.uncertaintySourcePixels) || marker.uncertaintySourcePixels < 0) { unavailable.push({ ...context, status: 'unmeasured-native', reason: marker?.reason ?? 'Landmark has no actual GPU-rendered pixels' }); continue }
    if (!sourcePointUnmasked(capture.sourceLayout, layoutIndex, observed.pixel) || !sourcePointUnmasked(capture.sourceLayout, layoutIndex, marker.sourcePixels)) { unavailable.push({ ...context, status: 'unmeasured-native', reason: 'Source/GPU landmark falls outside its view support or behind an opaque/inset layer' }); continue }
    const canvasPoint = [gate.x + marker.sourcePixels[0] / 1920 * gate.width, gate.y + marker.sourcePixels[1] / 1080 * gate.height]
    const mappingErrorPx = Math.hypot(marker.canvasPixels[0] - canvasPoint[0], marker.canvasPixels[1] - canvasPoint[1])
    if (mappingErrorPx > 0.75) { unavailable.push({ ...context, status: 'unmeasured-native', reason: `Actual source-to-canvas mapping differs by ${mappingErrorPx}px` }); continue }
    if (sourceIssue) { excluded.push({ ...context, status: 'source-inadmissible', method: observed.method, reasonCode: sourceIssue.code, reason: sourceIssue.reason }); continue }
    const rawErrorPx = Math.hypot(marker.sourcePixels[0] - observed.pixel[0], marker.sourcePixels[1] - observed.pixel[1])
    const errorPx = rawErrorPx + observed.uncertaintyPx + marker.uncertaintySourcePixels
    measured.push({ ...context, method: capture.method, nativePixels: marker.sourcePixels, canvasPixels: marker.canvasPixels, rawErrorPx, sourceUncertaintyPx: observed.uncertaintyPx, rasterUncertaintyPx: marker.uncertaintySourcePixels, errorPx, errorFrameWidthPercent: errorPx / 1920 * 100, status: errorPx <= tolerancePx ? 'passed' : 'failed', captureTimeSeconds: capture.timeSeconds, nativeMediaTime: response.native.mediaTime, sourceDrawRevision: mechanism.sourceDrawRevision, sourceSampling: rendered.sourceSampling, independentMidIntervalObservation: frame.measuredInterpolation === true })
  }
  if (excluded.length && !distributedLandmarkFloor(measured)) unavailable.push({ viewId: view.id, status: 'source-unavailable', reason: 'Source-inadmissible exclusions require at least three distributed admitted actual landmarks including an independent CHECK' })
  return { measured, unavailable, excluded, clockSkewSeconds: Math.abs(capture.timeSeconds - response.native.mediaTime) }
}

function playbackSourceObservations(record) {
  const frames = record.track.frames, anchors = new Map((record.track.anchors ?? []).map(anchor => [anchor.id, anchor]))
  const shots = new Map(record.track.shots.map(shot => [shot.id, shot])), seeds = sourceSeedIndex([...(record.observations?.frames ?? []), ...frames])
  return frames.map(frame => {
    const points = new Map()
    if (!frame.sourceImage || !sourcePtsInShot(frame, shots.get(frame.shotId))) return points
    let layout
    try { layout = sourceLayoutForViews(frame.views ?? []) } catch { return points }
    for (const observed of frame.landmarks ?? []) {
      const viewId = observed.viewId ?? 'main', index = layout.findIndex(view => view.viewId === viewId), anchor = anchors.get(observed.anchorId)
      if (index < 0 || !anchor?.partPath || (!anchor.partLocalMetres && !anchor.worldMetres) || !anchor.correspondenceEvidence
        || observed.status !== 'observed' || !['fit', 'check'].includes(observed.role) || !point(observed.pixel)
        || !finite(observed.uncertaintyPx) || observed.uncertaintyPx < 0 || !sourcePointUnmasked(layout, index, observed.pixel)
        || sourceMethodIssue(observed, anchor, frame, seeds, viewId)) continue
      points.set(`${viewId}/${observed.anchorId}`, { ...observed, viewId })
    }
    return points
  })
}

function sourceCameraChanged(from, to) {
  const a = from.camera, b = to.camera
  if (!a || !b) return false
  const distance = Math.hypot(...a.positionMetres.map((value, index) => value - b.positionMetres[index]))
  const dot = Math.abs(a.quaternion.reduce((sum, value, index) => sum + value * b.quaternion[index], 0))
  return distance > 1e-6 || dot < 1 - 1e-10 || Math.abs(a.verticalFovDegrees - b.verticalFovDegrees) > 1e-5
}

function playbackMotionEvidence(record, index, points, endSeconds) {
  const from = record.track.frames[index], frames = record.track.frames, shot = record.track.shots.find(shot => shot.id === from.shotId)
  const horizon = Math.min(endSeconds, from.timeSeconds + 1.5)
  let evidence = null
  for (let next = index + 1; next < frames.length && frames[next].timeSeconds <= horizon; next++) {
    const to = frames[next]
    if (to.shotId !== from.shotId) break
    if (!from.sourceImage || !to.sourceImage || to.sourceImage.frameIndex === from.sourceImage.frameIndex
      || !sourcePtsInShot(to, shot) || to.decodedTimeSeconds <= from.decodedTimeSeconds) continue
    for (const [key, observed] of points[index]) {
      const target = points[next].get(key)
      if (!target || observed.role !== target.role) continue
      const displacementPx = Math.hypot(target.pixel[0] - observed.pixel[0], target.pixel[1] - observed.pixel[1])
      const uncertaintyPx = observed.uncertaintyPx + target.uncertaintyPx, signalPx = displacementPx - uncertaintyPx
      if (signalPx <= 1 || evidence?.priority === 2 && signalPx <= evidence.signalPx) continue
      evidence = { kind: 'independently-observed-source-landmark-motion', priority: 2, signalPx, viewId: observed.viewId, anchorId: observed.anchorId, role: observed.role, fromTimeSeconds: from.timeSeconds, toTimeSeconds: to.timeSeconds, fromDecodedTimeSeconds: from.decodedTimeSeconds, toDecodedTimeSeconds: to.decodedTimeSeconds, sourceImageBefore: from.sourceImage, sourceImageAfter: to.sourceImage, sourcePixelsBefore: observed.pixel, sourcePixelsAfter: target.pixel, displacementPx, uncertaintyPx, methods: [observed.method, target.method] }
    }
    if (evidence?.priority === 2) continue
    for (const view of from.views) {
      const target = to.views?.find(item => item.id === view.id)
      if (!target || view.cameraProvenance?.kind !== 'source-fit' || target.cameraProvenance?.kind !== 'source-fit'
        || !view.cameraProvenance.family || view.cameraProvenance.family !== target.cameraProvenance.family
        || !sourceCameraChanged(view, target)) continue
      evidence = { kind: 'declared-source-fit-camera-change', priority: 1, signalPx: 0, viewId: view.id, cameraFamily: view.cameraProvenance.family, fromTimeSeconds: from.timeSeconds, toTimeSeconds: to.timeSeconds, sourceImageBefore: from.sourceImage, sourceImageAfter: to.sourceImage, cameraBefore: view.camera, cameraAfter: target.camera }
      break
    }
  }
  return evidence
}

/** Prefer observed visible motion; duration alone can select a static blurred montage with hidden-input changes. */
export function playbackInterval(record, minimumSeconds = 3) {
  const shots = new Map(record.track.shots.map(shot => [shot.id, shot])), frames = record.track.frames
  const ends = new Float64Array(frames.length)
  const points = playbackSourceObservations(record)
  let candidate = null
  for (let index = frames.length - 1; index >= 0; index--) {
    const frame = frames[index], shot = shots.get(frame.shotId)
    if (!sourcePtsInShot(frame, shot) || frame.sourceSampleUnavailable === true || !sourceNeedsMachine(frame, shot)
      || !frame.views?.length || !frame.views.every(view => view.camera && view.input)) continue
    let endSeconds = Math.min(shot.endSeconds, record.native.durationSeconds)
    const next = frames[index + 1]
    if (next && next.timeSeconds < endSeconds) endSeconds = next.shotId === frame.shotId && ends[index + 1] > next.timeSeconds ? ends[index + 1] : next.timeSeconds
    ends[index] = endSeconds
    const availableSeconds = endSeconds - Math.max(frame.timeSeconds, frame.decodedTimeSeconds)
    if (availableSeconds < minimumSeconds) continue
    const motionEvidence = playbackMotionEvidence(record, index, points, endSeconds)
    const priority = motionEvidence?.priority ?? 0, signalPx = motionEvidence?.signalPx ?? 0
    if (!candidate || priority > (candidate.motionEvidence?.priority ?? 0)
      || priority === (candidate.motionEvidence?.priority ?? 0) && (signalPx > (candidate.motionEvidence?.signalPx ?? 0)
        || signalPx === (candidate.motionEvidence?.signalPx ?? 0) && availableSeconds > candidate.availableSeconds)) {
      candidate = { frame, endSeconds, availableSeconds, motionEvidence }
    }
  }
  return candidate
}

async function playbackChecks(page, embed, record, report, outputDirectory) {
  const playback = { status: 'unavailable', selectedInterval: null, clocks: [] }
  report.playback[embed.player] = playback
  await pause(page, embed)
  await page.evaluate(() => window.harmonicAnalyzer.endReferenceReview())
  const interval = playbackInterval(record)
  assert(interval, 'No complete required same-shot source interval with playback-duration margin is available')
  const candidate = interval.frame
  playback.selectedInterval = { shotId: candidate.shotId, startTimeSeconds: candidate.timeSeconds, startDecodedTimeSeconds: candidate.decodedTimeSeconds, endSeconds: interval.endSeconds, availableSeconds: interval.availableSeconds, minimumRequiredSeconds: 3, selection: interval.motionEvidence?.kind ?? 'complete-required-same-shot-fallback', sourceMotionEvidence: interval.motionEvidence }
  const readRenderState = () => page.evaluate(() => {
    const api = window.harmonicAnalyzer, actual = api.snapshot()
    return { actual, receipts: actual.views.map(view => ({ viewId: view.id, mechanism: api.renderedMechanism(view.id) })) }
  })
  await page.evaluate(async sample => window.harmonicAnalyzer.reviewReferenceFrame(sample.timeSeconds, sample.decodedTimeSeconds), { timeSeconds: candidate.timeSeconds, decodedTimeSeconds: candidate.decodedTimeSeconds })
  const stage = page.locator('#stage')
  const canvasShot = () => stage.screenshot({ mask: [page.locator('#video-dock'), page.locator('#loading')], animations: 'disabled' })
  const beforePixels = await canvasShot()
  const beforeRender = await readRenderState(), beforeSource = beforeRender.actual
  playback.beforeState = { ...beforeRender, media: await media(embed) }
  const beforeScreenshot = `${record.id}-${embed.player}-playing-before.png`, afterScreenshot = `${record.id}-${embed.player}-playing-after.png`
  await writeFile(resolve(outputDirectory, beforeScreenshot), beforePixels)
  playback.canvas = { beforeSha256: digest(beforePixels), beforeScreenshot }
  await page.locator('#pause-video').click()
  await page.waitForFunction(() => window.harmonicAnalyzer.snapshot().playerState === 'playing', undefined, { timeout: 25_000 })
  const started = await media(embed); requireMedia(started, record)
  playback.startedMedia = started
  assert(!started.paused && !started.muted && started.volume > 0, 'Original video must actually play with unmuted nonzero audio')
  const clocks = playback.clocks
  for (let index = 0; index < 6; index++) {
    await delay(250)
    const before = await media(embed)
    const rendered = await readRenderState()
    const actual = rendered.actual, after = await media(embed)
    requireMedia(after, record)
    assert(after.mediaTime >= before.mediaTime && !after.paused && actual.mode === 'following-video', 'Actual media/source-following playback stopped')
    const skew = Math.max(0, before.mediaTime - actual.modelTime, actual.modelTime - after.mediaTime)
    assert(finite(skew) && skew <= CLOCK_LIMIT, 'Playing video/native model timing exceeds0.5s')
    assert(actual.referenceState === 'approximate', 'Playing required compact source-following draw became unavailable')
    const revisions = new Set()
    for (const entry of rendered.receipts) {
      const native = entry.mechanism, view = actual.views.find(item => item.id === entry.viewId)
      assert(native?.method === 'actual-native-mechanism-solve' && native.status === 'rendered' && native.timeSeconds === actual.modelTime && Number.isInteger(native.sourceDrawRevision) && native.sourceDrawRevision > 0 && native.channelAnglesRad?.length === 20 && native.channelAnglesRad.every(finite), 'Playback clock must be tied to a completed actual native geometry render, not a media/model-time alias')
      assert(view && jsonDigest(native.input) === jsonDigest(view.input) && jsonDigest(native.sourceLayout) === jsonDigest(view.sourceLayout) && jsonDigest(native.resolvedImagePlaneWarp) === jsonDigest(view.resolvedImagePlaneWarp), 'Live native render receipt has a stale/different physical input or source view layout')
      revisions.add(native.sourceDrawRevision)
    }
    assert(actual.views.length > 0 && revisions.size === 1, 'Playing clock proof needs one current completed native source draw shared by all physical views')
    clocks.push({ mediaTimeBefore: before.mediaTime, modelTime: actual.modelTime, mediaTimeAfter: after.mediaTime, clockSkewSeconds: skew, referenceState: actual.referenceState, sourceDrawRevision: [...revisions][0], renderedViews: rendered.receipts.map(entry => ({ viewId: entry.viewId, method: entry.mechanism.method, status: entry.mechanism.status, timeSeconds: entry.mechanism.timeSeconds, inputDigest: jsonDigest(entry.mechanism.input) })) })
  }
  const ended = await media(embed)
  playback.endedMedia = ended
  assert(ended.mediaTime - started.mediaTime >= 1, 'Actual source video did not advance through playback')
  assert(clocks.at(-1).sourceDrawRevision > clocks[0].sourceDrawRevision, 'Actual native completed draw revision never advanced while the original video played')
  const afterPixels = await canvasShot(), afterRender = await readRenderState(), afterSource = afterRender.actual
  playback.afterState = { ...afterRender, media: await media(embed) }
  await writeFile(resolve(outputDirectory, afterScreenshot), afterPixels)
  const visualState = actual => actual.views.map(view => ({ id: view.id, camera: view.camera, input: view.input, rectSourcePixels: view.rectSourcePixels, composite: view.composite, resolvedImagePlaneWarp: view.resolvedImagePlaneWarp }))
  const sourceStateChanged = jsonDigest(visualState(beforeSource)) !== jsonDigest(visualState(afterSource))
  const canvasChanged = digest(beforePixels) !== digest(afterPixels)
  Object.assign(playback.canvas, { sourceStateChanged, canvasChanged, afterSha256: digest(afterPixels), afterScreenshot })
  assert(!sourceStateChanged || canvasChanged, 'Changing source camera/mechanism receipts did not change actual rendered canvas pixels')
  await pause(page, embed)
  await page.locator('#minimize-player').click()
  const rect = await page.locator('#video-player').boundingBox()
  assert(rect && rect.width >= 200 && rect.height >= 200, 'Compact original player must remain at least200x200')
  const activeControls = await embed.frame.evaluate(selector => {
    const video = document.querySelector(selector)
    if (selector.includes('html5-main-video')) {
      const control = document.querySelector('.ytp-play-button'), bar = document.querySelector('.ytp-chrome-bottom'), bounds = control?.getBoundingClientRect()
      return { controls: !!control && !!bar && bounds?.width > 0 && bounds?.height > 0 }
    }
    return { controls: video?.controls === true }
  }, embed.selector)
  assert(activeControls.controls, 'Compact original player has no usable native playback controls')
  if (embed.player === 'youtube') await embed.frame.locator('.ytp-play-button').click()
  else {
    const video = page.locator(embed.selector)
    await video.hover()
    // Chromium owns this button in a closed user-agent shadow tree. Its actual
    // box, not the video's bottom-left corner, is the native mouse hit target.
    const session = await page.context().newCDPSession(page)
    try {
      const { result } = await session.send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(embed.selector)})` })
      assert(result.objectId, 'Compact original media element is unavailable')
      const { node } = await session.send('DOM.describeNode', { objectId: result.objectId, depth: -1, pierce: true })
      const findPlayButton = node => {
        const attributes = node.attributes ?? []
        if (attributes.some((value, index) => index % 2 === 1 && value === '-webkit-media-controls-play-button')) return node
        for (const child of [...(node.shadowRoots ?? []), ...(node.children ?? [])]) {
          const button = findPlayButton(child)
          if (button) return button
        }
        return null
      }
      const button = findPlayButton(node)
      assert(button, 'Compact original player has no native play button')
      const { model } = await session.send('DOM.getBoxModel', { backendNodeId: button.backendNodeId })
      const quad = model.border
      const x = (quad[0] + quad[2] + quad[4] + quad[6]) / 4, y = (quad[1] + quad[3] + quad[5] + quad[7]) / 4
      assert(model.width > 0 && model.height > 0 && x >= rect.x && x <= rect.x + rect.width && y >= rect.y && y <= rect.y + rect.height, 'Compact native play button has no visible in-player hit target')
      await page.mouse.click(x, y)
    } finally {
      await session.detach()
    }
  }
  await page.waitForFunction(() => window.harmonicAnalyzer.snapshot().playerState === 'playing', undefined, { timeout: 20_000 })
  const compactStarted = await media(embed); requireMedia(compactStarted, record)
  await delay(600)
  const compactPlayed = await media(embed)
  const compactRender = await page.evaluate(() => {
    const api = window.harmonicAnalyzer, actual = api.snapshot()
    return { actual, receipts: actual.views.map(view => api.renderedMechanism(view.id)) }
  })
  const compactState = compactRender.actual
  assert(!compactPlayed.paused && !compactPlayed.muted && compactPlayed.volume > 0 && compactPlayed.mediaTime - compactStarted.mediaTime >= 0.3 && compactState.mode === 'following-video' && Math.abs(compactState.modelTime - compactPlayed.mediaTime) <= CLOCK_LIMIT, 'Compact native controls did not actually play original audio/video with synchronized model')
  assert(compactRender.receipts.length > 0 && compactRender.receipts.every(receipt => receipt.method === 'actual-native-mechanism-solve' && receipt.status === 'rendered' && receipt.timeSeconds === compactState.modelTime && receipt.sourceDrawRevision > clocks.at(-1).sourceDrawRevision), 'Compact playback has no new completed native geometry render receipt')
  await pause(page, embed)
  const compactScreenshot = `${record.id}-${embed.player}-compact.png`
  await page.screenshot({ path: resolve(outputDirectory, compactScreenshot) })
  await page.locator('#minimize-player').click()
  Object.assign(playback, { status: 'passed', clockProof: 'Completed actual-native-geometry-render receipts, actual original media before/after brackets, and actual canvas screenshots; expensive landmark probes remain paused-review-only.', audio: { muted: started.muted, volume: started.volume, proof: 'Actual decoded original HTMLMediaElement playback; audio track retained in unchanged source bytes, not acoustic loopback' }, advancedSeconds: ended.mediaTime - started.mediaTime, clocks, maxClockSkewSeconds: Math.max(...clocks.map(item => item.clockSkewSeconds)), compact: { width: rect.width, height: rect.height, controls: activeControls.controls, screenshot: compactScreenshot } })
}

async function interactionChecks(page, embed, id, outputDirectory) {
  await pause(page, embed); await page.evaluate(() => window.harmonicAnalyzer.endReferenceReview())
  await page.locator('#fit-view').click()
  if (!await page.locator('#manual-controls').evaluate(details => details.open)) await page.locator('#manual-controls > summary').click()
  const crank = page.locator('#crank'), stage = page.locator('#stage')
  assert(await crank.isVisible() && await crank.isEnabled(), 'Paused native mechanism manual crank is hidden or disabled')
  const before = await snapshot(page), mediaBefore = await media(embed)
  const take = () => stage.screenshot({ mask: [page.locator('#video-dock'), page.locator('#loading')], animations: 'disabled' })
  const beforePixels = await take()
  const range = await crank.evaluate(control => ({ value: Number(control.value), min: Number(control.min), max: Number(control.max), step: Number(control.step) }))
  assert([range.value, range.min, range.max, range.step].every(finite) && range.step > 0 && range.max > range.min, 'Manual crank has invalid physical input bounds')
  const key = range.max - range.value >= range.value - range.min ? 'ArrowRight' : 'ArrowLeft'
  await crank.focus()
  assert(await crank.evaluate(control => document.activeElement === control), 'Manual crank did not receive actual keyboard focus')
  await crank.press(key); await crank.press(key); await crank.press(key)
  const changedValue = await crank.evaluate(control => Number(control.value))
  assert(Math.abs(changedValue - range.value) > 1e-6, 'Actual keyboard interaction did not move the bounded crank range')
  await page.waitForFunction(turns => Math.abs(window.harmonicAnalyzer.snapshot().input.crankTurns - turns) <= 1e-6, changedValue)
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))))
  const after = await snapshot(page), crankPixels = await take()
  assert(Math.abs(after.input.crankTurns - before.input.crankTurns) > 1e-6 && after.mode === 'exploring' && after.playerState === 'paused' && digest(beforePixels) !== digest(crankPixels) && jsonDigest(before.camera) === jsonDigest(after.camera), 'Manual crank must change actual native rendered geometry without moving camera or replaying media')
  const target = await stage.evaluate(canvas => {
    const rect = canvas.getBoundingClientRect()
    for (const [x, y] of [[0.3, 0.3], [0.6, 0.45], [0.5, 0.6], [0.7, 0.25]]) {
      const left = rect.left + rect.width * x, top = rect.top + rect.height * y, dx = Math.min(100, rect.width * 0.12)
      if (document.elementFromPoint(left, top) === canvas && document.elementFromPoint(left + dx, top + 35) === canvas) return { left, top, dx }
    }
    return null
  })
  assert(target, 'No usable native model orbit surface')
  await page.mouse.move(target.left, target.top); await page.mouse.down(); await page.mouse.move(target.left + target.dx, target.top + 35, { steps: 8 }); await page.mouse.up()
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))))
  const orbit = await snapshot(page), orbitPixels = await take(), mediaAfter = await media(embed)
  assert(jsonDigest(orbit.camera) !== jsonDigest(after.camera) && digest(orbitPixels) !== digest(crankPixels), 'Manual orbit must change actual rendered camera/pixels')
  assert(mediaAfter.paused && Math.abs(mediaAfter.mediaTime - mediaBefore.mediaTime) <= 0.1, 'Manual operation/orbit restarted the source video')
  const screenshot = `${id}-manual-orbit.png`; await writeFile(resolve(outputDirectory, screenshot), orbitPixels)
  return { status: 'passed', crankTurnsBefore: before.input.crankTurns, crankTurnsAfter: after.input.crankTurns, orbitCameraBefore: after.camera, orbitCameraAfter: orbit.camera, pausedDriftSeconds: Math.abs(mediaAfter.mediaTime - mediaBefore.mediaTime), screenshot }
}

export function requireSourceViews(row) {
  const frame = row.frame
  assert(frame?.views?.length > 0, 'Required source interval has no authored native views (closeups/insets/montages remain required)')
  const ids = new Set(frame.views.map(view => view.id))
  assert(row.expectedViewIds.every(id => ids.has(id)), `Required source view(s) omitted: ${row.expectedViewIds.filter(id => !ids.has(id)).join(',')}`)
  assert(frame.views.every(view => view.camera && view.input), 'Required source sample has a missing camera or complete physical input')
  assert(!frame.viewMappingUnavailable?.length, frame.viewMappingUnavailable?.map(item => `${item.anchorId}: ${item.reason}`).join('; '))
  const orphanViews = [...new Set((frame.landmarks ?? []).filter(item => !ids.has(item.viewId ?? 'main')).map(item => item.viewId ?? 'main'))]
  assert(!orphanViews.length, `Original source landmark view(s) lack an evidenced compact-view mapping: ${orphanViews.join(',')}`)
}

async function measureSamples(page, embed, record, census, video, tolerancePx, outputDirectory) {
  const anchors = new Map(record.track.anchors.map(anchor => [anchor.id, anchor]))
  const seeds = sourceSeedIndex([...record.observations.frames, ...record.track.frames])
  const measuredFrames = new Map()
  for (const row of census.selected) {
    const sample = { timeSeconds: row.timeSeconds, reasons: row.reasons, diagnosticOnly: row.diagnosticOnly === true, required: row.required, sourceShotId: row.sourceShotId, sampleTimeSeconds: row.frame?.timeSeconds ?? null, sourceImageReplay: row.sourceImageReplay ?? null, status: 'unavailable', measurements: [], unavailable: [], excluded: [] }
    video.samples.push(sample)
    if (!row.frame) { sample.unavailable.push({ reason: row.unavailableReason }); continue }
    const frame = row.frame
    try {
      assert(frame.sourceSampleUnavailable !== true, frame.unavailableReason ?? 'No independently available original source PTS')
      if (!row.required) {
        const response = await review(page, embed, record, frame, false)
        sample.nativeMediaTime = response.native.mediaTime
        sample.maxClockSkewSeconds = Math.abs(response.actual.modelTime - response.native.mediaTime)
        assert(sample.maxClockSkewSeconds <= CLOCK_LIMIT, 'No-machine/held sample timing exceeds0.5s')
        sample.status = 'not-required'
        continue
      }
      requireSourceViews(row)
      let result = measuredFrames.get(frame.timeSeconds)
      if (!result) {
        const response = await review(page, embed, record, frame)
        const measurements = [], unavailable = [], excluded = [], clocks = []
        for (const view of frame.views) {
          try { const measured = measureView(view, response, frame, frame.landmarks ?? [], tolerancePx, anchors, seeds); measurements.push(...measured.measured); unavailable.push(...measured.unavailable); excluded.push(...measured.excluded); clocks.push(measured.clockSkewSeconds) }
          catch (error) { unavailable.push({ viewId: view.id, status: 'unmeasured-native', reason: error.message }) }
        }
        const maxClockSkewSeconds = clocks.length ? Math.max(...clocks) : null
        result = { measurements, unavailable, excluded, maxClockSkewSeconds, status: measurements.some(item => item.status === 'failed') || maxClockSkewSeconds !== null && maxClockSkewSeconds > CLOCK_LIMIT ? 'failed' : unavailable.length || !measurements.length || maxClockSkewSeconds === null ? 'unavailable' : 'passed' }
        measuredFrames.set(frame.timeSeconds, result)
      }
      Object.assign(sample, result)
      if (!video.comparisonScreenshot && result.measurements.length) {
        video.comparisonScreenshot = `${record.id}-source-comparison.png`
        await page.screenshot({ path: resolve(outputDirectory, video.comparisonScreenshot) })
      }
    } catch (error) {
      if (finite(error.clockSkewSeconds)) Object.assign(sample, { maxClockSkewSeconds: error.clockSkewSeconds, nativeMediaTime: error.nativeMediaTime })
      if (finite(sample.maxClockSkewSeconds) && sample.maxClockSkewSeconds > CLOCK_LIMIT) sample.status = 'failed'
      sample.unavailable.push({ reason: error.message })
    }
  }
}
export function finishVideo(video, census, options) {
  const mandatoryRows = census.rows.filter(row => !row.diagnosticOnly), mandatory = video.samples.filter(sample => !sample.diagnosticOnly), diagnostic = video.samples.filter(sample => sample.diagnosticOnly)
  const required = mandatory.filter(sample => sample.required), measured = required.filter(sample => sample.measurements.length), passed = required.filter(sample => sample.status === 'passed' && !sample.unavailable.length && sample.measurements.length && sample.measurements.every(item => item.status === 'passed') && finite(sample.maxClockSkewSeconds) && sample.maxClockSkewSeconds <= CLOCK_LIMIT)
  const selectedTimes = new Map(mandatory.map(sample => [sample.timeSeconds.toFixed(6), sample]))
  const selectedRows = (census.selected ?? census.rows).filter(row => !row.diagnosticOnly)
  const missingCensusSamples = selectedRows.filter(row => {
    const sample = selectedTimes.get(row.timeSeconds.toFixed(6))
    return !sample || sample.required !== row.required
  }).length
  const unique = new Map()
  for (const sample of mandatory) for (const item of sample.measurements) unique.set(`${sample.sampleTimeSeconds}/${item.viewId}/${item.anchorId}`, item)
  const measurements = [...unique.values()], checks = measurements.filter(item => item.role === 'check')
  const isChange = row => row.reasons.some(reason => !['every-second', 'requested-sample', 'mid-interval'].includes(reason))
  video.coverage = { allSourceCensusSamples: census.rows.length, allMandatoryCensusSamples: mandatoryRows.length, allRequiredSourceSamples: mandatoryRows.filter(row => row.required).length, selectedCensusSamples: video.samples.length, selectedMandatoryCensusSamples: mandatory.length, selectedRequiredSamples: required.length, measuredRequiredSamples: measured.length, passedRequiredSamples: passed.length, failedRequiredSamples: required.filter(sample => sample.status === 'failed').length, unavailableRequiredSamples: required.filter(sample => sample.status === 'unavailable').length, missingCensusSamples, diagnosticSamples: { selected: diagnostic.length, measured: diagnostic.filter(sample => sample.measurements.length).length, passed: diagnostic.filter(sample => sample.status === 'passed').length, failed: diagnostic.filter(sample => sample.status === 'failed').length, unavailable: diagnostic.filter(sample => sample.status === 'unavailable').length }, everySecond: { required: mandatoryRows.filter(row => row.reasons.includes('every-second')).length, selected: mandatory.filter(row => row.reasons.includes('every-second')).length }, changePoints: { required: mandatoryRows.filter(isChange).length, selected: mandatory.filter(isChange).length }, complete: !options.scoped && missingCensusSamples === 0 && mandatory.length === mandatoryRows.length && required.length > 0 && passed.length === required.length && mandatory.every(sample => sample.required || sample.status === 'not-required') }
  video.coverage.unavailableCensusSamples = mandatory.filter(sample => sample.status === 'unavailable').length + missingCensusSamples
  video.coverage.complete &&= video.coverage.unavailableCensusSamples === 0
  video.landmarks = { measured: measurements.length, checks: checks.length, fitting: measurements.length - checks.length, fixedChecks: checks.filter(item => item.motion === 'fixed').length, movingChecks: checks.filter(item => item.motion === 'moving').length, maxErrorPx: maximumField(measurements, 'errorPx'), maxRawErrorPx: maximumField(measurements, 'rawErrorPx'), maxErrorFrameWidthPercent: maximumField(measurements, 'errorFrameWidthPercent') }
  const diagnosticMeasurements = diagnostic.flatMap(sample => sample.measurements)
  const diagnosticFailures = diagnosticMeasurements.filter(item => item.status === 'failed')
  const diagnosticClockFailures = diagnostic.filter(sample => finite(sample.maxClockSkewSeconds) && sample.maxClockSkewSeconds > CLOCK_LIMIT)
  const mandatoryClockFailures = mandatory.filter(sample => finite(sample.maxClockSkewSeconds) && sample.maxClockSkewSeconds > CLOCK_LIMIT)
  video.diagnosticLandmarks = { measured: diagnosticMeasurements.length, failed: diagnosticFailures.length, maxErrorPx: maximumField(diagnosticMeasurements, 'errorPx'), maxClockSkewSeconds: maximumField(diagnostic, 'maxClockSkewSeconds') }
  video.maxErrorPx = maximumField([...measurements, ...diagnosticMeasurements], 'errorPx')
  video.maxClockSkewSeconds = maximumField(video.samples, 'maxClockSkewSeconds')
  if (diagnosticFailures.length) video.failures.push({ code: 'diagnostic-pixel-counterexample', measuredLandmarks: diagnosticFailures.length, maxErrorPx: video.diagnosticLandmarks.maxErrorPx, reason: 'An independently admitted diagnostic source observation exceeds the stage pixel limit; optional missing or inadmissible oracles do not gate completeness, but actual measured counterexamples cannot be ignored.' })
  if (diagnosticClockFailures.length) video.failures.push({ code: 'diagnostic-clock-counterexample', measuredSamples: diagnosticClockFailures.length, maxClockSkewSeconds: maximumField(diagnosticClockFailures, 'maxClockSkewSeconds'), timeSeconds: diagnosticClockFailures.map(sample => sample.timeSeconds), reason: 'An independently observed diagnostic media/model clock exceeds0.5s; unknown timing remains unavailable, but a finite measured timing counterexample cannot be ignored.' })
  if (mandatoryClockFailures.length) video.failures.push({ code: 'mandatory-clock-counterexample', measuredSamples: mandatoryClockFailures.length, maxClockSkewSeconds: maximumField(mandatoryClockFailures, 'maxClockSkewSeconds'), timeSeconds: mandatoryClockFailures.map(sample => sample.timeSeconds), reason: 'An independently observed mandatory media/model clock exceeds0.5s; legitimate no-machine holds still gate timing, and a finite measured timing counterexample cannot be ignored.' })
  video.unavailableReasons = video.samples.flatMap(sample => sample.unavailable.map(item => ({ timeSeconds: sample.timeSeconds, diagnosticOnly: sample.diagnosticOnly === true, ...item })))
  const exclusionReasons = {}
  let excludedMandatory = 0, excludedDiagnostic = 0
  for (const sample of video.samples) for (const item of sample.excluded ?? []) {
    if (sample.diagnosticOnly) excludedDiagnostic++
    else excludedMandatory++
    exclusionReasons[item.reasonCode] = (exclusionReasons[item.reasonCode] ?? 0) + 1
  }
  video.sourceLandmarkExclusions = { mandatory: excludedMandatory, diagnostic: excludedDiagnostic, byReasonCode: exclusionReasons, interpretation: 'Source-method/provenance exclusions are reported separately, never measurements. Every affected view must retain three distributed admitted actual landmarks including CHECK; missing source pixels/views/native bodies and masked/unrendered GPU points remain blocking.' }
  if (!video.landmarks.fixedChecks) video.failures.push({ code: 'hard-fixed-landmark-coverage', reason: 'Hard fixed independent CHECK landmarks are required; easy camera-only FIT points cannot pass a video' })
  const shotMap = new Map((video.shots ?? []).map(shot => [shot.id, shot]))
  video.motionCoverage = []
  for (const shotId of new Set(required.map(sample => sample.sourceShotId ?? 'undeclared-shot'))) {
    const shot = shotMap.get(shotId), samples = required.filter(sample => (sample.sourceShotId ?? 'undeclared-shot') === shotId)
    const staticRig = shot?.internalMechanismMotion === 'static' && shot.sourceStaticControls?.status === 'source-controls-verified'
    const movingCheckSamples = samples.filter(sample => sample.measurements.some(item => item.role === 'check' && item.motion === 'moving')).length
    const fixedCheckAnchors = new Set(samples.flatMap(sample => sample.measurements.filter(item => item.role === 'check' && item.motion === 'fixed').map(item => item.anchorId))).size
    const complete = staticRig ? fixedCheckAnchors >= 2 : movingCheckSamples === samples.length
    video.motionCoverage.push({ shotId, internalMechanismMotion: staticRig ? 'source-backed-static-rig' : shot?.internalMechanismMotion ?? 'unknown', evidence: shot?.internalMotionEvidence ?? null, sourceControls: shot?.sourceStaticControls ?? null, requiredSamples: samples.length, movingCheckSamples, fixedCheckAnchors, status: complete ? 'measured' : 'unavailable' })
    if (!complete) video.failures.push({ code: 'hard-moving-landmark-coverage', shotId, reason: staticRig ? 'Source-backed static-rig shot needs distributed fixed CHECK landmarks; camera/error/timing/source views remain required' : 'Every required sample in a moving/unknown-mechanism shot needs an actual moving CHECK landmark; unknown/static hub axes cannot substitute' })
  }
  if (options.stage === 5 && video.playback.youtube?.status !== 'passed') video.failures.push({ code: 'official-player-unmeasured', reason: 'Final5% acceptance requires actual official YouTube playback/audio/compact checks' })
  if (!video.interaction || !Object.values(video.playback).some(result => result.status === 'passed')) video.failures.push({ code: 'interaction-unmeasured', reason: 'Actual original playback/audio/compact and paused manual native operation/orbit checks are required' })
  if (options.scoped) video.status = 'partial'
  else video.status = video.coverage.complete && !video.failures.length ? 'passed' : video.coverage.unavailableCensusSamples || !measurements.length ? 'unavailable' : 'failed'
  const measuredFailure = required.some(sample => sample.status === 'failed' || sample.measurements.some(item => item.status === 'failed')) || mandatoryClockFailures.length > 0 || diagnosticFailures.length > 0 || diagnosticClockFailures.length > 0
  video.stageMeasurement = { stage: options.stage, tolerancePx: 1920 * options.stage / 100, status: options.scoped ? 'unmeasured' : video.status === 'passed' ? 'passed' : measuredFailure || video.status === 'failed' ? 'failed' : 'unmeasured', scopedSamples: options.scoped ? { status: required.length && passed.length === required.length && missingCensusSamples === 0 && mandatory.length === selectedRows.length && !video.failures.length ? 'passed' : measuredFailure ? 'failed' : 'unavailable' } : null }
}

export async function verifySync(options = parseOptions(process.argv.slice(2))) {
  if (options.help) { console.log(HELP); return 0 }
  const startedAt = new Date().toISOString(), outputDirectory = resolve(options.output ?? resolve(WEB_ROOT, '.vite/verification-output', `stage-${options.stage}-${startedAt.replace(/[:.]/g, '-')}`))
  await mkdir(outputDirectory, { recursive: true })
  const report = { schemaVersion: 1, startedAt, finishedAt: null, status: 'unavailable', stage: options.stage, stageLadder: STAGES, scope: options.scoped ? 'time-scoped-diagnostic' : options.videos.length === 6 ? 'all-six-videos' : 'selected-videos', options, limits: { frameWidthPixels: 1920, frameHeightPixels: 1080, errorFrameWidthPercent: options.stage, sourceLandmarkPx: 1920 * options.stage / 100, videoModelClockSeconds: CLOCK_LIMIT, compactViewportPixels: [200, 200] }, model: { sha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT, integrity: 'unmeasured' }, interpretation: 'Chosen feasible hidden inputs are not historical recovery. Compact playback is approximate/unverified until this measured stage passes. Every integer second, authored/visible change and actual source view remains mandatory; missing/failed required measurements never pass. Extra interior observations are diagnostic: missing/inadmissible oracles do not add certification prerequisites, but independently admitted measured pixel counterexamples still fail the stage. GPU marker readback is actual render proof, not CPU projection; diagnostic markers alone do not certify every native surface. Narrow retained geometry exceptions remain uncertified.', videos: [], failures: [], builtAssets: [], browserLog: [], serverRequests: [] }
  const abort = new AbortController(), interrupt = () => abort.abort(new Error('Verification interrupted'))
  process.once('SIGINT', interrupt); process.once('SIGTERM', interrupt)
  let server, browser, context, page
  try {
    const referenceRoot = resolve(process.env.HARMONIC_REFERENCE_ROOT ?? resolve(WEB_ROOT, '.vite/reference-root'))
    report.builtAssets = await distManifest(resolve(WEB_ROOT, 'dist'))
    assert(report.builtAssets.find(asset => asset.path === 'models/harmonic-analyzer.glb')?.sha256 === MODEL_SHA256, 'Built model is missing or differs from the unchanged223MB native export')
    report.model.integrity = 'passed'
    server = await serveDist(resolve(WEB_ROOT, 'dist'), { referenceRoot, requests: report.serverRequests, signal: abort.signal, base: process.env.SIMULATOR_BASE })
    report.baseUrl = server.url
    const { chromium } = await import('playwright')
    const softwareGl = process.env.HARMONIC_SOFTWARE_GL === '1'
    report.rendererChoice = softwareGl ? 'explicit-swiftshader' : 'native-browser-default'
    browser = await chromium.launch({ executablePath: process.env.HARMONIC_CHROME ?? '/usr/bin/google-chrome', headless: !options.headed, args: [...(softwareGl ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : []), '--no-sandbox', '--disable-dev-shm-usage'], timeout: 30_000 })
    abort.signal.addEventListener('abort', () => void browser.close(), { once: true })
    context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 }); context.setDefaultTimeout(20_000)
    page = await context.newPage()
    page.on('pageerror', error => report.browserLog.push({ type: 'pageerror', reason: error.message }))
    report.browserVersion = browser.version()
    for (const id of options.videos) {
      const video = { videoId: id, status: 'unavailable', failures: [], samples: [], playback: {}, source: null, coverage: null, maxErrorPx: null, unavailableReasons: [] }
      report.videos.push(video)
      let census
      try {
        if (abort.signal.aborted) throw abort.signal.reason
        const record = await loadRecord(id, referenceRoot, abort.signal)
        video.source = { sha256: record.native.observedSha256, width: record.native.width, height: record.native.height, fps: record.native.fps, durationSeconds: record.native.durationSeconds, nativeFrameCount: record.native.nativeFrameCount, trackDigest: record.digest, nativeGeometryAssumptions: record.track.nativeGeometryAssumptions ?? record.observations.nativeGeometryAssumptions ?? [], geometricExceptionsInterpretation: 'Narrow retained source/native exceptions remain uncertified, never whole-view or landmark waivers.' }
        const staticControls = await staticSourceControls(record)
        video.source.staticMotionDiagnostics = staticControls.diagnostics
        video.shots = record.track.shots.map(shot => ({ id: shot.id, internalMechanismMotion: shot.internalMechanismMotion ?? 'unknown', internalMotionEvidence: shot.internalMotionEvidence ?? null, sourceStaticControls: staticControls.shots.get(shot.id) ?? null }))
        census = sourceCensus(record.observations, record.track, record.native, options)
        assert(census.selected.length > 0, 'Selected time window contains no source census samples')
        // Mandatory original images remain gating; optional interpolation probes
        // replay only new identities and report missing oracles diagnostically.
        await replayCensusImages(record, census, staticControls, video, abort.signal)
        const measurementPlayer = options.player === 'youtube' ? 'youtube' : 'local'
        const embed = await openRoute(page, server.url, record, measurementPlayer)
        video.route = embed.route
        video.webglRenderer = await page.evaluate(() => {
          const canvas = document.querySelector('#stage'), gl = canvas?.getContext('webgl2') ?? canvas?.getContext('webgl')
          if (!gl) throw new Error('Actual native model canvas has no WebGL context')
          const extension = gl.getExtension('WEBGL_debug_renderer_info')
          return { renderer: gl.getParameter(extension ? extension.UNMASKED_RENDERER_WEBGL : gl.RENDERER), vendor: gl.getParameter(extension ? extension.UNMASKED_VENDOR_WEBGL : gl.VENDOR), version: gl.getParameter(gl.VERSION), drawingBufferPixels: [gl.drawingBufferWidth, gl.drawingBufferHeight], canvasId: canvas.id }
        })
        // Playback checks are independent of landmark availability: useful measurement must still run after a UI failure.
        try { await playbackChecks(page, embed, record, video, outputDirectory) }
        catch (error) { if (video.playback[measurementPlayer]) Object.assign(video.playback[measurementPlayer], { status: 'failed', reason: error.message }); video.failures.push({ code: `${measurementPlayer}-playback`, reason: error.message }) }
        try { await pause(page, embed); await measureSamples(page, embed, record, census, video, report.limits.sourceLandmarkPx, outputDirectory) }
        catch (error) { video.failures.push({ code: 'source-measurement', reason: error.message }) }
        try { video.interaction = await interactionChecks(page, embed, id, outputDirectory) }
        catch (error) { video.failures.push({ code: 'manual-interaction', reason: error.message }) }
        if (options.player === 'both') {
          try { const official = await openRoute(page, server.url, record, 'youtube'); await playbackChecks(page, official, record, video, outputDirectory) }
          catch (error) { if (video.playback.youtube) Object.assign(video.playback.youtube, { status: 'failed', reason: error.message }); video.failures.push({ code: 'youtube-playback', reason: error.message }) }
        }
        finishVideo(video, census, options)
      } catch (error) { video.failures.push({ code: 'video-prerequisite', reason: error.message }); video.unavailableReasons.push({ reason: error.message }) }
      if (census) {
        const measuredTimes = new Set(video.samples.filter(sample => !sample.diagnosticOnly).map(sample => sample.timeSeconds.toFixed(6)))
        const unmeasured = census.selected.filter(row => !row.diagnosticOnly && !measuredTimes.has(row.timeSeconds.toFixed(6)))
        if (unmeasured.length) video.failures.push({ code: 'unmeasured-census', reason: `${unmeasured.length} selected mandatory samples were not measured` })
      }
      if (video.status !== 'passed') report.failures.push({ videoId: id, status: video.status, reasons: video.failures, unavailableSamples: video.coverage?.unavailableRequiredSamples ?? null })
      await writeFile(resolve(outputDirectory, `${id}.json`), `${JSON.stringify(video, null, 2)}\n`)
      console.log(JSON.stringify({ videoId: id, stage: options.stage, status: video.status, coverage: video.coverage, maxErrorPx: video.maxErrorPx, unavailableReasons: video.unavailableReasons.length }))
    }
    if (report.browserLog.some(item => item.type === 'pageerror')) report.failures.push({ code: 'unhandled-browser-error', reasons: report.browserLog })
    report.status = options.scoped ? 'partial' : report.videos.length === options.videos.length && report.videos.every(video => video.status === 'passed') && !report.failures.length ? 'passed' : report.videos.some(video => video.status === 'failed' || video.stageMeasurement?.status === 'failed') ? 'failed' : 'unavailable'
  } catch (error) { report.failures.push({ code: 'verification-prerequisite', reason: error.message }) }
  finally {
    for (const [name, value] of [['page', page], ['context', context], ['browser', browser], ['server', server]]) try { await value?.close() } catch (error) { report.failures.push({ code: `${name}-cleanup`, reason: error.message }) }
    process.removeListener('SIGINT', interrupt); process.removeListener('SIGTERM', interrupt)
    report.finishedAt = new Date().toISOString()
    if (report.status === 'passed' && report.failures.length) report.status = 'failed'
    const path = resolve(outputDirectory, 'report.json'); await writeFile(path, `${JSON.stringify(report, null, 2)}\n`)
    console.log(JSON.stringify({ status: report.status, scope: report.scope, stage: report.stage, tolerancePx: report.limits.sourceLandmarkPx, videoCount: report.videos.length, report: path }, null, 2))
  }
  return report.status === 'passed' ? 0 : 1
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { process.exitCode = await verifySync() }
  catch (error) { console.error(error.message); process.exitCode = 1 }
}
