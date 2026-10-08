import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { createHash, webcrypto } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

// Synthetic seam topology exercises the real consumer, not source/GPU qualification.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)), configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null, ws: false }, appType: 'custom',
})
after(async () => { await server.close() })
let exactStoredF32Class, incidentOriginalTriangles, deriveNativeStagePixelRay, joinNativeLandmarkEligibility, NATIVE_LANDMARK_ELIGIBILITY_SCOPE
try {
  ;({ exactStoredF32Class, incidentOriginalTriangles, deriveNativeStagePixelRay, joinNativeLandmarkEligibility, NATIVE_LANDMARK_ELIGIBILITY_SCOPE } = await server.ssrLoadModule(
    process.env.NATIVE_LANDMARK_ELIGIBILITY_MODULE ?? '/src/native-landmark-eligibility.ts',
  ))
} catch (error) { await server.close(); throw error }
if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })

function geometry() {
  const localPositions = new Float32Array(68 * 3)
  for (let i = 0; i < 32; i++) {
    const angle = i * 2 * Math.PI / 32
    localPositions.set([Math.cos(angle), Math.sin(angle), 0.1], (32 + i) * 3)
  }
  localPositions.set([0.2, 0, 0.1, 0.3, 0, 0.1, 0.2, 0.1, 0.1, 2 ** -149, 0, 0], 64 * 3)
  const indices = new Uint32Array(99)
  for (let i = 0; i < 32; i++) indices.set([i, 32 + i, 32 + (i + 1) % 32], i * 3)
  indices.set([64, 65, 66], 96)
  const worldPositions = Float64Array.from(localPositions)
  for (let i = 2; i < worldPositions.length; i += 3) worldPositions[i] -= 1
  return { localPositions, indices, worldPositions }
}

function receipts(id, buffers) {
  return Object.entries(buffers).map(([name, array]) => ({ primitiveId: id, name, arrayType: array.constructor.name,
    byteLength: array.byteLength, sha256: createHash('sha256').update(new Uint8Array(array.buffer, array.byteOffset, array.byteLength)).digest('hex') }))
}

const identityMatrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
const modelMatrix = [...identityMatrix.slice(0, 14), -1, 1]

