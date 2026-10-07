import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { gunzipSync } from 'node:zlib'

const { WEB_ROOT, validateCurrentObservations } = await import(
  process.env.FRESH_OBSERVATIONS_MODULE ?? './fresh-source-observations.mjs')
const webRoot = process.env.FRESH_OBSERVATIONS_WEB_ROOT ?? WEB_ROOT
const original = JSON.parse(gunzipSync(await readFile(
  resolve(webRoot, 'content/v39-source/XPQwKRt4Y2k.observations.json.gz'))))
const exposures = new Map(original.frames.map(frame => [frame.timeSeconds, frame]))

// Only the two-shot non-machine partition is synthetic. Original source/native
// authority, decoded PTS and exact image identities come from the sealed record.
// This fixture is a clock-contract control, not a measured source-fidelity claim.
function recordFixture() {
  const duration = original.source.durationSeconds
  return {
    schemaVersion: 1,
    kind: 'current-source-observations',
    source: structuredClone(original.source),
    model: structuredClone(original.model),
    nativeIdentity: structuredClone(original.nativeIdentity),
    anchors: [],
    shots: [
      { id: 'before', startSeconds: 0, endSeconds: 10, classification: 'non-machine', reason: 'Synthetic partition fixture.' },
      { id: 'after', startSeconds: 10, endSeconds: duration, classification: 'non-machine', reason: 'Synthetic partition fixture.' },
    ],
    frames: Array.from({ length: Math.ceil(duration) }, (_, time) => {
      const frame = exposures.get(time)
      assert(frame, `Missing original fixture exposure at ${time}s`)
      return {
        timeSeconds: time, decodedTimeSeconds: frame.decodedTimeSeconds,
        decodedFrameIndex: frame.sourceImage.frameIndex,
        sourceImage: structuredClone(frame.sourceImage),
        shotId: time < 10 ? 'before' : 'after', classification: 'non-machine',
        views: [], landmarks: [],
      }
    }),
    coverage: { status: 'complete', blockers: [], requiredEveryIntegerSecond: true, changeTimesSeconds: [] },
  }
}

async function requirePartitionRefusal(mutate, message) {
  const record = recordFixture()
  // Every refusal arm first proves its own unmodified record and authority valid.
  await validateCurrentObservations(record, { webRoot })
  mutate(record)
  const before = structuredClone(record)
  await assert.rejects(validateCurrentObservations(record, { webRoot }), message)
  assert.deepEqual(record, before, 'Refusal must not repair authored clocks or exposures')
}

test('accepts an exact zero-to-duration partition without rewriting authored clocks or exposures', async () => {
  const record = recordFixture(), before = structuredClone(record)
  await validateCurrentObservations(record, { webRoot })
  assert.deepEqual(record, before, 'Validation must preserve the exact authored evidence')
})

test('refuses a sub-microsecond gap even when near-integer coverage and exposure ownership are valid', async () => {
  await requirePartitionRefusal(record => {
    record.shots[1].startSeconds += 5e-7
    // The real decoded PTS is 10.01: it remains inside the incoming shot.
    // Only the requested key moves, so the old 1e-6 coverage check accepts it.
    record.frames[10].timeSeconds += 5e-7
  }, /Current source shots must form a complete ordered half-open census/)
})

test('refuses a sub-microsecond overlap instead of leaving ambiguous half-open ownership', async () => {
  await requirePartitionRefusal(record => {
    record.shots[1].startSeconds -= 5e-7
  }, /Current source shots must form a complete ordered half-open census/)
})

test('refuses a sub-microsecond final tail gap even when every integer exposure is covered', async () => {
  await requirePartitionRefusal(record => {
    record.shots[1].endSeconds -= 5e-7
  }, /Current source shot census does not reach source end/)
})
