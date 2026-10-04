#!/usr/bin/env node
// Parent-only smoke: every positive uses the actual approved raw GLB. This is
// native geometry/source-binding evidence, not a rendered/source acceptance run.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { parseArgs } from 'node:util'
import { parseNativeRawGLB } from './native-model-byte-proof.mjs'
import { freezeIntroSilverHeadWitnesses, nativeHorizontalSections, transformWitnessPoint,
  verifyFrozenFeatureSupport, verifyNativeMeshFeatureWitness, verifyPosedNativeFeaturePoint } from './native-mesh-feature-witness.mjs'

const { values } = parseArgs({ options: {
  'raw-glb': { type: 'string', default: fileURLToPath(new URL('../.vite/model-source/60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c.glb', import.meta.url)) },
  'source-inspection': { type: 'string', default: fileURLToPath(new URL('../.vite/verification-output/v39-source-feature-20261003/intro809-source-inspection.json', import.meta.url)) },
  output: { type: 'string' },
} })
const fixture = JSON.parse(await readFile(new URL('./fixtures/intro-silver-head-witness-v39.json', import.meta.url), 'utf8'))
const rawBytes = await readFile(values['raw-glb'])
const rawSHA256 = createHash('sha256').update(rawBytes).digest('hex')
assert.equal(rawSHA256, fixture.rawSHA256, 'positive must use immutable actual approved raw bytes')
const model = { ...parseNativeRawGLB(rawBytes), rawSHA256 }
const sourceInspection = JSON.parse(await readFile(values['source-inspection'], 'utf8'))
for (const [key, expected] of Object.entries(fixture.sourceInspection)) assert.deepEqual(sourceInspection[key], expected, `independent original source ${key}`)
const frozen = freezeIntroSilverHeadWitnesses(model, sourceInspection)
const positives = [], refusals = []
const rawExpected = fixture.actualRawExpectation
function refuse(id, action) {
  let reason
  try { action() } catch (error) { reason = error.message }
  assert.ok(reason, `${id} must independently refuse`)
  refusals.push({ id, reason })
}
function mutateModelPrimitive(path, change) {
  const primitives = new Map(model.primitives), primitive = { ...primitives.get(path) }
  change(primitive)
  primitives.set(path, primitive)
  return { ...model, primitives }
}
// Independently interpolate the authentic raw triangle AFTER posing each vertex.
// This is distinct from the helper's interpolate-local-then-transform path.
function posedRawTrianglePoint(primitive, witness) {
  const matrix = primitive.restMatrixF64, result = [0, 0, 0]
  for (let corner = 0; corner < 3; corner++) {
    const offset = primitive.index[witness.triangleIndex * 3 + corner] * 3
    const x = primitive.positions[offset], y = primitive.positions[offset + 1], z = primitive.positions[offset + 2]
    for (let axis = 0; axis < 3; axis++) result[axis] += witness.barycentric[corner] * (matrix[axis] * x + matrix[4 + axis] * y + matrix[8 + axis] * z + matrix[12 + axis])
  }
  return result
}
for (const [i, row] of frozen.entries()) {
  const expectedInstance = fixture.actualInstances[i], primitive = model.primitives.get(row.witness.partPath)
  const feature = verifyNativeMeshFeatureWitness(row.witness, primitive)
  assert.equal(row.witness.anchorId, expectedInstance.anchorId)
  assert.deepEqual([primitive.nodeIndex, primitive.meshIndex, primitive.primitiveIndex], [expectedInstance.rawNodeIndex, expectedInstance.rawMeshIndex, expectedInstance.primitiveIndex])
  assert.equal(primitive.positions.length / 3, rawExpected.vertexCount)
  assert.equal(primitive.index.length, rawExpected.indexCount)
  assert.equal(row.witness.kind, 'triangle-point')
  assert.equal(row.witness.triangleIndex, rawExpected.triangleIndex)
  assert.deepEqual(row.witness.barycentric, rawExpected.barycentric)
  assert.deepEqual(row.geometryEvidence.floorTriangles[0].vertexIndices, rawExpected.vertexIndices)
  assert.deepEqual(row.geometryEvidence.floorTriangles[0].localPointsMetres, rawExpected.floorTrianglePointsMetres)
  assert.equal(feature.localPointMetres[1], rawExpected.floorYMetres)
  assert.equal(feature.pointIsStoredVertex, false)
  assert.equal(feature.pointIsSurfacePoint, true)
  assert.equal(row.geometryEvidence.headMaximumYMetres, rawExpected.actualMaximumYMetres)
  assert.deepEqual(Array.from(primitive.restMatrixF64.subarray(12, 15)), expectedInstance.translationMetres)
  assert.equal(row.sourceBinding.role, 'fit')
  assert.equal(row.sourceBinding.uncertaintyPx, 4)
  const sections = nativeHorizontalSections(primitive, rawExpected.sectionYMetres)
  assert.equal(sections.cycles.length, 1)
  assert.equal(sections.cycles[0].endpoints.length, rawExpected.closedSectionEdgePointCount)
  const radii = sections.cycles[0].endpoints.map(endpoint => Math.hypot(endpoint.localMetres[0], endpoint.localMetres[2]))
  assert.ok(Math.abs(Math.min(...radii) - rawExpected.sectionRadiusBoundsMetres[0]) < 1e-16)
  assert.ok(Math.abs(Math.max(...radii) - rawExpected.sectionRadiusBoundsMetres[1]) < 1e-16)
  for (const endpoint of sections.cycles[0].endpoints) {
    assert.equal(endpoint.supportingRawEdges.length, 2, 'closed section endpoint must retain both authentic incident triangle edges')
    const t = endpoint.parameterFromFirstVertex
    assert.ok(t > 0 && t < 1, 'section endpoint is inside an actual raw edge')
    for (const edge of endpoint.supportingRawEdges) {
      const actualTriangle = Array.from(primitive.index.subarray(edge.triangleIndex * 3, edge.triangleIndex * 3 + 3))
      assert.ok(edge.vertexIndices.every(index => actualTriangle.includes(index)), 'support edge must belong to its declared actual raw triangle')
      const [a, b] = edge.vertexIndices
      const recomputed = [0, 1, 2].map(axis => primitive.positions[a * 3 + axis] + t * (primitive.positions[b * 3 + axis] - primitive.positions[a * 3 + axis]))
      assert.equal(recomputed[0], endpoint.localMetres[0])
      assert.equal(recomputed[2], endpoint.localMetres[2])
      assert.ok(Math.abs(recomputed[1] - endpoint.localMetres[1]) <= Number.EPSILON * rawExpected.floorYMetres * 2, 'canonical plane normalization must stay within scalar-rounding error')
    }
  }
  const cap = row.geometryEvidence.topCap
  const capTriangles = new Set(cap.capTriangleIndices)
  for (const triangleIndex of cap.capTriangleIndices) {
    const vertices = Array.from(primitive.index.subarray(triangleIndex * 3, triangleIndex * 3 + 3))
    const ys = vertices.map(vertex => primitive.positions[vertex * 3 + 1])
    assert.ok(Math.min(...ys) >= rawExpected.floorYMetres && Math.max(...ys) > rawExpected.floorYMetres, 'cap support must be actual upper-head facets, not hidden axis-section geometry')
    assert.ok(vertices.reduce((sum, vertex) => sum + primitive.normals[vertex * 3 + 1], 0) > 0, 'frozen cap facets must consume original positive-Y native normals')
  }
  for (const edge of cap.boundaryEdges) {
    assert.ok(capTriangles.has(edge.triangleIndex))
    const vertices = Array.from(primitive.index.subarray(edge.triangleIndex * 3, edge.triangleIndex * 3 + 3))
    assert.ok(edge.vertexIndices.every(vertex => vertices.includes(vertex)), 'cap boundary must be an authentic indexed edge, not an invented silhouette')
    assert.deepEqual(edge.localPointsMetres, edge.vertexIndices.map(vertex => Array.from(primitive.positions.subarray(vertex * 3, vertex * 3 + 3))))
  }
  for (const support of [...cap.surfaceSupportPoints, ...row.geometryEvidence.floorSurfaceSupports]) {
    if (support.vertexIndex !== null && support.vertexIndex !== undefined) {
      assert.deepEqual(support.localPointMetres, Array.from(primitive.positions.subarray(support.vertexIndex * 3, support.vertexIndex * 3 + 3)))
      for (const triangleIndex of support.supportTriangleIndices) {
        const vertices = Array.from(primitive.index.subarray(triangleIndex * 3, triangleIndex * 3 + 3))
        assert.ok(vertices.some(vertex => support.localPointMetres.every((value, axis) => value === primitive.positions[vertex * 3 + axis])), 'coincident seam support must retain actual triangle-coordinate membership')
      }
    } else {
      const supportWitness = { ...row.witness, triangleIndex: support.triangleIndex, barycentric: support.barycentric }
      const actual = verifyNativeMeshFeatureWitness(supportWitness, primitive)
      assert.ok(actual.pointIsSurfacePoint, 'cap/slot centroid must be a genuine indexed triangle point')
      assert.ok(Math.hypot(...actual.localPointMetres.map((value, axis) => value - support.localPointMetres[axis])) <= fixture.positionBoundMetres)
    }
  }
  assert.deepEqual(row.geometryEvidence.floorSurfaceSupports.map(support => support.triangleIndex), [38163, 38164])
  assert.ok(Math.hypot(...row.geometryEvidence.floorSurfaceSupports[0].localPointMetres.map((value, axis) => value - row.geometryEvidence.floorSurfaceSupports[1].localPointMetres[axis])) > fixture.positionBoundMetres, 'slot supports must be two distinct actual surface points')
  const independentWorldPoint = posedRawTrianglePoint(primitive, row.witness)
  const posed = verifyPosedNativeFeaturePoint(row.witness, primitive, primitive.restMatrixF64, independentWorldPoint, fixture.positionBoundMetres)
  positives.push({ anchorId: row.witness.anchorId, kind: row.witness.kind, primitiveSHA256: primitive.rawPrimitiveSHA256,
    rawAncestry: row.geometryEvidence.rawAncestry, localPointMetres: feature.localPointMetres,
    rawRestWorldPointMetres: posed.worldPointMetres, posedArithmeticErrorMetres: posed.errorMetres,
    floorTriangleIndex: row.witness.triangleIndex, sectionEdgePointCount: sections.cycles[0].endpoints.length,
    sectionCircle: row.geometryEvidence.sectionCircle, sourceBinding: row.sourceBinding })
  positives.at(-1).authenticUpperCapTriangleCount = cap.capTriangleIndices.length
  positives.at(-1).authenticCapBoundaryEdgeCount = cap.boundaryEdges.length
  positives.at(-1).authenticUpperCapSupportPointCount = cap.surfaceSupportPoints.length
  positives.at(-1).authenticSlotFloorSupportPoints = row.geometryEvidence.floorSurfaceSupports
  const wrongWorldNominal = transformWitnessPoint(primitive.restMatrixF64, [0, rawExpected.invalidNominalYMetres, 0])
  const wrongWorldCapEnvelope = transformWitnessPoint(primitive.restMatrixF64, [0, rawExpected.actualMaximumYMetres, 0])
  refuse(`${row.witness.anchorId}:nominal-wrong-Y`, () => verifyPosedNativeFeaturePoint(row.witness, primitive, primitive.restMatrixF64, wrongWorldNominal, fixture.positionBoundMetres))
  refuse(`${row.witness.anchorId}:cap-envelope-is-not-slot-floor`, () => verifyPosedNativeFeaturePoint(row.witness, primitive, primitive.restMatrixF64, wrongWorldCapEnvelope, fixture.positionBoundMetres))
  const movedWorld = [...independentWorldPoint]; movedWorld[0] += fixture.positionBoundMetres * 4
  refuse(`${row.witness.anchorId}:moved-posed-marker`, () => verifyPosedNativeFeaturePoint(row.witness, primitive, primitive.restMatrixF64, movedWorld, fixture.positionBoundMetres))
}
assert.equal(new Set(positives.map(row => row.rawAncestry.rawNodeIndex)).size, 4, 'native topology must preserve four actual instances')
assert.equal(new Set(positives.map(row => JSON.stringify(row.rawRestWorldPointMetres))).size, 4, 'native transformed support must remain distinct')
const first = frozen[0], firstPath = first.witness.partPath, firstPrimitive = model.primitives.get(firstPath)
refuse('wrong-primitive-instance', () => verifyNativeMeshFeatureWitness(first.witness, model.primitives.get(frozen[1].witness.partPath)))
refuse('wrong-primitive-seal', () => verifyNativeMeshFeatureWitness({ ...first.witness, rawPrimitiveSHA256: '0'.repeat(64) }, firstPrimitive))
refuse('camera-derived-alias-extra-key', () => verifyNativeMeshFeatureWitness({ ...first.witness, cameraRayHitLocalMetres: [0, rawExpected.floorYMetres, 0] }, firstPrimitive))
refuse('weakened-native-position-bound', () => verifyPosedNativeFeaturePoint(first.witness, firstPrimitive, firstPrimitive.restMatrixF64,
  transformWitnessPoint(firstPrimitive.restMatrixF64, [0, rawExpected.invalidNominalYMetres, 0]), 0.01))
