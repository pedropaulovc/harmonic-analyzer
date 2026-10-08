#!/usr/bin/env node
/** Build-time-only identity projection. The CAD map is the sole naming authority. */
import { createHash } from 'node:crypto'
import { isDeepStrictEqual } from 'node:util'
import { open, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { NATIVE_IDENTITY_MAP_SHA256 } from '../model-representation.mjs'
export { NATIVE_IDENTITY_MAP_SHA256 }

const MAP_PATH = fileURLToPath(new URL('../../cad/config/identity-migration-map.json', import.meta.url))
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const align4 = n => Math.ceil(n / 4) * 4
const fail = message => { throw new Error(`Native identity projection: ${message}`) }
const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const INSTANCE = /^(?:--[A-Za-z][A-Za-z0-9_.]*)?-[1-9][0-9]*$/
const IDENTITY_FIELDS = new Set(['stem', 'underscore', 'number', 'registry', 'builder', 'file', 'module', 'part', 'assembly', 'name', 'path'])

export async function loadNativeIdentityMap(path = MAP_PATH) {
  const bytes = await readFile(path)
  if (sha256(bytes) !== NATIVE_IDENTITY_MAP_SHA256) fail(`CAD identity map SHA256 mismatch; expected ${NATIVE_IDENTITY_MAP_SHA256}`)
  const map = JSON.parse(bytes)
  if (map.schema_version !== 2 || !Array.isArray(map.identities) || map.identities.length !== 154 || !isRecord(map.direct_graph)) fail('invalid authoritative map schema')
  const old = new Set(), current = new Set(), domains = Object.fromEntries(
    ['stem', 'underscore', 'number', 'registry', 'builder', 'file', 'module', 'part', 'assembly'].map(field => [field, { exact: new Map(), reverse: new Map() }]),
  )
  const rows = map.identities
  function pair(field, source, canonical) {
    if (typeof source !== 'string' || typeof canonical !== 'string' || !source || !canonical) fail(`invalid authoritative ${field} token`)
    const { exact, reverse } = domains[field]
    if (exact.has(source) && exact.get(source) !== canonical || reverse.has(canonical) && reverse.get(canonical) !== source) fail(`authoritative ${field} map is not bijective`)
    exact.set(source, canonical); reverse.set(canonical, source)
  }
  for (const row of rows) {
    if (!['part', 'assembly'].includes(row.kind) || old.has(row.old_stem) || current.has(row.new_stem)) fail('duplicate or invalid authoritative native identity')
    old.add(row.old_stem); current.add(row.new_stem)
    for (const key of ['stem', 'underscore', 'number', 'registry', 'builder']) pair(key, row[`old_${key}`], row[`new_${key}`])
    pair(row.kind, row.old_underscore, row.new_underscore)
  }
  if (rows.filter(row => row.kind === 'assembly').length !== 8 || rows.filter(row => row.kind === 'part').length !== 146) fail('invalid authoritative identity counts')
  for (const [source, canonical] of Object.entries(map.file_renames)) pair('file', source, canonical)
  for (const [source, canonical] of Object.entries(map.module_renames)) pair('module', source, canonical)
  for (const row of rows.filter(row => row.kind === 'assembly')) {
    const members = map.direct_graph[row.old_underscore]
    if (!Array.isArray(members) || new Set(members).size !== members.length || members.some(member => !rows.some(candidate => candidate.old_underscore === member))) fail(`invalid native assembly context ${row.old_stem}`)
  }
  const variants = map.variants.map(variant => {
    const candidates = rows.filter(row => variant.old_prefix.startsWith(row.old_stem) && variant.new_prefix.startsWith(row.new_stem))
    const row = candidates.sort((a, b) => b.old_stem.length - a.old_stem.length)[0]
    // Diagnostic identities without a registry identity are not native assembly components.
    if (!row) return null
    if (variant.old_prefix.slice(row.old_stem.length) !== variant.new_prefix.slice(row.new_stem.length)) fail('variant qualifier changed by authoritative map')
    return { ...variant, row }
  }).filter(Boolean)
  return { rows, domains, variants, directGraph: map.direct_graph }
}

function matchName(name, map) {
  if (typeof name !== 'string' || !name || name.includes('/') || name.includes('\\')) return null
  const matches = []
  for (const row of map.rows) for (const mode of ['old', 'new']) {
    const stem = row[`${mode}_stem`]
    if (name === stem || name.startsWith(stem) && INSTANCE.test(name.slice(stem.length))) {
      matches.push({ row, mode, name: row.new_stem + name.slice(stem.length) })
    }
  }
  for (const variant of map.variants) for (const mode of ['old', 'new']) {
    const prefix = variant[`${mode}_prefix`]
    if (!name.startsWith(prefix)) continue
    const suffix = name.slice(prefix.length)
    // Qualifiers are complete native tokens, never arbitrary substring/prose replacements.
    const valid = prefix.endsWith('stretch') ? /^[0-9]{2}-[1-9][0-9]*$/.test(suffix)
      : variant.kind === 'component_instance' ? /^[1-9][0-9]*$/.test(suffix)
        : /^[a-z0-9]+(?:-[a-z0-9]+)*-[1-9][0-9]*$/.test(suffix)
    if (valid) matches.push({ row: variant.row, mode, name: variant.new_prefix + suffix })
  }
  const unique = [...new Map(matches.map(match => [`${match.row.old_stem}:${match.mode}:${match.name}`, match])).values()]
  if (unique.length > 1) fail(`ambiguous native token ${JSON.stringify(name)}`)
  return unique[0] ?? null
}

function projectDocument(source, map) {
  if (!isRecord(source) || source.asset?.version !== '2.0' || !Array.isArray(source.nodes)) fail('expected glTF 2.0 nodes')
  const json = structuredClone(source), parents = new Map(), paths = [], pathNames = new Map(), nodeNames = new Map(), native = new Map()
  for (const [index, node] of source.nodes.entries()) {
    if (!isRecord(node) || node.children !== undefined && !Array.isArray(node.children)) fail(`invalid node ${index}`)
    for (const child of node.children ?? []) {
      if (!Number.isSafeInteger(child) || child < 0 || child >= source.nodes.length || parents.has(child)) fail('invalid, repeated or multi-parent native hierarchy')
      parents.set(child, index)
    }
  }
  const visited = new Set(), active = new Set(), modes = new Set(), sourcePaths = new Set(), canonicalPaths = new Set()
  function visit(index, parent = null, sourcePrefix = '', canonicalPrefix = '') {
    if (active.has(index)) fail('cyclic native hierarchy')
    if (visited.has(index)) return
    active.add(index); visited.add(index)
    const node = source.nodes[index], match = matchName(node.name, map)
    const isNative = parent !== null || match?.row.kind === 'assembly'
    if (isNative) {
      if (!match) fail(`unknown native node ${JSON.stringify(node.name)} below ${sourcePrefix || '<root>'}`)
      if (parent && !map.directGraph[parent.row.old_underscore]?.includes(match.row.old_underscore)) fail(`native node ${node.name} is not authorized in assembly ${parent.row.old_stem}`)
      if (match.row.kind === 'part' && node.children?.length) fail(`native part ${node.name} cannot contain an assembly subtree`)
      modes.add(match.mode)
      const sourcePath = sourcePrefix ? `${sourcePrefix}/${node.name}` : node.name
      const canonicalPath = canonicalPrefix ? `${canonicalPrefix}/${match.name}` : match.name
      if (sourcePaths.has(sourcePath) || canonicalPaths.has(canonicalPath)) fail(`colliding native path ${canonicalPath}`)
      sourcePaths.add(sourcePath); canonicalPaths.add(canonicalPath)
      paths.push({ source: sourcePath, canonical: canonicalPath })
      pathNames.set(sourcePath, canonicalPath)
      nodeNames.set(node.name, match.name)
      native.set(index, match)
      json.nodes[index].name = match.name
      for (const child of node.children ?? []) visit(child, match, sourcePath, canonicalPath)
    } else {
      // Cameras and non-native scaffolding retain their names and every other field.
      if (match || typeof node.name === 'string' && /^(?:ha|ch|dt|vn|fr|mg|pd|pn|sm|sh)-/.test(node.name)) fail(`unrooted or unknown native node ${JSON.stringify(node.name)}`)
      for (const child of node.children ?? []) visit(child)
    }
    active.delete(index)
  }
  for (let index = 0; index < source.nodes.length; index++) if (!parents.has(index)) visit(index)
  if (visited.size !== source.nodes.length) fail('cyclic or unreachable native hierarchy')
  if (!native.size) fail('no authoritative native assembly root found')
  if (modes.size !== 1) fail('mixed legacy and canonical native identities')
  const mode = [...modes][0]
  const localDomains = Object.fromEntries([['name', nodeNames], ['path', pathNames]].map(([field, exact]) => [
    field, { exact, reverse: new Map([...exact].map(([source, canonical]) => [canonical, source])) },
  ]))
  function identityValue(value, field) {
    if (typeof value !== 'string') fail(`native identity ${field} extra must be a string`)
    const { exact, reverse } = localDomains[field] ?? map.domains[field]
    if (mode === 'old') {
      if (exact.has(value)) return exact.get(value)
      if (reverse.has(value)) fail('mixed legacy and canonical native identity extras')
    } else {
      if (reverse.has(value)) return value
      if (exact.has(value)) fail('mixed legacy and canonical native identity extras')
    }
    fail(`unknown native identity extra ${field}: ${JSON.stringify(value)}`)
  }
  function numberValue(value, row) {
    if (typeof value !== 'string') fail('native identity number extra must be a string')
    const matches = ['old', 'new'].filter(epoch => {
      const base = row[`${epoch}_number`]
      return value === base || value.startsWith(base) && /^-T[0-9]{3}$/.test(value.slice(base.length))
    })
    if (matches.length !== 1) fail(`unknown or ambiguous native number extra ${JSON.stringify(value)} for ${row.old_stem}`)
    if (matches[0] !== mode) fail('mixed legacy and canonical native identity extras')
    return row.new_number + value.slice(row[`${matches[0]}_number`].length)
  }
  function extras(value, row) {
    // Only explicitly native identity fields are authorized. Descriptions,
    // user annotations and all other extras remain byte-semantically unchanged.
    if (!isRecord(value)) return value
    const result = { ...value }
    if (Object.hasOwn(value, 'nativeIdentity')) {
      if (!isRecord(value.nativeIdentity)) fail('nativeIdentity extra must be an object')
      result.nativeIdentity = Object.fromEntries(Object.entries(value.nativeIdentity).map(([key, item]) => [
        key, key === 'number' ? numberValue(item, row) : IDENTITY_FIELDS.has(key) ? identityValue(item, key) : item,
      ]))
    }
    if (Object.hasOwn(value, 'nativePath')) result.nativePath = identityValue(value.nativePath, 'path')
    if (Object.hasOwn(value, 'nativePaths')) {
      if (!Array.isArray(value.nativePaths)) fail('nativePaths extra must be an array')
      result.nativePaths = value.nativePaths.map(item => identityValue(item, 'path'))
    }
    return result
  }
  let renamedNodes = 0
  for (const index of native.keys()) {
    if (source.nodes[index].extras !== undefined) json.nodes[index].extras = extras(source.nodes[index].extras, native.get(index).row)
    if (!isDeepStrictEqual(source.nodes[index], json.nodes[index])) renamedNodes++
  }
  return { json, paths, renamedNodes, nodeCount: source.nodes.length }
}

function readHeader(bytes, size = bytes.length) {
  if (bytes.length < 20 || bytes.readUInt32LE(0) !== 0x46546c67 || bytes.readUInt32LE(4) !== 2 || bytes.readUInt32LE(8) !== size) fail('invalid GLB header or length')
  const jsonLength = bytes.readUInt32LE(12)
  if (bytes.readUInt32LE(16) !== 0x4e4f534a || jsonLength % 4 || 20 + jsonLength > size) fail('invalid first GLB JSON chunk')
  return jsonLength
}
function decodeJson(bytes) {
  try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)) }
  catch (error) { fail(`invalid GLB JSON: ${error.message}`) }
}
// This input is a parsed JSON tree, not arbitrary JavaScript values. Preserve
// signed zero while retaining JSON.stringify's escaping and Number semantics;
// JSON.parse has already rounded any unrepresentable source numeric lexemes.
function stringifyJson(value) {
  if (Object.is(value, -0)) return '-0'
  if (Array.isArray(value)) return `[${value.map(stringifyJson).join(',')}]`
  if (isRecord(value)) return `{${Object.entries(value).map(([key, item]) => `${JSON.stringify(key)}:${stringifyJson(item)}`).join(',')}}`
  return JSON.stringify(value)
}
function prefixBytes(json, trailingLength) {
  const text = Buffer.from(stringifyJson(json)), jsonLength = align4(text.length)
  const prefix = Buffer.alloc(20 + jsonLength, 0x20)
  prefix.writeUInt32LE(0x46546c67, 0); prefix.writeUInt32LE(2, 4)
  prefix.writeUInt32LE(prefix.length + trailingLength, 8)
  prefix.writeUInt32LE(jsonLength, 12); prefix.writeUInt32LE(0x4e4f534a, 16)
  text.copy(prefix, 20)
  return prefix
}
function asBytes(input) {
  if (input instanceof ArrayBuffer) return Buffer.from(input)
  if (ArrayBuffer.isView(input)) return Buffer.from(input.buffer, input.byteOffset, input.byteLength)
  fail('input must be an ArrayBuffer or typed-array byte view')
}
function validateTrailingChunks(bytes, offset) {
  for (let cursor = offset; cursor < bytes.length;) {
    if (cursor + 8 > bytes.length) fail('truncated GLB chunk header')
    const length = bytes.readUInt32LE(cursor)
    if (length % 4 || cursor + 8 + length > bytes.length || bytes.readUInt32LE(cursor + 4) !== 0x004e4942 || cursor !== offset) fail('invalid, duplicate or unsupported trailing GLB chunk')
    cursor += 8 + length
  }
}

