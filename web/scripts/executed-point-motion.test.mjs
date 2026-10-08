import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { readFile } from 'node:fs/promises'
import * as THREE from 'three'
import { createServer, createLogger } from 'vite'
import { createPointMotionPairCompiler, createSourcePointMotionPairCompiler, classifyPointMotion } from './executed-point-motion.mjs'

// Real source compilation/physical solving is portable; no production GLB,
// model-loader substitution, fixture machine, or network fetch is required.
const logger = createLogger()
logger.info = message => process.stderr.write(`${message}\n`)
const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
  configFile: false, customLogger: logger,
  server: { middlewareMode: true, hmr: false, watch: null, ws: false }, appType: 'custom' })
after(async () => server.close())
const witness = await server.ssrLoadModule('/src/source-witness.ts')
const mechanics = await server.ssrLoadModule('/src/mechanics.ts')
const compiler = () => createPointMotionPairCompiler({ ...witness, ...mechanics })
const assembly = await server.ssrLoadModule('/src/source-assembly.ts')
const sourceCompiler = () => createSourcePointMotionPairCompiler({ ...witness, ...mechanics, ...assembly })
const gearIds = Object.keys(assembly.SOURCE_GEAR_PART_PATHS)
const sourceState = () => ({ kind: 'source-assembly',
  provenance: { kind: 'chosen-feasible', videoId: 'jfH-NbsmvD4', frameIndex: 1,
    evidence: 'Portable rigid body capability control, not source image evidence.',
    unobservedDegreesOfFreedom: ['Chosen local body poses'] },
  photograph: { pair: 'four-gears',
    displayPose: { positionMetres: [.21, -.13, .04], quaternion: [0, 0, Math.sin(.2), Math.cos(.2)] },
    fourGearPoses: Object.fromEntries(gearIds.map((id, i) => [id,
      { positionMetres: [.04 * i, .013 * i, -.01 * i], quaternion: [Math.sin(.3), 0, 0, Math.cos(.3)] }])) } })
const sourceAnchor = id => {
  const partPath = assembly.SOURCE_GEAR_PART_PATHS[id]
  const runtime = Object.values(assembly.NATIVE_RUNTIME_INSTANCES).find(value => value.partPath === partPath)
  return { id: 'portable-feature', kind: 'physical-feature', partPath,
    ...(runtime ? { runtimeTemplatePartPath: runtime.templatePartPath } : {}),
    partLocalMetres: [0, .007, .0028], correspondenceEvidence: 'Explicit local material point' }
}
const input = () => ({ crankTurns: 0, amplitudes: Array(20).fill(0), phases: Array(20).fill(0),
  gearing: 'small-large', magnification: 4.1405269761606025,
  setup: { counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0,
    coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 } })

test('real source solver compiles a complete feasible pair with only a one-eighth crank change', () => {
  const raw = input(), original = structuredClone(raw), pairFor = compiler()
  const pair = pairFor(raw, 'crank')
  assert(pair)
  assert.deepEqual(raw, original)
  const [first, second] = pair.serialized
  assert.equal(second.crankTurns - first.crankTurns, 0.125)
  assert.deepEqual(first.phases, second.phases)
  assert.deepEqual(first.amplitudes, second.amplitudes)
  assert.deepEqual(first.setup, second.setup)
  assert.equal(first.gearing, second.gearing)
  assert.equal(first.magnification, second.magnification)
  assert(Math.abs(first.setup.counterHeightM - 1.1863569024618958) < 1e-12)
  assert.deepEqual(pair.angles, [0, Math.PI / 4])
  assert(pair.equilibriumResidualNm.every(value => Number.isFinite(value) && Math.abs(value) < 1e-9))
  assert.strictEqual(pairFor(structuredClone(raw), 'crank'), pair)
})

test('real loaded-bank/wire solver supplies the wheel angle, without amplitude or phase activation', () => {
  const raw = input()
  raw.setup.counterHeightM = 1.1863569024618958
  const pair = compiler()(raw, 'wheel')
  assert(pair)
  assert(pair.serialized.every(value => value.amplitudes.every(value => value === 0) && value.phases.every(value => value === 0)))
  assert(Math.abs(pair.angles[0]) < 1e-12)
  assert(Math.abs(pair.angles[1] - 0.0003511188588601461) < 1e-12)
})

