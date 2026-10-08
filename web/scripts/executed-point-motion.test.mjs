import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createPointMotionClassifier } from './executed-point-motion.mjs'

const approved = JSON.parse(await readFile(new URL('../content/model-representation.json', import.meta.url), 'utf8'))
const manifest = JSON.parse(await readFile(new URL('../content/canonical-native/manifest.json', import.meta.url), 'utf8'))
const authority = { model: { ...approved.source, units: 'metres', axes: 'X-width/Y-height/Z-depth' },
  nativeIdentity: { mapSha256: approved.identity.mapSha256, canonicalSha256: approved.identity.canonicalSha256,
    inventorySha256: manifest.currentSourceInventory.sha256 } }
const introInput = { crankTurns: 0, amplitudes: Array(20).fill(0), phases: Array(20).fill(0),
  gearing: 'small-large', magnification: 4.1405269761606025,
  setup: { counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0,
    coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 } }
const synthesisInput = { ...structuredClone(introInput), magnification: 4.85205222755,
  setup: { ...introInput.setup, counterHeightM: 1.24, wireFixtureOffsetM: 0.015 } }
const spinInput = { ...structuredClone(introInput), setup: { ...introInput.setup, counterHeightM: 1.1863569024618958 } }
const anchor = (id, partPath, partLocalMetres) => ({ id, kind: 'physical-feature', partPath, partLocalMetres,
  correspondenceEvidence: 'Actual raw native face/crown feature association; no authored motion override.' })
const intro = anchor('intro-front', 'ha-harmonic-analyzer/dt-drive-train/dt-crank-handle-1', [0.057999998331069946, 0, 0])
const synthesis = anchor('synthesis-butt', 'ha-harmonic-analyzer/dt-drive-train/dt-crank-handle-butt-cup-1', [-0.008100000210106373, 0, 0])
const wheel = anchor('spin-rim', 'ha-harmonic-analyzer/mg-magnifier/mg-magnifying-wheel-1', [-0.0014816663460806012, 0.04997804015874863, 0])
const classifier = await createPointMotionClassifier()
after(async () => classifier.dispose())
const request = cases => ({ ...authority, cases })
const positive = request([{ anchor: intro, input: introInput }, { anchor: synthesis, input: synthesisInput }, { anchor: wheel, input: spinInput }])
let receipt

test('actual approved model transforms Intro/Synthesis and rigid wheel points under feasible isolated drivers', async () => {
  const original = structuredClone(positive)
  receipt = classifier.classify(positive)
  assert.deepEqual(positive, original)
  assert.equal(receipt.provenance.identity, 'matched')
  assert.equal(receipt.provenance.observedSha256, approved.representation.sha256)
  assert.equal(receipt.provenance.observedByteLength, approved.representation.byteLength)
  assert.deepEqual(receipt.results.map(row => row.motion), ['moving', 'moving', 'moving'])
  for (const row of receipt.results) {
    assert(row.displacementMetres > row.roundoffMetres)
    assert(row.pointPair.flat().every(Number.isFinite))
    assert.equal(row.sameInputNoiseMetres, 0)
    assert.equal(row.returnInputNoiseMetres, 0)
    assert.deepEqual(row.pointPair[0], row.sameInputPoint)
    assert.deepEqual(row.pointPair[0], row.returnedInputPoint)
  }
  for (const pair of receipt.inputPairs) {
    const [first, second] = pair.input
    assert.deepEqual(first.setup, second.setup)
    assert.deepEqual(first.amplitudes, second.amplitudes)
    assert.equal(first.gearing, second.gearing)
    assert.equal(first.magnification, second.magnification)
    assert(pair.equilibriumResidualNm.every(value => Number.isFinite(value) && Math.abs(value) < 1e-9))
    assert.equal(pair.driver, 'crankTurns')
    assert.equal(second.crankTurns - first.crankTurns, 0.125)
    assert.deepEqual(first.phases, second.phases)
  }
  assert(Math.abs(receipt.results[0].displacementMetres - 0.0574025142845223) < 1e-10)
  assert(Math.abs(receipt.results[2].displacementMetres - 0.000017555937020096704) < 1e-12)
  if (process.env.POINT_MOTION_RECEIPT_PATH) await writeFile(process.env.POINT_MOTION_RECEIPT_PATH, JSON.stringify(receipt, null, 2) + '\n')
})

