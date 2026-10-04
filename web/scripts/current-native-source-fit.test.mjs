import test from 'node:test'
import assert from 'node:assert/strict'
import { currentNativeFitSourceTuple, prepareCurrentNativeFitSource, currentNativeFitWorldPoint,
  independentCurrentNativeFitRows, assertPrivateCurrentNativeFitOutput, createExactAssociatedCurrentNativeFitDefinitions } from './current-native-source-fit.mjs'
import { CURRENT_NATIVE_RAW_SHA256, jsonDigest, sha256 } from './native-model-byte-proof.mjs'

// Deliberately three vertices, not a fabricated CURRENT462 inventory. These
// arithmetic fixtures prove refusal/coordinate behavior only; the root's actual
// pinned original-CPU -> raw -> world CLI smoke provides native-world evidence.
const hash = 'a'.repeat(64), imageHash = 'b'.repeat(64)
function sourceFixture() {
  const sourceImage = { frameIndex: 809, sourceSha256: hash, sha256Bgr8: imageHash, pixelFormat: 'bgr8', width: 1920, height: 1080 }
  const landmark = { anchorId: 'genuine-source-feature', role: 'fit', pixel: [783, 110], status: 'observed', uncertaintyPx: 4, method: 'manual' }
  const frame = { sourceImage, timeSeconds: 27, decodedTimeSeconds: 26.993633, shotId: 'actual-shot', landmarks: [landmark], mechanicalState: { input: null } }
  const input = { crankTurns: 0.25, amplitudes: Array(20).fill(0), phases: Array(20).fill(0), gearing: 'medium-medium', magnification: 1,
    setup: { counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0, coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 } }
  const authoredFrame = structuredClone(frame)
  authoredFrame.input = input
  authoredFrame.provenance = { kind: 'chosen-feasible', unobservedInputFields: ['crankTurns'] }
  const decodedFrame = { frameIndex: 809, sourceSha256: hash, sha256Bgr8: imageHash, decodedTimestampTicks: 809809, timeBase: '1/30000', decodedTimeSeconds: 809809 / 30000 }
  return { originalObservations: { source: { videoId: 'source-only-test', sha256: hash, width: 1920, height: 1080 }, frames: [frame] },
    authoredFrame, viewId: 'main', decodedFrame,
    inputSelection: { field: 'input', state: 'chosen-unmeasured', evidence: 'Explicit independently selected candidate; not source recovered', ambiguities: ['unobserved crank home'] } }
}

function triangleFixture() {
  const primitive = { path: 'test/exact-triangle', rawPrimitiveSHA256: hash, nodeIndex: 4, meshIndex: 7, primitiveIndex: 0, instanceOf: null,
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]), index: new Uint32Array([0, 1, 2]) }
  const original = { path: primitive.path, association: { nodeIndex: 4, meshIndex: 17, primitiveIndex: 0 }, instanceOf: null, spring: null,
    attributes: { position: { array: Float32Array.from(primitive.positions), itemSize: 3, count: 3 } }, canonicalIndices: Uint32Array.from(primitive.index) }
  // Proper 90-degree Z rotation and a translation; binary64 translation has a
  // component lost by f32, so downcasting the independently solved pose fails.
  const pose = { path: primitive.path, effectiveVisibility: true, matrixWorld: new Float64Array([0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 1 + 2 ** -40, 2, 3, 1]) }
  const witness = { anchorId: 'surface-point', partPath: primitive.path, rawPrimitiveSHA256: hash, sourceFeatureEvidenceSHA256: imageHash,
    kind: 'triangle-point', triangleIndex: 0, barycentric: [0.5, 0.25, 0.25] }
  return { primitive, original, pose, witness }
}

test('independent exact PTS is retained separately from original rounded decoded time', () => {
  const f = sourceFixture(), s = prepareCurrentNativeFitSource(f)
  assert.equal(s.sourceBinding.decodedTimestampTicks, 809809)
  assert.equal(s.sourceBinding.decodedTimeSeconds, 809809 / 30000)
  assert.equal(s.sourceBinding.recordedOriginalDecodedTimeSeconds, 26.993633)
  assert.deepEqual(s.partOverrides, [])
  assert.equal(f.originalObservations.frames[0].decodedTimeSeconds, 26.993633)
})

