import test from 'node:test'
import assert from 'node:assert/strict'
import { CURRENT_NATIVE_RAW_SHA256, jsonDigest, parseNativeRawGLB, sha256 } from './native-model-byte-proof.mjs'
import { verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'
import { reproveCurrentNativeFitAssociationPrimitives } from './current-native-fit-association.mjs'
import { prepareCurrentNativeRockerCapWitness, createCurrentNativeRockerCapFitDefinitions } from './current-native-rocker-cap-fit.mjs'

// Analytic indexed stock, not a synthetic CURRENT462 model. All local coordinates
// are dyadic, hence independently exact Float32 values. The segmented perimeter
// has a genuinely sloped distal edge: top (4.5, 1.5), bottom (5, -0.5).
// Its two different native-Z faces have the same full native-X span. Fixture
// model/primitive seals come from actual fixture bytes, never the current pin.
const profile = [[-4, -1], [-2, -2], [0, -1.75], [2, -1.25], [5, -0.5],
  [4.5, 1.5], [2, 2], [0, 2.25], [-2, 1.75], [-4, 1]]
const evidenceHash = jsonDigest({ kind: 'analytic-stock-fixture-only', physicalSourceAcceptance: false })
const control = corner => ({ anchorId: `fixture-${corner}`, primitiveIndex: 0, corner, exterior: 'minimum-native-Z',
  construction: 'positive-native-X-terminal-stock-cap-corner-v1', sourceSemanticEvidence: 'Explicit analytic fixture cap corner, not a measured source correspondence.' })
const prepare = (primitive, corner = 'top') => prepareCurrentNativeRockerCapWitness(primitive, control(corner), `fixture-${corner}`, evidenceHash)

function parseFixture(positions, indices) {
  const p = new Float32Array(positions), n = new Float32Array(p.length), i = new Uint32Array(indices)
  for (let offset = 2; offset < n.length; offset += 3) n[offset] = 1
  const binary = Buffer.concat([p, n, i].map(array => Buffer.from(array.buffer)))
  const document = { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }],
    nodes: [{ name: 'analytic-stock', mesh: 0 }], buffers: [{ byteLength: binary.length }],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: p.byteLength },
      { buffer: 0, byteOffset: p.byteLength, byteLength: n.byteLength },
      { buffer: 0, byteOffset: p.byteLength + n.byteLength, byteLength: i.byteLength }],
    accessors: [{ bufferView: 0, componentType: 5126, count: p.length / 3, type: 'VEC3' },
      { bufferView: 1, componentType: 5126, count: n.length / 3, type: 'VEC3' },
      { bufferView: 2, componentType: 5125, count: i.length, type: 'SCALAR' }],
    materials: [{ doubleSided: true }], meshes: [{ primitives: [{ mode: 4, attributes: { POSITION: 0, NORMAL: 1 }, indices: 2, material: 0 }] }] }
  const json = Buffer.from(JSON.stringify(document)), jsonLength = Math.ceil(json.length / 4) * 4
  const bytes = Buffer.alloc(28 + jsonLength + binary.length)
  bytes.writeUInt32LE(0x46546c67); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(jsonLength, 12); bytes.writeUInt32LE(0x4e4f534a, 16)
  bytes.fill(32, 20, 20 + jsonLength); json.copy(bytes, 20)
  bytes.writeUInt32LE(binary.length, 20 + jsonLength); bytes.writeUInt32LE(0x004e4942, 24 + jsonLength)
  binary.copy(bytes, 28 + jsonLength)
  const nativeModel = { ...parseNativeRawGLB(bytes), rawSHA256: sha256(bytes) }
  return { nativeModel, primitive: [...nativeModel.primitives.values()][0] }
}

