import test from 'node:test'
import assert from 'node:assert/strict'
const { parseOptions, sourceCensus, finishVideo, seekSettlement, sourcePtsInShot, requireSourceViews, measureView, measureContours, sourceContourSidecar, playbackInterval, sourceSeedIndex, diagnosticReplayOutcome, requirePausedReview, compareCameraPose, normalizeVerificationReport, resolveVerificationReport, writeVerificationReport } = await import(process.env.HARMONIC_VERIFY_SYNC_MODULE ?? './verify-sync.mjs')
import { jsonDigest, sourceLayoutForViews } from './verify-reference.mjs'
import { mkdtemp, readFile, writeFile, rm, readdir } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

// These are decision-gate unit controls, NOT browser/source-fidelity evidence.
const native = { durationSeconds: 2.1, fps: 30, pts: Array.from({ length: 63 }, (_, index) => index / 30) }
const frame = (time, classification = 'machine') => ({ timeSeconds: time, decodedTimeSeconds: time, shotId: 'shot', classification, views: [{ id: 'main' }] })
const observations = { shots: [{ id: 'shot', startSeconds: 0, endSeconds: 2.1, classification: 'machine', hasCorrespondingMachine: true }], frames: [frame(0), frame(1), frame(2)], coverage: { changeTimesSeconds: [0.1, 0.2] } }

test('paused camera pose ignores normalization jitter but rejects actual translation, rotation and zoom', () => {
  const camera = { positionMetres: [1.4665951818671157, 1.0722987956210683, 2.0027832566537382], quaternion: [0, 0, 0, 1], verticalFovDegrees: 35 }
  const jitter = { ...camera, positionMetres: [camera.positionMetres[0], 1.07229879562107, camera.positionMetres[2]] }
  const comparison = compareCameraPose(camera, jitter)
  assert.equal(comparison.status, 'equivalent')
  assert.ok(comparison.positionMetres > 0 && comparison.positionMetres < 1e-9)
  assert.equal(compareCameraPose(camera, { ...jitter, quaternion: [0, 0, 0, -2], verticalFovDegrees: 35 + 1e-12 }).status, 'equivalent')
  assert.equal(compareCameraPose(camera, { ...camera, quaternion: [0, Math.sin(1e-12 / 2), 0, Math.cos(1e-12 / 2)] }).status, 'equivalent')
  const translated = compareCameraPose(camera, { ...camera, positionMetres: [camera.positionMetres[0] + 1e-6, ...camera.positionMetres.slice(1)] })
  assert.equal(translated.status, 'changed')
  assert.ok(translated.positionMetres > 1e-9)
  const angle = 1e-6
  const rotated = compareCameraPose(camera, { ...camera, quaternion: [0, Math.sin(angle / 2), 0, Math.cos(angle / 2)] })
  assert.equal(rotated.status, 'changed')
  assert.ok(Math.abs(rotated.rotationRadians - angle) < 1e-12)
  const zoomed = compareCameraPose(camera, { ...camera, verticalFovDegrees: 35.001 })
  assert.equal(zoomed.status, 'changed')
  assert.ok(zoomed.verticalFovDegrees > 1e-9)
})

test('invalid camera poses fail closed for both unchanged and orbit-changed gates', () => {
  const camera = { positionMetres: [0, 0, 1], quaternion: [0, 0, 0, 1], verticalFovDegrees: 35 }
  for (const invalid of [
    null,
    { ...camera, positionMetres: [0, 1] },
    { ...camera, positionMetres: [0, NaN, 1] },
    { ...camera, quaternion: [0, 0, 0, 0] },
    { ...camera, quaternion: [0, 0, 0, Infinity] },
    { ...camera, quaternion: [0, 0, 1] },
    { ...camera, verticalFovDegrees: NaN },
    { ...camera, verticalFovDegrees: 0 },
    { ...camera, verticalFovDegrees: 180 },
  ]) {
    assert.equal(compareCameraPose(camera, invalid).status, 'invalid')
    assert.equal(compareCameraPose(invalid, camera).status, 'invalid')
  }
})

test('stage percentages never reduce retained video or every-second coverage', () => {
  for (const stage of [50, 20, 10, 5]) {
    const options = parseOptions(['--stage', String(stage)])
    assert.equal(options.videos.length, 6)
    const census = sourceCensus(observations, { frames: observations.frames, coverage: { changeTimesSeconds: [] } }, native, options)
    assert.deepEqual(census.rows.filter(row => row.reasons.includes('every-second')).map(row => row.timeSeconds), [0, 1, 2])
  }
  assert.equal(parseOptions([]).stage, 5)
  assert.equal(parseOptions([]).player, 'both')
})

test('incremental runs select one video without requiring the other five', () => {
  const options = parseOptions(['--stage', '50', '--video', 'analysis', '--times', '1'])
  assert.deepEqual(options.videos, ['6dW6VYXp9HM'])
  assert.equal(options.player, 'local')
  const census = sourceCensus(observations, { frames: observations.frames, coverage: { changeTimesSeconds: [] } }, native, options)
  assert.deepEqual(census.selected.map(row => row.timeSeconds), [1])
  assert.deepEqual(census.rows.filter(row => row.reasons.includes('mid-interval')).map(row => row.timeSeconds), [])
  assert.equal(options.scoped, true)
})

test('meaningful compact change keys are required without reviving per-exposure certificates', () => {
  const track = { frames: [...observations.frames, frame(0.5)].sort((a, b) => a.timeSeconds - b.timeSeconds), coverage: { changeTimesSeconds: [0.5] } }
  const census = sourceCensus(observations, track, native, parseOptions(['--stage', '50']))
  assert.ok(census.rows.some(row => row.timeSeconds === 0.5 && row.reasons.includes('authored-change-point')))
  assert.ok(!census.rows.some(row => row.timeSeconds === 0.1 || row.timeSeconds === 0.2))
})

test('missing source samples and out-of-duration requests stay explicitly unavailable', () => {
  const options = parseOptions(['--video', 'analysis', '--times', '1,8'])
  const census = sourceCensus(observations, { frames: [frame(0)], coverage: {} }, native, options)
  assert.equal(census.selected[0].frame, null)
  assert.match(census.selected[0].unavailableReason, /Missing authored sample/)
  assert.equal(census.selected[1].frame, null)
  assert.match(census.selected[1].unavailableReason, /outside/)
})

const measurement = (anchorId, motion, status = 'passed') => ({ viewId: 'main', anchorId, motion, role: 'check', errorPx: status === 'passed' ? 20 : 1000, rawErrorPx: 19, errorFrameWidthPercent: status === 'passed' ? 20 / 1920 * 100 : 1000 / 1920 * 100, status })
function videoFixture() {
  return { failures: [], playback: { local: { status: 'passed' } }, interaction: { status: 'passed' }, samples: [{ timeSeconds: 0, sampleTimeSeconds: 0, reasons: ['every-second'], required: true, status: 'passed', unavailable: [], maxClockSkewSeconds: 0.1, measurements: [measurement('fixed', 'fixed'), measurement('moving', 'moving')] }] }
}
const censusFixture = { rows: [{ timeSeconds: 0, required: true, reasons: ['every-second'] }] }

test('missing exempt census samples cannot create a complete stage pass', () => {
  const video = videoFixture(), census = { rows: [...censusFixture.rows, { timeSeconds: 1, required: false, reasons: ['every-second'] }] }
  video.samples.push({ timeSeconds: 1, sampleTimeSeconds: null, reasons: ['every-second'], required: false, status: 'unavailable', unavailable: [{ reason: 'Missing source frame' }], measurements: [] })
  finishVideo(video, census, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.complete, false)
  assert.equal(video.coverage.unavailableCensusSamples, 1)
  assert.equal(video.status, 'unavailable')
  assert.equal(video.stageMeasurement.status, 'unmeasured')
})

test('a scoped successful measurement does not certify a whole-video stage', () => {
  const video = videoFixture()
  finishVideo(video, censusFixture, parseOptions(['--stage', '50', '--times', '0']))
  assert.equal(video.status, 'partial')
  assert.equal(video.coverage.complete, false)
  assert.equal(video.stageMeasurement.status, 'unmeasured')
  assert.equal(video.stageMeasurement.scopedSamples.status, 'passed')
})

test('measured failures remain failed even alongside unavailable landmarks', () => {
  const video = videoFixture()
  video.samples[0].status = 'unavailable'
  video.samples[0].measurements[1] = measurement('moving', 'moving', 'failed')
  video.samples[0].unavailable.push({ reason: 'Missing additional landmark' })
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.stageMeasurement.status, 'failed')
  assert.equal(video.maxErrorPx, 1000)
})

test('final5% stage cannot pass on a local-only original media check', () => {
  const video = videoFixture()
  finishVideo(video, censusFixture, parseOptions(['--player', 'local']))
  assert.notEqual(video.status, 'passed')
  assert.ok(video.failures.some(failure => failure.code === 'official-player-unmeasured'))
  assert.equal(video.stageMeasurement.tolerancePx, 96)
})

test('a new seek cannot pass merely because a later media clock equals the target', () => {
  const paused = mediaTime => ({ mediaTime, paused: true, seeking: false, readyState: 2, error: null })
  const observed = { sameElement: true, pre: paused(0), now: paused(1), events: [] }
  assert.equal(seekSettlement(observed, 1, 0.02).done, false)
  observed.events = [{ type: 'seeking', mediaTime: 1 }, { type: 'seeked', mediaTime: 1 }]
  assert.equal(seekSettlement(observed, 1, 0.02).done, true)
  observed.events = [{ type: 'seeked', mediaTime: 1 }, { type: 'seeking', mediaTime: 1 }]
  assert.equal(seekSettlement(observed, 1, 0.02).done, false)
  observed.events = []; observed.pre = paused(1)
  assert.equal(seekSettlement(observed, 1, 0.02).done, true)
})

test('moving CHECKs from one shot cannot certify another internally moving shot', () => {
  const video = videoFixture()
  video.samples[0].sourceShotId = 'moving-a'
  video.samples.push({ ...video.samples[0], timeSeconds: 1, sampleTimeSeconds: 1, sourceShotId: 'moving-b', measurements: [measurement('fixed-b', 'fixed')] })
  const census = { rows: [...censusFixture.rows, { timeSeconds: 1, required: true, reasons: ['every-second'] }] }
  finishVideo(video, census, parseOptions(['--stage', '50']))
  assert.notEqual(video.status, 'passed')
  assert.ok(video.failures.some(failure => failure.code === 'hard-moving-landmark-coverage' && failure.shotId === 'moving-b'))
})

test('source-backed static rigs retain distributed fixed checks instead of invented moving hubs', () => {
  const video = videoFixture()
  video.samples[0].sourceShotId = 'static-rig'
  video.samples[0].measurements = [measurement('fixed-left', 'fixed'), measurement('fixed-right', 'fixed')]
  video.shots = [{ id: 'static-rig', internalMechanismMotion: 'static', internalMotionEvidence: 'Source-only retained static mechanism observation; camera/turntable changes, internal bodies do not.', sourceStaticControls: { status: 'source-controls-verified' } }]
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.status, 'passed')
  assert.equal(video.landmarks.movingChecks, 0)
  assert.equal(video.motionCoverage[0].internalMechanismMotion, 'source-backed-static-rig')
  video.shots[0].sourceStaticControls = null
  video.failures = []
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.notEqual(video.status, 'passed')
  assert.ok(video.failures.some(failure => failure.code === 'hard-moving-landmark-coverage'))
})

test('compact-required endcards retain all source views despite a legacy non-machine label', () => {
  const legacy = { shots: [{ id: 'shot', startSeconds: 0, endSeconds: 2.1, classification: 'non-machine', hasCorrespondingMachine: false }], frames: [frame(0, 'non-machine'), frame(1, 'non-machine'), frame(2, 'non-machine')] }
  const authored = legacy.frames.map(frame => ({ ...frame, sourceMachineRequirement: 'required', views: [{ id: 'endcard-a' }, { id: 'endcard-b' }] }))
  const row = sourceCensus(legacy, { shots: legacy.shots, frames: authored }, native, parseOptions(['--times', '1'])).selected[0]
  assert.equal(row.required, true)
  assert.deepEqual(row.expectedViewIds, ['endcard-a', 'endcard-b'])
})

test('source PTS is half-open in its own shot, never rescued by the0.5s clock bound', () => {
  const shot = { id: 'shot', startSeconds: 0, endSeconds: 1, hasCorrespondingMachine: true }
  assert.equal(sourcePtsInShot(frame(0), shot), true)
  assert.equal(sourcePtsInShot({ ...frame(0.99), decodedTimeSeconds: 1 }, shot), false)
  const census = sourceCensus({ shots: [shot], frames: [frame(0.9)] }, { shots: [shot], frames: [{ ...frame(0.9), decodedTimeSeconds: 1 }] }, { ...native, durationSeconds: 1.1 }, parseOptions(['--times', '0.9']))
  assert.equal(census.selected[0].frame, null)
  assert.match(census.selected[0].unavailableReason, /half-open/)
})

