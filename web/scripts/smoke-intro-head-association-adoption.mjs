#!/usr/bin/env node
// Parent-only proof after the real Node -> current Python choices -> Intro track
// transaction. No source image/video decode, browser, GPU or fake primitive.
import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { parseArgs } from 'node:util'
import { verifyIntroHeadFeatureChoices } from './generate-intro-head-feature-choices.mjs'

const { values } = parseArgs({ options: {
  choices: { type: 'string' }, track: { type: 'string' }, output: { type: 'string' },
} })
if (!values.choices || !values.track) throw new Error('Parent-generated --choices and --track are required')
const verified = await verifyIntroHeadFeatureChoices(values.choices)
const [track, originalSeed, currentSeed] = await Promise.all([
  readFile(values.track, 'utf8').then(JSON.parse),
  readFile(new URL('../content/NAsM30MAHLg.static-camera-seeds.json', import.meta.url), 'utf8').then(JSON.parse),
  readFile(new URL('../content/v39/NAsM30MAHLg.static-camera-seeds.json', import.meta.url), 'utf8').then(JSON.parse),
])
assert.deepEqual(currentSeed.sourceFrame, originalSeed.sourceFrame, 'adoption cannot mutate any original source frame fact')
assert.equal(currentSeed.calibrationEligibility.status, 'unmeasured')
assert.equal(currentSeed.calibrationEligibility.eligible, null)
assert.equal(currentSeed.sourceAcceptance, false)
assert.equal(currentSeed.GPUAcceptance, false)
assert.equal(track.staticCalibrationEligibility.status, 'unmeasured')
assert.deepEqual(track.currentChoicePacket.headFeatureChoices, { path: verified.path, sha256: verified.sha256 })
for (const stage of [50, 20, 10, 5]) assert.equal(track.stages[stage].status, 'unmeasured', 'raw marker adoption cannot qualify a source stage')
const source809 = track.frames.find(frame => frame.sourceImage?.frameIndex === 809)
assert.ok(source809, 'current Intro track must retain original source809 exposure')
const adopted = []
for (const choice of verified.packet.choices) {
  const anchor = track.anchors.find(row => row.id === choice.anchorId)
  const originalPoint = originalSeed.sourceFrame.landmarks.find(row => row.anchorId === choice.anchorId)
  const point = source809.landmarks.find(row => row.anchorId === choice.anchorId)
  const currentSupport = currentSeed.nativeSupport.find(row => row.anchorId === choice.anchorId)
  assert.deepEqual(anchor.partLocalMetres, choice.partLocalMetres, 'marker must be the freshly reconstructed actual floor point')
  assert.equal(anchor.partPath, choice.partPath)
  assert.equal(anchor.nativeAssociation.proof.correspondenceChoice.state, 'chosen-unmeasured')
  assert.deepEqual(anchor.nativeAssociation.proof.frozenWitness, choice.frozenWitness)
  assert.deepEqual(anchor.nativeAssociation.proof.sourceBinding, choice.sourceBinding)
  assert.equal(currentSupport.status, 'mapped')
  assert.deepEqual(currentSupport.anchor.partLocalMetres, choice.partLocalMetres)
  for (const key of ['pixel', 'role', 'uncertaintyPx']) assert.deepEqual(point[key], originalPoint[key], `immutable original FIT ${key}`)
  assert.equal(point.role, 'fit')
  assert.equal(point.uncertaintyPx, 4)
  adopted.push({ anchorId: choice.anchorId, partPath: anchor.partPath, partLocalMetres: anchor.partLocalMetres,
    sourceRole: point.role, uncertaintyPx: point.uncertaintyPx, correspondenceState: 'chosen-unmeasured' })
}
assert.equal(new Set(adopted.map(row => row.partPath)).size, 4)
const temporary = await mkdtemp(join(tmpdir(), 'intro-raw-head-choice-control-'))
const refusals = []
try {
  for (const [id, mutate] of [
    ['nominal-head-height-substitution', packet => { packet.choices[0].partLocalMetres[1] = 0.004572 }],
    ['virtual-cap-centre-substitution', packet => { packet.choices[0].partLocalMetres[1] = 0.004556158557534218 }],
    ['different-native-instance', packet => { packet.choices[0].partPath = packet.choices[1].partPath }],
    ['FIT-promoted-to-CHECK', packet => { packet.choices[0].sourceBinding.role = 'check' }],
    ['contradictory-actual-slot-triangle', packet => { packet.choices[0].frozenWitness.triangleIndex++ }],
    ['moved-native-rim-support', packet => { packet.choices[0].geometryEvidence.rimEndpoints[0].localMetres[0] += 1e-5 }],
  ]) {
    const packet = structuredClone(verified.packet); mutate(packet)
    const path = join(temporary, `${id}.json`)
    await writeFile(path, JSON.stringify(packet))
    let reason
    try { await verifyIntroHeadFeatureChoices(path) } catch (error) { reason = error.message }
    assert.ok(reason, `${id} must refuse after original raw/source recomputation`)
    refusals.push({ id, reason })
  }
} finally { await rm(temporary, { recursive: true, force: true }) }
const report = { kind: 'actual-current-intro-head-choice-adoption-smoke', actualAdoptedFeatures: adopted,
  independentRefusals: refusals, originalSourceFrameUnchanged: true,
  sourceQualification: false, GPUQualification: false, firstSurfaceQualification: false,
  qualification: 'Fresh actual raw slot-floor native marker choices only. Source controls and all current camera/pose/rendered qualification obligations remain separate and unmeasured.' }
if (values.output) await writeFile(values.output, JSON.stringify(report, null, 2) + '\n')
console.log(JSON.stringify({ kind: report.kind, actualAdoptedFeatureCount: adopted.length,
  independentRefusalCount: refusals.length, originalSourceFrameUnchanged: true,
  sourceRoles: adopted.map(row => row.sourceRole), firstSurfaceQualification: false }, null, 2))