// Independent preservation oracle: never calls projectDocument and never
// restores whole nodes, extras objects or nativeIdentity containers. A mapper
// bug changing geometry, hierarchy, transforms or annotations therefore fails
// even if recomputing the mapper would reproduce the same unauthorized change.
function assertOnlyIdentityFieldsChanged(before, actual, map) {
  if (!isRecord(before) || !Array.isArray(before.nodes) || !isRecord(actual)
    || !Array.isArray(actual.nodes) || actual.nodes.length !== before.nodes.length) fail('unauthorized glTF semantic change: node inventory')
  const restored = structuredClone(actual)
  function restoreScalar(source, target, key) {
    if (isRecord(source) && isRecord(target) && Object.hasOwn(source, key) && Object.hasOwn(target, key)
      && typeof source[key] === 'string' && typeof target[key] === 'string') target[key] = source[key]
  }
  for (const [index, original] of before.nodes.entries()) {
    if (!isRecord(original)) fail('invalid source node shape')
    const node = restored.nodes[index]
    if (!isRecord(node)) fail('unauthorized glTF semantic change: node shape')
    const match = matchName(original.name, map)
    if (!match) continue
    if (node.name !== original.name && node.name !== match.name) fail(`unauthorized glTF semantic change: native name at node ${index}`)
    restoreScalar(original, node, 'name')
    const sourceExtras = original.extras, targetExtras = node.extras
    if (!isRecord(sourceExtras) || !isRecord(targetExtras)) continue
    for (const key of IDENTITY_FIELDS) restoreScalar(sourceExtras.nativeIdentity, targetExtras.nativeIdentity, key)
    restoreScalar(sourceExtras, targetExtras, 'nativePath')
    if (Array.isArray(sourceExtras.nativePaths) && Array.isArray(targetExtras.nativePaths)
      && sourceExtras.nativePaths.length === targetExtras.nativePaths.length) {
      for (let i = 0; i < sourceExtras.nativePaths.length; i++) {
        if (typeof sourceExtras.nativePaths[i] === 'string' && typeof targetExtras.nativePaths[i] === 'string') {
          targetExtras.nativePaths[i] = sourceExtras.nativePaths[i]
        }
      }
    }
  }
  if (!isDeepStrictEqual(before, restored)) fail('unauthorized glTF semantic change: fields outside the native identity allowlist')
}

