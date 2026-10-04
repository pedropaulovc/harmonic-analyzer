import test from 'node:test'
import assert from 'node:assert/strict'
import { Matrix4, PerspectiveCamera, Vector2, Vector3, BufferGeometry, Float32BufferAttribute, Mesh, MeshStandardMaterial, DoubleSide, Raycaster } from 'three'
import { parseNativeRawGLB, createNativeByteReader, canonicalJson, jsonDigest, sha256 } from './native-model-byte-proof.mjs'
import { createNativeMaterialProof } from './native-material-proof.mjs'
import { nativeHorizontalSections, nativeSectionCircle, verifyNativeMeshFeatureWitness } from './native-mesh-feature-witness.mjs'
import { proveNativeRaster } from './native-qualification.mjs'

// Real parser/material/section/surface consumer, with independent Three raycasts
// generating the synthetic fixture's complete finite ID and depth planes.
// No browser/GPU or whole-model/source qualification is implied.
const WIDTH = 65, HEIGHT = 65, FLOOR_Y = Math.fround(0.03), SECTION_Y = FLOOR_Y / 2
function rawFixture(sharedEdge = false) {
  const triangles = [], add = (a, b, c) => { triangles.push(a, b, c); return triangles.length / 3 - 1 }
  const ring = (r, y, k) => [r * Math.cos(k * Math.PI / 4), y, r * Math.sin(k * Math.PI / 4)]
  // One complete raw section on an eight-sided cylindrical sidewall.
  for (let k = 0; k < 8; k++) {
    const a = ring(0.3, -0.02, k), b = ring(0.3, -0.02, (k + 1) % 8), c = ring(0.3, 0.02, (k + 1) % 8), d = ring(0.3, 0.02, k)
    add(a, b, c); add(a, c, d)
  }
  // Floor centroids align with pixel centres. The default origin is strictly
  // inside facet 0; the boundary control places that same axis on a true shared
  // edge with distinct raw indices at exactly coincident endpoint coordinates.
  const step = 2 * (1 - FLOOR_Y) / WIDTH, h = 6 * step, shift = sharedEdge ? 0 : -step
  const floor = [[-h + shift, FLOOR_Y, -h], [h + shift, FLOOR_Y, -h], [h + shift, FLOOR_Y, h], [-h + shift, FLOOR_Y, h]]
  const floorIndices = [add(floor[0], floor[1], floor[2]), add(floor[0], floor[2], floor[3])]
  // Same native primitive, nearer annular wall. It hides every closed-section
  // endpoint but leaves the anchor and both floor centroids genuinely visible.
  const occluderIndices = []
  for (let k = 0; k < 8; k++) {
    const a = ring(0.2, 0.06, k), b = ring(0.4, 0.06, k), c = ring(0.4, 0.06, (k + 1) % 8), d = ring(0.2, 0.06, (k + 1) % 8)
    occluderIndices.push(add(a, b, c), add(a, c, d))
  }
  const positions = new Float32Array(triangles.flat()), normals = new Float32Array(positions.length), indices = Uint32Array.from({ length: positions.length / 3 }, (_, i) => i)
  for (let i = 0; i < normals.length; i += 3) normals[i + 1] = 1
  const binary = Buffer.concat([positions, normals, indices].map(a => Buffer.from(a.buffer)))
  const document = { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ name: 'same-authentic-head-body', mesh: 0 }], buffers: [{ byteLength: binary.length }],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: positions.byteLength }, { buffer: 0, byteOffset: positions.byteLength, byteLength: normals.byteLength }, { buffer: 0, byteOffset: positions.byteLength + normals.byteLength, byteLength: indices.byteLength }],
    accessors: [{ bufferView: 0, componentType: 5126, count: positions.length / 3, type: 'VEC3' }, { bufferView: 1, componentType: 5126, count: normals.length / 3, type: 'VEC3' }, { bufferView: 2, componentType: 5125, count: indices.length, type: 'SCALAR' }],
    materials: [{ name: 'opaque-native-fixture', doubleSided: true, pbrMetallicRoughness: { baseColorFactor: [1, 1, 1, 1], metallicFactor: 0, roughnessFactor: 1 } }],
    meshes: [{ primitives: [{ mode: 4, attributes: { POSITION: 0, NORMAL: 1 }, indices: 2, material: 0 }] }] }
  const json = Buffer.from(JSON.stringify(document)), padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 32); json.copy(padded)
  const header = Buffer.alloc(20), binHeader = Buffer.alloc(8)
  header.writeUInt32LE(0x46546c67, 0); header.writeUInt32LE(2, 4); header.writeUInt32LE(28 + padded.length + binary.length, 8); header.writeUInt32LE(padded.length, 12); header.writeUInt32LE(0x4e4f534a, 16)
  binHeader.writeUInt32LE(binary.length, 0); binHeader.writeUInt32LE(0x004e4942, 4)
  return { raw: Buffer.concat([header, padded, binHeader, binary]), floorIndices, occluderIndices }
}
function packDepth(depth) {
  const value = Math.round(Math.min(1, Math.max(0, depth)) * (2 ** 24 - 1)) / (2 ** 24 - 1)
  if (value <= 0) return new Uint8Array(4)
  if (value >= 1) return new Uint8Array([255, 255, 255, 255])
  const scaled = value * 2 ** 24, integer = Math.floor(scaled)
  return new Uint8Array([Math.floor(integer / 65536), Math.floor(integer / 256) % 256, integer % 256, Math.round((scaled - integer) * 255)])
}
function triangleRecord(primitive, triangleIndex) {
  const vertexIndices = Array.from(primitive.index.subarray(triangleIndex * 3, triangleIndex * 3 + 3))
  const localPointsMetres = vertexIndices.map(index => Array.from(primitive.positions.subarray(index * 3, index * 3 + 3)))
  return { triangleIndex, vertexIndices, localPointsMetres }
}

