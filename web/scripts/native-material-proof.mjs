import { spawn } from 'node:child_process'
import * as THREE from 'three'
import { canonicalJson, jsonDigest, sha256, requireClosed, integer, asBytes } from './native-model-byte-proof.mjs'
import { validateDecodedEquivalence } from './optimize-model.mjs'

// Immutable original assets are decoded once per independently hashed raw model
// and decoder executable, including when a consumer constructs a per-view proof.
const decodedImagesByRawIdentity = new Map()

const propertyNames = [
  'side', 'shadowSide', 'transparent', 'opacity', 'alphaTest', 'alphaHash', 'alphaToCoverage',
  'depthTest', 'depthWrite', 'depthFunc', 'colorWrite', 'blending', 'blendSrc', 'blendDst',
  'blendEquation', 'blendSrcAlpha', 'blendDstAlpha', 'blendEquationAlpha', 'blendAlpha', 'blendColor',
  'premultipliedAlpha', 'polygonOffset', 'polygonOffsetFactor', 'polygonOffsetUnits', 'clipIntersection',
  'clipShadows', 'vertexColors', 'flatShading', 'wireframe', 'wireframeLinewidth', 'roughness', 'metalness',
  'emissiveIntensity', 'toneMapped', 'visible', 'forceSinglePass', 'dithering', 'stencilWrite',
  'stencilWriteMask', 'stencilFunc', 'stencilRef', 'stencilFuncMask', 'stencilFail', 'stencilZFail',
  'stencilZPass', 'color', 'emissive', 'specular', 'normalScale', 'aoMapIntensity', 'lightMapIntensity',
  'bumpScale', 'displacementScale', 'displacementBias', 'normalMapType', 'envMapIntensity',
  'reflectivity', 'refractionRatio', 'clearcoat', 'clearcoatRoughness', 'clearcoatNormalScale',
  'ior', 'transmission', 'thickness', 'attenuationDistance', 'attenuationColor', 'specularIntensity',
  'specularColor', 'sheen', 'sheenColor', 'sheenRoughness', 'iridescence', 'iridescenceIOR',
  'iridescenceThicknessRange', 'anisotropy', 'anisotropyRotation', 'dispersion',
]
const filters = { 9728: THREE.NearestFilter, 9729: THREE.LinearFilter, 9984: THREE.NearestMipmapNearestFilter, 9985: THREE.LinearMipmapNearestFilter, 9986: THREE.NearestMipmapLinearFilter, 9987: THREE.LinearMipmapLinearFilter }
const wrappings = { 33071: THREE.ClampToEdgeWrapping, 33648: THREE.MirroredRepeatWrapping, 10497: THREE.RepeatWrapping }
const physicalExtensions = ['KHR_materials_clearcoat', 'KHR_materials_dispersion', 'KHR_materials_iridescence', 'KHR_materials_sheen', 'KHR_materials_transmission', 'KHR_materials_volume', 'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_anisotropy']
const textureKeys = ['slot', 'wrapS', 'wrapT', 'minFilter', 'magFilter', 'flipY', 'colorSpace', 'channel', 'offset', 'repeat', 'center', 'rotation', 'matrix', 'source']
const sourceKeys = ['authority', 'width', 'height', 'encoding', 'origin', 'bytes', 'sampler', 'binding', 'format', 'type', 'internalFormat', 'premultiplyAlpha', 'unpackAlignment']
const insist = (condition, message) => { if (!condition) throw new Error(message) }
const same = (a, b) => canonicalJson(a) === canonicalJson(b)
const bytesEqual = (a, b) => a.byteLength === b.byteLength && a.every((value, index) => value === b[index])
function propertyValue(value) {
  if (value === Infinity) return 'positive-infinity'
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Nonfinite original material value')
  if (value?.isColor) return [value.r, value.g, value.b]
  if (value?.toArray) return value.toArray()
  return Array.isArray(value) ? [...value] : value
}
function propertiesOf(material) {
  return Object.fromEntries(propertyNames.filter(name => material[name] !== undefined).map(name => [name, propertyValue(material[name])]))
}
function parseEmbeddedGLB(input) {
  const bytes = asBytes(input), view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  insist(bytes.length >= 28 && view.getUint32(0, true) === 0x46546c67 && view.getUint32(4, true) === 2 && view.getUint32(8, true) === bytes.length, 'Material authority requires complete GLB2 bytes')
  const jsonLength = view.getUint32(12, true), binaryHeader = 20 + jsonLength
  insist(jsonLength % 4 === 0 && binaryHeader + 8 <= bytes.length && view.getUint32(16, true) === 0x4e4f534a && view.getUint32(binaryHeader + 4, true) === 0x004e4942 && binaryHeader + 8 + view.getUint32(binaryHeader, true) === bytes.length, 'Material authority requires exact embedded JSON/BIN chunks')
  const document = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(20, binaryHeader))), binary = bytes.subarray(binaryHeader + 8)
  insist(document.asset?.version === '2.0' && document.buffers?.length === 1 && document.buffers[0].uri === undefined && document.buffers[0].byteLength <= binary.length, 'Material authority requires one real embedded buffer')
  function image(index) {
    integer(index, 'raw image index')
    const image = document.images?.[index], storage = document.bufferViews?.[image?.bufferView]
    insist(image && image.uri === undefined && storage && (storage.buffer ?? 0) === 0 && !storage.extensions && !storage.byteStride, 'Original image must be an actual embedded image buffer view')
    const offset = integer(storage.byteOffset ?? 0, 'image offset'), length = integer(storage.byteLength, 'image byte length', 1)
    insist(offset + length <= document.buffers[0].byteLength && ['image/png', 'image/jpeg'].includes(image.mimeType), 'Embedded native PNG/JPEG bounds or MIME type invalid')
    return { mimeType: image.mimeType, bytes: binary.subarray(offset, offset + length) }
  }
  return { document, image }
}

