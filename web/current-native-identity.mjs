/**
 * Current naming at the sealed archive's ingestion boundary, not a CAD rebuild.
 * The release's map, GLB/representation hashes, source files and evidence remain
 * exact historical inputs. This independently pinned table changes identity only.
 */
import mapping from './content/current-native-identities.json' with { type: 'json' }

export const CURRENT_NATIVE_IDENTITY_MAP_SHA256 = '55483bab7ebd0de57d71839288628de50229f881172c83515512ff937df49af9'
export const CURRENT_NATIVE_IDENTITY_PROJECTION = Object.freeze({
  kind: 'current-native-identity-projection',
  mapSha256: CURRENT_NATIVE_IDENTITY_MAP_SHA256,
  sourceMapSha256: mapping.sourceMapSha256,
})

const fail = message => { throw new Error(`Current native identity projection: ${message}`) }
if (mapping.schemaVersion !== 1 || mapping.kind !== CURRENT_NATIVE_IDENTITY_PROJECTION.kind
  || mapping.numberWidth !== 2 || mapping.sourceMapSha256 !== '1ee9084204cab7025783c5bf0fa98e040cfaa3e4e8200f0d61e58e8dd32c3bfd') fail('invalid frozen mapping')

/** Check the actual imported/loaded table, not just two copies of its declared pin. */
export async function validateCurrentNativeIdentityTable(table = mapping) {
  const bytes = new TextEncoder().encode(JSON.stringify(table))
  const hash = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  const observed = Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('')
  if (observed !== CURRENT_NATIVE_IDENTITY_MAP_SHA256) fail('current table SHA256 mismatch')
}

const aliases = new Map(mapping.archivedAliases.map(row => [row.sourceStem, row.stem]))
const archivedNumbers = new Map(mapping.archivedNumbers.map(row => [row.sourceStem, row.sourceNumber]))
const sources = new Map(), targets = new Map()
function register(sourceStem, sourceNumber, identities) {
  if (!identities.length) fail(`empty mapping for ${sourceStem}`)
  const row = sources.get(sourceStem) ?? { sourceStem, sourceNumber, identities: [] }
  if (row.sourceNumber !== sourceNumber) fail(`conflicting historical number for ${sourceStem}`)
  row.identities.push(...identities)
  sources.set(sourceStem, row)
  for (const identity of identities) {
    const key = `${identity.parent ?? ''}/${identity.stem}`
    if (targets.has(key)) fail(`colliding current identity ${key}`)
    targets.set(key, { row, identity })
  }
}
for (const row of [...mapping.machineVendors, ...mapping.nativeIdentities]) register(row.sourceStem, row.sourceNumber, row.identities)
for (const row of [...mapping.toolingVendors, ...mapping.archiveOnlyVendors]) register(row.sourceStem, row.sourceNumber, [row])
const tokens = [...new Set([...sources.keys(), ...aliases.keys(), ...Array.from(targets.values(), value => value.identity.stem)])].sort((a, b) => b.length - a.length)
const INSTANCE = /^(?:(?:--[A-Za-z][A-Za-z0-9_.]*)?-[1-9][0-9]*|-stretch[0-9]{2}-[1-9][0-9]*)(?:@[A-Za-z][A-Za-z0-9_-]*)?$/
const ROOT = 'ha-harmonic-analyzer'

function token(name) {
  if (typeof name !== 'string') return null
  for (const stem of tokens) if (name === stem || name.startsWith(stem) && INSTANCE.test(name.slice(stem.length))) return { stem, suffix: name.slice(stem.length) }
  return null
}
function resolveIdentity(stem, parent) {
  const sourceStem = aliases.get(stem) ?? stem
  const row = sources.get(sourceStem)
  if (row) {
    // Multi-parent source identities are deliberately not a global rename.
    const candidates = row.identities.filter(identity => !identity.parent || identity.parent === parent)
    if (candidates.length !== 1) fail(`native identity ${stem} has no unique immediate parent ${parent ?? '<root>'}`)
    return { row, identity: candidates[0] }
  }
  const exact = targets.get(`${parent ?? ''}/${stem}`) ?? targets.get(`/${stem}`)
  if (!exact) fail(`unknown native identity ${stem} below ${parent ?? '<root>'}`)
  return exact
}

/** A complete qualified native path, with all occurrence/configuration suffixes retained. */
export function projectCurrentNativePath(path) {
  if (typeof path !== 'string') fail('native path must be a string')
  if (path !== ROOT && !path.startsWith(`${ROOT}/`)) return path
  if (path.includes('\\') || path.split('/').some(part => !part || part === '.' || part === '..')) fail(`unsafe native path ${path}`)
  let parent = null
  return path.split('/').map(name => {
    const found = token(name)
    if (!found) {
      if (name.startsWith('vn-')) fail(`unknown vendor component ${name}`)
      parent = name
      return name
    }
    const { identity } = resolveIdentity(found.stem, parent)
    parent = identity.stem
    return identity.stem + found.suffix
  }).join('/')
}

/** Resolve a registry Number using its native stem and immediate assembly parent. */
export function projectCurrentNativeNumber(number, stem, parent = null) {
  const found = token(stem)
  if (!found) fail(`unknown native identity ${stem}`)
  const { row, identity } = resolveIdentity(found.stem, parent)
  const match = /^(.*?)(-T[0-9]{3})?$/.exec(number)
  if (!match || ![row.sourceNumber, archivedNumbers.get(found.stem), identity.number].includes(match[1])) fail(`number ${number} does not identify ${stem}`)
  if (identity.number === null) return null // Historical-only geometry has no invented current registry Number.
  return identity.number + (match[2] ?? '')
}

