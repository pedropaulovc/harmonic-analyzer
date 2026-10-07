import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { writeJsonReport } from './json-report-writer.mjs'

test('report output preserves native JSON value semantics and repeated evidence across stream chunks', async t => {
  const root = await mkdtemp(join(tmpdir(), 'json-report-values-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const path = join(root, 'report.json')
  const capture = { sourcePixels: [1.25, 2.5], nativeViewportBackingPixels: null, reason: 'unresolved "source"\n\\\ud800😀', raw: { missing: undefined, nonfinite: Infinity } }
  const sample = { status: 'unavailable', measurements: [{ rawErrorPx: NaN, errorPx: -0 }], nativeLandmarkEligibility: { state: 'unresolved', landmarks: [{ projection: capture }, { projection: capture }] } }
  const report = {
    status: 'unavailable', samples: Array.from({ length: 128 }, () => sample),
    unavailable: undefined, callback: () => {}, symbol: Symbol('omitted'),
    array: [undefined, , NaN, Infinity, -Infinity, () => {}, Symbol('null')],
    escapedReason: '😀\ud800\n"\\'.repeat(20_000),
    keyedValue: { toJSON(key) { return { key, state: 'unresolved' } } },
  }
  report.samples[0] = { ...sample, timeSeconds: 0.125 }
  report.samples[127] = { ...sample, timeSeconds: 127.875 }
  await writeJsonReport(path, report)
  const actual = JSON.parse(await readFile(path, 'utf8'))
  assert.deepEqual(actual, JSON.parse(JSON.stringify(report)))
  assert.equal(actual.status, 'unavailable')
  assert.equal(actual.samples[0].timeSeconds, 0.125)
  assert.equal(actual.samples[127].timeSeconds, 127.875)
  assert.ok(actual.samples.every(item => item.status === 'unavailable' && item.nativeLandmarkEligibility.state === 'unresolved'))
  for (const field of ['unavailable', 'callback', 'symbol']) assert.equal(Object.hasOwn(actual, field), false)
  assert.deepEqual(actual.array, [null, null, null, null, null, null, null])
  assert.equal(actual.escapedReason, report.escapedReason)
  assert.deepEqual(actual.keyedValue, { key: 'keyedValue', state: 'unresolved' })
  for (const item of actual.samples) {
    assert.deepEqual(item.measurements, [{ rawErrorPx: null, errorPx: 0 }])
    assert.deepEqual(item.nativeLandmarkEligibility.landmarks.map(landmark => landmark.projection), [
      { sourcePixels: [1.25, 2.5], nativeViewportBackingPixels: null, reason: capture.reason, raw: { nonfinite: null } },
      { sourcePixels: [1.25, 2.5], nativeViewportBackingPixels: null, reason: capture.reason, raw: { nonfinite: null } },
    ])
  }
})

test('invalid report values and output failures cannot replace a complete report with partial JSON', async t => {
  const root = await mkdtemp(join(tmpdir(), 'json-report-refusal-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const path = join(root, 'report.json'), prior = '{"status":"unavailable","sentinel":"complete evidence"}\n'
  await writeFile(path, prior)
  const cycle = { status: 'unavailable' }; cycle.samples = [cycle]
  for (const invalid of [cycle, { samples: [{ rawValue: 1n }] }, { get samples() { throw new Error('capture unavailable') } }, undefined]) {
    await assert.rejects(writeJsonReport(path, invalid), error => error.message.includes(path) && error.cause instanceof Error)
    assert.equal(await readFile(path, 'utf8'), prior)
    assert.deepEqual(await readdir(root), ['report.json'])
  }
  await assert.rejects(writeJsonReport(join(path, 'nested.json'), { status: 'unavailable' }), error => error.cause?.code === 'ENOTDIR')
  assert.equal(await readFile(path, 'utf8'), prior)
})
