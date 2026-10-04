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

test('source-following rejects a different raw native source or release commit rather than adopting transport identity', () => {
  const replacement = fixture()
  replacement.model.sha256 = 'f'.repeat(64)
  assert.throws(() => new CompactVideoReference(replacement, video), /different native CAD export/)
  const otherCommit = fixture()
  otherCommit.model.sourceCommit = 'b'.repeat(40)
  assert.throws(() => new CompactVideoReference(otherCommit, video), /different native CAD export/)
})

test('unavailable native features retain source pixels without accepting ghost path or point', () => {
  const track = fixture()
  const unavailable = { id: 'lost-native-feature', kind: 'physical-feature', description: 'Original photographed feature still required',
    nativeAssociation: { status: 'unavailable', reason: 'No unchanged native counterpart', proof: {} } }
  track.anchors.push(unavailable)
  track.frames[0].landmarks.push({ anchorId: unavailable.id, viewId: 'main', pixel: [120, 340], role: 'check', status: 'observed', method: 'manual', uncertaintyPx: 2 })
  const reference = new CompactVideoReference(track, video)
  assert.equal(reference.getState(0), 'approximate')
  for (const ghost of [{ partPath: 'harmonic-analyzer/removed-part' }, { partLocalMetres: [1, 2, 3] }, { worldMetres: [1, 2, 3] }]) {
    const mutated = structuredClone(track)
    Object.assign(mutated.anchors[0], ghost)
    assert.throws(() => new CompactVideoReference(mutated, video), /Unavailable source features/)
  }
})

function crossfadeFixture() {
  const track = fixture()
  for (const frame of track.frames) {
    frame.views = ['outgoing', 'incoming'].map((id, index) => ({
      ...structuredClone(frame.views[0]), id,
      composite: { mode: 'crossfade', groupId: 'source-dissolve', imageLayerId: id, opacity: index ? 0.7 : 0.3 },
      compositeProvenance: { kind: 'chosen-unmeasured', evidence: 'Synthetic source-observed layer topology; numeric image weights chosen, not measured.' },
    }))
  }
  return track
}

test('source crossfade retains ordered topology and chosen unmeasured alpha during playback', () => {
  const track = crossfadeFixture(), reference = new CompactVideoReference(track, video)
  for (const time of [0, 0.5, 1.5]) {
    const sample = reference.at(time)
    assert.equal(sample.state, 'approximate')
    assert.deepEqual(sample.views.map(view => view.id), ['outgoing', 'incoming'])
    for (const view of sample.views) {
      const declared = track.frames[Math.floor(time)].views.find(item => item.id === view.id)
      assert.deepEqual(view.composite, declared.composite)
      assert.deepEqual(view.compositeProvenance, declared.compositeProvenance)
      assert.deepEqual(view.sourceLayout.map(entry => [entry.viewId, entry.composite, entry.compositeProvenance]),
        track.frames[Math.floor(time)].views.map(item => [item.id, item.composite, item.compositeProvenance]))
    }
  }
})

test('camera provenance cannot authorize missing malformed or falsely measured source alpha', () => {
  for (const provenance of [undefined, null, {}, { kind: 'measured', evidence: 'Camera fit certificate' },
    { kind: 'chosen-unmeasured', evidence: '   ' }, { kind: 'chosen-unmeasured', evidence: 'Candidate', measured: true }]) {
    for (const cameraKind of ['source-fit', 'source-informed-framing']) {
      const track = crossfadeFixture()
      track.frames[0].views[0].compositeProvenance = provenance
      track.frames[0].views[0].cameraProvenance.kind = cameraKind
      assert.throws(() => new CompactVideoReference(track, video), /[Cc]omposite|crossfade/)
    }
  }
  const opaque = fixture()
  opaque.frames[0].views[0].compositeProvenance = { kind: 'measured', evidence: 'Not an approved alpha authority' }
  assert.throws(() => new CompactVideoReference(opaque, video), /[Cc]omposite/)
})

