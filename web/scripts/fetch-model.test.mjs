import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { copyFile, mkdir, mkdtemp, readFile, rm, stat, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { authorizeSourceImport, importModel, parseImportOptions, publishPreparedModel } from './fetch-model.mjs'
import { validateDecodedEquivalence } from './optimize-model.mjs'

const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const commit = 'a'.repeat(40)

function rawFixture() {
  const geometry = Buffer.alloc(36)
  ;[0, 0, 0, 1, 0, 0, 0, 1, 0].forEach((value, index) => geometry.writeFloatLE(value, index * 4))
  const document = {
    asset: { version: '2.0', generator: 'Synthetic importer behavior fixture, not native CAD evidence' },
    scene: 0, scenes: [{ nodes: [0] }],
    nodes: [{ name: 'harmonic-analyzer', children: [1, 2] }, { name: 'part-1', mesh: 0 }, { name: 'part-2', mesh: 0, translation: [2, 0, 0] }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 }, mode: 4 }] }],
    buffers: [{ byteLength: geometry.length }],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: geometry.length, target: 34962 }],
    accessors: [{ bufferView: 0, byteOffset: 0, componentType: 5126, count: 3, type: 'VEC3', min: [0, 0, 0], max: [1, 1, 0] }],
  }
  const json = Buffer.from(JSON.stringify(document))
  const padded = Buffer.alloc((json.length + 3) & ~3, 0x20)
  json.copy(padded)
  const glb = Buffer.alloc(12 + 8 + padded.length + 8 + geometry.length)
  glb.writeUInt32LE(0x46546c67, 0); glb.writeUInt32LE(2, 4); glb.writeUInt32LE(glb.length, 8)
  glb.writeUInt32LE(padded.length, 12); glb.writeUInt32LE(0x4e4f534a, 16); padded.copy(glb, 20)
  const binary = 20 + padded.length
  glb.writeUInt32LE(geometry.length, binary); glb.writeUInt32LE(0x004e4942, binary + 4); geometry.copy(glb, binary + 8)
  return glb
}