async function fixture(includeFloorSupports, boundaryControl = null) {
  const { raw, floorIndices, occluderIndices } = rawFixture(boundaryControl !== null), parsed = parseNativeRawGLB(raw), model = { ...parsed, rawSHA256: sha256(raw) }
  const primitive = [...model.primitives.values()][0], path = primitive.path
  const section = nativeHorizontalSections(primitive, SECTION_Y)
  assert.equal(section.cycles.length, 1)
  const cycle = section.cycles[0], circle = nativeSectionCircle(cycle)
  const floorTriangles = floorIndices.map(index => triangleRecord(primitive, index))
  const wallControl = boundaryControl === 'noncoplanar-wall'
  const weights = boundaryControl ? [1 / 2, 0, 1 / 2] : [5 / 12, 1 / 12, 1 / 2]
  const ps = floorTriangles[0].localPointsMetres
  const marker = [0, 1, 2].map(axis => ps[0][axis] + weights[1] * (ps[1][axis] - ps[0][axis]) + weights[2] * (ps[2][axis] - ps[0][axis]))
  const cameraObject = new PerspectiveCamera(90, 1, 0.005, 100)
  cameraObject.up.set(0, 0, -1)
  if (boundaryControl) {
    // Stand outside the whole r=0.4 body: every original triangle then has
    // positive W and clear near/far support. The ray still crosses the nearer
    // y=0.06 annulus before the y=0.03 floor; z offset avoids a facet-edge tie.
    cameraObject.position.set(wallControl ? 0.6 : 0, wallControl ? 0.09 : 1, wallControl ? 0.02 : 0)
    const acrossEdge = boundaryControl === 'coplanar-neighbour' ? -2e-8 : boundaryControl === 'declared-floor' ? 2e-8 : 0
    cameraObject.lookAt(marker[0] + acrossEdge, marker[1], marker[2])
  } else { cameraObject.position.set(0, 1, 0); cameraObject.lookAt(0, 0, 0) }
  cameraObject.updateProjectionMatrix(); cameraObject.updateMatrixWorld(true)
  const camera = { view: cameraObject.matrixWorldInverse, projection: cameraObject.projectionMatrix, inverseProjection: cameraObject.projectionMatrixInverse, world: cameraObject.matrixWorld }
  if (wallControl) for (let offset = 0; offset < primitive.positions.length; offset += 3) {
    const viewPoint = new Vector3().fromArray(primitive.positions, offset).applyMatrix4(camera.view)
    assert.ok(-viewPoint.z > cameraObject.near && -viewPoint.z < cameraObject.far, 'wall control must keep every authentic triangle vertex clear of W/near/far clipping')
    const projected = viewPoint.applyMatrix4(camera.projection)
    assert.ok(Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1, 'wall control must fit the entire authentic primitive inside the viewport')
  }
  const pixelFor = point => { const p = new Vector3().fromArray(point).project(cameraObject); return [Math.floor((p.x + 1) * WIDTH / 2), Math.floor((p.y + 1) * HEIGHT / 2)] }
  const geometry = new BufferGeometry(); geometry.setAttribute('position', new Float32BufferAttribute(primitive.positions, 3)); geometry.setIndex(Array.from(primitive.index))
  const material = new MeshStandardMaterial({ side: DoubleSide }), mesh = new Mesh(geometry, material); mesh.updateMatrixWorld(true)
  const raycaster = new Raycaster(), idBytes = new Uint8Array(WIDTH * HEIGHT * 4), colorBytes = new Uint8Array(idBytes.length), depthBytes = new Uint8Array(idBytes.length), truth = new Map()
  for (let y = 0; y < HEIGHT; y++) for (let x = 0; x < WIDTH; x++) {
    raycaster.setFromCamera(new Vector2((x + 0.5) / WIDTH * 2 - 1, (y + 0.5) / HEIGHT * 2 - 1), cameraObject)
    const hit = raycaster.intersectObject(mesh, false).find(row => { const p = row.point.clone().project(cameraObject); return p.z >= -1 && p.z <= 1 })
    const offset = (y * WIDTH + x) * 4
    if (!hit) { depthBytes.set([255, 255, 255, 255], offset); continue }
    const depth = hit.point.clone().project(cameraObject).z * 0.5 + 0.5
    // The actual scene's nativePathId shader writes the low ID byte to red.
    const identifier = 1
    idBytes.set([identifier & 255, (identifier >> 8) & 255, (identifier >> 16) & 255, 255], offset)
    colorBytes.set([255, 255, 255, 255], offset); depthBytes.set(packDepth(depth), offset)
    truth.set(`${x},${y}`, { triangleIndex: hit.faceIndex, worldPointMetres: hit.point.toArray(), distance: hit.distance, depth })
  }
  geometry.dispose(); material.dispose()
  const objects = new Map(), put = bytes => { const hash = sha256(bytes); objects.set(hash, bytes); return hash }, json = value => put(Buffer.from(canonicalJson(value)))
  const span = bytes => ({ objectSHA256: put(bytes), objectByteLength: bytes.length, byteOffset: 0, byteLength: bytes.length, scalar: 'u8', components: 4, count: WIDTH * HEIGHT })
  const reader = createNativeByteReader({ get: async hash => { assert.ok(objects.has(hash)); return objects.get(hash) } })
  const materialProof = await createNativeMaterialProof({ rawGLBBytes: raw, model }), expectedMaterial = materialProof.expectedFor(primitive)
  const descriptor = Object.fromEntries(['schemaVersion', 'type', 'name', 'properties', 'clippingPlanes', 'textures'].map(key => [key, expectedMaterial[key]]))
  const plane = (encoding, targetSemantics, bytes) => ({ width: WIDTH, height: HEIGHT, origin: 'bottom-left', coordinateSpace: 'native-viewport', viewportBackingPixels: [0, 0, WIDTH, HEIGHT], encoding, depthBits: 24, bytes: span(bytes), targetSemantics, sampleCount: 0, textureColorSpace: '', depthAttachment: { type: 'fixture-depth24', bits: 24 } })
  const receipt = { raster: { nativeMaterialRGBA: plane('rgba8', 'actual-production-material-offscreen', colorBytes), nativeMaterialDepth: plane('three-rgba-depth-v1', 'actual-production-material-offscreen', depthBytes), nativePathID: plane('path-id-rgb24-low-r', 'depth-tested-native-id-diagnostic', idBytes), nativeIDDepth: plane('three-rgba-depth-v1', 'depth-tested-native-id-diagnostic', depthBytes) } }
  const binding = { sourceVideoId: 'private-finite-rim-control', sourceSha256: '0'.repeat(64), sourceImage: { pixelFormat: 'bgr8', sha256Bgr8: '1'.repeat(64), width: WIDTH, height: HEIGHT, frameIndex: 0 }, decodedFrameIndex: 0, decodedTimestampTicks: '0', timeBase: '1/1', decodedTimeSeconds: 0, shotId: 'one', viewId: 'main' }
  const evidence = { originalSourceBinding: binding }, anchorId = 'floor-feature'
  const witness = { anchorId, partPath: path, rawPrimitiveSHA256: primitive.rawPrimitiveSHA256, sourceFeatureEvidenceSHA256: jsonDigest(evidence), kind: 'triangle-point', triangleIndex: floorIndices[0], barycentric: weights }
  const feature = verifyNativeMeshFeatureWitness(witness, primitive)
  const geometryEvidence = { construction: 'native-slotted-head-floor-axis-v1', rawAncestry: { rawNodeIndex: 0, rawMeshIndex: 0, rawPrimitiveIndex: 0, partPath: path },
    positionAccessor: { index: 0, componentType: 5126, type: 'VEC3', count: primitive.positions.length / 3, typedBytesSHA256: sha256(new Uint8Array(primitive.positions.buffer, primitive.positions.byteOffset, primitive.positions.byteLength)) },
    indexAccessor: { index: 2, componentType: 5125, type: 'SCALAR', count: primitive.index.length, typedBytesSHA256: sha256(new Uint8Array(primitive.index.buffer, primitive.index.byteOffset, primitive.index.byteLength)) },
    floorTriangles, headMaximumYMetres: Math.fround(0.06), axisFloorYMetres: FLOOR_Y, sectionPlaneLocal: [0, 1, 0, -SECTION_Y], rimTriangleIndices: cycle.triangleIndices, rimEndpoints: cycle.endpoints, sectionCircle: circle,
    circleCentreAxisErrorMetres: Math.hypot(circle.centreLocalMetres[0], circle.centreLocalMetres[2]), supportTriangleIndices: [...new Set([...cycle.triangleIndices, ...floorIndices])].sort((a, b) => a - b), markerPointIsStoredVertex: false, markerPointIsSurfacePoint: true,
    virtualEnvelopeCentreLocalMetres: [0, Math.fround(0.06), 0], virtualEnvelopeCentreIsSurfacePoint: false }
  const rays = [{ anchorId, pixel: pixelFor(feature.localPointMetres) }], samples = []
  if (!wallControl) for (let i = 0; i < cycle.endpoints.length; i++) {
    const endpoint = cycle.endpoints[i], rayAnchorId = `rim-${i}`, pixel = pixelFor(endpoint.localMetres)
    const actual = truth.get(pixel.join(',')); assert.ok(actual && occluderIndices.includes(actual.triangleIndex), 'negative fixture must genuinely self-occlude each projected section endpoint')
    rays.push({ anchorId: rayAnchorId, pixel })
    samples.push({ rayAnchorId, kind: 'rim-endpoint', localPointMetres: endpoint.localMetres, triangleIndices: [...new Set(endpoint.supportingRawEdges.map(edge => edge.triangleIndex))].sort((a, b) => a - b), rawEndpointKey: endpoint.key })
  }
  if (includeFloorSupports && !wallControl) for (const floor of floorTriangles) {
    const point = [0, 1, 2].map(axis => floor.localPointsMetres.reduce((sum, p) => sum + p[axis], 0) / 3), pixel = pixelFor(point), rayAnchorId = `floor-${floor.triangleIndex}`
    const actual = truth.get(pixel.join(',')); assert.equal(actual?.triangleIndex, floor.triangleIndex, 'positive fixture needs actual triangle-specific visible floor centroids')
    rays.push({ anchorId: rayAnchorId, pixel }); samples.push({ rayAnchorId, kind: 'floor-triangle-centroid', localPointMetres: point, triangleIndices: [floor.triangleIndex], rawEndpointKey: null })
  }
  if (boundaryControl && !wallControl) {
    const rayAnchorId = 'physical-shared-floor-edge', pixel = pixelFor(feature.localPointMetres)
    rays.push({ anchorId: rayAnchorId, pixel })
    samples.push({ rayAnchorId, kind: 'floor-shared-edge', localPointMetres: feature.localPointMetres, triangleIndices: [floorIndices[1]], rawEndpointKey: null })
  }
  const actualAnchor = truth.get(rays[0].pixel.join(','))
  if (wallControl) assert.ok(actualAnchor && occluderIndices.includes(actualAnchor.triangleIndex), 'wall control must genuinely occlude the shared-floor marker with this same raw body')
  else assert.equal(actualAnchor?.triangleIndex, boundaryControl === 'coplanar-neighbour' ? floorIndices[1] : witness.triangleIndex, 'independent raycast must hit the intended authentic floor facet')
  const support = { anchorId, geometryEvidence, geometryEvidenceSHA256: jsonDigest(geometryEvidence), rayAnchorIds: samples.map(sample => sample.rayAnchorId) }
  support.raySupports = samples.map(sample => {
    if (sample.kind === 'rim-endpoint') {
      const endpointOrdinal = cycle.endpoints.findIndex(endpoint => endpoint.key === sample.rawEndpointKey)
      const endpoint = cycle.endpoints[endpointOrdinal]
      return { anchorId: sample.rayAnchorId, kind: 'section-edge', localPointMetres: sample.localPointMetres,
        endpointOrdinal, rawPositionIds: endpoint.rawPositionIds, supportingRawEdges: endpoint.supportingRawEdges,
        parameterFromFirstVertex: endpoint.parameterFromFirstVertex, supportTriangleIndices: sample.triangleIndices }
    }
    const floor = floorTriangles.find(row => row.triangleIndex === sample.triangleIndices[0])
    return { anchorId: sample.rayAnchorId, kind: 'floor-triangle', triangleIndex: floor.triangleIndex,
      vertexIndices: floor.vertexIndices, barycentric: sample.kind === 'floor-shared-edge' ? [1 / 2, 1 / 2, 0] : [1 / 3, 1 / 3, 1 / 3],
      localPointMetres: sample.localPointMetres, supportTriangleIndices: sample.triangleIndices }
  })
  const expectedDraw = { binding, witnesses: [witness], sourceFrame: {}, sourceView: {}, bodyProof: { rays, sourceFeatures: [{ anchorId, evidence }], featureSupports: wallControl ? [] : [support], contours: [] } }
  const entry = { primitive, springOracle: null, attributes: { position: primitive.attributes.POSITION, normal: primitive.attributes.NORMAL } }, matrixWorld = new Matrix4().elements
  const result = await proveNativeRaster(reader, receipt, expectedDraw, new Map([[path, entry]]), new Map([[path, { matrixWorld, effectiveVisibility: 'visible', springLengthM: null }]]), camera, new Map(), materialProof, [{ path, materialSlotsSHA256: [json(descriptor)] }])
  return { result, floorIndices, endpointCount: cycle.endpoints.length, actualAnchor, occluderIndices, marker: feature.localPointMetres, markerPixel: rays[0].pixel, path }
}