/**
 * Project authored/native metadata only where a complete qualified native path
 * occurs as a value or object key. Provenance paths, URLs, hashes and prose do
 * not match that grammar. Structural sharing keeps measurements/numeric arrays
 * exact rather than serializing, refitting or recomputing any geometry.
 */
export function projectCurrentNativeMetadata(value) {
  if (typeof value === 'string') return projectCurrentNativePath(value)
  if (!value || typeof value !== 'object') return value
  if (Array.isArray(value)) {
    let result = value
    for (let index = 0; index < value.length; index++) {
      const item = projectCurrentNativeMetadata(value[index])
      if (item !== value[index]) {
        if (result === value) result = value.slice()
        result[index] = item
      }
    }
    return result
  }
  let result = value
  for (const [key, original] of Object.entries(value)) {
    const currentKey = projectCurrentNativePath(key), item = projectCurrentNativeMetadata(original)
    if (currentKey !== key || item !== original) {
      if (result === value) result = { ...value }
      if (currentKey !== key) {
        if (Object.hasOwn(result, currentKey)) fail(`colliding metadata path ${currentKey}`)
        delete result[key]
      }
      result[currentKey] = item
    }
  }
  return result
}

/**
 * Project the already byte-verified parsed glTF JSON before GLTFLoader creates
 * objects. Only node names and declared native identity extras may change;
 * transforms, meshes/accessors/materials and every BIN byte stay untouched.
 */
export function projectCurrentNativeDocument(document) {
  if (!document || !Array.isArray(document.nodes)) fail('expected parsed glTF nodes')
  const parents = new Map()
  for (const [index, node] of document.nodes.entries()) for (const child of node.children ?? []) {
    if (!Number.isSafeInteger(child) || child < 0 || child >= document.nodes.length || parents.has(child)) fail('invalid native hierarchy')
    parents.set(child, index)
  }
  const paths = new Map(), active = new Set()
  function sourcePath(index) {
    if (paths.has(index)) return paths.get(index)
    if (active.has(index)) fail('cyclic native hierarchy')
    active.add(index)
    const node = document.nodes[index], parent = parents.get(index)
    const prefix = parent === undefined || node.name === ROOT ? '' : sourcePath(parent)
    const path = prefix ? `${prefix}/${node.name ?? ''}` : node.name ?? ''
    paths.set(index, path); active.delete(index)
    return path
  }
  for (let index = 0; index < document.nodes.length; index++) sourcePath(index)
  for (const [index, path] of paths) {
    const current = projectCurrentNativePath(path)
    const node = document.nodes[index]
    if (current !== path) node.name = current.slice(current.lastIndexOf('/') + 1)
    if (!node.extras || typeof node.extras !== 'object') continue
    const declared = { ...node.extras }
    if (typeof declared.nativePath === 'string') declared.nativePath = projectCurrentNativePath(declared.nativePath)
    if (Array.isArray(declared.nativePaths)) declared.nativePaths = declared.nativePaths.map(projectCurrentNativePath)
    node.extras = declared
    const identity = node.extras.nativeIdentity, found = token(path.slice(path.lastIndexOf('/') + 1))
    if (!identity || typeof identity !== 'object' || !found) continue
    const prefix = current.slice(0, current.lastIndexOf('/')), parentName = prefix.slice(prefix.lastIndexOf('/') + 1)
    const parent = token(parentName)?.stem ?? parentName
    const resolved = resolveIdentity(found.stem, parent || null)
    const result = { ...identity }
    if (result.name === node.name || result.name === path.slice(path.lastIndexOf('/') + 1)) result.name = node.name
    if (typeof result.path === 'string') result.path = projectCurrentNativePath(result.path)
    for (const field of ['stem', 'underscore', 'part', 'assembly']) if (typeof result[field] === 'string') {
      const old = field === 'stem' ? found.stem : found.stem.replaceAll('-', '_')
      if (result[field] === old) result[field] = field === 'stem' ? resolved.identity.stem : resolved.identity.stem.replaceAll('-', '_')
    }
    for (const field of ['registry', 'builder', 'file', 'module']) if (resolved.identity.status !== 'archive-only' && typeof result[field] === 'string') {
      const sourceDashed = found.stem, targetDashed = resolved.identity.stem
      const sourceUnderscore = sourceDashed.replaceAll('-', '_'), targetUnderscore = targetDashed.replaceAll('-', '_')
      result[field] = result[field].replace(new RegExp(`(?<![a-z0-9-])${sourceDashed}(?![a-z0-9-])`, 'g'), targetDashed)
        .replace(new RegExp(`(?<![a-z0-9])${sourceUnderscore}(?![a-z0-9])`, 'g'), targetUnderscore)
    }
    if (typeof result.number === 'string') result.number = projectCurrentNativeNumber(result.number, found.stem, parent || null)
    if (resolved.identity.status === 'archive-only') {
      result.archivedIdentity = { ...identity }
      if (typeof identity.number === 'string') result.archivedNumber = identity.number
      result.number = null
      result.registry = null
      result.builder = null
      for (const field of ['file', 'module']) if (Object.hasOwn(result, field)) result[field] = null
      result.status = 'archive-only'
    }
    node.extras = { ...node.extras, nativeIdentity: result }
  }
  return document
}
