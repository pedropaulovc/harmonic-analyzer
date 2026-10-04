import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { freezeOriginalNativeCPUClosure, readOriginalNativeCPUClosure, createOriginalNativePoseOracle } from './native-original-cpu.mjs'

// Parent-run only. These controls use the admitted actual current assets and
// source input, not a substitute scene/geometry/decoder. No GPU is created.
let closure, oracle, input
before(async () => {
  const webRoot = process.env.HARMONIC_ORIGINAL_NATIVE_CPU_WEB_ROOT
  closure = await freezeOriginalNativeCPUClosure({ webRoot,
    rawGLBPath: process.env.HARMONIC_ORIGINAL_NATIVE_RAW_GLB_PATH,
    deliveryGLBPath: process.env.HARMONIC_ORIGINAL_NATIVE_DELIVERY_GLB_PATH })
  const track = JSON.parse(await readFile(join(webRoot, 'content/v39/8KmVDxkia_w.source-track.json'), 'utf8'))
  input = track.frames.flatMap(frame => frame.views ?? []).find(view => view.input)?.input
  assert.ok(input, 'Actual original source track requires a fully authored input')
  oracle = await createOriginalNativePoseOracle({ closure })
})
after(() => oracle?.dispose())

function copyPose(result) {
  return result.drawables.map(row => ({ path: row.path, matrixWorld: Array.from(row.matrixWorld), effectiveVisibility: row.effectiveVisibility, springLengthM: row.springLengthM }))
}
function sourceInput(gearing) { return { ...input, gearing } }

test('simultaneous child-first absolute overrides do not inherit a later parent translation', () => {
  const child = oracle.inventory.drawables.find(row => row.binding?.motion === 'cylinder')
  const parent = child.path.slice(0, child.path.lastIndexOf('/'))
  assert.ok(oracle.inventory.partPaths.includes(parent), 'Use the genuine authored parent node')
  const expected = [0.123, 0.456, -0.078]
  const result = oracle.solve(input, [
    { partPath: child.path, worldPositionMetres: expected, visibility: 'hidden' },
    { partPath: parent, worldPositionMetres: [-0.2, 0.3, 0.4] },
  ])
  const row = result.drawables.find(row => row.path === child.path)
  expected.forEach((value, axis) => assert.ok(Math.abs(row.matrixWorld[12 + axis] - value) < 1e-12, `Absolute child world axis ${axis}`))
  assert.equal(row.effectiveVisibility, false)
  const other = result.drawables.find(row => row.path.startsWith(`${parent}/`) && row.path !== child.path)
  assert.equal(other.effectiveVisibility, true, 'Hidden child must not hide a sibling')
})

test('a hidden original ancestor hides every descendant, then the next source solve resets it', () => {
  const parent = 'harmonic-analyzer/channel'
  const baseline = copyPose(oracle.solve(input))
  const hidden = oracle.solve(input, [{ partPath: parent, visibility: 'hidden' }])
  for (const row of hidden.drawables) if (row.path.startsWith(`${parent}/`)) assert.equal(row.effectiveVisibility, false, row.path)
  assert.deepEqual(copyPose(oracle.solve(input)), baseline, 'Source update must reset prior override state, including all world transforms and spring lengths')
})

test('medium-medium gearing uses exactly the two real spare instances and resets without stale visibility', () => {
  const instances = oracle.inventory.drawables.filter(row => row.instanceOf !== null)
  assert.deepEqual(instances.map(row => row.path).sort(), [
    'harmonic-analyzer/paper-drive/transgear-removable-3@crank',
    'harmonic-analyzer/paper-drive/transgear-removable-3@upper',
  ])
  const ordinary = copyPose(oracle.solve(sourceInput('small-large')))
  const medium = oracle.solve(sourceInput('medium-medium'))
  for (const instance of instances) {
    assert.equal(medium.drawables.find(row => row.path === instance.path).effectiveVisibility, true)
    const source = oracle.inventory.drawables.find(row => row.path === instance.instanceOf)
    assert.equal(instance.geometry, source.geometry, 'Instances share the authentic source geometry')
    assert.deepEqual(instance.association, source.association, 'Clone ancestry is the parser association, not coincident positions')
    assert.deepEqual(instance.restMatrixF64, source.restMatrixF64, 'Both spare instances inherit the original raw-source rest frame, never their current driven placement')
  }
  for (const suffix of ['1', '2', '3']) assert.equal(medium.drawables.find(row => row.path === `harmonic-analyzer/paper-drive/transgear-removable-${suffix}`).effectiveVisibility, false)
  assert.deepEqual(copyPose(oracle.solve(sourceInput('small-large'))), ordinary)
})

