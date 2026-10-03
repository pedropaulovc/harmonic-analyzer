import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { deflateSync } from 'node:zlib'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'meshoptimizer'
import { optimizeModel, validateDecodedEquivalence } from './optimize-model.mjs'

const MESHOPT = 'EXT_meshopt_compression'
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const align4 = n => Math.ceil(n / 4) * 4

// All fixture media is generated here: one tiny opaque RGBA pixel, never a
// downloaded/model-exported/copyrighted image.
function pngPixel() {
  function crc32(bytes) {
    let crc = 0xffffffff
    for (const byte of bytes) {
      crc ^= byte
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0)
    }
    return (crc ^ 0xffffffff) >>> 0
  }
  function chunk(type, data) {
    const bytes = Buffer.alloc(12 + data.length)
    bytes.writeUInt32BE(data.length, 0); bytes.write(type, 4); data.copy(bytes, 8)
    bytes.writeUInt32BE(crc32(bytes.subarray(4, 8 + data.length)), 8 + data.length)
    return bytes
  }
  const header = Buffer.alloc(13)
  header.writeUInt32BE(1, 0); header.writeUInt32BE(1, 4); header[8] = 8; header[9] = 6
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(Buffer.from([0, 83, 137, 211, 255]))), chunk('IEND', Buffer.alloc(0))])
}
function floatBytes(values) {
  const bytes = Buffer.alloc(values.length * 4)
  values.forEach((value, i) => bytes.writeFloatLE(value, i * 4))
  return bytes
}
function indexBytes(values, size = 4) {
  const bytes = Buffer.alloc(values.length * size)
  values.forEach((value, i) => bytes.writeUIntLE(value, i * size, size))
  return bytes
}
function packGlb(json, binary) {
  const text = Buffer.from(JSON.stringify(json)), jsonLength = align4(text.length), binaryLength = align4(binary.length)
  const bytes = Buffer.alloc(28 + jsonLength + binaryLength)
  bytes.writeUInt32LE(0x46546c67, 0); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(jsonLength, 12); bytes.writeUInt32LE(0x4e4f534a, 16)
  bytes.fill(0x20, 20, 20 + jsonLength); text.copy(bytes, 20)
  bytes.writeUInt32LE(binaryLength, 20 + jsonLength); bytes.writeUInt32LE(0x004e4942, 24 + jsonLength)
  binary.copy(bytes, 28 + jsonLength)
  return bytes
}
function unpackGlb(bytes) {
  const jsonLength = bytes.readUInt32LE(12), json = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString())
  return { json, binary: Buffer.from(bytes.subarray(28 + jsonLength, 28 + jsonLength + json.buffers[0].byteLength)) }
}
function fixture({ copies = 20, positionX = 1, indexSize = 4 } = {}) {
  const json = {
    asset: { version: '2.0', generator: 'SOLIDWORKS GLTF', extras: { unchanged: 'fixture provenance' } },
    scene: 0, scenes: [{ name: 'assembly', nodes: [0], extras: { preserve: true } }],
    nodes: [{ name: 'assembly-root', children: [] }], meshes: [], accessors: [], bufferViews: [],
    materials: [{ name: 'spring-stock', pbrMetallicRoughness: { roughnessFactor: 0.5 }, extensions: { KHR_materials_unlit: {} }, extras: { stock: 'unchanged' } }],
    extensionsUsed: ['KHR_materials_unlit'],
    images: [], textures: [], samplers: [{}], buffers: [{ byteLength: 0, extras: { sourceBuffer: 'unchanged' } }],
    extras: { author: 'in-memory fixture', opaqueIndices: [10, 20] },
  }
  const chunks = []
  let offset = 0
  function addView(bytes, metadata = {}) {
    const start = align4(offset)
    if (start > offset) chunks.push(Buffer.alloc(start - offset))
    chunks.push(bytes); offset = start + bytes.length
    const index = json.bufferViews.length
    json.bufferViews.push({ buffer: 0, byteOffset: start, byteLength: bytes.length, ...metadata })
    return index
  }
  const positions = floatBytes([-0, 0, 0, positionX, 0, 0, 0, 1, 0])
  const normals = floatBytes([-0, 0, 1, 0, -0, 1, 0, 0, 1])
  const indices = indexBytes([2, 0, 1], indexSize)
  for (let i = 0; i < copies; i++) {
    const first = json.accessors.length
    const position = addView(positions, { byteStride: 12, target: 34962 })
    const normal = addView(normals, { byteStride: 12, target: 34962 })
    const index = addView(indices, { target: 34963 })
    json.accessors.push(
      { bufferView: position, byteOffset: 0, componentType: 5126, count: 3, type: 'VEC3', min: [0, 0, 0], max: [positionX, 1, 0] },
      { bufferView: normal, byteOffset: 0, componentType: 5126, count: 3, type: 'VEC3' },
      { bufferView: index, byteOffset: 0, componentType: indexSize === 4 ? 5125 : indexSize === 2 ? 5123 : 5121, count: 3, type: 'SCALAR' },
    )
    json.meshes.push({ primitives: [{ attributes: { POSITION: first, NORMAL: first + 1 }, indices: first + 2, material: 0, mode: 4, extras: { originalOrder: true } }], extras: { geometryRole: 'spring' } })
    json.nodes.push({ name: `spring-${i + 1}`, mesh: i, translation: [i * 2, i % 3, -i], rotation: [0, 0, 0, 1], scale: [1, 1 + i / 100, 1], extras: { assemblyPath: `bank/${i}` } })
    json.nodes[0].children.push(i + 1)
  }
  const png = pngPixel()
  for (let i = 0; i < 2; i++) {
    json.images.push({ mimeType: 'image/png', bufferView: addView(png), extras: { generated: true } })
    // Deliberately unreferenced by materials: Node's real GLTFLoader can exercise
    // the scene/geometry without pretending to implement a browser image API.
    json.textures.push({ source: i, sampler: 0 })
  }
  json.buffers[0].byteLength = offset
  return { json, binary: Buffer.concat(chunks, offset), positions, normals, indices, png }
}
function appendView(model, bytes, metadata = {}) {
  const offset = align4(model.binary.length), index = model.json.bufferViews.length
  model.binary = Buffer.concat([model.binary, Buffer.alloc(offset - model.binary.length), bytes])
  model.json.bufferViews.push({ buffer: 0, byteOffset: offset, byteLength: bytes.length, ...metadata })
  model.json.buffers[0].byteLength = model.binary.length
  return index
}
async function decodedView(model, index) {
  const view = model.json.bufferViews[index], extension = view.extensions?.[MESHOPT]
  if (!extension) return model.binary.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength)
  await MeshoptDecoder.ready
  const result = Buffer.alloc(view.byteLength)
  MeshoptDecoder.decodeGltfBuffer(result, extension.count, extension.byteStride, model.binary.subarray(extension.byteOffset ?? 0, (extension.byteOffset ?? 0) + extension.byteLength), extension.mode, extension.filter)
  return result
}
async function loadScene(bytes) {
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder)
  return loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '')
}