test('mid-interval measurements use real independent source pixels, not interpolated oracle pixels', () => {
  const source = { ...observations, frames: [frame(0), { ...frame(0.5), landmarks: [{ anchorId: 'actual-source', pixel: [31, 47], role: 'check', status: 'observed', method: 'manual' }] }, frame(1), frame(2)] }
  const row = sourceCensus(source, { frames: observations.frames }, native, parseOptions(['--times', '0.5'])).selected[0]
  assert.equal(row.frame.measuredInterpolation, true)
  assert.deepEqual(row.frame.interpolationInterval, [0, 1])
  assert.equal(row.frame.decodedTimeSeconds, 0.5)
  assert.deepEqual(row.frame.landmarks[0].pixel, [31, 47])
  const missing = sourceCensus(observations, { frames: observations.frames }, native, parseOptions(['--times', '0.5'])).selected[0]
  assert.equal(missing.frame, null)
  assert.match(missing.unavailableReason, /oracle pixels are never interpolated/)
})

test('extra intermediate probes use exact observed exposures and stay diagnostic unless also mandatory', () => {
  const observed = { ...frame(0.47), landmarks: [{ anchorId: 'actual-source', pixel: [31, 47], role: 'check', status: 'observed', method: 'manual' }] }
  const source = { ...observations, frames: [frame(0), observed, frame(1), frame(2)] }
  const census = sourceCensus(source, { frames: observations.frames }, native, parseOptions(['--stage', '50']))
  const extra = census.rows.find(row => row.reasons.includes('mid-interval'))
  assert.equal(extra.timeSeconds, 0.47)
  assert.equal(extra.frame.decodedTimeSeconds, 0.47)
  assert.deepEqual(extra.frame.landmarks[0].pixel, [31, 47])
  assert.equal(extra.diagnosticOnly, true)
  assert.deepEqual(census.rows.filter(row => row.reasons.includes('every-second')).map(row => row.timeSeconds), [0, 1, 2])
  const mandatory = sourceCensus(source, { frames: observations.frames, coverage: { changeTimesSeconds: [0.47] } }, native, parseOptions(['--stage', '50'])).rows.find(row => row.timeSeconds === 0.47)
  assert.equal(mandatory.diagnosticOnly, false)
  assert.ok(mandatory.reasons.includes('authored-change-point'))
})

test('actual source membership changes remain mandatory even without an authored sample', () => {
  const inset = { ...frame(0.4), views: [{ id: 'main' }, { id: 'inset' }] }
  const source = { ...observations, frames: [frame(0), inset, { ...frame(1), views: inset.views }, { ...frame(2), views: inset.views }] }
  const row = sourceCensus(source, { frames: observations.frames }, native, parseOptions(['--stage', '50'])).rows.find(row => row.timeSeconds === 0.4)
  assert.equal(row.diagnosticOnly, false)
  assert.ok(row.reasons.includes('retained-layout-change'))
  assert.equal(row.frame, null)
})

test('optional probes without an admitted error cannot create an extra stage gate', () => {
  const video = videoFixture(), extra = { timeSeconds: 0.5, required: true, diagnosticOnly: true, reasons: ['mid-interval'] }
  video.samples.push({ ...extra, sampleTimeSeconds: 0.5, status: 'unavailable', unavailable: [{ reason: 'Diagnostic observation unavailable' }], measurements: [] })
  finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.complete, true)
  assert.equal(video.status, 'passed')
  assert.equal(video.coverage.diagnosticSamples.unavailable, 1)
  assert.equal(video.maxErrorPx, 20)
})

test('diagnostic success cannot replace a missing integer second or required measurements', () => {
  const video = videoFixture(), extra = { timeSeconds: 0.5, required: true, diagnosticOnly: true, reasons: ['mid-interval'] }
  video.samples.push({ ...video.samples[0], ...extra, sampleTimeSeconds: 0.5 })
  finishVideo(video, { rows: [...censusFixture.rows, extra, { timeSeconds: 1, required: true, reasons: ['every-second'] }] }, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.complete, false)
  assert.equal(video.coverage.missingCensusSamples, 1)
  assert.notEqual(video.status, 'passed')
  const missing = videoFixture()
  missing.samples[0].measurements = []
  finishVideo(missing, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(missing.coverage.complete, false)
  assert.notEqual(missing.stageMeasurement.status, 'passed')
})

test('diagnostic moving CHECKs cannot certify mandatory static-only measurements', () => {
  const video = videoFixture(), extra = { timeSeconds: 0.5, required: true, diagnosticOnly: true, reasons: ['mid-interval'] }
  video.samples[0].measurements = [measurement('fixed', 'fixed')]
  video.samples.push({ ...video.samples[0], ...extra, sampleTimeSeconds: 0.5, measurements: [measurement('moving-extra', 'moving')] })
  finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
  assert.notEqual(video.status, 'passed')
  assert.equal(video.landmarks.movingChecks, 0)
  assert.ok(video.failures.some(failure => failure.code === 'hard-moving-landmark-coverage'))
})

const sourceView = (id, rectSourcePixels = [0, 0, 1920, 1080]) => ({
  id, rectSourcePixels, presentation: 'native',
  camera: { positionMetres: [1, 1, 1], quaternion: [0, 0, 0, 1], verticalFovDegrees: 30 },
  input: { crankTurns: 0 },
})
const implicitFrame = time => { const result = frame(time); delete result.views; return result }

test('implicit legacy main is not an extra body on decomposed source panels', () => {
  const source = { ...observations, frames: [implicitFrame(0), implicitFrame(1), implicitFrame(2)] }
  const views = ['large-small', 'medium-medium', 'small-large'].map((id, index) => sourceView(id, [0, index * 360, 1920, 360]))
  const authored = source.frames.map(frame => ({ ...frame, views }))
  const row = sourceCensus(source, { frames: authored }, native, parseOptions(['--times', '1'])).selected[0]
  assert.deepEqual(row.expectedViewIds, views.map(view => view.id))
  requireSourceViews(row)
})

test('explicit source endcard views and newly visible dynamic insets cannot be omitted', () => {
  const views = Array.from({ length: 8 }, (_, index) => sourceView(`endcard-${index}`, [index % 4 * 480, Math.floor(index / 4) * 540, 480, 540]))
  const source = { ...observations, frames: observations.frames.map(frame => ({ ...frame, views })) }
  const authored = source.frames.map(frame => ({ ...frame, views: views.slice(0, 7) }))
  const row = sourceCensus(source, { frames: authored }, native, parseOptions(['--times', '1'])).selected[0]
  assert.deepEqual(row.expectedViewIds, views.map(view => view.id))
  assert.throws(() => requireSourceViews(row), /endcard-7/)
  const main = sourceView('main'), inset = sourceView('dynamic-inset', [1400, 0, 520, 400])
  const dynamic = { ...observations, frames: [{ ...frame(0), views: [main] }, { ...frame(1), views: [main, inset] }, { ...frame(2), views: [main, inset] }] }
  const dynamicRow = sourceCensus(dynamic, { frames: observations.frames.map(frame => ({ ...frame, views: [main] })) }, native, parseOptions(['--times', '1'])).selected[0]
  assert.throws(() => requireSourceViews(dynamicRow), /dynamic-inset/)
})

test('explicit full-view decomposition requires retained mapping evidence for every layer', () => {
  const main = sourceView('main')
  const source = { ...observations, frames: observations.frames.map(frame => ({ ...frame, views: [main] })) }
  const layers = ['outgoing', 'incoming'].map(id => ({ ...sourceView(id), composite: { mode: 'crossfade', groupId: 'fade', imageLayerId: id, opacity: 0.5 }, sourceViewIds: ['main'], sourceViewMappingEvidence: 'Retained original full-canvas main and independently inspected ordered dissolve layout' }))
  const rowAt = views => sourceCensus(source, { frames: source.frames.map(frame => ({ ...frame, views })) }, native, parseOptions(['--times', '1'])).selected[0]
  const declared = rowAt(layers)
  assert.deepEqual(declared.expectedViewIds, ['outgoing', 'incoming'])
  requireSourceViews(declared)
  const missing = rowAt(layers.map(({ sourceViewMappingEvidence, ...view }) => view))
  assert.ok(missing.expectedViewIds.includes('main'))
  assert.throws(() => requireSourceViews(missing), /main/)
  assert.throws(() => requireSourceViews(rowAt(layers.slice(1))), /main/)
})

test('intermediate source landmark view renames need unique source-layout identity', () => {
  const original = { ...frame(0.5), views: [sourceView('presenter-whole')], landmarks: [{ anchorId: 'actual-source', viewId: 'presenter-whole', pixel: [31, 47], role: 'check', status: 'observed', method: 'manual' }] }
  const source = { ...observations, frames: [{ ...frame(0), views: original.views }, original, { ...frame(1), views: original.views }, { ...frame(2), views: original.views }] }
  const rowAt = views => sourceCensus(source, { frames: observations.frames.map(frame => ({ ...frame, views })) }, native, parseOptions(['--times', '0.5'])).selected[0]
  const renamed = rowAt([sourceView('main')])
  assert.equal(renamed.frame.landmarks[0].viewId, 'main')
  assert.equal(renamed.frame.landmarks[0].originalViewId, 'presenter-whole')
  assert.deepEqual(renamed.frame.landmarks[0].pixel, [31, 47])
  const ambiguous = rowAt([sourceView('outgoing'), sourceView('incoming')])
  assert.deepEqual(ambiguous.frame.landmarks, [])
  assert.match(ambiguous.frame.viewMappingUnavailable[0].reason, /Ambiguous/)
  assert.throws(() => requireSourceViews(ambiguous), /presenter-whole/)
})

const sourceImage = (frameIndex, hash) => ({ frameIndex, sha256Bgr8: hash, pixelFormat: 'bgr8', width: 1920, height: 1080, sourceSha256: '1'.repeat(64) })
const manualSeedFrame = (fixture, timeSeconds = 0, decodedTimeSeconds = 0, viewId = 'main') => ({
  timeSeconds, decodedTimeSeconds, sourceImage: sourceImage(Math.round(decodedTimeSeconds * 30), 'manual-seed'),
  landmarks: [{ ...fixture.observations[3], method: 'manual', viewId, originalViewId: viewId }],
})

function measuredViewFixture() {
  const view = sourceView('main'), frame = { timeSeconds: 1, decodedTimeSeconds: 1, views: [view], sourceImage: sourceImage(30, 'actual-target') }
  const positions = [[100, 100], [900, 100], [100, 800], [900, 800]]
  const observations = positions.map((pixel, index) => ({ anchorId: `anchor-${index}`, role: index < 2 ? 'fit' : 'check', pixel, status: 'observed', method: 'manual', uncertaintyPx: 1 }))
  const anchors = new Map(observations.map((observed, index) => [observed.anchorId, { kind: 'physical-feature', partPath: `native/part-${index}`, partLocalMetres: [0, 0, 0], correspondenceEvidence: 'Independently identified physical feature', motion: index === 2 ? 'moving' : 'fixed' }]))
  const layout = [{ viewId: 'main', rectSourcePixels: view.rectSourcePixels, presentation: 'native', composite: { mode: 'opaque' } }]
  const capture = { method: 'gpu-readback', status: 'captured', visibilityMode: 'depth-off-landmark-projection', viewId: 'main', timeSeconds: 1, sourceLayout: layout, resolvedImagePlaneWarp: null, landmarks: observations.map(observed => ({ id: observed.anchorId, state: 'rendered', sourcePixels: observed.pixel, canvasPixels: observed.pixel, uncertaintySourcePixels: 0.5 })) }
  const mechanism = { method: 'actual-native-mechanism-solve', status: 'rendered', viewId: 'main', timeSeconds: 1, sourceDrawRevision: 1, channelAnglesRad: Array(20).fill(0), input: view.input, sourceLayout: layout, resolvedImagePlaneWarp: null }
  const response = { captures: [{ viewId: 'main', capture, mechanism }], actual: { views: [{ ...view, sourceLayout: layout, resolvedImagePlaneWarp: null }] }, native: { mediaTime: 1 }, canvas: { tag: 'CANVAS', width: 1920, height: 1080, clientWidth: 1920, clientHeight: 1080, devicePixelRatio: 1 } }
  return { view, frame, observations, anchors, response, capture, seeds: new Map() }
}
const measureFixture = fixture => measureView(fixture.view, fixture.response, fixture.frame, fixture.observations, 96, fixture.anchors, fixture.seeds)

test('schema template matching admits only independent seed and actual correlation provenance', () => {
  const fixture = measuredViewFixture(), observed = fixture.observations[3]
  observed.method = 'template-match'
  observed.trackingEvidence = { seedTimeSeconds: 0, reacquiredFromActualPixels: true, wholeSourceViewCorrelation: 0.998, sourcePatchCorrelation: 0.97, sourceSha256Bgr8: 'actual-target' }
  fixture.seeds = sourceSeedIndex([manualSeedFrame(fixture)])
  const admitted = measureFixture(fixture)
  assert.equal(admitted.measured.length, 4)
  assert.deepEqual(admitted.excluded, [])
  for (const mutate of [
    evidence => { delete evidence.reacquiredFromActualPixels },
    evidence => { evidence.wholeSourceViewCorrelation = 0.9979 },
    evidence => { evidence.sourcePatchCorrelation = 0.9699 },
  ]) {
    const copy = structuredClone(fixture)
    mutate(copy.observations[3].trackingEvidence)
    const result = measureFixture(copy)
    assert.equal(result.measured.length, 3)
    assert.equal(result.excluded[0].reasonCode, 'template-provenance')
  }
  fixture.seeds.clear()
  assert.equal(measureFixture(fixture).excluded[0].reasonCode, 'template-provenance')
})

test('source method exclusions stay separate and require distributed admitted CHECK coverage', () => {
  const fixture = measuredViewFixture()
  fixture.observations[3].method = 'unsupported-source-technique'
  const result = measureFixture(fixture)
  assert.equal(result.measured.length, 3)
  assert.equal(result.excluded[0].status, 'source-inadmissible')
  assert.deepEqual(result.unavailable, [])
  const insufficient = structuredClone(fixture)
  insufficient.observations[2].method = 'unsupported-source-technique'
  assert.match(measureFixture(insufficient).unavailable[0].reason, /three distributed/)
  const collinear = structuredClone(fixture)
  collinear.observations[2].pixel = [500, 100]
  collinear.capture.landmarks[2].sourcePixels = [500, 100]
  collinear.capture.landmarks[2].canvasPixels = [500, 100]
  assert.match(measureFixture(collinear).unavailable[0].reason, /three distributed/)
})

test('missing actual pixels or native bodies and unrendered or masked GPU points remain blocking', () => {
  for (const mutate of [
    fixture => { fixture.observations[3].pixel = null },
    fixture => { fixture.anchors.get('anchor-3').partPath = null },
    fixture => { fixture.capture.landmarks[3].state = 'unavailable' },
    fixture => { fixture.capture.landmarks[3].sourcePixels = [1921, 800] },
    fixture => { fixture.capture.sourceLayout.push({ viewId: 'inset', rectSourcePixels: [850, 750, 200, 200], composite: { mode: 'opaque' } }) },
  ]) {
    const fixture = measuredViewFixture()
    fixture.observations[3].method = 'unsupported-source-technique'
    mutate(fixture)
    const result = measureFixture(fixture)
    assert.deepEqual(result.excluded, [])
    assert.equal(result.unavailable.length, 1)
    assert.ok(['source-unavailable', 'unmeasured-native'].includes(result.unavailable[0].status))
  }
  const noOracle = measuredViewFixture()
  assert.throws(() => measureView(noOracle.view, noOracle.response, noOracle.frame, [], 96, noOracle.anchors), /no independently observed landmarks/)
})

test('stale source evidence is excluded but measured pixel errors still fail', () => {
  const fixture = measuredViewFixture()
  fixture.observations[3].method = 'image-edge'
  fixture.observations[3].measurementEvidence = { sourceImage: { sha256Bgr8: 'different-exposure' } }
  fixture.capture.landmarks[2].sourcePixels = [1200, 800]
  fixture.capture.landmarks[2].canvasPixels = [1200, 800]
  const result = measureFixture(fixture)
  assert.equal(result.excluded[0].reasonCode, 'measurement-image-binding')
  assert.equal(result.measured.find(item => item.anchorId === 'anchor-2').status, 'failed')
  const video = videoFixture()
  Object.assign(video.samples[0], { measurements: result.measured, excluded: result.excluded, unavailable: result.unavailable, status: 'failed' })
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.stageMeasurement.status, 'failed')
  assert.equal(video.landmarks.measured, 3)
  assert.equal(video.sourceLandmarkExclusions.mandatory, 1)
})

