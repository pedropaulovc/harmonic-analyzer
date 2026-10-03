import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { copyFile, cp, mkdir, mkdtemp, readFile, rm, stat, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Matrix4 } from 'three'
import { authorizeSourceImport, importModel, parseImportOptions, publishPreparedModel } from './fetch-model.mjs'
import { validateDecodedEquivalence } from './optimize-model.mjs'
import { assertRuntimeMathCompatibility } from './native-math-compatibility.mjs'

const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const commit = 'a'.repeat(40)

function rawFixture(native = null) {
  const geometry = Buffer.alloc(36)
  ;[0, 0, 0, 1, 0, 0, 0, 1, 0].forEach((value, index) => geometry.writeFloatLE(value, index * 4))
  const document = {
    asset: { version: '2.0', generator: 'Synthetic importer behavior fixture, not native CAD evidence' },
    scene: 0, scenes: [{ nodes: [0] }],
    nodes: [{ name: 'ha-harmonic-analyzer', children: [1, 2] }, { name: 'part-1', mesh: 0 }, { name: 'part-2', mesh: 0, translation: [2, 0, 0] }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 }, mode: 4 }] }],
    buffers: [{ byteLength: geometry.length }],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: geometry.length, target: 34962 }],
    accessors: [{ bufferView: 0, byteOffset: 0, componentType: 5126, count: 3, type: 'VEC3', min: [0, 0, 0], max: [1, 1, 0] }],
  }
  if (native) {
    const matrices = native.renderFrames.worldMatrices
    const nodes = [], indexes = new Map(), identity = new Matrix4().toArray()
    function add(path) {
      if (indexes.has(path)) return indexes.get(path)
      const separator = path.lastIndexOf('/')
      const parentPath = separator < 0 ? null : path.slice(0, separator)
      const parent = parentPath ? add(parentPath) : null
      const world = new Matrix4().fromArray(matrices[path] ?? identity)
      const parentWorld = new Matrix4().fromArray(matrices[parentPath] ?? identity)
      const index = nodes.length
      nodes.push({ name: path.slice(separator + 1), matrix: parentWorld.invert().multiply(world).toArray(), children: [] })
      indexes.set(path, index)
      if (parent !== null) nodes[parent].children.push(index)
      return index
    }
    for (const path of Object.keys(matrices)) add(path)
    // A real geometry replacement with unchanged mechanism datums. It uses
    // the released native node frames, not a canned exporter response.
    nodes[add('ha-harmonic-analyzer/fr-frame/replacement-panel-1')].mesh = 0
    document.nodes = nodes
    document.scenes[0].nodes = [indexes.get('ha-harmonic-analyzer')]
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
const repository = fileURLToPath(new URL('../../', import.meta.url))
const web = fileURLToPath(new URL('../', import.meta.url))
const mechanismData = text => JSON.parse(text.split('export const MECHANISM_DATA = ')[1].split(' as const')[0])

async function releaseFixture(t, editSource = null) {
  const f = await fixture(t)
  f.nativeBytes = await readFile(join(web, 'src/mechanics-data.ts'), 'utf8')
  f.native = mechanismData(f.nativeBytes)
  await writeFile(f.nativePath, f.nativeBytes)
  // The candidate release uses the canonical source tree, not the historical
  // geometry-provenance commit whose module identities predate this cutover.
  for (const directory of ['scripts', 'config']) await cp(join(repository, 'cad', directory), join(f.directory, 'cad', directory), { recursive: true, filter: path => !path.split(/[\\/]/).includes('__pycache__') })
  await mkdir(join(f.webRoot, 'scripts'))
  for (const name of ['export-mechanics.py', 'requirements-model-export.txt']) await copyFile(join(web, 'scripts', name), join(f.webRoot, 'scripts', name))
  for (const name of ['kinematics.ts', 'magnifier.ts', 'scene.ts']) await copyFile(join(web, 'src', name), join(f.webRoot, 'src', name))
  if (editSource) {
    const path = join(f.directory, editSource.path)
    const before = await readFile(path, 'utf8')
    const after = before.replace(editSource.from, editSource.to)
    assert.notEqual(after, before, 'release mutation must change the native source parameter')
    await writeFile(path, after)
  } else {
    const path = join(f.directory, 'cad/config/machine/gear_train.yaml')
    await writeFile(path, `${await readFile(path, 'utf8')}\n# Geometry-only panel replacement release.\n`)
  }
  execFileSync('git', ['init', '--quiet'], { cwd: f.directory })
  execFileSync('git', ['add', 'cad'], { cwd: f.directory })
  execFileSync('git', ['-c', 'user.name=Importer fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--quiet', '-m', 'Approved CAD release fixture'], { cwd: f.directory })
  f.sourceCommit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: f.directory, encoding: 'utf8' }).trim()
  f.bytes = rawFixture(f.native)
  f.modelSha256 = digest(f.bytes)
  f.sourceSha256 = f.modelSha256
  await writeFile(f.sourcePath, f.bytes)
  f.asset = join(f.webRoot, 'public/models/ha-harmonic-analyzer.glb')
  f.descriptor = join(f.webRoot, 'content/model-representation.json')
  await writeFile(f.asset, 'previous optimized artifact')
  await writeFile(f.descriptor, 'previous approved descriptor')
  return f
}

