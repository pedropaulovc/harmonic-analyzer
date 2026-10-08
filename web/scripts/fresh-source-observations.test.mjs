import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp, mkdir, copyFile, symlink, rm, access, realpath } from 'node:fs/promises'
import { constants } from 'node:fs'
import { resolve, dirname, delimiter } from 'node:path'
import { tmpdir } from 'node:os'
import { gunzipSync } from 'node:zlib'

import { VIDEO_IDS, runTool } from './verify-reference.mjs'

const { WEB_ROOT, validateCurrentObservations, loadCurrentObservations, validateCurrentTrackAssociation } = await import(
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

test('actual current tracks associate through uv without an ambient python3 alias and retain refusal gates', async t => {
  const originalPath = process.env.PATH
  const directory = await mkdtemp(resolve(tmpdir(), 'fresh-association-'))
  try {
    if (process.platform !== 'win32') {
      const bin = resolve(directory, 'bin')
      await mkdir(bin)
      let uv
      for (const entry of originalPath.split(delimiter)) {
        const candidate = resolve(entry, 'uv')
        try { await access(candidate, constants.X_OK); uv = await realpath(candidate); break } catch {}
      }
      assert(uv, 'The declared uv tool must be available')
      const python = (await runTool(uv, ['python', 'find'])).stdout.toString().trim()
      for (const [name, executable] of [['node', process.execPath], ['uv', uv], ['python', python]]) {
        await symlink(executable, resolve(bin, name))
      }
      process.env.PATH = bin
      await assert.rejects(runTool('python3', ['--version']), error => error.code === 'ENOENT')
      await runTool('uv', ['run', '--isolated', '--no-project', 'python', '-c', 'import json,sys; print(json.dumps(sys.version))'])
    }
    let spinTrack, spinObservations
    await t.test('all six original current records preserve their exact direct association', async () => {
      for (const id of VIDEO_IDS) {
        const observations = await loadCurrentObservations(webRoot, id)
        const track = JSON.parse(await readFile(resolve(webRoot, `content/${id}.source-track.json`)))
        assert.strictEqual(await validateCurrentTrackAssociation(track, observations, webRoot), track)
        if (id === 'XPQwKRt4Y2k') { spinTrack = track; spinObservations = observations }
      }
    })
    assert(spinTrack && spinObservations)
    await t.test('a wrong actual compressed record hash still refuses without repair', async () => {
      const wrong = structuredClone(spinTrack)
      wrong.sourceRecord.sha256 = '0'.repeat(64)
      await assert.rejects(validateCurrentTrackAssociation(wrong, spinObservations, webRoot),
        /Compact track compressed fresh observation bytes changed/)
      assert.equal(wrong.sourceRecord.sha256, '0'.repeat(64))
    })
    await t.test('an actual wrong live generation seal still refuses through the Python checker', async () => {
      const fixture = resolve(directory, 'sealed/web')
      await mkdir(resolve(fixture, 'content/canonical-native'), { recursive: true })
      await mkdir(resolve(fixture, 'content/v39-source'), { recursive: true })
      for (const name of ['scripts', 'src', 'node_modules']) {
        await symlink(resolve(webRoot, name), resolve(fixture, name), 'junction')
      }
      await symlink(resolve(webRoot, '../cad'), resolve(fixture, '../cad'), 'junction')
      const manifest = JSON.parse(await readFile(resolve(webRoot, 'content/canonical-native/manifest.json')))
      for (const input of manifest.canonicalConsumerInputs) {
        if (/^(web\/(?:scripts|src)\/|cad\/)/.test(input.path)) continue
        const destination = resolve(fixture, '..', input.path)
        await mkdir(dirname(destination), { recursive: true })
        await copyFile(resolve(webRoot, '..', input.path), destination)
      }
      for (const name of ['native-inventory.json', 'XPQwKRt4Y2k.observations.json.gz']) {
        await copyFile(resolve(webRoot, 'content/v39-source', name), resolve(fixture, 'content/v39-source', name))
      }
      const manifestPath = resolve(fixture, 'content/canonical-native/manifest.json')
      await writeFile(manifestPath, JSON.stringify(manifest))
      assert.strictEqual(await validateCurrentTrackAssociation(spinTrack, spinObservations, fixture), spinTrack)
      const seal = manifest.canonicalConsumerInputs.find(input => input.path === 'web/scripts/compact-source-common.py')
      assert(seal, 'The actual mandatory Python seal must exist')
      seal.sha256 = '0'.repeat(64)
      const wrongBytes = JSON.stringify(manifest)
      await writeFile(manifestPath, wrongBytes)
      await assert.rejects(validateCurrentTrackAssociation(spinTrack, spinObservations, fixture),
        /Current live producer input differs: web\/scripts\/compact-source-common\.py/)
      assert.equal(await readFile(manifestPath, 'utf8'), wrongBytes)
    })
  } finally {
    process.env.PATH = originalPath
    await rm(directory, { recursive: true, force: true })
  }
})

function visibilityFixture() {
  const record = recordFixture(), frame = record.frames[0]
  frame.sourceMachineRequirement = 'required'
  frame.views = [structuredClone(original.frames[0].views[0])]
  const view = frame.views[0]
  view.sourceVisibility = {
    kind: 'policy-excluded', reasonCode: 'blurred-navigation-background',
    sourceImage: structuredClone(frame.sourceImage), rectSourcePixels: [...view.rectSourcePixels],
    manualSourceAudit: { method: 'manual-source-pixel-inspection', evidence: 'Synthetic full-ROI annotation control, not a claim that this readable source exposure is blurred.' },
  }
  return record
}

test('current visibility qualification retains the original exact source ROI and chosen candidate without a fidelity claim', async () => {
  const record = visibilityFixture(), before = structuredClone(record)
  await validateCurrentObservations(record, { webRoot })
  assert.deepEqual(record, before)
})

test('current visibility refuses misbound images, partial ROIs, unknown reasons, blank audits and readable physical support', async () => {
  for (const mutate of [
    view => { view.sourceVisibility.sourceImage.frameIndex++ },
    view => { view.sourceVisibility.rectSourcePixels[2]-- },
    view => { view.sourceVisibility.reasonCode = 'unobservable' },
    view => { view.sourceVisibility.manualSourceAudit.evidence = ' \n ' },
    view => { view.sourceVisibility.manualSourceAudit.method = 'candidate-status' },
    view => { view.sourceVisibility.approved = true },
    (view, frame) => { frame.landmarks.push({ viewId: view.id }) },
    view => { view.nativeLineChecks = [{}] },
  ]) {
    const record = visibilityFixture()
    mutate(record.frames[0].views[0], record.frames[0])
    await assert.rejects(validateCurrentObservations(record, { webRoot }), /Source visibility|source-readable/)
  }
})

test('visibility qualification cannot waive actual requested/decoded clock ownership', async () => {
  const record = visibilityFixture()
  record.frames[0].decodedTimeSeconds = 0.501
  await assert.rejects(validateCurrentObservations(record, { webRoot }), /requested\/decoded clock/)
})