const overrideCheckIds = ['override-check-left', 'override-check-right']
function overrideFixture() {
  const track = fixture()
  track.anchors = overrideCheckIds.map(id => ({
    id, kind: 'physical-feature', description: 'Synthetic CHECK identity for source override playback controls, not a measured native association.',
  }))
  for (const frame of track.frames) frame.landmarks = overrideCheckIds.map((anchorId, index) => ({
    anchorId, viewId: 'main', role: 'check', status: 'observed', method: 'manual',
    pixel: [400 + index * 800, 540], uncertaintyPx: 2,
  }))
  return track
}
function authoredOverrides(frame) {
  const sourceEvidence = {
    evidence: 'Synthetic original-source-shaped disassembly evidence for runtime controls only.',
    sourceTimeSeconds: frame.decodedTimeSeconds, landmarkIds: [...overrideCheckIds],
  }
  return [
    { partPath: 'harmonic-analyzer/channel/connecting-rod-1', visibility: 'visible',
      worldPositionMetres: [0.123, 0.456, -0.078], worldQuaternion: [0, 0, 1, 0], ...sourceEvidence },
    { partPath: 'harmonic-analyzer/channel/connecting-rod-2', visibility: 'hidden', ...sourceEvidence },
  ]
}

test('authored absolute source poses and visibility survive exact and held selections then clear in both reused playback buffers', () => {
  const track = overrideFixture(), overrides = authoredOverrides(track.frames[0])
  viewAt(track, 0).partOverrides = overrides
  const reference = new CompactVideoReference(track, video)
  for (const time of [0, 0.75]) {
    const view = reference.at(time).views[0]
    assert.equal(view.partOverrides, overrides)
    assert.equal(view.partOverrides[0].worldPositionMetres, overrides[0].worldPositionMetres)
    assert.equal(view.partOverrides[0].worldQuaternion, overrides[0].worldQuaternion)
    assert.equal(view.partOverrides[0].landmarkIds, overrides[0].landmarkIds)
    assert.equal(view.partOverrides[1].visibility, 'hidden')
    assertCamera(view.camera, cameraAt(0))
    closeNumber(view.input.crankTurns, 0)
    assert.equal(view.sourceSampling.selection, 'decoded-exposure')
  }
  const empty = reference.at(1).views[0].partOverrides
  assert.deepEqual(empty, [])
  assert.equal(reference.at(2).views[0].partOverrides, empty)
  assert.equal(reference.at(0).views[0].partOverrides, overrides)
  assert.equal(reference.at(1).views[0].partOverrides, empty)
})

test('different absolute placement visibility or source evidence holds the whole input and camera until the next authored frame', () => {
  const changes = [
    overrides => { overrides[0].worldPositionMetres = [0.321, 0.456, -0.078] },
    overrides => { overrides[0].worldQuaternion = [0, 0, 0, 1] },
    overrides => { overrides[0].visibility = 'hidden' },
    overrides => { overrides[1].visibility = 'visible' },
    overrides => { overrides[0].evidence = 'Different synthetic source evidence for the same absolute pose.' },
    overrides => { overrides[0].landmarkIds = [...overrideCheckIds].reverse() },
  ]
  for (const change of changes) {
    const track = overrideFixture()
    // Same valid decoded exposure isolates the changed physical/evidence field
    // from the independent timestamp boundary exercised below.
    track.frames[0].decodedTimeSeconds = 0.5
    track.frames[1].decodedTimeSeconds = 0.5
    const from = authoredOverrides(track.frames[0]), next = authoredOverrides(track.frames[1])
    change(next)
    viewAt(track, 0).partOverrides = from
    viewAt(track, 1).partOverrides = next
    const reference = new CompactVideoReference(track, video), held = reference.at(0.5).views[0]
    assert.equal(held.partOverrides, from)
    assertCamera(held.camera, cameraAt(0))
    closeNumber(held.input.crankTurns, 0)
    assert.deepEqual(held.sourceSampling, {
      fromTimeSeconds: 0, toTimeSeconds: 0, mix: 0, selection: 'decoded-exposure', cameraSelection: 'decoded-exposure',
    })
    const selected = reference.at(1).views[0]
    assert.equal(selected.partOverrides, next)
    assertCamera(selected.camera, cameraAt(1))
    closeNumber(selected.input.crankTurns, 0.1)
  }
})

