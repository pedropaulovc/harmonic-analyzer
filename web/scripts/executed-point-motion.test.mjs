import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import * as THREE from 'three'
import { createServer, createLogger } from 'vite'
import { createPointMotionPairCompiler, classifyPointMotion } from './executed-point-motion.mjs'

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
