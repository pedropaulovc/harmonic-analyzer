#!/usr/bin/env node
// Parent-only actual-raw boundary regression. Finite raster bytes below are an
// independently Three-raycast CPU reference fixture, NOT captured GPU evidence.
// No whole scene, source-first-surface, source CHECK or production pass is minted.
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { register } from 'node:module'
import { BufferGeometry, Float32BufferAttribute, Matrix4, Mesh, MeshStandardMaterial, PerspectiveCamera, Raycaster, Vector2, Vector3 } from 'three'
import { parseNativeRawGLB, createNativeByteReader, canonicalJson, jsonDigest, sha256 } from './native-model-byte-proof.mjs'
import { createNativeMaterialProof } from './native-material-proof.mjs'
import { freezeIntroSilverHeadWitnesses } from './native-mesh-feature-witness.mjs'

const arguments_ = process.argv.slice(2), before = arguments_.includes('--before')
const outputIndex = arguments_.indexOf('--output'), outputPath = outputIndex < 0 ? null : arguments_[outputIndex + 1]
assert.ok(arguments_.every((value, index) => value === '--before' || value === '--output' || (outputIndex >= 0 && index === outputIndex + 1)), 'Use --before and/or --output PATH')
assert.ok(outputIndex < 0 || outputPath, '--output requires a path')
const beforeDirectory = new URL('../.vite/verification-output/native-shared-edge-before-20261003/', import.meta.url)
const currentConsumer = new URL('./native-qualification.mjs', import.meta.url)
let consumerURL = currentConsumer
if (before) {
  // The retained two modules remain byte-for-byte untouched. Resolve only their
  // other dependencies against the live original script location; this is not a
  // claim that their complete imported closure was frozen (the manifest says so).
  const loader = `export async function resolve(specifier, context, nextResolve) {
    if (context.parentURL?.startsWith(${JSON.stringify(beforeDirectory.href)}) && (specifier.startsWith('./') || specifier.startsWith('../'))) {
      const retained = new URL(specifier, context.parentURL);
      if (retained.href === ${JSON.stringify(new URL('native-mesh-feature-witness.mjs', beforeDirectory).href)}) return nextResolve(retained.href, context);
      return nextResolve(new URL(specifier, ${JSON.stringify(currentConsumer.href)}).href, context);
    }
    return nextResolve(specifier, context);
  }`
  register(`data:text/javascript,${encodeURIComponent(loader)}`, { parentURL: import.meta.url })
  consumerURL = new URL('native-qualification.mjs', beforeDirectory)
  for (const [name, expected] of [['native-mesh-feature-witness.mjs', '02c674a4f5e04fdbded68531e5ad2b403b518469b657a01259bf38afdc94a164'], ['native-qualification.mjs', 'f1aba85482d9e3b0ec7429769d907eeeb12355e338bcd89f616ccd8d01f6e025']]) {
    assert.equal(sha256(await readFile(new URL(name, beforeDirectory))), expected, 'retained failing-before module literal bytes changed')
  }
}
const consumerBytes = await readFile(consumerURL)
// These are the two concrete observed DTO epochs, not inferred source text.
// Passing the real consumer validates the fixture's actual encoding/layout.
const littleRed = !before
const { proveNativeRaster } = await import(consumerURL.href)
const raw = await readFile(new URL('../.vite/model-source/60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c.glb', import.meta.url))
assert.equal(sha256(raw), '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c')
const model = { ...parseNativeRawGLB(raw), rawSHA256: sha256(raw) }
const source = JSON.parse(await readFile(new URL('../.vite/verification-output/v39-source-feature-20261003/intro809-source-inspection.json', import.meta.url), 'utf8'))
const row = freezeIntroSilverHeadWitnesses(model, source)[0], sourceBindingBefore = canonicalJson(row.sourceBinding)
const primitive = model.primitives.get(row.witness.partPath), materialProof = await createNativeMaterialProof({ rawGLBBytes: raw, model })
const expectedMaterial = materialProof.expectedFor(primitive)
assert.equal(expectedMaterial.properties.transparent, false, 'reference fixture requires authentic opaque head material')
assert.equal(expectedMaterial.properties.alphaTest, 0)
assert.equal(expectedMaterial.textures.length, 0, 'reference fixture cannot replace authentic textured/alpha surface')
const descriptor = Object.fromEntries(['schemaVersion', 'type', 'name', 'properties', 'clippingPlanes', 'textures'].map(key => [key, expectedMaterial[key]]))
const objects = new Map(), put = bytes => { const hash = sha256(bytes); objects.set(hash, bytes); return hash }, json = value => put(Buffer.from(canonicalJson(value)))
const reader = createNativeByteReader({ get: async hash => { assert.ok(objects.has(hash)); return objects.get(hash) } })
const matrix = new Matrix4().fromArray(primitive.restMatrixF64)
const geometry = new BufferGeometry(); geometry.setAttribute('position', new Float32BufferAttribute(primitive.positions, 3)); geometry.setIndex(Array.from(primitive.index))
const material = new MeshStandardMaterial({ side: expectedMaterial.properties.side }), mesh = new Mesh(geometry, material)
mesh.matrixAutoUpdate = false; mesh.matrix.copy(matrix); mesh.updateMatrixWorld(true)
const WIDTH = 65, HEIGHT = 65, positionBoundMetres = 1e-7
function packDepth(depth) {
  const value = Math.round(Math.min(1, Math.max(0, depth)) * (2 ** 24 - 1)) / (2 ** 24 - 1)
  if (value <= 0) return new Uint8Array(4)
  if (value >= 1) return new Uint8Array([255, 255, 255, 255])
  const scaled = value * 2 ** 24, integer = Math.floor(scaled)
  return new Uint8Array([Math.floor(integer / 65536), Math.floor(integer / 256) % 256, integer % 256, Math.round((scaled - integer) * 255)])
}
const binding = { sourceVideoId: row.sourceBinding.videoId, sourceSha256: row.sourceBinding.sourceSHA256,
  sourceImage: { pixelFormat: 'bgr8', sha256Bgr8: row.sourceBinding.sha256Bgr8, width: row.sourceBinding.width, height: row.sourceBinding.height, frameIndex: row.sourceBinding.frameIndex },
  decodedFrameIndex: row.sourceBinding.frameIndex, decodedTimestampTicks: String(row.sourceBinding.decodedTimestampTicks), timeBase: row.sourceBinding.timeBase,
  decodedTimeSeconds: row.sourceBinding.decodedTimeSeconds, shotId: 'private-actual-raw-edge-control', viewId: 'main' }
