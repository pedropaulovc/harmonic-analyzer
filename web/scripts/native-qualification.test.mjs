import test from 'node:test'
import assert from 'node:assert/strict'
import { BufferGeometry, Float32BufferAttribute, PerspectiveCamera } from 'three'
import { createNativeByteReader, parseNativeRawGLB, sha256 } from './native-model-byte-proof.mjs'
import { transportNormalEnclosure, normalError, createFiniteCurveWitnessProof, originalCurveWitness, nextFloat32, contains } from './native-f32-enclosure.mjs'
import { encloseNativeClipPoint, encloseNativeTriangleDepth, qualifyNativeSourceVisibleLeaves, qualifyOriginalNativeFixedLeaf, rayTriangle, unpackNativeDepth } from './native-qualification.mjs'
import { verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'

function glb({ primitiveCount = 1, badIndex = false, hiddenNonfinite = false } = {}) {
  const positions = new Float32Array([-1, -1, 0, 1, -1, 0, 0, 1, hiddenNonfinite ? NaN : 0]), normals = new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]), indices = new Uint32Array([0, 1, badIndex ? 3 : 2])
  const binary = Buffer.concat([Buffer.from(positions.buffer), Buffer.from(normals.buffer), Buffer.from(indices.buffer)])
  const document = { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ name: 'original', mesh: 0 }], meshes: [{ primitives: Array.from({ length: primitiveCount }, () => ({ mode: 4, attributes: { POSITION: 0, NORMAL: 1 }, indices: 2 })) }], buffers: [{ byteLength: binary.length }], bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: 36 }, { buffer: 0, byteOffset: 36, byteLength: 36 }, { buffer: 0, byteOffset: 72, byteLength: 12 }], accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3' }, { bufferView: 1, componentType: 5126, count: 3, type: 'VEC3' }, { bufferView: 2, componentType: 5125, count: 3, type: 'SCALAR' }] }
  const text = Buffer.from(JSON.stringify(document)), padded = Buffer.alloc(Math.ceil(text.length / 4) * 4, 32); text.copy(padded)
  const bytes = Buffer.alloc(28 + padded.length + binary.length)
  bytes.writeUInt32LE(0x46546c67, 0); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(padded.length, 12); bytes.writeUInt32LE(0x4e4f534a, 16); padded.copy(bytes, 20)
  bytes.writeUInt32LE(binary.length, 20 + padded.length); bytes.writeUInt32LE(0x004e4942, 24 + padded.length); binary.copy(bytes, 28 + padded.length)
  return bytes
}

test('raw multimaterial primitives keep authentic node ancestry and distinct ordered indices', () => {
  const model = parseNativeRawGLB(glb({ primitiveCount: 2 }))
  const first = model.primitives.get('original#primitive:0'), second = model.primitives.get('original#primitive:1')
  assert.deepEqual([first.nodeIndex, second.nodeIndex, first.primitiveIndex, second.primitiveIndex], [0, 0, 0, 1])
  assert.deepEqual([...first.index], [0, 1, 2])
  assert.equal(first.rawPath, second.rawPath)
  assert.notEqual(first.rawPrimitiveSHA256, second.rawPrimitiveSHA256)
  assert.equal(parseNativeRawGLB(glb()).primitives.get('original').rawPath, 'original')
})

test('raw full indices and hidden finite vertices are independently checked', () => {
  assert.throws(() => parseNativeRawGLB(glb({ badIndex: true })), /indices/)
  assert.throws(() => parseNativeRawGLB(glb({ hiddenNonfinite: true })), /Nonfinite raw attribute/)
})

test('CAS hash, exact typed shape and own-object bounds refuse altered or truncated evidence', async () => {
  const actual = new Uint8Array(new Float32Array([1, 2, 3]).buffer), hash = sha256(actual)
  const span = { objectSHA256: hash, objectByteLength: 12, byteOffset: 0, byteLength: 12, scalar: 'f32le', components: 3, count: 1 }
  const reader = createNativeByteReader({ get: () => actual })
  assert.deepEqual([...await reader.numbers(span)], [1, 2, 3])
  await assert.rejects(reader.span({ ...span, byteOffset: 4 }), /Truncated/)
  await assert.rejects(reader.span({ ...span, components: 2 }), /incorrectly shaped/)
  const changed = actual.slice(); changed[0] ^= 1
  await assert.rejects(createNativeByteReader({ get: () => changed }).numbers(span), /hash mismatch/)
})