/** Independently checks the projected document and every untouched trailing byte. */
export async function validateNativeIdentityProjection(sourceInput, canonicalInput, { mapPath = MAP_PATH } = {}) {
  const source = asBytes(sourceInput), canonical = asBytes(canonicalInput)
  const beforeLength = readHeader(source), afterLength = readHeader(canonical)
  validateTrailingChunks(source, 20 + beforeLength); validateTrailingChunks(canonical, 20 + afterLength)
  const before = decodeJson(source.subarray(20, 20 + beforeLength)), map = await loadNativeIdentityMap(mapPath)
  const actual = decodeJson(canonical.subarray(20, 20 + afterLength))
  assertOnlyIdentityFieldsChanged(before, actual, map)
  const expected = projectDocument(before, map)
  // This covers node order/hierarchy, transforms, accessors, geometry, materials,
  // unused definitions and unknown document fields, not just drawable counts.
  if (!isDeepStrictEqual(expected.json, actual)) fail('unauthorized glTF semantic change; only authoritative node identity names/extras may differ')
  if (!source.subarray(20 + beforeLength).equals(canonical.subarray(20 + afterLength))) fail('binary payload or GLB chunk change')
  return { passed: true, identity: { mapSha256: NATIVE_IDENTITY_MAP_SHA256, canonicalSha256: sha256(canonical), renamedNodes: expected.renamedNodes, nodeCount: expected.nodeCount }, paths: expected.paths }
}