function stockFixture({ perimeter = profile, planes = [{ z: -0.125, scale: 1 }, { z: 0.25, scale: 1 }], seam = true,
  walls = true, hole = false, mutate = null } = {}) {
  const positions = [], indices = [], rings = [], centres = []
  const vertex = point => { const index = positions.length / 3; positions.push(...point); return index }
  for (const [planeIndex, plane] of planes.entries()) {
    const centre = hole ? null : vertex([0, 0, plane.z])
    centres.push(centre)
    const outer = perimeter.map(([x, y]) => vertex([x * plane.scale, y, plane.z]))
    rings.push(outer)
    if (hole) {
      const inner = perimeter.map(([x, y]) => vertex([x * plane.scale / 4, y / 4, plane.z]))
      for (let j = 0; j < perimeter.length; j++) {
        const next = (j + 1) % perimeter.length
        const triangles = [[outer[j], outer[next], inner[next]], [outer[j], inner[next], inner[j]]]
        for (const triangle of triangles) indices.push(...(planeIndex % 2 ? [...triangle].reverse() : triangle))
      }
    } else {
      for (let j = 0; j < perimeter.length; j++) {
        const triangle = [centre, outer[j], outer[(j + 1) % perimeter.length]]
        indices.push(...(planeIndex % 2 ? [...triangle].reverse() : triangle))
      }
    }
  }
  if (seam && !hole && perimeter === profile) {
    // Replace only one front triangle's centre/top with exact stored seam
    // duplicates. Its two shared geometric edges must remain interior.
    const topDuplicate = vertex([4.5, 1.5, planes[0].z]), centreDuplicate = vertex([0, 0, planes[0].z])
    indices[5 * 3] = centreDuplicate; indices[5 * 3 + 1] = topDuplicate
  }
  if (walls && rings.length >= 2) {
    for (let j = 0; j < perimeter.length; j++) {
      const next = (j + 1) % perimeter.length, a = rings[0][j], b = rings[0][next], c = rings[1][next], d = rings[1][j]
      indices.push(a, b, c, a, c, d)
    }
  }
  mutate?.({ positions, indices, rings, centres, vertex })
  return parseFixture(positions, indices)
}

test('actual sloped terminal edge yields analytic top/bottom stored surface points with complete support', () => {
  const { primitive, nativeModel } = stockFixture(), top = prepare(primitive), bottom = prepare(primitive, 'bottom')
  assert.notEqual(nativeModel.rawSHA256, CURRENT_NATIVE_RAW_SHA256, 'fixture must not masquerade as admitted current raw bytes')
  assert.deepEqual(top.feature.localPointMetres, [4.5, 1.5, -0.125])
  assert.deepEqual(bottom.feature.localPointMetres, [5, -0.5, -0.125])
  assert.equal(top.witness.kind, 'mesh-vertex')
  assert.equal(bottom.witness.kind, 'mesh-vertex')
  assert.equal(top.feature.pointIsStoredVertex, true)
  assert.equal(top.feature.pointIsSurfacePoint, true)
  assert.equal(top.feature.constructionResidualMetres, 0)
  assert.equal(bottom.geometry.pointIsSurfacePoint, true)
  assert.deepEqual(top.witness.adjacentTriangleIndices, [4, 28, 30, 31])
  assert.deepEqual(bottom.witness.adjacentTriangleIndices, [3, 4, 26, 28, 29])
  assert.deepEqual(top.geometry.stockExteriorPlanes.map(plane => [plane.nativeZ, plane.nativeXSpan]), [[-0.125, 9], [0.25, 9]])
  assert.equal(top.geometry.selectedTerminalEdge.nativeXMidpoint, 4.75)
  assert.deepEqual(top.geometry.selectedTerminalEdge.top.localMetres, [4.5, 1.5, -0.125])
  assert.deepEqual(top.geometry.selectedTerminalEdge.bottom.localMetres, [5, -0.5, -0.125])
  assert.equal(top.geometry.frontBoundary.boundaryLoops.length, 1)
  assert.deepEqual(verifyNativeMeshFeatureWitness(top.witness, primitive).localPointMetres, [4.5, 1.5, -0.125])
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...top.witness, adjacentTriangleIndices: [4] }, primitive), /complete adjacent triangle membership/)
})

test('exact seam welding retains indexed triangles and one physical terminal point, not extra landmarks', () => {
  const { primitive } = stockFixture(), result = prepare(primitive), boundary = result.geometry.frontBoundary
  assert.deepEqual(result.geometry.coincidentRawVertexIndices, [6, 22])
  assert.deepEqual(result.geometry.coincidentSupportTriangleIndices, [4, 5, 28, 30, 31])
  assert.equal(boundary.weldedVertices.length, 11)
  assert.equal(boundary.boundaryEdges.length, 10)
  assert.deepEqual(boundary.completeIndexedTriangles[5].rawVertexIndices, [23, 22, 7])
  assert.deepEqual(result.geometry.selectedTerminalEdge.top.rawVertexIndices, [6, 22])
  assert.deepEqual(result.feature.supportTriangleIndices, [4, 28, 30, 31])
})

