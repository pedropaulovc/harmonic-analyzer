#!/usr/bin/env node
/**
 * Import immutable raw CAD bytes, project authoritative native identities, prove
 * exact canonical decoded equivalence, and publish a deduplicated Meshopt GLB.
 * Native source provenance always identifies the original raw release bytes.
 *
 * npm run fetch-model -- /path/to/raw.glb
 * npm run fetch-model -- /path/to/new.glb --source-commit <40hex> --source-sha256 <approved64hex>
 */

import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { copyFile, link, mkdir, mkdtemp, readFile, readdir, realpath, rename, rm, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { assertNativeSourceAssociation, validateModelRepresentation, REPRESENTATION_KIND, REPRESENTATION_PATH, PIPELINE_VERSION, PIPELINE_STEPS } from '../model-representation.mjs'
import { projectNativeIdentity, validateNativeIdentityProjection } from './native-identity-map.mjs'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SHA256 = /^[0-9a-f]{64}$/
const COMMIT = /^[0-9a-f]{40}$/
const RELEASE_PAIRS = JSON.parse(await readFile(new URL('./released-models.json', import.meta.url), 'utf8'))
if (!Array.isArray(RELEASE_PAIRS) || RELEASE_PAIRS.length === 0 ||
    RELEASE_PAIRS.some(release => !release || Object.keys(release).sort().join(',') !== 'modelSha256,sourceCommit' ||
      typeof release.sourceCommit !== 'string' || !COMMIT.test(release.sourceCommit) ||
      typeof release.modelSha256 !== 'string' || !SHA256.test(release.modelSha256)) ||
    new Set(RELEASE_PAIRS.map(release => release.sourceCommit)).size !== RELEASE_PAIRS.length ||
    new Set(RELEASE_PAIRS.map(release => release.modelSha256)).size !== RELEASE_PAIRS.length) {
  throw new Error('Invalid released-models.json; expected unique exact commit/raw SHA256 pairs')
}
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const HELP = `Usage: npm run fetch-model -- [raw.glb] [--source-commit <40hex> --source-sha256 <approved64hex>]
No path: select ha-harmonic-analyzer.glb from cad/out/gltf.
The current native source stays SHA-pinned. A different CAD release requires both
explicit release commit and approved raw GLB SHA256; local bytes alone cannot
establish their association. The exact CAD revision must be available locally.
Only optimized bytes are published. Raw input is retained read-only by convention
in .vite/model-source/<raw-sha256>.glb, never in public/. Old source calibration
is not requalified by importing a new release.`

export function parseImportOptions(args) {
  const options = { sourcePath: null, sourceCommit: null, sourceSha256: null }
  for (let index = 0; index < args.length; index++) {
    const arg = args[index]
    if (arg === '--help') return { help: true }
    if (arg === '--source-commit' || arg === '--source-sha256') {
      const value = args[++index]
      const key = arg === '--source-commit' ? 'sourceCommit' : 'sourceSha256'
      if (options[key] !== null || typeof value !== 'string' || !(key === 'sourceCommit' ? COMMIT : SHA256).test(value)) {
        throw new Error(`${arg} requires exactly ${key === 'sourceCommit' ? 40 : 64} lowercase hexadecimal characters (once)`)
      }
      options[key] = value
    } else if (arg.startsWith('-') || options.sourcePath !== null) {
      throw new Error(`Unexpected argument: ${arg}`)
    } else options.sourcePath = arg
  }
  return options
}

function nativeMetadataFromModule(text) {
  const match = /export const MECHANISM_DATA = ([\s\S]+?) as const\s*$/.exec(text)
  if (!match) throw new Error('Cannot read generated MECHANISM_DATA; run the native metadata exporter with an explicit release identity')
  const data = JSON.parse(match[1])
  const native = data.provenance
  if (!native || !COMMIT.test(native.sourceCommit) || !SHA256.test(native.modelSha256)) throw new Error('Native metadata has no valid pinned source identity')
  return data
}

export function nativeProvenanceFromModule(text) {
  return nativeMetadataFromModule(text).provenance
}

export function authorizeSourceImport(native, actualSha256, { sourceCommit = null, sourceSha256 = null } = {}) {
  if (sourceCommit !== null && !COMMIT.test(sourceCommit)) throw new Error('Invalid --source-commit; expected 40 lowercase hexadecimal characters')
  if (sourceSha256 !== null && !SHA256.test(sourceSha256)) throw new Error('Invalid --source-sha256; expected 64 lowercase hexadecimal characters')
  const commit = sourceCommit ?? native.sourceCommit
  const pinned = RELEASE_PAIRS.find(release => release.sourceCommit === commit)
  if (pinned && (actualSha256 !== pinned.modelSha256 || sourceSha256 !== null && sourceSha256 !== pinned.modelSha256)) {
    throw new Error(`Released native commit ${commit} remains pinned to raw SHA256 ${pinned.modelSha256}; --source-commit cannot authorize different bytes for that release`)
  }
  const releasedRaw = RELEASE_PAIRS.find(release => release.modelSha256 === actualSha256)
  if (releasedRaw && releasedRaw.sourceCommit !== commit) {
    throw new Error(`Raw model SHA256 ${actualSha256} requires its exact source commit ${releasedRaw.sourceCommit}; --source-commit cannot relabel released bytes`)
  }
  if (commit === native.sourceCommit) {
    if (actualSha256 !== native.modelSha256 || sourceSha256 !== null && sourceSha256 !== native.modelSha256) {
      throw new Error(`The current native commit ${native.sourceCommit} is pinned to raw SHA256 ${native.modelSha256}; this input is ${actualSha256}. For a different CAD release pass --source-commit <release40hex> --source-sha256 <approved-release64hex>`)
    }
  } else {
    if (!sourceCommit || !sourceSha256) throw new Error('A new CAD source requires both --source-commit <release40hex> and --source-sha256 <approved-release64hex>; a computed file hash alone is not release authority')
    if (actualSha256 !== sourceSha256) throw new Error(`Raw model SHA256 ${actualSha256} does not match approved release digest ${sourceSha256}; no model or native metadata replaced`)
  }
  return { sourceCommit: commit, modelSha256: actualSha256, regenerateMetadata: commit !== native.sourceCommit }
}

async function pickSource(webRoot, explicit) {
  if (explicit) return resolve(explicit)
  const sourceDirectory = resolve(webRoot, '../cad/out/gltf')
  let entries
  try { entries = await readdir(sourceDirectory) }
  catch (error) {
    if (error.code !== 'ENOENT') throw error
    throw new Error(`${sourceDirectory} not found. Run the CAD export on the SolidWorks seat, or download a release bundle with gh release download and pass the raw .glb explicitly.`)
  }
  const basename = 'ha-harmonic-analyzer.glb'
  if (!entries.includes(basename)) throw new Error(`No ${basename} in ${sourceDirectory}`)
  return join(sourceDirectory, basename)
}

async function cacheRawSource(webRoot, bytes, sha256) {
  const directory = resolve(webRoot, '.vite/model-source')
  const cache = join(directory, `${sha256}.glb`)
  await mkdir(directory, { recursive: true })
  const temporary = await mkdtemp(join(directory, '.import-'))
  try {
    const staged = join(temporary, 'raw.glb')
    await writeFile(staged, bytes, { mode: 0o444 })
    try { await link(staged, cache) }
    catch (error) {
      if (error.code !== 'EEXIST') throw error
      if (digest(await readFile(cache)) !== sha256) throw new Error(`Immutable raw source cache is corrupt: ${cache}; remove that corrupt cache entry and re-import the approved raw source`)
    }
    return cache
  } finally { await rm(temporary, { recursive: true, force: true }) }
}

// All computation/decoding/rest checks finish before touching live outputs.
// Individual renames are atomic; rollback restores the entire prior set on a
// publication error. A concurrent browser with an old bundle fails closed on
// byte mismatch until the newly compiled descriptor is deployed.
export async function publishPreparedModel(files, stagingDirectory) {
  const backups = []
  const published = []
  try {
    for (const [index, file] of files.entries()) {
      await mkdir(dirname(file.destination), { recursive: true })
      const backup = join(stagingDirectory, `previous-${index}`)
      try { await copyFile(file.destination, backup); backups.push({ ...file, backup }) }
      catch (error) {
        if (error.code !== 'ENOENT') throw error
        backups.push({ ...file, backup: null })
      }
    }
    for (const file of files) {
      await rename(file.staged, file.destination)
      published.push(file.destination)
    }
  } catch (error) {
    const rollbackErrors = []
    for (const file of backups.reverse()) {
      if (!published.includes(file.destination)) continue
      try {
        if (file.backup) await rename(file.backup, file.destination)
        else await rm(file.destination, { force: true })
      } catch (rollbackError) { rollbackErrors.push(rollbackError.message) }
    }
    if (rollbackErrors.length) throw new Error(`Publication failed: ${error.message}; rollback failed: ${rollbackErrors.join('; ')}. Recovery files retained at ${stagingDirectory}`, { cause: error })
    throw error
  }
}

export async function importModel({ webRoot = WEB, sourcePath = null, sourceCommit = null, sourceSha256 = null } = {}) {
  webRoot = resolve(webRoot)
  const source = await pickSource(webRoot, sourcePath)
  const modelDestination = resolve(webRoot, 'public', REPRESENTATION_PATH)
  let destinationPath
  try { destinationPath = await realpath(modelDestination) }
  catch (error) {
    if (error.code !== 'ENOENT') throw error
    destinationPath = modelDestination
  }
  if (await realpath(source) === destinationPath) throw new Error('The original raw input must be outside the public model destination so it is never overwritten; pass the CAD export or downloaded raw release GLB instead')
  const sourceBytes = await readFile(source)
  const sourceDigest = digest(sourceBytes)
  const nativePath = resolve(webRoot, 'src/mechanics-data.ts')
  const currentNative = nativeMetadataFromModule(await readFile(nativePath, 'utf8'))
  const native = currentNative.provenance
  const identity = authorizeSourceImport(native, sourceDigest, { sourceCommit, sourceSha256 })
  const rawCachePath = await cacheRawSource(webRoot, sourceBytes, sourceDigest)
  await mkdir(resolve(webRoot, '.vite'), { recursive: true })
  const stagingDirectory = await mkdtemp(resolve(webRoot, '.vite/model-import-'))
  let retainRecovery = false
  try {
    const { optimizeModel, validateDecodedEquivalence } = await import('./optimize-model.mjs')
    const projection = await projectNativeIdentity(sourceBytes)
    const projectionProof = await validateNativeIdentityProjection(sourceBytes, projection.canonicalBytes)
    if (!projectionProof.passed || JSON.stringify(projectionProof.identity) !== JSON.stringify(projection.identity)) {
      throw new Error('Native identity projection does not agree with independently checked raw/canonical bytes')
    }
    const { optimizedBytes, report } = await optimizeModel(projection.canonicalBytes)
    const optimizedDigest = digest(optimizedBytes)
    const equivalence = await validateDecodedEquivalence(projection.canonicalBytes, optimizedBytes)
    if (report.sourceSha256 !== projection.identity.canonicalSha256 || report.optimizedSha256 !== optimizedDigest
      || report.sourceBytes !== projection.canonicalBytes.byteLength || report.optimizedBytes !== optimizedBytes.byteLength
      || equivalence.passed !== true || equivalence.sourceSha256 !== projection.identity.canonicalSha256 || equivalence.optimizedSha256 !== optimizedDigest
      || equivalence.semanticDigest !== report.semanticDigest || equivalence.drawableInstances !== report.equivalence.drawableInstances
      || report.codec.name !== 'meshoptimizer' || report.codec.extension !== 'EXT_meshopt_compression') {
      throw new Error('Optimizer report does not agree with independently checked canonical/output bytes and decoded equivalence')
    }
    const canonicalPaths = new Set(projectionProof.paths.map(path => path.canonical))
    const regenerateMetadata = identity.regenerateMetadata
      || native.nativeIdentityMapSha256 !== projection.identity.mapSha256
      || native.canonicalModelSha256 !== projection.identity.canonicalSha256
      || Object.keys(currentNative.renderFrames?.worldMatrices ?? {}).some(path => !canonicalPaths.has(path))
    const representation = validateModelRepresentation({
      schemaVersion: 2, kind: REPRESENTATION_KIND,
      source: { sha256: sourceDigest, sourceCommit: identity.sourceCommit },
      identity: projectionProof.identity,
      representation: { path: REPRESENTATION_PATH, sha256: optimizedDigest, byteLength: optimizedBytes.byteLength, codec: report.codec.extension },
      pipeline: { version: PIPELINE_VERSION, steps: [...PIPELINE_STEPS], codecVersion: `${report.codec.name}@${report.codec.version}` },
      equivalence: { method: 'decoded-per-drawable-exact-after-native-identity-v2', semanticSha256: equivalence.semanticDigest, drawableCount: equivalence.drawableInstances },
    })
    const stagedModel = join(stagingDirectory, 'model.glb')
    const stagedDescriptor = join(stagingDirectory, 'model-representation.json')
    await writeFile(stagedModel, optimizedBytes)
    await writeFile(stagedDescriptor, `${JSON.stringify(representation, null, 2)}\n`)
    const stagedBytes = await readFile(stagedModel)
    if (digest(stagedBytes) !== optimizedDigest || stagedBytes.byteLength !== representation.representation.byteLength) throw new Error('Staged optimized model failed its byte integrity check')
    validateModelRepresentation(JSON.parse(await readFile(stagedDescriptor, 'utf8')))
    const files = [
      { staged: stagedModel, destination: resolve(webRoot, 'public', REPRESENTATION_PATH) },
      { staged: stagedDescriptor, destination: resolve(webRoot, 'content/model-representation.json') },
    ]
    if (regenerateMetadata) {
      const stagedNative = join(stagingDirectory, 'mechanics-data.ts')
      try {
        execFileSync('uv', ['run', '--isolated', '--no-project', '--python', '3.13', '--with-requirements', resolve(webRoot, 'scripts/requirements-model-export.txt'), 'python', resolve(webRoot, 'scripts/export-mechanics.py'), '--model', rawCachePath, '--source-commit', identity.sourceCommit, '--expected-model-sha256', sourceDigest, '--output', stagedNative], { cwd: resolve(webRoot, '..'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
      } catch (error) {
        throw new Error(`Native metadata export for ${identity.sourceCommit} failed; the exact CAD release must be available locally and pass twenty-channel/rest checks. No live outputs replaced.\n${error.stderr?.toString() ?? error.message}`, { cause: error })
      }
      const generatedNative = nativeMetadataFromModule(await readFile(stagedNative, 'utf8'))
      assertNativeSourceAssociation(representation, generatedNative.provenance)
      const { assertRuntimeMathCompatibility } = await import('./native-math-compatibility.mjs')
      await assertRuntimeMathCompatibility(generatedNative, currentNative, webRoot)
      files.push({ staged: stagedNative, destination: nativePath })
    } else assertNativeSourceAssociation(representation, native)
    try { await publishPreparedModel(files, stagingDirectory) }
    catch (error) {
      retainRecovery = error.message.includes('rollback failed')
      throw error
    }
    return { sourcePath: source, rawCachePath, rawByteLength: sourceBytes.byteLength, nativeMetadataRegenerated: regenerateMetadata, representation, report, projectionProof }
  } finally {
    if (!retainRecovery) await rm(stagingDirectory, { recursive: true, force: true })
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const options = parseImportOptions(process.argv.slice(2))
    if (options.help) console.log(HELP)
    else {
      const result = await importModel(options)
      console.log(`   OK  ${result.sourcePath} -> public/${REPRESENTATION_PATH} (${(result.report.optimizedBytes / 1024 / 1024).toFixed(1)} MB; raw ${(result.rawByteLength / 1024 / 1024).toFixed(1)} MB)`)
      console.log(`   Raw source: ${result.representation.source.sha256} @ ${result.representation.source.sourceCommit}`)
      console.log(`   Native identity: ${result.representation.identity.renamedNodes}/${result.representation.identity.nodeCount} nodes projected with ${result.representation.identity.mapSha256}; canonical ${result.representation.identity.canonicalSha256}`)
      console.log(`   Representation: ${result.representation.representation.sha256}; exact ${result.representation.equivalence.drawableCount}-drawable equivalence ${result.representation.equivalence.semanticSha256}`)
      console.log(`   Raw cache: ${result.rawCachePath}; native metadata ${result.nativeMetadataRegenerated ? 'regenerated with canonical provenance; existing source tracks remain unqualified for this release' : 'unchanged (same native release and canonical projection)'}`)
    }
  } catch (error) {
    console.error(`xx ${error.message}`)
    process.exitCode = 1
  }
}