function fixture() {
  const id = 'native/marker#primitive/0', buffers = geometry(), classVertexIds = Array.from({ length: 32 }, (_, i) => i)
  const draw = {
    drawRevision: 7, rendererFrame: 19, contextRevision: 2, submittedAtPerformanceMs: 10, viewId: 'measured', timeSeconds: 1,
    camera: { uuid: 'camera', positionMetres: [0, 0, 0], quaternion: [0, 0, 0, 1], verticalFovDegrees: 90, aspect: 1, near: 0.1, far: 10,
      layersMask: 1, viewOffset: null, matrixWorld: identityMatrix, matrixWorldInverse: identityMatrix,
      projectionMatrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -10.1 / 9.9, -1, 0, 0, -2 / 9.9, 0],
      projectionMatrixInverse: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, -9.9 / 2, 0, 0, -1, 10.1 / 2] },
    viewportBackingPixels: [0, 0, 101, 101], scissorBackingPixels: [0, 0, 101, 101], scissorTest: true, renderTarget: null,
    canvas: { width: 101, height: 101, clientWidth: 101, clientHeight: 101, devicePixelRatio: 1 }, presentation: 'native',
    rectSourcePixels: [0, 0, 1920, 1080], sourceOpacity: 1, imagePlaneWarp: null, sourceAssembly: { kind: 'operating' }, sourceLayout: [],
    nativeRenderCallbacks: [{ objectUuid: 'object', materialUuid: 'material', group: null }],
  }
  const model = { runtimeRootUuid: 'root', provenance: { identity: 'matched', sourceSha256: 'a'.repeat(64), expectedSha256: 'b'.repeat(64), observedSha256: 'b'.repeat(64) },
    identityMapSha256: 'c'.repeat(64), canonicalModelSha256: 'd'.repeat(64), semanticSha256: 'e'.repeat(64) }
  const census = { artifactPrimitiveCount: 1, artifactMeshNodeCount: 1, runtimeClonePrimitiveCount: 0,
    springPrimitiveCount: 0, artifactSpringPrimitiveCount: 0, runtimeCloneSpringPrimitiveCount: 0 }
  const row = { id, identity: { canonicalId: id, nodePath: 'native/marker', nativeNodeIndex: 3, representationMeshIndex: 2,
    primitiveIndex: 0, gltfMode: 4, positionAccessor: 398, indexAccessor: 397 }, scope: 'artifact', runtimeInstance: null,
    objectUuid: 'object', objectName: 'marker', geometryUuid: 'geometry', vertexCount: 68, indexCount: 99, indexOrigin: 'decoded-index-attribute',
    decodedPosition: { componentType: 'Float32', itemSize: 3, normalized: false, interleaved: false, version: 0 },
    decodedIndex: { componentType: 'Uint32Array', version: 0 }, matrixLocal: modelMatrix, matrixWorld: modelMatrix, ancestors: [],
    visibility: 'visible-through-ancestors', cameraLayerEligible: true, renderedPresence: 'native-render-callback-observed',
    renderSubmissions: draw.nativeRenderCallbacks, drawMode: 'triangles', drawRange: { start: 0, count: null, effectiveStart: 0, effectiveCount: 99 },
    groups: [], layersMask: 1, frustumCulled: true, renderOrder: 0, materials: [{ uuid: 'material' }],
    deformation: { kind: 'matrix-only', cpuEvaluation: 'float64-matrix-world-on-decoded-float32-position' },
    buffers: { localPositions: `${id}/localPositions`, indices: `${id}/indices`, worldPositions: `${id}/worldPositions` } }
  const input = { crankTurns: 0, amplitudes: [], phases: [], gearing: 'fine', magnification: 1, setup: {} }
  const metadata = { status: 'current-diagnostic-submission', method: 'current-native-renderer-submission-metadata', reason: null,
    sourceProof: false, sourceAcceptance: false, sourceQualification: 'not-performed',
    gpuSafety: 'independent-gpu-rounding-raster-and-first-surface-proof-required', model, machineRevision: 4, inventoryRevision: 5,
    input, draw, census, runtimeInstanceDeclarations: [] }
  const snapshot = { status: 'captured', method: 'current-native-cpu-geometry', manifest: { schemaVersion: 1, method: 'current-native-cpu-geometry',
    worldCoordinatePrecision: 'float64-cpu-not-exact-gpu', geometricResidualToleranceMetres: 1e-7,
    bufferEncoding: 'typed-arrays-packed-xyz-no-welding', bufferByteOrder: 'little-endian', model, machineRevision: 4, inventoryRevision: 5,
    input, draw, census, runtimeInstanceDeclarations: [], primitives: [row], runtimeClones: [], issues: { bindingFailures: [], currentOverrideMisses: [] } }, buffers: { [id]: buffers } }
  const hit = { primitiveId: id, identity: row.identity, scope: row.scope, runtimeInstance: null, triangleIndex: 31, indexOffset: 93,
    vertexIds: [31, 63, 32], materialUuid: 'material', distanceMetres: 1, barycentric: [1, 0, 0], worldPointMetres: [0, 0, -1],
    targetResidualMetres: 0, targetClassIncident: true }
  const bufferReceipts = receipts(id, buffers)
  const result = { eligibilityScope: 'queried-ray-exact-vertex-identity', eligibility: 'eligible-cpu-exact-local-class', targetPrimitiveId: id, targetLocalCoordinate: [0, 0, 0], classVertexIds,
    geometricResidualToleranceMetres: 1e-7, firstHit: hit, coincidentClosestHits: [hit], scope: { primitiveCount: 1,
      artifactPrimitiveCount: 1, runtimeClonePrimitiveCount: 0, springPrimitiveCount: 0, drawSubmissionCount: 1, limitations: [], rayProofLimited: false },
    safety: { sourceQualification: 'not-performed', gpuSafety: 'unmeasured-independent-proof-required', worldCoordinatePrecision: 'float64-cpu-not-exact-gpu',
      gpuRoundingBoundMetres: null, rasterFirstSurfaceCertificate: false, genericApproval: false } }
  const projection = { metadata, anchor: { id: 'apex', partPath: 'native/marker', partLocalMetres: [0, 0, 0] }, capture: {
    method: 'gpu-readback', visibilityMode: 'depth-off-landmark-projection', status: 'captured', sourceOpacity: 1, viewId: 'measured',
    timeSeconds: 1, presentation: 'native', resolvedImagePlaneWarp: null, sourceAssembly: { kind: 'operating' }, sourceLayout: [],
    nativeViewportBackingPixels: null, destinationCellSourcePixels: [1920 / 101, 1080 / 101], landmarks: [{ id: 'apex',
      partPath: 'native/marker', runtimeTemplatePartPath: null, state: 'rendered', worldMetres: [0, 0, -1], worldReason: null,
      sourcePixels: [960, 540], canvasPixels: [50.5, 50.5], uncertaintySourcePixels: 0.4, uncertaintyCanvasPixels: 0.5, reason: null }] } }
  const target = { primitiveId: id, exactLocalPosition: [0, 0, 0], nativeStageBackingPixel: [50, 50] }
  const flags = { sourceProof: false, sourceAcceptance: false, numericVertexResidualBoundMetres: null, gpuPositionRoundingBoundMetres: null, eligibility: 'unresolved' }
  const gpu = { status: 'readback', reason: null, method: 'current-native-depth-target-surface-association', equivalence: 'depth-native-not-colour-or-composite',
    ...flags, request: { expectedDrawRevision: 7, expectedContextRevision: 2, expectedViewId: 'measured', expectedTimeSeconds: 1,
      targetPrimitiveId: id, targetIndexOffset: 0, exactLocalPosition: [0, 0, 0], nativeStageBackingPixel: [50, 50] },
    model, machineRevision: 4, inventoryRevision: 5, input, draw, census, runtimeInstanceDeclarations: [],
    target: { record: row, primitiveId: id, canonicalPrimitiveId: id, classVertexIndices: classVertexIds,
      incidentTriangleIndexOffsets: classVertexIds.map(i => i * 3), triangleCount: 33 },
    nativeStage: { width: 101, height: 101, viewportBackingPixels: [0, 0, 101, 101], scissorBackingPixels: [0, 0, 101, 101],
      scissorTest: true, pixelCentreBacking: [50.5, 50.5] },
    association: { ...flags, status: 'target-incident-triangle', primitiveId: id, canonicalPrimitiveId: id, triangleIndexOffset: 93,
      requestedTriangleIndexOffset: 0, targetClassVertexIndices: classVertexIds, incidentTriangleIndexOffsets: classVertexIds.map(i => i * 3), rawPixel: [32, 0, 0, 255] } }
  return { snapshot, currentMetadata: metadata, target, projection, gpu,
    cpu: { metadata, ray: deriveNativeStagePixelRay(draw, target.nativeStageBackingPixel), bufferReceipts, result }, independentGpuProof: null }
}

