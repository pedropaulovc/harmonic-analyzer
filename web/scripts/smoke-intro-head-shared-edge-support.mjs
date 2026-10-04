#!/usr/bin/env node
// Parent-only regression: genuine original raw shared-edge incidence, not a
// camera-picked alias, synthetic primitive, broader same-body hit or new source CHECK.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { parseNativeRawGLB } from './native-model-byte-proof.mjs'
import { freezeIntroSilverHeadWitnesses, verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'

const rawPath = fileURLToPath(new URL('../.vite/model-source/60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c.glb', import.meta.url))
const sourcePath = fileURLToPath(new URL('../.vite/verification-output/v39-source-feature-20261003/intro809-source-inspection.json', import.meta.url))
const raw = await readFile(rawPath), rawSHA256 = createHash('sha256').update(raw).digest('hex')
assert.equal(rawSHA256, '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c')
const model = { ...parseNativeRawGLB(raw), rawSHA256 }
const source = JSON.parse(await readFile(sourcePath, 'utf8'))
const frozen = freezeIntroSilverHeadWitnesses(model, source)
const records = []
for (const row of frozen) {
  const primitive = model.primitives.get(row.witness.partPath), feature = verifyNativeMeshFeatureWitness(row.witness, primitive)
  const primary = Array.from(primitive.index.subarray(38163 * 3, 38163 * 3 + 3))
  const neighbour = Array.from(primitive.index.subarray(38164 * 3, 38164 * 3 + 3))
  const shared = primary.filter(vertex => neighbour.includes(vertex))
  assert.deepEqual(shared, [58580, 58581], 'positive must use this authentic original shared edge')
  const a = Array.from(primitive.positions.subarray(shared[0] * 3, shared[0] * 3 + 3))
  const b = Array.from(primitive.positions.subarray(shared[1] * 3, shared[1] * 3 + 3))
  assert.ok([...primary, ...neighbour].every(vertex => primitive.positions[vertex * 3 + 1] === 0.002962084487080574), 'support must be authentic coplanar floor, not a head wall')
  const d = b.map((value, axis) => value - a[axis]), p = feature.localPointMetres
  const t = Math.max(0, Math.min(1, d.reduce((sum, value, axis) => sum + value * (p[axis] - a[axis]), 0) / d.reduce((sum, value) => sum + value * value, 0)))
  const edgePoint = a.map((value, axis) => value + t * d[axis])
  const distanceMetres = Math.hypot(...edgePoint.map((value, axis) => value - p[axis]))
  assert.ok(distanceMetres <= 1e-7, 'original centre must be within the unchanged native position footprint of its shared edge')
  assert.equal(row.sourceBinding.role, 'fit')
  assert.equal(row.sourceBinding.uncertaintyPx, 4)
  assert.deepEqual(feature.supportTriangleIndices, [38163, 38164], 'genuine coplanar neighbour38164 must not be falsely refused at the shared-edge marker footprint')
  records.push({ anchorId: row.witness.anchorId, actualRawSharedEdge: shared, pointToRawEdgeDistanceMetres: distanceMetres,
    actualCoplanarSupportTriangleIndices: feature.supportTriangleIndices, sourceRole: row.sourceBinding.role })
}
console.log(JSON.stringify({ kind: 'actual-raw-intro-head-shared-edge-support-regression', records,
  positionBoundMetres: 1e-7, sourceQualification: false, firstSurfaceQualification: false }, null, 2))
