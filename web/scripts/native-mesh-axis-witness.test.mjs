import test from 'node:test'
import assert from 'node:assert/strict'
import { jsonDigest, sha256 } from './native-model-byte-proof.mjs'
import {
  nativeAxisSections, nativeHorizontalSections, nativeSectionCircle,
  verifyNativeMeshFeatureWitness, verifyPosedNativeFeaturePoint,
} from './native-mesh-feature-witness.mjs'

// Small controlled Float32/u32 fixtures, not the CURRENT native inventory or
// source evidence. Geometry is authored in each native XYZ axis, without a pose.
const CENTRE = [0.015625, -0.03125, 0.0625]
const RADIUS = 0.00390625
const LEVELS = [-0.125, 0, 0.125]
const OPEN_COORDINATES = [-0.0625, 0.0625]
const POSITION_BOUND = 1e-7
const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

function sealPrimitive(path, positions, index) {
  return {
    path, positions, index,
    rawPrimitiveSHA256: jsonDigest({
      fixture: 'controlled-indexed-native-axis-cylinder', path,
      positionFloat32SHA256: sha256(new Uint8Array(positions.buffer)),
      indexUint32SHA256: sha256(new Uint8Array(index.buffer)),
    }),
  }
}

function cylinder(axisIndex, { collinear = false } = {}) {
  const tangentAxes = [0, 1, 2].filter(axis => axis !== axisIndex)
  const ring = collinear
    ? [[-1, 0], [-0.5, 0], [0.5, 0], [1, 0]]
    : Array.from({ length: 8 }, (_, k) => {
      // Opposite points are exactly symmetric after Float32 representation.
      const angle = (k % 4) * Math.PI / 4, sign = k < 4 ? 1 : -1
      return [sign * Math.cos(angle), sign * Math.sin(angle)]
    })
  const vertices = [], indices = [], stride = ring.length + 1
  for (const coordinate of LEVELS) {
    const points = ring.map(([u, v]) => {
      const point = [...CENTRE]
      point[axisIndex] = coordinate
      point[tangentAxes[0]] += RADIUS * u
      point[tangentAxes[1]] += RADIUS * v
      return point
    })
    vertices.push(...points, [...points[0]]) // Exact duplicated seam, not a new control.
  }
  for (let band = 0; band < LEVELS.length - 1; band++) {
    for (let k = 0; k < ring.length; k++) {
      const a = band * stride + k, b = a + 1, d = a + stride, c = b + stride
      indices.push(a, b, c, a, c, d)
    }
  }
  const sideTriangleCount = indices.length / 3
  // Close both caps with rim-only fans: the analytic axis centre is not stored.
  for (const base of [0, (LEVELS.length - 1) * stride]) {
    for (let k = 1; k < ring.length - 1; k++) indices.push(base, base + k, base + k + 1)
  }
  const primitive = sealPrimitive(`fixture/native-${'XYZ'[axisIndex]}-cylinder`, new Float32Array(vertices.flat()), new Uint32Array(indices))
  return { primitive, sideTriangleCount, tangentAxes, ringSize: ring.length }
}

function plane(axisIndex, coordinate) {
  return [...[0, 1, 2].map(axis => Number(axis === axisIndex)), -coordinate]
}

function axisWitness(primitive, axisIndex) {
  const cycles = OPEN_COORDINATES.map(coordinate => {
    const section = nativeAxisSections(primitive, axisIndex, coordinate)
    assert.equal(section.cycles.length, 1, 'each raw section must determine one closed rim')
    return section.cycles[0]
  })
  const witness = {
    anchorId: `controlled-${'XYZ'[axisIndex]}-axis`, partPath: primitive.path,
    rawPrimitiveSHA256: primitive.rawPrimitiveSHA256,
    sourceFeatureEvidenceSHA256: jsonDigest({ fixture: primitive.path, feature: 'analytic-cylinder-axis' }),
    kind: 'geometric-axis', construction: 'axis-from-two-native-sections-v1',
    sectionPlaneLocal: plane(axisIndex, OPEN_COORDINATES[0]),
    secondSectionPlaneLocal: plane(axisIndex, OPEN_COORDINATES[1]),
    rimTriangleIndices: [...new Set(cycles.flatMap(cycle => cycle.triangleIndices))].sort((a, b) => a - b),
    axisPointCoordinate: LEVELS.at(-1),
  }
  return { witness, cycles }
}

