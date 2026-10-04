import { createHash, webcrypto } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { isAbsolute, relative, resolve, sep } from 'node:path'
import { pathToFileURL } from 'node:url'

const ORIGINAL_COMMIT = '9e72eb482a22797f48af5a6df2b00832b7137ace'
const ORIGINAL_SOURCE_SHA256 = Object.freeze({
  'src/scene.ts': 'ff16488a81948e0749beca5e12c56c49c5038792ef6910a4b0934bb5a72a9d54',
  'src/mechanics.ts': '731ae554aee8b77b7643073d4107f59a04ea530ad41612ec8de00316aaec183c',
  'src/mechanics-data.ts': 'fc838672c80170ada1bff42794438b5bd45ffcc2fc95030c8e29e677f8d6cd62',
  'src/kinematics.ts': '8bb5ffa3046609f9b3afa69dc72e37297e86c6a1d15fd1bdaf21b70b47ea561f',
  'src/magnifier.ts': '5941c074e7785b3f74e40baca8ad0d1d72da771162fd29805d5ecddb66b5afcd',
  'src/bindings.ts': '930cdcd9a46a9f11b7c97deb82abb6fa83681de12d84bd3d5615b061ca043d15',
  'src/source-witness.ts': '114fd8e9c176172a111a665534be22d0879741362ff2ebc3bd63bb0e7bbf03da',
  'src/image-plane-homography.ts': 'fd756310336f3eeed5eb637d78f3583c0400b9d76850060c30623e571d58ac71',
  'model-representation.mjs': '8d3cce25c5cff1d4e6151b3723816985fa41e3c7c9df8042d5c9804f638d29f2',
  'content/model-representation.json': 'a5b9ba0c336a0d5d36a2bcc5f36d651794d5e0c722768da5ac90374300dd2374',
})
const ORIGINAL_LOCK_SHA256 = '17a2451e21e525e2595aa5079d6abb57514a524f00c08d93aa52af4cc8a289fc'
const RAW_SHA256 = '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c'
const DELIVERY_SHA256 = '81750ae4c422b973dfd647df4e22f3088933003e39ff41c54563d780eb33fa65'
const DELIVERY_BYTE_LENGTH = 41071140
const MODEL_URL = 'https://original-native.invalid/models/harmonic-analyzer.glb'
const ENTRY_REQUESTS = { scene: '/src/scene.ts', sourceWitness: '/src/source-witness.ts', mechanics: '/src/mechanics.ts', bindings: '/src/bindings.ts', three: 'three', gltfLoader: 'three/examples/jsm/loaders/GLTFLoader.js' }
const encoder = new TextEncoder()
const decoder = new TextDecoder('utf-8', { fatal: true })
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
// The same sorted-key canonical JSON convention as verify-reference, without
// importing that module's current-descriptor side effect into frozen replay.
const canonicalJson = value => Array.isArray(value) ? `[${value.map(canonicalJson).join(',')}]`
  : value && typeof value === 'object' ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}` : JSON.stringify(value)
const manifestDigest = manifest => digest(canonicalJson(manifest))

function checkBytes(bytes, sha256, byteLength, label) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength !== byteLength || digest(bytes) !== sha256) throw new Error(`${label}: frozen byte identity mismatch`)
}
function assertCurrentAssets(raw, delivery) {
  if (!(raw instanceof Uint8Array) || digest(raw) !== RAW_SHA256) throw new Error('Original native raw GLB: not the admitted CURRENT462 bytes')
  checkBytes(delivery, DELIVERY_SHA256, DELIVERY_BYTE_LENGTH, 'Original native delivery GLB')
}
async function assetBytes(bytes, path, label) {
  if (bytes !== undefined && path !== undefined) throw new Error(`${label}: supply bytes or a path, not both`)
  if (bytes === undefined && path === undefined) throw new Error(`${label}: explicit protected asset bytes or path required`)
  if (bytes !== undefined) {
    if (!(bytes instanceof Uint8Array)) throw new Error(`${label}: Uint8Array bytes required`)
    return Uint8Array.from(bytes)
  }
  return readFile(path)
}
function requestForFile(id, webRoot) {
  const local = relative(webRoot, id)
  return !local.startsWith(`..${sep}`) && local !== '..' && !isAbsolute(local)
    ? `/${local.split(sep).join('/')}` : `/@fs/${id.split(sep).join('/')}`
}
function freezeRecords(value) {
  if (value && typeof value === 'object' && !ArrayBuffer.isView(value)) {
    for (const item of Object.values(value)) freezeRecords(item)
    Object.freeze(value)
  }
  return value
}

async function originalCameraNearFar(sourceText) {
  // Parse the ORIGINAL retained TypeScript, not current scene.ts and not the
  // renderer. Nonliteral/ambiguous constructors are unavailable, not defaults.
  const { default: ts } = await import('typescript')
  const source = ts.createSourceFile('original-scene.ts', sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  if (source.parseDiagnostics.length) throw new Error('Original CPU camera convention: original scene source cannot be parsed')
  const viewers = source.statements.filter(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === 'createViewer')
  if (viewers.length !== 1 || !viewers[0].body) throw new Error('Original CPU camera convention: unique original createViewer required')
  const cameras = []
  let rewritten = false
  function visit(node) {
    if (ts.isNewExpression(node) && ts.isPropertyAccessExpression(node.expression)
      && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === 'THREE' && node.expression.name.text === 'PerspectiveCamera') cameras.push(node)
    if (ts.isBinaryExpression(node) && node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment && node.operatorToken.kind <= ts.SyntaxKind.LastAssignment
      && ts.isPropertyAccessExpression(node.left) && ['near', 'far'].includes(node.left.name.text)) rewritten = true
    ts.forEachChild(node, visit)
  }
  visit(viewers[0].body)
  if (cameras.length !== 1 || rewritten || cameras[0].arguments?.length !== 4
    || !ts.isNumericLiteral(cameras[0].arguments[2]) || !ts.isNumericLiteral(cameras[0].arguments[3])) throw new Error('Original CPU camera convention: unique unchanged literal near/far constructor required')
  const nearFar = [Number(cameras[0].arguments[2].text), Number(cameras[0].arguments[3].text)]
  if (!nearFar.every(Number.isFinite) || nearFar[0] <= 0 || nearFar[1] <= nearFar[0]) throw new Error('Original CPU camera convention: invalid original clip planes')
  return Object.freeze(nearFar)
}

/**
 * Authorized admission step, not a qualification result. Read and hash original
 * code and both immutable models once; Vite transforms, but does not execute,
 * the complete scene/mechanics/input/Three/Meshopt graph. Retain this returned
 * byte closure and independently record manifestSHA256 BEFORE production runs.
 * createOriginalNativePoseOracle never regenerates it from current source.
 *
 * Sources and executable SSR transforms are both retained. Absolute module IDs
 * are labels/import-meta locations only during replay, never filesystem reads.
 */
export async function freezeOriginalNativeCPUClosure(options = {}) {
  if (typeof options.webRoot !== 'string' || !options.webRoot.trim()) throw new Error('Original CPU admission: explicit read-only published original webRoot required; no current-root default')
  const webRoot = resolve(options.webRoot)
  const rawGLBBytes = await assetBytes(options.rawGLBBytes, options.rawGLBPath, 'Raw GLB')
  const deliveryGLBBytes = await assetBytes(options.deliveryGLBBytes, options.deliveryGLBPath, 'Delivery GLB')
  assertCurrentAssets(rawGLBBytes, deliveryGLBBytes)
  const packageLockBytes = await readFile(resolve(webRoot, 'package-lock.json'))
  if (digest(packageLockBytes) !== ORIGINAL_LOCK_SHA256) throw new Error('Original CPU admission: published original locked package graph mismatch')
  const sources = new Map()
  for (const [path, sha256] of Object.entries(ORIGINAL_SOURCE_SHA256)) {
    const id = resolve(webRoot, path), bytes = await readFile(id)
    if (digest(bytes) !== sha256) throw new Error(`Original CPU admission: ${path} is not the admitted published ${ORIGINAL_COMMIT} bytes`)
    sources.set(id, bytes)
  }
  const { createServer } = await import('vite')
  const server = await createServer({
    root: webRoot, configFile: false, appType: 'custom',
    server: { middlewareMode: true, hmr: false, watch: null },
    ssr: { noExternal: true, optimizeDeps: { noDiscovery: true, include: [] } },
    plugins: [{ name: 'freeze-original-native-cpu-source', enforce: 'pre',
      async load(id) {
        if (!isAbsolute(id) || id.includes('?') || id.includes('\0')) throw new Error(`Original CPU closure has an unsupported module: ${id}`)
        let bytes = sources.get(id)
        if (!bytes) { bytes = await readFile(id); sources.set(id, bytes) }
        return decoder.decode(bytes)
      },
    }],
  })
  try {
    const environment = server.environments.ssr
    const modules = new Map()
    async function resolveImport(specifier, importer) {
      const resolved = await environment.pluginContainer.resolveId(specifier, importer)
      if (!resolved || resolved.external || !isAbsolute(resolved.id) || resolved.id.includes('?') || resolved.id.includes('\0')) throw new Error(`Original CPU closure refuses an external/unresolved module: ${specifier}`)
      const local = relative(webRoot, resolved.id)
      if (local === '..' || local.startsWith(`..${sep}`) || isAbsolute(local)) throw new Error(`Original CPU closure refuses a dependency outside the explicit original root: ${specifier}`)
      return resolved.id
    }
    async function collect(id) {
      if (modules.has(id)) return
      // Mark before descending so genuine module cycles are a closed graph.
      const record = { id, sourceSHA256: '', sourceByteLength: 0, transformedSHA256: '', transformedByteLength: 0, imports: [], dynamicImports: [] }
      modules.set(id, record)
      const transformed = await environment.transformRequest(requestForFile(id, webRoot))
      if (!transformed?.ssr || typeof transformed.code !== 'string' || !sources.has(id)) throw new Error(`Original CPU closure was not SSR transformed: ${id}`)
      const source = sources.get(id)
      const executable = encoder.encode(transformed.code)
      Object.assign(record, { sourceSHA256: digest(source), sourceByteLength: source.byteLength, transformedSHA256: digest(executable), transformedByteLength: executable.byteLength })
      record.bytes = { id, source, transformed: executable }
      for (const [field, dependencies] of [['imports', transformed.deps ?? []], ['dynamicImports', transformed.dynamicDeps ?? []]]) {
        for (const specifier of dependencies) {
          const moduleId = await resolveImport(specifier, id)
          record[field].push({ specifier, moduleId })
          await collect(moduleId)
        }
      }
    }
    const entries = {}
    for (const [name, specifier] of Object.entries(ENTRY_REQUESTS)) {
      entries[name] = await resolveImport(specifier)
      await collect(entries[name])
    }
    const records = [...modules.values()].sort((a, b) => a.id.localeCompare(b.id))
    const cameraNearFar = await originalCameraNearFar(decoder.decode(sources.get(entries.scene)))
    const manifest = freezeRecords({ schemaVersion: 1, kind: 'frozen-original-native-cpu-vite-ssr', entries, modelURL: MODEL_URL,
      cameraNearFar,
      original: { sourceCommit: ORIGINAL_COMMIT, inventoryAdapter: 'published-original-readonly-observer', packageLockSHA256: ORIGINAL_LOCK_SHA256, packageLockByteLength: packageLockBytes.byteLength,
        code: Object.entries(ORIGINAL_SOURCE_SHA256).map(([path, sourceSHA256]) => ({ path, id: resolve(webRoot, path), sourceSHA256 })) },
      assets: { rawSHA256: RAW_SHA256, rawByteLength: rawGLBBytes.byteLength, deliverySHA256: DELIVERY_SHA256, deliveryByteLength: DELIVERY_BYTE_LENGTH },
      modules: records.map(({ bytes, ...record }) => record),
    })
    return { manifest, manifestSHA256: manifestDigest(manifest), modules: records.map(record => record.bytes), packageLockBytes, rawGLBBytes, deliveryGLBBytes }
  } finally { await server.close() }
}

/**
 * Read an already admitted byte archive. The independently provided manifest
 * SHA is mandatory; manifest.sha256 is never read as an authority. No freeze,
 * current source import, model regeneration, alternate filename or fallback.
 * Buffers returned by readFile already are Uint8Arrays and are retained as-is.
 * createOriginalNativePoseOracle subsequently rehashes every asset/code byte.
 */
export async function readOriginalNativeCPUClosure({ archive, manifestSHA256 } = {}) {
  if (typeof archive !== 'string' || !archive.trim() || !/^[a-f0-9]{64}$/.test(manifestSHA256 ?? '')) throw new Error('Original CPU archive: directory and independently pinned manifest SHA256 required')
  const directory = resolve(archive)
  const manifest = JSON.parse(await readFile(resolve(directory, 'manifest.json'), 'utf8'))
  if (manifestDigest(manifest) !== manifestSHA256) throw new Error('Original CPU archive: independently pinned manifest SHA256 mismatch')
  if (manifest?.schemaVersion !== 1 || manifest.kind !== 'frozen-original-native-cpu-vite-ssr' || !Array.isArray(manifest.modules)) throw new Error('Original CPU archive: unsupported admitted manifest')
  const ids = new Set()
  for (const record of manifest.modules) {
    if (!record || typeof record.id !== 'string' || ids.has(record.id)) throw new Error('Original CPU archive: missing/duplicate module identity')
    ids.add(record.id)
  }
  const [rawGLBBytes, deliveryGLBBytes, packageLockBytes, modules] = await Promise.all([
    readFile(resolve(directory, 'raw.glb')),
    readFile(resolve(directory, 'delivery.glb')),
    readFile(resolve(directory, 'package-lock.json')),
    Promise.all(manifest.modules.map(async (record, i) => {
      const [source, transformed] = await Promise.all([readFile(resolve(directory, `${i}.source`)), readFile(resolve(directory, `${i}.ssr`))])
      return { id: record.id, source, transformed }
    })),
  ])
  return { manifest: freezeRecords(manifest), manifestSHA256, modules, packageLockBytes, rawGLBBytes, deliveryGLBBytes }
}

function checkedClosure(closure) {
  if (!closure || !/^[a-f0-9]{64}$/.test(closure.manifestSHA256 ?? '') || manifestDigest(closure.manifest) !== closure.manifestSHA256) throw new Error('Original CPU closure: independently pinned manifest SHA256 required/mismatched')
  const manifest = closure.manifest
  if (manifest.schemaVersion !== 1 || manifest.kind !== 'frozen-original-native-cpu-vite-ssr' || manifest.modelURL !== MODEL_URL
    || manifest.original?.sourceCommit !== ORIGINAL_COMMIT || manifest.original?.inventoryAdapter !== 'published-original-readonly-observer'
    || manifest.original?.packageLockSHA256 !== ORIGINAL_LOCK_SHA256
    || manifest.assets?.rawSHA256 !== RAW_SHA256 || manifest.assets?.deliverySHA256 !== DELIVERY_SHA256 || manifest.assets?.deliveryByteLength !== DELIVERY_BYTE_LENGTH) throw new Error('Original CPU closure: unsupported original reference/assets')
  checkBytes(closure.rawGLBBytes, manifest.assets.rawSHA256, manifest.assets.rawByteLength, 'Frozen raw GLB')
  checkBytes(closure.deliveryGLBBytes, manifest.assets.deliverySHA256, manifest.assets.deliveryByteLength, 'Frozen delivery GLB')
  checkBytes(closure.packageLockBytes, ORIGINAL_LOCK_SHA256, manifest.original.packageLockByteLength, 'Frozen original package lock')
  if (!Array.isArray(closure.modules) || !Array.isArray(manifest.modules) || closure.modules.length !== manifest.modules.length) throw new Error('Original CPU closure: incomplete module bytes')
  const bytesById = new Map()
  for (const bytes of closure.modules) {
    if (!bytes || typeof bytes.id !== 'string' || bytesById.has(bytes.id)) throw new Error('Original CPU closure: duplicate/malformed module bytes')
    bytesById.set(bytes.id, bytes)
  }
  const modules = new Map()
  for (const record of manifest.modules) {
    const bytes = bytesById.get(record.id)
    if (!bytes || modules.has(record.id) || !Array.isArray(record.imports) || !Array.isArray(record.dynamicImports)) throw new Error('Original CPU closure: missing/duplicate module identity')
    checkBytes(bytes.source, record.sourceSHA256, record.sourceByteLength, `Frozen source ${record.id}`)
    checkBytes(bytes.transformed, record.transformedSHA256, record.transformedByteLength, `Frozen executable ${record.id}`)
    // Decode every executable BEFORE any one can execute; later mutation of the
    // caller's Uint8Arrays cannot change this session's original reference.
    modules.set(record.id, { code: decoder.decode(bytes.transformed), imports: new Map(record.imports.map(edge => [edge.specifier, edge.moduleId])), dynamicImports: new Map(record.dynamicImports.map(edge => [edge.specifier, edge.moduleId])) })
  }
  for (const module of modules.values()) for (const edges of [module.imports, module.dynamicImports]) for (const id of edges.values()) if (!modules.has(id)) throw new Error(`Original CPU closure: missing imported bytes ${id}`)
  for (const name of Object.keys(ENTRY_REQUESTS)) if (!modules.has(manifest.entries?.[name])) throw new Error(`Original CPU closure: missing entry ${name}`)
  if (!Array.isArray(manifest.original.code) || manifest.original.code.length !== Object.keys(ORIGINAL_SOURCE_SHA256).length) throw new Error('Original CPU closure: incomplete published original code authority')
  for (const [path, sha256] of Object.entries(ORIGINAL_SOURCE_SHA256)) {
    const admitted = manifest.original.code.filter(record => record.path === path)
    if (admitted.length !== 1 || admitted[0].sourceSHA256 !== sha256) throw new Error(`Original CPU closure: published original source binding mismatch ${path}`)
    const bytes = bytesById.get(admitted[0].id)
    if (bytes && digest(bytes.source) !== sha256) throw new Error(`Original CPU closure: not the published original bytes ${path}`)
    if (path === 'src/scene.ts' && admitted[0].id !== manifest.entries.scene) throw new Error('Original CPU closure: scene entry is not the admitted original source')
  }
  // Small metadata copy, not a per-view model/vertex copy.
  return { manifest: JSON.parse(JSON.stringify(manifest)), modules, deliveryGLBBytes: closure.deliveryGLBBytes }
}

function frozenModuleScope(modules) {
  const loaded = new Map()
  const AsyncFunction = (async function () {}).constructor
  async function execute(id, ancestry = []) {
    const existing = loaded.get(id)
    if (existing) return ancestry.includes(id) ? existing.exports : existing.promise
    const module = modules.get(id)
    if (!module) throw new Error(`Original CPU replay refuses an unlisted module: ${id}`)
    const exports = Object.create(null)
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' })
    const state = { exports, promise: null }
    loaded.set(id, state)
    const chain = [...ancestry, id]
    const importModule = async (specifier, metadata, dynamic = false) => {
      const target = (dynamic ? module.dynamicImports : module.imports).get(String(specifier))
      if (!target) throw new Error(`Original CPU replay refuses an unlisted import: ${specifier} from ${id}`)
      const imported = await execute(target, chain)
      for (const name of metadata?.importedNames ?? []) if (!(name in imported)) throw new Error(`Original CPU replay: absent ${name} export from ${target}`)
      return imported
    }
    const defineExport = (name, getter) => Object.defineProperty(exports, name, { enumerable: true, configurable: true, get: getter })
    const exportAll = imported => { for (const key of Object.keys(imported)) if (key !== 'default' && key !== '__esModule' && !(key in exports)) defineExport(key, () => imported[key]) }
    // Exactly Vite's ESModulesEvaluator callback interface. This executes the
    // frozen Vite transform, not a port/reimplementation of scene/pose laws.
    state.promise = new AsyncFunction('__vite_ssr_exports__', '__vite_ssr_import_meta__', '__vite_ssr_import__', '__vite_ssr_dynamic_import__', '__vite_ssr_exportAll__', '__vite_ssr_exportName__', `"use strict";\n${module.code}`)(exports,
      { url: pathToFileURL(id).href, env: { SSR: true, BASE_URL: '/' } }, importModule, specifier => importModule(specifier, undefined, true), exportAll, defineExport)
      .then(() => { Object.seal(exports); return exports })
    return state.promise
  }
  return { execute, dispose() { loaded.clear(); modules.clear() } }
}

// Global adaptation is limited to the actual asynchronous GLTF load. Restore
// exact descriptors even on failure; reject concurrent scopes rather than race
// another oracle's asset provider. solve() is synchronous and needs no globals.
let globalScopeActive = false
async function withNativeNodeGlobals(deliveryBytes, callback) {
  if (globalScopeActive) throw new Error('Original native CPU asset scope is already active')
  globalScopeActive = true
  const names = ['fetch', 'self', 'location', 'crypto']
  const descriptors = new Map(names.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]))
  try {
    Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: async request => {
      const url = typeof request === 'string' ? request : request instanceof URL ? request.href : request?.url
      if (url !== MODEL_URL) throw new Error(`Original native CPU refuses an unlisted asset: ${url}`)
      return new Response(deliveryBytes, { status: 200 })
    } })
    Object.defineProperty(globalThis, 'self', { configurable: true, value: globalThis })
    Object.defineProperty(globalThis, 'location', { configurable: true, value: Object.freeze({ href: MODEL_URL }) })
    if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { configurable: true, value: webcrypto })
    return await callback()
  } finally {
    for (const [name, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor)
      else delete globalThis[name]
    }
    globalScopeActive = false
  }
}

function canonicalIndices(geometry, path) {
  const count = geometry.getAttribute('position')?.count
  if (!Number.isSafeInteger(count) || count <= 0) throw new Error(`Original native inventory: position missing at ${path}`)
  const index = geometry.getIndex()
  const originalU32 = index && !index.isInterleavedBufferAttribute && !index.normalized && index.itemSize === 1 && index.array instanceof Uint32Array
  const indices = originalU32 ? index.array : new Uint32Array(index ? index.count : count)
  for (let i = 0; i < indices.length; i++) {
    const value = index ? index.getX(i) : i
    if (!Number.isSafeInteger(value) || value < 0 || value >= count) throw new Error(`Original native inventory: index out of range at ${path}`)
    if (!originalU32) indices[i] = value
  }
  if (indices.length % 3) throw new Error(`Original native inventory: nontriangle index topology at ${path}`)
  return indices
}
function validateOverrides(overrides, partPaths) {
  if (!Array.isArray(overrides)) throw new Error('Original native pose: overrides must be an array')
  const seen = new Set()
  for (const item of overrides) {
    if (!item || typeof item !== 'object' || typeof item.partPath !== 'string' || !partPaths.has(item.partPath) || seen.has(item.partPath)
      || Object.keys(item).some(key => !['partPath', 'visibility', 'worldPositionMetres', 'worldQuaternion', 'evidence', 'sourceTimeSeconds', 'landmarkIds'].includes(key))) throw new Error('Original native pose: unknown/duplicate override part or field')
    seen.add(item.partPath)
    if (item.visibility !== undefined && !['visible', 'hidden'].includes(item.visibility)) throw new Error('Original native pose: invalid override visibility')
    for (const [field, count] of [['worldPositionMetres', 3], ['worldQuaternion', 4]]) {
      const value = item[field]
      if (value !== undefined && (!Array.isArray(value) || value.length !== count || !value.every(value => typeof value === 'number' && Number.isFinite(value)))) throw new Error(`Original native pose: invalid ${field}`)
    }
    if (item.worldQuaternion?.every(value => value === 0)) throw new Error('Original native pose: zero override quaternion')
    if (['evidence', 'sourceTimeSeconds', 'landmarkIds'].some(key => Object.hasOwn(item, key))) {
      // Existing source override record, retained whole in the original update
      // and exact state key. Only the independently supplied source context can
      // bind its timestamp and CHECK landmark membership; CPU pose does not.
      if (typeof item.evidence !== 'string' || !item.evidence.trim()
        || typeof item.sourceTimeSeconds !== 'number' || !Number.isFinite(item.sourceTimeSeconds) || item.sourceTimeSeconds < 0
        || !Array.isArray(item.landmarkIds) || !item.landmarkIds.length
        || item.landmarkIds.some(id => typeof id !== 'string' || !id.trim()) || new Set(item.landmarkIds).size !== item.landmarkIds.length) throw new Error('Original native pose: incomplete/invalid source override evidence')
      if (item.worldQuaternion && Math.abs(Math.hypot(...item.worldQuaternion) - 1) > 0.002) throw new Error('Original native pose: source override quaternion is not an observed unit pose')
    }
  }
}

function observePublishedOriginalNativeLoad(THREE, GLTFLoader, BINDINGS, instanceIndex) {
  // Read-only external observation of admitted published code. Neither source,
  // scene physical laws, parser, native geometry nor spring shader is replaced.
  const parseAsync = GLTFLoader.prototype.parseAsync
  const clone = THREE.Object3D.prototype.clone
  const originals = new WeakMap()
  const cloneSources = new WeakMap()
  let root = null
  let restored = false

  function rememberClone(source, target) {
    const original = originals.get(source) ?? cloneSources.get(source)
    if (original) cloneSources.set(target, original)
    if (source.children.length !== target.children.length) throw new Error('Original native observer: authentic clone tree correspondence changed')
    for (let i = 0; i < source.children.length; i++) rememberClone(source.children[i], target.children[i])
  }
  function restore() {
    if (restored) return
    restored = true
    GLTFLoader.prototype.parseAsync = parseAsync
    THREE.Object3D.prototype.clone = clone
  }
  GLTFLoader.prototype.parseAsync = async function (...args) {
    const gltf = await parseAsync.apply(this, args)
    if (root || !gltf.scene || !gltf.parser?.associations) throw new Error('Original native observer: exactly one authentic parsed scene required')
    root = gltf.scene
    root.updateMatrixWorld(true)
    function visit(node, parentPath, inheritedNodeIndex) {
      const association = gltf.parser.associations.get(node)
      const nodeIndex = Number.isSafeInteger(association?.nodes) ? association.nodes : inheritedNodeIndex
      const originalName = typeof node.userData.name === 'string' ? node.userData.name : node.name
      const path = parentPath ? `${parentPath}/${originalName}` : originalName
      if (node !== root) {
        let binding = null, station = null
        // Execute the actual original binding table and original instanceIndex,
        // matching the admitted loader's last matching binding assignment.
        for (const candidate of BINDINGS) if (candidate.pattern.test(path)) {
          binding = candidate
          station = candidate.kind === 'indexed' ? instanceIndex(path, candidate.pattern) - 1 : null
        }
        originals.set(node, { node, path, binding, station, restMatrixWorldF64: Float64Array.from(node.matrixWorld.elements),
          association: { nodeIndex, meshIndex: association?.meshes ?? null, primitiveIndex: association?.primitives ?? null } })
      }
      for (const child of node.children) visit(child, node === root ? '' : path, nodeIndex)
    }
    visit(root, '', null)
    // Observe only clones made by the original loader AFTER authentic parse.
    // Geometry/material .clone methods are untouched.
    THREE.Object3D.prototype.clone = function (...cloneArgs) {
      const target = clone.apply(this, cloneArgs)
      rememberClone(this, target)
      return target
    }
    return gltf
  }

  function springUniforms(object, binding) {
    const hasCoordinates = object.geometry.hasAttribute('springCoordinate')
    const isSpring = binding && ['channel-spring', 'counter-spring'].includes(binding.motion)
    if (!hasCoordinates && !isSpring) return null
    if (!hasCoordinates || !isSpring) throw new Error('Original native observer: authentic spring attributes/binding disagree')
    const stock = binding.motion === 'counter-spring' ? 'counter' : 'channel'
    let handles = null
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (material.customProgramCacheKey() !== `native-stock-spring:${stock}`) throw new Error('Original native observer: original spring factory key unavailable')
      // Execute the ORIGINAL callback against the ORIGINAL locked Three shader
      // library as CPU metadata only. No renderer, compilation or GLSL execution.
      const shader = { uniforms: THREE.UniformsUtils.clone(THREE.ShaderLib.standard.uniforms),
        vertexShader: THREE.ShaderLib.standard.vertexShader, fragmentShader: THREE.ShaderLib.standard.fragmentShader }
      material.onBeforeCompile(shader, undefined)
      const length = shader.uniforms.springLength, rest = shader.uniforms.springRestLength
      if (!length || !rest || !Number.isFinite(rest.value) || rest.value <= 0 || !Number.isFinite(length.value) || length.value <= 0) throw new Error('Original native observer: genuine spring length handles unavailable')
      if (handles && (handles.length !== length || handles.rest !== rest)) throw new Error('Original native observer: material slots have differing original spring handles')
      handles = { length, rest }
    }
    if (!handles) throw new Error('Original native observer: original spring material unavailable')
    return { stock, restLengthM: handles.rest.value, length: handles.length }
  }

  return {
    restore,
    inventory(machine) {
      if (!root || !restored) throw new Error('Original native observer: completed original load required')
      const entries = [], observedPartPaths = [], seen = new Set()
      function visit(node, parentPath, inheritedBindingOwner) {
        const original = originals.get(node) ?? cloneSources.get(node)
        const originalName = typeof node.userData.name === 'string' ? node.userData.name : node.name
        let path = parentPath ? `${parentPath}/${originalName}` : originalName
        let bindingOwner = inheritedBindingOwner
        if (node !== root) {
          if (!original) throw new Error('Original native observer: a node lacks authentic parse/clone ancestry')
          if (node.userData.nativeInstancePath !== undefined) {
            if (typeof node.userData.nativeInstancePath !== 'string' || node.userData.nativeInstanceSource !== original.path || cloneSources.get(node) !== original) throw new Error('Original native observer: explicit original instance ancestry mismatch')
            path = node.userData.nativeInstancePath
          }
          if (seen.has(path)) throw new Error(`Original native observer: duplicate authentic path ${path}`)
          seen.add(path)
          observedPartPaths.push(path)
          if (original.binding) bindingOwner = { path, binding: original.binding, station: original.station }
          if (node instanceof THREE.Mesh) entries.push({ path, object: node, restMatrixWorldF64: original.restMatrixWorldF64,
            association: original.association, instanceOf: cloneSources.has(node) ? original.path : null,
            bindingOwnerPath: bindingOwner?.path ?? null, binding: bindingOwner?.binding ?? null, station: bindingOwner?.station ?? null,
            spring: springUniforms(node, bindingOwner?.binding ?? null) })
          else if (node instanceof THREE.Line || node instanceof THREE.Points) throw new Error('Original native observer: nonmesh drawable is not admitted CURRENT462')
        }
        for (const child of node.children) visit(child, node === root ? '' : path, bindingOwner)
      }
      visit(root, '', null)
      if (observedPartPaths.length !== machine.partPaths.length || observedPartPaths.some(path => !machine.partPaths.includes(path))
        || entries.length !== machine.nativeDrawablePartPaths.length || entries.some(entry => !machine.nativeDrawablePartPaths.includes(entry.path))) throw new Error('Original native observer: real original loader and external tree census disagree')
      return entries
    },
  }
}

/**
 * Execute ONLY an independently retained/admitted closure. No current source,
 * asset, renderer, fake geometry, or producer status is an oracle input.
 * This is geometry/physical-pose authority ONLY. Real GLTFLoader may report a
 * texture/blob/image decode failure in Node; its original warnings are never
 * suppressed or replaced with invented textures. A loaded Mesh material/map
 * is therefore NOT a texture, alpha, material, raster or first-surface oracle.
 *
 * inventory = { drawables, partPaths, mechanismData, closureSHA256, rawSHA256,
 * deliverySHA256 }; drawable entries expose real immutable geometry references,
 * canonicalIndices, original restMatrixF64, parser ancestry and explicit clones.
 * solve(input, overrides=[]) = { drawables, mechanismData }. Its F64 matrix and
 * scalar records are stable scratch: consumed synchronously, overwritten by the
 * next solve. Copy only needed 16-value matrices to retain a particular pose.
 * dispose() disposes the actual native scene and isolated evaluated module scope.
 */
export async function createOriginalNativePoseOracle({ closure } = {}) {
  const frozen = checkedClosure(closure)
  const cameraNearFar = await originalCameraNearFar(decoder.decode(closure.modules.find(module => module.id === frozen.manifest.entries.scene).source))
  if (canonicalJson(cameraNearFar) !== canonicalJson(frozen.manifest.cameraNearFar)) throw new Error('Original CPU camera convention: frozen source and admitted manifest disagree')
  const scope = frozenModuleScope(frozen.modules)
  let machine, scene, observation
  try {
    await withNativeNodeGlobals(frozen.deliveryGLBBytes, async () => {
      const sceneModule = await scope.execute(frozen.manifest.entries.scene)
      const THREE = await scope.execute(frozen.manifest.entries.three)
      const { GLTFLoader } = await scope.execute(frozen.manifest.entries.gltfLoader)
      const { BINDINGS, instanceIndex } = await scope.execute(frozen.manifest.entries.bindings)
      observation = observePublishedOriginalNativeLoad(THREE, GLTFLoader, BINDINGS, instanceIndex)
      scene = new THREE.Scene()
      try { machine = await sceneModule.loadMachine(scene, { url: MODEL_URL }) }
      finally { observation.restore() }
    })
    if (machine.availability !== 'available' || machine.provenance.identity !== 'matched' || machine.missing.length) throw new Error(`Original native CPU load failed: ${machine.loadError ?? machine.missing.join('; ')}`)
    let { compileInput } = await scope.execute(frozen.manifest.entries.sourceWitness)
    const { MECHANISM_DATA } = await scope.execute(frozen.manifest.entries.mechanics)
    if (MECHANISM_DATA.provenance.modelSha256 !== RAW_SHA256 || machine.provenance.observedSha256 !== DELIVERY_SHA256 || machine.provenance.observedByteLength !== DELIVERY_BYTE_LENGTH) throw new Error('Original native CPU reference has foreign model provenance')
    let entries = observation.inventory(machine)
    observation = null
    if (entries.length !== 462 || machine.partPaths.length !== 479 || machine.nativeDrawablePartPaths.length !== 462) throw new Error('Original native CPU inventory is not all CURRENT462/479 names')
    const paths = new Set()
    const indexCache = new Map()
    let springs = 0, springVertices = 0, instances = 0
    const inventoryDrawables = entries.map(entry => {
      if (paths.has(entry.path) || !entry.object?.isMesh || !entry.object.geometry) throw new Error('Original native CPU inventory: duplicate or nonmesh drawable')
      paths.add(entry.path)
      if (entry.restMatrixWorldF64?.length !== 16) throw new Error(`Original native CPU inventory: missing original rest matrix at ${entry.path}`)
      const restMatrixF64 = Float64Array.from(entry.restMatrixWorldF64)
      if (!restMatrixF64.every(Number.isFinite)) throw new Error(`Original native CPU inventory: nonfinite original rest matrix at ${entry.path}`)
      for (const field of ['nodeIndex', 'meshIndex', 'primitiveIndex']) if (!Number.isSafeInteger(entry.association?.[field]) || entry.association[field] < 0) throw new Error(`Original native CPU inventory: missing authentic ${field} at ${entry.path}`)
      if (entry.instanceOf !== null) instances++
      if (entry.spring) {
        springs++
        springVertices += entry.object.geometry.getAttribute('position').count
        if (!(entry.spring.restLengthM > 0) || !['channel', 'counter'].includes(entry.spring.stock)) throw new Error('Original native CPU inventory: invalid original spring role')
      }
      let indices = indexCache.get(entry.object.geometry)
      if (!indices) { indices = canonicalIndices(entry.object.geometry, entry.path); indexCache.set(entry.object.geometry, indices) }
      return Object.freeze({ path: entry.path, object: entry.object, geometry: entry.object.geometry, attributes: entry.object.geometry.attributes,
        canonicalIndices: indices, restMatrixF64,
        association: Object.freeze({ ...entry.association }), instanceOf: entry.instanceOf,
        bindingOwnerPath: entry.bindingOwnerPath, binding: entry.binding, station: entry.station,
        spring: entry.spring ? Object.freeze({ stock: entry.spring.stock, restLengthM: entry.spring.restLengthM }) : null })
    })
    if (instances !== 2 || springs !== 21 || springVertices !== 3293594) throw new Error('Original native CPU inventory: incomplete two-instance/21-spring ancestry')
    for (const entry of inventoryDrawables) if (entry.instanceOf !== null && !paths.has(entry.instanceOf)) throw new Error(`Original native CPU inventory: unresolved clone source ${entry.instanceOf}`)
    freezeRecords(MECHANISM_DATA)
    const inventory = Object.freeze({ drawables: Object.freeze(inventoryDrawables), partPaths: Object.freeze([...machine.partPaths]), mechanismData: MECHANISM_DATA,
      cameraNearFar,
      limitations: Object.freeze(['Geometry and physical pose only; CPU GLTF texture/blob decode warnings remain observable and do not admit texture, alpha, material, raster or first-surface state.']),
      closureSHA256: closure.manifestSHA256, rawSHA256: RAW_SHA256, deliverySHA256: DELIVERY_SHA256 })
    const poseDrawables = entries.map(entry => ({ path: entry.path, matrixWorld: new Float64Array(16), effectiveVisibility: false,
      bindingOwnerPath: entry.bindingOwnerPath, binding: entry.binding, station: entry.station, springLengthM: null }))
    const result = { drawables: poseDrawables, mechanismData: MECHANISM_DATA }
    const partPaths = new Set(machine.partPaths)
    let disposed = false
    let lastPoseStateKey = null
    return {
      inventory,
      solve(serializedInput, overrides = []) {
        if (disposed) throw new Error('Original native pose oracle is disposed')
        const input = compileInput(serializedInput, 'Independently expected original native input')
        validateOverrides(overrides, partPaths)
        const stateKey = canonicalJson([serializedInput, overrides])
        if (stateKey === lastPoseStateKey) return result
        lastPoseStateKey = null
        machine.update(input, overrides)
        scene.updateMatrixWorld(true)
        for (let i = 0; i < entries.length; i++) {
          const entry = entries[i], target = poseDrawables[i]
          target.matrixWorld.set(entry.object.matrixWorld.elements)
          if (!target.matrixWorld.every(Number.isFinite)) throw new Error(`Original native pose: nonfinite matrix at ${entry.path}`)
          let visible = true
          for (let node = entry.object; node; node = node.parent) if (!node.visible) { visible = false; break }
          target.effectiveVisibility = visible
          target.springLengthM = entry.spring?.length.value ?? null
          if (target.springLengthM !== null && (!Number.isFinite(target.springLengthM) || target.springLengthM <= 0)) throw new Error(`Original native pose: invalid spring length at ${entry.path}`)
        }
        lastPoseStateKey = stateKey
        return result
      },
      dispose() {
        if (disposed) return
        disposed = true
        machine.dispose()
        scene.clear()
        poseDrawables.splice(0)
        entries = null
        compileInput = null
        machine = null
        scene = null
        lastPoseStateKey = null
        indexCache.clear()
        partPaths.clear()
        scope.dispose()
      },
    }
  } catch (error) {
    observation?.restore()
    machine?.dispose()
    scene?.clear()
    scope.dispose()
    throw error
  } finally {
    // Only the actual loader retains parsed native geometry. Release this
    // session's raw binary provider immediately, not at the end of all views.
    frozen.deliveryGLBBytes = null
  }
}
