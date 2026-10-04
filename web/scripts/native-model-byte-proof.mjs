import { createHash } from 'node:crypto'
import { Matrix4, Quaternion, Vector3 } from 'three'
import { validateDecodedEquivalence } from './optimize-model.mjs'
import { canonicalJson } from '../native-qualification-contract.mjs'
export { canonicalJson } from '../native-qualification-contract.mjs'

export const CURRENT_NATIVE_RAW_SHA256 = '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c'
export const CURRENT_NATIVE_DELIVERY_SHA256 = '81750ae4c422b973dfd647df4e22f3088933003e39ff41c54563d780eb33fa65'
export const CURRENT_NATIVE_DELIVERY_BYTES = 41071140
export const SPARE_SOURCE_PATH = 'harmonic-analyzer/paper-drive/transgear-removable-3'
export const SPARE_INSTANCE_PATHS = Object.freeze([`${SPARE_SOURCE_PATH}@upper`, `${SPARE_SOURCE_PATH}@crank`])
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
export const jsonDigest = value => sha256(canonicalJson(value))
export function requireClosed(value, keys, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key))) throw new TypeError(`${label}: exact closed keys required`)
}
export function integer(value, label, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) throw new RangeError(`${label}: integer >= ${minimum} required`)
  return value
}
export function requireSHA(value, label) {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) throw new TypeError(`${label}: SHA256 required`)
  return value
}
export function asBytes(value) {
  if (!(value instanceof Uint8Array)) throw new TypeError('Actual Uint8Array bytes required')
  return value
}
const scalarBytes = { f32le: 4, f64le: 8, u32le: 4, u8: 1 }
const constructors = { f32le: Float32Array, f64le: Float64Array, u32le: Uint32Array, u8: Uint8Array }
/** One adjudication's immutable CAS reads. Each fetched object is independently hashed. */
export function createNativeByteReader(byteStore) {
  const objects = new Map()
  async function object(hash) {
    requireSHA(hash, 'objectSHA256')
    if (!objects.has(hash)) {
      const bytes = asBytes(await byteStore.get(hash))
      if (sha256(bytes) !== hash) throw new Error(`Actual byte hash mismatch: ${hash}`)
      objects.set(hash, bytes)
    }
    return objects.get(hash)
  }
  async function span(value, shape = {}) {
    requireClosed(value, ['objectSHA256', 'objectByteLength', 'byteOffset', 'byteLength', 'scalar', 'components', 'count'], 'span')
    const size = scalarBytes[value.scalar]
    if (!size) throw new TypeError('Unsupported little-endian scalar')
    for (const key of ['objectByteLength', 'byteOffset', 'byteLength', 'count']) integer(value[key], `span.${key}`)
    integer(value.components, 'span.components', 1)
    if (value.byteLength !== value.count * value.components * size || value.byteOffset % size || value.byteOffset + value.byteLength > value.objectByteLength) throw new RangeError('Truncated, misaligned, or incorrectly shaped span')
    for (const [key, expected] of Object.entries(shape)) if (value[key] !== expected) throw new TypeError(`span.${key}: expected ${expected}`)
    const bytes = await object(value.objectSHA256)
    if (bytes.byteLength !== value.objectByteLength) throw new RangeError('Actual object length differs')
    return bytes.subarray(value.byteOffset, value.byteOffset + value.byteLength)
  }
  async function numbers(value, shape = {}) {
    const bytes = await span(value, shape), Constructor = constructors[value.scalar]
    // Buffer offsets need not have the scalar alignment of the addressed span.
    const array = bytes.byteOffset % Constructor.BYTES_PER_ELEMENT ? new Constructor(bytes.slice().buffer) : new Constructor(bytes.buffer, bytes.byteOffset, bytes.byteLength / Constructor.BYTES_PER_ELEMENT)
    if (value.scalar.startsWith('f') && array.some(number => !Number.isFinite(number))) throw new RangeError('Nonfinite actual scalar bytes')
    return array
  }
  async function json(hash) {
    const bytes = await object(hash), value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
    if (canonicalJson(value) !== new TextDecoder().decode(bytes)) throw new TypeError('Content-addressed JSON must be canonical')
    return value
  }
  return { object, span, numbers, json }
}