test('stored endpoint precision is retained and nearby seam coordinates are never proximity-welded', () => {
  const increment = 2 ** -20
  const changedEndpoint = stockFixture({ seam: false, mutate: ({ positions }) => { positions[6 * 3] += increment } })
  assert.deepEqual(prepare(changedEndpoint.primitive).feature.localPointMetres, [4.5 + increment, 1.5, -0.125])
  const nearbySeam = stockFixture({ mutate: ({ positions }) => { positions[22 * 3] += increment } })
  const result = prepare(nearbySeam.primitive)
  assert.deepEqual(result.feature.localPointMetres, [4.5, 1.5, -0.125])
  assert.deepEqual(result.geometry.coincidentRawVertexIndices, [6])
  assert.equal(result.geometry.frontBoundary.weldedVertices.length, 12)
  assert.equal(result.geometry.frontBoundary.boundaryEdges.length, 12)
})

test('a genuine planar hole stays a complete second boundary loop and cannot choose the distal cap', () => {
  const { primitive } = stockFixture({ hole: true }), result = prepare(primitive)
  assert.deepEqual(result.feature.localPointMetres, [4.5, 1.5, -0.125])
  assert.equal(result.geometry.frontBoundary.boundaryLoops.length, 2)
  assert.deepEqual(result.geometry.frontBoundary.boundaryLoops.map(loop => loop.weldedVertexIndices.length).sort((a, b) => a - b), [10, 10])
  assert.equal(result.geometry.frontStockPlane.completeRawTriangleIndices.length, 20)
  assert.equal(result.geometry.frontBoundary.boundaryEdges.length, 20)
})

test('a smaller-span planar patch does not replace either full-stock exterior', () => {
  const { primitive } = stockFixture({ planes: [{ z: -0.125, scale: 1 }, { z: 0.25, scale: 1 }, { z: 0, scale: 0.25 }] })
  const result = prepare(primitive)
  assert.deepEqual(result.feature.localPointMetres, [4.5, 1.5, -0.125])
  assert.deepEqual(result.geometry.stockExteriorPlanes.map(plane => plane.nativeZ), [-0.125, 0.25])
})

test('unequal, missing or extra maximal-span exterior planes are unavailable rather than ranked approximately', () => {
  for (const planes of [[{ z: -0.125, scale: 1 }, { z: 0.25, scale: 0.5 }],
    [{ z: -0.125, scale: 1 }], [{ z: -0.125, scale: 1 }, { z: 0.25, scale: 1 }, { z: 0, scale: 1 }]]) {
    assert.throws(() => prepare(stockFixture({ planes }).primitive), /exactly two distinct stock exterior planes/)
  }
})

test('nonmanifold edges, branched boundary components and degenerate face triangles refuse', () => {
  const nonmanifold = stockFixture({ mutate: ({ indices }) => indices.push(0, 1, 2) })
  assert.throws(() => prepare(nonmanifold.primitive), /nonmanifold planar face edge/)
  const branched = stockFixture({ mutate: ({ indices, rings, vertex }) => {
    const a = vertex([-3.5, -2.5, -0.125]), b = vertex([-3, -2.75, -0.125])
    indices.push(rings[0][0], a, b)
  } })
  assert.throws(() => prepare(branched.primitive), /open or branched.*closed 2-valent/)
  for (const triangle of [[0, 1, 1], [0, 0, 0]]) {
    const degenerate = stockFixture({ mutate: ({ indices }) => indices.push(...triangle) })
    assert.throws(() => prepare(degenerate.primitive), /degenerate planar face triangle/)
  }
})

test('greatest-midpoint ties, nonpositive stock ends and equal-Y terminal endpoints refuse', () => {
  const tied = stockFixture({ perimeter: [[-3, -1], [0, -2], [4, 0], [0, 2], [-3, 1]], seam: false })
  assert.throws(() => prepare(tied.primitive), /tied greatest native-X midpoint/)
  const negative = stockFixture({ seam: false, mutate: ({ positions }) => {
    for (let index = 0; index < positions.length; index += 3) positions[index] -= 8
  } })
  assert.throws(() => prepare(negative.primitive), /positive-native-X stock end/)
  const horizontal = stockFixture({ perimeter: [[-4, -1], [0, -2], [5, 1], [4.5, 1], [0, 2], [-4, 1]], seam: false })
  assert.throws(() => prepare(horizontal.primitive), /equal native Y/)
})