test('preserves all 32 exact seam rows but excludes one ULP and an unrounded sub-ULP query', () => {
  const { localPositions, indices } = geometry()
  assert.deepEqual(exactStoredF32Class(localPositions, [0, 0, -0]), Array.from({ length: 32 }, (_, i) => i))
  assert.deepEqual(exactStoredF32Class(localPositions, [2 ** -149, 0, 0]), [67])
  assert.deepEqual(exactStoredF32Class(localPositions, [Number.MIN_VALUE, 0, 0]), [])
  const triangles = incidentOriginalTriangles(indices, exactStoredF32Class(localPositions, [0, 0, 0]), 68)
  assert.deepEqual(triangles.map(triangle => triangle.indexOffset), Array.from({ length: 32 }, (_, i) => i * 3))
  assert.deepEqual(triangles.at(-1).vertexIds, [31, 63, 32])
})

test('derives the same GL stage ray from actual matrices even when source layout is mirrored and warped', () => {
  const input = fixture(), ordinary = deriveNativeStagePixelRay(input.currentMetadata.draw, [50, 50])
  input.currentMetadata.draw.presentation = 'horizontal-mirror'
  input.currentMetadata.draw.rectSourcePixels = [400, 200, 200, 100]
  input.currentMetadata.draw.imagePlaneWarp = { kind: 'homography', unwarpedViewportPixels: [101, 101], renderToSourcePixels: [2, 0, 100, 0, 2, 100, 0, 0, 1] }
  assert.deepEqual(deriveNativeStagePixelRay(input.currentMetadata.draw, [50, 50]), ordinary)
  assert.deepEqual(ordinary.direction, [0, 0, -1])
  assert.equal(ordinary.near, 0.1)
  assert.equal(ordinary.far, 10)
  assert.throws(() => deriveNativeStagePixelRay(input.currentMetadata.draw, [101, 50]), RangeError)
})