test('canonical gray8 source identity remains gray8; converted or dual image identities refuse', () => {
  const f = sourceFixture()
  for (const image of [f.originalObservations.frames[0].sourceImage, f.authoredFrame.sourceImage]) {
    image.pixelFormat = 'gray8'; image.sha256Gray8 = image.sha256Bgr8; delete image.sha256Bgr8
  }
  f.decodedFrame.sha256Gray8 = f.decodedFrame.sha256Bgr8; delete f.decodedFrame.sha256Bgr8
  const prepared = prepareCurrentNativeFitSource(f)
  assert.equal(prepared.sourceBinding.sourceImage.pixelFormat, 'gray8')
  assert.equal(prepared.sourceBinding.sourceImage.sha256Gray8, imageHash)
  assert.equal(prepared.sourceBinding.sourceImage.sha256Bgr8, undefined)
  const converted = structuredClone(f)
  converted.decodedFrame.sha256Bgr8 = converted.decodedFrame.sha256Gray8; delete converted.decodedFrame.sha256Gray8
  assert.throws(() => prepareCurrentNativeFitSource(converted), Error)
  const dual = structuredClone(f)
  dual.originalObservations.frames[0].sourceImage.sha256Bgr8 = imageHash
  assert.throws(() => prepareCurrentNativeFitSource(dual), Error)
})

test('unprobed PTS, wrong original image and source clock beyond unchanged half second refuse', () => {
  for (const mutate of [f => { f.decodedFrame.decodedTimestampTicks++ }, f => { f.decodedFrame.sha256Bgr8 = 'c'.repeat(64) },
    f => { f.originalObservations.frames[0].timeSeconds = 26; f.authoredFrame.timeSeconds = 26 }]) {
    const f = sourceFixture(); mutate(f)
    assert.throws(() => currentNativeFitSourceTuple(f.originalObservations, f.originalObservations.frames[0], 'main', f.decodedFrame), /PTS|frame\/PTS|clock/)
  }
})

test('authored roles, actual pixels and source uncertainty cannot be changed or omitted', () => {
  for (const mutate of [l => { l.role = 'check' }, l => { l.pixel[0] += 1 }, l => { l.uncertaintyPx = 40 }]) {
    const f = sourceFixture(); mutate(f.authoredFrame.landmarks[0])
    assert.throws(() => prepareCurrentNativeFitSource(f), /role\/pixel\/uncertainty/)
  }
})

test('chosen authored input cannot be called independently measured, and partial inputs never default', () => {
  const f = sourceFixture(); f.inputSelection.state = 'independently-measured'
  assert.throws(() => prepareCurrentNativeFitSource(f), /cannot be promoted/)
  const partial = sourceFixture(); delete partial.authoredFrame.input.setup.counterHeightM
  assert.throws(() => prepareCurrentNativeFitSource(partial), /complete explicit 51-field/)
  const chosen = sourceFixture(); chosen.authoredFrame.chosenInput = chosen.authoredFrame.input
  chosen.inputSelection.field = 'chosenInput'; chosen.inputSelection.state = 'independently-measured'
  assert.throws(() => prepareCurrentNativeFitSource(chosen), /cannot be promoted/)
})

test('exact raw triangle barycentric point uses original binary64 rigid world pose', () => {
  const f = triangleFixture(), p = currentNativeFitWorldPoint(f)
  assert.deepEqual(p.localMetres, [0.25, 0.25, 0])
  assert.deepEqual(p.worldMetres, [0.75 + 2 ** -40, 2.25, 3])
  assert.notEqual(p.worldMetres[0], Math.fround(p.worldMetres[0]))
  assert.deepEqual(p.supportTriangleIndices, [0])
})

test('missing/hidden pose, raw ordinal mismatch and unsupported pseudo-feature remain refused', () => {
  const hidden = triangleFixture(); hidden.pose.effectiveVisibility = false
  assert.throws(() => currentNativeFitWorldPoint(hidden), /missing or hidden/)
  const missing = triangleFixture(); delete missing.pose
  assert.throws(() => currentNativeFitWorldPoint(missing), /missing or hidden/)
  const foreign = triangleFixture(); foreign.original.association.nodeIndex++
  assert.throws(() => currentNativeFitWorldPoint(foreign), /ancestry differs/)
  const pseudo = triangleFixture(); pseudo.witness.kind = 'nearest-vertex'
  assert.throws(() => currentNativeFitWorldPoint(pseudo), /unsupported.*kind/)
  const spring = triangleFixture(); spring.original.spring = { stock: 'channel', restLengthM: 0.2 }
  assert.throws(() => currentNativeFitWorldPoint(spring), /pinned original spring oracle/)
})

test('deduplicated delivery mesh ordinals differ legitimately, but changed decoded topology refuses', () => {
  const f = triangleFixture()
  assert.notEqual(f.original.association.meshIndex, f.primitive.meshIndex)
  assert.deepEqual(currentNativeFitWorldPoint(f).worldMetres, [0.75 + 2 ** -40, 2.25, 3])
  const position = triangleFixture(); position.original.attributes.position.array[3] = 0.5
  assert.throws(() => currentNativeFitWorldPoint(position), /delivery POSITION differs/)
  const index = triangleFixture(); index.original.canonicalIndices[0] = 2
  assert.throws(() => currentNativeFitWorldPoint(index), /delivery indices differ/)
})

