import test from 'node:test'
import assert from 'node:assert/strict'
import { nativeWitnessAtOriginalPoint, nativeSourceVisibilityExpectation } from './native-source-feature-bindings.mjs'
import { verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'

function primitive() {
  return { path: 'harmonic-analyzer/test/surface', rawPrimitiveSHA256: 'a'.repeat(64),
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 0]), index: new Uint32Array([0, 1, 2, 1, 3, 2]) }
}
const sourceSHA = 'b'.repeat(64)

test('an original point in the surface gets its exact closed triangle, not a nearby vertex', () => {
  const raw = primitive(), witness = nativeWitnessAtOriginalPoint(raw, [0.25, 0.25, 0], 'original-point', sourceSHA)
  assert.equal(witness.kind, 'triangle-point')
  assert.deepEqual(witness.barycentric, [0.5, 0.25, 0.25])
  const feature = verifyNativeMeshFeatureWitness(witness, raw)
  assert.deepEqual(feature.localPointMetres, [0.25, 0.25, 0])
  assert.deepEqual(feature.supportTriangleIndices, [0])
})

test('a virtual centre off the original surface is unavailable even inside the physical tolerance', () => {
  assert.throws(() => nativeWitnessAtOriginalPoint(primitive(), [0.25, 0.25, 1e-9], 'virtual-centre', sourceSHA), /no genuine.*surface support/)
  assert.throws(() => nativeWitnessAtOriginalPoint(primitive(), [0.75, -0.25, 0], 'outside', sourceSHA), /no genuine.*surface support/)
})

test('stored vertex support retains all of its authentic adjacent triangles', () => {
  const raw = primitive(), witness = nativeWitnessAtOriginalPoint(raw, [1, 0, 0], 'vertex', sourceSHA)
  assert.equal(witness.kind, 'mesh-vertex')
  assert.deepEqual(witness.adjacentTriangleIndices, [0, 1])
  const amputated = { ...witness, adjacentTriangleIndices: [0] }
  assert.throws(() => verifyNativeMeshFeatureWitness(amputated, raw), /complete adjacent triangle membership/)
})

test('original source body certificates cannot rebind to a new physical input on the same exposure', () => {
  const sourceImage = { frameIndex: 1, pixelFormat: 'bgr8', width: 1920, height: 1080, sourceSha256: sourceSHA, sha256Bgr8: 'c'.repeat(64) }
  const input = { crankTurns: 0, gearing: 'medium-medium', magnification: 1, amplitudes: Array(20).fill(0), phases: Array(20).fill(0),
    setup: { counterHeightM: 0.2, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0, coneSwingRad: 0,
      pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 } }
  const camera = { positionMetres: [0, 0, 2], quaternion: [0, 0, 0, 1], verticalFovDegrees: 40 }
  const layout = [{ viewId: 'main', rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', composite: { mode: 'opaque' },
    compositeProvenance: null, resolvedImagePlaneWarp: null }]
  const originalTuple = { sourceVideoId: 'original', sourceSha256: sourceSHA, sourceImage, modelSha256: 'a'.repeat(64),
    modelSourceCommit: 'original-model', shotId: 'source-shot', viewId: 'main', timeSeconds: 1, decodedTimeSeconds: 1, input, camera,
    rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', imagePlaneWarp: null, resolvedImagePlaneWarp: null,
    sourceLayout: layout, composite: { mode: 'opaque' }, partOverrides: [], constraints: [], continuity: null,
    nativeGeometryAssumptions: [], sourceNonIdentifiableFixedParts: [] }
  const proof = { binding: { ...originalTuple, intervalSeconds: [1, 1] }, sourceVisibleParts: [{ partPath: primitive().path,
    sourceFeatures: ['original physical surface'], sourceCoverage: { kind: 'landmarks', landmarkIds: ['marker'] }, evidence: 'Original source observation' }],
    excludedParts: [], sourceNonIdentifiableFixedParts: [], unresolvedParts: [], evidence: 'Original source body certificate' }
  const view = { id: 'main', camera, input, rectSourcePixels: originalTuple.rectSourcePixels, presentation: 'native',
    mechanicalState: { status: 'observed', input, visiblePoseCompleteness: 'complete', evidence: 'Original physical controls', visibilityProof: proof } }
  const frame = { timeSeconds: 1, decodedTimeSeconds: 1, shotId: 'source-shot', sourceImage, views: [view],
    landmarks: [{ anchorId: 'marker', status: 'observed', role: 'check', pixel: [10, 20] }] }
  const record = { observations: { frames: [frame], anchors: [{ id: 'marker', partPath: primitive().path }], nativeGeometryAssumptions: [] } }
  const binding = { ...originalTuple, camera: { ...camera, principalPointViewportPixels: [960, 540] }, modelRawSHA256: originalTuple.modelSha256 }
  assert.deepEqual(nativeSourceVisibilityExpectation({ record, frame, view, binding }).sourceVisibilityErrors, [])
  const changed = { ...binding, input: { ...input, crankTurns: 0.25 } }
  assert.ok(nativeSourceVisibilityExpectation({ record, frame, view, binding: changed }).sourceVisibilityErrors.includes('Visibility proof binding mismatch: input'))
})