test('non-Float32, non-indexed, nonfinite and out-of-range raw geometry cannot provide surface support', () => {
  const { primitive } = stockFixture()
  assert.throws(() => prepare({ ...primitive, positions: Float64Array.from(primitive.positions) }), /indexed Float32/)
  assert.throws(() => prepare({ ...primitive, index: Uint16Array.from(primitive.index) }), /Uint32/)
  const nonfinite = Float32Array.from(primitive.positions); nonfinite[0] = NaN
  assert.throws(() => prepare({ ...primitive, positions: nonfinite }), /nonfinite/)
  const indices = Uint32Array.from(primitive.index); indices[0] = primitive.positions.length / 3
  assert.throws(() => prepare({ ...primitive, index: indices }), /out of range/)
})

test('closed selection rejects coordinate overrides, nonintegral ordinals and implicit corner semantics', () => {
  const { primitive } = stockFixture()
  for (const selection of [{ ...control('top'), partLocalMetres: [5, -0.5, -0.125] },
    { ...control('top'), primitiveIndex: 0.5 }, { ...control('top'), corner: 'nearest' },
    { ...control('top'), sourceSemanticEvidence: '' }, { ...control('top'), exterior: 'camera-front' }]) {
    assert.throws(() => prepareCurrentNativeRockerCapWitness(primitive, selection, 'fixture-top', evidenceHash), /closed keys|explicit closed/)
  }
  assert.throws(() => prepareCurrentNativeRockerCapWitness(primitive, { ...control('top'), primitiveIndex: 1 }, 'fixture-top', evidenceHash), /ordinal/)
})