/** Decode raw accessors independently; never use parser associations as byte authority. */
export function parseNativeRawGLB(input) {
  const bytes = asBytes(input), view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (bytes.length < 28 || view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== bytes.length) throw new Error('Exact GLB2 header required')
  const jsonLength = view.getUint32(12, true), binHeader = 20 + jsonLength
  if (jsonLength % 4 || binHeader + 8 > bytes.length || view.getUint32(16, true) !== 0x4e4f534a || view.getUint32(binHeader + 4, true) !== 0x004e4942 || binHeader + 8 + view.getUint32(binHeader, true) !== bytes.length) throw new Error('Exact JSON/BIN GLB chunks required')
  const document = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(20, binHeader)))
  const binary = bytes.subarray(binHeader + 8)
  if (document.asset?.version !== '2.0' || document.buffers?.length !== 1 || document.buffers[0].uri !== undefined || document.buffers[0].byteLength > binary.length) throw new Error('Raw embedded glTF2 required')
  const widths = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }, ctypes = { 5120: Int8Array, 5121: Uint8Array, 5122: Int16Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array }, accessors = new Map()
  function accessor(index) {
    integer(index, 'accessor index')
    if (accessors.has(index)) return accessors.get(index)
    const entry = document.accessors?.[index], storage = document.bufferViews?.[entry?.bufferView], Constructor = ctypes[entry?.componentType], components = widths[entry?.type]
    if (!entry || !storage || !Constructor || !components || entry.sparse || entry.extensions || storage.extensions || (storage.buffer ?? 0) !== 0) throw new Error('Unsupported raw accessor')
    const count = integer(entry.count, 'accessor count', 1), width = components * Constructor.BYTES_PER_ELEMENT, stride = storage.byteStride ?? width, offset = entry.byteOffset ?? 0, start = storage.byteOffset ?? 0
    integer(stride, 'accessor stride', width); integer(offset, 'accessor offset'); integer(start, 'buffer view offset'); integer(storage.byteLength, 'buffer view length', 1)
    if (offset % Constructor.BYTES_PER_ELEMENT || start % Constructor.BYTES_PER_ELEMENT || stride % Constructor.BYTES_PER_ELEMENT || offset + (count - 1) * stride + width > storage.byteLength || start + storage.byteLength > document.buffers[0].byteLength) throw new Error('Raw accessor exceeds its own buffer view')
    let packed = binary.subarray(start + offset, start + offset + count * width)
    if (stride !== width) {
      packed = new Uint8Array(count * width)
      for (let i = 0; i < count; i++) packed.set(binary.subarray(start + offset + i * stride, start + offset + i * stride + width), i * width)
    }
    const array = packed.byteOffset % Constructor.BYTES_PER_ELEMENT ? new Constructor(packed.slice().buffer) : new Constructor(packed.buffer, packed.byteOffset, count * components)
    if (entry.componentType === 5126 && array.some(value => !Number.isFinite(value))) throw new Error('Nonfinite raw attribute, including hidden geometry')
    const result = { array, bytes: packed, count, itemSize: components, componentType: entry.componentType, normalized: entry.normalized ?? false }
    accessors.set(index, result)
    return result
  }
  const nodes = new Map(), primitives = new Map(), visiting = new Set(), visited = new Set()
  function visit(index, prefix, parent) {
    integer(index, 'node index')
    const node = document.nodes?.[index]
    if (!node || visiting.has(index) || visited.has(index) || typeof node.name !== 'string' || !node.name || node.name.includes('/')) throw new Error('Ambiguous or cyclic raw ancestry')
    visiting.add(index); visited.add(index)
    const path = prefix ? `${prefix}/${node.name}` : node.name
    if (nodes.has(path)) throw new Error(`Duplicate raw path ${path}`)
    let local
    if (node.matrix) {
      if (node.matrix.length !== 16 || node.matrix.some(value => !Number.isFinite(value))) throw new Error('Invalid raw matrix')
      local = new Matrix4().fromArray(node.matrix)
    } else {
      const t = node.translation ?? [0, 0, 0], r = node.rotation ?? [0, 0, 0, 1], s = node.scale ?? [1, 1, 1]
      if (t.length !== 3 || r.length !== 4 || s.length !== 3 || [...t, ...r, ...s].some(value => !Number.isFinite(value))) throw new Error('Invalid raw TRS')
      local = new Matrix4().compose(new Vector3().fromArray(t), new Quaternion().fromArray(r), new Vector3().fromArray(s))
    }
    const world = new Matrix4().multiplyMatrices(parent, local), restMatrixF64 = new Float64Array(world.elements)
    nodes.set(path, { path, nodeIndex: index, node, restMatrixF64 })
    if (node.mesh !== undefined) {
      const mesh = document.meshes?.[node.mesh]
      if (!mesh || node.skin !== undefined || node.weights || mesh.weights || !mesh.primitives.length) throw new Error('Current native raw node must own unskinned original primitives')
      for (const [primitiveIndex, primitive] of mesh.primitives.entries()) {
        if ((primitive.mode ?? 4) !== 4 || primitive.targets || Object.keys(primitive).some(key => !['mode', 'attributes', 'indices', 'material'].includes(key))) throw new Error('Unsupported raw primitive')
        const attributes = Object.fromEntries(Object.entries(primitive.attributes).sort().map(([name, id]) => [name, accessor(id)])), position = attributes.POSITION, normal = attributes.NORMAL, indices = accessor(primitive.indices)
        if (!position || !normal || [position, normal].some(a => a.componentType !== 5126 || a.normalized || a.itemSize !== 3) || Object.values(attributes).some(a => a.count !== position.count)) throw new Error('Full compatible native vertex attributes required')
        if (indices.itemSize !== 1 || indices.normalized || ![5121, 5123, 5125].includes(indices.componentType) || indices.count % 3 || indices.array.some(value => value >= position.count)) throw new Error('Invalid full native triangle indices')
        const canonicalIndices = Uint32Array.from(indices.array), material = primitive.material === undefined ? null : document.materials[primitive.material]
        const seal = { path, nodeIndex: index, meshIndex: node.mesh, primitiveIndex, mode: 4, attributes: Object.fromEntries(Object.entries(attributes).map(([name, a]) => [name, { componentType: a.componentType, normalized: a.normalized, components: a.itemSize, count: a.count, sha256: sha256(a.bytes) }])), indicesSHA256: sha256(new Uint8Array(canonicalIndices.buffer)), material }
        // A multi-material node's primitive identities are raw ordinal keys,
        // not invented renderer child paths. The frozen real CPU loader joins
        // its actual child paths to these node/mesh/primitive associations.
        const primitiveKey = mesh.primitives.length === 1 ? path : `${path}#primitive:${primitiveIndex}`
        primitives.set(primitiveKey, { path: primitiveKey, rawPath: path, nodeIndex: index, meshIndex: node.mesh, primitiveIndex, attributes, positions: position.array, normals: normal.array, index: canonicalIndices, restMatrixF64, rawPrimitiveSHA256: jsonDigest(seal), material, instanceOf: null })
      }
    }
    for (const child of node.children ?? []) visit(child, path, world)
    visiting.delete(index)
  }
  for (const index of document.scenes?.[document.scene ?? 0]?.nodes ?? []) visit(index, '', new Matrix4())
  if (!nodes.size || !primitives.size) throw new Error('Missing raw scene')
  return { document, nodes, primitives, accessor }
}

