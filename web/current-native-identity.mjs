/**
 * Current naming at the sealed archive's ingestion boundary, not a CAD rebuild.
 * The release's map, GLB/representation hashes, source files and evidence remain
 * exact historical inputs. This independently pinned table changes identity only.
 */
import mapping from './content/current-native-identities.json' with { type: 'json' }

export const CURRENT_NATIVE_IDENTITY_MAP_SHA256 = '79addb71fe2ae3ee60039f07577b6dc0e40b0104449f18096a0b7643ce4b73af'
export const CURRENT_NATIVE_OCCURRENCE_NAMESPACE = 'archive-role-local'
export const CURRENT_NATIVE_IDENTITY_PROJECTION = Object.freeze({
  kind: 'current-native-identity-projection',
  mapSha256: CURRENT_NATIVE_IDENTITY_MAP_SHA256,
  sourceMapSha256: mapping.sourceMapSha256,
  occurrenceNamespace: CURRENT_NATIVE_OCCURRENCE_NAMESPACE,
})

const fail = message => { throw new Error(`Current native identity projection: ${message}`) }
/** Archive logical selectors are not rebuilt-native Component2.Name2 values. */
export function requireCurrentNativeOccurrenceNamespace(namespace) {
  if (namespace !== CURRENT_NATIVE_OCCURRENCE_NAMESPACE) fail(`unsupported occurrence namespace ${namespace}; native readback is required`)
}
if (mapping.schemaVersion !== 1 || mapping.kind !== CURRENT_NATIVE_IDENTITY_PROJECTION.kind
  || mapping.numberWidth !== 2 || mapping.sourceMapSha256 !== '1ee9084204cab7025783c5bf0fa98e040cfaa3e4e8200f0d61e58e8dd32c3bfd') fail('invalid frozen mapping')
requireCurrentNativeOccurrenceNamespace(mapping.occurrenceNamespace)
/** Check the actual imported/loaded table, not just two copies of its declared pin. */
export async function validateCurrentNativeIdentityTable(table = mapping) {
  const bytes = new TextEncoder().encode(JSON.stringify(table))
  const hash = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  const observed = Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('')
  if (observed !== CURRENT_NATIVE_IDENTITY_MAP_SHA256) fail('current table SHA256 mismatch')
}

const aliases = new Map(mapping.archivedAliases.map(row => [row.sourceStem, row.stem]))
const archivedNumbers = new Map(mapping.archivedNumbers.map(row => [row.sourceStem, row.sourceNumber]))
const shared = new Map(mapping.sharedVendors.map(row => [row.stem, row]))
const sources = new Map(), targets = new Map(), priorTargets = new Map(), numbers = new Map()
const contextKey = identity => JSON.stringify([identity.parent ?? null, identity.stem, identity.configuration ?? null, identity.role ?? null])
function register(sourceStem, sourceNumber, identities) {
  if (!identities.length) fail(`empty mapping for ${sourceStem}`)
  const row = sources.get(sourceStem) ?? { sourceStem, sourceNumber, identities: [] }
  if (row.sourceNumber !== sourceNumber) fail(`conflicting historical number for ${sourceStem}`)
  for (const identity of identities) {
    if (row.identities.some(previous => contextKey(previous) === contextKey(identity))) fail(`colliding current identity for ${sourceStem}`)
    if (numbers.has(identity.stem) && numbers.get(identity.stem) !== identity.number) fail(`conflicting current Number for ${identity.stem}`)
    numbers.set(identity.stem, identity.number)
    const group = shared.get(identity.stem)
    if (group && (identity.number !== group.number || !group.configurations.includes(identity.configuration)
      || group.configurations.length > 1 && identity.role !== identity.configuration
      || typeof identity.role !== 'string' || !/^[A-Za-z][A-Za-z0-9]*$/.test(identity.role))) fail(`conflicting shared identity ${identity.stem}`)
    row.identities.push(identity)
    const record = { row, identity }, key = `${identity.parent ?? ''}/${identity.stem}`
    if (!targets.has(key)) targets.set(key, [])
    targets.get(key).push(record)
    if (identity.priorStem) {
      if (!priorTargets.has(identity.priorStem)) priorTargets.set(identity.priorStem, [])
      priorTargets.get(identity.priorStem).push(record)
    }
  }
  sources.set(sourceStem, row)
}
for (const row of [...mapping.machineVendors, ...mapping.nativeIdentities]) register(row.sourceStem, row.sourceNumber, row.identities)
for (const row of [...mapping.toolingVendors, ...mapping.archiveOnlyVendors]) register(row.sourceStem, row.sourceNumber, [row])
const tokens = [...new Set([...sources.keys(), ...aliases.keys(), ...priorTargets.keys(),
  ...Array.from(targets.values()).flatMap(records => records.map(record => record.identity.stem))])].sort((a, b) => b.length - a.length)
