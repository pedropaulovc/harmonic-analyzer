// Main alone runs this helper. A freeze is an explicit original-code admission,
// never an automatically refreshed expectation. Replay requires its independently
// recorded SHA, reads archived bytes only, and never imports current scene.ts.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { freezeOriginalNativeCPUClosure, readOriginalNativeCPUClosure, createOriginalNativePoseOracle } from './native-original-cpu.mjs'

const args = process.argv.slice(2)
const mode = args[0]
if (!['--freeze', '--replay'].includes(mode) || !args[1]
  || (mode === '--freeze' ? args.length !== 8 || args[2] !== '--web-root' || !args[3] || args[4] !== '--raw-glb' || !args[5] || args[6] !== '--delivery-glb' || !args[7]
    : args.length !== 6 || args[2] !== '--closure-sha' || !/^[a-f0-9]{64}$/.test(args[3]) || args[4] !== '--source-track' || !args[5])) {
  throw new Error('Usage: node web/scripts/native-original-cpu-parent-smoke.mjs --freeze <new-archive-dir> --web-root <read-only-published-original-web> --raw-glb <protected-raw> --delivery-glb <protected-delivery> | --replay <archive-dir> --closure-sha <independently-recorded-sha256> --source-track <explicit-authored-source-track>')
}
const archive = resolve(args[1])
const sourceTrackPath = mode === '--freeze' ? resolve(args[3], 'content/v39/8KmVDxkia_w.source-track.json') : resolve(args[5])
let closure
if (mode === '--freeze') {
  closure = await freezeOriginalNativeCPUClosure({ webRoot: args[3], rawGLBPath: args[5], deliveryGLBPath: args[7] })
  // Refuse replacement: admission is once, not a stale reference refreshed in
  // place when the production code changes. Use a separately authorized archive.
  await mkdir(archive)
  await writeFile(resolve(archive, 'manifest.json'), JSON.stringify(closure.manifest, null, 2), { flag: 'wx' })
  await writeFile(resolve(archive, 'manifest.sha256'), `${closure.manifestSHA256}\n`, { flag: 'wx' })
  await writeFile(resolve(archive, 'raw.glb'), closure.rawGLBBytes, { flag: 'wx' })
  await writeFile(resolve(archive, 'delivery.glb'), closure.deliveryGLBBytes, { flag: 'wx' })
  await writeFile(resolve(archive, 'package-lock.json'), closure.packageLockBytes, { flag: 'wx' })
  for (let i = 0; i < closure.modules.length; i++) {
    await writeFile(resolve(archive, `${i}.source`), closure.modules[i].source, { flag: 'wx' })
    await writeFile(resolve(archive, `${i}.ssr`), closure.modules[i].transformed, { flag: 'wx' })
  }
} else {
  closure = await readOriginalNativeCPUClosure({ archive, manifestSHA256: args[3] })
}

const globals = new Map(['fetch', 'self', 'location', 'crypto'].map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]))
const oracle = await createOriginalNativePoseOracle({ closure })
try {
  assert.equal(oracle.inventory.drawables.length, 462)
  assert.equal(oracle.inventory.partPaths.length, 479)
  const springs = oracle.inventory.drawables.filter(row => row.spring !== null)
  assert.equal(springs.length, 21)
  assert.equal(springs.reduce((count, row) => count + row.geometry.getAttribute('position').count, 0), 3293594)
  assert.equal(oracle.inventory.drawables.filter(row => row.instanceOf !== null).length, 2)
  for (const [name, descriptor] of globals) assert.deepEqual(Object.getOwnPropertyDescriptor(globalThis, name), descriptor, `Node ${name} descriptor restored after GLTF load`)

  const trackBytes = await readFile(sourceTrackPath)
  const track = JSON.parse(trackBytes.toString('utf8'))
  const sourceTrackSHA256 = createHash('sha256').update(trackBytes).digest('hex')
  const views = track.frames.flatMap(frame => frame.views ?? []).filter(view => view.input)
  const first = views[0]
  const next = views.find(view => view.input.crankTurns !== first.input.crankTurns || JSON.stringify(view.input.amplitudes) !== JSON.stringify(first.input.amplitudes))
  assert.ok(first && next, 'Require two actual authored source inputs, not fabricated animation samples')
  function snapshot(view) {
    const result = oracle.solve(view.input, view.partOverrides ?? [])
    const hash = createHash('sha256')
    const lengths = []
    for (const row of result.drawables) {
      assert.ok(row.matrixWorld.every(Number.isFinite), row.path)
      hash.update(new Uint8Array(row.matrixWorld.buffer, row.matrixWorld.byteOffset, row.matrixWorld.byteLength))
      hash.update(row.effectiveVisibility ? 'visible' : 'hidden')
      if (row.springLengthM !== null) {
        assert.ok(Number.isFinite(row.springLengthM) && row.springLengthM > 0, row.path)
        lengths.push({ path: row.path, station: row.station, lengthM: row.springLengthM })
      }
    }
    assert.equal(lengths.length, 21)
    return { viewId: view.id, matrixAndVisibilitySHA256: hash.digest('hex'), lengths }
  }
  const initial = snapshot(first), moved = snapshot(next), restored = snapshot(first)
  assert.notEqual(initial.matrixAndVisibilitySHA256, moved.matrixAndVisibilitySHA256)
  assert.deepEqual(restored, initial, 'Original CPU source state is reproducible after another real state')

  const child = oracle.inventory.drawables.find(row => row.binding?.motion === 'cylinder')
  const parent = child.path.slice(0, child.path.lastIndexOf('/'))
  const target = [0.123, 0.456, -0.078]
  const childPose = oracle.solve(first.input, [
    { partPath: child.path, worldPositionMetres: target, visibility: 'hidden' },
    { partPath: parent, worldPositionMetres: [-0.2, 0.3, 0.4] },
  ]).drawables.find(row => row.path === child.path)
  target.forEach((value, axis) => assert.ok(Math.abs(childPose.matrixWorld[12 + axis] - value) < 1e-12))
  assert.equal(childPose.effectiveVisibility, false)
  console.log(JSON.stringify({ proof: 'Real frozen original ViteSSR/Three/GLTF/Meshopt CPU update; no renderer/GPU/source-fidelity claim',
    mode, archive, closureSHA256: closure.manifestSHA256, modules: closure.modules.length,
    originalSourceCommit: closure.manifest.original.sourceCommit, sourceTrackPath, sourceTrackSHA256,
    rawSHA256: oracle.inventory.rawSHA256, deliverySHA256: oracle.inventory.deliverySHA256,
    limitations: oracle.inventory.limitations,
    cameraNearFar: oracle.inventory.cameraNearFar,
    nativeNames: oracle.inventory.partPaths.length, nativeDrawables: oracle.inventory.drawables.length,
    springs: springs.length, snapshots: [initial, moved], simultaneousChildFirstOverride: { path: child.path, expectedWorldPositionMetres: target, actualWorldPositionMetres: Array.from(childPose.matrixWorld.subarray(12, 15)) },
  }, null, 2))
} finally { oracle.dispose() }
assert.throws(() => oracle.solve({}), /disposed/)