export async function projectNativeIdentity(sourceInput, { mapPath = MAP_PATH } = {}) {
  const bytes = asBytes(sourceInput), jsonLength = readHeader(bytes)
  validateTrailingChunks(bytes, 20 + jsonLength)
  const projected = projectDocument(decodeJson(bytes.subarray(20, 20 + jsonLength)), await loadNativeIdentityMap(mapPath))
  const trailing = bytes.subarray(20 + jsonLength)
  // The BIN chunk (including padding) is copied verbatim; only the JSON chunk is encoded.
  const canonicalBytes = projected.renamedNodes ? Buffer.concat([prefixBytes(projected.json, trailing.length), trailing]) : bytes
  return { canonicalBytes, identity: { mapSha256: NATIVE_IDENTITY_MAP_SHA256, canonicalSha256: sha256(canonicalBytes), renamedNodes: projected.renamedNodes, nodeCount: projected.nodeCount }, paths: projected.paths }
}

async function readExactly(file, bytes, position) {
  let offset = 0
  while (offset < bytes.length) {
    const { bytesRead } = await file.read(bytes, offset, bytes.length - offset, position + offset)
    if (!bytesRead) fail('truncated GLB file')
    offset += bytesRead
  }
}

/** Read JSON once, then stream untouched chunks into both hashes without a full GLB allocation. */
export async function nativeIdentityPaths(modelPath, { mapPath = MAP_PATH } = {}) {
  const file = await open(modelPath, 'r')
  try {
    const size = (await file.stat()).size, header = Buffer.alloc(20)
    await readExactly(file, header, 0)
    const jsonLength = readHeader(header, size), jsonBytes = Buffer.alloc(jsonLength)
    await readExactly(file, jsonBytes, 20)
    const projected = projectDocument(decodeJson(jsonBytes), await loadNativeIdentityMap(mapPath))
    const start = 20 + jsonLength, rawHash = createHash('sha256'), canonicalHash = createHash('sha256')
    rawHash.update(header).update(jsonBytes)
    canonicalHash.update(projected.renamedNodes ? prefixBytes(projected.json, size - start) : header)
    if (!projected.renamedNodes) canonicalHash.update(jsonBytes)
    const buffer = Buffer.alloc(Math.min(1024 * 1024, Math.max(size - start, 8)))
    if (start < size) {
      const chunkHeader = Buffer.alloc(8)
      await readExactly(file, chunkHeader, start)
      if (chunkHeader.readUInt32LE(4) !== 0x004e4942 || chunkHeader.readUInt32LE(0) % 4 || start + 8 + chunkHeader.readUInt32LE(0) !== size) fail('invalid, duplicate or unsupported trailing GLB chunk')
    }
    for (let cursor = start; cursor < size;) {
      const length = Math.min(buffer.length, size - cursor), chunk = buffer.subarray(0, length)
      await readExactly(file, chunk, cursor)
      rawHash.update(chunk); canonicalHash.update(chunk); cursor += length
    }
    if ((await file.stat()).size !== size) fail('raw model changed while reading')
    return { rawSha256: rawHash.digest('hex'), identity: { mapSha256: NATIVE_IDENTITY_MAP_SHA256, canonicalSha256: canonicalHash.digest('hex'), renamedNodes: projected.renamedNodes, nodeCount: projected.nodeCount }, paths: projected.paths }
  } finally { await file.close() }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2)
    if (args.length !== 3 || args[0] !== '--model' || args[2] !== '--paths-only' || !args[1]) fail('usage: native-identity-map.mjs --model <raw.glb> --paths-only')
    console.log(JSON.stringify(await nativeIdentityPaths(resolve(args[1]))))
  } catch (error) {
    console.error(error.message)
    process.exitCode = 1
  }
}