for (const [label, value] of [['NaN', NaN], ['Infinity', Infinity], ['-Infinity', -Infinity]]) {
  test(`warm valid automatic counter then ${label} cannot hit a valid cached pair`, () => {
    const pairFor = compiler(), valid = input(), invalid = structuredClone(valid)
    const pair = pairFor(valid, 'crank')
    assert(pair)
    invalid.setup.counterHeightM = value
    assert.equal(pairFor(invalid, 'crank'), null)
    assert.strictEqual(pairFor(valid, 'crank'), pair)
  })
  test(`cold ${label} counter cannot poison a later valid automatic-counter family`, () => {
    const pairFor = compiler(), valid = input(), invalid = structuredClone(valid)
    invalid.setup.counterHeightM = value
    assert.equal(pairFor(invalid, 'crank'), null)
    const pair = pairFor(valid, 'crank')
    assert(pair)
    assert.strictEqual(pairFor(valid, 'crank'), pair)
  })
}

test('raw shape/nonfinite values and real compiler/solver refusal occur before cache promotion', () => {
  const pairFor = compiler(), valid = input(), pair = pairFor(valid, 'crank')
  assert(pair)
  const invalid = [
    { ...valid, extraField: undefined }, { ...valid, crankTurns: NaN },
    { ...valid, magnification: Infinity }, { ...valid, phases: [0] },
    { ...valid, magnification: 99 }, { ...valid, setup: { ...valid.setup, wireFixtureOffsetM: 99 } },
  ]
  for (const raw of invalid) assert.equal(pairFor(raw, 'crank'), null)
  assert.equal(pairFor(valid, 'channel-spring'), null)
  assert.equal(pairFor(valid, 'cone-spin'), null)
  assert.strictEqual(pairFor(valid, 'crank'), pair)
})

test('JSON numeric overflow is rejected, while the distinct valid null counter remains automatic', () => {
  const raw = input()
  const overflow = JSON.parse(JSON.stringify(raw).replace('"counterHeightM":null', '"counterHeightM":1e999'))
  const pairFor = compiler()
  assert.equal(overflow.setup.counterHeightM, Infinity)
  assert.equal(pairFor(overflow, 'crank'), null)
  assert(pairFor(raw, 'crank'))
})

test('a small real THREE rigid geometry quarter-turn has independently known point displacement', () => {
  // This tests the production displacement boundary, not native Machine/lease
  // eligibility. Real approved-Machine controls remain separate integration evidence.
  const geometry = new THREE.BoxGeometry(0.002, 0.002, 0.002)
  const body = new THREE.Mesh(geometry)
  const root = new THREE.Group()
  body.position.set(0.075, 0, 0)
  root.add(body)
  const point = new THREE.Vector3(), world = []
  for (const angle of [0, 0, Math.PI / 2, 0]) {
    root.rotation.z = angle
    root.updateMatrixWorld(true)
    world.push(point.set(0, 0, 0).applyMatrix4(body.matrixWorld).toArray())
  }
  const result = classifyPointMotion(world)
  assert.equal(result.motion, 'moving')
  assert(Math.abs(result.displacementMetres - 0.075 * Math.SQRT2) < 1e-15)
  assert.equal(result.sameInputNoiseMetres, 0)
  assert.equal(result.returnInputNoiseMetres, 0)
  assert.deepEqual(world[0], [0.075, 0, 0])
  assert(Math.abs(world[2][0]) < 1e-15)
  assert.equal(world[2][1], 0.075)
  geometry.dispose()
  body.material.dispose()
})