const INSTANCE = /^(?:__[A-Za-z][A-Za-z0-9]*)?(?:(?:--[A-Za-z][A-Za-z0-9_.]*)*-[1-9][0-9]*|-stretch[0-9]{2}-[1-9][0-9]*)(?:@[A-Za-z][A-Za-z0-9_-]*)?$/
const ROOT = 'ha-harmonic-analyzer'

function token(name, allowConfiguration = false) {
  if (typeof name !== 'string') return null
  for (const stem of tokens) if (name === stem || name.startsWith(stem)
    && (INSTANCE.test(name.slice(stem.length)) || allowConfiguration
      && /^(?:__[A-Za-z][A-Za-z0-9]*(?:--[A-Za-z][A-Za-z0-9_.]*)*|(?:--[A-Za-z][A-Za-z0-9_.]*)+)$/.test(name.slice(stem.length)))) return { stem, suffix: name.slice(stem.length) }
  return null
}
function resolveIdentity(stem, parent, suffix = '') {
  const sourceStem = aliases.get(stem) ?? stem, row = sources.get(sourceStem)
  let records = row ? row.identities.map(identity => ({ row, identity })) : priorTargets.get(stem)
  const current = !records
  records ??= targets.get(`${parent ?? ''}/${stem}`) ?? targets.get(`/${stem}`) ?? []
  records = records.filter(record => !record.identity.parent || record.identity.parent === parent)
  if (current) {
    const role = /^__([A-Za-z][A-Za-z0-9]*)/.exec(suffix)?.[1]
    const configuration = /^--([A-Za-z][A-Za-z0-9_.]*)/.exec(suffix)?.[1]
    if (role) records = records.filter(record => record.identity.role === role)
    if (configuration && shared.has(stem) && !shared.get(stem).configurations.includes('Default')) records = records.filter(record => record.identity.configuration === configuration)
  }
  const identities = new Map(records.map(record => [contextKey(record.identity), record.identity]))
  if (identities.size !== 1) fail(`native identity ${stem} has no unique immediate parent/member ${parent ?? '<root>'}`)
  const identity = identities.values().next().value
  const role = /^__([A-Za-z][A-Za-z0-9]*)/.exec(suffix)?.[1]
  if (role && role !== identity.role) fail(`wrong role for ${stem}`)
  const group = shared.get(identity.stem)
  if (group) {
    const configuration = /^--([A-Za-z][A-Za-z0-9_.]*)/.exec(suffix)?.[1]
    if (configuration && group.configurations.includes(configuration) && configuration !== identity.configuration) fail(`wrong configuration for ${stem}`)
  }
  return { records, identity }
}
function occurrenceSuffix(identity, suffix) {
  let qualifier = ''
  if (identity.configuration && identity.configuration !== 'Default') qualifier = `--${identity.configuration}`
  else if (identity.role) {
    const peers = targets.get(`${identity.parent ?? ''}/${identity.stem}`) ?? []
    if (new Set(peers.map(record => record.identity.role)).size > 1) qualifier = `__${identity.role}`
  }
  return qualifier && !suffix.startsWith(qualifier) ? qualifier + suffix : suffix
}

/** Qualified archive-role-local selector; never a claim about rebuilt Name2 indices. */
export function projectCurrentNativePath(path, occurrenceNamespace = CURRENT_NATIVE_OCCURRENCE_NAMESPACE) {
  requireCurrentNativeOccurrenceNamespace(occurrenceNamespace)
  if (typeof path !== 'string') fail('native path must be a string')
  if (path !== ROOT && !path.startsWith(`${ROOT}/`)) return path
  if (path.includes('\\') || path.split('/').some(part => !part || part === '.' || part === '..')) fail(`unsafe native path ${path}`)
  let parent = null
  return path.split('/').map(name => {
    const found = token(name)
    if (!found) {
      if (name.startsWith('vn-') || name.startsWith('sh-vn-')) fail(`unknown vendor component ${name}`)
      parent = name
      return name
    }
    const { identity } = resolveIdentity(found.stem, parent, found.suffix)
    parent = identity.stem
    return identity.stem + occurrenceSuffix(identity, found.suffix)
  }).join('/')
}

