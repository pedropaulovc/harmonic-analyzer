import test from 'node:test'
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
import { BufferGeometry, DoubleSide, Float32BufferAttribute, Mesh, MeshBasicMaterial, PerspectiveCamera, Raycaster, Vector2 } from 'three'
import { canonicalJson, parseNativeRawGLB, sha256 } from './native-model-byte-proof.mjs'
import { MODEL_COMMIT, MODEL_SHA256 } from './verify-reference.mjs'
import { verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'

const bindingsURL = process.env.NATIVE_SOURCE_FEATURE_BINDINGS_PATH
  ? pathToFileURL(process.env.NATIVE_SOURCE_FEATURE_BINDINGS_PATH)
  : new URL('./native-source-feature-bindings.mjs', import.meta.url)
const { createNativeSourceFeatureBindings, nativeWitnessAtOriginalPoint, nativeSourceVisibilityExpectation } = await import(bindingsURL)

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

const contourViewport = [80, 60]
// x = 100 + 2u/d, y = 50 + 1.5v/d, d = 1 + u/100 + v/200.
// Its denominator varies across the image: this is genuinely projective, not
// an affine identity with a decorative presentation flag.
const contourWarp = { kind: 'homography', unwarpedViewportPixels: contourViewport,
  renderToSourcePixels: [3, 0.5, 100, 0.5, 1.75, 50, 0.01, 0.005, 1] }

function contourRawModel() {
  // A left foreground triangle, a larger left triangle behind it, and an
  // differently sized right triangle nearer the camera. A second mirror hits
  // a real, wrong first surface, rather than merely missing empty space.
  const positions = new Float32Array([
    -2, -1.5, 0, -0.25, -1.5, 0, -1.125, 1.5, 0,
    -2.5, -2, -0.5, -0.125, -2, -0.5, -1.25, 2, -0.5,
    0.25, -0.5, 0.5, 1.75, -0.5, 0.5, 1, 1.5, 0.5,
  ])
  const normals = new Float32Array(positions.length)
  for (let offset = 2; offset < normals.length; offset += 3) normals[offset] = 1
  const indices = Uint32Array.from({ length: positions.length / 3 }, (_, index) => index)
  const binary = Buffer.concat([positions, normals, indices].map(array => Buffer.from(array.buffer)))
  const document = { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }],
    nodes: [{ name: 'harmonic-analyzer', children: [1] }, { name: 'asymmetric-contour', mesh: 0 }],
    buffers: [{ byteLength: binary.length }],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: positions.byteLength },
      { buffer: 0, byteOffset: positions.byteLength, byteLength: normals.byteLength },
      { buffer: 0, byteOffset: positions.byteLength + normals.byteLength, byteLength: indices.byteLength }],
    accessors: [{ bufferView: 0, componentType: 5126, count: positions.length / 3, type: 'VEC3' },
      { bufferView: 1, componentType: 5126, count: normals.length / 3, type: 'VEC3' },
      { bufferView: 2, componentType: 5125, count: indices.length, type: 'SCALAR' }],
    materials: [{ doubleSided: true }],
    meshes: [{ primitives: [{ mode: 4, attributes: { POSITION: 0, NORMAL: 1 }, indices: 2, material: 0 }] }] }
  const text = Buffer.from(JSON.stringify(document)), jsonLength = Math.ceil(text.length / 4) * 4
  const bytes = Buffer.alloc(28 + jsonLength + binary.length)
  bytes.writeUInt32LE(0x46546c67); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(jsonLength, 12); bytes.writeUInt32LE(0x4e4f534a, 16)
  bytes.fill(32, 20, 20 + jsonLength); text.copy(bytes, 20)
  bytes.writeUInt32LE(binary.length, 20 + jsonLength); bytes.writeUInt32LE(0x004e4942, 24 + jsonLength)
  binary.copy(bytes, 28 + jsonLength)
  return parseNativeRawGLB(bytes)
}