// These bounds are explicitly synthetic consumer controls, never actual GPU evidence.
function boundedProof(input, rounding = 2e-8, residual = 3e-8) {
  return { method: 'independent-gpu-position-and-residual-bound', status: 'bounded', measurement: 'gpu-position-readback',
    evidenceSha256: 'f'.repeat(64), controlEvidenceSha256: '1'.repeat(64), metadata: input.currentMetadata,
    bufferReceipts: input.cpu.bufferReceipts, targetPrimitiveId: input.target.primitiveId, exactLocalPosition: input.target.exactLocalPosition,
    classVertexIds: input.cpu.result.classVertexIds, nativeStageBackingPixel: input.target.nativeStageBackingPixel,
    gpuRoundingBoundMetres: rounding, numericVertexResidualBoundMetres: residual }
}

function addCoincidentPrimitive(input) {
  const original = input.snapshot.manifest.primitives[0], id = 'native/other#primitive/0'
  const row = { ...original, id, objectUuid: 'other-object', geometryUuid: 'other-geometry',
    identity: { ...original.identity, canonicalId: id, nodePath: 'native/other', nativeNodeIndex: 4 },
    renderSubmissions: [{ objectUuid: 'other-object', materialUuid: 'material', group: null }],
    buffers: { localPositions: `${id}/localPositions`, indices: `${id}/indices`, worldPositions: `${id}/worldPositions` } }
  input.snapshot.manifest.primitives.push(row)
  input.snapshot.buffers[id] = geometry()
  input.currentMetadata.census.artifactPrimitiveCount = 2
  input.currentMetadata.census.artifactMeshNodeCount = 2
  input.currentMetadata.draw.nativeRenderCallbacks.push(row.renderSubmissions[0])
  input.cpu.bufferReceipts.push(...receipts(id, input.snapshot.buffers[id]))
  input.cpu.result.scope.primitiveCount = 2
  input.cpu.result.scope.artifactPrimitiveCount = 2
  input.cpu.result.scope.drawSubmissionCount = 2
  return row
}