/** Header dimensions are checked independently against the decoder's exact output size. */
export function nativeEmbeddedImageDimensions(bytes, mimeType) {
  asBytes(bytes)
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (mimeType === 'image/png') {
    insist(bytes.length >= 33 && [137, 80, 78, 71, 13, 10, 26, 10].every((byte, index) => bytes[index] === byte) && view.getUint32(8) === 13 && view.getUint32(12) === 0x49484452, 'Actual PNG IHDR required')
    return { width: integer(view.getUint32(16), 'PNG width', 1), height: integer(view.getUint32(20), 'PNG height', 1) }
  }
  insist(mimeType === 'image/jpeg' && bytes[0] === 0xff && bytes[1] === 0xd8, 'Actual JPEG SOI required')
  let offset = 2
  while (offset + 4 <= bytes.length) {
    insist(bytes[offset++] === 0xff, 'Malformed JPEG marker stream')
    while (bytes[offset] === 0xff) offset++
    const marker = bytes[offset++]
    if (marker === 0xd9 || marker === 0xda) break
    if (marker === 0x01 || marker >= 0xd0 && marker <= 0xd7) continue
    insist(offset + 2 <= bytes.length, 'Truncated JPEG marker length')
    const length = view.getUint16(offset)
    insist(length >= 2 && offset + length <= bytes.length, 'Truncated JPEG marker payload')
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      insist(length >= 8, 'Truncated JPEG frame header')
      return { width: integer(view.getUint16(offset + 5), 'JPEG width', 1), height: integer(view.getUint16(offset + 3), 'JPEG height', 1) }
    }
    offset += length
  }
  throw new Error('Original JPEG has no complete frame dimensions')
}