function originalContourFixture(presentation, warped) {
  const nativeModel = contourRawModel(), raw = [...nativeModel.primitives.values()][0]
  const original = { path: raw.path, restMatrixF64: raw.restMatrixF64, binding: null, bindingOwnerPath: null, station: null }
  const poseOracle = { inventory: { drawables: [original] },
    solve: () => ({ drawables: [{ path: raw.path, matrixWorld: raw.restMatrixF64, effectiveVisibility: true }] }) }
  const descriptor = { mode: 4, attributes: Object.fromEntries(Object.entries(raw.attributes).map(([name, attribute]) => [name, {
    componentType: attribute.componentType, type: 'VEC3', count: attribute.count, normalized: attribute.normalized,
    typedBytesSha256: sha256(attribute.bytes),
  }])), indices: { componentType: 5125, type: 'SCALAR', count: raw.index.length, normalized: false,
    typedBytesSha256: sha256(nativeModel.accessor(2).bytes) }, material: raw.material }
  const proof = { method: 'exact-original-native-primitive-role-v1', qualifiedPartPath: raw.path,
    historicalSource: { sha256: '2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d', sourceCommit: '1268c23d4a8fc741147c5e09d8d1e45247a71945' },
    currentSource: { sha256: MODEL_SHA256, sourceCommit: MODEL_COMMIT },
    historicalPrimitiveSha256: raw.rawPrimitiveSHA256, currentPrimitiveSha256: raw.rawPrimitiveSHA256,
    historicalWorldMatrix: Array.from(raw.restMatrixF64), currentWorldMatrix: Array.from(raw.restMatrixF64), primitives: [descriptor] }
  const body = { status: 'mapped', reason: null, proof }
  const serializedProof = canonicalJson(body)
  const pixels = warped ? [[134, 79], [136, 81]] : [[214, 89], [210, 93]]
  const check = { id: 'original-left-contour', viewId: 'main', role: 'check',
    originalPartPath: raw.path, partPath: raw.path, sourceContourPixels: pixels,
    sourceUncertaintyPixels: 0.25, nativeAssociation: { status: 'mapped', reason: null,
      proofRef: raw.path, proofSha256: sha256(serializedProof) } }
  const camera = { positionMetres: [0, 0, 2], quaternion: [0, 0, 0, 1], verticalFovDegrees: 90 }
  const view = { id: 'main', camera }
  const sourceImage = { frameIndex: 0, pixelFormat: 'bgr8', width: 320, height: 180,
    sourceSha256: sourceSHA, sha256Bgr8: 'c'.repeat(64) }
  const sourceFrame = { shotId: 'original-contour-shot', timeSeconds: 0, decodedTimeSeconds: 0,
    sourceImage, views: [view], landmarks: [], sourceContourChecks: [check] }
  const record = { id: 'original-contour-video', native: { observedSha256: sourceSHA },
    observations: { frames: [sourceFrame], anchors: [], nativeBodyAssociations: { [raw.path]: { ...body, serializedProof } } } }
  const frame = { ...sourceFrame, contourChecks: [{ viewId: 'main', check }] }
  const binding = { sourceVideoId: record.id, sourceSha256: sourceSHA, sourceImage,
    decodedTimestampTicks: '0', timeBase: '1/1', decodedTimeSeconds: 0, timeSeconds: 0,
    shotId: sourceFrame.shotId, viewId: view.id, camera, input: {}, partOverrides: [],
    rectSourcePixels: [100, 50, 160, 90], presentation, resolvedImagePlaneWarp: warped ? contourWarp : null }
  const result = createNativeSourceFeatureBindings({ nativeModel, poseOracle }).forView({
    record, frame, view, binding, viewport: contourViewport,
  })
  return { raw, pixels, result }
}

function analyticalContourPixel(sourcePixel, warped) {
  const [x, y] = sourcePixel, [width, height] = contourViewport
  let u, v
  if (warped) {
    // Solve the two translated equations directly; neither the production
    // homography inverse nor its project/unproject helpers are the oracle.
    const X = x - 100, Y = y - 50, d = 1 / (1 - X / 200 - Y / 300)
    u = X * d / 2; v = Y * d / 1.5
  } else {
    u = (1 - (x - 100) / 160) * width
    v = (y - 50) / 90 * height
  }
  return [Math.floor(u), height - 1 - Math.floor(v)]
}

