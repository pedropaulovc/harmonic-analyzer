import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'
import { parseOptions, sourceCensus, finishVideo, seekSettlement, sourcePtsInShot, requireSourceViews, measureView, playbackInterval, sourceSeedIndex, diagnosticReplayOutcome, requirePausedReview, compareCameraPose, requireModel } from './verify-sync.mjs'
import { jsonDigest, loadCanonicalObservations, MODEL_SHA256, MODEL_COMMIT } from './verify-reference.mjs'

// These are decision-gate unit controls, NOT browser/source-fidelity evidence.
const native = { durationSeconds: 2.1, fps: 30, pts: [0, 1, 2] }
const frame = (time, classification = 'machine') => ({ timeSeconds: time, decodedTimeSeconds: time, shotId: 'shot', classification, views: [{ id: 'main' }] })
const observations = { shots: [{ id: 'shot', startSeconds: 0, endSeconds: 2.1, classification: 'machine', hasCorrespondingMachine: true }], frames: [frame(0), frame(1), frame(2)], coverage: { changeTimesSeconds: [0.1, 0.2] } }

test('canonical observation loading rejects missing, corrupt or invalid gzip without using plain siblings', async t => {
  const root = await mkdtemp(join(tmpdir(), 'canonical-observation-boundaries-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const content = join(root, 'content', 'canonical-native')
  await mkdir(content, { recursive: true })
  await writeFile(join(content, 'fixture.observations.json'), '{"frames": []}')
  const valid = gzipSync('{"frames": []}')
  const badCrc = Buffer.from(valid)
  badCrc[badCrc.length - 8] ^= 1
  for (const [label, stored, error] of [
    ['missing', null, { code: 'ENOENT' }],
    ['bad-header', Buffer.from('not a gzip stream'), { code: 'Z_DATA_ERROR' }],
    ['truncated', valid.subarray(0, -8), { code: 'Z_BUF_ERROR' }],
    ['bad-crc', badCrc, { code: 'Z_DATA_ERROR' }],
    ['invalid-json', gzipSync('{"frames":'), SyntaxError],
  ]) {
    await t.test(label, async () => {
      if (stored !== null) await writeFile(join(content, 'fixture.observations.json.gz'), stored)
      await assert.rejects(loadCanonicalObservations(root, 'fixture'), error)
    })
  }
})

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

test('render verification separates the real representation digest from pinned raw native identity', () => {
  const descriptor = {
    schemaVersion: 2, kind: 'lossless-web-model-representation',
    source: { sha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT },
    identity: { mapSha256: 'c'.repeat(64), canonicalSha256: 'd'.repeat(64), renamedNodes: 1, nodeCount: 2 },
    representation: { path: 'models/ha-harmonic-analyzer.glb', sha256: 'a'.repeat(64), byteLength: 4096, codec: 'EXT_meshopt_compression' },
    pipeline: { version: 2, steps: ['native-identity-map', 'exact-dedup', 'meshopt'], codecVersion: 'meshoptimizer@0.22.0' },
    equivalence: { method: 'decoded-per-drawable-exact-after-native-identity-v2', semanticSha256: 'b'.repeat(64), drawableCount: 435 },
  }
  const nativeIdentity = {
    modelSha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT,
    nativeIdentityMapSha256: descriptor.identity.mapSha256,
    canonicalModelSha256: descriptor.identity.canonicalSha256,
  }
  const actual = {
    videoId: 'fixture', playerVideoId: 'fixture', modelState: 'ready', missingBindings: [],
    modelProvenance: {
      sourceSha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT, representationKind: descriptor.kind,
      identity: 'matched', expectedSha256: descriptor.representation.sha256, observedSha256: descriptor.representation.sha256,
      expectedByteLength: descriptor.representation.byteLength, observedByteLength: descriptor.representation.byteLength,
    },
    physics: { springForcesN: Array(20).fill(1), springLengthsM: Array(20).fill(0.1), equilibriumResidualNm: 0 },
  }
  requireModel(actual, 'fixture', descriptor, nativeIdentity)
  for (const change of [
    { observedSha256: MODEL_SHA256 },
    { expectedSha256: MODEL_SHA256 },
    { sourceSha256: 'c'.repeat(64) },
    { sourceCommit: 'd'.repeat(40) },
    { observedByteLength: 4095 },
    { expectedByteLength: 4095 },
    { identity: 'mismatched' },
  ]) assert.throws(() => requireModel({ ...actual, modelProvenance: { ...actual.modelProvenance, ...change } }, 'fixture', descriptor, nativeIdentity), /identity mismatch/)
  const unapprovedSource = structuredClone(descriptor)
  unapprovedSource.source.sha256 = 'c'.repeat(64)
  assert.throws(() => requireModel(actual, 'fixture', unapprovedSource, nativeIdentity), /different native CAD source/)
  for (const field of ['mapSha256', 'canonicalSha256']) {
    const unapprovedIdentity = structuredClone(descriptor)
    unapprovedIdentity.identity[field] = 'e'.repeat(64)
    assert.throws(() => requireModel(actual, 'fixture', unapprovedIdentity, nativeIdentity), /identity|canonical|mapping|association|different native/i)
  }
})