test('near-clip and vanishing-w geometry cannot turn a broad derivative into a positive depth', () => {
  const p = new PerspectiveCamera(60, 1, 0.005, 100).projectionMatrix.elements
  const visible = encloseNativeClipPoint([0, 0, -0.25], p)
  assert.equal(visible.status, 'inside')
  assert.ok(visible.depth[0] > 0 && visible.depth[1] < 1)
  for (const depth of [1e-7, 1e-12]) {
    const clipped = encloseNativeClipPoint([0, 0, -depth], p)
    assert.equal(clipped.status, 'outside')
    assert.equal(clipped.depth, null)
  }
  for (const depth of [0.005 - 2e-8, 0.005 + 2e-8]) {
    assert.equal(encloseNativeClipPoint([0, 0, -depth], p).status, 'ambiguous')
  }
})

test('fixed-pixel triangle depth includes XY movement rather than substituting the moved hit point', () => {
  const vertices = [[-0.5, -0.5, -0.2], [0.5, -0.5, 0.6], [-0.5, 0.5, -0.2]], pixel = [-0.1, -0.1]
  const original = encloseNativeTriangleDepth(vertices.map(vertex => vertex.map(value => [value, value])), pixel)
  assert.equal(original.status, 'inside')
  assert.ok(original.depth[0] <= 0.56 && original.depth[1] >= 0.56)
  const perturbed = encloseNativeTriangleDepth(vertices.map(vertex => vertex.map((value, axis) => [value, value + (axis === 0 ? 0.02 : 0)])), pixel)
  assert.equal(perturbed.status, 'inside')
  // The whole triangle can translate +.02 in X without changing any vertex Z.
  // At this fixed pixel its depth becomes .552, not the old hit depth .56.
  assert.ok(perturbed.depth[0] <= 0.552 && perturbed.depth[1] >= 0.552)
  assert.ok(0.552 < original.depth[0])
})

test('projected determinant ambiguity and unbounded window depth refuse first-surface admission', () => {
  const point = value => [value, value]
  const tangent = [[point(0), point(0), point(0)], [point(1), point(0), point(0.2)], [point(0), [-0.01, 0.01], point(0.1)]]
  const result = encloseNativeTriangleDepth(tangent, [0.1, 0])
  assert.equal(result.status, 'ambiguous')
  assert.equal(result.depth, null)
  const beyondFar = [[[-1, -1], [-1, -1], [0.95, 1.05]], [[1, 1], [-1, -1], [0.95, 1.05]], [[0, 0], [1, 1], [0.95, 1.05]]]
  assert.equal(encloseNativeTriangleDepth(beyondFar, [0, 0]).status, 'ambiguous')
})

test('authentic ray intersection respects nearest distance, triangle boundary and original side', () => {
  const origin = [0, 0, 0], ray = [0, 0, -1]
  const near = rayTriangle(origin, ray, [-1, -1, -0.25], [1, -1, -0.25], [0, 1, -0.25], 'front')
  const far = rayTriangle(origin, ray, [-1, -1, -1], [1, -1, -1], [0, 1, -1], 'front')
  assert.equal(near.distance, 0.25); assert.equal(far.distance, 1)
  assert.deepEqual(near.barycentric, [0.25, 0.25, 0.5])
  assert.equal(rayTriangle(origin, ray, [-1, -1, -0.25], [0, 1, -0.25], [1, -1, -0.25], 'front'), null)
  assert.equal(rayTriangle(origin, [8, 0, -1], [-1, -1, -0.25], [1, -1, -0.25], [0, 1, -0.25], 'double'), null)
})