test('a new source exposure is an override boundary even when its absolute pose and CHECK identities are unchanged', () => {
  const track = overrideFixture()
  for (const index of [0, 1]) viewAt(track, index).partOverrides = authoredOverrides(track.frames[index])
  const held = interior(track)
  assert.equal(held.partOverrides, viewAt(track, 0).partOverrides)
  assertCamera(held.camera, cameraAt(0))
  closeNumber(held.input.crankTurns, 0)
  assert.equal(held.sourceSampling.selection, 'decoded-exposure')
})

test('identical complete authored override states do not disable existing input and camera continuity', () => {
  const track = overrideFixture()
  for (const index of [0, 1]) {
    track.frames[index].decodedTimeSeconds = 0.5
    viewAt(track, index).partOverrides = authoredOverrides(track.frames[index])
  }
  const view = interior(track)
  assert.equal(view.partOverrides, viewAt(track, 0).partOverrides)
  assertCamera(view.camera, cameraAt(0.5))
  closeNumber(view.input.crankTurns, 0.05)
  assert.equal(view.sourceSampling.selection, 'continuous')
  assert.equal(view.sourceSampling.cameraSelection, 'continuous')
})

test('source overrides reject malformed containers foreign paths unknown physical fields and invalid absolute states', () => {
  for (const overrides of [null, {}, 'hidden', [null], [[]]]) {
    const track = overrideFixture()
    viewAt(track, 0).partOverrides = overrides
    assert.throws(() => new CompactVideoReference(track, video))
  }
  const invalid = [
    { partPath: 'different-machine/channel/connecting-rod-1' },
    { partPath: 'harmonic-analyzer/channel/*' },
    { partPath: 'harmonic-analyzer/channel/connecting-rod-1?' },
    { worldScale: [1, 1, 1] },
    { matrixWorld: Array(16).fill(0) },
    { visibility: 'transparent' },
    { visibility: undefined },
    { worldPositionMetres: [0, 1] },
    { worldPositionMetres: new Float64Array([0, 1, 2]) },
    { worldPositionMetres: [0, NaN, 2] },
    { worldPositionMetres: Array(3) },
    { worldQuaternion: [0, 0, 1] },
    { worldQuaternion: [0, 0, 0, Infinity] },
    { worldQuaternion: [0, 0, 0, 0] },
    { worldQuaternion: [0, 0, 0, 2] },
    { worldQuaternion: Array(4) },
  ]
  for (const fields of invalid) {
    const track = overrideFixture()
    viewAt(track, 0).partOverrides = [{ ...authoredOverrides(track.frames[0])[0], ...fields }]
    assert.throws(() => new CompactVideoReference(track, video))
  }
  const duplicate = overrideFixture(), override = authoredOverrides(duplicate.frames[0])[0]
  viewAt(duplicate, 0).partOverrides = [override, { ...override }]
  assert.throws(() => new CompactVideoReference(duplicate, video))
})

test('authored source overrides need all original metadata fields bound to the current same-view observed CHECKs', () => {
  const invalid = [
    override => { delete override.evidence },
    override => { delete override.sourceTimeSeconds },
    override => { delete override.landmarkIds },
    override => { delete override.evidence; delete override.sourceTimeSeconds; delete override.landmarkIds },
    override => { override.evidence = ' \n\t ' },
    override => { override.evidence = {} },
    override => { override.sourceTimeSeconds = NaN },
    override => { override.sourceTimeSeconds = 0.01 },
    override => { override.landmarkIds = [] },
    override => { override.landmarkIds = [overrideCheckIds[0], overrideCheckIds[0]] },
    override => { override.landmarkIds = [1] },
    override => { override.landmarkIds = Array(1) },
    override => { override.landmarkIds = ['absent-original-check'] },
    (_, track) => { track.frames[0].landmarks = [] },
    (_, track) => { track.frames[0].landmarks[0].role = 'fit' },
    (_, track) => {
      track.frames[0].views.push({ ...structuredClone(viewAt(track, 0)), id: 'inset', partOverrides: undefined })
      track.frames[0].landmarks[0].viewId = 'inset'
    },
  ]
  for (const change of invalid) {
    const track = overrideFixture(), override = authoredOverrides(track.frames[0])[0]
    change(override, track)
    viewAt(track, 0).partOverrides = [override]
    assert.throws(() => new CompactVideoReference(track, video))
  }
})