function associationFixture() {
  const fixture = stockFixture(), { nativeModel, primitive } = fixture
  // Decimal source identity deliberately is not any point on this stock. Its
  // unchanged identity can reprove a primitive, never a surface coordinate.
  const originalAnchor = { id: 'fixture-top', kind: 'physical-feature', partPath: primitive.rawPath,
    partLocalMetres: [123.12345678, -45.12345678, 9.12345678],
    description: 'Left distal cap top physical corner on curved LOWER rocker stock' }
  const widths = { 1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4' }, index = nativeModel.accessor(2)
  const descriptor = { mode: 4, attributes: Object.fromEntries(Object.entries(primitive.attributes).map(([name, attribute]) => [name, {
    componentType: attribute.componentType, type: widths[attribute.itemSize], count: attribute.count,
    normalized: attribute.normalized, typedBytesSha256: sha256(attribute.bytes),
  }])), indices: { componentType: index.componentType, type: 'SCALAR', count: index.count, normalized: index.normalized,
    typedBytesSha256: sha256(index.bytes) }, material: primitive.material }
  const original = { path: primitive.path, restMatrixF64: Float64Array.from(primitive.restMatrixF64) }
  const anchor = { ...structuredClone(originalAnchor), nativeAssociation: { status: 'mapped', proof: {
    method: 'exact-original-native-local-feature-v1', currentSource: { sha256: CURRENT_NATIVE_RAW_SHA256 },
    qualifiedPartPath: primitive.rawPath, historicalAnchorSha256: jsonDigest(originalAnchor),
    currentNodeIndex: primitive.nodeIndex, currentWorldMatrix: Array.from(original.restMatrixF64), primitives: [descriptor],
  } } }
  return { ...fixture, descriptor, original, originalAnchor, anchor, inventoryByPath: new Map([[original.path, original]]) }
}

test('actual typed association reproves only the fixture primitive; decimal source XYZ cannot choose its cap', () => {
  const fixture = associationFixture(), primitives = reproveCurrentNativeFitAssociationPrimitives({ ...fixture, primitiveIndex: 0 })
  assert.equal(primitives.length, 1)
  assert.equal(primitives[0], fixture.primitive)
  assert.deepEqual(prepare(primitives[0]).feature.localPointMetres, [4.5, 1.5, -0.125])
  assert.deepEqual(fixture.anchor.partLocalMetres, [123.12345678, -45.12345678, 9.12345678])
  assert.notEqual(fixture.nativeModel.rawSHA256, CURRENT_NATIVE_RAW_SHA256)
})

test('changed real typed attribute/index bytes, descriptor semantics, material or CPU rest ancestry yield no cap primitive', () => {
  for (const mutate of [
    fixture => { fixture.primitive.attributes.NORMAL.bytes[0] ^= 1 },
    fixture => { fixture.nativeModel.accessor(2).bytes[0] ^= 1 },
    fixture => { fixture.descriptor.attributes.POSITION.componentType = 5123 },
    fixture => { fixture.descriptor.attributes.NORMAL.type = 'VEC2' },
    fixture => { fixture.descriptor.indices.normalized = true },
    fixture => { fixture.descriptor.material = null },
    fixture => { fixture.original.restMatrixF64[12] += 1 },
  ]) {
    const fixture = associationFixture(); mutate(fixture)
    assert.deepEqual(reproveCurrentNativeFitAssociationPrimitives({ ...fixture, primitiveIndex: 0 }), [])
  }
  const changedIdentity = associationFixture(); changedIdentity.anchor.partLocalMetres[0] += 1
  assert.throws(() => reproveCurrentNativeFitAssociationPrimitives({ ...changedIdentity, primitiveIndex: 0 }), /local point changed/)
  const changedOriginal = associationFixture(); changedOriginal.originalAnchor.description = 'A different physical source feature'
  assert.throws(() => reproveCurrentNativeFitAssociationPrimitives({ ...changedOriginal, primitiveIndex: 0 }), /original source anchor digest/)
})

function definitionFixture() {
  const fixture = associationFixture()
  const sourceBinding = { videoId: '4mBuyixt22U', sourceSha256: 'a'.repeat(64), originalViewId: 'main', frameIndex: 0,
    decodedTimestampTicks: 0, timeBase: '1/24000', sourceImage: { pixelFormat: 'gray8', sha256Gray8: 'b'.repeat(64) } }
  const originalLandmark = { anchorId: 'fixture-top', status: 'observed', role: 'check', pixel: [123, 456], uncertaintyPx: 3.5,
    method: 'Explicit fixture observation; no real video acceptance' }
  return { ...fixture, originalObservations: { source: { videoId: '4mBuyixt22U' }, anchors: [fixture.originalAnchor] },
    currentAnchors: [fixture.anchor], poseOracle: { inventory: { drawables: [fixture.original] } },
    source: { sourceBinding, landmarks: [originalLandmark] }, selections: [control('top')] }
}

test('foreign video and explicit physical cap semantic mismatch remain unavailable with immutable source facts', () => {
  for (const mutate of [fixture => { fixture.source.sourceBinding.videoId = 'foreign-video' },
    fixture => { fixture.selections[0].corner = 'bottom' },
    fixture => { fixture.originalAnchor.description = 'Top of unrelated upper rocker part' }]) {
    const fixture = definitionFixture(); mutate(fixture)
    const originalFacts = structuredClone({ source: fixture.source, anchors: fixture.originalObservations.anchors, currentAnchors: fixture.currentAnchors })
    const [definition] = createCurrentNativeRockerCapFitDefinitions(fixture)
    assert.equal(definition.witness, null)
    assert.match(definition.unavailableReason, /4mBuyixt22U source binding|physical cap description/)
    assert.equal(definition.correspondence.state, 'chosen-unmeasured')
    assert.deepEqual(definition.originalLandmark, originalFacts.source.landmarks[0])
    assert.deepEqual(definition.sourceBinding, originalFacts.source.sourceBinding)
    assert.deepEqual({ source: fixture.source, anchors: fixture.originalObservations.anchors, currentAnchors: fixture.currentAnchors }, originalFacts)
  }
})

test('fixture-derived byte seals never pass the current60a definition admission guard', () => {
  const fixture = definitionFixture(), [definition] = createCurrentNativeRockerCapFitDefinitions(fixture)
  assert.equal(definition.witness, null)
  assert.match(definition.unavailableReason, /protected actual current60a raw model/)
  assert.notEqual(fixture.nativeModel.rawSHA256, CURRENT_NATIVE_RAW_SHA256)
})