test('Three RGBA depth high byte ordering and saturation are preserved', () => {
  assert.equal(unpackNativeDepth(Uint8Array.of(128, 0, 0, 0)), 0.5)
  assert.equal(unpackNativeDepth(Uint8Array.of(0, 1, 0, 0)), 1 / 65536)
  assert.equal(unpackNativeDepth(Uint8Array.of(255, 255, 255, 255)), 1)
})

test('normal enclosure uses raw inputs and observed tangent, never a wrong final normal to widen acceptance', () => {
  const enclosure = transportNormalEnclosure([0, 1, 0], [1, 0, 0], [0, 1, 0])
  const admitted = normalError([-1, 0, 0], [-1, 0, 0], enclosure)
  assert.equal(admitted.inside, true)
  assert.equal(admitted.angularErrorRadians, 0)
  const corrupt = normalError([0, 0, 1], [-1, 0, 0], enclosure)
  assert.equal(corrupt.inside, false)
  assert.equal(corrupt.angularErrorRadians, Math.PI / 2)
  assert.ok(corrupt.euclideanError > 1)
  assert.equal(contains([0, 1], NaN), false)
  assert.ok(nextFloat32(0, -1) < 0 && nextFloat32(0, 1) > 0)
})

test('same-program coil tangent must share the observed centre trig rather than merely be finite', () => {
  const parameters = { radiusM: 0.001, turns: 25, insetM: 0.002, endCorrectionM: 0, restLengthM: 0.05 }
  const original = originalCurveWitness(parameters, 0, 0.31, 0.05)
  assert.equal(original.unwrappedAngleRadians, 0.31 * 25 * 2 * Math.PI)
  const centre = original.centre.map(Math.fround), tangent = original.tangent.map(Math.fround)
  const proof = createFiniteCurveWitnessProof(parameters, 0.05)
  assert.equal(proof.check(0, Math.fround(0.31), centre, tangent, [1, 0, 0]), true)
  assert.equal(proof.check(0, Math.fround(0.31), centre, tangent.map(value => -value), [1, 0, 0]), false)
})

function sourceLeafBoundaryFixture() {
  const model = parseNativeRawGLB(glb({ primitiveCount: 5 })), paths = [...model.primitives.keys()]
  const sourceHash = sha256('independently supplied source-boundary fixture')
  const witnesses = paths.map((path, i) => {
    const primitive = model.primitives.get(path), witness = { anchorId: `source-${i}`, partPath: path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, sourceFeatureEvidenceSHA256: sourceHash, kind: 'triangle-point', triangleIndex: 0, barycentric: [0.25, 0.25, 0.5] }
    const feature = verifyNativeMeshFeatureWitness(witness, primitive)
    const intersection = rayTriangle([0, 0, 1], [0, 0, -1], [-1, -1, 0], [1, -1, 0], [0, 1, 0], 'front')
    // This boundary consumes already Node-derived raster/source support, not a
    // producer pass flag or a substitute native GPU qualification.
    return { ...witness, ...feature, sourceEvidenceQualified: true, nearestHit: { ...intersection, path, triangleIndex: 0 }, footprint: null }
  })
  return { paths, witnesses, pathPixelCounts: Object.fromEntries(paths.map(path => [path, 1])) }
}

test('four native source features cannot promote the other assembly leaf even when it has pixels', () => {
  const fixture = sourceLeafBoundaryFixture(), coverage = { kind: 'landmarks', landmarkIds: fixture.witnesses.slice(0, 4).map(row => row.anchorId) }
  const result = qualifyNativeSourceVisibleLeaves({ paths: fixture.paths, coverage, raster: { pathPixelCounts: fixture.pathPixelCounts, witnesses: fixture.witnesses.slice(0, 4), contours: [] } })
  assert.equal(result.status, 'unmeasured')
  assert.equal(result.leaves[4].status, 'unmeasured')
  assert.ok(result.leaves[4].reasons.some(reason => reason.includes('another leaf/ancestor feature cannot promote it')))
  assert.ok(result.leaves.slice(0, 4).every(leaf => leaf.status === 'qualified'))
})

