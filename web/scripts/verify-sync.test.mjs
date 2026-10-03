import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
const { parseOptions, verificationGoal, finishReport, sourceCensus, sourceContourSidecar: joinSourceContours, finishVideo, seekSettlement, sourcePtsInShot, requireSourceViews, measureView, measureFrame, measureContours, playbackInterval, sourceSeedIndex, diagnosticReplayOutcome, requirePausedReview, compareCameraPose, requireModel } = await import(process.env.HARMONIC_VERIFY_SYNC_MODULE ?? './verify-sync.mjs')
import { jsonDigest, sourceLayoutForViews, MODEL_SHA256, MODEL_COMMIT, nativeBodyAssociationIndex } from './verify-reference.mjs'

// These are decision-gate unit controls, NOT browser/source-fidelity evidence.
const BODY_PATH = 'harmonic-analyzer/channel/connecting-rod-20'
function bodyProofTable() {
  const matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
  const body = { status: 'mapped', reason: null, proof: { method: 'exact-original-native-primitive-role-v1',
    historicalSource: { sha256: '2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d', sourceCommit: '1268c23d4a8fc741147c5e09d8d1e45247a71945' },
    currentSource: { sha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT }, qualifiedPartPath: BODY_PATH,
    historicalWorldMatrix: matrix, currentWorldMatrix: matrix, historicalPrimitiveSha256: 'b'.repeat(64), currentPrimitiveSha256: 'b'.repeat(64),
    primitives: [{ mode: 4, attributes: { POSITION: { componentType: 5126, type: 'VEC3', count: 3, normalized: false, typedBytesSha256: 'c'.repeat(64) },
      NORMAL: { componentType: 5126, type: 'VEC3', count: 3, normalized: false, typedBytesSha256: 'd'.repeat(64) } }, indices: null, material: null }] } }
  // Actual Python-produced proofs spell integral floats as 1.0. Measurement must
  // hash this exact string, not JavaScript's numeric reserialization.
  const serializedProof = JSON.stringify(body).replaceAll('WorldMatrix":[1,', 'WorldMatrix":[1.0,')
  return { [BODY_PATH]: { ...body, serializedProof } }
}
const nativeBodyAssociations = bodyProofTable()
const sourceContourSidecar = (frame, originals, table = nativeBodyAssociations) =>
  joinSourceContours(frame, originals, nativeBodyAssociationIndex(table))
function bodyProofRef(table = nativeBodyAssociations) {
  const body = table[BODY_PATH]
  return { status: body.status, reason: body.reason, proofRef: BODY_PATH,
    proofSha256: createHash('sha256').update(body.serializedProof, 'utf8').digest('hex') }
}
const native = { durationSeconds: 2.1, fps: 30, pts: [0, 1, 2] }
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
})

test('incremental runs select one video without requiring the other five', () => {
  const options = parseOptions(['--stage', '50', '--video', 'analysis', '--times', '1'])
  assert.deepEqual(options.videos, ['6dW6VYXp9HM'])
  const census = sourceCensus(observations, { frames: observations.frames, coverage: { changeTimesSeconds: [] } }, native, options)
  assert.deepEqual(census.selected.map(row => row.timeSeconds), [1])
  assert.deepEqual(census.rows.filter(row => row.reasons.includes('mid-interval')).map(row => row.timeSeconds), [])
  assert.equal(options.scoped, true)
})

test('the original source event census is independent of compact keys and keeps missing authored samples', () => {
  const track = { frames: [...observations.frames, frame(0.5)].sort((a, b) => a.timeSeconds - b.timeSeconds), coverage: { changeTimesSeconds: [0.5] } }
  const census = sourceCensus(observations, track, native, parseOptions(['--stage', '50']))
  assert.ok(census.rows.some(row => row.timeSeconds === 0.5 && row.reasons.includes('authored-change-point')))
  for (const time of observations.coverage.changeTimesSeconds) {
    const row = census.rows.find(row => row.timeSeconds === time)
    assert.ok(row.reasons.includes('original-change-point'))
    assert.equal(row.diagnosticOnly, false)
    assert.equal(row.frame, null)
    assert.match(row.unavailableReason, /Missing authored sample/)
  }
})

test('source-declared change events do not borrow nearby authored keys or collapse distinct decimal times', () => {
  const loss = { anchorId: 'event-loss', viewId: 'main', role: 'check', required: true, reason: 'Original event feature unavailable' }
  const source = { shots: observations.shots, coverage: { changeTimesSeconds: [0.4, 0.6, 0.6000001] },
    frames: [frame(0), { ...frame(0.4), unavailable: [loss] }, frame(0.6), frame(0.6000001), frame(1), frame(2)] }
  const track = { frames: [frame(0), frame(0.4001), frame(0.6), frame(1), frame(2)], coverage: { changeTimesSeconds: [] } }
  const census = sourceCensus(source, track, native, parseOptions(['--stage', '50']))
  const declared = census.rows.filter(row => row.reasons.includes('original-change-point'))
  assert.deepEqual(declared.map(row => row.timeSeconds), [0.4, 0.6, 0.6000001])
  assert.equal(declared[0].frame, null)
  assert.equal(declared[0].sourceUnavailable.find(item => item.anchorId === 'event-loss').required, true)
  assert.equal(declared[1].frame.timeSeconds, 0.6)
  assert.equal(declared[2].frame, null)
  const video = videoFixture()
  video.samples = census.rows.filter(row => row.timeSeconds !== 0.6000001).map(row => ({
    ...structuredClone(video.samples[0]), timeSeconds: row.timeSeconds, sampleTimeSeconds: row.frame?.timeSeconds ?? null,
    reasons: row.reasons, required: row.required, unavailable: [], measurements: [measurement('fixed', 'fixed'), measurement('moving', 'moving')] }))
  finishVideo(video, census, parseOptions(['--stage', '50']))
  assert.equal(video.coverage.missingCensusSamples, 1)
  assert.equal(video.coverage.complete, false)
  assert.ok(video.unavailableReasons.some(item => item.timeSeconds === 0.4 && item.anchorId === 'event-loss'))
})

test('requesting an omitted original event cannot turn diagnostic interpolation into its authored measurement', () => {
  const original = { ...frame(0.5), landmarks: [{ anchorId: 'source-feature', viewId: 'main', status: 'observed', pixel: [31, 47] }] }
  const source = { shots: observations.shots, coverage: { changeTimesSeconds: [0.5] },
    frames: [frame(0), original, frame(1), frame(2)] }
  const track = { frames: observations.frames, coverage: { changeTimesSeconds: [] } }
  for (const args of [['--stage', '50'], ['--stage', '50', '--times', '0.5']]) {
    const row = sourceCensus(source, track, native, parseOptions(args)).rows.find(row => row.timeSeconds === 0.5)
    assert.ok(row.reasons.includes('original-change-point'))
    assert.equal(row.diagnosticOnly, false)
    assert.equal(row.frame, null)
    assert.match(row.unavailableReason, /Missing authored sample/)
  }
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
  finishVideo(video, censusFixture, parseOptions(['--stage', '5', '--player', 'local']))
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
  input: { crankTurns: 0, amplitudes: Array(20).fill(0), phases: Array(20).fill(0), gearing: 'small-large', magnification: 1,
    setup: { counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0, coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 } },
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
  const layout = sourceLayoutForViews([view])
  const capture = { method: 'gpu-readback', status: 'captured', visibilityMode: 'depth-off-landmark-projection', viewId: 'main', timeSeconds: 1, drawRevision: 1,
    presentation: 'native', sourceOpacity: 1, sourceLayout: layout, resolvedImagePlaneWarp: null, nativeViewportBackingPixels: null, destinationCellSourcePixels: [1, 1],
    landmarks: observations.map(observed => ({ id: observed.anchorId, state: 'rendered', worldMetres: [0, 0, 0], worldReason: null, sourcePixels: observed.pixel, canvasPixels: observed.pixel, uncertaintySourcePixels: 0.5, uncertaintyCanvasPixels: 0.5, reason: null })) }
  const mechanism = { method: 'actual-native-mechanism-solve', status: 'rendered', viewId: 'main', timeSeconds: 1, sourceDrawRevision: 1, channelAnglesRad: Array(20).fill(0), input: view.input, sourceLayout: layout, resolvedImagePlaneWarp: null }
  const response = { captures: [{ viewId: 'main', capture, mechanism }], actual: { mode: 'reference-review', playerState: 'paused', modelTime: 1,
    sourceDrawRevision: 1, sourceDrawTimeSeconds: 1, views: [{ ...view, sourceLayout: layout, resolvedImagePlaneWarp: null }] },
    native: { mediaTime: 1, paused: true, seeking: false }, canvas: { tag: 'CANVAS', width: 1920, height: 1080, clientWidth: 1920, clientHeight: 1080, devicePixelRatio: 1 } }
  return { view, frame, observations, anchors, response, capture, seeds: new Map() }
}
const measureFixture = fixture => measureView(fixture.view, fixture.response, fixture.frame, fixture.observations, 96, fixture.anchors, fixture.seeds)

function finishMeasuredFixture(fixture, result) {
  const video = videoFixture()
  Object.assign(video.samples[0], { timeSeconds: fixture.frame.timeSeconds, sampleTimeSeconds: fixture.frame.timeSeconds, measurements: result.measured ?? result.measurements,
    contourChecks: result.contourChecks, contourFits: result.contourFits, unavailable: result.unavailable,
    maxClockSkewSeconds: result.clockSkewSeconds ?? result.maxClockSkewSeconds, status: result.status ?? 'passed' })
  const rows = [{ timeSeconds: fixture.frame.timeSeconds, required: true, reasons: ['every-second'] }]
  finishVideo(video, { rows, selected: rows }, parseOptions(['--stage', '50']))
  return video
}

test('unavailable native counterparts remain required losses even if a ghost point has matching GPU pixels', () => {
  for (const retainGhost of [false, true]) {
    const fixture = measuredViewFixture()
    const observed = fixture.observations[2], anchor = fixture.anchors.get(observed.anchorId)
    anchor.nativeAssociation = { status: 'unavailable', reason: 'Original native primitive changed; fresh source feature mapping required', proof: {} }
    if (!retainGhost) {
      delete anchor.partPath
      delete anchor.partLocalMetres
      delete anchor.correspondenceEvidence
    }
    fixture.frame.landmarks = fixture.observations
    const result = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors)
    assert.ok(!result.measurements.some(item => item.anchorId === observed.anchorId))
    const loss = result.unavailable.find(item => item.anchorId === observed.anchorId)
    assert.equal(loss.required, true)
    assert.deepEqual(loss.sourcePixels, observed.pixel)
    assert.equal(loss.originalRole, 'check')
    assert.equal(result.status, 'unavailable')
    const finished = finishMeasuredFixture(fixture, result)
    assert.equal(finished.coverage.passedRequiredSamples, 0)
    assert.equal(finished.stageMeasurement.status, 'unmeasured')
  }
})

