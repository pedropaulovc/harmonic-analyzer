import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

// Runtime decision controls, not source-fidelity or recovered-camera evidence.
// SSR loads the real mechanics and source-track modules without a browser or GLB.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)),
  configFile: false,
  server: { middlewareMode: true, hmr: false, ws: false, watch: null },
  appType: 'custom',
})
after(async () => { await server.close() })
let CompactVideoReference, createMechanismInput, MECHANISM_DATA, INPUT_FIELDS, SOURCE_ASSEMBLY_DATUMS
try {
  ;({ CompactVideoReference } = await server.ssrLoadModule(process.env.SOURCE_TRACK_MODULE ?? '/src/source-track.ts'))
  ;({ createMechanismInput, MECHANISM_DATA } = await server.ssrLoadModule('/src/mechanics.ts'))
  ;({ INPUT_FIELDS } = await server.ssrLoadModule('/src/source-witness.ts'))
  ;({ SOURCE_ASSEMBLY_DATUMS } = await server.ssrLoadModule('/src/source-assembly.ts'))
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

const operationVideo = { ...video, id: 'jfH-NbsmvD4' }
function assemblyFixture() {
  const track = fixture()
  track.source.videoId = operationVideo.id
  return track
}
function assemblyState(controls) {
  return {
    kind: 'source-assembly',
    provenance: {
      kind: 'chosen-feasible', videoId: operationVideo.id, frameIndex: 5200,
      evidence: 'Synthetic chosen DOFs for runtime boundary control only; not measured source fidelity.',
      unobservedDegreesOfFreedom: ['world depth', 'free rigid pose'],
    },
    ...controls,
  }
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

test('assembly travel holds until the next exposure independently of complete input and camera blending', () => {
  const track = assemblyFixture()
  const first = assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: 0 } })
  const next = assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: 4 } })
  viewAt(track, 0).sourceAssembly = first
  viewAt(track, 1).sourceAssembly = next
  const reference = new CompactVideoReference(track, operationVideo)
  for (const time of [0.25, 0.5, 1 - 1e-9]) {
    const view = reference.at(time).views[0]
    assert.equal(view.sourceAssembly.retainingNut.releaseTurns, 0)
    assertCamera(view.camera, cameraAt(time))
    closeNumber(view.input.crankTurns, time / 10)
  }
  assert.equal(reference.at(1).views[0].sourceAssembly.retainingNut.releaseTurns, 4)
  first.retainingNut.releaseTurns = 9
  assert.equal(reference.at(0).views[0].sourceAssembly.retainingNut.releaseTurns, 0)
})

test('free rigid poses and attachment-domain changes step without synthesizing assembly transitions', () => {
  const track = assemblyFixture()
  const first = assemblyState({ retainingNut: { attachment: 'held', pose: { positionMetres: [0.1, 0.2, 0.3], quaternion: [0, 0, 0, 1] } } })
  const next = assemblyState({ retainingNut: { attachment: 'held', pose: { positionMetres: [0.4, 0.5, 0.6], quaternion: [0, 1, 0, 0] } } })
  const radius = SOURCE_ASSEMBLY_DATUMS.chainChordMetres / (2 * Math.sin(Math.PI / 68))
  const hanger = assemblyState({
    hanger: { attachment: 'open', swingRad: 0.4, hookReleaseRad: 0.1 },
    chain: {
      attachment: 'held-off-sprockets',
      jointsMetres: Array.from({ length: 68 }, (_, j) => [
        10 + radius * (Math.cos(2 * Math.PI * j / 68) - 1),
        10 + radius * Math.sin(2 * Math.PI * j / 68),
        10,
      ]),
      planeNormal: [0, 0, 1],
      contacts: [{ kind: 'held', joint: 0, positionMetres: [10, 10, 10] }],
    },
  })
  viewAt(track, 0).sourceAssembly = first
  viewAt(track, 1).sourceAssembly = next
  viewAt(track, 2).sourceAssembly = hanger
  const reference = new CompactVideoReference(track, operationVideo)
  assert.deepEqual(reference.at(0.5).views[0].sourceAssembly, first)
  assert.deepEqual(reference.at(1).views[0].sourceAssembly, next)
  assert.deepEqual(reference.at(1.5).views[0].sourceAssembly, next)
  assert.deepEqual(reference.at(2).views[0].sourceAssembly, hanger)
})