test('source-visible leaves need their own same-epoch pixels and admitted original support', () => {
  const fixture = sourceLeafBoundaryFixture(), coverage = { kind: 'landmarks', landmarkIds: fixture.witnesses.map(row => row.anchorId) }
  const raster = { pathPixelCounts: fixture.pathPixelCounts, witnesses: fixture.witnesses, contours: [] }
  assert.equal(qualifyNativeSourceVisibleLeaves({ paths: fixture.paths, coverage, raster }).status, 'qualified')
  const missingPixels = qualifyNativeSourceVisibleLeaves({ paths: fixture.paths, coverage, raster: { ...raster, pathPixelCounts: { ...raster.pathPixelCounts, [fixture.paths[4]]: 0 } } })
  assert.equal(missingPixels.status, 'unmeasured')
  assert.ok(missingPixels.leaves[4].reasons.some(reason => reason.includes('explicit original descendant exclusion/fixed declaration')))
  const wrongNearest = qualifyNativeSourceVisibleLeaves({ paths: fixture.paths, coverage, raster: { ...raster, witnesses: fixture.witnesses.map((row, i) => i === 4 ? { ...row, nearestHit: { ...row.nearestHit, path: fixture.paths[0] } } : row) } })
  assert.equal(wrongNearest.status, 'unmeasured')
  const noOriginalSource = qualifyNativeSourceVisibleLeaves({ paths: fixture.paths, coverage, raster: { ...raster, witnesses: fixture.witnesses.map((row, i) => i === 4 ? { ...row, sourceEvidenceQualified: false } : row) } })
  assert.equal(noOriginalSource.status, 'unmeasured')
  assert.equal(qualifyNativeSourceVisibleLeaves({ paths: [fixture.paths[4]], coverage: { kind: 'rigid-native-attachment', attachedToPartPath: 'original' }, rigidAttachmentEligible: true, raster: { ...raster, pathPixelCounts: { [fixture.paths[4]]: 0 } } }).status, 'unmeasured')
})

test('world-fixed admission rejects driven fixed-labelled parts and nonrigid leaves without centre probes', () => {
  const path = 'harmonic-analyzer/fixture/component/mesh', owner = 'harmonic-analyzer/fixture/component', geometry = new BufferGeometry()
  geometry.setAttribute('position', new Float32BufferAttribute([-1, -1, 0, 1, -1, 0, 0, 1, 0], 3))
  const reference = { path, bindingOwnerPath: owner, binding: { pattern: /^harmonic-analyzer\/fixture\/component$/, motion: 'paper-fixed' }, station: null, spring: null, geometry, object: {} }
  const inventory = row => ({ closureSHA256: 'd3f0bcdeaea5924931d82715ace92e483eb123e0685419ccb5940c06c6730413', drawables: [row] })
  const qualify = (row, overrides = []) => qualifyOriginalNativeFixedLeaf(path, { springOracle: null }, inventory(row), overrides)
  assert.equal(qualify(reference).status, 'fixed')
  assert.equal(qualify({ ...reference, binding: null, bindingOwnerPath: null }).status, 'fixed')
  // In the pinned original, magnifier-fixed rotates with summingAngleRad;
  // paper-sprocket is driven separately despite exclusion from generic driven.
  for (const motion of ['magnifier-fixed', 'paper-sprocket', 'unknown']) assert.equal(qualify({ ...reference, binding: { ...reference.binding, motion } }).status, 'unmeasured')
  const spring = qualify({ ...reference, spring: { stock: 'channel', restLengthM: 0.05 } })
  assert.equal(spring.status, 'unmeasured')
  assert.ok(spring.reasons.some(reason => reason.includes('fixed end/centre')))
  geometry.morphAttributes.position = [new Float32BufferAttribute([-1, -1, 0.1, 1, -1, 0.1, 0, 1, 0.1], 3)]
  assert.equal(qualify(reference).status, 'unmeasured')
  geometry.morphAttributes.position = []
  assert.equal(qualify(reference, [{ partPath: owner, worldPositionMetres: [0, 0, 1] }]).status, 'unmeasured')
  assert.equal(qualifyOriginalNativeFixedLeaf(path, { springOracle: null }, { ...inventory(reference), closureSHA256: '0'.repeat(64) }, []).status, 'unmeasured')
  geometry.dispose()
})
