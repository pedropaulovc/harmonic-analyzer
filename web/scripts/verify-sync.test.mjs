import test from 'node:test'
import assert from 'node:assert/strict'
import { parseOptions, sourceCensus, finishVideo, seekSettlement, sourcePtsInShot } from './verify-sync.mjs'

// These are decision-gate unit controls, NOT browser/source-fidelity evidence.
const native = { durationSeconds: 2.1, fps: 30, pts: [0, 1, 2] }
const frame = (time, classification = 'machine') => ({ timeSeconds: time, decodedTimeSeconds: time, shotId: 'shot', classification, views: [{ id: 'main' }] })
const observations = { shots: [{ id: 'shot', startSeconds: 0, endSeconds: 2.1, classification: 'machine', hasCorrespondingMachine: true }], frames: [frame(0), frame(1), frame(2)], coverage: { changeTimesSeconds: [0.1, 0.2] } }

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
  assert.deepEqual(census.rows.filter(row => row.reasons.includes('mid-interval')).map(row => row.timeSeconds), [0.5, 1.5])
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