test('positive current CPU/class/GPU association remains unresolved without an independent GPU bound, preserving raw projection', async () => {
  const input = fixture(), result = await joinNativeLandmarkEligibility(input)
  assert.equal(result.state, 'unresolved')
  assert.deepEqual(result.reasons, ['independent-gpu-rounding-bound-not-supplied', 'independent-gpu-vertex-residual-bound-not-supplied'])
  assert.deepEqual(result.classVertexIds, Array.from({ length: 32 }, (_, i) => i))
  assert.equal(result.cpuGeometricResidualMetres, 0)
  assert.equal(result.measurements.projection, input.projection)
  assert.deepEqual(result.measurements.projection.capture.landmarks[0].sourcePixels, [960, 540])
  assert.equal(result.measurements.projection.capture.landmarks[0].uncertaintySourcePixels, 0.4)
})

test('producer-shaped unwarped and warped captures reach CPU/GPU association without granting source qualification', async () => {
  for (const presentation of ['native', 'horizontal-mirror']) {
    for (const warped of [false, true]) {
      const input = fixture(), draw = input.currentMetadata.draw, capture = input.projection.capture
      draw.presentation = capture.presentation = presentation
      if (warped) {
        draw.imagePlaneWarp = { kind: 'homography', unwarpedViewportPixels: [100.25, 100.75],
          renderToSourcePixels: [1, 0, 0, 0, 1, 0, 0, 0, 1] }
        capture.resolvedImagePlaneWarp = structuredClone(draw.imagePlaneWarp)
        capture.nativeViewportBackingPixels = draw.imagePlaneWarp.unwarpedViewportPixels.map(Math.ceil)
      }
      const result = await joinNativeLandmarkEligibility(input)
      assert.equal(result.state, 'unresolved')
      assert.deepEqual(result.reasons, ['independent-gpu-rounding-bound-not-supplied', 'independent-gpu-vertex-residual-bound-not-supplied'])
      assert.equal(result.cpuGeometricResidualMetres, 0)
      assert.equal(result.sourceProof, false)
      assert.equal(result.sourceAcceptance, false)
      assert.equal(result.measurements.projection, input.projection)
    }
  }
})

test('mismatched or absent viewport backing and image-plane identity fail closed before CPU/GPU association', async () => {
  for (const warped of [false, true]) {
    for (const backing of warped ? [[100, 101], [101, 100], null, undefined] : [[101, 101], undefined]) {
      const input = fixture(), draw = input.currentMetadata.draw, capture = input.projection.capture
      if (warped) {
        draw.imagePlaneWarp = { kind: 'homography', unwarpedViewportPixels: [100.25, 100.75],
          renderToSourcePixels: [1, 0, 0, 0, 1, 0, 0, 0, 1] }
        capture.resolvedImagePlaneWarp = structuredClone(draw.imagePlaneWarp)
      }
      capture.nativeViewportBackingPixels = backing
      const result = await joinNativeLandmarkEligibility(input)
      assert.equal(result.state, 'unresolved')
      assert.deepEqual(result.reasons, ['projection-current-draw-identity-mismatch'])
      assert.equal(result.cpuGeometricResidualMetres, null)
      assert.equal(result.measurements.projection, input.projection)
    }
  }
  const input = fixture()
  input.projection.capture.resolvedImagePlaneWarp = { kind: 'homography', unwarpedViewportPixels: [101, 101],
    renderToSourcePixels: [1, 0, 0, 0, 1, 0, 0, 0, 1] }
  assert.deepEqual((await joinNativeLandmarkEligibility(input)).reasons, ['projection-current-draw-identity-mismatch'])
})