async function fixture(t) {
  const directory = await mkdtemp(join(tmpdir(), 'harmonic-model-import-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const webRoot = join(directory, 'web')
  await mkdir(join(webRoot, 'src'), { recursive: true })
  await mkdir(join(webRoot, 'public/models'), { recursive: true })
  await mkdir(join(webRoot, 'content'), { recursive: true })
  const sourcePath = join(directory, 'original.glb'), bytes = rawFixture()
  await writeFile(sourcePath, bytes)
  const modelSha256 = digest(bytes)
  const nativePath = join(webRoot, 'src/mechanics-data.ts')
  const nativeBytes = `// Synthetic native identity fixture; no mechanics calibration.\nexport const MECHANISM_DATA = ${JSON.stringify({ provenance: { sourceCommit: commit, modelSha256 } })} as const\n`
  await writeFile(nativePath, nativeBytes)
  return { directory, webRoot, sourcePath, bytes, modelSha256, nativePath, nativeBytes }
}

test('same-source import publishes exact decoded bytes and descriptor, caches raw, and never regenerates native seals', async t => {
  const f = await fixture(t)
  const imported = await importModel(f)
  const optimized = await readFile(join(f.webRoot, 'public/models/harmonic-analyzer.glb'))
  const descriptor = JSON.parse(await readFile(join(f.webRoot, 'content/model-representation.json'), 'utf8'))
  assert.equal(imported.nativeMetadataRegenerated, false)
  assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
  assert.deepEqual(await readFile(f.sourcePath), f.bytes)
  assert.equal(imported.rawCachePath, join(f.webRoot, '.vite/model-source', `${f.modelSha256}.glb`))
  assert.deepEqual(await readFile(imported.rawCachePath), f.bytes)
  assert.equal(descriptor.source.sha256, f.modelSha256)
  assert.equal(descriptor.source.sourceCommit, commit)
  assert.equal(descriptor.representation.sha256, digest(optimized))
  assert.equal(descriptor.representation.byteLength, optimized.length)
  assert.notEqual(descriptor.representation.sha256, f.modelSha256)
  const equivalence = await validateDecodedEquivalence(f.bytes, optimized)
  assert.equal(equivalence.passed, true)
  assert.equal(descriptor.equivalence.semanticSha256, equivalence.semanticDigest)
  assert.equal(descriptor.equivalence.drawableCount, 2)
  // A second import reuses only the content-addressed raw input, without
  // rewriting generated metadata based on today's working CAD checkout.
  await importModel(f)
  assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
})

test('current commit remains digest-pinned even when both identity options are explicit', () => {
  const native = { sourceCommit: '1268c23d4a8fc741147c5e09d8d1e45247a71945', modelSha256: '2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d' }
  const wrong = 'f'.repeat(64)
  for (const options of [{}, { sourceCommit: native.sourceCommit }, { sourceCommit: native.sourceCommit, sourceSha256: wrong }]) {
    assert.throws(() => authorizeSourceImport(native, wrong, options), /pinned/)
  }
  // The historical release pairing is still fixed after another source becomes current.
  assert.throws(() => authorizeSourceImport({ sourceCommit: commit, modelSha256: wrong }, wrong, { sourceCommit: native.sourceCommit, sourceSha256: wrong }), /pinned/)
})

test('new release authority requires explicit commit and approved digest, not the computed hash alone', () => {
  const native = { sourceCommit: commit, modelSha256: '1'.repeat(64) }, rawSha256 = '2'.repeat(64)
  assert.throws(() => authorizeSourceImport(native, rawSha256), /--source-commit/)
  assert.throws(() => authorizeSourceImport(native, rawSha256, { sourceCommit: 'b'.repeat(40) }), /both --source-commit/)
  assert.throws(() => authorizeSourceImport(native, rawSha256, { sourceCommit: 'b'.repeat(40), sourceSha256: '3'.repeat(64) }), /approved release digest/)
  assert.equal(authorizeSourceImport(native, rawSha256, { sourceCommit: 'b'.repeat(40), sourceSha256: rawSha256 }).regenerateMetadata, true)
  for (const args of [['--source-commit', 'b'.repeat(39)], ['--source-sha256', '2'.repeat(63)], ['--source-commit', 'B'.repeat(40)], ['--unknown']]) assert.throws(() => parseImportOptions(args))
})

test('unavailable exact CAD archive preserves all previous live artifacts and native metadata', async t => {
  const f = await fixture(t)
  const asset = join(f.webRoot, 'public/models/harmonic-analyzer.glb'), descriptor = join(f.webRoot, 'content/model-representation.json')
  await writeFile(asset, 'previous optimized artifact')
  await writeFile(descriptor, 'previous approved descriptor')
  await mkdir(join(f.webRoot, 'scripts'))
  await copyFile(new URL('./export-mechanics.py', import.meta.url), join(f.webRoot, 'scripts/export-mechanics.py'))
  await copyFile(new URL('./requirements-model-export.txt', import.meta.url), join(f.webRoot, 'scripts/requirements-model-export.txt'))
  await assert.rejects(importModel({ ...f, sourceCommit: 'b'.repeat(40), sourceSha256: f.modelSha256 }), /Cannot archive CAD source commit/)
  assert.equal(await readFile(asset, 'utf8'), 'previous optimized artifact')
  assert.equal(await readFile(descriptor, 'utf8'), 'previous approved descriptor')
  assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
  assert.deepEqual(await readFile(f.sourcePath), f.bytes)
})

test('publication errors roll back both existing and initially absent destinations', async t => {
  const f = await fixture(t)
  const staged = join(f.directory, 'staged.glb'), destination = join(f.directory, 'live.glb')
  const other = join(f.directory, 'live.json')
  await writeFile(other, 'old descriptor')
  for (const existing of [true, false]) {
    await writeFile(staged, 'replacement')
    if (existing) await writeFile(destination, 'old model')
    else await rm(destination, { force: true })
    await assert.rejects(publishPreparedModel([
      { staged, destination },
      { staged: join(f.directory, 'missing-stage.json'), destination: other },
    ], f.directory), /ENOENT/)
    if (existing) assert.equal(await readFile(destination, 'utf8'), 'old model')
    else await assert.rejects(stat(destination), /ENOENT/)
    assert.equal(await readFile(other, 'utf8'), 'old descriptor')
  }
})

test('a raw input alias of the published destination is refused without overwriting original bytes', async t => {
  const f = await fixture(t)
  const destination = join(f.webRoot, 'public/models/harmonic-analyzer.glb')
  await writeFile(destination, f.bytes)
  const alias = join(f.directory, 'raw-alias.glb')
  await symlink(destination, alias)
  for (const sourcePath of [destination, alias]) {
    await assert.rejects(importModel({ webRoot: f.webRoot, sourcePath }), /original raw input must be outside/)
    assert.deepEqual(await readFile(destination), f.bytes)
    assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
  }
})

test('a corrupt immutable raw cache is rejected rather than silently repaired or published', async t => {
  const f = await fixture(t)
  const cacheDirectory = join(f.webRoot, '.vite/model-source')
  await mkdir(cacheDirectory, { recursive: true })
  const cachePath = join(cacheDirectory, `${f.modelSha256}.glb`)
  await writeFile(cachePath, 'corrupted raw cache')
  const destination = join(f.webRoot, 'public/models/harmonic-analyzer.glb')
  await writeFile(destination, 'previous optimized artifact')
  await assert.rejects(importModel(f), /Immutable raw source cache is corrupt/)
  assert.equal(await readFile(cachePath, 'utf8'), 'corrupted raw cache')
  assert.equal(await readFile(destination, 'utf8'), 'previous optimized artifact')
  assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
})