test('exact meshes/images deduplicate while all named independently transformed scene instances survive and share real Three geometry', async () => {
  const model = fixture(), sourceBytes = packGlb(model.json, model.binary)
  // Compare against the serialized source document, not JavaScript-only -0
  // transform values that JSON.stringify has already encoded as 0.
  const sourceJson = unpackGlb(sourceBytes).json
  const { optimizedBytes, report } = await optimizeModel(sourceBytes)
  const optimized = unpackGlb(optimizedBytes)
  assert.equal(optimized.json.meshes.length, 1)
  assert.equal(optimized.json.accessors.length, 3)
  assert.equal(optimized.json.bufferViews.length, 4)
  assert.equal(optimized.json.images.length, 1)
  assert.equal(optimized.json.textures[0].source, optimized.json.textures[1].source)
  assert.deepEqual(optimized.json.nodes.map(node => ({ ...node, mesh: node.mesh === undefined ? undefined : 'same-geometry' })), sourceJson.nodes.map(node => ({ ...node, mesh: node.mesh === undefined ? undefined : 'same-geometry' })))
  assert.deepEqual(optimized.json.scenes, model.json.scenes)
  assert.deepEqual(optimized.json.materials, model.json.materials)
  assert.deepEqual(optimized.json.asset, model.json.asset)
  assert.deepEqual(optimized.json.extras, model.json.extras)
  assert.equal(optimized.json.images[0].mimeType, 'image/png')
  const imageView = optimized.json.bufferViews[optimized.json.images[0].bufferView]
  assert.equal(imageView.extensions?.[MESHOPT], undefined)
  assert.deepEqual(await decodedView(optimized, optimized.json.images[0].bufferView), model.png)
  assert.ok(optimized.json.extensionsRequired.includes(MESHOPT))
  assert.equal(optimized.json.buffers[1].extensions[MESHOPT].fallback, true)
  assert.equal(optimized.json.buffers[1].uri, undefined)
  for (const view of optimized.json.bufferViews) if (view.extensions?.[MESHOPT]) {
    assert.equal(view.buffer, 1)
    assert.ok(view.byteOffset + view.byteLength <= optimized.json.buffers[1].byteLength)
    assert.equal(view.extensions[MESHOPT].buffer, 0)
  }
  assert.deepEqual(report.statistics.source, { bufferViews: 62, accessors: 60, meshes: 20, images: 2, nodes: 21, drawableInstances: 20 })
  assert.deepEqual(report.statistics.optimized, { bufferViews: 4, accessors: 3, meshes: 1, images: 1, nodes: 21, drawableInstances: 20 })
  assert.ok(report.deduplicatedBytes < report.sourceBytes)
  assert.equal(report.optimizedBytes, optimizedBytes.length)
  assert.equal(report.sourceSha256, sha256(sourceBytes))
  assert.equal(report.optimizedSha256, sha256(optimizedBytes))
  assert.equal(report.equivalence.passed, true)
  assert.match(report.semanticDigest, /^[a-f0-9]{64}$/)
  assert.deepEqual(await validateDecodedEquivalence(sourceBytes, optimizedBytes), report.equivalence)

  const before = await loadScene(sourceBytes), after = await loadScene(optimizedBytes)
  const first = after.scene.getObjectByName('spring-1')
  assert.notEqual(before.scene.getObjectByName('spring-1').geometry, before.scene.getObjectByName('spring-2').geometry)
  for (let i = 1; i <= 20; i++) {
    const original = before.scene.getObjectByName(`spring-${i}`), instance = after.scene.getObjectByName(`spring-${i}`)
    assert.equal(instance.geometry, first.geometry)
    assert.notEqual(instance, original)
    if (i > 1) assert.notEqual(instance, first)
    assert.deepEqual(instance.position.toArray(), original.position.toArray())
    assert.deepEqual(instance.quaternion.toArray(), original.quaternion.toArray())
    assert.deepEqual(instance.scale.toArray(), original.scale.toArray())
    assert.deepEqual(Array.from(instance.geometry.index.array), [2, 0, 1])
  }
  const loaderWithoutDecoder = new GLTFLoader()
  await assert.rejects(loaderWithoutDecoder.parseAsync(optimizedBytes.buffer.slice(optimizedBytes.byteOffset, optimizedBytes.byteOffset + optimizedBytes.byteLength), ''), /setMeshoptDecoder/)
})