test('same-body occlusion is not visible native rim support', async () => {
  const { result, endpointCount } = await fixture(false)
  assert.deepEqual(result.failures, [])
  assert.ok(result.gaps.length > 0, 'occluded rim without another physical support must remain unmeasured')
  const feature = result.witnesses[0], support = feature.footprint
  assert.equal(support.rawClosedSection, true)
  assert.equal(support.visibleRimCount, 0)
  assert.equal(support.occludedRimCount, endpointCount)
  assert.deepEqual(support.visibleSlotTriangleIndices, [])
  assert.ok(support.outcomes.every(row => row.status === 'occluded'))
})

test('two distinct visible native floor facets qualify without claiming occluded rim visibility', async () => {
  const { result, floorIndices, endpointCount } = await fixture(true)
  assert.deepEqual(result.failures, [])
  assert.deepEqual(result.gaps, [])
  const support = result.witnesses[0].footprint
  assert.equal(support.rawClosedSection, true)
  assert.equal(support.visibleRimCount, 0)
  assert.equal(support.occludedRimCount, endpointCount)
  assert.deepEqual([...support.visibleSlotTriangleIndices].sort((a, b) => a - b), floorIndices)
  const floor = support.outcomes.filter(row => row.kind === 'floor-triangle')
  assert.deepEqual(floor.map(row => row.triangleIndex).sort((a, b) => a - b), floorIndices)
  for (const row of floor) {
    assert.equal(row.status, 'visible')
    assert.ok(row.worldDiscrepancyMetres <= row.pixelFootprintRadiusMetres)
  }
})