test('actual axis centres, missing/unbound/deforming/unsupported points and invalid associations remain null', () => {
  const cases = [
    anchor('actual-wheel-centre', wheel.partPath, [0, 0, 0]),
    anchor('actual-crank-centre', 'ha-harmonic-analyzer/dt-drive-train/dt-crankshaft-1', [0, 0, 0]),
    anchor('missing', 'ha-harmonic-analyzer/dt-drive-train/nonexistent-1', [0, 0, 0]),
    anchor('actual-unbound', 'ha-harmonic-analyzer/fr-frame/fr-harmonic-base-1', [0, 0, 0]),
    anchor('actual-deforming-spring', 'ha-harmonic-analyzer/ch-channel/vn-channel-spring-installed-stretch00-1', [0, 0, 0]),
    anchor('unproven-cylinder', 'ha-harmonic-analyzer/dt-drive-train/dt-cylinder-gear-1', [0.01, 0, 0]),
    { ...intro, id: 'ambiguous', worldMetres: [0, 0, 0] },
    { ...intro, id: 'nonfinite', partLocalMetres: [NaN, 0, 0] },
    { ...intro, id: 'wrong-template', runtimeTemplatePartPath: intro.partPath },
    { ...intro, id: 'no-correspondence', correspondenceEvidence: '' },
  ]
  for (const index of [3, 4, 5]) assert(classifier.machine.partPaths.includes(cases[index].partPath))
  const result = classifier.classify(request(cases.map(anchor => ({ anchor, input: introInput }))))
  assert(result.results.every(row => row.motion === null))
  assert(result.results[0].displacementMetres < result.results[0].roundoffMetres)
  assert(result.results[1].displacementMetres < result.results[1].roundoffMetres)
})

test('actual rest-world association uses the loaded native node frame, not an inventory rotation', () => {
  const restWorld = [-0.12933643429222708, 0.05485000088810921, -0.24099999467688288]
  const { partLocalMetres, ...worldAnchor } = intro
  const result = classifier.classify(request([{ anchor: { ...worldAnchor, id: 'front-rest-world', worldMetres: restWorld }, input: introInput }]))
  assert.equal(result.results[0].motion, 'moving')
  assert(Math.abs(result.results[0].displacementMetres - receipt.results[0].displacementMetres) < 1e-12)
})

test('invalid authority and unclosed complete inputs cannot promote a native point', () => {
  for (const field of ['mapSha256', 'canonicalSha256', 'inventorySha256']) {
    const invalid = structuredClone(positive)
    invalid.nativeIdentity[field] = '0'.repeat(64)
    assert(classifier.classify(invalid).results.every(row => row.motion === null))
  }
  const invalid = structuredClone(positive)
  invalid.model.sha256 = '0'.repeat(64)
  assert(classifier.classify(invalid).results.every(row => row.motion === null))
  for (const input of [{ ...introInput, magnification: 99 }, { ...introInput, phases: [0] }, { ...introInput, crankTurns: NaN }]) {
    assert.equal(classifier.classify(request([{ anchor: intro, input }])).results[0].motion, null)
  }
})

test('normal baseline leases expire; identical actual input leaves its matrix unchanged', () => {
  let lease
  const matrix = new Float64Array(16), worlds = []
  for (let repeat = 0; repeat < 2; repeat++) {
    const input = { ...classifier.machine.input, crankTurns: 0, amplitudes: new Float64Array(20), phases: new Float64Array(20), setup: { ...introInput.setup } }
    classifier.machine.update(input, baseline => {
      lease = baseline
      assert.equal(baseline.readWorldMatrix(wheel.partPath, matrix), true)
      worlds.push(Array.from(matrix))
      assert.equal(baseline.readWorldMatrix('missing/native/part', matrix), false)
      assert.throws(() => baseline.readWorldMatrix(wheel.partPath, new Float64Array(15)), /exactly 16/)
      return []
    })
  }
  assert.deepEqual(worlds[0], worlds[1])
  assert.throws(() => lease.readWorldMatrix(wheel.partPath, matrix), /only within the current update provider callback/)
})

test('cached body/input-family matrices require no further actual updates for repeated/new points', () => {
  const update = classifier.machine.update
  let updates = 0
  classifier.machine.update = (...args) => { updates++; return update(...args) }
  try {
    assert.equal(classifier.classify(positive).results[0].motion, 'moving')
    assert.equal(classifier.classify(request([{ anchor: { ...intro, id: 'same-body-new-point', partLocalMetres: [0.04, 0, 0] }, input: introInput }])).results[0].motion, 'moving')
    assert.equal(updates, 0)
  } finally { classifier.machine.update = update }
})

test('tampered actual GLB cannot stand in for the identity-matched model', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'actual-point-motion-invalid-'))
  try {
    const bytes = await readFile(new URL('../public/models/ha-harmonic-analyzer.glb', import.meta.url))
    bytes[bytes.length - 1] ^= 1
    const path = join(directory, 'tampered.glb')
    await writeFile(path, bytes)
    await assert.rejects(createPointMotionClassifier({ modelPath: path }), /Actual native motion model unavailable:.*identity mismatch/)
  } finally { await rm(directory, { recursive: true, force: true }) }
})