async function runCase(name, eyeLocal, targetOffsetX, expectedNearestTriangle) {
  const floorPoint = new Vector3().fromArray(row.feature.localPointMetres), worldFloor = floorPoint.clone().applyMatrix4(matrix)
  const cameraObject = new PerspectiveCamera(name === 'same-body-noncoplanar-wall' ? 40 : 20, 1, 0.0001, 1)
  cameraObject.position.copy(new Vector3().fromArray(eyeLocal).applyMatrix4(matrix))
  cameraObject.up.copy(new Vector3(0, 0, -1).transformDirection(matrix))
  cameraObject.lookAt(floorPoint.clone().add(new Vector3(targetOffsetX, 0, 0)).applyMatrix4(matrix))
  cameraObject.updateProjectionMatrix(); cameraObject.updateMatrixWorld(true)
  const camera = { view: cameraObject.matrixWorldInverse, projection: cameraObject.projectionMatrix, inverseProjection: cameraObject.projectionMatrixInverse, world: cameraObject.matrixWorld }
  const pixelFor = local => { const p = new Vector3().fromArray(local).applyMatrix4(matrix).project(cameraObject); return [Math.floor((p.x + 1) * WIDTH / 2), Math.floor((p.y + 1) * HEIGHT / 2)] }
  const idBytes = new Uint8Array(WIDTH * HEIGHT * 4), depthBytes = new Uint8Array(idBytes.length), colorBytes = new Uint8Array(idBytes.length), truth = new Map(), raycaster = new Raycaster()
  for (let y = 0; y < HEIGHT; y++) for (let x = 0; x < WIDTH; x++) {
    raycaster.setFromCamera(new Vector2((x + 0.5) / WIDTH * 2 - 1, (y + 0.5) / HEIGHT * 2 - 1), cameraObject)
    const hit = raycaster.intersectObject(mesh, false).find(hit => { const p = hit.point.clone().project(cameraObject); return p.z >= -1 && p.z <= 1 })
    const offset = (y * WIDTH + x) * 4
    if (!hit) { depthBytes.set([255, 255, 255, 255], offset); continue }
    const depth = hit.point.clone().project(cameraObject).z * 0.5 + 0.5
    idBytes.set(littleRed ? [1, 0, 0, 255] : [0, 0, 1, 255], offset); colorBytes.set([255, 255, 255, 255], offset); depthBytes.set(packDepth(depth), offset)
    truth.set(`${x},${y}`, { triangleIndex: hit.faceIndex, worldPointMetres: hit.point.toArray(), depth })
  }
  const primaryPixel = pixelFor(row.feature.localPointMetres), actual = truth.get(primaryPixel.join(','))
  assert.ok(actual, `${name}: primary marker pixel must genuinely intersect original posed head`)
  if (expectedNearestTriangle !== null) assert.equal(actual.triangleIndex, expectedNearestTriangle, `${name}: independent Three original raw first hit must be the intended actual facet`)
  else {
    assert.ok(![38163, 38164].includes(actual.triangleIndex), 'negative must hit a different actual same-body face')
    const ys = [0, 1, 2].map(corner => primitive.positions[primitive.index[actual.triangleIndex * 3 + corner] * 3 + 1])
    assert.ok(ys.some(y => y !== row.feature.localPointMetres[1]), 'negative must be truly noncoplanar with original floor')
  }
  const plane = (encoding, targetSemantics, bytes) => ({ width: WIDTH, height: HEIGHT, origin: 'bottom-left', coordinateSpace: 'native-viewport', viewportBackingPixels: [0, 0, WIDTH, HEIGHT], encoding, depthBits: 24,
    bytes: { objectSHA256: put(bytes), objectByteLength: bytes.length, byteOffset: 0, byteLength: bytes.length, scalar: 'u8', components: 4, count: WIDTH * HEIGHT },
    targetSemantics, sampleCount: 0, textureColorSpace: '', depthAttachment: { type: 'reference-cpu-depth24-not-GPU', bits: 24 } })
  const receipt = { raster: { nativeMaterialRGBA: plane('rgba8', 'actual-production-material-offscreen', colorBytes), nativeMaterialDepth: plane('three-rgba-depth-v1', 'actual-production-material-offscreen', depthBytes),
    nativePathID: plane(littleRed ? 'path-id-rgb24-low-r' : 'path-id-rgb24', 'depth-tested-native-id-diagnostic', idBytes), nativeIDDepth: plane('three-rgba-depth-v1', 'depth-tested-native-id-diagnostic', depthBytes) } }
  const rays = [{ anchorId: row.witness.anchorId, pixel: primaryPixel }], grouped = new Map()
  // Complete original frozen upper-cap census plus both genuine floor supports.
  // CPU truth may make a sample occluded; no unrelated same-body point substitutes.
  for (const point of [...row.geometryEvidence.topCap.surfaceSupportPoints, ...row.geometryEvidence.floorSurfaceSupports.map(({ vertexIndices, ...point }) => ({ ...point, vertexIndex: null }))]) {
    const pixel = pixelFor(point.localPointMetres)
    if (!(pixel[0] >= 0 && pixel[0] < WIDTH && pixel[1] >= 0 && pixel[1] < HEIGHT)) continue
    const key = pixel.join(',')
    if (!grouped.has(key)) grouped.set(key, { pixel, points: [] })
    grouped.get(key).points.push(point)
  }
  const raySupports = []
  for (const [key, group] of grouped) {
    const anchorId = `${row.witness.anchorId}:surface:${key}`
    rays.push({ anchorId, pixel: group.pixel }); raySupports.push({ anchorId, kind: 'head-cap-pixel-support', candidates: group.points })
  }
  // Direct consumer's actual-plane / actual-pixel-cone branch for the shared
  // edge representative. Its actual raw barycentric point differs from the
  // frozen source marker only by F64 construction footprint, never source fit.
  const neighbour = [0, 1, 2].map(corner => primitive.index[38164 * 3 + corner])
  const edgePoint = [0, 1, 2].map(axis => primitive.positions[neighbour[0] * 3 + axis] + 0.5 * (primitive.positions[neighbour[1] * 3 + axis] - primitive.positions[neighbour[0] * 3 + axis]))
  const edgePixel = pixelFor(edgePoint), edgeAnchorId = `${row.witness.anchorId}:physical-shared-edge`
  assert.deepEqual(edgePixel, primaryPixel, 'frozen source marker and authentic edge representative occupy the same real target pixel')
  const markerToEdge = Math.hypot(...edgePoint.map((value, axis) => value - row.feature.localPointMetres[axis]))
  assert.ok(markerToEdge <= Number.EPSILON * 64 * 0.02, 'shared-edge representative must agree within F64 footprint, not mere 1e-7 proximity')
  rays.push({ anchorId: edgeAnchorId, pixel: edgePixel })
  raySupports.push({ anchorId: edgeAnchorId, kind: 'floor-triangle', triangleIndex: 38164, vertexIndices: neighbour, barycentric: [0.5, 0.5, 0], localPointMetres: edgePoint, supportTriangleIndices: [38164] })
  const support = { anchorId: row.witness.anchorId, geometryEvidence: row.geometryEvidence, geometryEvidenceSHA256: row.geometryEvidenceSHA256,
    rayAnchorIds: raySupports.map(point => point.anchorId), raySupports }
  const expectedDraw = { binding, witnesses: [row.witness], sourceFrame: {}, sourceView: {}, bodyProof: { rays, featureSupports: [support],
    sourceFeatures: [{ anchorId: row.witness.anchorId, evidence: row.sourceBinding }], contours: [] } }
  const entry = { primitive, springOracle: null, attributes: { position: primitive.attributes.POSITION, normal: primitive.attributes.NORMAL } }
  const result = await proveNativeRaster(reader, receipt, expectedDraw, new Map([[primitive.path, entry]]), new Map([[primitive.path, { matrixWorld: matrix.elements, effectiveVisibility: 'visible', springLengthM: null }]]), camera, new Map(), materialProof,
    [{ path: primitive.path, materialSlotsSHA256: [json(descriptor)] }])
  const consumerWitness = result.witnesses.find(point => point.anchorId === row.witness.anchorId)
  assert.ok(consumerWitness && consumerWitness.nearestHit.triangleIndex === actual.triangleIndex, 'public consumer must independently agree with original posed Three first-hit triangle')
  const physical = consumerWitness.footprint.outcomes.find(point => point.anchorId === edgeAnchorId)
  if (name === 'shared-edge-neighbour38164') {
    assert.equal(physical.status, 'visible', 'real surfaceCorrespondence must admit authentic original edge point at neighbour38164 in its actual pixel-plane cone')
    assert.ok(physical.worldDiscrepancyMetres <= physical.pixelFootprintRadiusMetres)
    assert.ok(physical.worldDiscrepancyMetres <= positionBoundMetres)
  }
  const membershipFailure = result.failures.includes(`Witness ${row.witness.anchorId}: nearest surface is not authentic feature support`)
  console.log(JSON.stringify({ case: name, scope: 'actual-raw-public-consumer-CPU-reference-control-not-GPU',
    nearestRawTriangleIndex: actual.triangleIndex, actualPixel: primaryPixel, physicalEdgeSupport: physical,
    computedSupportTriangleIndices: consumerWitness.supportTriangleIndices, firstSurfaceSupportRefused: membershipFailure,
    sourceBindingSHA256: jsonDigest(row.sourceBinding) }))
  if (expectedNearestTriangle === null) assert.ok(membershipFailure, 'noncoplanar same-body wall must remain refused by public consumer')
  else assert.ok(!membershipFailure, `${name}: public consumer wrongly refuses genuine posed original floor support; failures=${JSON.stringify(result.failures)}`)
  assert.equal(canonicalJson(row.sourceBinding), sourceBindingBefore, 'original FIT pixels/role/source bytes must stay unchanged')
  return { name, nearestRawTriangleIndex: actual.triangleIndex, nearestRawVertexIndices: Array.from(primitive.index.subarray(actual.triangleIndex * 3, actual.triangleIndex * 3 + 3)),
    pixel: primaryPixel, posedMatrixF64: matrix.elements, consumerSupportTriangleIndices: consumerWitness.supportTriangleIndices,
    firstSurfaceSupportRefused: membershipFailure, physicalEdgeSupport: physical,
    rawMarkerToSharedEdgeDistanceMetres: markerToEdge, actualWorldMarkerToFirstHitMetres: new Vector3().fromArray(actual.worldPointMetres).distanceTo(worldFloor),
    sourceBindingSHA256: jsonDigest(row.sourceBinding), unrelatedGaps: result.gaps, failures: result.failures }
}
try {
  const cases = []
  cases.push(await runCase('known-floor38163', [0, 0.05, 0], -2e-8, 38163))
  cases.push(await runCase('same-body-noncoplanar-wall', [0.02, 0.0055, 0], 0, null))
  cases.push(await runCase('shared-edge-neighbour38164', [0, 0.05, 0], 2e-8, 38164))
  const result = { kind: 'actual-raw-public-consumer-shared-edge-regression', mode: before ? 'retained-literal-before-two-module-bytes' : 'current-live',
    consumerSHA256: sha256(consumerBytes), pathIDCodec: littleRed ? 'little-red-rgb24' : 'big-red-rgb24-retained-before', originalRawSHA256: model.rawSHA256, positionBoundMetres, cases,
    evidenceScope: 'actual original indexed head/raw rest pose; independent Three raycast finite CPU reference raster; direct real public consumer; not complete imported closure, full scene or captured GPU',
    sourceQualification: false, GPUQualification: false, firstSurfaceQualification: false }
  if (outputPath) await writeFile(outputPath, JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify(result, null, 2))
} finally { geometry.dispose(); material.dispose() }