test('source-loss obligation blocks passing surviving landmarks for CHECK, FIT and unknown roles', () => {
  for (const role of ['check', 'fit', null]) {
    const fixture = measuredViewFixture()
    const loss = { anchorId: 'lost-control', viewId: 'main', role, reason: 'Actual source patch is unresolved',
      trackingEvidence: { seedTimeSeconds: 0, seedPatchCorrelation: 0.2 } }
    fixture.frame.unavailable = [loss]
    const result = measureFixture(fixture), video = finishMeasuredFixture(fixture, result)
    assert.ok(result.measured.every(item => item.status === 'passed'))
    assert.equal(video.coverage.passedRequiredSamples, 0)
    assert.equal(video.coverage.complete, false)
    assert.equal(video.status, 'unavailable')
    assert.equal(video.stageMeasurement.status, 'unmeasured')
    const reported = video.unavailableReasons.find(item => item.anchorId === 'lost-control')
    assert.equal(reported.role, role)
    assert.equal(reported.originalRole, role)
    assert.equal(reported.viewId, 'main')
    assert.equal(reported.originalViewId, 'main')
    assert.equal(reported.reason, loss.reason)
    assert.deepEqual(reported.trackingEvidence, loss.trackingEvidence)
    assert.deepEqual(reported.sourceImage, fixture.frame.sourceImage)
    assert.equal(reported.decodedTimeSeconds, fixture.frame.decodedTimeSeconds)
  }
})

test('source-loss obligation without a role or physical mapping remains missing data', () => {
  const fixture = measuredViewFixture()
  fixture.frame.unavailable = [{ anchorId: 'uncatalogued-control', reason: 'No native/source correspondence' }]
  const result = measureFixture(fixture), video = finishMeasuredFixture(fixture, result)
  assert.equal(video.status, 'unavailable')
  const reported = video.unavailableReasons.find(item => item.anchorId === 'uncatalogued-control')
  assert.equal(reported.role, null)
  assert.equal(reported.originalRole, null)
  assert.equal(reported.sourcePixels, null)
  assert.equal(reported.viewId, 'main')
  assert.equal(video.landmarks.measured, 4)
})

test('source-loss sample gate preserves loss-free positive coverage and blocks mixed or absent views', () => {
  const fixture = measuredViewFixture()
  fixture.frame.landmarks = fixture.observations
  const positive = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.equal(positive.status, 'passed')
  assert.equal(finishMeasuredFixture(fixture, positive).stageMeasurement.status, 'passed')
  for (const viewId of ['main', 'inset', 'unmapped-source-view']) {
    const copy = structuredClone(fixture)
    copy.frame.unavailable = [{ anchorId: 'lost-control', viewId, role: 'fit', reason: 'Source loss remains required' }]
    const result = measureFrame(copy.frame, copy.response, 96, copy.anchors, copy.seeds)
    const video = finishMeasuredFixture(copy, result)
    assert.equal(result.status, 'unavailable')
    assert.equal(video.coverage.passedRequiredSamples, 0)
    assert.equal(video.stageMeasurement.status, 'unmeasured')
    assert.equal(video.unavailableReasons.filter(item => item.anchorId === 'lost-control').length, 1)
    assert.equal(video.unavailableReasons.find(item => item.anchorId === 'lost-control').viewId, viewId)
  }
})

test('source-loss sample gate deduplicates the same missing obligation without merging roles or views', () => {
  const fixture = measuredViewFixture(), observed = fixture.observations[3]
  observed.pixel = null
  fixture.frame.landmarks = fixture.observations
  fixture.frame.unavailable = [
    { anchorId: observed.anchorId, role: observed.role, reason: 'Original source feature was lost' },
    { anchorId: observed.anchorId, role: 'fit', reason: 'Separate original FIT obligation' },
    { anchorId: observed.anchorId, viewId: 'inset', role: observed.role, reason: 'Separate source perspective' },
  ]
  const result = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  const same = result.unavailable.filter(item => item.anchorId === observed.anchorId && item.viewId === 'main' && item.role === 'check')
  assert.equal(same.length, 1)
  assert.equal(same[0].reason, 'Original source feature was lost')
  assert.ok(same[0].relatedUnavailable.some(item => item.reason === 'Independent source landmark pixel/measurement is unavailable'))
  assert.equal(result.unavailable.filter(item => item.anchorId === observed.anchorId).length, 3)
  assert.equal(result.status, 'unavailable')
})

test('source-loss sample gate retains required loss when native capture throws and prioritizes measured failure', () => {
  const fixture = measuredViewFixture()
  fixture.frame.landmarks = fixture.observations
  fixture.frame.unavailable = [{ anchorId: 'lost-control', role: null, reason: 'Source control unresolved' }]
  fixture.capture.landmarks[2].sourcePixels = [1200, 800]
  fixture.capture.landmarks[2].canvasPixels = [1200, 800]
  const failed = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.equal(failed.status, 'failed')
  assert.equal(finishMeasuredFixture(fixture, failed).stageMeasurement.status, 'failed')
  fixture.capture.status = 'unavailable'
  const missing = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.equal(missing.status, 'unavailable')
  assert.ok(missing.unavailable.some(item => item.anchorId === 'lost-control' && item.role === null))
  assert.ok(missing.unavailable.some(item => /Missing\/stale actual GPU/.test(item.reason)))
})

test('source-loss sample gate keeps each actual view and original role independently required', () => {
  const fixture = measuredViewFixture(), inset = sourceView('inset', [960, 0, 960, 1080])
  fixture.view.rectSourcePixels = [0, 0, 960, 1080]
  fixture.frame.views.push(inset)
  const insetObservations = fixture.observations.map(item => ({ ...item, anchorId: `inset-${item.anchorId}`, viewId: 'inset', pixel: [item.pixel[0] + 960, item.pixel[1]] }))
  fixture.frame.landmarks = [...fixture.observations, ...insetObservations]
  for (const item of insetObservations) fixture.anchors.set(item.anchorId, { ...fixture.anchors.get(item.anchorId.slice(6)) })
  const layout = sourceLayoutForViews(fixture.frame.views), main = fixture.response.captures[0]
  main.capture.sourceLayout = layout
  main.mechanism.sourceLayout = layout
  fixture.response.actual.views = fixture.frame.views.map(view => ({ ...view, sourceLayout: layout, resolvedImagePlaneWarp: null }))
  fixture.response.captures.push({ viewId: 'inset',
    capture: { ...structuredClone(main.capture), viewId: 'inset', landmarks: insetObservations.map(item => ({
      ...structuredClone(main.capture.landmarks[0]), id: item.anchorId, sourcePixels: item.pixel, canvasPixels: item.pixel })) },
    mechanism: { ...structuredClone(main.mechanism), viewId: 'inset', input: inset.input } })
  const positive = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.equal(positive.status, 'passed')
  assert.equal(finishMeasuredFixture(fixture, positive).status, 'passed')
  fixture.frame.unavailable = [
    { anchorId: 'same-source-control', viewId: 'main', role: 'fit', reason: 'Main-view source control lost' },
    { anchorId: 'same-source-control', viewId: 'inset', role: 'check', reason: 'Inset-view source control lost' },
  ]
  const result = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds), video = finishMeasuredFixture(fixture, result)
  assert.equal(video.coverage.passedRequiredSamples, 0)
  assert.equal(video.status, 'unavailable')
  assert.deepEqual(video.unavailableReasons.filter(item => item.anchorId === 'same-source-control').map(item => [item.viewId, item.originalRole]), [['main', 'fit'], ['inset', 'check']])
})