/** Real decoder only: original encoded bytes go to ffmpeg stdin, raw RGBA stdout. */
export async function decodeNativeEmbeddedImage(bytes, mimeType, { ffmpegPath = 'ffmpeg' } = {}) {
  const { width, height } = nativeEmbeddedImageDimensions(bytes, mimeType), byteLength = width * height * 4
  insist(Number.isSafeInteger(byteLength), 'Decoded native image size exceeds safe storage')
  const rgba = await new Promise((resolve, reject) => {
    const decoder = spawn(ffmpegPath, ['-hide_banner', '-loglevel', 'error', '-threads', '1', '-f', 'image2pipe', '-i', 'pipe:0', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'], { stdio: ['pipe', 'pipe', 'pipe'] })
    const output = Buffer.allocUnsafe(byteLength), errors = []; let offset = 0, overflow = false
    decoder.stdout.on('data', chunk => {
      if (offset + chunk.byteLength > byteLength) { overflow = true; decoder.kill(); return }
      output.set(chunk, offset); offset += chunk.byteLength
    })
    decoder.stderr.on('data', chunk => errors.push(chunk))
    decoder.on('error', reject)
    decoder.stdin.on('error', error => { if (error.code !== 'EPIPE') reject(error) })
    decoder.on('close', code => {
      if (code !== 0 || overflow || offset !== byteLength) reject(new Error(`Real native image decoder failed (${code}; ${offset}/${byteLength} RGBA bytes): ${Buffer.concat(errors).toString('utf8')}`))
      else resolve(output)
    })
    decoder.stdin.end(bytes)
  })
  return { width, height, rgba, encodedSHA256: sha256(bytes), rgbaSHA256: sha256(rgba), mimeType }
}

function rawTexture(parsed, info, slot, colorSpace) {
  integer(info.index, 'raw texture index')
  const texture = parsed.document.textures?.[info.index]
  insist(texture && !texture.extensions, 'Original texture source must be core embedded glTF')
  const source = parsed.image(texture.source), sampler = texture.sampler === undefined ? {} : parsed.document.samplers?.[texture.sampler]
  insist(sampler, 'Raw texture references absent sampler')
  const actual = new THREE.Texture()
  actual.flipY = false; actual.colorSpace = colorSpace; actual.channel = info.texCoord ?? 0
  actual.wrapS = wrappings[sampler.wrapS ?? 10497]; actual.wrapT = wrappings[sampler.wrapT ?? 10497]
  actual.minFilter = filters[sampler.minFilter ?? 9987]; actual.magFilter = filters[sampler.magFilter ?? 9729]
  insist(actual.wrapS !== undefined && actual.wrapT !== undefined && actual.minFilter !== undefined && [9728, 9729].includes(sampler.magFilter ?? 9729), 'Invalid authentic texture sampler')
  const transform = info.extensions?.KHR_texture_transform
  insist(!info.extensions || Object.keys(info.extensions).every(name => name === 'KHR_texture_transform'), 'Unknown raw texture-info extension')
  if (transform) {
    if (transform.offset) actual.offset.fromArray(transform.offset)
    if (transform.scale) actual.repeat.fromArray(transform.scale)
    if (transform.rotation !== undefined) actual.rotation = transform.rotation
    if (transform.texCoord !== undefined) actual.channel = transform.texCoord
  }
  actual.updateMatrix()
  const descriptor = { slot, wrapS: actual.wrapS, wrapT: actual.wrapT, minFilter: actual.minFilter, magFilter: actual.magFilter, flipY: false, colorSpace: actual.colorSpace, channel: actual.channel,
    offset: actual.offset.toArray(), repeat: actual.repeat.toArray(), center: actual.center.toArray(), rotation: actual.rotation, matrix: actual.matrix.toArray() }
  return { descriptor, image: source, rawTextureIndex: info.index, rawSampler: sampler, imageSHA256: sha256(source.bytes), gpuSampler: { wrapS: sampler.wrapS ?? 10497, wrapT: sampler.wrapT ?? 10497, minFilter: sampler.minFilter ?? 9987, magFilter: sampler.magFilter ?? 9729 } }
}
function rawMaterialIdentity(parsed, material) {
  if (material === null) return null
  function resolve(value) {
    if (Array.isArray(value)) return value.map(resolve)
    if (!value || typeof value !== 'object') return value
    return Object.fromEntries(Object.entries(value).map(([key, child]) => {
      if (key.endsWith('Texture') && child && typeof child === 'object' && Object.hasOwn(child, 'index')) {
        const texture = parsed.document.textures[child.index], source = parsed.image(texture.source)
        return [key, { ...child, index: { ...texture, source: { mimeType: source.mimeType, encodedSHA256: sha256(source.bytes), byteLength: source.bytes.byteLength }, ...(texture.sampler === undefined ? {} : { sampler: parsed.document.samplers[texture.sampler] }) } }]
      }
      return [key, resolve(child)]
    }))
  }
  return resolve(material)
}
function expectedMaterial(parsed, primitive) {
  const node = parsed.document.nodes?.[primitive.nodeIndex], rawPrimitive = parsed.document.meshes?.[primitive.meshIndex]?.primitives?.[primitive.primitiveIndex]
  insist(node && node.mesh === primitive.meshIndex && rawPrimitive, 'Material association differs from actual raw node/mesh/primitive ordinal')
  const raw = rawPrimitive.material === undefined ? null : parsed.document.materials?.[rawPrimitive.material]
  insist(raw !== undefined, 'Raw primitive material root absent')
  const definition = raw ?? {}, extensions = definition.extensions ?? {}, unknown = Object.keys(extensions).filter(name => ![...physicalExtensions, 'KHR_materials_unlit', 'KHR_materials_emissive_strength', 'EXT_materials_bump'].includes(name))
  insist(!unknown.length, `Original material extension needs genuine mapping: ${unknown.join(',')}`)
  const unlit = Boolean(extensions.KHR_materials_unlit), physical = !unlit && physicalExtensions.some(name => extensions[name])
  const material = unlit ? new THREE.MeshBasicMaterial() : physical ? new THREE.MeshPhysicalMaterial() : new THREE.MeshStandardMaterial()
  material.name = definition.name ?? ''
  const pbr = definition.pbrMetallicRoughness ?? {}, base = pbr.baseColorFactor ?? [1, 1, 1, 1]
  insist(base.length === 4 && base.every(Number.isFinite), 'Raw base-color factor invalid')
  material.color.setRGB(base[0], base[1], base[2], THREE.LinearSRGBColorSpace); material.opacity = base[3]
  const alphaMode = definition.alphaMode ?? 'OPAQUE'
  insist(['OPAQUE', 'MASK', 'BLEND'].includes(alphaMode), 'Unknown authentic alpha mode')
  if (definition.doubleSided === true) material.side = THREE.DoubleSide
  material.transparent = alphaMode === 'BLEND'; material.depthWrite = alphaMode !== 'BLEND'
  if (alphaMode === 'MASK') material.alphaTest = definition.alphaCutoff ?? 0.5
  const textures = [], add = (slot, info, colorSpace = THREE.NoColorSpace) => { if (info) textures.push(rawTexture(parsed, info, slot, colorSpace)) }
  add('map', pbr.baseColorTexture, THREE.SRGBColorSpace)
  if (!unlit) {
    material.metalness = pbr.metallicFactor ?? 1; material.roughness = pbr.roughnessFactor ?? 1
    add('metalnessMap', pbr.metallicRoughnessTexture); add('roughnessMap', pbr.metallicRoughnessTexture)
    material.emissive.fromArray(definition.emissiveFactor ?? [0, 0, 0])
    add('normalMap', definition.normalTexture); add('aoMap', definition.occlusionTexture); add('emissiveMap', definition.emissiveTexture, THREE.SRGBColorSpace)
    if (definition.normalTexture) material.normalScale.setScalar(definition.normalTexture.scale ?? 1)
    if (definition.occlusionTexture?.strength !== undefined) material.aoMapIntensity = definition.occlusionTexture.strength
    if (extensions.KHR_materials_emissive_strength) material.emissiveIntensity = extensions.KHR_materials_emissive_strength.emissiveStrength ?? 1
    const extensionMappings = {
      KHR_materials_clearcoat: { values: { clearcoatFactor: 'clearcoat', clearcoatRoughnessFactor: 'clearcoatRoughness' }, textures: { clearcoatTexture: 'clearcoatMap', clearcoatRoughnessTexture: 'clearcoatRoughnessMap', clearcoatNormalTexture: 'clearcoatNormalMap' } },
      KHR_materials_dispersion: { values: { dispersion: 'dispersion' } },
      KHR_materials_iridescence: { values: { iridescenceFactor: 'iridescence', iridescenceIor: 'iridescenceIOR' }, textures: { iridescenceTexture: 'iridescenceMap', iridescenceThicknessTexture: 'iridescenceThicknessMap' } },
      KHR_materials_sheen: { values: { sheenRoughnessFactor: 'sheenRoughness' }, colors: { sheenColorFactor: 'sheenColor' }, textures: { sheenColorTexture: 'sheenColorMap', sheenRoughnessTexture: 'sheenRoughnessMap' } },
      KHR_materials_transmission: { values: { transmissionFactor: 'transmission' }, textures: { transmissionTexture: 'transmissionMap' } },
      KHR_materials_volume: { values: { thicknessFactor: 'thickness', attenuationDistance: 'attenuationDistance' }, colors: { attenuationColor: 'attenuationColor' }, textures: { thicknessTexture: 'thicknessMap' } },
      KHR_materials_ior: { values: { ior: 'ior' } },
      KHR_materials_specular: { values: { specularFactor: 'specularIntensity' }, colors: { specularColorFactor: 'specularColor' }, textures: { specularTexture: 'specularIntensityMap', specularColorTexture: 'specularColorMap' } },
      KHR_materials_anisotropy: { values: { anisotropyStrength: 'anisotropy', anisotropyRotation: 'anisotropyRotation' }, textures: { anisotropyTexture: 'anisotropyMap' } },
      EXT_materials_bump: { values: { bumpFactor: 'bumpScale' }, textures: { bumpTexture: 'bumpMap' } },
    }
    for (const [name, mapping] of Object.entries(extensionMappings)) {
      const extension = extensions[name]
      if (!extension) continue
      for (const [rawKey, key] of Object.entries(mapping.values ?? {})) if (extension[rawKey] !== undefined) material[key] = extension[rawKey]
      for (const [rawKey, key] of Object.entries(mapping.colors ?? {})) if (extension[rawKey]) material[key].fromArray(extension[rawKey])
      for (const [rawKey, slot] of Object.entries(mapping.textures ?? {})) add(slot, extension[rawKey], ['sheenColorMap', 'specularColorMap'].includes(slot) ? THREE.SRGBColorSpace : THREE.NoColorSpace)
    }
    if (extensions.KHR_materials_sheen) { material.sheen = 1; material.sheenRoughness = extensions.KHR_materials_sheen.sheenRoughnessFactor ?? 0 }
    if (extensions.KHR_materials_iridescence) material.iridescenceThicknessRange = [extensions.KHR_materials_iridescence.iridescenceThicknessMinimum ?? 100, extensions.KHR_materials_iridescence.iridescenceThicknessMaximum ?? 400]
    if (extensions.KHR_materials_clearcoat?.clearcoatNormalTexture?.scale !== undefined) material.clearcoatNormalScale.setScalar(extensions.KHR_materials_clearcoat.clearcoatNormalTexture.scale)
  }
  // These are the installed loader's real primitive adaptations, not CPU maps.
  material.vertexColors = primitive.attributes.COLOR_0 !== undefined
  if (!primitive.attributes.TANGENT) {
    if (material.normalScale) material.normalScale.y *= -1
    if (material.clearcoatNormalScale) material.clearcoatNormalScale.y *= -1
  }
  const identity = rawMaterialIdentity(parsed, raw)
  return { schemaVersion: 1, type: material.type, name: material.name, properties: propertiesOf(material), clippingPlanes: [], textures, alphaMode, rawMaterial: identity, rawMaterialSHA256: jsonDigest(identity), rawMaterialIndex: rawPrimitive.material ?? null }
}
function attributeComponent(attribute, index, component) {
  let value = attribute.array[index * attribute.itemSize + component]
  if (!attribute.normalized) return value
  if (attribute.componentType === 5121) return value / 255
  if (attribute.componentType === 5123) return value / 65535
  if (attribute.componentType === 5120) return Math.max(value / 127, -1)
  if (attribute.componentType === 5122) return Math.max(value / 32767, -1)
  return value
}
function wrapIndex(index, size, wrapping) {
  if (wrapping === 33071) return Math.min(size - 1, Math.max(0, index))
  if (wrapping === 33648) { const repeat = ((index % (size * 2)) + size * 2) % (size * 2); return repeat < size ? repeat : size * 2 - 1 - repeat }
  return ((index % size) + size) % size
}
function alphaFunctions(primitive, expected, images) {
  const texture = expected.textures.find(texture => texture.descriptor.slot === 'map'), opacity = expected.properties.opacity
  const vertexAlpha = (triangle, barycentric) => {
    const colors = primitive.attributes.COLOR_0
    if (!colors || colors.itemSize < 4) return 1
    return barycentric.reduce((sum, weight, corner) => sum + weight * attributeComponent(colors, primitive.index[triangle * 3 + corner], 3), 0)
  }
  const at = (triangle, barycentric) => {
    integer(triangle, 'alpha triangle'); insist(triangle * 3 + 2 < primitive.index.length && Array.isArray(barycentric) && barycentric.length === 3 && barycentric.every(Number.isFinite), 'Actual triangle and finite barycentric alpha sample required')
    let alpha = opacity * vertexAlpha(triangle, barycentric)
    if (!texture) return alpha
    const descriptor = texture.descriptor, attribute = primitive.attributes[descriptor.channel === 0 ? 'TEXCOORD_0' : `TEXCOORD_${descriptor.channel}`], image = images.get(texture.imageSHA256)
    insist(attribute && attribute.itemSize === 2 && image, 'Authentic UV/image data required for alpha sample')
    const uv = [0, 0]
    for (let corner = 0; corner < 3; corner++) for (let axis = 0; axis < 2; axis++) uv[axis] += barycentric[corner] * attributeComponent(attribute, primitive.index[triangle * 3 + corner], axis)
    const matrix = descriptor.matrix, u = matrix[0] * uv[0] + matrix[3] * uv[1] + matrix[6], v = matrix[1] * uv[0] + matrix[4] * uv[1] + matrix[7]
    const sample = (x, y) => image.rgba[(wrapIndex(y, image.height, texture.gpuSampler.wrapT) * image.width + wrapIndex(x, image.width, texture.gpuSampler.wrapS)) * 4 + 3] / 255
    if (texture.gpuSampler.magFilter === 9728) alpha *= sample(Math.floor(u * image.width), Math.floor(v * image.height))
    else {
      const x = u * image.width - 0.5, y = v * image.height - 0.5, ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy
      alpha *= (sample(ix, iy) * (1 - fx) + sample(ix + 1, iy) * fx) * (1 - fy) + (sample(ix, iy + 1) * (1 - fx) + sample(ix + 1, iy + 1) * fx) * fy
    }
    return alpha
  }
  // No derivatives/LOD are invented. The complete native alpha extrema are a
  // conservative enclosure for every legal mip/filter sample; opaque textures
  // close exactly, while mask/blend consumers may refine with actual GPU LOD.
  let minimum = 1, maximum = 1
  if (texture) {
    const image = images.get(texture.imageSHA256); minimum = 1; maximum = 0
    if (!image) return { alphaAt: () => { throw new Error('Original alpha image decode unavailable') }, alphaRangeAt: () => [0, 1], survivesAlpha: () => null, independentlyOpaque: false }
    for (let offset = 3; offset < image.rgba.length; offset += 4) { minimum = Math.min(minimum, image.rgba[offset] / 255); maximum = Math.max(maximum, image.rgba[offset] / 255) }
  }
  const range = (triangle, barycentric) => { const factor = opacity * vertexAlpha(triangle, barycentric); return [factor * minimum, factor * maximum] }
  const survives = (triangle, barycentric) => {
    if (expected.alphaMode === 'OPAQUE') return true
    const [low, high] = range(triangle, barycentric), cutoff = expected.properties.alphaTest
    if (expected.alphaMode === 'MASK') return low >= cutoff ? true : high < cutoff ? false : null
    return high === 0 ? false : low > 0 ? true : null
  }
  const colors = primitive.attributes.COLOR_0
  let colorOpaque = true
  if (colors?.itemSize >= 4) for (let index = 0; index < colors.count; index++) if (attributeComponent(colors, index, 3) !== 1) { colorOpaque = false; break }
  return { alphaAt: at, alphaRangeAt: range, survivesAlpha: survives, independentlyOpaque: expected.alphaMode === 'OPAQUE' || expected.alphaMode === 'MASK' && opacity * minimum >= expected.properties.alphaTest && colorOpaque }
}

/**
 * Independent material authority. The original CPU oracle is deliberately NOT
 * consulted: its real Node GLTFLoader blob-image warning does not prove maps.
 * Associations and image/sampler signatures come from original GLB JSON/BIN;
 * installed Three constructors provide current code defaults, never image data.
 */
export async function createNativeMaterialProof({ rawGLBBytes, deliveryGLBBytes, model, byteReader, ffmpegPath = 'ffmpeg' }) {
  const parsed = parseEmbeddedGLB(rawGLBBytes)
  insist(model && sha256(rawGLBBytes) === model.rawSHA256 && same(parsed.document, model.document), 'Material proof raw bytes differ from independently admitted model')
  if (deliveryGLBBytes) {
    insist(sha256(deliveryGLBBytes) === model.deliverySHA256 && deliveryGLBBytes.byteLength === model.deliveryByteLength, 'Material proof delivery byte identity differs')
    await validateDecodedEquivalence(rawGLBBytes, deliveryGLBBytes)
  }
  const assetKey = canonicalJson([model.rawSHA256, ffmpegPath])
  if (!decodedImagesByRawIdentity.has(assetKey)) decodedImagesByRawIdentity.set(assetKey, new Map())
  const expectations = new Map(), decoded = decodedImagesByRawIdentity.get(assetKey), images = new Map(), results = new Map()
  function expectedFor(primitive) {
    const key = `${primitive.nodeIndex}/${primitive.meshIndex}/${primitive.primitiveIndex}/${Object.keys(primitive.attributes).sort().join(',')}`
    if (!expectations.has(key)) expectations.set(key, expectedMaterial(parsed, primitive))
    return expectations.get(key)
  }
  async function imageFor(texture) {
    if (!decoded.has(texture.imageSHA256)) decoded.set(texture.imageSHA256, decodeNativeEmbeddedImage(texture.image.bytes, texture.image.mimeType, { ffmpegPath }))
    const image = await decoded.get(texture.imageSHA256)
    images.set(texture.imageSHA256, image)
    return image
  }
  async function prove({ primitive, actualDescriptors, reader = byteReader, requireDrawBinding = false }) {
    insist(reader && Array.isArray(actualDescriptors), 'Actual material-slot CAS descriptors and independent byte reader required')
    const expected = expectedFor(primitive), key = `${expected.rawMaterialSHA256}/${primitive.rawPrimitiveSHA256}/${requireDrawBinding}/${actualDescriptors.map(value => typeof value === 'string' ? value : jsonDigest(value)).join('/')}`
    if (results.has(key)) return results.get(key)
    const gaps = [], failures = [], textureProofs = [], descriptorHashes = []
    if (actualDescriptors.length !== 1) failures.push(`${primitive.path}: original raw primitive must retain its one actual material slot`)
    for (const candidate of actualDescriptors) {
      const actual = typeof candidate === 'string' ? await reader.json(candidate) : candidate
      descriptorHashes.push(typeof candidate === 'string' ? candidate : jsonDigest(actual))
      requireClosed(actual, ['schemaVersion', 'type', 'name', 'properties', 'clippingPlanes', 'textures'], 'actual material slot')
      insist(Array.isArray(actual.textures) && Array.isArray(actual.clippingPlanes), 'Material texture/clipping arrays required')
      requireClosed(actual.properties, Object.keys(expected.properties), 'actual material properties')
      if (actual.schemaVersion !== 1 || actual.type !== expected.type || actual.name !== expected.name) failures.push(`${primitive.path}: actual material root/type/name differs from raw association`)
      if (!same(actual.properties, expected.properties)) failures.push(`${primitive.path}: actual original material numeric/alpha/side/depth/blending properties differ`)
      if (!same(actual.clippingPlanes, expected.clippingPlanes)) failures.push(`${primitive.path}: actual material clipping planes differ from authentic current native load`)
      const seen = new Set()
      for (const texture of actual.textures) {
        requireClosed(texture, textureKeys, 'actual material texture')
        insist(!seen.has(texture.slot), 'Duplicate actual material texture slot'); seen.add(texture.slot)
        const original = expected.textures.find(value => value.descriptor.slot === texture.slot)
        if (!original) { failures.push(`${primitive.path}: ${texture.slot} is not an original embedded material texture (environment needs independent current-code authority)`); continue }
        const { source, ...metadata } = texture
        if (!same(metadata, original.descriptor)) failures.push(`${primitive.path}: ${texture.slot} actual sampler/UV/color-space metadata differs`)
        if (source?.authority === 'unmeasured-original-gpu-texture') {
          requireClosed(source, ['authority', 'reason'], 'unmeasured original GPU texture'); insist(typeof source.reason === 'string' && source.reason.length > 0, 'Actual unmeasured texture reason required')
          gaps.push(`${primitive.path}: ${texture.slot} ${source.reason}`); continue
        }
        requireClosed(source, sourceKeys, 'actual GPU texture source')
        requireClosed(source.sampler, ['wrapS', 'wrapT', 'minFilter', 'magFilter', 'baseLevel', 'maxLevel', 'compareMode', 'compareFunc'], 'actual GPU texture sampler')
        requireClosed(source.binding, ['authority', 'uniform', 'unit', 'boundMatchesTexture'], 'actual GPU texture binding')
        if (source.authority !== 'original-renderer-gpu-texture-level0' || source.encoding !== 'rgba8' || source.origin !== 'texture-row0' || source.format !== THREE.RGBAFormat || source.type !== THREE.UnsignedByteType || source.internalFormat !== null || source.premultiplyAlpha !== false || source.unpackAlignment !== 4) failures.push(`${primitive.path}: ${texture.slot} original GPU storage/readback semantics differ`)
        integer(source.width, 'actual GPU texture width', 1); integer(source.height, 'actual GPU texture height', 1)
        for (const [name, value] of Object.entries(source.sampler)) integer(value, `actual GPU sampler ${name}`)
        for (const [name, value] of Object.entries(original.gpuSampler)) if (source.sampler[name] !== value) failures.push(`${primitive.path}: ${texture.slot} actual GL ${name} differs from raw sampler`)
        if (source.sampler.baseLevel !== 0 || source.sampler.maxLevel !== 1000 || source.sampler.compareMode !== 0 || source.sampler.compareFunc !== 515) failures.push(`${primitive.path}: ${texture.slot} actual GL base/mipmap/compare sampling differs from the installed current loader`)
        if (source.binding.authority === 'actual-original-draw-sampler') {
          integer(source.binding.unit, 'actual sampler unit')
          if (source.binding.uniform !== texture.slot || source.binding.boundMatchesTexture !== true) failures.push(`${primitive.path}: ${texture.slot} original draw sampler is bound to a different actual texture`)
        } else if (source.binding.authority !== 'renderer-installed-texture' || source.binding.uniform !== null || source.binding.unit !== null || source.binding.boundMatchesTexture !== null) failures.push(`${primitive.path}: invalid original texture binding authority`)
        else if (requireDrawBinding) gaps.push(`${primitive.path}: ${texture.slot} original active draw sampler binding absent; installed storage alone is not draw authority`)
        let image
        try { image = await imageFor(original) } catch (error) { gaps.push(`${primitive.path}: ${texture.slot} independent original image decode failed: ${error.message}`); continue }
        const bytes = await reader.span(source.bytes, { scalar: 'u8', components: 4, count: source.width * source.height })
        if (source.width !== image.width || source.height !== image.height || !bytesEqual(bytes, image.rgba)) failures.push(`${primitive.path}: ${texture.slot} all original uploaded GPU texel bytes differ from independently decoded embedded image`)
        textureProofs.push({ slot: texture.slot, rawTextureIndex: original.rawTextureIndex, rawImageSHA256: image.encodedSHA256, decodedRGBA8SHA256: image.rgbaSHA256, actualGPUObjectSHA256: source.bytes.objectSHA256, width: image.width, height: image.height, comparedByteCount: image.rgba.byteLength, bindingAuthority: source.binding.authority })
      }
      for (const original of expected.textures) if (!seen.has(original.descriptor.slot)) failures.push(`${primitive.path}: original ${original.descriptor.slot} texture omitted`)
    }
    const semantics = alphaFunctions(primitive, expected, images), properties = expected.properties
    const result = { gaps, failures, side: properties.side, sideName: properties.side === THREE.DoubleSide ? 'double' : properties.side === THREE.BackSide ? 'back' : 'front', alphaMode: expected.alphaMode,
      clippingPlanes: expected.clippingPlanes, depthWrite: properties.depthWrite, depthTest: properties.depthTest, depthFunc: properties.depthFunc, alphaTest: properties.alphaTest,
      opacity: properties.opacity, colorWrite: properties.colorWrite, transparent: properties.transparent, blending: properties.blending, rawMaterialSHA256: expected.rawMaterialSHA256,
      materialSlotsSHA256: descriptorHashes, textureProofs, ...semantics }
    results.set(key, result); return result
  }
  return { expectedFor, prove }
}