test('a source cut cannot bridge assembly removal or existing input and camera states', () => {
  const track = assemblyFixture()
  const first = assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: 2 } })
  const next = assemblyState({ retainingNut: { attachment: 'held', pose: { positionMetres: [0.1, 0.2, 0.3], quaternion: [0, 0, 0, 1] } } })
  viewAt(track, 0).sourceAssembly = first
  viewAt(track, 1).sourceAssembly = next
  track.shots[0].endSeconds = 1
  track.shots.push({ ...track.shots[0], id: 'cut', startSeconds: 1, endSeconds: operationVideo.durationSeconds })
  track.frames[1].shotId = 'cut'
  track.frames[2].shotId = 'cut'
  const reference = new CompactVideoReference(track, operationVideo)
  const held = reference.at(0.5).views[0]
  assert.deepEqual(held.sourceAssembly, first)
  assertCamera(held.camera, cameraAt(0))
  closeNumber(held.input.crankTurns, 0)
  assert.deepEqual(reference.at(1).views[0].sourceAssembly, next)
})

test('omitted and explicit operating states reset removed parts after playback and backward seeks', () => {
  for (const explicit of [false, true]) {
    const track = assemblyFixture()
    const removed = assemblyState({ retainingNut: { attachment: 'held', pose: { positionMetres: [0.1, 0.2, 0.3], quaternion: [0, 0, 0, 1] } } })
    viewAt(track, 0).sourceAssembly = removed
    viewAt(track, 1).sourceAssembly = removed
    if (explicit) viewAt(track, 2).sourceAssembly = { kind: 'operating' }
    const reference = new CompactVideoReference(track, operationVideo)
    for (const time of [0, 1, 2, 0, 2]) {
      assert.deepEqual(reference.at(time).views[0].sourceAssembly, time === 2 ? { kind: 'operating' } : removed)
    }
  }
})

test('invalid physical assembly states reject compilation even on an unavailable input or camera', () => {
  const invalid = [
    null, false, [], {}, { kind: 'assembly' },
    { kind: 'operating', retainingNut: { attachment: 'threaded', releaseTurns: 0 } },
    { kind: 'operating', partOverrides: [] },
    assemblyState({ retainingNut: { attachment: 'missing' } }),
    assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: Infinity } }),
    assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: -1 } }),
    assemblyState({ retainingNut: { attachment: 'held', pose: { positionMetres: [0, 0, 0], quaternion: [0, 0, 0, 2] } } }),
    assemblyState({ hanger: { attachment: 'latched', swingRad: 0.1, hookReleaseRad: 0 } }),
    assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: 0 }, interpolation: 'continuous-shot' }),
  ]
  for (const state of invalid) {
    for (const unavailable of [false, true]) {
      const track = assemblyFixture()
      viewAt(track, 1).sourceAssembly = state
      if (unavailable) {
        viewAt(track, 1).input = null
        viewAt(track, 1).camera = null
      }
      assert.throws(() => new CompactVideoReference(track, operationVideo), /jfH-NbsmvD4@1s\/main/)
    }
  }
})

test('assembly source witnesses cannot be borrowed into another footage identity', () => {
  const track = fixture()
  viewAt(track, 0).sourceAssembly = assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: 0 } })
  assert.throws(() => new CompactVideoReference(track, video), /witness must belong to this footage/)
})