function nearPoint(actual, expected) {
  assert.ok(Math.hypot(...actual.map((value, axis) => value - expected[axis])) <= POSITION_BOUND,
    `point ${actual} must remain within ${POSITION_BOUND} m of analytic centre ${expected}`)
}

for (const axisIndex of [0, 1, 2]) {
  test(`${'XYZ'[axisIndex]} raw sections construct a front-cap axis point without surface authority`, () => {
    const { primitive, sideTriangleCount, tangentAxes, ringSize } = cylinder(axisIndex)
    const { witness, cycles } = axisWitness(primitive, axisIndex)
    const expected = [...CENTRE]; expected[axisIndex] = LEVELS.at(-1)
    const feature = verifyNativeMeshFeatureWitness(witness, primitive)
    nearPoint(feature.localPointMetres, expected)
    assert.equal(feature.localPointMetres[axisIndex], LEVELS.at(-1))
    assert.equal(feature.pointIsStoredVertex, false)
    assert.equal(feature.pointIsSurfacePoint, false, 'virtual axis centre cannot certify opaque first-surface support')
    assert.deepEqual(feature.supportTriangleIndices, Array.from({ length: sideTriangleCount }, (_, i) => i))
    assert.deepEqual(feature.supportPointsLocalMetres, cycles.flatMap(cycle => cycle.endpoints.map(endpoint => endpoint.localMetres)))
    for (const [i, cycle] of cycles.entries()) {
      const circle = nativeSectionCircle(cycle), analytic = [...CENTRE]
      analytic[axisIndex] = OPEN_COORDINATES[i]
      nearPoint(circle.centreLocalMetres, analytic)
      assert.equal(cycle.endpoints.length, 2 * ringSize, 'seam duplicates must not create extra geometric intersections')
      assert.equal(new Set(cycle.endpoints.map(endpoint => endpoint.key)).size, 2 * ringSize)
      for (const endpoint of cycle.endpoints) {
        assert.equal(endpoint.localMetres[axisIndex], OPEN_COORDINATES[i])
        assert.ok(endpoint.parameterFromFirstVertex > 0 && endpoint.parameterFromFirstVertex < 1)
        for (const edge of endpoint.supportingRawEdges) {
          const [a, b] = edge.vertexIndices.map(index => Array.from(primitive.positions.subarray(index * 3, index * 3 + 3)))
          nearPoint(endpoint.localMetres, a.map((value, axis) => value + endpoint.parameterFromFirstVertex * (b[axis] - value)))
        }
      }
      // The centre is interior to the rim, not one of its duplicated vertices.
      assert.ok(cycle.endpoints.every(endpoint => Math.hypot(...tangentAxes.map(axis => endpoint.localMetres[axis] - circle.centreLocalMetres[axis])) > POSITION_BOUND))
    }
    const posed = verifyPosedNativeFeaturePoint(witness, primitive, IDENTITY, expected, POSITION_BOUND)
    assert.ok(posed.errorMetres <= POSITION_BOUND)
    assert.equal(posed.feature.pointIsSurfacePoint, false)
    const displaced = [...expected]; displaced[tangentAxes[0]] += 2 * POSITION_BOUND
    assert.throws(() => verifyPosedNativeFeaturePoint(witness, primitive, IDENTITY, displaced, POSITION_BOUND), /marker disagrees/)
    assert.throws(() => verifyPosedNativeFeaturePoint(witness, primitive, IDENTITY, expected, 2 * POSITION_BOUND), /must not relax/)
  })
}

test('legacy horizontal sections and axes retain their analytic native-Y coordinates', () => {
  const { primitive } = cylinder(1)
  for (const coordinate of OPEN_COORDINATES) {
    const horizontal = nativeHorizontalSections(primitive, coordinate)
    const analytic = [...CENTRE]; analytic[1] = coordinate
    nearPoint(nativeSectionCircle(horizontal.cycles[0]).centreLocalMetres, analytic)
    const sectionWitness = {
      anchorId: 'legacy-native-Y-circle', partPath: primitive.path,
      rawPrimitiveSHA256: primitive.rawPrimitiveSHA256,
      sourceFeatureEvidenceSHA256: jsonDigest({ fixture: primitive.path, feature: 'analytic-Y-section' }),
      kind: 'section-center', construction: 'circle-center-from-native-section-v1',
      sectionPlaneLocal: plane(1, coordinate), secondSectionPlaneLocal: null,
      rimTriangleIndices: horizontal.cycles[0].triangleIndices,
    }
    const section = verifyNativeMeshFeatureWitness(sectionWitness, primitive)
    nearPoint(section.localPointMetres, analytic)
    assert.equal(section.pointIsSurfacePoint, false)
  }
  const legacy = axisWitness(primitive, 1).witness
  delete legacy.axisPointCoordinate
  const expected = [...CENTRE]; expected[1] = OPEN_COORDINATES[0]
  nearPoint(verifyNativeMeshFeatureWitness(legacy, primitive).localPointMetres, expected)
})