test('bounded consumer control accepts every incident class triangle, not only the requested triangle, and keeps the 1e-7 budget', async () => {
  const input = fixture()
  input.independentGpuProof = boundedProof(input)
  let result = await joinNativeLandmarkEligibility(input)
  assert.equal(result.state, 'eligible')
  assert.equal(result.eligibilityScope, NATIVE_LANDMARK_ELIGIBILITY_SCOPE)
  assert.equal(result.combinedGpuVertexBoundMetres, 5e-8)
  assert.equal(result.sourceAcceptance, false)
  input.independentGpuProof = boundedProof(input, 1e-7, 0)
  assert.equal((await joinNativeLandmarkEligibility(input)).state, 'eligible')
  input.independentGpuProof = boundedProof(input, 1e-7 + Number.EPSILON * 1e-7, 0)
  assert.equal((await joinNativeLandmarkEligibility(input)).state, 'ineligible')
  input.independentGpuProof = boundedProof(input, 6e-8, 5e-8)
  result = await joinNativeLandmarkEligibility(input)
  assert.equal(result.state, 'ineligible')
  assert.deepEqual(result.reasons, ['independently-bounded-gpu-position-exceeds-geometric-budget'])
})

test('one-ULP stored neighbour cannot borrow the 32-row apex topology', async () => {
  const input = fixture()
  input.target.exactLocalPosition = [2 ** -149, 0, 0]
  const result = await joinNativeLandmarkEligibility(input)
  assert.equal(result.state, 'ineligible')
  assert.deepEqual(result.classVertexIds, [67])
  assert.deepEqual(result.reasons, ['target-class-has-no-original-incident-triangle'])
})

test('coincident world positions in a different native primitive earn neither CPU nor GPU target credit', async () => {
  const cpuInput = fixture(), other = addCoincidentPrimitive(cpuInput)
  const otherHit = { ...cpuInput.cpu.result.firstHit, primitiveId: other.id, identity: other.identity, targetClassIncident: false }
  cpuInput.cpu.result.firstHit = otherHit
  cpuInput.cpu.result.coincidentClosestHits = [otherHit]
  cpuInput.cpu.result.eligibility = 'ineligible-first-surface'
  let result = await joinNativeLandmarkEligibility(cpuInput)
  assert.equal(result.state, 'ineligible')
  assert.deepEqual(result.reasons, ['cpu-occluded-by-other-native-primitive'])
  const gpuInput = fixture(), occluder = addCoincidentPrimitive(gpuInput)
  Object.assign(gpuInput.gpu.association, { status: 'occluded-by-native-primitive', primitiveId: occluder.id, canonicalPrimitiveId: occluder.identity.canonicalId, triangleIndexOffset: null })
  result = await joinNativeLandmarkEligibility(gpuInput)
  assert.equal(result.state, 'ineligible')
  assert.deepEqual(result.reasons, ['gpu-occluded-by-other-native-primitive'])
})

test('adjacent GPU triangle is ineligible even when the same primitive/class is present and bounds are missing', async () => {
  const input = fixture()
  input.gpu.association.status = 'target-other-triangle'
  input.gpu.association.triangleIndexOffset = 96
  const result = await joinNativeLandmarkEligibility(input)
  assert.equal(result.state, 'ineligible')
  assert.deepEqual(result.reasons, ['gpu-first-surface-is-adjacent-nonclass-triangle'])
})

test('stale draw, camera, context or inventory cannot join otherwise positive evidence', async () => {
  for (const mutate of [
    gpu => { gpu.draw.drawRevision++ },
    gpu => { gpu.draw.contextRevision++ },
    gpu => { gpu.draw.viewId = 'earlier-view' },
    gpu => { gpu.draw.camera.projectionMatrix[8] = 0.1 },
    gpu => { gpu.inventoryRevision++ },
  ]) {
    const input = fixture()
    input.gpu = structuredClone(input.gpu)
    mutate(input.gpu)
    const result = await joinNativeLandmarkEligibility(input)
    assert.equal(result.state, 'unresolved')
    assert.deepEqual(result.reasons, ['stale-or-asymmetric-gpu-target-state'])
  }
  const input = fixture()
  delete input.snapshot.manifest.inventoryRevision
  assert.deepEqual((await joinNativeLandmarkEligibility(input)).reasons, ['missing-or-mismatched-inventory-revision'])
})