test('playback chooses a complete required same-shot window instead of crossing legitimate no-machine cuts', () => {
  const shots = [
    { id: 'short', startSeconds: 0, endSeconds: 1, classification: 'machine' },
    { id: 'hold', startSeconds: 1, endSeconds: 5, classification: 'non-machine', hasCorrespondingMachine: false },
    { id: 'long', startSeconds: 5, endSeconds: 15, classification: 'machine' },
  ]
  const sample = (time, shotId, complete = true) => ({ ...frame(time), shotId, classification: shotId === 'hold' ? 'non-machine' : 'machine', views: complete ? [sourceView('main')] : [] })
  const frames = [sample(0, 'short'), sample(1, 'hold', false), sample(5, 'long'), sample(8, 'long', false), sample(9, 'long'), sample(12, 'long')]
  const interval = playbackInterval({ track: { shots, frames }, native: { durationSeconds: 15 } })
  assert.equal(interval.frame.timeSeconds, 9)
  assert.equal(interval.endSeconds, 15)
  assert.equal(interval.availableSeconds, 6)
  assert.equal(playbackInterval({ track: { shots: shots.slice(0, 2), frames: frames.slice(0, 2) }, native: { durationSeconds: 15 } }), null)
})

test('a passed summary cannot hide failed pixels or an unmeasured mandatory clock', () => {
  for (const mutate of [
    video => { video.samples[0].measurements[1].status = 'failed' },
    video => { video.samples[0].maxClockSkewSeconds = null },
  ]) {
    const video = videoFixture()
    mutate(video)
    finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
    assert.equal(video.coverage.complete, false)
    assert.notEqual(video.status, 'passed')
    assert.notEqual(video.stageMeasurement.status, 'passed')
  }
})

test('an admitted diagnostic pixel counterexample still fails the stage without supplying mandatory coverage', () => {
  const video = videoFixture(), extra = { timeSeconds: 0.5, required: true, diagnosticOnly: true, reasons: ['mid-interval'] }
  video.samples.push({ ...extra, sampleTimeSeconds: 0.5, status: 'failed', unavailable: [], measurements: [measurement('diagnostic-moving', 'moving', 'failed')], maxClockSkewSeconds: 0.1 })
  finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.complete, true)
  assert.equal(video.landmarks.movingChecks, 1)
  assert.equal(video.diagnosticLandmarks.failed, 1)
  assert.equal(video.maxErrorPx, 1000)
  assert.equal(video.status, 'failed')
  assert.equal(video.stageMeasurement.status, 'failed')
  assert.ok(video.failures.some(failure => failure.code === 'diagnostic-pixel-counterexample'))
})

test('template seed identity remains the original source view after an evidenced compact rename', () => {
  const fixture = measuredViewFixture(), observed = fixture.observations[3]
  observed.method = 'template-match'
  observed.originalViewId = 'presenter-whole'
  observed.trackingEvidence = { seedTimeSeconds: 0, reacquiredFromActualPixels: true, wholeSourceViewCorrelation: 1, sourcePatchCorrelation: 1 }
  fixture.seeds = sourceSeedIndex([manualSeedFrame(fixture, 0, 0, 'presenter-whole')])
  assert.equal(measureFixture(fixture).measured.length, 4)
  fixture.seeds.get('0/presenter-whole/anchor-3').role = 'fit'
  assert.equal(measureFixture(fixture).excluded[0].reasonCode, 'template-provenance')
  fixture.seeds.clear()
  fixture.seeds = sourceSeedIndex([manualSeedFrame(fixture)])
  assert.equal(measureFixture(fixture).excluded[0].reasonCode, 'template-provenance')
})

test('a missing selected mandatory sample cannot be called a successful scoped measurement', () => {
  const video = videoFixture(), required = { timeSeconds: 1, required: true, reasons: ['requested-sample'] }
  const rows = [...censusFixture.rows, required]
  finishVideo(video, { rows, selected: rows }, parseOptions(['--stage', '50', '--times', '0,1']))
  assert.equal(video.coverage.missingCensusSamples, 1)
  assert.equal(video.stageMeasurement.scopedSamples.status, 'unavailable')
  assert.equal(video.stageMeasurement.status, 'unmeasured')
})

test('authored source landmark aliases also require same-exposure layout evidence', () => {
  const source = { ...observations, frames: observations.frames.map(frame => ({ ...frame, views: [sourceView('presenter-whole')] })) }
  const authored = source.frames.map(frame => ({ ...frame, views: [sourceView('main')], landmarks: [{ anchorId: 'actual-source', viewId: 'presenter-whole', pixel: [31, 47], role: 'check', status: 'observed', method: 'manual' }] }))
  const row = sourceCensus(source, { frames: authored }, native, parseOptions(['--times', '1'])).selected[0]
  assert.equal(row.frame.landmarks[0].viewId, 'main')
  assert.equal(row.frame.landmarks[0].originalViewId, 'presenter-whole')
  assert.deepEqual(row.frame.landmarks[0].pixel, [31, 47])
  requireSourceViews(row)
  const unknown = structuredClone(row)
  unknown.frame.landmarks[0].viewId = 'undeclared-dynamic-view'
  assert.throws(() => requireSourceViews(unknown), /undeclared-dynamic-view/)
})

test('tracked seeds admit declared nominal and decoded aliases of the exact original exposure and view', () => {
  for (const method of ['optical-flow', 'template-match']) for (const [nominal, decoded] of [[3, 3.003], [20, 19.9866], [95, 94.9949]]) {
    const fixture = measuredViewFixture(), observed = fixture.observations[3]
    observed.method = method
    observed.originalViewId = 'presenter-whole'
    observed.trackingEvidence = { seedTimeSeconds: nominal, forwardBackwardErrorPx: 0.1, seedPatchCorrelation: 0.99, adjacentPatchCorrelation: 0.99, reacquiredFromActualPixels: true, wholeSourceViewCorrelation: 1, sourcePatchCorrelation: 1 }
    const seedFrame = manualSeedFrame(fixture, nominal, decoded, 'presenter-whole')
    fixture.seeds = sourceSeedIndex([seedFrame])
    for (const seedTimeSeconds of [nominal, decoded]) {
      observed.trackingEvidence = { ...observed.trackingEvidence, seedTimeSeconds, seedDecodedFrameIndex: seedFrame.sourceImage.frameIndex, seedSourceImage: seedFrame.sourceImage }
      assert.equal(measureFixture(fixture).measured.length, 4)
      assert.deepEqual(measureFixture(fixture).excluded, [])
    }
    for (const mutate of [
      copy => { copy.observations[3].trackingEvidence.seedTimeSeconds = decoded + 0.000001 },
      copy => { copy.observations[3].trackingEvidence.seedTimeSeconds = nominal + 0.5 },
      copy => { copy.observations[3].trackingEvidence.seedDecodedFrameIndex = seedFrame.sourceImage.frameIndex + 1 },
      copy => { copy.observations[3].trackingEvidence.seedSourceImage = { ...seedFrame.sourceImage, sha256Bgr8: 'different-seed-image' } },
      copy => { copy.frame.sourceImage.sourceSha256 = '2'.repeat(64) },
      copy => { delete copy.observations[3].originalViewId },
    ]) {
      const copy = structuredClone(fixture)
      mutate(copy)
      const result = measureFixture(copy)
      assert.equal(result.measured.length, 3)
      assert.equal(result.excluded[0].reasonCode, method === 'optical-flow' ? 'flow-provenance' : 'template-provenance')
    }
    for (const mutate of [
      copy => { copy.sourceImage.sha256Bgr8 = 'contradictory-seed-image' },
      copy => { copy.sourceImage.frameIndex++ },
      copy => { copy.landmarks[0].pixel[0]++ },
      copy => { copy.landmarks[0].role = 'fit' },
    ]) {
      const contradictory = structuredClone(seedFrame)
      mutate(contradictory)
      // A later repeat must not resurrect either contradictory alias.
      fixture.seeds = sourceSeedIndex([seedFrame, contradictory, seedFrame])
      for (const seedTimeSeconds of [nominal, decoded]) {
        observed.trackingEvidence.seedTimeSeconds = seedTimeSeconds
        const result = measureFixture(fixture)
        assert.equal(result.measured.length, 3)
        assert.equal(result.excluded[0].reasonCode, method === 'optical-flow' ? 'flow-provenance' : 'template-provenance')
      }
    }
  }
})

test('a nominal/decoded alias collision fails closed only for its contradictory identity', () => {
  const fixture = measuredViewFixture(), observed = fixture.observations[3]
  observed.method = 'optical-flow'
  observed.trackingEvidence = { seedTimeSeconds: 3.003, forwardBackwardErrorPx: 0.1, seedPatchCorrelation: 0.99, adjacentPatchCorrelation: 0.99 }
  const first = manualSeedFrame(fixture, 3, 3.003), second = manualSeedFrame(fixture, 3.003, 3.04)
  fixture.seeds = sourceSeedIndex([first, second, first])
  assert.equal(measureFixture(fixture).excluded[0].reasonCode, 'flow-provenance')
  for (const [seedTimeSeconds, seedSourceImage] of [[3, first.sourceImage], [3.04, second.sourceImage]]) {
    observed.trackingEvidence = { ...observed.trackingEvidence, seedTimeSeconds, seedSourceImage, seedDecodedFrameIndex: seedSourceImage.frameIndex }
    assert.equal(measureFixture(fixture).measured.length, 4)
    assert.deepEqual(measureFixture(fixture).excluded, [])
  }
})