function assertContourFirstSurface(presentation, warped) {
  const { raw, pixels, result } = originalContourFixture(presentation, warped)
  assert.deepEqual(result.unavailable, [], 'exact original contour must remain measurable')
  assert.equal(result.bodyProof.contours.length, 1)
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new Float32BufferAttribute(raw.positions, 3))
  geometry.setIndex(Array.from(raw.index))
  const material = new MeshBasicMaterial({ side: DoubleSide }), mesh = new Mesh(geometry, material)
  mesh.updateMatrixWorld(true)
  const [width, height] = contourViewport, camera = new PerspectiveCamera(90, width / height, 0.005, 100)
  camera.position.set(0, 0, 2); camera.updateMatrixWorld(true)
  const raycaster = new Raycaster(), contour = result.bodyProof.contours[0]
  try {
    assert.equal(contour.rayAnchorIds.length, pixels.length)
    for (const [index, sourcePixel] of pixels.entries()) {
      const expectedPixel = analyticalContourPixel(sourcePixel, warped)
      const xNDC = (expectedPixel[0] + 0.5) / width * 2 - 1, yNDC = (expectedPixel[1] + 0.5) / height * 2 - 1
      // Camera is at (0,0,2), looks down -Z, and has tan(FOV/2)=1.
      const expectedPoint = [2 * xNDC * width / height, 2 * yNDC, 0]
      const expectedDistance = Math.hypot(expectedPoint[0], expectedPoint[1], 2)
      const expectedDirection = [expectedPoint[0] / expectedDistance, expectedPoint[1] / expectedDistance, -2 / expectedDistance]
      const actual = result.bodyProof.rays.find(ray => ray.anchorId === contour.rayAnchorIds[index])
      assert.ok(actual, 'each original contour point must produce its own actual native support ray')
      raycaster.setFromCamera(new Vector2((actual.pixel[0] + 0.5) / width * 2 - 1,
        (actual.pixel[1] + 0.5) / height * 2 - 1), camera)
      const intersections = raycaster.intersectObject(mesh, false)
      assert.equal(intersections[0]?.faceIndex, 0,
        `original left contour at ${sourcePixel} must hit the left foreground surface, not the mirrored right surface at native pixel ${actual.pixel}`)
      assert.equal(intersections[1]?.faceIndex, 1, 'the other left triangle is a real farther surface, not the first hit')
      assert.deepEqual(actual.pixel, expectedPixel)
      for (let axis = 0; axis < 3; axis++) {
        assert.ok(Math.abs(raycaster.ray.direction.getComponent(axis) - expectedDirection[axis]) < 1e-14, 'native ray must equal the independent analytical inverse-camera direction')
        assert.ok(Math.abs(intersections[0].point.getComponent(axis) - expectedPoint[axis]) < 1e-14, 'first triangle intersection must equal the independently derived surface point')
      }
      assert.ok(Math.abs(intersections[0].distance - expectedDistance) < 1e-14)
      raycaster.setFromCamera(new Vector2(-xNDC, yNDC), camera)
      const opposite = raycaster.intersectObject(mesh, false)[0]
      assert.equal(opposite?.faceIndex, 2, 'wrong-side control must hit a distinct authentic asymmetric surface')
      assert.equal(opposite.point.z, 0.5)
    }
  } finally { geometry.dispose(); material.dispose() }
}

test('resolved projective warp with horizontal-mirror keeps the original contour on its first native surface', () => {
  assertContourFirstSurface('horizontal-mirror', true)
})

test('unwarped horizontal-mirror maps the original contour to its first native surface', () => {
  assertContourFirstSurface('horizontal-mirror', false)
})

test('resolved projective warp without mirror maps the original contour to its first native surface', () => {
  assertContourFirstSurface('native', true)
})
