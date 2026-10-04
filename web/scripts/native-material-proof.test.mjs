import test from 'node:test'
import assert from 'node:assert/strict'
import { deflateSync } from 'node:zlib'
import * as THREE from 'three'
import { parseNativeRawGLB, sha256, canonicalJson, createNativeByteReader } from './native-model-byte-proof.mjs'
import { createNativeMaterialProof, decodeNativeEmbeddedImage } from './native-material-proof.mjs'

// Real lossless PNG payloads, not a decoder stub. The scoped suite invokes the
// same installed ffmpeg executable used by the independent native consumer.
function crc32(bytes) {
  let value = 0xffffffff
  for (const byte of bytes) {
    value ^= byte
    for (let bit = 0; bit < 8; bit++) value = (value >>> 1) ^ (value & 1 ? 0xedb88320 : 0)
  }
  return (value ^ 0xffffffff) >>> 0
}
function png(rgba, width = 2, height = 2) {
  const chunk = (kind, bytes) => {
    const type = Buffer.from(kind), result = Buffer.alloc(bytes.length + 12)
    result.writeUInt32BE(bytes.length); type.copy(result, 4); bytes.copy(result, 8)
    result.writeUInt32BE(crc32(Buffer.concat([type, bytes])), result.length - 4)
    return result
  }
  const header = Buffer.alloc(13); header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 6
  const scanlines = Buffer.alloc(height * (width * 4 + 1))
  for (let row = 0; row < height; row++) Buffer.from(rgba.subarray(row * width * 4, (row + 1) * width * 4)).copy(scanlines, row * (width * 4 + 1) + 1)
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(scanlines)), chunk('IEND', Buffer.alloc(0))])
}
const opaquePixels = Uint8Array.from([27, 98, 216, 255, 203, 14, 6, 255, 8, 223, 89, 255, 231, 175, 42, 255])
function fixture({ alphaMode = 'OPAQUE', doubleSided = false, pixels = opaquePixels, materialIndex = 0 } = {}) {
  const position = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]), normal = new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]), uv = new Float32Array([0, 0, 1, 0, 0, 1]), index = new Uint32Array([0, 1, 2])
  const image = png(pixels), binary = Buffer.concat([Buffer.from(position.buffer), Buffer.from(normal.buffer), Buffer.from(uv.buffer), Buffer.from(index.buffer), image])
  const document = {
    asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ name: 'original', mesh: 0 }], buffers: [{ byteLength: binary.byteLength }],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: 36 }, { buffer: 0, byteOffset: 36, byteLength: 36 }, { buffer: 0, byteOffset: 72, byteLength: 24 }, { buffer: 0, byteOffset: 96, byteLength: 12 }, { buffer: 0, byteOffset: 108, byteLength: image.byteLength }],
    accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3' }, { bufferView: 1, componentType: 5126, count: 3, type: 'VEC3' }, { bufferView: 2, componentType: 5126, count: 3, type: 'VEC2' }, { bufferView: 3, componentType: 5125, count: 3, type: 'SCALAR' }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0, NORMAL: 1, TEXCOORD_0: 2 }, indices: 3, material: materialIndex }] }],
    materials: [{ name: 'raw-painted-part', alphaMode, alphaCutoff: 0.7, doubleSided, pbrMetallicRoughness: { baseColorFactor: [0.4, 0.7, 0.2, 1], metallicFactor: 0.35, roughnessFactor: 0.65, baseColorTexture: { index: 0 } } }, { name: 'other-raw-part', pbrMetallicRoughness: { baseColorFactor: [0.9, 0.1, 0.1, 1] } }],
    textures: [{ source: 0, sampler: 0 }], samplers: [{ magFilter: 9728, minFilter: 9728, wrapS: 10497, wrapT: 33071 }], images: [{ bufferView: 4, mimeType: 'image/png' }],
  }
  const text = Buffer.from(JSON.stringify(document)), jsonLength = Math.ceil(text.length / 4) * 4, binaryLength = Math.ceil(binary.length / 4) * 4
  const bytes = Buffer.alloc(28 + jsonLength + binaryLength); bytes.writeUInt32LE(0x46546c67); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(jsonLength, 12); bytes.writeUInt32LE(0x4e4f534a, 16); bytes.fill(0x20, 20, 20 + jsonLength); text.copy(bytes, 20)
  bytes.writeUInt32LE(binaryLength, 20 + jsonLength); bytes.writeUInt32LE(0x004e4942, 24 + jsonLength); binary.copy(bytes, 28 + jsonLength)
  const model = { ...parseNativeRawGLB(bytes), rawSHA256: sha256(bytes) }, primitive = model.primitives.get('original'), objects = new Map()
  const reader = createNativeByteReader({ get: hash => { assert.ok(objects.has(hash), 'Actual CAS object must exist'); return objects.get(hash) } })
  function object(bytes) { const hash = sha256(bytes); objects.set(hash, bytes); return hash }
  function span(bytes) { return { objectSHA256: object(bytes), objectByteLength: bytes.byteLength, byteOffset: 0, byteLength: bytes.byteLength, scalar: 'u8', components: 4, count: bytes.byteLength / 4 } }
  return { bytes, image, pixels, model, primitive, reader, objects, object, span }
}
async function proofFixture(options) {
  const data = fixture(options), proof = await createNativeMaterialProof({ rawGLBBytes: data.bytes, model: data.model, byteReader: data.reader }), expected = proof.expectedFor(data.primitive)
  const descriptor = { schemaVersion: 1, type: expected.type, name: expected.name, properties: structuredClone(expected.properties), clippingPlanes: [], textures: expected.textures.map(texture => ({
    ...texture.descriptor, source: { authority: 'original-renderer-gpu-texture-level0', width: 2, height: 2, encoding: 'rgba8', origin: 'texture-row0', bytes: data.span(data.pixels),
      sampler: { ...texture.gpuSampler, baseLevel: 0, maxLevel: 1000, compareMode: 0, compareFunc: 515 }, binding: { authority: 'actual-original-draw-sampler', uniform: texture.descriptor.slot, unit: 3, boundMatchesTexture: true },
      format: THREE.RGBAFormat, type: THREE.UnsignedByteType, internalFormat: null, premultiplyAlpha: false, unpackAlignment: 4 },
  })) }
  async function prove(actual = descriptor, options = {}) {
    const hash = data.object(Buffer.from(canonicalJson(actual)))
    return proof.prove({ primitive: data.primitive, actualDescriptors: [hash], requireDrawBinding: true, ...options })
  }
  return { ...data, proof, descriptor, prove }
}