test('finite diagnostic timing counterexamples fail even when pixels pass or no machine measurement is required', () => {
  for (const required of [true, false]) {
    const video = videoFixture(), extra = { timeSeconds: 0.5, required, diagnosticOnly: true, reasons: ['mid-interval'] }
    video.samples.push({ ...extra, sampleTimeSeconds: 0.5, status: required ? 'failed' : 'unavailable', unavailable: [], measurements: required ? [measurement('diagnostic-moving', 'moving')] : [], maxClockSkewSeconds: 0.5001 })
    finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
    assert.equal(video.coverage.complete, true)
    assert.equal(video.diagnosticLandmarks.failed, 0)
    assert.equal(video.maxClockSkewSeconds, 0.5001)
    assert.equal(video.stageMeasurement.status, 'failed')
    assert.ok(video.failures.some(failure => failure.code === 'diagnostic-clock-counterexample'))
  }
})

test('missing, non-finite and within-bound diagnostic timing do not become fabricated counterexamples', () => {
  for (const maxClockSkewSeconds of [null, undefined, NaN, Infinity, 0.5]) {
    const video = videoFixture(), extra = { timeSeconds: 0.5, required: false, diagnosticOnly: true, reasons: ['mid-interval'] }
    video.samples.push({ ...extra, sampleTimeSeconds: 0.5, status: 'unavailable', unavailable: [{ reason: 'No independent diagnostic oracle' }], measurements: [], maxClockSkewSeconds })
    finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
    assert.equal(video.status, 'passed')
    assert.equal(video.stageMeasurement.status, 'passed')
    assert.ok(!video.failures.some(failure => failure.code === 'diagnostic-clock-counterexample'))
  }
})

test('stale paused model clocks are retained before reference-state and nominal-time rejection', () => {
  for (const required of [true, false]) for (const diagnosticOnly of [true, false]) {
    const actual = { mode: 'reference-review', playerState: 'paused', modelTime: 1, referenceState: 'unavailable' }
    const native = { paused: true, seeking: false, mediaTime: 2 }
    let failure
    try { requirePausedReview(actual, native, { timeSeconds: 2 }, required) }
    catch (error) { failure = error }
    assert.match(failure.message, /clock exceeds/)
    assert.equal(failure.clockSkewSeconds, 1)
    assert.equal(failure.nativeMediaTime, 2)
    const video = videoFixture(), extra = { timeSeconds: 2, required, diagnosticOnly, reasons: ['mid-interval'] }
    video.samples.push({ ...extra, sampleTimeSeconds: 2, status: 'failed', unavailable: [{ reason: failure.message }], measurements: [], maxClockSkewSeconds: failure.clockSkewSeconds })
    finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
    assert.equal(video.stageMeasurement.status, 'failed')
    const named = video.failures.find(item => item.code === `${diagnosticOnly ? 'diagnostic' : 'mandatory'}-clock-counterexample`)
    assert.equal(named.measuredSamples, 1)
    assert.equal(named.maxClockSkewSeconds, 1)
    assert.deepEqual(named.timeSeconds, [2])
  }
})

test('finite mandatory clocks gate exempt samples despite other unavailable census rows', () => {
  for (const scoped of [false, true]) {
    const video = videoFixture(), extra = { timeSeconds: 1, required: false, reasons: ['every-second'] }
    const missing = { timeSeconds: 2, required: false, reasons: ['every-second'] }
    video.samples.push({ ...extra, sampleTimeSeconds: 1, status: 'failed', unavailable: [{ reason: 'Clock exceeded' }], measurements: [], maxClockSkewSeconds: 0.5001 })
    video.samples.push({ ...missing, sampleTimeSeconds: null, status: 'unavailable', unavailable: [{ reason: 'Missing source frame' }], measurements: [] })
    const rows = [...censusFixture.rows, extra, missing]
    finishVideo(video, { rows, selected: rows }, parseOptions(['--stage', '50', ...(scoped ? ['--times', '0,1,2'] : [])]))
    assert.equal(video.coverage.unavailableCensusSamples, 1)
    assert.equal(video.coverage.complete, false)
    assert.equal(scoped ? video.stageMeasurement.scopedSamples.status : video.stageMeasurement.status, 'failed')
    assert.ok(video.failures.some(item => item.code === 'mandatory-clock-counterexample'))
  }
})

test('unknown and within-bound mandatory clocks do not fabricate timing counterexamples', () => {
  for (const maxClockSkewSeconds of [null, undefined, NaN, Infinity, 0.5]) {
    const video = videoFixture(), extra = { timeSeconds: 1, required: false, reasons: ['every-second'] }
    video.samples.push({ ...extra, sampleTimeSeconds: 1, status: 'unavailable', unavailable: [{ reason: 'Missing source oracle' }], measurements: [], maxClockSkewSeconds })
    finishVideo(video, { rows: [...censusFixture.rows, extra] }, parseOptions(['--stage', '50']))
    assert.equal(video.stageMeasurement.status, 'unmeasured')
    assert.ok(!video.failures.some(item => item.code === 'mandatory-clock-counterexample'))
  }
})

test('paused review retains within-bound skew on stale-state errors without inventing unknown clocks', () => {
  for (const modelTime of [1.5, 2, undefined, NaN, Infinity]) {
    const actual = { mode: 'reference-review', playerState: 'paused', modelTime, referenceState: 'unavailable' }
    assert.throws(() => requirePausedReview(actual, { paused: true, seeking: false, mediaTime: 2 }, { timeSeconds: 2 }), error => {
      assert.match(error.message, /no current native draw/)
      assert.equal(Object.hasOwn(error, 'clockSkewSeconds'), Number.isFinite(modelTime))
      if (Number.isFinite(modelTime)) assert.equal(error.clockSkewSeconds, Math.abs(modelTime - 2))
      return true
    })
  }
})

test('a bad diagnostic image does not erase an unrelated admitted pixel counterexample in the same decode batch', () => {
  const good = jsonDigest(sourceImage(15, '3'.repeat(64))), bad = jsonDigest(sourceImage(15, '4'.repeat(64)))
  const result = { verifiedImageDigests: [good], imageFailures: [{ imageDigest: bad, reason: 'Decoded source-image hash mismatch' }] }
  const goodOutcome = diagnosticReplayOutcome([good], result), badOutcome = diagnosticReplayOutcome([bad], result)
  assert.equal(goodOutcome.status, 'passed')
  assert.equal(badOutcome.status, 'unavailable')
  assert.match(badOutcome.reason, /hash mismatch/)
  assert.equal(diagnosticReplayOutcome([good, bad], result).status, 'unavailable')
  assert.equal(diagnosticReplayOutcome(['unverified-identity'], result).status, 'unavailable')
  assert.equal(diagnosticReplayOutcome([good], { verifiedImageDigests: [good], imageFailures: [{ imageDigest: good, reason: 'Conflicting verification result' }] }).status, 'unavailable')
  const video = videoFixture(), extra = { timeSeconds: 0.5, required: true, diagnosticOnly: true, reasons: ['mid-interval'] }
  video.samples.push({ ...extra, sampleTimeSeconds: 0.5, sourceImageReplay: goodOutcome, status: 'failed', unavailable: [], measurements: [measurement('diagnostic-moving', 'moving', 'failed')], maxClockSkewSeconds: 0.1 })
  video.samples.push({ ...extra, timeSeconds: 0.7, sampleTimeSeconds: null, sourceImageReplay: badOutcome, status: 'unavailable', unavailable: [{ reason: badOutcome.reason }], measurements: [] })
  finishVideo(video, { rows: [...censusFixture.rows, extra, { ...extra, timeSeconds: 0.7 }] }, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.complete, true)
  assert.equal(video.diagnosticLandmarks.failed, 1)
  assert.equal(video.stageMeasurement.status, 'failed')
})

function playbackMotionFixture() {
  const bankFrame = (time, x) => ({
    ...frame(time), shotId: 'bank', views: [{ ...sourceView('main'), cameraProvenance: { kind: 'source-transfer', family: 'bank' } }],
    sourceImage: sourceImage(time * 30, `bank-${time}`),
    landmarks: [{ anchorId: 'cap', viewId: 'main', role: 'check', status: 'observed', pixel: [x, 100], method: 'manual', uncertaintyPx: 2 }],
  })
  const montageFrame = time => ({
    ...frame(time, 'non-machine'), shotId: 'montage', views: [{ ...sourceView('main'), cameraProvenance: { kind: 'source-transfer', family: 'bank' }, input: { crankTurns: time } }],
    sourceImage: sourceImage(time * 30, `montage-${time}`), landmarks: [],
  })
  return {
    track: {
      shots: [{ id: 'bank', startSeconds: 0, endSeconds: 5, classification: 'machine' }, { id: 'montage', startSeconds: 5, endSeconds: 25, classification: 'non-machine', hasCorrespondingMachine: true }],
      frames: [bankFrame(0, 100), bankFrame(1, 180), bankFrame(4, 180), montageFrame(5), montageFrame(10), montageFrame(20)],
      anchors: [{ id: 'cap', kind: 'physical-feature', partPath: 'native/cap', partLocalMetres: [0, 0, 0], correspondenceEvidence: 'Independent visible cap feature' }],
    },
    observations: { frames: [] }, native: { durationSeconds: 25 },
  }
}

test('playback prefers observed visible source motion over a longer montage with only transferred hidden-input changes', () => {
  const interval = playbackInterval(playbackMotionFixture())
  assert.equal(interval.frame.shotId, 'bank')
  assert.equal(interval.frame.timeSeconds, 0)
  assert.equal(interval.availableSeconds, 5)
  assert.equal(interval.motionEvidence.kind, 'independently-observed-source-landmark-motion')
  assert.deepEqual(interval.motionEvidence.sourcePixelsBefore, [100, 100])
  assert.deepEqual(interval.motionEvidence.sourcePixelsAfter, [180, 100])
})

test('inadmissible, reused-exposure or sub-uncertainty points cannot fabricate a visible playback-motion preference', () => {
  for (const mutate of [
    record => { for (const frame of record.track.frames.slice(0, 3)) frame.landmarks[0].method = 'unsupported-method' },
    record => { for (const frame of record.track.frames.slice(0, 3)) frame.sourceImage = record.track.frames[0].sourceImage },
    record => { record.track.frames[1].landmarks[0].pixel = [103, 100] },
  ]) {
    const record = playbackMotionFixture()
    mutate(record)
    const interval = playbackInterval(record)
    assert.equal(interval.frame.shotId, 'montage')
    assert.equal(interval.motionEvidence, null)
  }
})

test('visible source motion cannot override the complete same-shot minimum playback duration', () => {
  const record = playbackMotionFixture()
  record.track.shots[0].endSeconds = 2.5
  const interval = playbackInterval(record)
  assert.equal(interval.frame.shotId, 'montage')
  assert.ok(interval.availableSeconds >= 3)
})

function contourFixture(sourceDrawRevision = 1) {
  const fixture = measuredViewFixture(), { view, frame, response, capture, anchors } = fixture
  frame.sourceImage = sourceImage(30, 'a'.repeat(64))
  const check = { id: 'right-exterior', role: 'check', partPath: 'harmonic-analyzer/channel/connecting-rod-20',
    sourceContourPixels: [[100.5, 100.5], [120.5, 100.5], [140.5, 100.5]], uncertaintyPx: 3,
    measurementEvidence: { sourceImage: frame.sourceImage, evidence: 'Source-only partial right exterior edge; original endpoints retained.' } }
  frame.contourChecks = [{ viewId: 'main', originalViewId: 'main', decodedTimeSeconds: 1, sourceImage: frame.sourceImage, check }]
  const layout = sourceLayoutForViews([view]), mechanism = response.captures[0].mechanism
  capture.sourceLayout = layout; mechanism.sourceLayout = layout; response.actual.views[0].sourceLayout = layout
  capture.sourceOpacity = 1; capture.destinationCellSourcePixels = [1, 1]; capture.nativeViewportBackingPixels = null
  capture.sourceDrawRevision = sourceDrawRevision; mechanism.sourceDrawRevision = sourceDrawRevision
  Object.assign(response.actual, { mode: 'reference-review', playerState: 'paused', modelTime: 1, sourceDrawRevision, sourceDrawTimeSeconds: 1 })
  const part = { partPath: check.partPath, status: 'visible', pixelCount: 1024, contourPixelCount: 40,
    contourSourcePixels: [[103.5, 104.5], [120.5, 100.5], [140.5, 100.5], [1800.5, 900.5]], uncertaintySourcePixels: 2 }
  const visibility = { method: 'gpu-readback', visibilityMode: 'depth-tested-native-surfaces', status: 'captured', viewId: 'main', timeSeconds: 1, sourceDrawRevision,
    rectSourcePixels: view.rectSourcePixels, presentation: view.presentation, sourceOpacity: 1, camera: { ...view.camera, principalPointViewportPixels: [960, 540] },
    sourceLayout: layout, resolvedImagePlaneWarp: null, nativeViewportBackingPixels: null, destinationCellSourcePixels: [1, 1], parts: [part] }
  response.captures[0].partVisibility = visibility
  response.nativePartBindings = [{ partPath: check.partPath, binding: { partPath: check.partPath, bindingId: 'connectingRods', kind: 'indexed', motion: 'rod', stationIndex: 19 } }]
  anchors.set('rod-motion', { id: 'rod-motion', partPath: check.partPath, motion: 'moving', correspondenceEvidence: 'Existing identified Rod20 motion ancestry' })
  return { ...fixture, check, part, visibility }
}
const measureContourFixture = (fixture, tolerancePx = 10) => measureContours(fixture.view, fixture.response, fixture.frame, tolerancePx, fixture.anchors)