test('centres, identical points, decoded-datum ambiguity and measured repeat/return noise remain null', () => {
  const zero = [0, 0, 0], a = [0.075, 0, 0]
  assert.equal(classifyPointMotion([zero, zero, zero, zero]).motion, null)
  assert.equal(classifyPointMotion([a, a, a, a]).motion, null)
  assert.equal(classifyPointMotion([a, a, [a[0] + Number.EPSILON, 0, 0], a]).motion, null)
  const b = [0.076, 0, 0], noisy = [0.077, 0, 0]
  const repeat = classifyPointMotion([a, noisy, b, a])
  assert.equal(repeat.motion, null)
  assert(repeat.sameInputNoiseMetres > repeat.displacementMetres)
  const returned = classifyPointMotion([a, a, b, noisy])
  assert.equal(returned.motion, null)
  assert(returned.returnInputNoiseMetres > returned.displacementMetres)
})

test('missing, malformed and nonfinite point leases cannot become moving or fixed', () => {
  const a = [0.075, 0, 0]
  for (const world of [null, [], [a, a, a], [a, a, null, a], [a, a, [NaN, 0, 0], a], [a, a, [0, Infinity, 0], a]]) {
    const result = classifyPointMotion(world)
    assert.equal(result.motion, null)
    assert.match(result.reason, /unavailable or nonfinite/)
  }
})

test('compiled registered geometry chooses only a target local quaternion, preserving every other gauge/input', () => {
  const pairFor = sourceCompiler(), raw = input(), state = sourceState(), original = structuredClone(state)
  for (const id of gearIds) {
    const pair = pairFor(raw, state, sourceAnchor(id))
    assert(pair)
    assert.deepEqual(pair.serialized, [raw, raw])
    assert.strictEqual(pair.inputs[0], pair.inputs[1])
    assert.deepEqual(pair.sourceAssembly[0], state)
    assert.deepEqual(pair.sourceAssembly[1].photograph.displayPose, state.photograph.displayPose)
    for (const other of gearIds) {
      const before = state.photograph.fourGearPoses[other], after = pair.sourceAssembly[1].photograph.fourGearPoses[other]
      assert.deepEqual(after.positionMetres, before.positionMetres)
      if (other !== id) assert.deepEqual(after, before)
      else {
        const expected = new THREE.Quaternion().fromArray(before.quaternion)
          .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), .125))
        assert(Math.hypot(...after.quaternion.map((value, i) => value - expected.toArray()[i])) < 1e-15)
      }
    }
    assert.deepEqual(pair.angles, [0, .125])
    assert(pair.equilibriumResidualNm.every(value => Number.isFinite(value) && Math.abs(value) < 1e-9))
    assert.strictEqual(pairFor(structuredClone(raw), structuredClone(state), sourceAnchor(id)), pair)
  }
  assert.deepEqual(state, original)
})