test('same-source import publishes exact decoded bytes and descriptor, caches raw, and never regenerates native seals', async t => {
  const f = await fixture(t)
  const imported = await importModel(f)
  const optimized = await readFile(join(f.webRoot, 'public/models/ha-harmonic-analyzer.glb'))
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
  const asset = join(f.webRoot, 'public/models/ha-harmonic-analyzer.glb'), descriptor = join(f.webRoot, 'content/model-representation.json')
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
  const destination = join(f.webRoot, 'public/models/ha-harmonic-analyzer.glb')
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
  const destination = join(f.webRoot, 'public/models/ha-harmonic-analyzer.glb')
  await writeFile(destination, 'previous optimized artifact')
  await assert.rejects(importModel(f), /Immutable raw source cache is corrupt/)
  assert.equal(await readFile(cachePath, 'utf8'), 'corrupted raw cache')
  assert.equal(await readFile(destination, 'utf8'), 'previous optimized artifact')
  assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
})

test('compatible future geometry publishes with source/config provenance changes and unchanged runtime mathematics', async t => {
  const f = await releaseFixture(t)
  const imported = await importModel(f)
  const optimized = await readFile(f.asset)
  const descriptor = JSON.parse(await readFile(f.descriptor, 'utf8'))
  const native = mechanismData(await readFile(f.nativePath, 'utf8'))
  assert.equal(imported.nativeMetadataRegenerated, true)
  assert.equal(native.provenance.sourceCommit, f.sourceCommit)
  assert.equal(native.provenance.modelSha256, f.sourceSha256)
  assert.equal(descriptor.representation.sha256, digest(optimized))
  assert.equal(descriptor.source.sha256, native.provenance.modelSha256)
  assert.equal((await validateDecodedEquivalence(f.bytes, optimized)).passed, true)
  const previousSource = f.native.provenance.sourceFiles.find(file => file.path === 'cad/config/machine/gear_train.yaml')
  const newSource = native.provenance.sourceFiles.find(file => file.path === previousSource.path)
  assert.notEqual(newSource.sha256, previousSource.sha256)
  // Exercise the uncertain fixed-math boundaries on actual exported metadata,
  // while allowing wheel dimensions/rest-frame geometry that the solver reads.
  const compatible = structuredClone(native)
  compatible.magnifier.hubPitchRadiusMm += 0.1
  compatible.magnifier.wheelCentreMm[0] += 1
  compatible.channel.stationZ0Mm += 1
  compatible.magnifier.clampRadiusBandMm = compatible.magnifier.clampRadiusBandMm.map(radius => radius * 1.1)
  compatible.summing.anchorArmMm *= 1.1
  compatible.spring.rateNPerMm *= 1.1
  // These remain staged-data inputs, not fixed runtime stock/catalog values.
  compatible.counter.coilTurns += 1
  compatible.counter.coilOutsideDiameterMm += 0.2
  compatible.counter.loopMeanRadiusMm += 0.1
  compatible.counter.deformation.coilMeanRadiusMm += 0.1
  compatible.counter.maximumLengthMm += 1
  const counterMaximum = compatible.counter.deformation.profiles[1]
  counterMaximum.lengthMm += 1
  counterMaximum.coilEndsMm[0] -= 0.5
  counterMaximum.coilEndsMm[1] += 0.5
  compatible.counter.freeLengthMm += 1
  const counterFree = compatible.counter.deformation.profiles[0]
  counterFree.lengthMm += 1
  counterFree.coilEndsMm[0] -= 0.5
  counterFree.coilEndsMm[1] += 0.5
  await assertRuntimeMathCompatibility(compatible, f.native, f.webRoot)
  for (const [parameter, change] of [
    ['driveTrain.crankRatio', data => { data.driveTrain.crankRatio[0] += 1 }],
    ['driveTrain.crankTeeth', data => { data.driveTrain.crankTeeth[1] += 1 }],
    ['harmonicNumbers', data => { [data.harmonicNumbers[0], data.harmonicNumbers[1]] = [data.harmonicNumbers[1], data.harmonicNumbers[0]] }],
    ['coneTeeth/cylinderTeeth', data => { data.driveTrain.channelMeshes[0].coneTeeth -= 6 }],
    ['channelMeshes', data => { data.driveTrain.channelMeshes[1].ratio[0] += 6 }],
    ['clampRadiusBandMm', data => { data.magnifier.clampRadiusBandMm[2] += 1 }],
    ['clampRadiusBandMm', data => { data.summing.anchorArmMm += 1 }],
    ['penRestMm', data => { data.magnifier.penRestMm[0] += 1 }],
    ['reducerRatio', data => { data.paperDrive.reducerRatio *= 2; data.paperDrive.feedPitchDiameterMm /= 2 }],
    ['fineTravelMmPerCrankRev', data => { data.paperDrive.fineTravelMmPerCrankRev *= 1.01 }],
    ['netTravelSense', data => { data.paperDrive.netTravelSense *= -1 }],
    ['counter.deformation.coilEndInsetMm', data => { data.counter.deformation.coilEndInsetMm += 0.1 }],
    ['counter.deformation.coilEndCorrectionMm', data => { data.counter.deformation.coilEndCorrectionMm += 0.1 }],
    ['counter.deformation.coilMeanRadiusMm', data => { data.counter.deformation.coilMeanRadiusMm += 0.1 }],
    ['counter.deformation.wireRadiusMm', data => { data.counter.deformation.wireRadiusMm += 0.1 }],
    ['counter.deformation.coilAxis', data => { data.counter.deformation.coilAxis[1] = 1 }],
    ['counter.deformation.profiles[1].coilEndsMm', data => { data.counter.deformation.profiles[1].coilEndsMm[1] += 0.1 }],
    ['spring.deformation.transitionHandlePolarRad', data => { data.spring.deformation.transitionHandlePolarRad += 1e-6 }],
    ['spring.deformation.transitionTangentMm', data => { data.spring.deformation.transitionTangentMm += 0.1 }],
    ['spring.deformation.profiles[0].hookEyeCentresMm', data => { data.spring.deformation.profiles[0].hookEyeCentresMm[0][0] += 0.1 }],
    ['spring.deformation.profiles[1].transitionControlPointsMm', data => { data.spring.deformation.profiles[1].transitionControlPointsMm[2][0] += 0.1 }],
  ]) {
    const unsupported = structuredClone(native)
    change(unsupported)
    await assert.rejects(assertRuntimeMathCompatibility(unsupported, f.native, f.webRoot), error => {
      assert.match(error.message, /Unsupported native runtime parameter/)
      assert.ok(error.message.includes(parameter), error.message)
      return true
    })
  }
})