test('identical bytes with different accessor layouts, material assignment, or metadata do not collapse semantic definitions', async () => {
  const model = fixture({ copies: 3 })
  const a = model.json.accessors.length
  model.json.accessors.push(
    { bufferView: 0, byteOffset: 0, componentType: 5126, count: 3, type: 'VEC3' },
    { bufferView: 3, byteOffset: 4, componentType: 5126, count: 3, type: 'VEC2' },
  )
  model.json.meshes[0].primitives[0].attributes._FIELD = a
  model.json.meshes[1].primitives[0].attributes._FIELD = a + 1
  model.json.materials.push({ name: 'other-stock', pbrMetallicRoughness: { metallicFactor: 1, roughnessFactor: 0.3 } })
  model.json.meshes[2].primitives[0].material = 1
  model.json.meshes[2].name = 'retain-this-mesh-name'
  const { optimizedBytes } = await optimizeModel(packGlb(model.json, model.binary))
  const optimized = unpackGlb(optimizedBytes)
  assert.equal(optimized.json.meshes.length, 3)
  const primitives = optimized.json.nodes.slice(1).map(node => optimized.json.meshes[node.mesh].primitives[0])
  assert.notEqual(primitives[0].attributes._FIELD, primitives[1].attributes._FIELD)
  const first = optimized.json.accessors[primitives[0].attributes._FIELD], second = optimized.json.accessors[primitives[1].attributes._FIELD]
  assert.equal(first.bufferView, second.bufferView)
  assert.deepEqual([first.type, first.byteOffset, second.type, second.byteOffset], ['VEC3', 0, 'VEC2', 4])
  assert.deepEqual(primitives.map(primitive => primitive.material), [0, 0, 1])
  assert.equal(optimized.json.meshes[optimized.json.nodes[3].mesh].name, 'retain-this-mesh-name')
  assert.deepEqual(optimized.json.materials, model.json.materials)
})

