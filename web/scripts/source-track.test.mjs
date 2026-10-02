import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

// Runtime decision controls, not source-fidelity or recovered-camera evidence.
// SSR loads the real mechanics and source-track modules without a browser or GLB.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)),
  configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(async () => { await server.close() })
let CompactVideoReference, createMechanismInput, MECHANISM_DATA, INPUT_FIELDS
try {
  ;({ CompactVideoReference } = await server.ssrLoadModule(process.env.SOURCE_TRACK_MODULE ?? '/src/source-track.ts'))
  ;({ createMechanismInput, MECHANISM_DATA } = await server.ssrLoadModule('/src/mechanics.ts'))
  ;({ INPUT_FIELDS } = await server.ssrLoadModule('/src/source-witness.ts'))
} catch (error) {
  await server.close()
  throw error
}

const video = {
  id: 'synthetic-camera-playback',
  sourceSha256: 'a'.repeat(64),
  durationSeconds: 2.1,
}
const continuityEvidence = 'Synthetic same-shot framing permission for runtime testing only; not a measured source trajectory.'

function inputAt(crankTurns) {
  const input = createMechanismInput()
  return { ...input, crankTurns, amplitudes: Array.from(input.amplitudes), phases: Array.from(input.phases), setup: { ...input.setup } }
}

function cameraAt(key) {
  const angle = key * Math.PI / 2
  return {
    positionMetres: [1 + key, 2 + 2 * key, 3 - key],
    quaternion: [0, Math.sin(angle / 2), 0, Math.cos(angle / 2)],
    verticalFovDegrees: 40 + 20 * key,
    principalPointViewportPixels: [960 + 40 * key, 540 - 20 * key],
  }
}

function fixture() {
  return {
    schemaVersion: 1,
    kind: 'compact-source-track',
    source: { videoId: video.id, sha256: video.sourceSha256, width: 1920, height: 1080, durationSeconds: video.durationSeconds, fps: 30 },
    model: { sha256: MECHANISM_DATA.provenance.modelSha256, sourceCommit: MECHANISM_DATA.provenance.sourceCommit, units: 'metres', axes: 'native CAD machine frame' },
    anchors: [],
    shots: [{ id: 'shot', startSeconds: 0, endSeconds: video.durationSeconds, classification: 'machine', hasCorrespondingMachine: true, reason: 'Synthetic continuous machine shot for playback boundary tests.' }],
    frames: [0, 1, 2].map(key => ({
      timeSeconds: key,
      decodedTimeSeconds: key,
      shotId: 'shot',
      classification: 'machine',
      landmarks: [],
      views: [{
        id: 'main',
        rectSourcePixels: [0, 0, 1920, 1080],
        presentation: 'native',
        camera: cameraAt(key),
        input: inputAt(key / 10),
        provenance: { kind: 'chosen-feasible', evidence: 'Synthetic complete mechanic-builder input, not recovered source history.', unobservedInputFields: [...INPUT_FIELDS] },
        cameraProvenance: { kind: 'source-informed-framing', evidence: 'Synthetic chosen framing, not a source measurement.', family: 'synthetic-framing' },
        cameraContinuityFamily: 'synthetic-shot',
        cameraInterpolation: 'continuous-shot',
        cameraInterpolationEvidence: continuityEvidence,
      }],
    })),
    coverage: { status: 'blocked', blockers: ['Synthetic fixture has no source images or measured landmarks.'], requiredEveryIntegerSecond: true },
    stages: Object.fromEntries([50, 20, 10, 5].map(stage => [stage, { status: 'unmeasured' }])),
  }
}