test('source-loss exact-exposure join retains authoritative role and provenance after a compact view rename', () => {
  const fixture = measuredViewFixture()
  fixture.frame.shotId = 'shot'
  fixture.frame.sourceImage = sourceImage(30, '3'.repeat(64))
  fixture.frame.landmarks = fixture.observations
  fixture.frame.unavailable = [{ anchorId: 'lost-control', viewId: 'main', reason: 'Actual source patch lost' }]
  const original = { ...fixture.frame, views: [sourceView('presenter-whole')], landmarks: [], unavailable: [{
    anchorId: 'lost-control', viewId: 'presenter-whole', role: 'fit', reason: 'Actual source patch lost',
    trackingEvidence: { sourceImage: fixture.frame.sourceImage, seedPatchCorrelation: 0.2 },
  }] }
  const source = { shots: observations.shots, frames: [original] }, track = { frames: [fixture.frame] }
  const row = sourceCensus(source, track, native, parseOptions(['--times', '1'])).selected[0]
  const result = measureFrame(row.frame, fixture.response, 96, fixture.anchors, fixture.seeds), video = finishMeasuredFixture(fixture, result)
  const loss = video.unavailableReasons.filter(item => item.anchorId === 'lost-control')
  assert.equal(loss.length, 1)
  assert.equal(loss[0].viewId, 'main')
  assert.equal(loss[0].originalViewId, 'presenter-whole')
  assert.equal(loss[0].originalRole, 'fit')
  assert.deepEqual(loss[0].trackingEvidence, original.unavailable[0].trackingEvidence)
  assert.equal(video.status, 'unavailable')
  original.sourceImage = sourceImage(30, '4'.repeat(64))
  const otherExposure = sourceCensus(source, track, native, parseOptions(['--times', '1'])).selected[0]
  const unresolved = measureFrame(otherExposure.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.equal(unresolved.unavailable.find(item => item.anchorId === 'lost-control').originalRole, null)
  assert.equal(unresolved.status, 'unavailable')
})

test('source-loss ambiguous view mapping and unresolved null controls cannot turn surviving measurements into a pass', () => {
  const fixture = measuredViewFixture()
  fixture.frame.shotId = 'shot'
  fixture.frame.sourceImage = sourceImage(30, '3'.repeat(64))
  fixture.frame.landmarks = fixture.observations
  const original = { ...fixture.frame, views: [sourceView('presenter-whole')], landmarks: [], unavailable: [{
    anchorId: 'lost-control', viewId: 'presenter-whole', role: 'check', reason: 'Original control remains required',
  }] }
  const layers = [sourceView('outgoing'), sourceView('incoming')]
  const row = sourceCensus({ shots: observations.shots, frames: [original] }, { frames: [{ ...fixture.frame, views: layers }] }, native, parseOptions(['--times', '1'])).selected[0]
  assert.throws(() => requireSourceViews(row), /presenter-whole/)
  assert.equal(row.frame.unavailable[0].originalViewId, 'presenter-whole')
  assert.equal(row.frame.unavailable[0].originalRole, 'check')
  assert.match(row.frame.unavailable[0].viewMappingUnavailableReason, /Ambiguous/)
  const unavailable = measureFrame(row.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.equal(finishMeasuredFixture(fixture, unavailable).status, 'unavailable')
  fixture.frame.unavailable = [null]
  const missing = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds), video = finishMeasuredFixture(fixture, missing)
  assert.equal(missing.status, 'unavailable')
  assert.equal(video.status, 'unavailable')
  assert.equal(video.stageMeasurement.status, 'unmeasured')
  assert.equal(video.unavailableReasons[0].role, null)
  assert.equal(video.unavailableReasons[0].sourcePixels, null)
  assert.equal(video.unavailableReasons[0].anchorId, undefined)
})

test('source-loss census gate restores omitted losses from passing summaries and rejected source rows', () => {
  for (const rejected of [false, true]) {
    const video = videoFixture(), loss = { anchorId: 'lost-control', viewId: 'main', role: 'fit', reason: 'Required source loss cannot disappear at the sample boundary' }
    const sourceFrame = { ...frame(0), sourceImage: sourceImage(0, '3'.repeat(64)), unavailable: [loss] }
    const row = { ...censusFixture.rows[0], frame: rejected ? null : sourceFrame,
      ...(rejected ? { sourceUnavailable: [{ ...loss, originalViewId: 'main', originalRole: 'fit', sourceImage: sourceFrame.sourceImage, decodedTimeSeconds: 0 }] } : {}) }
    finishVideo(video, { rows: [row], selected: [row] }, parseOptions(['--stage', '50']))
    assert.equal(video.samples[0].status, 'unavailable')
    assert.equal(video.coverage.passedRequiredSamples, 0)
    assert.equal(video.coverage.complete, false)
    assert.equal(video.coverage.unavailableRequiredSamples, 1)
    assert.equal(video.status, 'unavailable')
    assert.equal(video.stageMeasurement.status, 'unmeasured')
    const reported = video.unavailableReasons.find(item => item.anchorId === 'lost-control')
    assert.equal(reported.originalRole, 'fit')
    assert.deepEqual(reported.sourceImage, sourceFrame.sourceImage)
    assert.equal(reported.decodedTimeSeconds, 0)
  }
})

test('source-loss original census declarations survive actual missing compact selection without borrowing neighboring losses', () => {
  for (const [decodedTimeSeconds, shotId] of [[1, 'shot'], [0.999, 'shot'], [1, 'unresolved-original-shot']]) {
    const original = { ...frame(1), decodedTimeSeconds, shotId, sourceImage: sourceImage(30, '3'.repeat(64)),
      views: [sourceView('presenter-whole')], unavailable: [
        { anchorId: 'original-fit-loss', viewId: 'presenter-whole', role: 'fit', reason: 'Original FIT control was lost',
          trackingEvidence: { seedTimeSeconds: 0.5, sourcePatchCorrelation: 0.2 } },
        { anchorId: 'original-unknown-loss', viewId: 'presenter-whole', reason: 'Correspondence and original role remain unresolved' },
        { anchorId: 'original-null-loss', viewId: null, originalViewId: null, role: null, originalRole: null,
          sourcePixels: null, sourceImage: null, decodedTimeSeconds: null, trackingEvidence: null,
          reason: 'Original source namespace and binding remain explicitly null' },
      ] }
    const neighbor = { ...original, timeSeconds: 0.9, decodedTimeSeconds: 0.9, sourceImage: sourceImage(27, '4'.repeat(64)),
      unavailable: [{ anchorId: 'neighbor-loss', role: 'check', reason: 'Different real exposure; cannot be borrowed' }] }
    const compact = { ...frame(0), views: [sourceView('main')], sourceImage: sourceImage(0, '5'.repeat(64)) }
    const options = parseOptions(['--stage', '50', '--times', '1'])
    const census = sourceCensus({ shots: observations.shots, frames: [neighbor, original] }, { frames: [compact] }, native, options)
    const row = census.selected[0], video = videoFixture()
    assert.equal(row.frame, null)
    assert.match(row.unavailableReason, /Missing authored sample/)
    Object.assign(video.samples[0], { timeSeconds: 1, sampleTimeSeconds: null })
    finishVideo(video, census, options)
    assert.equal(video.stageMeasurement.scopedSamples.status, 'unavailable')
    assert.equal(video.samples[0].status, 'unavailable')
    assert.equal(video.coverage.passedRequiredSamples, 0)
    const fit = video.unavailableReasons.find(item => item.anchorId === 'original-fit-loss')
    assert.equal(fit.viewId, 'presenter-whole')
    assert.equal(fit.originalViewId, 'presenter-whole')
    assert.equal(fit.role, 'fit')
    assert.equal(fit.originalRole, 'fit')
    assert.equal(fit.reason, original.unavailable[0].reason)
    assert.deepEqual(fit.trackingEvidence, original.unavailable[0].trackingEvidence)
    assert.deepEqual(fit.sourceImage, original.sourceImage)
    assert.equal(fit.decodedTimeSeconds, decodedTimeSeconds)
    assert.equal(fit.sourceShotId, shotId)
    const unknown = video.unavailableReasons.find(item => item.anchorId === 'original-unknown-loss')
    assert.equal(unknown.role, null)
    assert.equal(unknown.originalRole, null)
    assert.equal(unknown.sourcePixels, null)
    const unresolved = video.unavailableReasons.find(item => item.anchorId === 'original-null-loss')
    for (const field of ['viewId', 'originalViewId', 'role', 'originalRole', 'sourcePixels', 'sourceImage', 'decodedTimeSeconds', 'trackingEvidence']) {
      assert.equal(unresolved[field], null)
    }
    assert.equal(unresolved.reason, original.unavailable[2].reason)
    assert.equal(video.unavailableReasons.some(item => item.anchorId === 'neighbor-loss'), false)
    assert.deepEqual(census.rows.find(row => row.timeSeconds === 0).sourceUnavailable, [])
  }
})

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
    schemaVersion: 1, kind: 'lossless-web-model-representation',
    source: { sha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT },
    representation: { path: 'models/harmonic-analyzer.glb', sha256: 'a'.repeat(64), byteLength: 4096, codec: 'EXT_meshopt_compression' },
    pipeline: { version: 1, steps: ['exact-dedup', 'meshopt'], codecVersion: 'meshoptimizer@0.22.0' },
    equivalence: { method: 'decoded-per-drawable-exact-v1', semanticSha256: 'b'.repeat(64), drawableCount: 435 },
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
  requireModel(actual, 'fixture', descriptor)
  for (const change of [
    { observedSha256: MODEL_SHA256 },
    { expectedSha256: MODEL_SHA256 },
    { sourceSha256: 'c'.repeat(64) },
    { sourceCommit: 'd'.repeat(40) },
    { observedByteLength: 4095 },
    { expectedByteLength: 4095 },
    { identity: 'mismatched' },
  ]) assert.throws(() => requireModel({ ...actual, modelProvenance: { ...actual.modelProvenance, ...change } }, 'fixture', descriptor), /identity mismatch/)
  const unapprovedSource = structuredClone(descriptor)
  unapprovedSource.source.sha256 = 'c'.repeat(64)
  assert.throws(() => requireModel(actual, 'fixture', unapprovedSource), /different native CAD source/)
})