test('staged fixed feed and spring-shape changes are refused before any live model, descriptor or native publication', async t => {
  for (const [name, path, from, to, parameter] of [
    ['reducer teeth', 'cad/scripts/transgear_pinion_spec.py', 'TEETH = 12', 'TEETH = 13', 'paperDrive.reducerRatio'],
    ['rack pitch', 'cad/scripts/pd_transgear_feed_pinion_spec.py', 'DIAMETRAL_PITCH = 30.0', 'DIAMETRAL_PITCH = 32.0', 'paperDrive.feedPitchDiameterMm'],
    ['signed feed', 'cad/scripts/build_kinematic_probe.py', 'FEED_SIGN = +1.0', 'FEED_SIGN = -1.0', 'paperDrive.rackFeedSense'],
    ['counter coil inset with unchanged origin and eye seats', 'cad/scripts/vn_counter_spring_stock_geom.py', '_COIL_END_INSET_MM = 10.2997', '_COIL_END_INSET_MM = 10.3997', 'counter.deformation.coilEndInsetMm'],
    ['counter coil axial correction', 'cad/scripts/vn_counter_spring_stock_geom.py', 'return -coil_start_x_mm(length_mm) - WIRE_RADIUS_MM', 'return -coil_start_x_mm(length_mm) - 2.0 * WIRE_RADIUS_MM', 'counter.deformation.coilEndCorrectionMm'],
    ['channel transition polar', 'cad/scripts/diagnostics/diag_build_9432K31.py', 'VENDOR_HANDLE_POLAR_RAD = -0.00014851266501942706', 'VENDOR_HANDLE_POLAR_RAD = -0.00024851266501942706', 'spring.deformation.transitionHandlePolarRad'],
    ['channel transition handle', 'cad/scripts/vn_channel_spring_stock_geom.py', 'TRANSITION_TANGENT_MM = COIL_OD_MM * 3.0 / 4.0', 'TRANSITION_TANGENT_MM = COIL_OD_MM * 3.1 / 4.0', 'spring.deformation.transitionTangentMm'],
    ['channel coil length law with unchanged hook seats', 'cad/scripts/vn_channel_spring_stock_geom.py', 'return check_length_mm(length_mm) - 2.0 * COIL_ID_MM', 'return check_length_mm(length_mm) - 2.1 * COIL_ID_MM', 'spring.deformation.coilEndInsetMm'],
    ['channel transition hook anchor', 'cad/scripts/diagnostics/diag_build_9432K31.py', '(-22.225, 2.844799999999999, 0.0)', '(-22.325, 2.844799999999999, 0.0)', 'spring.deformation.profiles[0].transitionControlPointsMm'],
  ]) await t.test(name, async child => {
    const f = await releaseFixture(child, { path, from, to })
    await assert.rejects(importModel(f), error => {
      assert.match(error.message, /Unsupported native runtime parameter/)
      assert.ok(error.message.includes(parameter), error.message)
      assert.match(error.message, /No live outputs replaced/)
      return true
    })
    assert.equal(await readFile(f.asset, 'utf8'), 'previous optimized artifact')
    assert.equal(await readFile(f.descriptor, 'utf8'), 'previous approved descriptor')
    assert.equal(await readFile(f.nativePath, 'utf8'), f.nativeBytes)
    assert.deepEqual(await readFile(f.sourcePath), f.bytes)
  })
})