refuse('arbitrary-nearest-vertex-alias', () => verifyFrozenFeatureSupport({ ...first.witness, kind: 'mesh-vertex', vertexIndex: 58580 }, first.witness))
refuse('wrong-raw-primitive-ancestry', () => freezeIntroSilverHeadWitnesses(mutateModelPrimitive(firstPath, primitive => { primitive.nodeIndex = 299 }), sourceInspection))
refuse('moved-native-support-point', () => freezeIntroSilverHeadWitnesses(mutateModelPrimitive(firstPath, primitive => {
  primitive.positions = new Float32Array(primitive.positions)
  primitive.positions[58580 * 3 + 1] += 1e-5
}), sourceInspection))
refuse('wrong-native-index-membership', () => freezeIntroSilverHeadWitnesses(mutateModelPrimitive(firstPath, primitive => {
  primitive.index = new Uint32Array(primitive.index)
  primitive.index[rawExpected.triangleIndex * 3] = 58579
}), sourceInspection))
refuse('wrong-original-raw-SHA', () => freezeIntroSilverHeadWitnesses({ ...model, rawSHA256: '0'.repeat(64) }, sourceInspection))
const supportMoved = structuredClone(first.geometryEvidence)
supportMoved.rimEndpoints[0].localMetres[0] += 1e-5
refuse('moved-declared-rim-support-point', () => verifyFrozenFeatureSupport(supportMoved, first.geometryEvidence))
const supportWrongEdge = structuredClone(first.geometryEvidence)
supportWrongEdge.rimEndpoints[0].supportingRawEdges[0].vertexIndices[0] = 0
refuse('wrong-declared-rim-raw-index-membership', () => verifyFrozenFeatureSupport(supportWrongEdge, first.geometryEvidence))
const movedVisibleCap = structuredClone(first.geometryEvidence)
movedVisibleCap.topCap.surfaceSupportPoints[0].localPointMetres[0] += 1e-5
refuse('moved-actual-cap-surface-support-point', () => verifyFrozenFeatureSupport(movedVisibleCap, first.geometryEvidence))
const supportWrongTriangle = structuredClone(first.geometryEvidence)
supportWrongTriangle.floorTriangles[0].triangleIndex++
refuse('contradictory-slot-support-triangle', () => verifyFrozenFeatureSupport(supportWrongTriangle, first.geometryEvidence))
const changedBarycentric = { ...first.witness, barycentric: [0.25, 0.5, 0.25] }
refuse('different-valid-triangle-point-is-not-frozen-centre', () => verifyFrozenFeatureSupport(changedBarycentric, first.witness))
const sectionWitness = {
  anchorId: first.witness.anchorId, partPath: firstPath,
  rawPrimitiveSHA256: first.witness.rawPrimitiveSHA256,
  sourceFeatureEvidenceSHA256: first.witness.sourceFeatureEvidenceSHA256,
  kind: 'section-center', rimTriangleIndices: first.geometryEvidence.rimTriangleIndices,
  sectionPlaneLocal: first.geometryEvidence.sectionPlaneLocal,
  construction: 'circle-center-from-native-section-v1', secondSectionPlaneLocal: null,
}
const actualSectionFeature = verifyNativeMeshFeatureWitness(sectionWitness, firstPrimitive)
assert.equal(actualSectionFeature.pointIsSurfacePoint, false, 'centre of the solid section is not its rendered rim')
assert.equal(actualSectionFeature.pointIsStoredVertex, false)
assert.deepEqual(actualSectionFeature.supportTriangleIndices, first.geometryEvidence.rimTriangleIndices)
refuse('incomplete-native-section-support', () => verifyNativeMeshFeatureWitness({
  ...sectionWitness, rimTriangleIndices: sectionWitness.rimTriangleIndices.slice(1),
}, firstPrimitive))
refuse('nominal-plane-outside-actual-head', () => verifyNativeMeshFeatureWitness({
  ...sectionWitness, sectionPlaneLocal: [0, 1, 0, -rawExpected.invalidNominalYMetres],
}, firstPrimitive))
refuse('virtual-section-centre-cannot-replace-floor-centre', () => verifyFrozenFeatureSupport(sectionWitness, first.witness))
for (const [id, mutate] of [
  ['FIT-promoted-to-CHECK', source => { source.headCrops[0].role = 'check' }],
  ['moved-original-source-pixel', source => { source.headCrops[0].pixel[0] += 1 }],
  ['weakened-original-source-uncertainty', source => { source.headCrops[0].uncertaintyPx = 8 }],
  ['wrong-original-BGR8-image', source => { source.sha256Bgr8 = '0'.repeat(64) }],
  ['wrong-original-PTS', source => { source.decodedTimestampTicks++ }],
]) {
  const source = structuredClone(sourceInspection); mutate(source)
  refuse(id, () => freezeIntroSilverHeadWitnesses(model, source))
}
const report = { kind: 'actual-raw-v39-intro809-slot-floor-witness-smoke', rawSHA256,
  sourceInspectionSHA256: createHash('sha256').update(await readFile(values['source-inspection'])).digest('hex'),
  positives, refusals, sourceQualification: false, cameraQualification: false, GPUQualification: false,
  firstSurfaceQualification: false, scope: fixture.scope }
if (values.output) await writeFile(values.output, JSON.stringify(report, null, 2) + '\n')
console.log(JSON.stringify({ kind: report.kind, rawSHA256, actualPositiveCount: positives.length,
  independentRefusalCount: refusals.length, firstSurfaceQualification: false, output: values.output ?? null,
  floorYMetres: rawExpected.floorYMetres, actualMaximumYMetres: rawExpected.actualMaximumYMetres,
  sourceRoles: positives.map(row => row.sourceBinding.role) }, null, 2))