function viewAt(track, key) { return track.frames[key].views[0] }
function removePermission(view) {
  delete view.cameraInterpolation
  delete view.cameraInterpolationEvidence
}
function measuredFamily(track, kind) {
  // Synthetic metadata exercises the measured-family branch; no actual fit is claimed.
  for (const frame of track.frames) frame.views[0].cameraProvenance = {
    kind, family: 'synthetic-measured-family', evidence: 'Synthetic measured-family metadata solely for runtime gate testing.',
  }
}
function closeNumber(actual, expected) {
  assert.ok(Math.abs(actual - expected) < 1e-10, `Expected ${expected}, received ${actual}`)
}
function assertCamera(camera, expected) {
  for (const field of ['positionMetres', 'quaternion', 'principalPointViewportPixels']) {
    assert.equal(camera[field].length, expected[field].length)
    camera[field].forEach((value, index) => closeNumber(value, expected[field][index]))
  }
  closeNumber(camera.verticalFovDegrees, expected.verticalFovDegrees)
}
function interior(track, time = 0.5) {
  const reference = new CompactVideoReference(track, video)
  assert.equal(reference.getState(time), 'approximate')
  const sample = reference.prepareAt(time)
  assert.equal(sample.state, 'approximate')
  assert.equal(sample.mechanicalProvenance, 'chosen')
  assert.equal(sample.views.length, 1)
  return sample.views[0]
}
function assertHeld(track, selection = 'continuous') {
  const view = interior(track)
  assertCamera(view.camera, cameraAt(0))
  assert.equal(view.sourceSampling.cameraSelection, 'decoded-exposure')
  assert.equal(view.sourceSampling.selection, selection)
}

test('both chosen endpoints opt in to continuous position, rotation, zoom and principal point without claiming matched history', () => {
  for (const time of [0.25, 0.5]) {
    const view = interior(fixture(), time)
    assertCamera(view.camera, cameraAt(time))
    assert.equal(view.sourceSampling.cameraSelection, 'continuous')
    closeNumber(view.input.crankTurns, time / 10)
  }
})

test('chosen source-informed framing remains held without permission at both endpoints', () => {
  for (const optedEndpoint of [null, 0, 1]) {
    const track = fixture()
    for (const key of [0, 1]) if (key !== optedEndpoint) removePermission(viewAt(track, key))
    assertHeld(track)
  }
})

test('held at either endpoint vetoes camera blending in chosen and measured families', () => {
  for (const kind of ['source-informed-framing', 'source-fit', 'source-transfer']) {
    for (const endpoint of [0, 1]) {
      const track = fixture()
      if (kind !== 'source-informed-framing') measuredFamily(track, kind)
      viewAt(track, endpoint).cameraInterpolation = 'held'
      delete viewAt(track, endpoint).cameraInterpolationEvidence
      assertHeld(track)
    }
  }
})

test('measured-family continuity remains usable without chosen-framing opt-in', () => {
  for (const kind of ['source-fit', 'source-transfer']) {
    const track = fixture()
    measuredFamily(track, kind)
    track.frames.forEach(frame => removePermission(frame.views[0]))
    const view = interior(track)
    assertCamera(view.camera, cameraAt(0.5))
    assert.equal(view.sourceSampling.cameraSelection, 'continuous')
  }
})

test('authored permission cannot cross a source cut, layout change, gearing change or counter-height mode change', () => {
  const discontinuities = [
    track => {
      track.shots[0].endSeconds = 1
      track.shots.push({ ...track.shots[0], id: 'cut', startSeconds: 1, endSeconds: video.durationSeconds })
      track.frames[1].shotId = 'cut'
      track.frames[2].shotId = 'cut'
    },
    track => { viewAt(track, 1).rectSourcePixels = [0, 0, 960, 1080] },
    track => { viewAt(track, 1).input.gearing = 'medium-medium' },
    track => { viewAt(track, 1).input.setup.counterHeightM = MECHANISM_DATA.counter.referenceGooseneckYMm / 1000 },
  ]
  for (const change of discontinuities) {
    const track = fixture()
    change(track)
    assertHeld(track, 'decoded-exposure')
  }
})

test('permission does not override mismatched camera continuity or provenance families', () => {
  for (const change of [
    view => { view.cameraContinuityFamily = 'different-shot-framing' },
    view => { view.cameraProvenance.family = 'different-camera-family' },
  ]) {
    const track = fixture()
    change(viewAt(track, 1))
    assertHeld(track)
  }
})

test('unknown or non-string interpolation policies reject the track rather than allowing playback', () => {
  for (const policy of ['linear', '', null, false, 1, {}]) {
    const track = fixture()
    viewAt(track, 1).cameraInterpolation = policy
    assert.throws(() => new CompactVideoReference(track, video))
  }
})

test('continuous-shot permission requires nonblank string evidence at either endpoint', () => {
  for (const endpoint of [0, 1]) {
    for (const evidence of [undefined, null, false, 1, {}, '', ' \n\t ']) {
      const track = fixture()
      viewAt(track, endpoint).cameraInterpolationEvidence = evidence
      assert.throws(() => new CompactVideoReference(track, video))
    }
  }
})