test('partial contour uses directed maximum actual sample distance and additive source-global bounds', () => {
  const fixture = contourFixture(), result = measureContourFixture(fixture), measured = result.measured[0]
  assert.deepEqual(result.unavailable, [])
  assert.equal(measured.rawErrorPx, 5)
  assert.equal(measured.errorPx, 10)
  assert.equal(measured.status, 'passed')
  assert.deepEqual(measured.worstSourcePixel, [100.5, 100.5])
  assert.deepEqual(measured.nearestNativePixel, [103.5, 104.5])
  assert.equal(measureContourFixture(fixture, 9.999).measured[0].status, 'failed')
  fixture.part.contourSourcePixels = fixture.part.contourSourcePixels.slice(1)
  assert.equal(measureContourFixture(fixture).measured[0].rawErrorPx, 20)
})

test('warped contour bounds stay source-global and unsupported localization footprints refuse measurement', () => {
  const fixture = contourFixture()
  const warp = { kind: 'homography', unwarpedViewportPixels: [960, 540], cornersSourcePixels: [[0, 0], [1920, 0], [1920, 1080], [0, 1080]] }
  fixture.view.imagePlaneWarp = warp; fixture.response.actual.views[0].imagePlaneWarp = warp
  const layout = sourceLayoutForViews([fixture.view]), resolved = layout[0].resolvedImagePlaneWarp
  for (const receipt of [fixture.visibility, fixture.capture, fixture.response.captures[0].mechanism, fixture.response.actual.views[0]]) {
    receipt.sourceLayout = layout; receipt.resolvedImagePlaneWarp = resolved
  }
  fixture.visibility.camera.principalPointViewportPixels = [480, 270]
  fixture.visibility.nativeViewportBackingPixels = [960, 540]; fixture.capture.nativeViewportBackingPixels = [960, 540]
  fixture.part.uncertaintySourcePixels = 6
  const result = measureContourFixture(fixture, 14)
  assert.deepEqual(result.unavailable, [])
  assert.equal(result.measured[0].rawErrorPx, 5)
  assert.equal(result.measured[0].sourceUncertaintyPx, 3)
  assert.equal(result.measured[0].rasterUncertaintyPx, 6)
  assert.equal(result.measured[0].errorPx, 14)
  fixture.check.sourceContourPixels = [[1, 100], [2, 100]]
  assert.equal(measureContourFixture(fixture).measured.length, 0)
  assert.match(measureContourFixture(fixture).unavailable[0].reason, /localization footprint/)
})

test('contour native evidence refuses another part, stale receipts, zero contribution and empty geometry', () => {
  for (const mutate of [
    fixture => { fixture.part.partPath = 'harmonic-analyzer/channel/connecting-rod-19' },
    fixture => { fixture.visibility.status = 'stale' },
    fixture => { fixture.visibility.timeSeconds = 0.99 },
    fixture => { fixture.response.captures[0].mechanism.status = 'stale' },
    fixture => { fixture.response.captures[0].mechanism.input = { crankTurns: 3 } },
    fixture => { fixture.visibility.camera.positionMetres = [2, 1, 1] },
    fixture => { fixture.visibility.camera.principalPointViewportPixels = [959, 540] },
    fixture => { fixture.visibility.sourceLayout = [...fixture.visibility.sourceLayout].reverse().concat(fixture.visibility.sourceLayout) },
    fixture => { fixture.visibility.resolvedImagePlaneWarp = { kind: 'homography', unwarpedViewportPixels: [1920, 1080], renderToSourcePixels: [1, 0, 0, 0, 1, 0, 0, 0, 1] } },
    fixture => { fixture.visibility.destinationCellSourcePixels = [2, 1] },
    fixture => { fixture.visibility.sourceOpacity = 0 },
    fixture => { fixture.part.pixelCount = 0 },
    fixture => { fixture.part.status = 'not-visible' },
    fixture => { fixture.part.contourSourcePixels = [] },
    fixture => { fixture.part.uncertaintySourcePixels = null },
    fixture => { fixture.check.sourceContourPixels = [] },
    fixture => { fixture.check.measurementEvidence.sourceImage = { ...fixture.frame.sourceImage, sha256Bgr8: 'b'.repeat(64) } },
  ]) {
    const fixture = contourFixture()
    mutate(fixture)
    const result = measureContourFixture(fixture)
    assert.equal(result.measured.length, 0)
    assert.equal(result.unavailable.length, 1)
  }
})

test('contour supports positive fades without claiming a full-weight color silhouette', () => {
  const fixture = contourFixture()
  fixture.view.composite = { mode: 'crossfade', groupId: 'fade', imageLayerId: 'rod-layer', opacity: 0.25 }
  fixture.response.actual.views[0].composite = fixture.view.composite
  fixture.visibility.sourceLayout[0].composite = fixture.view.composite
  fixture.visibility.sourceOpacity = 0.25; fixture.capture.sourceOpacity = 0.25
  const measured = measureContourFixture(fixture).measured[0]
  assert.equal(measured.errorPx, 10)
  assert.equal(measured.sourceOpacity, 0.25)
  fixture.view.composite.opacity = 0; fixture.visibility.sourceOpacity = 0; fixture.capture.sourceOpacity = 0
  assert.equal(measureContourFixture(fixture).measured.length, 0)
})

test('source and actual native contour samples behind a later mask or outside the scissor are unavailable', () => {
  for (const nativeMasked of [false, true]) {
    const fixture = contourFixture()
    fixture.check.sourceContourPixels = [[100, 100], [120, 100]]
    fixture.part.contourSourcePixels = [[130, 100], [140, 100]]
    const mask = sourceView('inset', nativeMasked ? [129, 99, 20, 4] : [99, 99, 25, 4])
    fixture.frame.views.push(mask)
    const layout = sourceLayoutForViews(fixture.frame.views)
    fixture.visibility.sourceLayout = layout; fixture.capture.sourceLayout = layout
    fixture.response.captures[0].mechanism.sourceLayout = layout; fixture.response.actual.views[0].sourceLayout = layout
    assert.equal(measureContourFixture(fixture).measured.length, 0)
    assert.match(measureContourFixture(fixture).unavailable[0].reason, /support\/scissor|later mask/)
  }
  const fixture = contourFixture()
  fixture.part.contourSourcePixels[0] = [1920.5, 100.5]
  assert.equal(measureContourFixture(fixture).measured.length, 0)
})

test('a bound source partial endpoint is neither extrapolated nor dropped at the image edge', () => {
  const fixture = contourFixture()
  fixture.check.sourceContourPixels = [[100, 1078], [100, 1079]]
  fixture.part.contourSourcePixels = [[100, 1077]]
  const measured = measureContourFixture(fixture).measured[0]
  assert.deepEqual(measured.sourcePixels, [[100, 1078], [100, 1079]])
  assert.equal(measured.rawErrorPx, 2)
  assert.equal(measured.errorPx, 7)
})

test('exact sidecar joins retain original curve scope and reject frame, PTS, SHA, format and layout substitutions', () => {
  const fixture = contourFixture()
  const raw = { ...fixture.frame, timeSeconds: 0.999, contourChecks: undefined,
    views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
  const joined = sourceContourSidecar(fixture.frame, [raw])
  assert.equal(joined.contourChecks.length, 1)
  assert.deepEqual(joined.contourChecks[0].check.sourceContourPixels, fixture.check.sourceContourPixels)
  for (const mutate of [
    original => { original.sourceImage = { ...original.sourceImage, frameIndex: 31 } },
    original => { original.decodedTimeSeconds = 1.000001 },
    original => { original.sourceImage = { ...original.sourceImage, sha256Bgr8: 'b'.repeat(64) } },
    original => { original.sourceImage = { ...original.sourceImage, sourceSha256: '2'.repeat(64) } },
    original => { original.sourceImage = { ...original.sourceImage, pixelFormat: 'gray8', sha256Gray8: original.sourceImage.sha256Bgr8 }; delete original.sourceImage.sha256Bgr8 },
    original => { original.views[0].rectSourcePixels = [0, 0, 1919, 1080] },
    original => { original.views[0].presentation = 'horizontal-mirror' },
  ]) {
    const original = structuredClone(raw)
    mutate(original)
    assert.equal(sourceContourSidecar(fixture.frame, [original]).contourChecks.length, 0)
  }
  const gray = structuredClone(raw), selected = structuredClone(fixture.frame)
  for (const row of [gray, selected]) { row.sourceImage.pixelFormat = 'gray8'; row.sourceImage.sha256Gray8 = row.sourceImage.sha256Bgr8; delete row.sourceImage.sha256Bgr8 }
  gray.views[0].sourceContourChecks[0].measurementEvidence.sourceImage = gray.sourceImage
  assert.equal(sourceContourSidecar(selected, [gray]).contourChecks.length, 1)
})

test('sidecar view renames require a unique actual source-layout match and never merge crossfade perspectives', () => {
  const fixture = contourFixture(), raw = { ...fixture.frame, views: [{ ...fixture.view, id: 'original', sourceContourChecks: [fixture.check] }] }
  const renamed = sourceContourSidecar(fixture.frame, [raw])
  assert.equal(renamed.contourChecks[0].viewId, 'main')
  assert.equal(renamed.contourChecks[0].originalViewId, 'original')
  const selected = { ...fixture.frame, views: [sourceView('outgoing'), sourceView('incoming')] }
  assert.equal(sourceContourSidecar(selected, [raw]).contourChecks.length, 0)
  assert.match(sourceContourSidecar(selected, [raw]).contourJoinUnavailable[0].reason, /Ambiguous/)
})

test('a measured contour CHECK supplies a contour-only required view without inflating point landmarks', () => {
  const fixture = contourFixture()
  const result = measureView(fixture.view, fixture.response, fixture.frame, [], 10, fixture.anchors)
  assert.deepEqual(result.measured, [])
  assert.deepEqual(result.unavailable, [])
  assert.equal(result.contourChecks.length, 1)
  const video = videoFixture()
  video.samples.push({ ...video.samples[0], timeSeconds: 1, sampleTimeSeconds: 1, measurements: result.measured, contourChecks: result.contourChecks })
  const census = { rows: [...censusFixture.rows, { timeSeconds: 1, required: true, reasons: ['every-second'] }] }
  finishVideo(video, census, parseOptions(['--stage', '50']))
  assert.equal(video.status, 'passed')
  assert.equal(video.coverage.passedRequiredSamples, 2)
  assert.equal(video.landmarks.measured, 2)
  assert.equal(video.landmarks.movingChecks, 1)
  assert.equal(video.contourChecks.measured, 1)
  assert.equal(video.motionCoverage[0].movingCheckSamples, 2)
})

test('unknown contour motion ancestry and missing/failed contours never produce coverage success', () => {
  for (const motion of ['unknown', 'fixed']) {
    const fixture = contourFixture()
    fixture.anchors.get('rod-motion').motion = motion
    fixture.response.nativePartBindings[0].binding = null
    const contours = measureContourFixture(fixture).measured
    assert.equal(contours[0].motion, 'unknown')
    const video = videoFixture()
    video.samples[0].measurements = [measurement('fixed', 'fixed')]
    video.samples[0].contourChecks = contours
    finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
    assert.notEqual(video.status, 'passed')
    assert.ok(video.failures.some(item => item.code === 'hard-moving-landmark-coverage'))
  }
  const fixture = contourFixture(), video = videoFixture()
  video.samples[0].measurements = [measurement('fixed', 'fixed')]
  video.samples[0].contourChecks = measureContourFixture(fixture, 9).measured
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.passedRequiredSamples, 0)
  assert.equal(video.stageMeasurement.status, 'failed')
  fixture.part.contourSourcePixels = []
  assert.ok(measureView(fixture.view, fixture.response, fixture.frame, [], 10, fixture.anchors).unavailable.length > 0)
})