test('filter-free codecs preserve signed-zero bits, exact index order and arbitrary opaque floating-point bit patterns', async () => {
  for (const indexSize of [2, 4]) {
    const model = fixture({ copies: 2, indexSize })
    const opaque = indexBytes([0x80000000, 0x7fc00001, 0x7fa12345, 0xff800000])
    const opaqueIndex = appendView(model, opaque, { name: 'opaque-float-bit-patterns', extras: { note: 'not a numeric glTF accessor' } })
    const source = packGlb(model.json, model.binary), { optimizedBytes } = await optimizeModel(source)
    const optimized = unpackGlb(optimizedBytes), primitive = optimized.json.meshes[0].primitives[0]
    for (const [attribute, expected] of [['POSITION', model.positions], ['NORMAL', model.normals]]) {
      const accessor = optimized.json.accessors[primitive.attributes[attribute]], view = optimized.json.bufferViews[accessor.bufferView]
      assert.equal(view.extensions[MESHOPT].mode, 'ATTRIBUTES')
      assert.equal(view.extensions[MESHOPT].filter, 'NONE')
      const decoded = await decodedView(optimized, accessor.bufferView)
      assert.deepEqual(decoded, expected)
      assert.equal(decoded.readUInt32LE(0), 0x80000000)
    }
    const accessor = optimized.json.accessors[primitive.indices], view = optimized.json.bufferViews[accessor.bufferView]
    assert.equal(view.extensions[MESHOPT].mode, 'INDICES')
    assert.deepEqual(await decodedView(optimized, accessor.bufferView), model.indices)
    const preserved = optimized.json.bufferViews.findIndex(candidate => candidate.name === model.json.bufferViews[opaqueIndex].name)
    assert.deepEqual(await decodedView(optimized, preserved), opaque)
    await validateDecodedEquivalence(source, optimizedBytes)
  }
})

test('eight-bit indices and non-codec-aligned attributes remain raw rather than being widened or quantized', async () => {
  const model = fixture({ copies: 2, indexSize: 1 })
  const values = Buffer.from([10, 20, 30, 40, 50, 60, 70, 80, 90]), viewIndex = appendView(model, values)
  const accessorIndex = model.json.accessors.length
  model.json.accessors.push({ bufferView: viewIndex, componentType: 5121, normalized: true, count: 3, type: 'VEC3' })
  for (const mesh of model.json.meshes) mesh.primitives[0].attributes._COLOR = accessorIndex
  const { optimizedBytes } = await optimizeModel(packGlb(model.json, model.binary)), optimized = unpackGlb(optimizedBytes)
  const primitive = optimized.json.meshes[0].primitives[0]
  for (const [index, expected] of [[primitive.indices, model.indices], [primitive.attributes._COLOR, values]]) {
    const accessor = optimized.json.accessors[index], view = optimized.json.bufferViews[accessor.bufferView]
    assert.equal(view.extensions?.[MESHOPT], undefined)
    assert.deepEqual(await decodedView(optimized, accessor.bufferView), expected)
  }
  assert.equal(optimized.json.accessors[primitive.attributes._COLOR].normalized, true)
})