test('detached diagnostic publication preserves held live banks and a pending transaction after async success or failure', async () => {
  for (const failure of [false, true]) {
    const reference = new CompactVideoReference(fixture(), video)
    const published = reference.at(0)
    const publishedBefore = structuredClone(published)
    const pending = reference.prepareAt(0.25)
    const pendingBefore = structuredClone(pending)
    const diagnostic = structuredClone(pending)
    diagnostic.timeSeconds = 0
    diagnostic.views[0].input.crankTurns = 0.09
    let capability
    const lease = reference.withDiagnosticSamples([diagnostic], async state => {
      capability = state
      assert.equal(state.sourceProof, false)
      assert.equal(state.sourceAcceptance, false)
      const prepared = state.reference.prepareAt(0.5)
      closeNumber(prepared.views[0].input.crankTurns, 0.09)
      assert.equal(state.snapshot().publishedSample.state, 'unavailable')
      state.reference.commitPrepared()
      const receipt = state.snapshot()
      assert.equal(receipt.prepareCount, 1)
      assert.equal(receipt.commitCount, 1)
      closeNumber(receipt.publishedSample.views[0].input.crankTurns, 0.09)
      receipt.publishedSample.views[0].input.crankTurns = 3
      closeNumber(state.snapshot().publishedSample.views[0].input.crankTurns, 0.09)
      await Promise.resolve()
      if (failure) {
        assert.throws(() => state.reference.prepareAt(NaN), /finite/)
        assert.throws(() => state.reference.commitPrepared(), /No successfully prepared/)
        throw new Error('Diagnostic transaction control failure.')
      }
      return 'diagnostic-only'
    })
    if (failure) await assert.rejects(lease, /Diagnostic transaction control failure/)
    else assert.equal(await lease, 'diagnostic-only')
    assert.deepEqual(published, publishedBefore)
    assert.deepEqual(pending, pendingBefore)
    assert.equal(reference.commitPrepared(), pending)
    assert.throws(() => capability.snapshot(), /no longer active/)
    assert.throws(() => capability.reference.prepareAt(0), /no longer active/)
    assert.throws(() => capability.reference.commitPrepared(), /no longer active/)
    closeNumber(reference.at(0.5).views[0].input.crankTurns, 0.05)
  }
})

test('live consumers and overlapping detached publications never consume or invalidate each other’s banks', async () => {
  const reference = new CompactVideoReference(fixture(), video)
  const diagnostic = structuredClone(reference.at(0))
  diagnostic.views[0].input.crankTurns = 0.09
  await reference.withDiagnosticSamples([diagnostic], async first => {
    const held = first.reference.prepareAt(0.5)
    closeNumber(held.views[0].input.crankTurns, 0.09)
    const live = reference.prepareAt(0.25)
    await reference.withDiagnosticSamples([diagnostic], async second => {
      second.reference.prepareAt(0.75)
      closeNumber(second.reference.commitPrepared().views[0].input.crankTurns, 0.09)
      assert.equal(reference.commitPrepared(), live)
      closeNumber(live.views[0].input.crankTurns, 0.025)
      assert.equal(first.reference.commitPrepared(), held)
      assert.throws(() => second.reference.prepareAt(NaN), /finite/)
      assert.throws(() => second.reference.commitPrepared(), /No successfully prepared/)
      closeNumber(reference.at(0.5).views[0].input.crankTurns, 0.05)
      closeNumber(first.snapshot().publishedSample.views[0].input.crankTurns, 0.09)
    })
    closeNumber(first.snapshot().publishedSample.views[0].input.crankTurns, 0.09)
  })
})

function excludeBackground(frame, view = frame.views[0]) {
  frame.sourceImage = {
    frameIndex: Math.round(frame.decodedTimeSeconds * 30), width: 1920, height: 1080,
    sourceSha256: video.sourceSha256, pixelFormat: 'gray8', sha256Gray8: 'b'.repeat(64),
  }
  view.sourceVisibility = {
    kind: 'policy-excluded', reasonCode: 'blurred-navigation-background',
    sourceImage: structuredClone(frame.sourceImage), rectSourcePixels: [...view.rectSourcePixels],
    manualSourceAudit: { method: 'manual-source-pixel-inspection', evidence: 'Synthetic whole physical ROI audit solely for hold-contract decisions.' },
  }
}

test('wholly qualified source backgrounds request hold without publishing their native candidate pose', () => {
  const track = assemblyFixture()
  viewAt(track, 0).cameraInterpolation = 'held'
  viewAt(track, 0).sourceAssembly = assemblyState({ retainingNut: { attachment: 'threaded', releaseTurns: 1 } })
  for (const frame of track.frames.slice(1)) excludeBackground(frame)
  const reference = new CompactVideoReference(track, operationVideo)
  assert.equal(reference.getState(1.2), 'hold-last-readable')
  const held = reference.at(1.2)
  assert.equal(held.timeSeconds, 1.2)
  assert.deepEqual(held.views, [])
  assert.equal(held.mechanicalProvenance, null)
  assert.match(held.reason, /preceding displayed pose, not a current source match/)
  const fallback = reference.prepareLastReadableAt(1.2)
  assert.equal(fallback.state, 'approximate')
  assert.equal(fallback.timeSeconds, 0)
  assertCamera(fallback.views[0].camera, cameraAt(0))
  assert.equal(fallback.views[0].input.crankTurns, 0)
  assert.deepEqual(fallback.views[0].sourceAssembly, viewAt(track, 0).sourceAssembly)
  assert.deepEqual(fallback.views[0].sourceLayout.map(view => view.viewId), ['main'])
  reference.commitPrepared()
  assert.equal(reference.at(1.9).state, 'hold-last-readable')
  assert.equal(track.frames[1].views.length, 1, 'Excluded source inventory is never removed')
})