function contourFixture(drawRevision = 1) {
  const fixture = measuredViewFixture(), { view, frame, response, capture } = fixture
  frame.shotId = 'shot'
  frame.classification = 'machine'
  frame.sourceImage = sourceImage(30, 'a'.repeat(64))
  const check = { id: 'right-exterior', role: 'check', partPath: BODY_PATH, originalPartPath: BODY_PATH, nativeAssociation: bodyProofRef(),
    sourceContourPixels: [[100.5, 100.5], [120.5, 100.5], [140.5, 100.5]], uncertaintyPx: 3,
    measurementEvidence: { sourceImage: frame.sourceImage, evidence: 'Original measured partial exterior edge; original CHECK role, not a newly independent camera/input fit.' } }
  const original = { ...frame, views: [{ ...view, sourceContourChecks: [check] }] }
  Object.assign(frame, sourceContourSidecar(frame, [original]))
  capture.drawRevision = drawRevision
  response.captures[0].mechanism.sourceDrawRevision = drawRevision
  response.actual.sourceDrawRevision = drawRevision
  // Native triangle/background boundaries produce actual depth-ID samples.
  // Line/sprite-only visibility has pixels but no eligible contour samples.
  const part = { partPath: check.partPath, status: 'visible', pixelCount: 1024, contourPixelCount: 40,
    contourSourcePixels: [[103.5, 104.5], [120.5, 100.5], [140.5, 100.5], [1800.5, 900.5]], uncertaintySourcePixels: 2 }
  const visibility = { method: 'gpu-readback', visibilityMode: 'depth-tested-native-surfaces', status: 'captured', viewId: 'main',
    timeSeconds: 1, drawRevision, rectSourcePixels: view.rectSourcePixels, presentation: 'native', sourceOpacity: 1,
    camera: { ...view.camera, principalPointViewportPixels: [960, 540] }, sourceLayout: capture.sourceLayout,
    resolvedImagePlaneWarp: null, nativeViewportBackingPixels: null, destinationCellSourcePixels: [1, 1], parts: [part] }
  response.captures[0].partVisibility = visibility
  return { ...fixture, check, original, visibility, part }
}
const measureContourFixture = (fixture, tolerancePx = 10) => measureContours(fixture.view, fixture.response, fixture.frame, tolerancePx)

test('exact source contour packets preserve partial CHECK residuals with additive uncertainty', () => {
  const fixture = contourFixture(), result = measureContourFixture(fixture), measured = result.measured[0]
  assert.deepEqual(result.unavailable, [])
  assert.equal(measured.rawErrorPx, 5)
  assert.equal(measured.errorPx, 10)
  assert.equal(measured.status, 'passed')
  assert.deepEqual(measured.worstSourcePixel, [100.5, 100.5])
  assert.deepEqual(measured.nearestNativePixel, [103.5, 104.5])
  assert.equal(measureContourFixture(fixture, 9.999).measured[0].status, 'failed')
  fixture.part.contourSourcePixels = fixture.part.contourSourcePixels.slice(1)
  assert.equal(measureContourFixture(fixture, 25).measured[0].rawErrorPx, 20)
})

test('literal shared body proofs reach actual contour measurement despite Python float spelling', () => {
  const fixture = contourFixture()
  assert.equal(measureContourFixture(fixture).measured[0].errorPx, 10)
  assert.equal(measureContourFixture(fixture).measured[0].status, 'passed')
  const cloned = structuredClone(fixture.frame)
  const forged = measureContours(fixture.view, fixture.response, cloned, 10)
  assert.deepEqual(forged.measured, [])
  assert.match(forged.unavailable[0].reason, /native-body proof reference/)
})

test('missing, forged, old-model and unavailable body references remain required census losses', () => {
  const cases = [
    (table, check) => { delete table[BODY_PATH] },
    (table, check) => { check.nativeAssociation.proofSha256 = 'e'.repeat(64) },
    (table, check) => { check.nativeAssociation.proofRef = 'harmonic-analyzer/channel/connecting-rod-19' },
    (table, check) => { check.originalPartPath = 'harmonic-analyzer/channel/connecting-rod-19' },
    (table, check) => { check.nativeAssociation.status = 'unavailable' },
    (table, check) => { table[BODY_PATH].proof.currentSource.sha256 = 'f'.repeat(64) },
    (table, check) => { table[BODY_PATH].serializedProof = '{' },
    (table, check) => { check.nativeAssociation = { status: 'mapped', reason: null, proof: table[BODY_PATH].proof } },
    (table, check) => {
      const body = table[BODY_PATH]
      body.proof.currentSource = { ...body.proof.historicalSource }
      body.serializedProof = JSON.stringify({ status: body.status, reason: body.reason, proof: body.proof })
      check.nativeAssociation = bodyProofRef(table)
    },
    (table, check) => {
      const body = table[BODY_PATH]
      body.status = 'unavailable'; body.reason = 'Original geometry changed; fresh primary mapping required'
      body.serializedProof = JSON.stringify({ status: body.status, reason: body.reason, proof: body.proof })
      check.nativeAssociation = bodyProofRef(table)
      delete check.partPath
    },
  ]
  for (const mutate of cases) {
    const fixture = contourFixture(), table = bodyProofTable(), original = structuredClone(fixture.original)
    const check = original.views[0].sourceContourChecks[0]
    mutate(table, check)
    const source = { shots: observations.shots, frames: [original], nativeBodyAssociations: table }
    const row = sourceCensus(source, { frames: [fixture.frame] }, native, parseOptions(['--times', '1'])).selected[0]
    assert.deepEqual(row.frame.contourChecks, [])
    const loss = row.frame.unavailable.find(item => item.contourId === check.id)
    assert.equal(loss.required, true)
    assert.equal(loss.originalRole, 'check')
    assert.deepEqual(loss.sourcePixels, check.sourceContourPixels)
    assert.deepEqual(loss.sourceImage, original.sourceImage)
    assert.equal(loss.decodedTimeSeconds, original.decodedTimeSeconds)
    const measured = measureContours(fixture.view, fixture.response, row.frame, 10)
    assert.deepEqual(measured.measured, [])
    assert.equal(measured.unavailable[0].contourId, check.id)
  }
})

