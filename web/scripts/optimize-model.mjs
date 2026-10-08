import { createHash } from 'node:crypto'
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer'

const MESHOPT = 'EXT_meshopt_compression'
const CODEC_VERSION = '0.22.0'
const COMPONENT_BYTES = new Map([[5120, 1], [5121, 1], [5122, 2], [5123, 2], [5125, 4], [5126, 4]])
const TYPE_SHAPE = new Map([['SCALAR', [1, 1]], ['VEC2', [1, 2]], ['VEC3', [1, 3]], ['VEC4', [1, 4]], ['MAT2', [2, 2]], ['MAT3', [3, 3]], ['MAT4', [4, 4]]])
// These extensions either reference unchanged tables, or have their references
// explicitly handled below. Unknown extensions cannot safely survive index remaps.
const SUPPORTED_EXTENSIONS = new Set([
  MESHOPT, 'KHR_mesh_quantization', 'KHR_lights_punctual', 'KHR_texture_transform',
  'KHR_texture_basisu', 'EXT_texture_webp', 'EXT_texture_avif', 'EXT_mesh_gpu_instancing',
  'KHR_materials_variants', 'KHR_materials_unlit', 'KHR_materials_pbrSpecularGlossiness',
  'KHR_materials_clearcoat', 'KHR_materials_transmission', 'KHR_materials_volume',
  'KHR_materials_ior', 'KHR_materials_specular', 'KHR_materials_sheen',
  'KHR_materials_emissive_strength', 'KHR_materials_iridescence', 'KHR_materials_anisotropy',
  'KHR_materials_dispersion',
])
const TABLES = ['buffers', 'bufferViews', 'accessors', 'meshes', 'nodes', 'scenes', 'materials', 'textures', 'images', 'samplers', 'skins', 'animations', 'cameras']

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const align4 = n => Math.ceil(n / 4) * 4
const clone = value => structuredClone(value)
function fail(message) { throw new Error(`Lossless GLB: ${message}`) }
function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${label} must be an object`)
}
function integer(value, label, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) fail(`${label} must be an integer >= ${minimum}`)
  return value
}
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
  return JSON.stringify(value)
}
function without(value, keys) {
  const result = { ...value }
  for (const key of keys) delete result[key]
  return result
}
function stripMeshopt(value) {
  const result = clone(value)
  if (result.extensions?.[MESHOPT]) {
    delete result.extensions[MESHOPT]
    if (!Object.keys(result.extensions).length) delete result.extensions
  }
  return result
}
function asBytes(value) {
  if (value instanceof ArrayBuffer) return Buffer.from(value)
  if (ArrayBuffer.isView(value)) return Buffer.from(value.buffer, value.byteOffset, value.byteLength)
  fail('input must be an ArrayBuffer or a typed-array byte view')
}

function parseGlb(input) {
  const bytes = asBytes(input)
  if (bytes.length < 20 || bytes.readUInt32LE(0) !== 0x46546c67) fail('invalid GLB header')
  if (bytes.readUInt32LE(4) !== 2) fail('only GLB version 2 is supported')
  if (bytes.readUInt32LE(8) !== bytes.length) fail('GLB declared length does not match input')
  let cursor = 12, json, bin
  while (cursor < bytes.length) {
    if (cursor + 8 > bytes.length) fail('truncated GLB chunk header')
    const length = bytes.readUInt32LE(cursor), type = bytes.readUInt32LE(cursor + 4)
    if (length % 4 || cursor + 8 + length > bytes.length) fail('invalid GLB chunk length')
    const chunk = bytes.subarray(cursor + 8, cursor + 8 + length)
    if (type === 0x4e4f534a && cursor === 12 && json === undefined) {
      try { json = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(chunk)) }
      catch (error) { fail(`invalid GLB JSON: ${error.message}`) }
    } else if (type === 0x004e4942 && json !== undefined && bin === undefined) bin = chunk
    else fail('unsupported, duplicate, or out-of-order GLB chunk')
    cursor += 8 + length
  }
  object(json, 'glTF document')
  if (json.asset?.version !== '2.0' || (json.asset.minVersion && json.asset.minVersion !== '2.0')) fail('only glTF 2.0 is supported')
  for (const table of TABLES) {
    if (json[table] !== undefined && !Array.isArray(json[table])) fail(`${table} must be an array`)
    for (const [i, value] of (json[table] ?? []).entries()) object(value, `${table}[${i}]`)
  }
  if (!json.buffers?.length || !bin) fail('an embedded GLB binary buffer is required')
  const length = integer(json.buffers[0].byteLength, 'buffers[0].byteLength', 1)
  if (json.buffers[0].uri !== undefined) fail('external buffers are unsupported; buffer 0 must be embedded')
  if (length > bin.length || bin.length - length > 3) fail('embedded buffer length does not match BIN chunk')
  for (let i = length; i < bin.length; i++) if (bin[i] !== 0) fail('nonzero BIN padding is unsupported')
  if (json.buffers[0].extensions?.[MESHOPT] !== undefined) fail('meshopt fallback metadata on the embedded buffer is unsupported')
  for (let i = 1; i < json.buffers.length; i++) {
    const buffer = json.buffers[i]
    integer(buffer.byteLength, `buffers[${i}].byteLength`, 1)
    if (buffer.uri !== undefined || buffer.extensions?.[MESHOPT]?.fallback !== true) fail('external or non-fallback secondary buffers are unsupported')
    if (Object.keys(buffer).some(key => !['byteLength', 'extensions'].includes(key)) || canonical(buffer.extensions) !== canonical({ [MESHOPT]: { fallback: true } })) fail('placeholder fallback buffers with additional metadata are unsupported')
    if (!Array.isArray(json.extensionsRequired) || !json.extensionsRequired.includes(MESHOPT)) fail('placeholder fallback buffer requires EXT_meshopt_compression')
  }
  for (const list of ['extensionsUsed', 'extensionsRequired']) {
    if (json[list] !== undefined && (!Array.isArray(json[list]) || json[list].some(name => typeof name !== 'string'))) fail(`${list} must contain extension names`)
    for (const name of json[list] ?? []) if (!SUPPORTED_EXTENSIONS.has(name)) fail(`unsupported extension ${name}; cannot safely remap its references`)
  }
  for (const name of json.extensionsRequired ?? []) if (!json.extensionsUsed?.includes(name)) fail(`required extension ${name} is not declared in extensionsUsed`)
  function inspect(value, path = 'document') {
    if (!value || typeof value !== 'object') return
    if (value.extensions) {
      object(value.extensions, `${path}.extensions`)
      for (const name of Object.keys(value.extensions)) {
        if (!SUPPORTED_EXTENSIONS.has(name)) fail(`unsupported extension ${name} at ${path}; cannot safely remap its references`)
        if (!json.extensionsUsed?.includes(name)) fail(`${name} at ${path} is not declared in extensionsUsed`)
        object(value.extensions[name], `${path}.extensions.${name}`)
      }
    }
    for (const [key, child] of Object.entries(value)) if (key !== 'extras') inspect(child, `${path}.${key}`)
  }
  inspect(json)
  return { bytes, json, bin: bin.subarray(0, length) }
}

function ref(json, table, value, label) {
  integer(value, label)
  if (value >= (json[table]?.length ?? 0)) fail(`${label} references missing ${table}[${value}]`)
  return json[table][value]
}
function elementSize(accessor, label) {
  const size = COMPONENT_BYTES.get(accessor.componentType), shape = TYPE_SHAPE.get(accessor.type)
  if (!size || !shape) fail(`${label} has unsupported componentType or accessor type`)
  const [columns, rows] = shape
  return columns * (columns > 1 ? align4(rows * size) : rows * size)
}
function range(offset, length, limit, label) {
  integer(offset, `${label}.byteOffset`)
  integer(length, `${label}.byteLength`, 1)
  if (!Number.isSafeInteger(offset + length) || offset + length > limit) fail(`${label} is outside its buffer`)
}

async function decodeViews(parsed) {
  await MeshoptDecoder.ready
  const { json, bin } = parsed
  const views = []
  for (const [i, view] of (json.bufferViews ?? []).entries()) {
    const label = `bufferViews[${i}]`
    const buffer = ref(json, 'buffers', view.buffer, `${label}.buffer`)
    range(view.byteOffset ?? 0, view.byteLength, buffer.byteLength, label)
    if (view.byteStride !== undefined && (integer(view.byteStride, `${label}.byteStride`, 4) > 252 || view.byteStride % 4)) fail(`${label} has invalid byteStride`)
    if (view.target !== undefined && ![34962, 34963].includes(view.target)) fail(`${label} has invalid target`)
    const extension = view.extensions?.[MESHOPT]
    if (extension) {
      if (Object.keys(extension).some(key => !['buffer', 'byteOffset', 'byteLength', 'byteStride', 'count', 'mode', 'filter'].includes(key))) fail(`${label} meshopt extension has unsupported additional metadata`)
      if (extension.buffer !== 0) fail(`${label} compressed data must use the embedded buffer, not fallback/external storage`)
      range(extension.byteOffset ?? 0, extension.byteLength, bin.length, `${label}.${MESHOPT}`)
      const count = integer(extension.count, `${label}.compression.count`, 1)
      const stride = integer(extension.byteStride, `${label}.compression.byteStride`, 1)
      if (count * stride !== view.byteLength || (view.byteStride !== undefined && view.byteStride !== stride)) fail(`${label} compression layout does not match decoded view`)
      if (!['ATTRIBUTES', 'INDICES', 'TRIANGLES'].includes(extension.mode)) fail(`${label} has unsupported compression mode`)
      if (extension.filter !== undefined && extension.filter !== 'NONE') fail(`${label} uses a lossy/unsupported compression filter`)
      if (extension.mode === 'ATTRIBUTES' ? stride > 256 || stride % 4 : ![2, 4].includes(stride)) fail(`${label} has invalid compression stride`)
      if (extension.mode === 'TRIANGLES' && count % 3) fail(`${label} has invalid triangle count`)
      const decoded = Buffer.alloc(view.byteLength)
      try {
        MeshoptDecoder.decodeGltfBuffer(decoded, count, stride, bin.subarray(extension.byteOffset ?? 0, (extension.byteOffset ?? 0) + extension.byteLength), extension.mode, 'NONE')
      } catch (error) { fail(`${label} meshopt decoding failed: ${error.message}`) }
      views.push(decoded)
    } else {
      if (view.buffer !== 0) fail(`${label} cannot read missing fallback data without compression`)
      views.push(bin.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength))
    }
  }
  // No uninterpreted binary payload is discarded. Only up to three zero bytes of
  // alignment between referenced ranges are allowed outside stored buffer views.
  const ranges = (json.bufferViews ?? []).map(view => {
    const ext = view.extensions?.[MESHOPT]
    return ext ? [ext.byteOffset ?? 0, (ext.byteOffset ?? 0) + ext.byteLength] : [view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength]
  }).sort((a, b) => a[0] - b[0])
  let cursor = 0
  for (const [start, end] of [...ranges, [bin.length, bin.length]]) {
    if (start > cursor) {
      if (start - cursor > 3) fail('unreferenced binary payload is unsupported')
      for (let i = cursor; i < start; i++) if (bin[i] !== 0) fail('nonzero unreferenced binary payload is unsupported')
    }
    cursor = Math.max(cursor, end)
  }
  return views
}

function validateReferences(json, views) {
  function accessorRange(accessor, viewIndex, offset, count, size, label, strideAllowed = true) {
    const view = ref(json, 'bufferViews', viewIndex, `${label}.bufferView`)
    const stride = strideAllowed ? view.byteStride ?? size : size
    integer(offset, `${label}.byteOffset`)
    if (stride < size) fail(`${label} stride is smaller than its element`)
    const component = COMPONENT_BYTES.get(accessor.componentType)
    if (offset % component || (view.byteOffset ?? 0) % component) fail(`${label} is not component-aligned`)
    if (offset + (count - 1) * stride + size > view.byteLength) fail(`${label} exceeds its bufferView`)
    return view
  }
  for (const [i, accessor] of (json.accessors ?? []).entries()) {
    const label = `accessors[${i}]`, size = elementSize(accessor, label)
    integer(accessor.count, `${label}.count`, 1)
    if (accessor.normalized !== undefined && typeof accessor.normalized !== 'boolean') fail(`${label}.normalized must be boolean`)
    if (accessor.normalized && [5125, 5126].includes(accessor.componentType)) fail(`${label} component type cannot be normalized`)
    if (accessor.bufferView !== undefined) accessorRange(accessor, accessor.bufferView, accessor.byteOffset ?? 0, accessor.count, size, label)
    else if ((accessor.byteOffset ?? 0) !== 0) fail(`${label} without a bufferView cannot have a byteOffset`)
    for (const key of ['min', 'max']) if (accessor[key] !== undefined && (!Array.isArray(accessor[key]) || accessor[key].length !== TYPE_SHAPE.get(accessor.type).reduce((a, b) => a * b) || accessor[key].some(value => !Number.isFinite(value)))) fail(`${label}.${key} has invalid bounds`)
    if (accessor.sparse !== undefined) {
      const sparse = accessor.sparse
      object(sparse, `${label}.sparse`)
      integer(sparse.count, `${label}.sparse.count`, 1)
      if (sparse.count > accessor.count) fail(`${label} sparse count exceeds accessor count`)
      object(sparse.indices, `${label}.sparse.indices`)
      object(sparse.values, `${label}.sparse.values`)
      if (![5121, 5123, 5125].includes(sparse.indices.componentType)) fail(`${label} sparse indices must be unsigned integers`)
      const indexSize = COMPONENT_BYTES.get(sparse.indices.componentType)
      const iv = accessorRange(sparse.indices, sparse.indices.bufferView, sparse.indices.byteOffset ?? 0, sparse.count, indexSize, `${label}.sparse.indices`, false)
      const vv = accessorRange(accessor, sparse.values.bufferView, sparse.values.byteOffset ?? 0, sparse.count, size, `${label}.sparse.values`, false)
      if (iv.byteStride !== undefined || vv.byteStride !== undefined || iv.target !== undefined || vv.target !== undefined) fail(`${label} sparse views cannot have stride or target`)
      let previous = -1
      for (let n = 0; n < sparse.count; n++) {
        const index = views[sparse.indices.bufferView].readUIntLE((sparse.indices.byteOffset ?? 0) + n * indexSize, indexSize)
        if (index <= previous || index >= accessor.count) fail(`${label} sparse indices are not increasing/in bounds`)
        previous = index
      }
    }
  }
  function attributes(value, label) {
    object(value, label)
    if (!Object.keys(value).length) fail(`${label} cannot be empty`)
    let count
    for (const [name, index] of Object.entries(value)) {
      const accessor = ref(json, 'accessors', index, `${label}.${name}`)
      if (count !== undefined && accessor.count !== count) fail(`${label} attribute counts disagree`)
      count = accessor.count
    }
    return count
  }
  for (const [i, mesh] of (json.meshes ?? []).entries()) {
    if (!Array.isArray(mesh.primitives) || !mesh.primitives.length) fail(`meshes[${i}].primitives must be nonempty`)
    for (const [p, primitive] of mesh.primitives.entries()) {
      object(primitive, `meshes[${i}].primitives[${p}]`)
      const label = `meshes[${i}].primitives[${p}]`
      const count = attributes(primitive.attributes, `${label}.attributes`)
      if (primitive.indices !== undefined) {
        const index = ref(json, 'accessors', primitive.indices, `${label}.indices`)
        if (index.type !== 'SCALAR' || ![5121, 5123, 5125].includes(index.componentType) || index.normalized || index.sparse || index.bufferView === undefined) fail(`${label} unsupported index accessor (requires dense unsigned SCALAR)`)
        const size = COMPONENT_BYTES.get(index.componentType), view = json.bufferViews[index.bufferView]
        if (view.byteStride !== undefined) fail(`${label} indices cannot have a byteStride`)
        for (let n = 0; n < index.count; n++) if (views[index.bufferView].readUIntLE((index.byteOffset ?? 0) + n * size, size) >= count) fail(`${label} index is outside its vertex attributes`)
      }
      if (primitive.material !== undefined) ref(json, 'materials', primitive.material, `${label}.material`)
      if (primitive.mode !== undefined && (!Number.isInteger(primitive.mode) || primitive.mode < 0 || primitive.mode > 6)) fail(`${label} has invalid primitive mode`)
      if (primitive.targets !== undefined && !Array.isArray(primitive.targets)) fail(`${label}.targets must be an array`)
      for (const [t, target] of (primitive.targets ?? []).entries()) if (attributes(target, `${label}.targets[${t}]`) !== count) fail(`${label} morph target count disagrees`)
      const mappings = primitive.extensions?.KHR_materials_variants?.mappings ?? []
      if (!Array.isArray(mappings)) fail(`${label}.variants.mappings must be an array`)
      for (const mapping of mappings) {
        object(mapping, `${label}.variants.mapping`)
        if (!Array.isArray(mapping.variants)) fail(`${label}.variants.mapping.variants must be an array`)
        ref(json, 'materials', mapping.material, `${label}.variants.material`)
        for (const variant of mapping.variants ?? []) {
          integer(variant, `${label}.variants.variant`)
          if (variant >= (json.extensions?.KHR_materials_variants?.variants?.length ?? 0)) fail(`${label} references missing material variant`)
        }
      }
    }
  }
  const parents = new Map()
  for (const [i, node] of (json.nodes ?? []).entries()) {
    for (const key of ['mesh', 'camera', 'skin']) if (node[key] !== undefined) ref(json, `${key === 'mesh' ? 'meshes' : `${key}s`}`, node[key], `nodes[${i}].${key}`)
    if (node.children !== undefined && !Array.isArray(node.children)) fail(`nodes[${i}].children must be an array`)
    for (const child of node.children ?? []) {
      ref(json, 'nodes', child, `nodes[${i}].children`)
      if (parents.has(child)) fail(`nodes[${child}] has multiple parents`)
      parents.set(child, i)
    }
    for (const [key, length] of [['translation', 3], ['rotation', 4], ['scale', 3], ['matrix', 16]]) if (node[key] !== undefined && (!Array.isArray(node[key]) || node[key].length !== length || node[key].some(value => !Number.isFinite(value)))) fail(`nodes[${i}].${key} has invalid transform`)
    if (node.matrix !== undefined && ['translation', 'rotation', 'scale'].some(key => node[key] !== undefined)) fail(`nodes[${i}] cannot mix matrix and TRS transforms`)
    if (node.extensions?.EXT_mesh_gpu_instancing) attributes(node.extensions.EXT_mesh_gpu_instancing.attributes, `nodes[${i}].instancing.attributes`)
    if (node.extensions?.KHR_lights_punctual) {
      const light = integer(node.extensions.KHR_lights_punctual.light, `nodes[${i}].light`)
      if (light >= (json.extensions?.KHR_lights_punctual?.lights?.length ?? 0)) fail(`nodes[${i}] references missing light`)
    }
  }
  const visited = new Set(), visiting = new Set()
  function visit(i) {
    if (visiting.has(i)) fail('node hierarchy contains a cycle')
    if (visited.has(i)) return
    visiting.add(i)
    for (const child of json.nodes[i].children ?? []) visit(child)
    visiting.delete(i); visited.add(i)
  }
  for (let i = 0; i < (json.nodes?.length ?? 0); i++) visit(i)
  for (const [i, scene] of (json.scenes ?? []).entries()) {
    if (scene.nodes !== undefined && !Array.isArray(scene.nodes)) fail(`scenes[${i}].nodes must be an array`)
    for (const node of scene.nodes ?? []) ref(json, 'nodes', node, `scenes[${i}].nodes`)
  }
  if (json.scene !== undefined) ref(json, 'scenes', json.scene, 'scene')
  for (const [i, image] of (json.images ?? []).entries()) {
    if ((image.bufferView !== undefined) === (image.uri !== undefined)) fail(`images[${i}] requires exactly one bufferView or URI`)
    if (image.bufferView !== undefined) {
      ref(json, 'bufferViews', image.bufferView, `images[${i}].bufferView`)
      if (typeof image.mimeType !== 'string') fail(`images[${i}] requires mimeType`)
    } else {
      if (typeof image.uri !== 'string') fail(`images[${i}].uri must be a string`)
      // Only embedded payloads are sealed by the GLB hash and published with it.
      if (!/^data:[^,]*,/i.test(image.uri)) fail(`external image URIs are unsupported; images[${i}].uri must be an embedded data URI`)
    }
  }
  for (const [i, texture] of (json.textures ?? []).entries()) {
    if (texture.source !== undefined) ref(json, 'images', texture.source, `textures[${i}].source`)
    if (texture.sampler !== undefined) ref(json, 'samplers', texture.sampler, `textures[${i}].sampler`)
    for (const name of ['KHR_texture_basisu', 'EXT_texture_webp', 'EXT_texture_avif']) if (texture.extensions?.[name]) ref(json, 'images', texture.extensions[name].source, `textures[${i}].${name}.source`)
  }
  function textureInfos(value, path) {
    if (!value || typeof value !== 'object') return
    for (const [key, child] of Object.entries(value)) {
      if (key === 'extras') continue
      if (key.endsWith('Texture')) {
        object(child, `${path}.${key}`)
        ref(json, 'textures', child.index, `${path}.${key}.index`)
      }
      textureInfos(child, `${path}.${key}`)
    }
  }
  for (const [i, material] of (json.materials ?? []).entries()) textureInfos(material, `materials[${i}]`)
  for (const [i, skin] of (json.skins ?? []).entries()) {
    if (!Array.isArray(skin.joints) || !skin.joints.length) fail(`skins[${i}].joints must be nonempty`)
    for (const joint of skin.joints) ref(json, 'nodes', joint, `skins[${i}].joints`)
    if (skin.skeleton !== undefined) ref(json, 'nodes', skin.skeleton, `skins[${i}].skeleton`)
    if (skin.inverseBindMatrices !== undefined) ref(json, 'accessors', skin.inverseBindMatrices, `skins[${i}].inverseBindMatrices`)
  }
  for (const [i, animation] of (json.animations ?? []).entries()) {
    if (!Array.isArray(animation.samplers) || !Array.isArray(animation.channels)) fail(`animations[${i}] requires samplers and channels`)
    for (const [s, sampler] of animation.samplers.entries()) {
      object(sampler, `animations[${i}].samplers[${s}]`)
      for (const key of ['input', 'output']) ref(json, 'accessors', sampler[key], `animations[${i}].samplers[${s}].${key}`)
    }
    for (const [c, channel] of animation.channels.entries()) {
      object(channel, `animations[${i}].channels[${c}]`)
      integer(channel.sampler, `animations[${i}].channels[${c}].sampler`)
      if (channel.sampler >= animation.samplers.length) fail(`animations[${i}] references missing sampler`)
      object(channel.target, `animations[${i}].channels[${c}].target`)
      if (channel.target.node !== undefined) ref(json, 'nodes', channel.target.node, `animations[${i}].channels[${c}].target.node`)
      if (!['translation', 'rotation', 'scale', 'weights'].includes(channel.target.path)) fail(`animations[${i}] has unsupported target path`)
    }
  }
}

function remapReferences(json, maps) {
  function remap(value, key, map) { if (value[key] !== undefined && map) value[key] = map[value[key]] }
  for (const accessor of json.accessors ?? []) {
    remap(accessor, 'bufferView', maps.view)
    if (accessor.sparse) for (const key of ['indices', 'values']) remap(accessor.sparse[key], 'bufferView', maps.view)
  }
  for (const image of json.images ?? []) remap(image, 'bufferView', maps.view)
  for (const mesh of json.meshes ?? []) for (const primitive of mesh.primitives) {
    remap(primitive, 'indices', maps.accessor)
    for (const attrs of [primitive.attributes, ...(primitive.targets ?? [])]) for (const name of Object.keys(attrs)) remap(attrs, name, maps.accessor)
  }
  for (const node of json.nodes ?? []) {
    remap(node, 'mesh', maps.mesh)
    const attrs = node.extensions?.EXT_mesh_gpu_instancing?.attributes
    if (attrs) for (const name of Object.keys(attrs)) remap(attrs, name, maps.accessor)
  }
  for (const texture of json.textures ?? []) {
    remap(texture, 'source', maps.image)
    for (const name of ['KHR_texture_basisu', 'EXT_texture_webp', 'EXT_texture_avif']) if (texture.extensions?.[name]) remap(texture.extensions[name], 'source', maps.image)
  }
  for (const skin of json.skins ?? []) remap(skin, 'inverseBindMatrices', maps.accessor)
  for (const animation of json.animations ?? []) for (const sampler of animation.samplers) for (const key of ['input', 'output']) remap(sampler, key, maps.accessor)
}

function deduplicate(items, keyOf, equal = () => true) {
  const result = [], map = [], sourceIndices = [], buckets = new Map()
  for (const [i, value] of items.entries()) {
    const key = keyOf(value, i), candidates = buckets.get(key) ?? []
    const existing = candidates.find(index => equal(sourceIndices[index], i))
    if (existing !== undefined) map.push(existing)
    else {
      const index = result.length
      result.push(value); sourceIndices.push(i); map.push(index)
      candidates.push(index); buckets.set(key, candidates)
    }
  }
  return { result, map, sourceIndices }
}
function viewIdentity(view, bytes) {
  return canonical({ ...without(stripMeshopt(view), ['buffer', 'byteOffset']), bytesSha256: sha256(bytes) })
}

function semanticIdentity(json, views, cachedViewIds) {
  const result = clone(json)
  const viewIds = cachedViewIds ?? (json.bufferViews ?? []).map((view, i) => sha256(viewIdentity(view, views[i])))
  remapReferences(result, { view: viewIds })
  const accessorIds = (result.accessors ?? []).map(accessor => sha256(canonical(accessor)))
  remapReferences(result, { accessor: accessorIds })
  const meshIds = (result.meshes ?? []).map(mesh => sha256(canonical(mesh)))
  const imageIds = (result.images ?? []).map(image => sha256(canonical(image)))
  remapReferences(result, { mesh: meshIds, image: imageIds })
  result.bufferViews = [...new Set(viewIds)].sort()
  for (const [key, ids] of [['accessors', accessorIds], ['meshes', meshIds], ['images', imageIds]]) if (json[key] !== undefined) result[key] = [...new Set(ids)].sort()
  result.buffers = [without(stripMeshopt(json.buffers[0]), ['byteLength'])]
  for (const key of ['extensionsUsed', 'extensionsRequired']) if (result[key]) {
    result[key] = result[key].filter(name => name !== MESHOPT).sort()
    if (!result[key].length) delete result[key]
  }
  return { document: result, viewIds }
}

/**
 * Verify decoded byte identity AND expanded core-glTF semantics. Node order,
 * names, hierarchy, local transforms, materials, primitive metadata, images,
 * accessor layouts, sparse payloads, and unused definitions are covered. Storage
 * offsets, exact duplicate table entries, and meshopt declarations may differ.
 * Throws on malformed inputs, codec corruption, or any semantic/byte difference.
 */
export async function validateDecodedEquivalence(sourceBytes, optimizedBytes) {
  const source = parseGlb(sourceBytes), optimized = parseGlb(optimizedBytes)
  const sourceViews = await decodeViews(source), optimizedViews = await decodeViews(optimized)
  validateReferences(source.json, sourceViews)
  validateReferences(optimized.json, optimizedViews)
  return compareDecoded(source, sourceViews, optimized, optimizedViews)
}

function compareDecoded(source, sourceViews, optimized, optimizedViews, sourceViewIds) {
  const sourceIdentity = semanticIdentity(source.json, sourceViews, sourceViewIds), optimizedIdentity = semanticIdentity(optimized.json, optimizedViews)
  const before = sourceIdentity.document, after = optimizedIdentity.document
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) if (canonical(before[key]) !== canonical(after[key])) fail(`decoded equivalence failed for ${key}`)
  // Digests locate equivalent definitions; actual byte comparisons establish
  // identity, including signed zero, opaque NaN payloads and untouched PNG data.
  const candidates = new Map()
  for (const [i, id] of optimizedIdentity.viewIds.entries()) {
    const bucket = candidates.get(id) ?? []
    bucket.push(optimizedViews[i]); candidates.set(id, bucket)
  }
  for (const [i, id] of sourceIdentity.viewIds.entries()) if (!candidates.get(id)?.some(bytes => sourceViews[i].equals(bytes))) fail(`decoded equivalence failed for bufferViews[${i}] bytes`)
  return {
    passed: true,
    semanticDigest: sha256(canonical(before)),
    sourceSha256: sha256(source.bytes), optimizedSha256: sha256(optimized.bytes),
    nodes: source.json.nodes?.length ?? 0,
    drawableInstances: drawableInstances(source.json),
    sourceBufferViews: sourceViews.length, optimizedBufferViews: optimizedViews.length,
    decodedBytesCompared: sourceViews.reduce((total, view) => total + view.length, 0),
  }
}

function drawableInstances(json) {
  return (json.nodes ?? []).reduce((total, node) => total + (node.mesh === undefined ? 0 : json.meshes[node.mesh].primitives.length), 0)
}
function compressionLayouts(json) {
  const uses = (json.bufferViews ?? []).map(() => ({ indices: new Set(), attributes: false, raw: false }))
  const indexAccessors = new Set((json.meshes ?? []).flatMap(mesh => mesh.primitives.flatMap(primitive => primitive.indices === undefined ? [] : [primitive.indices])))
  for (const [i, accessor] of (json.accessors ?? []).entries()) {
    if (accessor.bufferView !== undefined) {
      const use = uses[accessor.bufferView]
      if (indexAccessors.has(i)) use.indices.add(COMPONENT_BYTES.get(accessor.componentType))
      else use.attributes = true
    }
    if (accessor.sparse) for (const key of ['indices', 'values']) uses[accessor.sparse[key].bufferView].raw = true
  }
  for (const image of json.images ?? []) if (image.bufferView !== undefined) uses[image.bufferView].raw = true
  return (json.bufferViews ?? []).map((view, i) => {
    const use = uses[i]
    if (use.raw) return null
    if (use.indices.size) {
      const stride = [...use.indices][0]
      if (use.attributes || use.indices.size !== 1 || ![2, 4].includes(stride) || view.byteLength % stride) return null
      return { mode: 'INDICES', stride }
    }
    if (use.attributes) {
      const stride = view.byteStride ?? 4
      if (stride <= 256 && stride % 4 === 0 && view.byteLength % stride === 0) return { mode: 'ATTRIBUTES', stride }
    }
    return null
  })
}
function serializeGlb(json, binary) {
  const text = Buffer.from(JSON.stringify(json)), jsonLength = align4(text.length), binLength = align4(binary.length)
  const bytes = Buffer.alloc(12 + 8 + jsonLength + 8 + binLength)
  bytes.writeUInt32LE(0x46546c67, 0); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(jsonLength, 12); bytes.writeUInt32LE(0x4e4f534a, 16)
  bytes.fill(0x20, 20, 20 + jsonLength); text.copy(bytes, 20)
  bytes.writeUInt32LE(binLength, 20 + jsonLength); bytes.writeUInt32LE(0x004e4942, 24 + jsonLength)
  binary.copy(bytes, 28 + jsonLength)
  return bytes
}

/**
 * Internal exact same-name storage optimizer: no native identity projection.
 * The importer supplies independently verified canonical bytes; its public v2
 * descriptor proves decoded equivalence after that authorized projection.
 */
export async function optimizeModel(inputBytes) {
  await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready])
  const source = parseGlb(inputBytes), sourceViews = await decodeViews(source)
  validateReferences(source.json, sourceViews)
  const sourceViewKeys = (source.json.bufferViews ?? []).map((view, i) => viewIdentity(view, sourceViews[i]))
  const json = clone(source.json)
  const viewDedup = deduplicate(json.bufferViews ?? [], (_, i) => sourceViewKeys[i], (a, b) => sourceViews[a].equals(sourceViews[b]))
  remapReferences(json, { view: viewDedup.map })
  json.bufferViews = viewDedup.result.map(stripMeshopt)
  const accessorDedup = deduplicate(json.accessors ?? [], canonical)
  remapReferences(json, { accessor: accessorDedup.map })
  if (json.accessors) json.accessors = accessorDedup.result
  const meshDedup = deduplicate(json.meshes ?? [], canonical)
  remapReferences(json, { mesh: meshDedup.map })
  if (json.meshes) json.meshes = meshDedup.result
  const imageDedup = deduplicate(json.images ?? [], canonical)
  remapReferences(json, { image: imageDedup.map })
  if (json.images) json.images = imageDedup.result

  // Measure the actual deduplicated, still-uncompressed GLB layout separately
  // from the final codec layout. No second large binary allocation is needed.
  const deduplicatedJson = clone(json)
  let deduplicatedBinaryBytes = 0
  for (const [i, view] of deduplicatedJson.bufferViews.entries()) {
    view.buffer = 0
    view.byteOffset = align4(deduplicatedBinaryBytes)
    deduplicatedBinaryBytes = view.byteOffset + sourceViews[viewDedup.sourceIndices[i]].length
  }
  deduplicatedJson.buffers = [{ ...without(stripMeshopt(source.json.buffers[0]), ['byteLength']), byteLength: deduplicatedBinaryBytes }]
  for (const key of ['extensionsUsed', 'extensionsRequired']) if (deduplicatedJson[key]) {
    deduplicatedJson[key] = deduplicatedJson[key].filter(name => name !== MESHOPT)
    if (!deduplicatedJson[key].length) delete deduplicatedJson[key]
  }
  const deduplicatedBytes = 28 + align4(Buffer.byteLength(JSON.stringify(deduplicatedJson))) + align4(deduplicatedBinaryBytes)

  const layouts = compressionLayouts(json), chunks = []
  let storedBytes = 0, fallbackBytes = 0, compressedViews = 0, compressedSourceBytes = 0, compressedBytes = 0
  function append(bytes) {
    const offset = align4(storedBytes)
    if (offset !== storedBytes) chunks.push(Buffer.alloc(offset - storedBytes))
    chunks.push(bytes); storedBytes = offset + bytes.length
    return offset
  }
  for (const [i, view] of json.bufferViews.entries()) {
    const raw = sourceViews[viewDedup.sourceIndices[i]], layout = layouts[i]
    if (!layout) {
      view.buffer = 0; view.byteOffset = append(raw)
      continue
    }
    // The index codec creates typed-array views and therefore needs alignment.
    const input = raw.byteOffset % layout.stride === 0 || layout.mode === 'ATTRIBUTES' ? raw : Buffer.from(raw)
    let encoded
    try { encoded = MeshoptEncoder.encodeGltfBuffer(input, raw.length / layout.stride, layout.stride, layout.mode) }
    catch (error) { fail(`bufferViews[${i}] meshopt encoding failed: ${error.message}`) }
    const decoded = Buffer.alloc(raw.length)
    try { MeshoptDecoder.decodeGltfBuffer(decoded, raw.length / layout.stride, layout.stride, encoded, layout.mode, 'NONE') }
    catch (error) { fail(`bufferViews[${i}] encoded stream cannot be decoded: ${error.message}`) }
    if (!raw.equals(decoded)) fail(`bufferViews[${i}] codec did not preserve exact bytes`)
    view.buffer = 1; view.byteOffset = align4(fallbackBytes); fallbackBytes = view.byteOffset + raw.length
    view.extensions = { ...view.extensions, [MESHOPT]: {
      buffer: 0, byteOffset: append(encoded), byteLength: encoded.length,
      byteStride: layout.stride, count: raw.length / layout.stride, mode: layout.mode, filter: 'NONE',
    } }
    compressedViews++; compressedSourceBytes += raw.length; compressedBytes += encoded.length
  }
  json.buffers = [{ ...without(stripMeshopt(source.json.buffers[0]), ['byteLength']), byteLength: storedBytes }]
  for (const key of ['extensionsUsed', 'extensionsRequired']) {
    const names = (json[key] ?? []).filter(name => name !== MESHOPT)
    if (compressedViews) names.push(MESHOPT)
    if (names.length) json[key] = names
    else delete json[key]
  }
  if (compressedViews) json.buffers.push({ byteLength: fallbackBytes, extensions: { [MESHOPT]: { fallback: true } } })
  const optimizedBytes = serializeGlb(json, Buffer.concat(chunks, storedBytes))
  const optimized = parseGlb(optimizedBytes), optimizedViews = await decodeViews(optimized)
  validateReferences(optimized.json, optimizedViews)
  const equivalence = compareDecoded(source, sourceViews, optimized, optimizedViews, sourceViewKeys.map(sha256))
  const sourceCounts = Object.fromEntries(['bufferViews', 'accessors', 'meshes', 'images'].map(key => [key, source.json[key]?.length ?? 0]))
  const optimizedCounts = Object.fromEntries(Object.keys(sourceCounts).map(key => [key, json[key]?.length ?? 0]))
  sourceCounts.nodes = source.json.nodes?.length ?? 0
  sourceCounts.drawableInstances = drawableInstances(source.json)
  optimizedCounts.nodes = json.nodes?.length ?? 0
  optimizedCounts.drawableInstances = drawableInstances(json)
  return { optimizedBytes, report: {
    schemaVersion: 2, sourceSha256: equivalence.sourceSha256, optimizedSha256: equivalence.optimizedSha256,
    sourceBytes: source.bytes.length, deduplicatedBytes, optimizedBytes: optimizedBytes.length,
    semanticDigest: equivalence.semanticDigest,
    stages: ['exact-dedup', 'meshopt'],
    codec: { name: 'meshoptimizer', version: CODEC_VERSION, extension: MESHOPT, attributeMode: 'ATTRIBUTES', indexMode: 'INDICES', filter: 'NONE' },
    statistics: {
      source: sourceCounts, optimized: optimizedCounts,
      deduplicated: Object.fromEntries(Object.keys(sourceCounts).map(key => [key, sourceCounts[key] - optimizedCounts[key]])),
      deduplicatedBufferViewBytes: sourceViews.reduce((total, view) => total + view.length, 0) - viewDedup.sourceIndices.reduce((total, index) => total + sourceViews[index].length, 0),
      nodes: equivalence.nodes, drawableInstances: equivalence.drawableInstances,
      compressedViews, rawViews: json.bufferViews.length - compressedViews, compressedSourceBytes, compressedBytes,
    },
    equivalence,
  } }
}