test('sparse attribute values and indices retain their exact raw bytes and semantics', async () => {
  const model = fixture({ copies: 1 }), indices = Buffer.from([1]), values = floatBytes([-0, 2, 3])
  const indexView = appendView(model, indices), valueView = appendView(model, values)
  delete model.json.accessors[0].bufferView
  delete model.json.accessors[0].byteOffset
  delete model.json.accessors[0].min
  delete model.json.accessors[0].max
  model.json.accessors[0].sparse = { count: 1, indices: { bufferView: indexView, componentType: 5121 }, values: { bufferView: valueView } }
  const source = packGlb(model.json, model.binary), { optimizedBytes } = await optimizeModel(source), optimized = unpackGlb(optimizedBytes)
  const accessor = optimized.json.accessors[optimized.json.meshes[0].primitives[0].attributes.POSITION]
  assert.equal(accessor.bufferView, undefined)
  assert.equal(accessor.sparse.count, 1)
  for (const [key, expected] of [['indices', indices], ['values', values]]) {
    const view = accessor.sparse[key].bufferView
    assert.equal(optimized.json.bufferViews[view].extensions?.[MESHOPT], undefined)
    assert.deepEqual(await decodedView(optimized, view), expected)
  }
  const originalScene = await loadScene(source), optimizedScene = await loadScene(optimizedBytes)
  assert.deepEqual(Array.from(optimizedScene.scene.getObjectByName('spring-1').geometry.attributes.position.array), Array.from(originalScene.scene.getObjectByName('spring-1').geometry.attributes.position.array))
})

test('replacement source content yields new source/artifact pins and semantic identity, while same-source output is deterministic', async () => {
  const original = fixture({ copies: 2 }), replacement = fixture({ copies: 2, positionX: 2 })
  const originalBytes = packGlb(original.json, original.binary), replacementBytes = packGlb(replacement.json, replacement.binary)
  const first = await optimizeModel(originalBytes), repeated = await optimizeModel(originalBytes), replaced = await optimizeModel(replacementBytes)
  assert.deepEqual(repeated.optimizedBytes, first.optimizedBytes)
  assert.deepEqual(repeated.report, first.report)
  assert.equal(replaced.report.sourceSha256, sha256(replacementBytes))
  assert.equal(replaced.report.optimizedSha256, sha256(replaced.optimizedBytes))
  assert.notEqual(replaced.report.sourceSha256, first.report.sourceSha256)
  assert.notEqual(replaced.report.optimizedSha256, first.report.optimizedSha256)
  assert.notEqual(replaced.report.semanticDigest, first.report.semanticDigest)
  await validateDecodedEquivalence(replacementBytes, replaced.optimizedBytes)
  await assert.rejects(validateDecodedEquivalence(originalBytes, replaced.optimizedBytes), /decoded equivalence failed/)
})

