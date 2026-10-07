import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
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
  const blocked = join(root, 'blocked.json')
  await mkdir(blocked)
  const renameCode = process.platform === 'win32' ? 'EPERM' : 'EISDIR'
  let reason
  await assert.rejects(writeJsonReport(blocked, report), error => {
    assert.equal(error.cause?.code, renameCode)
    reason = error.message
    return true
  })
  const failurePath = join(root, 'failure.json')
  await writeJsonReport(failurePath, { failures: [{ code: 'verification-prerequisite', reason }] })
  const savedReason = JSON.parse(await readFile(failurePath, 'utf8')).failures[0].reason
  assert.ok(savedReason.includes(blocked))
  assert.match(savedReason, new RegExp(`\\b${renameCode}\\b`))
  assert.deepEqual((await readdir(root)).sort(), ['blocked.json', 'failure.json', 'report.json'])
})

test('invalid report values and output failures cannot replace a complete report with partial JSON', async t => {
  const root = await mkdtemp(join(tmpdir(), 'json-report-refusal-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const path = join(root, 'report.json'), prior = '{"status":"unavailable","sentinel":"complete evidence"}\n'
  await writeFile(path, prior)
  const cycle = { status: 'unavailable' }; cycle.samples = [cycle]
  const invalidReports = [
    [cycle, /circular structure/],
    [{ samples: [{ rawValue: 1n }] }, /serialize a BigInt/],
    [{ get samples() { throw new Error('capture unavailable') } }, /capture unavailable/],
    [{ get samples() { throw 'capture threw a string' } }, /capture threw a string/],
    [undefined, /no JSON representation/],
  ]
  const failures = []
  for (const [invalid] of invalidReports) {
    await assert.rejects(writeJsonReport(path, invalid), error => {
      assert.ok(error.cause instanceof Error || error.cause === 'capture threw a string')
      failures.push({ code: 'verification-prerequisite', reason: error.message })
      return true
    })
    assert.equal(await readFile(path, 'utf8'), prior)
    assert.deepEqual(await readdir(root), ['report.json'])
  }
  const nestedPath = join(path, 'nested.json')
  await assert.rejects(writeJsonReport(nestedPath, { status: 'unavailable' }), error => {
    assert.equal(error.cause?.code, 'ENOTDIR')
    failures.push({ code: 'verification-prerequisite', reason: error.message })
    return true
  })
  assert.equal(await readFile(path, 'utf8'), prior)
  const failurePath = join(root, 'failure.json')
  await writeJsonReport(failurePath, { failures, videos: [{ interaction: { reportWriteError: failures[2].reason } }] })
  const saved = JSON.parse(await readFile(failurePath, 'utf8'))
  for (const [index, [, underlyingMessage]] of invalidReports.entries()) {
    assert.ok(saved.failures[index].reason.includes(path))
    assert.match(saved.failures[index].reason, underlyingMessage)
  }
  assert.ok(saved.failures.at(-1).reason.includes(nestedPath))
  assert.match(saved.failures.at(-1).reason, /ENOTDIR/)
  assert.ok(saved.videos[0].interaction.reportWriteError.includes(path))
  assert.match(saved.videos[0].interaction.reportWriteError, /capture unavailable/)
  assert.deepEqual((await readdir(root)).sort(), ['failure.json', 'report.json'])
})