test('many samples on a single contour cannot rescue the distributed admitted landmark exclusion floor', () => {
  const fixture = contourFixture()
  fixture.observations.forEach((observed, index) => { if (index >= 2) observed.method = 'unsupported-source-technique' })
  const result = measureFixture(fixture)
  assert.equal(result.contourChecks.length, 1)
  assert.equal(result.measured.length, 2)
  assert.match(result.unavailable.find(item => /three distributed/.test(item.reason)).reason, /three distributed/)
})

test('conflicting exposure/view contour declarations refuse a winner while repeated identical rows count once', () => {
  const fixture = contourFixture(), original = { ...fixture.frame, views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
  assert.equal(sourceContourSidecar(fixture.frame, [original, structuredClone(original)]).contourChecks.length, 1)
  const conflicting = structuredClone(original)
  conflicting.views[0].sourceContourChecks[0].sourceContourPixels[0] = [500, 500]
  const joined = sourceContourSidecar(fixture.frame, [original, conflicting])
  assert.deepEqual(joined.contourChecks, [])
  assert.match(joined.contourJoinUnavailable[0].reason, /Conflicting/)
})

test('census contour sidecars use the selected exact exposure without changing chosen cameras, inputs or landmark roles', () => {
  const fixture = contourFixture()
  const selected = { ...fixture.frame, shotId: 'shot', classification: 'machine', landmarks: fixture.observations.slice(0, 2) }
  const original = { ...selected, views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
  const compact = { frames: [{ ...frame(0), views: [fixture.view] }, selected, { ...frame(2), views: [fixture.view] }] }
  const raw = { ...observations, frames: [compact.frames[0], original, compact.frames[2]] }
  const row = sourceCensus(raw, compact, native, parseOptions(['--times', '1'])).selected[0]
  assert.equal(row.frame.contourChecks.length, 1)
  assert.deepEqual(row.frame.views, selected.views)
  assert.deepEqual(row.frame.landmarks, selected.landmarks)
  assert.equal(row.frame.landmarks.every(item => item.role === 'fit'), true)
  original.sourceImage = { ...original.sourceImage, sha256Bgr8: 'b'.repeat(64) }
  const stale = sourceCensus(raw, compact, native, parseOptions(['--times', '1'])).selected[0]
  assert.deepEqual(stale.frame.contourChecks, [])
  assert.match(stale.frame.contourJoinUnavailable[0].reason, /same-format image hash/)
})

test('diagnostic contour counterexamples fail stages without inflating diagnostic landmark counts', () => {
  const fixture = contourFixture(), video = videoFixture()
  video.samples.push({ ...video.samples[0], timeSeconds: 1, sampleTimeSeconds: 1, diagnosticOnly: true, reasons: ['mid-interval'], measurements: [],
    contourChecks: measureContourFixture(fixture, 9).measured, status: 'failed' })
  const census = { rows: [...censusFixture.rows, { timeSeconds: 1, diagnosticOnly: true, required: true, reasons: ['mid-interval'] }] }
  finishVideo(video, census, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.passedRequiredSamples, 1)
  assert.equal(video.diagnosticLandmarks.measured, 0)
  assert.equal(video.diagnosticLandmarks.failed, 0)
  assert.equal(video.diagnosticContourChecks.failed, 1)
  assert.equal(video.stageMeasurement.status, 'failed')
  assert.equal(video.failures.find(item => item.code === 'diagnostic-pixel-counterexample').measuredContours, 1)
})

test('an exact contour exposure survives unselected PTS aliases without borrowing their pixels', () => {
  const fixture = contourFixture(), exact = { ...fixture.frame, views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
  const unselected = structuredClone(exact)
  unselected.decodedTimeSeconds = 1 + Number.EPSILON
  unselected.views[0].sourceContourChecks[0].sourceContourPixels = [[1700, 700], [1700, 800]]
  const joined = sourceContourSidecar(fixture.frame, [unselected, exact])
  assert.deepEqual(joined.contourJoinUnavailable.map(item => [item.contourId, item.status, item.check.sourceContourPixels]), [[fixture.check.id, 'source-unavailable', [[1700, 700], [1700, 800]]]])
  assert.deepEqual(joined.contourChecks[0].check.sourceContourPixels, fixture.check.sourceContourPixels)
  assert.deepEqual(sourceContourSidecar(fixture.frame, [unselected]).contourChecks, [])
  assert.match(sourceContourSidecar(fixture.frame, [unselected]).contourJoinUnavailable[0].reason, /PTS/)
})

test('resolved exact native rod binding supplies kinematic moving eligibility without claiming observed source motion', () => {
  const fixture = contourFixture()
  fixture.anchors.delete('rod-motion')
  const measured = measureContourFixture(fixture).measured[0]
  assert.equal(measured.motion, 'moving')
  assert.equal(measured.motionBasis, 'resolved-native-rod-binding')
  assert.equal(measured.observedSourceInternalMotion, 'unmeasured')
  assert.deepEqual(measured.motionAnchorIds, [])
  assert.deepEqual(measured.nativePartBinding, { partPath: fixture.check.partPath, bindingId: 'connectingRods', kind: 'indexed', motion: 'rod', stationIndex: 19 })
  const video = videoFixture()
  video.samples[0].measurements = [measurement('fixed', 'fixed')]
  video.samples[0].contourChecks = [measured]
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.status, 'passed')
  assert.equal(video.landmarks.movingChecks, 0)
  assert.equal(video.motionCoverage[0].movingCheckSamples, 1)
})

test('missing, wrong-path, non-rod and unresolved station binding cannot manufacture contour moving coverage', () => {
  for (const mutate of [
    fixture => { fixture.response.nativePartBindings = [] },
    fixture => { fixture.response.nativePartBindings[0].binding = null },
    fixture => { fixture.response.nativePartBindings[0].binding.partPath = 'harmonic-analyzer/channel/rocker-arm-20' },
    fixture => { fixture.response.nativePartBindings[0].binding.bindingId = '' },
    fixture => { fixture.response.nativePartBindings[0].binding.motion = 'rocker' },
    fixture => { fixture.response.nativePartBindings[0].binding.kind = 'group' },
    fixture => { fixture.response.nativePartBindings[0].binding.stationIndex = -1 },
    fixture => { fixture.response.nativePartBindings[0].binding.stationIndex = 20 },
    fixture => { fixture.response.nativePartBindings.push(structuredClone(fixture.response.nativePartBindings[0])) },
  ]) {
    const fixture = contourFixture()
    fixture.anchors.delete('rod-motion')
    mutate(fixture)
    const measured = measureContourFixture(fixture).measured[0]
    assert.equal(measured.status, 'passed')
    assert.equal(measured.motion, 'unknown')
    const video = videoFixture()
    video.samples[0].measurements = [measurement('fixed', 'fixed')]
    video.samples[0].contourChecks = [measured]
    finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
    assert.notEqual(video.status, 'passed')
    assert.ok(video.failures.some(item => item.code === 'hard-moving-landmark-coverage'))
  }
})

test('retained captured pixels from an older same-time redraw cannot satisfy current contour review', () => {
  const older = contourFixture(1), current = contourFixture(2)
  assert.equal(measureContourFixture(current).measured[0].status, 'passed')
  for (const captures of [
    [{ ...current.response.captures[0], partVisibility: older.visibility }],
    [{ ...current.response.captures[0], capture: older.capture }],
    older.response.captures,
  ]) {
    const response = { ...current.response, captures }
    const result = measureContours(current.view, response, current.frame, 10, current.anchors)
    assert.deepEqual(result.measured, [])
    assert.match(result.unavailable[0].reason, /current completed source draw revision/)
  }
  assert.equal(older.visibility.status, 'captured')
  assert.equal(older.capture.status, 'captured')
  assert.equal(older.visibility.timeSeconds, current.visibility.timeSeconds)
})

test('missing draw receipts and a same-revision receipt for another source draw time fail closed', () => {
  for (const mutate of [
    fixture => { delete fixture.visibility.sourceDrawRevision },
    fixture => { delete fixture.capture.sourceDrawRevision },
    fixture => { delete fixture.response.actual.sourceDrawRevision },
    fixture => { delete fixture.response.actual.sourceDrawTimeSeconds },
    fixture => { fixture.response.actual.sourceDrawTimeSeconds = 0.99 },
    fixture => { fixture.response.captures[0].mechanism.sourceDrawRevision = 2 },
  ]) {
    const fixture = contourFixture()
    mutate(fixture)
    const result = measureContourFixture(fixture)
    assert.deepEqual(result.measured, [])
    assert.match(result.unavailable[0].reason, /current completed source draw revision/)
  }
})

test('authoritative FIT contours stay retained without independent CHECK or moving coverage', () => {
  const fixture = contourFixture()
  fixture.check.role = 'fit'
  fixture.check.measurementEvidence.evidence = 'Prose says CHECK, but the authoritative structured role is FIT.'
  const result = measureContourFixture(fixture)
  assert.deepEqual(result.measured, [])
  assert.deepEqual(result.unavailable, [])
  assert.equal(result.retainedFits[0].status, 'fit-retained-unmeasured')
  assert.equal(result.retainedFits[0].check.role, 'fit')
  const video = videoFixture()
  video.samples[0].measurements = [measurement('fixed', 'fixed')]
  video.samples[0].contourFits = result.retainedFits
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.contourChecks.measured, 0)
  assert.equal(video.contourChecks.movingChecks, 0)
  assert.equal(video.contourFits.retained, 1)
  assert.equal(video.motionCoverage[0].movingCheckSamples, 0)
  assert.ok(video.failures.some(item => item.code === 'hard-moving-landmark-coverage'))
})

test('missing or invalid contour roles fail closed despite CHECK prose and moving native binding', () => {
  for (const role of [undefined, null, 'CHECK', 'held-out']) {
    const fixture = contourFixture()
    fixture.check.role = role
    fixture.check.measurementEvidence.evidence = 'Independent held-out CHECK station.'
    const direct = measureContourFixture(fixture)
    assert.deepEqual(direct.measured, [])
    assert.deepEqual(direct.retainedFits, [])
    assert.match(direct.unavailable[0].reason, /authoritative explicit FIT\/CHECK role/)
    const original = { ...fixture.frame, views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
    const joined = sourceContourSidecar(fixture.frame, [original])
    assert.deepEqual(joined.contourChecks, [])
    assert.match(joined.contourJoinUnavailable[0].reason, /authoritative explicit FIT\/CHECK role/)
  }
})

test('FIT-only curves cannot supply a required contour-only view or inflate CHECK summaries', () => {
  const fixture = contourFixture()
  fixture.check.role = 'fit'
  assert.throws(() => measureView(fixture.view, fixture.response, fixture.frame, [], 10, fixture.anchors), /no independently observed landmarks or contour CHECK/)
  const result = measureContourFixture(fixture), video = videoFixture()
  video.samples[0].measurements = []
  video.samples[0].contourChecks = result.retainedFits
  video.samples[0].contourFits = result.retainedFits
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.measuredRequiredSamples, 0)
  assert.equal(video.coverage.passedRequiredSamples, 0)
  assert.equal(video.contourChecks.measured, 0)
  assert.equal(video.motionCoverage[0].movingCheckSamples, 0)
  assert.notEqual(video.stageMeasurement.status, 'passed')
})

test('unavailable FIT source joins remain diagnostics instead of gating genuine held-out CHECKs', () => {
  const fixture = contourFixture(), fit = structuredClone(fixture.check)
  fit.id = 'fit-edge'; fit.role = 'fit'
  fit.measurementEvidence.sourceImage.sha256Bgr8 = 'b'.repeat(64)
  const original = { ...fixture.frame, views: [{ ...fixture.view, sourceContourChecks: [fixture.check, fit] }] }
  Object.assign(fixture.frame, sourceContourSidecar(fixture.frame, [original]))
  const result = measureView(fixture.view, fixture.response, fixture.frame, [], 10, fixture.anchors)
  assert.equal(result.contourChecks[0].status, 'passed')
  assert.deepEqual(result.unavailable, [])
  const retained = measureContourFixture(fixture).retainedFits
  assert.equal(retained[0].status, 'fit-source-unavailable')
  assert.equal(retained[0].role, 'fit')
})

test('view precondition failures account for actual required CHECK contours without FIT inflation', () => {
  const fixture = contourFixture(), fit = structuredClone(fixture.frame.contourChecks[0])
  fit.check.id = 'fit-edge'; fit.check.role = 'fit'
  fixture.frame.contourChecks.push(fit)
  fixture.capture.status = 'stale'
  let failure
  try { measureView(fixture.view, fixture.response, fixture.frame, [], 10, fixture.anchors) } catch (error) { failure = error }
  assert.match(failure.message, /Missing\/stale actual GPU landmark/)
  assert.deepEqual(failure.contourUnavailable.map(item => [item.contourId, item.role]), [['right-exterior', 'check']])
  const video = videoFixture()
  Object.assign(video.samples[0], { status: 'unavailable', measurements: [], contourChecks: [], contourFits: measureContourFixture(fixture).retainedFits, unavailable: failure.contourUnavailable })
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.contourChecks.unavailable, 1)
  assert.equal(video.contourChecks.measured, 0)
  assert.equal(video.contourFits.retained, 1)
  assert.notEqual(video.stageMeasurement.status, 'passed')
})