test('shared-edge marker retains genuine first-surface support on its declared floor facet', async () => {
  const { result, floorIndices, actualAnchor, marker } = await fixture(true, 'declared-floor')
  assert.deepEqual(result.failures, [])
  assert.deepEqual(result.gaps, [])
  const witness = result.witnesses[0]
  assert.equal(witness.nearestHit.triangleIndex, floorIndices[0])
  assert.equal(witness.nearestHit.triangleIndex, actualAnchor.triangleIndex)
  assert.ok(new Vector3().fromArray(witness.nearestHit.worldPointMetres).distanceTo(new Vector3().fromArray(marker)) <= 1e-7)
})

test('shared-edge marker admits the authentic coplanar neighbouring floor first hit', async () => {
  const { result, floorIndices, actualAnchor, marker, markerPixel } = await fixture(true, 'coplanar-neighbour')
  assert.deepEqual(result.failures, [])
  assert.deepEqual(result.gaps, [])
  const witness = result.witnesses[0]
  assert.equal(witness.nearestHit.triangleIndex, floorIndices[1])
  assert.equal(witness.nearestHit.triangleIndex, actualAnchor.triangleIndex)
  assert.deepEqual(witness.pixel, markerPixel)
  assert.ok(new Vector3().fromArray(witness.nearestHit.worldPointMetres).distanceTo(new Vector3().fromArray(marker)) <= 1e-7)
  const physical = witness.footprint.outcomes.find(row => row.anchorId === 'physical-shared-floor-edge')
  assert.equal(physical.status, 'visible')
  assert.equal(physical.triangleIndex, floorIndices[1])
  assert.ok(physical.worldDiscrepancyMetres <= physical.pixelFootprintRadiusMetres)
})

test('shared-edge incidence never admits a nearer noncoplanar face of the same native body', async () => {
  const { result, actualAnchor, occluderIndices, marker, path } = await fixture(false, 'noncoplanar-wall')
  assert.deepEqual(result.gaps, [])
  assert.equal(result.failures.length, 1, 'exactly the physical first-surface requirement must refuse this otherwise valid exposure')
  const witness = result.witnesses[0]
  assert.equal(witness.nearestHit.path, path)
  assert.equal(witness.nearestHit.triangleIndex, actualAnchor.triangleIndex)
  assert.ok(occluderIndices.includes(witness.nearestHit.triangleIndex))
  assert.ok(Math.abs(witness.nearestHit.worldPointMetres[1] - Math.fround(0.06)) <= 1e-7)
  assert.ok(witness.nearestHit.worldPointMetres[1] > marker[1])
})