test('32 coincident apex indices are one physical FIT, and cannot provide held-out CHECKs', () => {
  const rows = Array.from({ length: 32 }, (_, i) => ({ status: 'world-exported', worldMetres: [0.125, 0.25, 0.5],
    originalLandmark: { anchorId: `apex-seam-${i}`, role: i < 30 ? 'fit' : 'check', pixel: [100, 200], uncertaintyPx: 4 } }))
  const originals = structuredClone(rows.map(r => r.originalLandmark))
  independentCurrentNativeFitRows(rows)
  assert.equal(rows.filter(r => r.status === 'world-exported').length, 1)
  assert.equal(rows.filter(r => r.status === 'world-exported' && r.originalLandmark.role === 'check').length, 0)
  assert.deepEqual(rows.map(r => r.originalLandmark), originals)
  assert.equal(rows[31].duplicateOf, 'apex-seam-0')
  assert.match(rows[31].reason, /one support/)
})

test('private command never targets canonical tracks or parent-directory escape', () => {
  assert.throws(() => assertPrivateCurrentNativeFitOutput('web/content/v39/NAsM30MAHLg.source-track.json'), /never canonical/)
  assert.throws(() => assertPrivateCurrentNativeFitOutput('web/.vite/verification-output/../../content/false-track.json'), /never canonical/)
})

test('an unchanged typed association still needs an actual closed raw feature, not its historical world point', () => {
  const f = triangleFixture(), s = sourceFixture(), source = prepareCurrentNativeFitSource(s)
  const originalAnchor = { id: source.landmarks[0].anchorId, partPath: f.primitive.path, partLocalMetres: [0.25, 0.25, 0], correspondenceEvidence: 'Actual independently measured source feature' }
  s.originalObservations.anchors = [originalAnchor]
  f.primitive.rawPath = f.primitive.path
  const positions = { array: f.primitive.positions, itemSize: 3, count: 3, componentType: 5126, normalized: false, bytes: new Uint8Array(f.primitive.positions.buffer) }
  const indices = { array: f.primitive.index, itemSize: 1, count: 3, componentType: 5125, normalized: false, bytes: new Uint8Array(f.primitive.index.buffer) }
  f.primitive.attributes = { POSITION: positions }
  f.primitive.material = null
  f.original.restMatrixF64 = f.pose.matrixWorld
  const descriptor = { mode: 4, attributes: { POSITION: { componentType: 5126, type: 'VEC3', count: 3, normalized: false, typedBytesSha256: sha256(positions.bytes) } },
    indices: { componentType: 5125, type: 'SCALAR', count: 3, normalized: false, typedBytesSha256: sha256(indices.bytes) }, material: null }
  const anchor = { ...structuredClone(originalAnchor), nativeAssociation: { status: 'mapped', proof: {
    method: 'exact-original-native-local-feature-v1', currentSource: { sha256: CURRENT_NATIVE_RAW_SHA256 }, qualifiedPartPath: f.primitive.path,
    historicalAnchorSha256: jsonDigest(originalAnchor), currentNodeIndex: f.primitive.nodeIndex, currentWorldMatrix: Array.from(f.pose.matrixWorld),
    // This intentionally nonsensical historical world point must not enter the
    // genuine raw local construction; actual CPU posing occurs in another API.
    historicalWorldMetres: [999, 999, 999], primitives: [descriptor],
  } } }
  const meshes = []; meshes[f.primitive.meshIndex] = { primitives: [{ indices: 0 }] }
  const args = { nativeModel: { primitives: new Map([[f.primitive.path, f.primitive]]), document: { meshes }, accessor: () => indices },
    poseOracle: { inventory: { drawables: [f.original] } }, originalObservations: s.originalObservations, currentAnchors: [anchor],
    source, selections: [{ anchorId: originalAnchor.id }] }
  const actual = createExactAssociatedCurrentNativeFitDefinitions(args)[0]
  assert.equal(actual.witness.kind, 'triangle-point')
  assert.deepEqual(actual.witness.barycentric, [0.5, 0.25, 0.25])
  anchor.partLocalMetres = [0.25, 0.25, 1e-9]
  assert.match(createExactAssociatedCurrentNativeFitDefinitions(args)[0].unavailableReason, /local point changed/)
  originalAnchor.partLocalMetres = [...anchor.partLocalMetres]
  anchor.nativeAssociation.proof.historicalAnchorSha256 = jsonDigest(originalAnchor)
  assert.match(createExactAssociatedCurrentNativeFitDefinitions(args)[0].unavailableReason, /no closed raw surface witness/)
  anchor.partLocalMetres = [0.25, 0.25, 0]
  originalAnchor.partLocalMetres = [...anchor.partLocalMetres]
  anchor.nativeAssociation.proof.historicalAnchorSha256 = jsonDigest(originalAnchor)
  descriptor.attributes.POSITION.typedBytesSha256 = 'e'.repeat(64)
  assert.match(createExactAssociatedCurrentNativeFitDefinitions(args)[0].unavailableReason, /no closed raw surface witness/)
})