test('real embedded PNG decode preserves every RGBA channel and independently measured dimensions', async () => {
  const source = png(opaquePixels), decoded = await decodeNativeEmbeddedImage(source, 'image/png')
  assert.deepEqual([...decoded.rgba], [...opaquePixels])
  assert.deepEqual([decoded.width, decoded.height], [2, 2])
  assert.equal(decoded.encodedSHA256, sha256(source))
})

test('opaque raw textured material closes source-image and actual GPU byte identity, even non-unit color factors', async () => {
  const data = await proofFixture(), result = await data.prove()
  assert.deepEqual(result.failures, []); assert.deepEqual(result.gaps, [])
  assert.equal(result.textureProofs[0].comparedByteCount, opaquePixels.byteLength)
  assert.equal(result.textureProofs[0].rawImageSHA256, sha256(data.image))
  assert.equal(result.independentlyOpaque, true)
  assert.equal(result.survivesAlpha(0, [0.5, 0.25, 0.25]), true)
})

test('changed actual texture texel and changed actual sampler binding cannot retain native material authority', async () => {
  const data = await proofFixture(), changed = structuredClone(data.descriptor), altered = data.pixels.slice(); altered[6] ^= 1
  changed.textures[0].source.bytes = data.span(altered)
  assert.ok((await data.prove(changed)).failures.some(reason => reason.includes('all original uploaded GPU texel bytes differ')))
  const misbound = structuredClone(data.descriptor); misbound.textures[0].source.binding.boundMatchesTexture = false
  assert.ok((await data.prove(misbound)).failures.some(reason => reason.includes('bound to a different actual texture')))
  const storageOnly = structuredClone(data.descriptor); storageOnly.textures[0].source.binding = { authority: 'renderer-installed-texture', uniform: null, unit: null, boundMatchesTexture: null }
  assert.ok((await data.prove(storageOnly)).gaps.some(reason => reason.includes('original active draw sampler binding absent')))
  assert.deepEqual((await data.prove(storageOnly, { requireDrawBinding: false })).gaps, [])
})

test('real material alpha, side, depth and material-root changes are rejected separately', async () => {
  const data = await proofFixture({ doubleSided: true })
  for (const [field, value] of [['opacity', 0.25], ['alphaTest', 0.8], ['transparent', true], ['side', THREE.BackSide], ['depthWrite', false], ['depthTest', false]]) {
    const changed = structuredClone(data.descriptor); changed.properties[field] = value
    assert.ok((await data.prove(changed)).failures.some(reason => reason.includes('numeric/alpha/side/depth/blending')), field)
  }
  const changedRoot = structuredClone(data.descriptor); changedRoot.name = 'other-raw-part'
  assert.ok((await data.prove(changedRoot)).failures.some(reason => reason.includes('material root/type/name')))
  const changedAssociation = fixture({ materialIndex: 1 }), other = await createNativeMaterialProof({ rawGLBBytes: changedAssociation.bytes, model: changedAssociation.model, byteReader: data.reader })
  assert.ok((await other.prove({ primitive: changedAssociation.primitive, actualDescriptors: [data.object(Buffer.from(canonicalJson(data.descriptor)))] })).failures.some(reason => reason.includes('material root/type/name')))
})

test('MASK uncertainty is not an opaque assumption; BLEND retains effective depthWrite false', async () => {
  const pixels = opaquePixels.slice(); pixels[3] = 0
  const mask = await proofFixture({ alphaMode: 'MASK', pixels }), masked = await mask.prove()
  assert.deepEqual(masked.failures, []); assert.deepEqual(masked.gaps, [])
  assert.equal(masked.independentlyOpaque, false)
  assert.equal(masked.survivesAlpha(0, [1, 0, 0]), null)
  assert.deepEqual(masked.alphaRangeAt(0, [1, 0, 0]), [0, 1])
  const blend = await proofFixture({ alphaMode: 'BLEND' }), blended = await blend.prove()
  assert.equal(blended.transparent, true); assert.equal(blended.depthWrite, false); assert.equal(blended.independentlyOpaque, false)
  const forcedDepth = structuredClone(blend.descriptor); forcedDepth.properties.depthWrite = true
  assert.ok((await blend.prove(forcedDepth)).failures.some(reason => reason.includes('numeric/alpha/side/depth/blending')))
})

test('canonical material CAS rejects open material schema and corrupted pixel object bytes', async () => {
  const data = await proofFixture(), open = { ...data.descriptor, accepted: true }
  await assert.rejects(data.prove(open), /exact closed keys/)
  const hash = data.descriptor.textures[0].source.bytes.objectSHA256, corrupt = data.pixels.slice(); corrupt[0] ^= 1; data.objects.set(hash, corrupt)
  await assert.rejects(data.prove(), /Actual byte hash mismatch/)
})