/** Resolve a registry Number using its stem and immediate parent/member context. */
export function projectCurrentNativeNumber(number, stem, parent = null) {
  const found = token(stem, true)
  if (!found) fail(`unknown native identity ${stem}`)
  const { records, identity } = resolveIdentity(found.stem, parent, found.suffix)
  const match = /^(.*?)(-T[0-9]{3})?$/.exec(number)
  const accepted = [archivedNumbers.get(found.stem), identity.number,
    ...records.flatMap(record => [record.row.sourceNumber, record.identity.priorNumber])]
  if (!match || !accepted.includes(match[1])) fail(`number ${number} does not identify ${stem}`)
  if (identity.number === null) return null
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
  if (Object.hasOwn(value, 'occurrenceNamespace')) requireCurrentNativeOccurrenceNamespace(value.occurrenceNamespace)
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
export function projectCurrentNativeDocument(document, occurrenceNamespace = CURRENT_NATIVE_OCCURRENCE_NAMESPACE) {
  requireCurrentNativeOccurrenceNamespace(occurrenceNamespace)
  if (!document || !Array.isArray(document.nodes)) fail('expected parsed glTF nodes')
  for (const extras of [document.extras, document.asset?.extras]) {
    if (extras && Object.hasOwn(extras, 'occurrenceNamespace')) requireCurrentNativeOccurrenceNamespace(extras.occurrenceNamespace)
  }
  for (const node of document.nodes) for (const extras of [node.extras, node.extras?.nativeIdentity]) {
    if (extras && Object.hasOwn(extras, 'occurrenceNamespace')) requireCurrentNativeOccurrenceNamespace(extras.occurrenceNamespace)
  }
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
    if (Array.isArray(declared.nativePaths)) declared.nativePaths = declared.nativePaths.map(value => projectCurrentNativePath(value))
    node.extras = declared
    const identity = node.extras.nativeIdentity, found = token(path.slice(path.lastIndexOf('/') + 1))
    if (!identity || typeof identity !== 'object' || !found) continue
    const prefix = current.slice(0, current.lastIndexOf('/')), parentName = prefix.slice(prefix.lastIndexOf('/') + 1)
    const parent = token(parentName)?.stem ?? parentName
    const resolved = resolveIdentity(found.stem, parent || null, found.suffix)
    const result = { ...identity }
    if (shared.has(resolved.identity.stem)) {
      result.configuration = resolved.identity.configuration
      result.role = resolved.identity.role
      result.occurrenceNamespace = CURRENT_NATIVE_OCCURRENCE_NAMESPACE
      const ordinal = /-([1-9][0-9]*)(?:@[A-Za-z][A-Za-z0-9_-]*)?$/.exec(found.suffix)?.[1]
      if (ordinal) result.semanticReference = `${resolved.identity.role}:${ordinal}`
    }
    if (result.name === node.name || result.name === path.slice(path.lastIndexOf('/') + 1)) result.name = node.name
    if (typeof result.path === 'string') result.path = projectCurrentNativePath(result.path)
    for (const field of ['stem', 'underscore', 'part', 'assembly']) if (typeof result[field] === 'string') {
      const old = field === 'stem' ? found.stem : found.stem.replaceAll('-', '_')
      if (result[field] === old) result[field] = field === 'stem' ? resolved.identity.stem : resolved.identity.stem.replaceAll('-', '_')
    }
    for (const field of ['registry', 'builder', 'file', 'module']) if (resolved.identity.status !== 'archive-only' && typeof result[field] === 'string') {
      const memberSource = mapping.sourceFiles.find(source => {
        if (source.configuration !== resolved.identity.configuration || source.role !== resolved.identity.role) return false
        const module = source.sourcePath.split('/').at(-1).slice(0, -3), kind = /_(geom|spec)$/.exec(module)?.[1]
        const sourceStems = new Set([found.stem, ...resolved.records.flatMap(record => [record.row.sourceStem, record.identity.priorStem])].filter(Boolean))
        const names = [source.sourcePath, module, module + '.py']
        if (kind) for (const stem of sourceStems) {
          const name = `${stem.replaceAll('-', '_')}_${kind}`
          names.push(name, `${name}.py`, `cad/scripts/${name}.py`)
        }
        return names.includes(result[field])
      })
      if (memberSource) {
        result[field] = field === 'module' ? memberSource.currentPath.split('/').at(-1).slice(0, -3) : memberSource.currentPath
        continue
      }
      const sourceDashed = found.stem, targetDashed = resolved.identity.stem
      const sourceUnderscore = sourceDashed.replaceAll('-', '_'), targetUnderscore = targetDashed.replaceAll('-', '_')
      result[field] = result[field].replace(new RegExp(`(?<![a-z0-9-])${sourceDashed}(?![a-z0-9-])`, 'g'), targetDashed)
        .replace(new RegExp(`(?<![a-z0-9])${sourceUnderscore}(?![a-z0-9])`, 'g'), targetUnderscore)
    }
    if (typeof result.number === 'string') result.number = projectCurrentNativeNumber(result.number, found.stem + found.suffix, parent || null)
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