test('axis construction refuses stored-vertex planes, nonparallel planes and repeated planes', () => {
  const { primitive } = cylinder(0), { witness } = axisWitness(primitive, 0)
  assert.throws(() => nativeAxisSections(primitive, 0, LEVELS[1]), /passes through a stored vertex/)
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, sectionPlaneLocal: plane(0, LEVELS[1]) }, primitive), /passes through a stored vertex/)
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, secondSectionPlaneLocal: plane(2, OPEN_COORDINATES[1]) }, primitive), /distinct parallel/)
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, secondSectionPlaneLocal: [...witness.sectionPlaneLocal] }, primitive), /distinct parallel/)
})

test('two-section support must include both complete rims and no unrelated cap triangle', () => {
  const { primitive, sideTriangleCount } = cylinder(2), { witness, cycles } = axisWitness(primitive, 2)
  for (const omitted of [cycles[0].triangleIndices[0], cycles[1].triangleIndices[0]]) {
    assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, rimTriangleIndices: witness.rimTriangleIndices.filter(index => index !== omitted) }, primitive), /complete cycle/)
  }
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, rimTriangleIndices: [...witness.rimTriangleIndices, sideTriangleCount] }, primitive), /complete two-section support/)
})

test('open raw rims and degenerate triangle intersections cannot construct axes', () => {
  const { primitive } = cylinder(1), { witness } = axisWitness(primitive, 1)
  const open = sealPrimitive(primitive.path, primitive.positions, primitive.index.slice(3))
  assert.throws(() => nativeAxisSections(open, 1, OPEN_COORDINATES[0]), /closed two-valent loop/)
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, rawPrimitiveSHA256: open.rawPrimitiveSHA256 }, open), /closed two-valent loop/)
  const degenerate = sealPrimitive(primitive.path, primitive.positions, new Uint32Array([...primitive.index, 0, 0, 9]))
  assert.throws(() => nativeAxisSections(degenerate, 1, OPEN_COORDINATES[0]), /degenerate triangle intersection/)
})

test('a closed collinear raw rim has no uniquely determined circle or axis', () => {
  const { primitive } = cylinder(0, { collinear: true }), { witness, cycles } = axisWitness(primitive, 0)
  assert.throws(() => nativeSectionCircle(cycles[0]), /no uniquely determined circle centre/)
  assert.throws(() => verifyNativeMeshFeatureWitness(witness, primitive), /no uniquely determined circle centre/)
})

test('axis points may reach raw axial boundaries but cannot leave them', () => {
  const { primitive } = cylinder(2), { witness } = axisWitness(primitive, 2)
  for (const coordinate of [LEVELS[0], LEVELS.at(-1)]) {
    const expected = [...CENTRE]; expected[2] = coordinate
    nearPoint(verifyNativeMeshFeatureWitness({ ...witness, axisPointCoordinate: coordinate }, primitive).localPointMetres, expected)
  }
  for (const coordinate of [LEVELS[0] - POSITION_BOUND, LEVELS.at(-1) + POSITION_BOUND]) {
    assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, axisPointCoordinate: coordinate }, primitive), /actual raw axial extent/)
  }
  assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, axisPointCoordinate: NaN }, primitive), /coordinate is nonfinite/)
})

test('axis witnesses refuse malformed or noncanonical native section planes', () => {
  const { primitive } = cylinder(0), { witness } = axisWitness(primitive, 0)
  for (const malformed of [[1, 0, 0], [1, 0, 0, NaN]]) {
    assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, sectionPlaneLocal: malformed }, primitive), /section plane must contain 4 finite numbers/)
  }
  for (const malformed of [[2, 0, 0, 0.0625], [-1, 0, 0, 0.0625], [1, 1, 0, 0.0625], [0, 0, 0, 0.0625]]) {
    assert.throws(() => verifyNativeMeshFeatureWitness({ ...witness, secondSectionPlaneLocal: malformed }, primitive), /normalized native Cartesian-axis sections/)
  }
})