test('failed explicitly held-out curves remain CHECK failures rather than converting to FIT', () => {
  const fixture = contourFixture()
  fixture.check.measurementEvidence.evidence = 'Failure does not authorize conversion of this original CHECK to FIT.'
  fixture.part.contourSourcePixels = [[1800, 1000], [1810, 1000]]
  const result = measureContourFixture(fixture)
  assert.equal(result.measured[0].role, 'check')
  assert.equal(result.measured[0].status, 'failed')
  assert.deepEqual(result.retainedFits, [])
  const video = videoFixture()
  video.samples[0].measurements = [measurement('fixed', 'fixed')]
  video.samples[0].contourChecks = result.measured
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.contourChecks.failed, 1)
  assert.equal(video.stageMeasurement.status, 'failed')
})

test('a conflicting FIT alias never erases the unavailable obligation of an original CHECK', () => {
  for (const firstRole of ['check', 'fit']) {
    const fixture = contourFixture(), first = { ...fixture.frame, views: [{ ...fixture.view, sourceContourChecks: [{ ...fixture.check, role: firstRole }] }] }
    const second = structuredClone(first)
    second.views[0].sourceContourChecks[0].role = firstRole === 'check' ? 'fit' : 'check'
    const joined = sourceContourSidecar(fixture.frame, [first, second])
    Object.assign(fixture.frame, joined)
    const result = measureContourFixture(fixture)
    assert.deepEqual(result.measured, [])
    assert.ok(result.unavailable.some(item => item.contourId === fixture.check.id && item.role === 'check'))
    const video = videoFixture()
    Object.assign(video.samples[0], { status: 'unavailable', contourChecks: result.measured, contourFits: result.retainedFits, unavailable: result.unavailable })
    finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
    assert.equal(video.contourChecks.unavailable, 1)
    assert.equal(video.contourChecks.measured, 0)
    assert.notEqual(video.stageMeasurement.status, 'passed')
  }
})

test('contour-only exact CHECK exposures are mandatory census oracles without creating landmark observations', () => {
  const fixture = contourFixture(), image = sourceImage(15, 'b'.repeat(64))
  const check = { ...fixture.check, measurementEvidence: { ...fixture.check.measurementEvidence, sourceImage: image } }
  const original = { ...frame(0.5), sourceImage: image, landmarks: [], views: [{ ...fixture.view, sourceContourChecks: [check] }] }
  const compact = { frames: observations.frames.map(item => ({ ...item, views: [fixture.view] })) }
  const raw = { ...observations, frames: [compact.frames[0], original, compact.frames[1], compact.frames[2]] }
  const census = sourceCensus(raw, compact, native, parseOptions(['--stage', '20']))
  const row = census.rows.find(item => item.timeSeconds === 0.5)
  assert.ok(row.reasons.includes('source-contour-check'))
  assert.equal(row.diagnosticOnly, false)
  assert.equal(row.required, true)
  assert.equal(row.frame.decodedTimeSeconds, original.decodedTimeSeconds)
  assert.deepEqual(row.frame.sourceImage, image)
  assert.deepEqual(row.frame.landmarks, [])
  assert.deepEqual(row.frame.views, compact.frames[0].views)
  assert.deepEqual(row.frame.contourChecks.map(item => item.check), [check])
  original.views[0].sourceContourChecks[0] = { ...check, role: 'fit' }
  const fitCensus = sourceCensus(raw, compact, native, parseOptions(['--stage', '20']))
  assert.equal(fitCensus.rows.some(item => item.reasons.includes('source-contour-check')), false)
  assert.equal(fitCensus.rows.some(item => item.timeSeconds === 0.5), false)
})

test('CHECK exposures without a compact camera/input bracket retain every unavailable exposure obligation', () => {
  const fixture = contourFixture()
  const originals = [0.5, 0.6].map(timeSeconds => {
    const image = sourceImage(Math.round(timeSeconds * 30), 'b'.repeat(64))
    const check = { ...fixture.check, measurementEvidence: { ...fixture.check.measurementEvidence, sourceImage: image } }
    return { ...frame(timeSeconds), sourceImage: image, landmarks: [], views: [{ ...fixture.view, sourceContourChecks: [check] }] }
  })
  const compact = { frames: [{ ...frame(0), views: [fixture.view] }] }
  const raw = { ...observations, frames: [compact.frames[0], ...originals] }
  const rows = sourceCensus(raw, compact, native, parseOptions(['--stage', '20'])).rows.filter(item => item.reasons.includes('source-contour-check'))
  assert.deepEqual(rows.map(row => row.timeSeconds), [0.5, 0.6])
  for (const row of rows) {
    assert.equal(row.frame, null)
    assert.equal(row.required, true)
    assert.deepEqual(row.contourJoinUnavailable.map(item => [item.contourId, item.role, item.status]), [[fixture.check.id, 'check', 'unmeasured-native']])
  }
  const video = videoFixture()
  video.samples = rows.map(row => ({ ...video.samples[0], timeSeconds: row.timeSeconds, sampleTimeSeconds: null, measurements: [], status: 'unavailable', unavailable: row.contourJoinUnavailable }))
  finishVideo(video, { rows }, parseOptions(['--stage', '20']))
  assert.equal(video.contourChecks.unavailable, 2)
  assert.equal(video.contourChecks.measured, 0)
  assert.equal(video.stageMeasurement.status, 'unmeasured')
  assert.equal(video.coverage.complete, false)
})

test('selected exact source rows retain alias-only CHECK IDs as unavailable and count identical declarations once', () => {
  const fixture = contourFixture(), exact = { ...fixture.frame, shotId: 'shot', views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
  const alias = structuredClone(exact)
  alias.decodedTimeSeconds = 1 + Number.EPSILON
  const aliasOnly = { ...alias.views[0].sourceContourChecks[0], id: 'alias-only', sourceContourPixels: [[1700, 700], [1700, 800]] }
  alias.views[0].sourceContourChecks.push(aliasOnly, { ...aliasOnly, id: 'alias-fit', role: 'fit' })
  const selected = { ...fixture.frame, shotId: 'shot' }
  const joined = sourceContourSidecar(selected, [alias, exact, structuredClone(alias), structuredClone(exact)])
  assert.deepEqual(joined.contourChecks.map(item => item.check), [fixture.check])
  assert.deepEqual(joined.contourJoinUnavailable.map(item => [item.contourId, item.role, item.status]), [['alias-only', 'check', 'source-unavailable']])
  assert.match(joined.contourJoinUnavailable[0].reason, /exact source exposure/)
  const compact = { frames: [{ ...frame(0), views: [fixture.view] }, selected, { ...frame(2), views: [fixture.view] }] }
  const census = sourceCensus({ ...observations, frames: [compact.frames[0], exact, alias, compact.frames[2]] }, compact, native, parseOptions(['--times', '1']))
  assert.deepEqual(census.rows.filter(item => item.reasons.includes('source-contour-check')).map(item => item.timeSeconds), [1])
  assert.deepEqual(census.selected[0].frame.contourJoinUnavailable.map(item => item.contourId), ['alias-only'])
})

test('exact or ancestor selected world pose overrides cannot supply moving contour coverage from native or anchor ancestry', () => {
  for (const target of ['exact', 'ancestor']) for (const field of ['worldPositionMetres', 'worldQuaternion']) for (const withAncestry of [false, true]) {
    const fixture = contourFixture()
    if (!withAncestry) fixture.anchors.clear()
    fixture.view.partOverrides = [{ partPath: target === 'exact' ? fixture.check.partPath : 'harmonic-analyzer/channel', [field]: field === 'worldPositionMetres' ? [0, 0, 0] : [0, 0, 0, 1] }]
    const result = measureContourFixture(fixture)
    assert.deepEqual(result.unavailable, [])
    assert.equal(result.measured[0].status, 'passed')
    assert.equal(result.measured[0].errorPx, 10)
    assert.equal(result.measured[0].motion, 'unknown')
    const video = videoFixture()
    video.samples[0].measurements = [measurement('fixed', 'fixed')]
    video.samples[0].contourChecks = result.measured
    finishVideo(video, censusFixture, parseOptions(['--stage', '20']))
    assert.equal(video.contourChecks.movingChecks, 0)
    assert.ok(video.failures.some(item => item.code === 'hard-moving-landmark-coverage'))
  }
})

test('visibility-only and different exact-part pose overrides retain genuinely visible native moving eligibility', () => {
  for (const override of [
    { visibility: 'visible' },
    { partPath: 'harmonic-analyzer/channel', visibility: 'visible' },
    { partPath: 'harmonic-analyzer/channel/connecting-rod-2', worldPositionMetres: [0, 0, 0] },
    { partPath: 'harmonic-analyzer/channel/connecting-rod-19', worldPositionMetres: [0, 0, 0], worldQuaternion: [0, 0, 0, 1] },
  ]) {
    const fixture = contourFixture()
    fixture.anchors.clear()
    fixture.view.partOverrides = [{ partPath: fixture.check.partPath, ...override }]
    const result = measureContourFixture(fixture)
    assert.deepEqual(result.unavailable, [])
    assert.equal(result.measured[0].status, 'passed')
    assert.equal(result.measured[0].motion, 'moving')
    assert.equal(result.measured[0].motionBasis, 'resolved-native-rod-binding')
  }
})

test('malformed-only CHECK rows diagnose source evidence before an absent GPU contour readback', () => {
  for (const [mutate, reason] of [
    [fixture => { delete fixture.check.uncertaintyPx }, /bounded source uncertainty/],
    [fixture => { fixture.check.uncertaintyPx = 38.4001 }, /bounded source uncertainty/],
    [fixture => { fixture.check.sourceContourPixels = [[1920, 100], [1920, 101]] }, /source ROI/],
    [fixture => { fixture.check.sourceContourPixels = [[100, 100], [100, 100]] }, /nondegenerate/],
    [fixture => { fixture.check.measurementEvidence.sourceImage = { ...fixture.frame.sourceImage, sha256Gray8: fixture.frame.sourceImage.sha256Bgr8 } }, /canonical current-source image/],
    [fixture => { fixture.check.measurementEvidence.sourceImage = { ...fixture.frame.sourceImage, pixelFormat: 'gray8', sha256Gray8: fixture.frame.sourceImage.sha256Bgr8 }; delete fixture.check.measurementEvidence.sourceImage.sha256Bgr8 }, /canonical current-source image/],
    [fixture => { fixture.frame.contourChecks[0].decodedTimeSeconds += Number.EPSILON }, /exact exposure/],
  ]) {
    const fixture = contourFixture()
    mutate(fixture)
    delete fixture.response.captures[0].partVisibility
    const result = measureContourFixture(fixture)
    assert.deepEqual(result.measured, [])
    assert.equal(result.unavailable.length, 1)
    assert.equal(result.unavailable[0].status, 'source-unavailable')
    assert.match(result.unavailable[0].reason, reason)
  }
  const valid = contourFixture()
  delete valid.response.captures[0].partVisibility
  const result = measureContourFixture(valid)
  assert.equal(result.unavailable[0].status, 'unmeasured-native')
  assert.match(result.unavailable[0].reason, /depth-ID contour readback/)
})

test('mixed CHECK rows keep structural source faults separate from genuine native readback faults', () => {
  const fixture = contourFixture(), invalid = structuredClone(fixture.frame.contourChecks[0])
  invalid.check.id = 'missing-uncertainty'
  delete invalid.check.uncertaintyPx
  fixture.frame.contourChecks.push(invalid)
  delete fixture.response.captures[0].partVisibility
  const result = measureContourFixture(fixture)
  assert.deepEqual(result.measured, [])
  assert.deepEqual(result.unavailable.map(item => [item.contourId, item.status]), [['missing-uncertainty', 'source-unavailable'], ['right-exterior', 'unmeasured-native']])
  assert.match(result.unavailable[0].reason, /bounded source uncertainty/)
  assert.match(result.unavailable[1].reason, /depth-ID contour readback/)
})

test('canonical source uncertainty and image equality remain required even with complete native receipts', () => {
  for (const mutate of [
    fixture => { fixture.check.uncertaintyPx = 38.4001 },
    fixture => { fixture.check.measurementEvidence.sourceImage = { ...fixture.frame.sourceImage, sha256Gray8: fixture.frame.sourceImage.sha256Bgr8 } },
    fixture => { fixture.check.measurementEvidence.sourceImage = { ...fixture.frame.sourceImage, extraImageIdentity: 'not canonical' } },
  ]) {
    const fixture = contourFixture()
    mutate(fixture)
    const result = measureContourFixture(fixture, 100)
    assert.deepEqual(result.measured, [])
    assert.equal(result.unavailable[0].status, 'source-unavailable')
  }
  const bounded = contourFixture()
  bounded.check.uncertaintyPx = 38.4
  assert.equal(measureContourFixture(bounded, 100).measured[0].errorPx, 45.4)
  const gray = contourFixture()
  gray.frame.sourceImage = { frameIndex: 30, pixelFormat: 'gray8', sha256Gray8: 'a'.repeat(64), width: 1920, height: 1080, sourceSha256: '1'.repeat(64) }
  gray.frame.contourChecks[0].sourceImage = gray.frame.sourceImage
  gray.check.measurementEvidence.sourceImage = gray.frame.sourceImage
  const result = measureContourFixture(gray)
  assert.deepEqual(result.unavailable, [])
  assert.equal(result.measured[0].status, 'passed')
  assert.equal(result.measured[0].errorPx, 10)
})

test('report evidence roundtrip preserves conflicting same-ID per-draw CHECK values and all source obligations', () => {
  const first = contourFixture(1), second = contourFixture(2)
  second.part.contourSourcePixels[0] = [110.5, 100.5]
  const checks = [measureContourFixture(first, 9).measured[0], measureContourFixture(second, 9).measured[0]]
  const fit = { ...first.frame.contourChecks[0], role: 'fit', status: 'fit-retained-unmeasured', check: { ...first.check, role: 'fit' } }
  const video = { ...videoFixture(), videoId: '4mBuyixt22U' }
  video.samples[0].contourChecks = checks
  video.samples[0].contourFits = [fit]
  video.samples[0].unavailable.push({ viewId: 'main', contourId: 'alias-only', partPath: first.check.partPath, role: 'check', status: 'source-unavailable', reason: 'Different exact source declaration' })
  video.playback.local.receipt = { nativeBoundarySamples: checks[0].nativeBoundarySamples, camera: checks[0].camera, input: checks[0].input }
  const wire = JSON.parse(JSON.stringify(video)), encoded = normalizeVerificationReport(video)
  assert.equal(encoded.reportSchemaVersion, 2)
  assert.deepEqual(encoded.samples[0].contourChecks.map(row => [row.contourId, row.role, row.status, row.sourceDrawRevision, row.errorPx]),
    [['right-exterior', 'check', 'failed', 1, 10], ['right-exterior', 'check', 'failed', 2, 15]])
  const refs = encoded.samples[0].contourChecks.map(row => row.nativeBoundarySamplesRef)
  assert.notEqual(refs[0], refs[1])
  assert.equal(encoded.playback.local.receipt.nativeBoundarySamplesRef, refs[0])
  assert.equal(encoded.samples[0].contourChecks[0].cameraRef, encoded.samples[0].contourChecks[1].cameraRef)
  assert.deepEqual(resolveVerificationReport(JSON.parse(JSON.stringify(encoded))), wire)
  const decoded = resolveVerificationReport(JSON.parse(JSON.stringify(encoded)))
  finishVideo(wire, censusFixture, parseOptions(['--stage', '20']))
  finishVideo(decoded, censusFixture, parseOptions(['--stage', '20']))
  assert.deepEqual(decoded, wire)
  assert.equal(decoded.stageMeasurement.status, 'failed')
  assert.equal(decoded.contourChecks.unavailable, 1)
  assert.equal(decoded.contourFits.retained, 1)
})

test('report evidence resolver rejects missing or corrupted native boundary references', () => {
  const fixture = contourFixture(), video = { ...videoFixture(), videoId: '4mBuyixt22U' }
  video.samples[0].contourChecks = measureContourFixture(fixture).measured
  const encoded = normalizeVerificationReport(video), id = encoded.samples[0].contourChecks[0].nativeBoundarySamplesRef
  const missing = structuredClone(encoded)
  delete missing.contourEvidence[id]
  assert.throws(() => resolveVerificationReport(missing), /Unresolved verification evidence reference/)
  const corrupt = structuredClone(encoded)
  corrupt.contourEvidence[id][0][0] += 1
  assert.throws(() => resolveVerificationReport(corrupt), /Corrupt verification evidence reference/)
})

test('streamed aggregate report preserves exact JSON values and atomically keeps prior output on failure', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'harmonic-report-test-'))
  try {
    const fixture = contourFixture(), video = { ...videoFixture(), videoId: '4mBuyixt22U' }
    video.samples[0].contourChecks = measureContourFixture(fixture).measured
    video.samples[0].unavailable.push({ reason: 'Source unavailable — independently observed' })
    video.jsonValues = { omitted: undefined, array: [undefined, NaN, Infinity, 'á'.repeat(70_000)], nullValue: null }
    const report = { schemaVersion: 1, status: 'unavailable', videos: [video], startedAt: 'old-capture-time' }
    const output = join(directory, 'report.json'), statistics = await writeVerificationReport(output, report)
    const bytes = await readFile(output), decoded = resolveVerificationReport(JSON.parse(bytes))
    assert.deepEqual(decoded, JSON.parse(JSON.stringify(report)))
    assert.equal(statistics.bytesWritten, bytes.length)
    assert.ok(statistics.chunksWritten > 1)
    assert.ok(statistics.maxChunkBytes <= 64 * 1024)
    await writeFile(output, '{"prior":"actual report remains"}\n')
    await assert.rejects(writeVerificationReport(output, { videoId: '4mBuyixt22U', invalid: 1n }), /BigInt/)
    assert.deepEqual(JSON.parse(await readFile(output, 'utf8')), { prior: 'actual report remains' })
    assert.deepEqual(await readdir(directory), ['report.json'])
  } finally { await rm(directory, { recursive: true, force: true }) }
})