test('unavailable frame-level body facts retain unknown views and required source losses', () => {
  const fixture = contourFixture(), original = structuredClone(fixture.original)
  delete original.views[0].sourceContourChecks
  original.sourceRodBodyMeasurements = [{ id: 'unresolved-rod-body', partPath: BODY_PATH, originalPartPath: BODY_PATH,
    viewId: null, nativeAssociation: { ...bodyProofRef(), proofSha256: 'e'.repeat(64) },
    sourceLinePixels: [[123, 456], [321, 654]], measurementEvidence: { sourceImage: original.sourceImage } }]
  const row = sourceCensus({ shots: observations.shots, frames: [original], nativeBodyAssociations },
    { frames: [fixture.frame] }, native, parseOptions(['--times', '1'])).selected[0]
  const loss = row.frame.unavailable.find(item => item.contourId === 'unresolved-rod-body')
  assert.equal(loss.required, true)
  assert.equal(loss.originalViewId, null)
  assert.equal(loss.originalRole, null)
  assert.deepEqual(loss.sourcePixels, [[123, 456], [321, 654]])
  assert.deepEqual(loss.sourceImage, original.sourceImage)
})

test('partial original endpoints at the last source rows remain measured rather than extrapolated or dropped', () => {
  const fixture = contourFixture()
  fixture.check.sourceContourPixels = [[100, 1078], [100, 1079]]
  fixture.part.contourSourcePixels = [[100, 1077]]
  const measured = measureContourFixture(fixture).measured[0]
  assert.deepEqual(measured.sourcePixels, [[100, 1078], [100, 1079]])
  assert.equal(measured.rawErrorPx, 2)
  assert.equal(measured.errorPx, 7)
})

test('source packet joins reject substituted SHA, byte format, decoded pixels, frame index, exact PTS and layout', () => {
  const fixture = contourFixture()
  for (const mutate of [
    original => { original.sourceImage.sourceSha256 = 'b'.repeat(64) },
    original => { original.sourceImage.sha256Bgr8 = 'b'.repeat(64) },
    original => { original.sourceImage.frameIndex++ },
    original => { original.sourceImage.frameIndex++; original.decodedTimeSeconds += 1 / 30 },
    original => { original.decodedTimeSeconds += Number.EPSILON },
    original => { original.shotId = 'another-shot' },
    original => { original.sourceImage.pixelFormat = 'gray8'; original.sourceImage.sha256Gray8 = original.sourceImage.sha256Bgr8; delete original.sourceImage.sha256Bgr8 },
    original => { original.sourceImage.sha256Gray8 = original.sourceImage.sha256Bgr8 },
    original => { delete original.sourceImage },
    original => { original.views[0].rectSourcePixels = [0, 0, 1920, 1079] },
    original => { original.views[0].presentation = 'horizontal-mirror' },
    original => { original.views[0].composite = { mode: 'crossfade', groupId: 'fade', imageLayerId: 'other', opacity: 1 } },
    original => { original.views[0].sourceContourChecks[0].measurementEvidence.sourceImage = sourceImage(30, 'c'.repeat(64)) },
    original => { original.views.push(sourceView('missing-original-inset', [500, 500, 10, 10])) },
  ]) {
    const original = structuredClone(fixture.original)
    mutate(original)
    const joined = sourceContourSidecar(fixture.frame, [original])
    assert.deepEqual(joined.contourChecks, [])
    assert.equal(joined.contourJoinUnavailable[0].role, 'check')
    assert.equal(joined.contourJoinUnavailable[0].status, 'source-unavailable')
  }
  const original = structuredClone(fixture.original), selected = structuredClone(fixture.frame)
  for (const row of [original, selected]) {
    row.sourceImage = { frameIndex: 30, pixelFormat: 'gray8', sha256Gray8: 'a'.repeat(64), width: 1920, height: 1080, sourceSha256: '1'.repeat(64) }
  }
  original.views[0].sourceContourChecks[0].measurementEvidence.sourceImage = original.sourceImage
  const joined = sourceContourSidecar(selected, [original])
  assert.equal(joined.contourChecks[0].check.role, 'check')
  assert.deepEqual(joined.contourJoinUnavailable, [])
})

test('ordered mask layouts must match the original exposure even when the target view ROI is unchanged', () => {
  const fixture = contourFixture(), mask = sourceView('inset', [500, 500, 10, 10])
  fixture.original.views.push(mask)
  fixture.frame.views.push(mask)
  const exact = sourceContourSidecar(fixture.frame, [fixture.original])
  assert.equal(exact.contourChecks[0].check.id, 'right-exterior')
  const reordered = sourceContourSidecar({ ...fixture.frame, views: [...fixture.frame.views].reverse() }, [fixture.original])
  assert.deepEqual(reordered.contourChecks, [])
  assert.match(reordered.contourJoinUnavailable[0].reason, /ordered view layout/)
})

test('ambiguous view joins and conflicting curves retain every original unavailable CHECK instead of choosing pixels', () => {
  const fixture = contourFixture(), original = structuredClone(fixture.original)
  original.views[0].id = 'source-main'
  const renamed = sourceContourSidecar(fixture.frame, [original])
  assert.equal(renamed.contourChecks[0].viewId, 'main')
  assert.equal(renamed.contourChecks[0].originalViewId, 'source-main')
  const ambiguous = sourceContourSidecar({ ...fixture.frame, views: [sourceView('outgoing'), sourceView('incoming')] }, [original])
  assert.deepEqual(ambiguous.contourChecks, [])
  assert.match(ambiguous.contourJoinUnavailable[0].reason, /Ambiguous/)
  const conflicting = structuredClone(fixture.original)
  conflicting.views[0].sourceContourChecks[0].sourceContourPixels[0] = [500, 500]
  const refused = sourceContourSidecar(fixture.frame, [fixture.original, conflicting, fixture.original])
  assert.deepEqual(refused.contourChecks, [])
  assert.deepEqual(refused.contourJoinUnavailable.map(item => item.check.sourceContourPixels[0]), [[100.5, 100.5], [500, 500]])
})

test('alias-only CHECK curves remain unavailable alongside an exact selected curve without borrowing their pixels', () => {
  const fixture = contourFixture(), alias = structuredClone(fixture.original)
  alias.decodedTimeSeconds += Number.EPSILON
  alias.views[0].sourceContourChecks[0].id = 'alias-only'
  alias.views[0].sourceContourChecks[0].sourceContourPixels = [[1700, 700], [1700, 800]]
  const joined = sourceContourSidecar(fixture.frame, [alias, fixture.original, structuredClone(alias)])
  assert.deepEqual(joined.contourChecks.map(item => item.check.id), ['right-exterior'])
  assert.deepEqual(joined.contourJoinUnavailable.map(item => [item.contourId, item.role, item.status]), [['alias-only', 'check', 'source-unavailable']])
  assert.deepEqual(joined.contourJoinUnavailable[0].check.sourceContourPixels, [[1700, 700], [1700, 800]])
})

test('FIT and absent role cannot qualify as CHECK or promote inherited CHECK-informed camera/input to a new holdout', () => {
  const fixture = contourFixture()
  fixture.check.role = 'fit'
  const fit = measureContourFixture(fixture)
  assert.deepEqual(fit.measured, [])
  assert.deepEqual(fit.unavailable, [])
  assert.equal(fit.retainedFits[0].status, 'fit-retained-unmeasured')
  const video = videoFixture()
  video.samples[0].measurements = []
  video.samples[0].contourChecks = fit.retainedFits
  video.samples[0].contourFits = fit.retainedFits
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.contourChecks.measured, 0)
  assert.equal(video.landmarks.checks, 0)
  assert.notEqual(video.stageMeasurement.status, 'passed')
  for (const role of [undefined, null, 'CHECK']) {
    const original = structuredClone(fixture.original)
    original.views[0].sourceContourChecks[0].role = role
    const joined = sourceContourSidecar(fixture.frame, [original])
    assert.deepEqual(joined.contourChecks, [])
    assert.match(joined.contourJoinUnavailable[0].reason, /authoritative explicit FIT\/CHECK role/)
  }
  fixture.check.role = 'check'
  fixture.view.cameraProvenance = { kind: 'source-fit', evidence: 'Conditional on inherited CHECK-informed bank/gearing/cam/magnification.' }
  const measured = measureContourFixture(fixture).measured[0]
  assert.equal(measured.holdoutQualification, 'not-established-by-contour-role')
  assert.equal(measured.observedSourceInternalMotion, 'unmeasured')
  assert.deepEqual(measured.cameraProvenance, fixture.view.cameraProvenance)
})