export async function proveCurrentNativeModelBytes(rawGLBBytes, deliveryGLBBytes) {
  const raw = asBytes(rawGLBBytes), delivery = asBytes(deliveryGLBBytes)
  if (sha256(raw) !== CURRENT_NATIVE_RAW_SHA256 || sha256(delivery) !== CURRENT_NATIVE_DELIVERY_SHA256 || delivery.byteLength !== CURRENT_NATIVE_DELIVERY_BYTES) throw new Error('Actual model bytes differ from admitted current462 source/delivery')
  const equivalence = await validateDecodedEquivalence(raw, delivery)
  const parsed = parseNativeRawGLB(raw)
  if (parsed.primitives.size !== 460 || parsed.nodes.size !== 479) throw new Error('Raw460 / named479 census differs')
  const original = parsed.primitives.get(SPARE_SOURCE_PATH)
  if (!original) throw new Error('Authentic spare sprocket ancestor missing')
  for (const path of SPARE_INSTANCE_PATHS) parsed.primitives.set(path, { ...original, path, instanceOf: SPARE_SOURCE_PATH })
  return { ...parsed, rawSHA256: sha256(raw), deliverySHA256: sha256(delivery), deliveryByteLength: delivery.byteLength, semanticDigest: equivalence.semanticDigest }
}

/** Runtime paths come exclusively from the independently replayed original
 * loader. Raw ordinal identity stays intact when delivery deduplicates meshes. */
export function bindNativeRawPrimitivesToOriginalInventory(model, inventory) {
  const raw = [...model.primitives.values()].filter(primitive => primitive.instanceOf === null), result = new Map(), used = new Set()
  for (const original of inventory.drawables) {
    const sourcePath = original.instanceOf ?? original.path
    const association = original.association
    const candidates = raw.filter(primitive => (sourcePath === primitive.rawPath || sourcePath.startsWith(`${primitive.rawPath}/`)) && primitive.primitiveIndex === association.primitiveIndex)
    const longest = Math.max(...candidates.map(primitive => primitive.rawPath.length))
    const selected = candidates.filter(primitive => primitive.rawPath.length === longest)
    if (selected.length !== 1) throw new Error(`Ambiguous authentic raw primitive for ${original.path}`)
    const primitive = selected[0]
    if (association.nodeIndex !== null && association.nodeIndex !== primitive.nodeIndex) throw new Error('Original loader/raw node ancestry differs')
    if (original.instanceOf === null) {
      const identity = `${primitive.nodeIndex}/${primitive.meshIndex}/${primitive.primitiveIndex}`
      if (used.has(identity)) throw new Error('Raw primitive ancestry reused without explicit original instance')
      used.add(identity)
    } else if (!SPARE_INSTANCE_PATHS.includes(original.path) || original.instanceOf !== SPARE_SOURCE_PATH || primitive.rawPath !== SPARE_SOURCE_PATH) throw new Error('Nonoriginal extra native instance')
    result.set(original.path, { ...primitive, path: original.path, instanceOf: original.instanceOf })
  }
  if (used.size !== 460 || result.size !== 462) throw new Error('Original raw460+two real instance join incomplete')
  return result
}