test('mixed readable inset remains live while excluded native background candidate is not drawn or measured', () => {
  const track = fixture()
  for (const frame of track.frames) {
    const foreground = structuredClone(frame.views[0])
    foreground.id = 'readable-inset'
    foreground.rectSourcePixels = [100, 100, 400, 300]
    excludeBackground(frame)
    frame.views.push(foreground)
  }
  const sample = new CompactVideoReference(track, video).at(0.5)
  assert.equal(sample.state, 'approximate')
  assert.deepEqual(sample.views.map(view => view.id), ['readable-inset'])
  assert.deepEqual(sample.views[0].sourceLayout.map(view => view.viewId), ['readable-inset'])
})

test('missing decoder PTS and missing readable source input remain unavailable, not qualified holds', () => {
  for (const mutation of ['decoder', 'readable-input']) {
    const track = fixture()
    excludeBackground(track.frames[1])
    if (mutation === 'decoder') {
      track.frames[1].decodedTimeSeconds = null
      track.frames[1].sourceSampleUnavailable = true
      track.frames[1].views = []
      delete track.frames[1].sourceImage
    } else {
      const foreground = structuredClone(track.frames[0].views[0])
      foreground.id = 'readable-inset'
      foreground.input = null
      track.frames[1].views.push(foreground)
    }
    assert.equal(new CompactVideoReference(track, video).at(1.1).state, 'unavailable')
  }
})

test('qualified backgrounds have no cold-start source fallback before the first readable exposure', () => {
  const track = fixture()
  track.frames.forEach(frame => excludeBackground(frame))
  const reference = new CompactVideoReference(track, video)
  assert.equal(reference.prepareLastReadableAt(1), null)
  assert.equal(reference.at(1).state, 'hold-last-readable')
})

test('runtime qualification refuses foreign image, partial ROI, blank audit, unknown reason and measured readable views', () => {
  for (const mutate of [
    view => { view.sourceVisibility.sourceImage.frameIndex++ },
    view => { view.sourceVisibility.rectSourcePixels[2]-- },
    view => { view.sourceVisibility.manualSourceAudit.evidence = '' },
    view => { view.sourceVisibility.reasonCode = 'unknown-motion' },
    (view, frame) => { frame.landmarks.push({ viewId: view.id }) },
    view => { view.nativeLineChecks = [{}] },
  ]) {
    const track = fixture()
    excludeBackground(track.frames[1])
    mutate(track.frames[1].views[0], track.frames[1])
    assert.throws(() => new CompactVideoReference(track, video), /Source visibility|source-readable/)
  }
  const clock = fixture()
  excludeBackground(clock.frames[1])
  clock.frames[1].decodedTimeSeconds = 1.501
  assert.throws(() => new CompactVideoReference(clock, video), /0.5s timing tolerance/)
})

test('finite native-line probes contain only bounded exact local-segment diagnostics, never extra observed source points', () => {
  const track = fixture()
  const local = [[0.06985, -0.06477, 0], [0.06985, 0.06477, 0]]
  for (const frame of track.frames) frame.views[0].nativeLineChecks = [{
    id: 'fixed-stock', partPath: 'ha-harmonic-analyzer/fr-frame/fr-rocker-arm-support-1',
    partLocalLineMetres: structuredClone(local),
  }]
  const reference = new CompactVideoReference(track, video)
  assert.equal(reference.landmarkProbeAnchors.length, 5, 'One shared finite segment never expands to an all-vertex certificate')
  assert.deepEqual(reference.landmarkProbeAnchors.map(anchor => anchor.partLocalMetres), [0, 0.25, 0.5, 0.75, 1].map(fraction => [
    local[0][0], local[0][1] + fraction * (local[1][1] - local[0][1]), 0,
  ]))
  assert.equal(track.anchors.length, 0)
  assert.ok(track.frames.every(frame => frame.landmarks.length === 0))
  assert.equal(reference.at(0.5).state, 'approximate', 'Native line probes do not claim source fidelity')
})