test('missing source pixels, evidence and null uncertainty remain unavailable CHECK obligations', () => {
  for (const mutate of [
    original => { original.views[0].sourceContourChecks[0].sourceContourPixels = null },
    original => { original.views[0].sourceContourChecks[0].sourceContourPixels = [[100, 100], [100, 100]] },
    original => { original.views[0].sourceContourChecks[0].uncertaintyPx = null },
    original => { original.views[0].sourceContourChecks[0].measurementEvidence.evidence = '' },
  ]) {
    const fixture = contourFixture(), original = structuredClone(fixture.original)
    mutate(original)
    const joined = sourceContourSidecar(fixture.frame, [original])
    assert.deepEqual(joined.contourChecks, [])
    assert.equal(joined.contourJoinUnavailable[0].role, 'check')
    assert.equal(joined.contourJoinUnavailable[0].status, 'source-unavailable')
  }
})

test('mandatory off-track CHECK rows cannot manufacture ready views from a camera/input interpolation bracket', () => {
  const fixture = contourFixture(), original = structuredClone(fixture.original)
  original.timeSeconds = 0.5; original.decodedTimeSeconds = 0.5
  original.sourceImage = sourceImage(15, 'b'.repeat(64))
  original.views[0].sourceContourChecks[0].measurementEvidence.sourceImage = original.sourceImage
  original.landmarks = []
  const source = { shots: observations.shots, frames: [original], nativeBodyAssociations }
  const compact = { shots: observations.shots, frames: observations.frames.map(frame => ({ ...frame, views: [fixture.view] })) }
  const row = sourceCensus(source, compact, native, parseOptions(['--times', '0.5'])).selected[0]
  assert.equal(row.required, true)
  assert.equal(row.diagnosticOnly, false)
  assert.equal(row.frame, null)
  assert.equal(row.contourJoinUnavailable[0].contourId, 'right-exterior')
  assert.match(row.unavailableReason, /exact CHECK source exposure/)
})

test('census retains off-track CHECK exposure requirements and rejects ambiguous or missing-image authority', () => {
  const fixture = contourFixture(), originals = [0.5, 0.6].map(time => {
    const original = structuredClone(fixture.original)
    original.timeSeconds = time
    original.decodedTimeSeconds = time
    original.sourceImage = sourceImage(Math.round(time * 30), 'b'.repeat(64))
    original.views[0].sourceContourChecks[0].measurementEvidence.sourceImage = original.sourceImage
    original.landmarks = []
    return original
  })
  const source = { shots: observations.shots, frames: originals, nativeBodyAssociations }
  const compact = { shots: observations.shots, frames: [{ ...frame(1), views: [fixture.view] }] }
  const census = sourceCensus(source, compact, native, parseOptions(['--stage', '50']))
  const obligations = census.rows.filter(row => row.reasons.includes('source-contour-check'))
  assert.deepEqual(obligations.map(row => row.timeSeconds), [0.5, 0.6])
  assert.ok(obligations.every(row => row.required && !row.diagnosticOnly && row.frame === null))
  assert.deepEqual(obligations.map(row => row.contourJoinUnavailable[0].sourceImage.frameIndex), [15, 18])
  const alias = structuredClone(originals[0])
  alias.decodedTimeSeconds += 0.0001
  alias.views[0].sourceContourChecks[0].sourceContourPixels = [[1700, 700], [1700, 800]]
  const ambiguous = sourceCensus({ ...source, frames: [originals[0], alias] }, compact, native, parseOptions(['--stage', '50']))
    .rows.find(row => row.reasons.includes('source-contour-check'))
  assert.equal(ambiguous.required, true)
  assert.equal(ambiguous.frame, null)
  assert.match(ambiguous.unavailableReason, /no single exact source exposure authority/)
  assert.equal(ambiguous.contourJoinUnavailable.length, 2)
  const missing = structuredClone(originals[0])
  delete missing.sourceImage
  const row = sourceCensus({ ...source, frames: [missing] }, compact, native, parseOptions(['--stage', '50']))
    .rows.find(row => row.reasons.includes('source-contour-check'))
  assert.equal(row.required, true)
  assert.equal(row.frame, null)
  assert.equal(row.contourJoinUnavailable[0].contourId, 'right-exterior')
})

test('CHECK contours override compact exemptions without rescuing invalid source PTS or different decoded formats', () => {
  const fixture = contourFixture()
  const exemptShots = observations.shots.map(shot => ({ ...shot, classification: 'non-machine', hasCorrespondingMachine: false }))
  const source = { shots: exemptShots, frames: [{ ...fixture.original, classification: 'non-machine' }], nativeBodyAssociations }
  const compact = { shots: exemptShots, frames: [{ ...fixture.frame, classification: 'non-machine' }] }
  const row = sourceCensus(source, compact, native, parseOptions(['--times', '1'])).selected[0]
  assert.equal(row.required, true)
  assert.equal(row.frame.contourChecks[0].check.role, 'check')
  const gray = structuredClone(compact)
  gray.frames[0].sourceImage = { frameIndex: 30, pixelFormat: 'gray8', sha256Gray8: 'a'.repeat(64), width: 1920, height: 1080, sourceSha256: '1'.repeat(64) }
  const wrongFormat = sourceCensus(source, gray, native, parseOptions(['--times', '1'])).selected[0]
  assert.equal(wrongFormat.required, true)
  assert.deepEqual(wrongFormat.frame.contourChecks, [])
  assert.equal(wrongFormat.frame.contourJoinUnavailable[0].role, 'check')
  const invalid = structuredClone(fixture.original)
  invalid.timeSeconds = 0.9; invalid.decodedTimeSeconds = 1
  const shots = [{ ...observations.shots[0], endSeconds: 1 }]
  const outside = sourceCensus({ shots, frames: [invalid], nativeBodyAssociations }, { shots, frames: [{ ...invalid, views: [fixture.view] }] }, native, parseOptions(['--times', '0.9'])).selected[0]
  assert.equal(outside.required, true)
  assert.equal(outside.frame, null)
  assert.equal(outside.contourJoinUnavailable[0].role, 'check')
  assert.match(outside.unavailableReason, /half-open/)
})

test('older same-time world solves and pixel captures cannot satisfy the current completed draw', () => {
  const older = contourFixture(1), current = contourFixture(2)
  assert.equal(measureContourFixture(current).measured[0].status, 'passed')
  for (const capture of [
    { ...current.response.captures[0], mechanism: older.response.captures[0].mechanism },
    { ...current.response.captures[0], capture: older.capture },
    { ...current.response.captures[0], partVisibility: older.visibility },
  ]) {
    const response = { ...current.response, captures: [capture] }
    const result = measureContours(current.view, response, current.frame, 10)
    assert.deepEqual(result.measured, [])
    assert.equal(result.unavailable[0].role, 'check')
    assert.match(result.unavailable[0].reason, /current completed source draw revision/)
    if (capture.partVisibility === current.visibility) assert.throws(() => measureView(current.view, response, current.frame, current.observations, 96, current.anchors), /current completed source draw revision/)
  }
  for (const mutate of [
    fixture => { delete fixture.capture.drawRevision },
    fixture => { delete fixture.response.actual.sourceDrawRevision },
    fixture => { fixture.visibility.drawRevision = null },
    fixture => { fixture.response.actual.sourceDrawTimeSeconds = 0.99 },
    fixture => { fixture.response.captures[0].mechanism.input = { crankTurns: 1 } },
    fixture => { fixture.response.native.mediaTime = 1.6 },
    fixture => { fixture.response.native.paused = false },
  ]) {
    const fixture = contourFixture()
    mutate(fixture)
    assert.deepEqual(measureContourFixture(fixture).measured, [])
    assert.equal(measureContourFixture(fixture).unavailable[0].role, 'check')
  }
})

test('visible line/sprite pixels cannot substitute for eligible actual native triangle boundary samples', () => {
  const fixture = contourFixture()
  assert.equal(measureContourFixture(fixture).measured[0].errorPx, 10)
  fixture.part.contourSourcePixels = []
  fixture.part.contourPixelCount = 0
  const lineOnly = measureContourFixture(fixture)
  assert.deepEqual(lineOnly.measured, [])
  assert.match(lineOnly.unavailable[0].reason, /sampled depth-ID boundary/)
  assert.equal(lineOnly.unavailable[0].role, 'check')
})