test('full source fields and genuine override paths are required, not interactive defaults or silent missing parts', () => {
  const bad = structuredClone(input)
  delete bad.setup.driveCrankOffsetTurns
  assert.throws(() => oracle.solve(bad), /missing or unknown fields/)
  assert.throws(() => oracle.solve(input, [{ partPath: 'invented-native-part', visibility: 'hidden' }]), /unknown\/duplicate override/)
  const path = oracle.inventory.drawables[0].path
  assert.throws(() => oracle.solve(input, [{ partPath: path }, { partPath: path }]), /unknown\/duplicate override/)
  assert.throws(() => oracle.solve(input, [{ partPath: path, worldQuaternion: [0, 0, 0, 0] }]), /zero override quaternion/)
})

test('existing source override metadata is retained without changing physical pose; partial evidence is refused', () => {
  const path = oracle.inventory.drawables.find(row => row.binding?.motion === 'cylinder').path
  // Deliberately structural CPU evidence only, not an actual-exposure/CHECK
  // source qualification. verify-reference must still bind those authorities.
  const override = { partPath: path, worldPositionMetres: [0.123, 0.456, -0.078],
    evidence: 'CPU metadata compatibility control, not measured source proof', sourceTimeSeconds: 0, landmarkIds: ['diagnostic-check'] }
  const pose = oracle.solve(input, [override]).drawables.find(row => row.path === path)
  override.worldPositionMetres.forEach((value, axis) => assert.ok(Math.abs(pose.matrixWorld[12 + axis] - value) < 1e-12))
  const partial = { ...override }
  delete partial.landmarkIds
  assert.throws(() => oracle.solve(input, [partial]), /source override evidence/)
  assert.throws(() => oracle.solve(input, [{ ...override, sourceTimeSeconds: NaN }]), /source override evidence/)
  assert.throws(() => oracle.solve(input, [{ ...override, landmarkIds: ['same', 'same'] }]), /source override evidence/)
  assert.throws(() => oracle.solve(input, [{ ...override, worldQuaternion: [2, 0, 0, 0] }]), /observed unit pose/)
})

test('a changed frozen executable, original source, raw asset or delivery byte is refused before execution', async () => {
  const module = closure.modules.find(row => row.id === closure.manifest.entries.scene)
  for (const [label, bytes] of [['executable', module.transformed], ['source', module.source], ['lock', closure.packageLockBytes], ['raw', closure.rawGLBBytes], ['delivery', closure.deliveryGLBBytes]]) {
    const offset = Math.min(32, bytes.length - 1), original = bytes[offset]
    try {
      bytes[offset] ^= 1
      await assert.rejects(createOriginalNativePoseOracle({ closure }), /frozen byte identity mismatch/, label)
    } finally { bytes[offset] = original }
  }
})

test('changed manifest edges or absent module bytes cannot silently resolve to current local code', async () => {
  const manifest = structuredClone(closure.manifest)
  manifest.entries.scene = manifest.entries.mechanics
  await assert.rejects(createOriginalNativePoseOracle({ closure: { ...closure, manifest } }), /pinned manifest SHA256 required\/mismatched/)
  await assert.rejects(createOriginalNativePoseOracle({ closure: { ...closure, modules: closure.modules.filter(row => row.id !== closure.manifest.entries.mechanics) } }), /incomplete module bytes/)
})

test('an admitted live session keeps its original code when an external byte container changes', () => {
  const ordinary = copyPose(oracle.solve(sourceInput('small-large')))
  const medium = copyPose(oracle.solve(sourceInput('medium-medium')))
  const bytes = closure.modules.find(row => row.id === closure.manifest.entries.scene).transformed
  const original = bytes[32]
  try {
    bytes[32] ^= 1
    assert.deepEqual(copyPose(oracle.solve(sourceInput('small-large'))), ordinary)
    assert.deepEqual(copyPose(oracle.solve(sourceInput('medium-medium'))), medium)
  } finally { bytes[32] = original }
})

test('archive-carried SHA cannot authorize replay and a wrong independent pin fails before asset reads', async t => {
  const archive = await mkdtemp(join(tmpdir(), 'original-native-cpu-archive-'))
  t.after(() => rm(archive, { recursive: true, force: true }))
  await writeFile(join(archive, 'manifest.json'), JSON.stringify(closure.manifest))
  await writeFile(join(archive, 'manifest.sha256'), `${closure.manifestSHA256}\n`)
  await assert.rejects(readOriginalNativeCPUClosure({ archive }), /independently pinned manifest SHA256 required/)
  const wrongPin = `${closure.manifestSHA256[0] === '0' ? '1' : '0'}${closure.manifestSHA256.slice(1)}`
  // No model/module files exist: a missing-file result would expose reading
  // unauthenticated assets before the independently supplied manifest was bound.
  await assert.rejects(readOriginalNativeCPUClosure({ archive, manifestSHA256: wrongPin }), /independently pinned manifest SHA256 mismatch/)
})