test('changed actual bytes, incomplete full-scope receipts and unsupported CPU modes stay unresolved', async () => {
  const altered = fixture()
  altered.snapshot.buffers[altered.target.primitiveId].worldPositions[99] += 0.01
  assert.deepEqual((await joinNativeLandmarkEligibility(altered)).reasons, ['cpu-buffer-sha256-mismatch'])
  const partial = fixture()
  partial.cpu.bufferReceipts.pop()
  assert.deepEqual((await joinNativeLandmarkEligibility(partial)).reasons, ['incomplete-full-scope-cpu-buffer-receipts'])
  const limited = fixture()
  limited.cpu.result.scope.rayProofLimited = true
  limited.cpu.result.scope.limitations.push({ reason: 'unsupported clipping' })
  assert.deepEqual((await joinNativeLandmarkEligibility(limited)).reasons, ['unsupported-full-scope-cpu-raster-or-deformation-mode'])
})

test('null, nonfinite, CPU-labelled or stale independent bounds do not qualify a current positive association', async () => {
  for (const mutate of [
    proof => { proof.gpuRoundingBoundMetres = null },
    proof => { proof.numericVertexResidualBoundMetres = null },
    proof => { proof.gpuRoundingBoundMetres = NaN },
    proof => { proof.measurement = 'cpu-world-residual' },
    proof => { proof.metadata.draw.timeSeconds = 0 },
  ]) {
    const input = fixture()
    input.independentGpuProof = structuredClone(boundedProof(input))
    mutate(input.independentGpuProof)
    assert.equal((await joinNativeLandmarkEligibility(input)).state, 'unresolved')
  }
})

test('missing unwarped pixel authority and foreign-camera rays remain unresolved without altering projection', async () => {
  const missing = fixture()
  missing.target = null
  let result = await joinNativeLandmarkEligibility(missing)
  assert.equal(result.state, 'unresolved')
  assert.deepEqual(result.reasons, ['missing-unique-native-target-or-unwarped-stage-pixel-authority'])
  assert.equal(result.measurements.projection, missing.projection)
  const foreignRay = fixture()
  foreignRay.cpu.ray.origin = [1, 0, 0]
  result = await joinNativeLandmarkEligibility(foreignRay)
  assert.equal(result.state, 'unresolved')
  assert.deepEqual(result.reasons, ['cpu-ray-is-not-the-current-unwarped-native-stage-pixel'])
})

test('general landmark claims or absent CPU query scope cannot join otherwise positive exact-class evidence', async () => {
  const positive = fixture()
  positive.independentGpuProof = boundedProof(positive)
  assert.equal((await joinNativeLandmarkEligibility(positive)).state, 'eligible')
  for (const scope of [undefined, 'general-native-landmark-validity']) {
    const input = fixture()
    input.cpu.result.eligibilityScope = scope
    const result = await joinNativeLandmarkEligibility(input)
    assert.equal(result.state, 'unresolved')
    assert.deepEqual(result.reasons, ['missing-or-unsupported-cpu-query-eligibility-scope'])
    assert.equal(result.eligibilityScope, NATIVE_LANDMARK_ELIGIBILITY_SCOPE)
    assert.equal(result.measurements.projection, input.projection)
  }
})

test('stale GPU readback refuses even a known CPU occluder instead of joining obsolete surface evidence', async () => {
  const input = fixture(), other = addCoincidentPrimitive(input)
  const hit = { ...input.cpu.result.firstHit, primitiveId: other.id, identity: other.identity, targetClassIncident: false }
  input.cpu.result.firstHit = hit
  input.cpu.result.coincidentClosestHits = [hit]
  input.cpu.result.eligibility = 'ineligible-first-surface'
  input.gpu = { status: 'stale', reason: 'Draw changed', request: input.gpu.request }
  const result = await joinNativeLandmarkEligibility(input)
  assert.equal(result.state, 'unresolved')
  assert.deepEqual(result.reasons, ['missing-or-stale-actual-gpu-target-association'])
})