test('native/source boundaries outside scissors or behind later masks remain unavailable with an unmasked positive control', () => {
  for (const target of ['source', 'native', 'unrelated']) {
    const fixture = contourFixture()
    const rect = target === 'source' ? [99, 99, 3, 3] : target === 'native' ? [102, 103, 3, 3] : [500, 500, 10, 10]
    const mask = sourceView('inset', rect), layout = sourceLayoutForViews([fixture.view, mask])
    fixture.frame.views.push(mask)
    fixture.original.views.push(mask)
    Object.assign(fixture.frame, sourceContourSidecar(fixture.frame, [fixture.original]))
    fixture.capture.sourceLayout = layout; fixture.visibility.sourceLayout = layout
    fixture.response.captures[0].mechanism.sourceLayout = layout; fixture.response.actual.views[0].sourceLayout = layout
    const result = measureContourFixture(fixture)
    if (target === 'unrelated') assert.equal(result.measured[0].errorPx, 10)
    else {
      assert.deepEqual(result.measured, [])
      assert.match(result.unavailable[0].reason, /support\/scissor|later mask/)
    }
  }
  const fixture = contourFixture()
  fixture.part.contourSourcePixels[0] = [1920.5, 100.5]
  assert.deepEqual(measureContourFixture(fixture).measured, [])
  assert.equal(measureContourFixture(fixture).unavailable[0].role, 'check')
})