test('malformed GLB and references, external buffers and ambiguous extensions are refused without fallback geometry', async () => {
  await assert.rejects(optimizeModel(Buffer.from('not a GLB')), /invalid GLB header/)
  const badHeader = fixture({ copies: 1 }), badHeaderBytes = packGlb(badHeader.json, badHeader.binary)
  badHeaderBytes.writeUInt32LE(badHeaderBytes.length - 4, 8)
  await assert.rejects(optimizeModel(badHeaderBytes), /declared length/)
  const cases = [
    [model => { model.json.accessors[0].bufferView = 999 }, /references missing bufferViews/],
    [model => { model.json.meshes[0].primitives[0].attributes.POSITION = 999 }, /references missing accessors/],
    [model => { model.json.images[0].bufferView = 999 }, /references missing bufferViews/],
    [model => { model.json.nodes[1].mesh = 999 }, /references missing meshes/],
    [model => { model.json.bufferViews[0].byteLength = model.binary.length + 1 }, /outside its buffer/],
    [model => { model.json.accessors[0].count = 4 }, /exceeds its bufferView/],
    [model => { const view = model.json.bufferViews[2]; model.binary.writeUInt32LE(3, view.byteOffset) }, /index is outside/],
    [model => { model.json.buffers[0].uri = 'source.bin' }, /external buffers/],
    [model => { model.json.buffers.push({ byteLength: 12, uri: 'external.bin' }) }, /external or non-fallback/],
    [model => { model.json.extensionsUsed.push('CUSTOM_geometry'); model.json.meshes[0].extensions = { CUSTOM_geometry: { accessor: 0 } } }, /unsupported extension CUSTOM_geometry/],
    [model => { model.json.nodes[1].children = [0] }, /hierarchy contains a cycle/],
    [model => { appendView(model, Buffer.from([1, 2, 3, 4])); model.json.bufferViews.pop() }, /unreferenced binary payload/],
    [model => { model.json.meshes[0].primitives[0].material = 999 }, /references missing materials/],
    [model => { model.json.materials[0].normalTexture = { index: 999 } }, /references missing textures/],
    [model => { model.json.nodes[1].matrix = Array(16).fill(0) }, /cannot mix matrix and TRS/],
  ]
  for (const [mutate, expected] of cases) {
    const model = fixture({ copies: 1 })
    mutate(model)
    await assert.rejects(optimizeModel(packGlb(model.json, model.binary)), expected)
  }
})

test('validator rejects codec corruption and changes to node, primitive, accessor, material, image and opaque metadata semantics', async () => {
  const model = fixture({ copies: 2 }), source = packGlb(model.json, model.binary)
  const { optimizedBytes } = await optimizeModel(source)
  const corrupted = unpackGlb(optimizedBytes)
  const extension = corrupted.json.bufferViews.find(view => view.extensions?.[MESHOPT]).extensions[MESHOPT]
  corrupted.binary[extension.byteOffset] = 0
  await assert.rejects(validateDecodedEquivalence(source, packGlb(corrupted.json, corrupted.binary)), /meshopt decoding failed/)
  const changes = [
    [artifact => { artifact.json.nodes[1].translation[0] += 1 }, /equivalence failed for nodes/],
    [artifact => { artifact.json.nodes[1].name = 'renamed' }, /equivalence failed for nodes/],
    [artifact => { artifact.json.nodes[0].children.reverse() }, /equivalence failed for nodes/],
    [artifact => { artifact.json.meshes[0].primitives[0].mode = 0 }, /equivalence failed for (meshes|nodes)/],
    [artifact => { artifact.json.accessors[0].max[0] += 1 }, /equivalence failed for (accessors|meshes|nodes)/],
    [artifact => { artifact.json.materials[0].extras.stock = 'changed' }, /equivalence failed for materials/],
    [artifact => { artifact.json.materials[0].pbrMetallicRoughness.baseColorFactor = [1, 0, 0, 1] }, /equivalence failed for materials/],
    [artifact => { const image = artifact.json.bufferViews[artifact.json.images[0].bufferView]; artifact.binary[image.byteOffset + 20] ^= 1 }, /equivalence failed for (bufferViews|images|textures)/],
    [artifact => { artifact.json.extras.author = 'changed' }, /equivalence failed for extras/],
  ]
  for (const [mutate, expected] of changes) {
    const artifact = unpackGlb(optimizedBytes)
    mutate(artifact)
    await assert.rejects(validateDecodedEquivalence(source, packGlb(artifact.json, artifact.binary)), expected)
  }
})