test('real source provider plus rigid Float32 geometry moves only the off-axis point and returns exactly', async () => {
  const id = gearIds.find(value => assembly.NATIVE_RUNTIME_INSTANCES.upperMedium.partPath === assembly.SOURCE_GEAR_PART_PATHS[value])
  const pair = sourceCompiler()(input(), sourceState(), sourceAnchor(id))
  assert(pair)
  const inventory = JSON.parse(await readFile(new URL('../content/v39-source/native-inventory.json', import.meta.url), 'utf8'))
  const matrices = new Map(inventory.inventory.map(row => [row.path, row.world]))
  for (const instance of Object.values(assembly.NATIVE_RUNTIME_INSTANCES)) matrices.set(instance.partPath, matrices.get(instance.templatePartPath))
  const context = { readWorldMatrix(path, out) { const value = matrices.get(path); if (!value) return false; out.set(value); return true },
    readVisibility(path) { return matrices.has(path) ? true : null } }
  const geometry = new THREE.BufferGeometry().setAttribute('position',
    new THREE.Float32BufferAttribute([0, .007, .0028, 0, 0, .0028], 3))
  const bodies = new Map(gearIds.map(gear => [assembly.SOURCE_GEAR_PART_PATHS[gear], new THREE.Points(geometry)]))
  const buffer = assembly.createSourceAssemblyBuffer(), point = new THREE.Vector3(), moving = [], axis = [], other = []
  const otherPath = assembly.SOURCE_GEAR_PART_PATHS[gearIds.find(gear => gear !== id)]
  for (const step of [0, 0, 1, 0]) {
    const overrides = assembly.solveSourceAssembly(pair.assemblies[step], context, buffer)
    for (const [path, body] of bodies) {
      const posed = overrides.find(value => value.partPath === path)
      assert(posed)
      body.position.fromArray(posed.worldPositionMetres); body.quaternion.fromArray(posed.worldQuaternion)
      body.updateMatrixWorld(true)
      assert.strictEqual(body.geometry, geometry)
    }
    const target = bodies.get(assembly.SOURCE_GEAR_PART_PATHS[id]), position = geometry.getAttribute('position')
    moving.push(point.fromBufferAttribute(position, 0).applyMatrix4(target.matrixWorld).toArray())
    axis.push(point.fromBufferAttribute(position, 1).applyMatrix4(target.matrixWorld).toArray())
    other.push(point.fromBufferAttribute(position, 0).applyMatrix4(bodies.get(otherPath).matrixWorld).toArray())
  }
  const result = classifyPointMotion(moving)
  assert.equal(result.motion, 'moving')
  assert(Math.abs(result.displacementMetres - 2 * geometry.getAttribute('position').getY(0) * Math.sin(.125 / 2)) < 1e-15)
  assert.equal(result.sameInputNoiseMetres, 0)
  assert.equal(result.returnInputNoiseMetres, 0)
  assert.equal(classifyPointMotion(axis).motion, null)
  assert.equal(classifyPointMotion(axis).displacementMetres, 0)
  assert.equal(classifyPointMotion(other).displacementMetres, 0)
  geometry.dispose()
  for (const body of bodies.values()) body.material.dispose()
})

test('source cache includes full assembly and rejects malformed/unsupported raw values before lookup', () => {
  const pairFor = sourceCompiler(), raw = input(), state = sourceState(), id = gearIds[0], anchor = sourceAnchor(id)
  const valid = pairFor(raw, state, anchor)
  assert(valid)
  for (const change of [
    value => { value.photograph.displayPose.positionMetres[0] += .1 },
    value => { value.photograph.fourGearPoses[gearIds[1]].positionMetres[1] += .1 },
    value => { value.photograph.fourGearPoses[gearIds[1]].quaternion = [0, 0, 0, 1] },
  ]) {
    const changed = structuredClone(state); change(changed)
    const pair = pairFor(raw, changed, anchor)
    assert(pair); assert.notStrictEqual(pair, valid)
  }
  for (const value of [NaN, Infinity, -Infinity, null]) {
    const changed = structuredClone(state)
    changed.photograph.fourGearPoses[id].positionMetres[0] = value
    assert.equal(pairFor(raw, changed, anchor), null)
  }
  for (const quaternion of [[0, 0, 0, 0], [0, 0, 0, 2], [NaN, 0, 0, 1], [0, Infinity, 0, 1], [0, 0, 1]]) {
    const changed = structuredClone(state); changed.photograph.fourGearPoses[id].quaternion = quaternion
    assert.equal(pairFor(raw, changed, anchor), null)
  }
  const pairView = structuredClone(state)
  pairView.photograph.pair = 'T24-T12'; delete pairView.photograph.fourGearPoses
  assert.equal(pairFor(raw, pairView, anchor), null)
  assert.equal(pairFor(raw, { kind: 'operating' }, anchor), null)
  assert.equal(pairFor(raw, state, { ...anchor, runtimeTemplatePartPath: 'wrong-template' }), null)
  const missingLocal = { ...anchor }; delete missingLocal.partLocalMetres
  assert.equal(pairFor(raw, state, missingLocal), null)
  assert.equal(pairFor(raw, state, { ...anchor, partPath: anchor.partPath + '@arbitrary-copy' }), null)
  assert.equal(pairFor(raw, state, { ...anchor, worldMetres: [0, 0, 0] }), null)
  assert.equal(pairFor({ ...raw, crankTurns: NaN }, state, anchor), null)
  assert.strictEqual(pairFor(raw, state, anchor), valid)
})