test('off-track contour PTS aliases use one explicit exact exposure authority', () => {
  const fixture = contourFixture(), image = sourceImage(15, 'b'.repeat(64))
  const check = { ...fixture.check, measurementEvidence: { ...fixture.check.measurementEvidence, sourceImage: image } }
  const original = { ...frame(0.5), sourceImage: image, landmarks: [], views: [{ ...fixture.view, sourceContourChecks: [check] }] }
  const alias = structuredClone(original)
  alias.timeSeconds = alias.decodedTimeSeconds = 0.5001
  alias.views[0].sourceContourChecks.push({ ...alias.views[0].sourceContourChecks[0], id: 'alias-only' })
  const compact = { frames: observations.frames.map(item => ({ ...item, views: [fixture.view] })) }
  const raw = { ...observations, frames: [compact.frames[0], original, alias, compact.frames[1], compact.frames[2]] }
  const rows = sourceCensus(raw, compact, native, parseOptions(['--stage', '20'])).rows.filter(row => row.reasons.includes('source-contour-check'))
  assert.deepEqual(rows.map(row => row.timeSeconds), [0.5])
  assert.equal(rows[0].frame.decodedTimeSeconds, 0.5)
  assert.deepEqual(rows[0].frame.contourChecks.map(item => item.check), [check])
  assert.deepEqual(rows[0].frame.contourJoinUnavailable.map(item => [item.contourId, item.status]), [['alias-only', 'source-unavailable']])
  assert.deepEqual(rows[0].frame.views, compact.frames[0].views)
})

test('ambiguous off-track CHECK PTS pools never select a camera and retain all distinct declarations', () => {
  const fixture = contourFixture(), image = sourceImage(15, 'b'.repeat(64))
  const check = { ...fixture.check, measurementEvidence: { ...fixture.check.measurementEvidence, sourceImage: image } }
  const first = { ...frame(0.5001), sourceImage: image, landmarks: [], views: [{ ...fixture.view, sourceContourChecks: [check] }] }
  const second = structuredClone(first)
  second.timeSeconds = second.decodedTimeSeconds = 0.5002
  second.views[0].sourceContourChecks[0].sourceContourPixels[0] = [500, 500]
  const compact = { frames: observations.frames.map(item => ({ ...item, views: [fixture.view] })) }
  const raw = { ...observations, frames: [compact.frames[0], first, second, structuredClone(second), compact.frames[1], compact.frames[2]] }
  const rows = sourceCensus(raw, compact, native, parseOptions(['--stage', '20'])).rows.filter(row => row.reasons.includes('source-contour-check'))
  assert.deepEqual(rows.map(row => row.timeSeconds), [native.pts[15]])
  assert.equal(rows[0].frame, null)
  assert.equal(rows[0].required, true)
  assert.deepEqual(rows[0].contourJoinUnavailable.map(item => item.status), ['source-unavailable', 'source-unavailable'])
  assert.deepEqual(rows[0].contourJoinUnavailable.map(item => item.check.sourceContourPixels), [check.sourceContourPixels, second.views[0].sourceContourChecks[0].sourceContourPixels])
  assert.notEqual(rows[0].contourJoinUnavailable[0].sourceDeclarationDigest, rows[0].contourJoinUnavailable[1].sourceDeclarationDigest)
  const video = videoFixture()
  video.samples = [{ ...video.samples[0], timeSeconds: rows[0].timeSeconds, sampleTimeSeconds: null, measurements: [], contourChecks: [], status: 'unavailable', unavailable: rows[0].contourJoinUnavailable }]
  finishVideo(video, { rows }, parseOptions(['--stage', '20']))
  assert.equal(video.contourChecks.measured, 0)
  assert.equal(video.contourChecks.unavailable, 2)
  assert.equal(video.coverage.complete, false)
  assert.equal(video.stageMeasurement.status, 'unmeasured')
})

test('authored CHECK exposure cannot be exempted or dropped by a null compact frame', () => {
  for (const mode of ['exempt', 'outside-shot', 'shot-mismatch']) {
    const fixture = contourFixture()
    const nonMachine = mode === 'exempt'
    const author = { ...fixture.frame, timeSeconds: mode === 'outside-shot' ? 0.9 : 1, shotId: 'shot', classification: nonMachine ? 'non-machine' : 'machine', landmarks: [] }
    const rawFrame = { ...author, views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
    const shots = nonMachine ? [{ ...observations.shots[0], classification: 'non-machine', hasCorrespondingMachine: false }]
      : [{ ...observations.shots[0], endSeconds: 1 }, { id: 'after', startSeconds: 1, endSeconds: 2.1, classification: 'machine', hasCorrespondingMachine: true }]
    const start = { ...frame(0, author.classification), views: [fixture.view] }
    const compact = { shots, frames: [start, author] }
    const raw = { shots, frames: [start, rawFrame] }
    const row = sourceCensus(raw, compact, native, parseOptions(['--times', String(author.timeSeconds)])).selected[0]
    assert.equal(row.required, true)
    assert.ok(row.reasons.includes('source-contour-check'))
    const retained = [...(row.frame?.contourChecks ?? []).map(item => item.check), ...row.contourJoinUnavailable.map(item => item.check)]
    assert.deepEqual(retained, [fixture.check])
    if (nonMachine) assert.deepEqual(row.expectedViewIds, ['main'])
    else {
      assert.equal(row.frame, null)
      assert.equal(row.contourJoinUnavailable[0].role, 'check')
      assert.equal(row.contourJoinUnavailable[0].contourId, fixture.check.id)
    }
  }
})

test('alias CHECK declarations use full canonical source support and mapped-view identity', () => {
  for (const kind of ['part', 'pixels', 'source-image']) {
    const fixture = contourFixture(), exact = { ...fixture.frame, shotId: 'shot', views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
    const alias = structuredClone(exact)
    alias.decodedTimeSeconds += 0.0001
    if (kind === 'part') alias.views[0].sourceContourChecks[0].partPath = 'harmonic-analyzer/channel/connecting-rod-4'
    if (kind === 'pixels') alias.views[0].sourceContourChecks[0].sourceContourPixels[0] = [500, 500]
    if (kind === 'source-image') alias.sourceImage = { ...alias.sourceImage, extraImageIdentity: 'different original declaration' }
    const selected = { ...fixture.frame, shotId: 'shot' }
    const joined = sourceContourSidecar(selected, [exact, alias, structuredClone(exact), structuredClone(alias)])
    assert.deepEqual(joined.contourChecks.map(item => item.check), [fixture.check])
    assert.equal(joined.contourJoinUnavailable.length, 1)
    assert.equal(joined.contourJoinUnavailable[0].status, 'source-unavailable')
    assert.deepEqual(joined.contourJoinUnavailable[0].check, alias.views[0].sourceContourChecks[0])
    assert.deepEqual(joined.contourJoinUnavailable[0].sourceImage, alias.sourceImage)
  }
  const fixture = contourFixture(), exact = { ...fixture.frame, shotId: 'shot', views: [{ ...fixture.view, sourceContourChecks: [fixture.check] }] }
  const alias = structuredClone(exact)
  alias.decodedTimeSeconds += 0.0001
  alias.views[0].id = 'original-source-name'
  const selected = { ...fixture.frame, shotId: 'shot' }
  const joined = sourceContourSidecar(selected, [exact, alias])
  assert.deepEqual(joined.contourChecks.map(item => item.check), [fixture.check])
  assert.deepEqual(joined.contourJoinUnavailable, [])
})