test('contour CHECK counterexamples fail stages without supplying independent fixed/moving landmark coverage', () => {
  const fixture = contourFixture(), video = videoFixture()
  video.samples[0].measurements = []
  video.samples[0].contourChecks = measureContourFixture(fixture, 9).measured
  video.samples[0].status = 'failed'
  finishVideo(video, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(video.stageMeasurement.status, 'failed')
  assert.equal(video.contourChecks.failed, 1)
  assert.equal(video.landmarks.measured, 0)
  assert.ok(video.failures.some(item => item.code === 'hard-fixed-landmark-coverage'))
  assert.ok(video.failures.some(item => item.code === 'hard-moving-landmark-coverage'))
  const missing = videoFixture()
  missing.samples[0].unavailable = [{ contourId: 'retained-original-check', role: 'check', status: 'source-unavailable', reason: 'Missing exact decoded pixels' }]
  missing.samples[0].status = 'unavailable'
  finishVideo(missing, censusFixture, parseOptions(['--stage', '50']))
  assert.equal(missing.contourChecks.unavailable, 1)
  assert.equal(missing.coverage.complete, false)
  assert.notEqual(missing.stageMeasurement.status, 'passed')
})

// Actual admission/measurement consumers produce these synthetic decision-gate
// receipts. They are not browser, source-fidelity or renderer qualification.
function eligiblePixelVideo(kind, errorPx) {
  const fixture = contourFixture()
  fixture.frame.landmarks = fixture.observations
  if (kind === 'contour') {
    fixture.check.sourceContourPixels = [[0, 100], [0, 120], [0, 140]]
    fixture.check.uncertaintyPx = 0
    fixture.part.contourSourcePixels = [[errorPx, 100], [errorPx, 120], [errorPx, 140]]
    fixture.part.uncertaintySourcePixels = 0
  } else {
    const observed = fixture.observations[kind === 'fit-point' ? 0 : 2]
    observed.pixel = [0, observed.pixel[1]]
    observed.uncertaintyPx = 0
    const marker = fixture.capture.landmarks.find(item => item.id === observed.anchorId)
    marker.sourcePixels = [errorPx, observed.pixel[1]]
    marker.canvasPixels = [...marker.sourcePixels]
    marker.uncertaintySourcePixels = 0
  }
  // The incoming 5%-qualified statuses intentionally say passed. finishVideo
  // must independently enforce the stricter goal on the admitted numeric error.
  const result = measureFrame(fixture.frame, fixture.response, 96, fixture.anchors, fixture.seeds)
  assert.deepEqual(result.unavailable, [])
  assert.equal(result.status, 'passed')
  const subject = kind === 'contour' ? result.contourChecks[0]
    : result.measurements.find(item => item.anchorId === (kind === 'fit-point' ? 'anchor-0' : 'anchor-2'))
  assert.equal(subject.errorPx, errorPx)
  assert.equal(subject.status, 'passed')
  const video = videoFixture()
  video.playback.youtube = { status: 'passed' }
  video.shots = [{ id: 'shot', internalMechanismMotion: 'moving' }]
  Object.assign(video.samples[0], result, { timeSeconds: fixture.frame.timeSeconds,
    sampleTimeSeconds: fixture.frame.timeSeconds, sourceShotId: 'shot' })
  const rows = [{ timeSeconds: fixture.frame.timeSeconds, required: true,
    reasons: ['every-second'], frame: fixture.frame }]
  return { video, census: { rows, selected: rows }, fixture, subject }
}

test('the strict full goal is distinct from every explicit qualification stage', () => {
  const full = verificationGoal(parseOptions([]))
  assert.equal(full.kind, 'full-acceptance')
  assert.equal(full.stage, null)
  assert.equal(full.frameWidthPercent, 2)
  assert.equal(full.tolerancePx, 38.4)
  assert.equal(full.requiresOfficialPlayer, true)
  assert.equal(full.requiresLocalPlayer, true)
  for (const [stage, tolerancePx] of [[50, 960], [20, 384], [10, 192], [5, 96]]) {
    const goal = verificationGoal(parseOptions(['--stage', String(stage)]))
    assert.equal(goal.kind, 'stage-qualification')
    assert.equal(goal.stage, stage)
    assert.equal(goal.tolerancePx, tolerancePx)
    assert.equal(goal.requiresOfficialPlayer, stage === 5)
    assert.equal(goal.requiresLocalPlayer, false)
  }
  assert.throws(() => parseOptions(['--stage', '2']))
})

test('the same admitted95px point and CHECK contour fail strict full acceptance but pass explicit5 qualification', () => {
  for (const kind of ['point', 'contour']) {
    const full = eligiblePixelVideo(kind, 95)
    finishVideo(full.video, full.census, parseOptions([]))
    assert.equal(full.subject.status, 'failed')
    assert.equal(full.video.status, 'failed')
    assert.equal(full.video.acceptanceMeasurement.status, 'failed')
    assert.equal(full.video.acceptanceMeasurement.tolerancePx, 38.4)
    assert.equal(Object.hasOwn(full.video, 'stageMeasurement'), false)
    const stage = eligiblePixelVideo(kind, 95)
    finishVideo(stage.video, stage.census, parseOptions(['--stage', '5']))
    assert.equal(stage.subject.status, 'passed')
    assert.equal(stage.video.status, 'passed')
    assert.equal(stage.video.stageMeasurement.status, 'passed')
    assert.equal(stage.video.stageMeasurement.tolerancePx, 96)
    assert.equal(Object.hasOwn(stage.video, 'acceptanceMeasurement'), false)
  }
})

test('strict source point and CHECK contour limits include38.4px equality without certifying unmeasured full geometry', () => {
  for (const kind of ['point', 'contour']) {
    for (const errorPx of [20, 38.4]) {
      const positive = eligiblePixelVideo(kind, errorPx)
      finishVideo(positive.video, positive.census, parseOptions([]))
      assert.equal(positive.video.sourceMeasurement.status, 'passed')
      assert.equal(positive.video.status, 'unavailable')
      assert.equal(positive.video.acceptanceMeasurement.status, 'unmeasured')
      assert.equal(positive.subject.status, 'passed')
    }
    const outside = eligiblePixelVideo(kind, 38.400001)
    finishVideo(outside.video, outside.census, parseOptions([]))
    assert.equal(outside.subject.status, 'failed')
    assert.equal(outside.video.sourceMeasurement.status, 'failed')
    assert.equal(outside.video.acceptanceMeasurement.status, 'failed')
  }
})

test('an admitted FIT point with a preassigned pass cannot hide a finite strict image-error counterexample', () => {
  const fixture = eligiblePixelVideo('fit-point', 95)
  assert.equal(fixture.subject.role, 'fit')
  finishVideo(fixture.video, fixture.census, parseOptions([]))
  assert.equal(fixture.subject.status, 'failed')
  assert.equal(fixture.video.acceptanceMeasurement.status, 'failed')
  assert.equal(fixture.video.landmarks.fixedChecks, 1)
  assert.equal(fixture.video.landmarks.movingChecks, 1)
})

test('strict source qualification requires both original players and a passed manual interaction receipt', () => {
  for (const [receipt, code] of [['youtube', 'official-player-unmeasured'],
    ['local', 'local-player-unmeasured'], ['interaction', 'interaction-unmeasured']]) {
    for (const state of [undefined, 'unavailable', 'failed']) {
      const fixture = eligiblePixelVideo('point', 20)
      const target = receipt === 'interaction' ? fixture.video : fixture.video.playback
      if (state === undefined) delete target[receipt]
      else target[receipt] = { status: state }
      finishVideo(fixture.video, fixture.census, parseOptions([]))
      assert.notEqual(fixture.video.status, 'passed')
      assert.notEqual(fixture.video.acceptanceMeasurement.status, 'passed')
      assert.notEqual(fixture.video.sourceMeasurement.status, 'passed')
      assert.ok(fixture.video.failures.some(item => item.code === code))
    }
  }
})

test('a failed manual interaction object cannot satisfy explicit stage qualification either', () => {
  const fixture = eligiblePixelVideo('point', 20)
  fixture.video.interaction = { status: 'failed' }
  finishVideo(fixture.video, fixture.census, parseOptions(['--stage', '5']))
  assert.equal(fixture.video.stageMeasurement.status, 'failed')
  assert.ok(fixture.video.failures.some(item => item.code === 'interaction-unmeasured'))
})

test('finite admitted diagnostic point and CHECK contour errors override their passed status without supplying mandatory coverage', () => {
  for (const kind of ['point', 'contour']) {
    for (const strict of [true, false]) {
      const diagnostic = eligiblePixelVideo(kind, 95), video = videoFixture()
      video.playback.youtube = { status: 'passed' }
      const sample = { ...diagnostic.video.samples[0], diagnosticOnly: true, reasons: ['mid-interval'] }
      const row = { ...diagnostic.census.rows[0], diagnosticOnly: true, reasons: ['mid-interval'] }
      video.samples.push(sample)
      const rows = [...censusFixture.rows, row]
      finishVideo(video, { rows, selected: rows }, parseOptions(strict ? [] : ['--stage', '5']))
      assert.equal(video.coverage.complete, true)
      assert.equal(video.landmarks.movingChecks, 1)
      if (strict) {
        assert.equal(diagnostic.subject.status, 'failed')
        assert.equal(video.acceptanceMeasurement.status, 'failed')
        assert.ok(video.failures.some(item => item.code === (kind === 'contour'
          ? 'diagnostic-contour-counterexample' : 'diagnostic-pixel-counterexample')))
      } else {
        assert.equal(diagnostic.subject.status, 'passed')
        assert.equal(video.stageMeasurement.status, 'passed')
      }
    }
  }
})

test('unknown required source losses block both full acceptance and stage qualification without guessing their view or pixels', () => {
  for (const strict of [true, false]) {
    const fixture = eligiblePixelVideo('point', 20)
    fixture.fixture.frame.unavailable = [{ featureId: 'unidentified-exterior', viewId: null,
      role: null, sourcePixels: null, required: true, reason: 'Original unidentified source feature remains unresolved.' }]
    finishVideo(fixture.video, fixture.census, parseOptions(strict ? [] : ['--stage', '5']))
    assert.equal(fixture.video.coverage.complete, false)
    assert.notEqual((strict ? fixture.video.acceptanceMeasurement : fixture.video.stageMeasurement).status, 'passed')
    const loss = fixture.video.unavailableReasons.find(item => item.featureId === 'unidentified-exterior')
    assert.equal(loss.required, true)
    assert.equal(loss.originalViewId, null)
    assert.equal(loss.role, null)
    assert.equal(loss.sourcePixels, null)
  }
})

function finishedRouteReceipts(options, kind = 'point', errorPx = 20) {
  return options.videos.map(videoId => {
    const fixture = eligiblePixelVideo(kind, errorPx)
    fixture.video.videoId = videoId
    finishVideo(fixture.video, fixture.census, options)
    return fixture.video
  })
}

test('selected-video and time-scoped full runs cannot become all-six acceptance even with successful eligible measurements', () => {
  for (const args of [['--video', 'analysis'], ['--times', '1']]) {
    const options = parseOptions(args)
    const report = { goal: verificationGoal(options), failures: [], videos: finishedRouteReceipts(options) }
    finishReport(report, options)
    assert.equal(report.status, 'partial')
    assert.equal(report.acceptanceMeasurement.status, 'unmeasured')
    assert.equal(report.acceptanceMeasurement.scope, 'all-six-videos')
    assert.equal(report.sourceMeasurement.status, 'unmeasured')
    if (options.scoped) {
      assert.ok(report.videos.every(video => video.sourceMeasurement.status === 'unmeasured'))
      assert.ok(report.videos.every(video => video.sourceMeasurement.scopedSamples.status === 'passed'))
    } else {
      assert.ok(report.videos.every(video => video.sourceMeasurement.status === 'passed'))
    }
    assert.ok(report.videos.every(video => video.acceptanceMeasurement.status === 'unmeasured'))
  }
})

test('all six unique routes can pass strict source measurement while full geometry acceptance remains unmeasured', () => {
  const options = parseOptions([])
  const report = { goal: verificationGoal(options), failures: [], videos: finishedRouteReceipts(options) }
  finishReport(report, options)
  assert.equal(report.sourceMeasurement.status, 'passed')
  assert.equal(report.status, 'unavailable')
  assert.equal(report.acceptanceMeasurement.status, 'unmeasured')
  assert.equal(report.acceptanceMeasurement.tolerancePx, 38.4)
  assert.ok(report.videos.every(video => video.sourceMeasurement.status === 'passed'
    && video.acceptanceMeasurement.kind === 'full-acceptance' && video.acceptanceMeasurement.scope === 'video'
    && video.acceptanceMeasurement.status === 'unmeasured' && !Object.hasOwn(video, 'stageMeasurement')))
})

test('unchanged admitted landmarks and partial CHECK contours cannot accept absent failed stale wrong-tuple or incomplete geometry', () => {
  for (const kind of ['point', 'contour']) for (const state of ['absent', 'unavailable', 'failed', 'old-code', 'wrong-tuple', 'incomplete', 'metadata-pass']) {
    const fixture = eligiblePixelVideo(kind, 20)
    if (state !== 'absent') fixture.video.nativeQualification = {
      status: state === 'metadata-pass' ? 'passed' : state,
      fullNative: { status: 'passed', drawableCount: state === 'incomplete' ? 20 : 462 },
      sweptSpring: { status: state === 'failed' ? 'failed' : 'passed',
        maxWorldErrorMetres: state === 'failed' ? 3.33e-7 : 0 },
      posedSurface: { status: 'passed' },
      modelSha256: state === 'wrong-tuple' ? '0'.repeat(64) : MODEL_SHA256,
      executedCodeSha256: state === 'old-code' ? '0'.repeat(64) : '1'.repeat(64),
    }
    finishVideo(fixture.video, fixture.census, parseOptions([]))
    assert.equal(fixture.subject.status, 'passed')
    assert.equal(fixture.video.sourceMeasurement.status, 'passed')
    assert.equal(fixture.video.acceptanceMeasurement.status, 'unmeasured')
    assert.equal(fixture.video.status, 'unavailable')
  }
})

test('preassigned all-six full passes cannot replace the absent native geometry qualification consumer', () => {
  const options = parseOptions([])
  const videos = finishedRouteReceipts(options)
  for (const video of videos) {
    video.status = 'passed'
    video.acceptanceMeasurement.status = 'passed'
  }
  const report = { failures: [], videos, nativeQualification: { status: 'passed' } }
  finishReport(report, options)
  assert.equal(report.sourceMeasurement.status, 'passed')
  assert.equal(report.status, 'unavailable')
  assert.equal(report.acceptanceMeasurement.status, 'unmeasured')
})

test('missing duplicate foreign failed or stage-only route receipts cannot certify all-six strict acceptance', () => {
  const options = parseOptions([])
  for (const mismatch of ['missing', 'duplicate', 'foreign', 'measured-failure', 'stage-only', 'global-failure']) {
    const report = { goal: verificationGoal(options), failures: [], videos: finishedRouteReceipts(options) }
    if (mismatch === 'missing') report.videos.pop()
    else if (mismatch === 'duplicate') report.videos.at(-1).videoId = report.videos[0].videoId
    else if (mismatch === 'foreign') report.videos.at(-1).videoId = 'not-an-original-route'
    else if (mismatch === 'measured-failure') {
      const failed = eligiblePixelVideo('point', 95)
      failed.video.videoId = report.videos.at(-1).videoId
      finishVideo(failed.video, failed.census, options)
      report.videos[report.videos.length - 1] = failed.video
    } else if (mismatch === 'stage-only') {
      report.videos = finishedRouteReceipts(parseOptions(['--stage', '5']), 'point', 95)
      assert.ok(report.videos.every(video => video.stageMeasurement.status === 'passed'))
    } else report.failures.push({ code: 'missing-source-prerequisite' })
    finishReport(report, options)
    assert.notEqual(report.status, 'passed')
    assert.notEqual(report.acceptanceMeasurement.status, 'passed')
    assert.notEqual(report.sourceMeasurement.status, 'passed')
    if (mismatch === 'measured-failure') {
      assert.equal(report.status, 'failed')
      assert.equal(report.acceptanceMeasurement.status, 'failed')
    }
  }
})
