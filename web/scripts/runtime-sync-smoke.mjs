import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile, unlink } from 'node:fs/promises'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const root = fileURLToPath(new URL('..', import.meta.url))
const base = new URL(process.argv[2] ?? 'http://127.0.0.1:5173/harmonic-analyzer/')
const output = join(process.env.HARMONIC_SYNC_DATA ?? join(homedir(), 'data/harmonic-analyzer-sync'), 'runtime-smoke')
const manualPath = join(root, 'sync/videos/8KmVDxkia_w/manual.json')
let previousManual = null
try { previousManual = await readFile(manualPath) } catch (error) { if (error.code !== 'ENOENT') throw error }
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.HARMONIC_CHROME, args: ['--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const errors = []
page.on('pageerror', error => errors.push(error.message))
const samples = []
let modifiedManual = false
try {
  await page.goto(new URL('?video=synthesis', base).href)
  await page.waitForFunction(() => window.harmonicSync?.snapshot().loaded && window.harmonicSync.snapshot().modelState === 'ready', undefined, { timeout: 90000 })
  // A separate inline oracle survives replacement of the shipped rough track.
  const oracle = await page.evaluate(async url => {
    const { createSyncTrack, serializeSyncInput } = await import(url)
    const setup = { counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0, wireFixtureOffsetM: 0, coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0 }
    const segmentInput = { amplitudes: Array(20).fill(0), phases: Array(20).fill(0), gearing: 'small-large', magnification: 4, setup }
    const quality = { medianPx: 0, p90Px: 0, maxPx: 0, status: 'unfitted' }
    const track = createSyncTrack({
      schemaVersion: 1, videoId: 'test', fps: [24, 1], sourceSha256: '', modelSha256: '',
      shots: [
        { id: 'a', start: 0, end: 1, startFrame: 0, endFrame: 24, classification: 'machine', views: [{ viewId: 'crop', rectSourcePixels: [100, 50, 800, 600], presentation: 'horizontal-mirror', quality, cameraKeys: [
          { t: 0, camera: { positionMetres: [0, 0, 0], quaternion: [0, 0, 0, 1], verticalFovDegrees: 35 } },
          { t: 1, camera: { positionMetres: [2, 0, 0], quaternion: [0, 0, Math.SQRT1_2, Math.SQRT1_2], verticalFovDegrees: 45, principalPointViewportPixels: [420, 310] } },
        ] }] },
        { id: 'b', start: 1, end: 2, startFrame: 24, endFrame: 48, classification: 'machine', views: [{ viewId: 'main', rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', quality, cameraKeys: [{ t: 1, camera: { positionMetres: [10, 0, 0], quaternion: [0, 0, 0, 1], verticalFovDegrees: 30 } }] }] },
        { id: 'hold', start: 2, end: 5, startFrame: 48, endFrame: 120, classification: 'non-machine', views: [] },
      ],
      segments: [
        { id: 'first', start: 0, end: 1, input: segmentInput, provenance: {} },
        { id: 'second', start: 1, end: 2, input: { ...segmentInput, amplitudes: Array(20).fill(0.5) }, provenance: {} },
        { id: 'later', start: 2, end: 5, input: { ...segmentInput, amplitudes: Array(20).fill(0.9) }, provenance: {} },
      ],
      crank: [0, 1, 2, 5].map(t => ({ t, turns: t, source: 'tracked' })),
    })
    return [-1, 0.5, 1, 2, 4, 0.99, 1.99].map(t => {
      const frame = track.evaluate(t)
      return { t, views: structuredClone(frame.views), input: serializeSyncInput(frame.input) }
    })
  }, new URL('src/sync-track.ts', base).href)
  assert.equal(oracle[0].views.length, 0)
  assert.equal(oracle[0].input.crankTurns, 0)
  assert.deepEqual(oracle[1].views[0].camera.positionMetres, [1, 0, 0])
  assert.equal(oracle[1].views[0].camera.verticalFovDegrees, 40)
  assert.deepEqual(oracle[1].views[0].camera.principalPointViewportPixels, [410, 305])
  assert.ok(Math.abs(oracle[1].views[0].camera.quaternion[2] - Math.sin(Math.PI / 8)) < 1e-10)
  assert.equal(oracle[1].input.crankTurns, 0.5)
  assert.equal(oracle[1].views[0].presentation, 'horizontal-mirror')
  assert.deepEqual(oracle[2].views[0].camera.positionMetres, [10, 0, 0])
  assert.equal(oracle[2].input.amplitudes[0], 0.5)
  assert.deepEqual(oracle[3], { ...oracle[4], t: 2 })
  assert.equal(oracle[4].input.crankTurns, 47 / 24)
  assert.equal(oracle[4].input.amplitudes[0], 0.5)
  // Nearest-frame selection crosses these cuts before the descriptive second.
  assert.deepEqual(oracle[5].views[0].camera.positionMetres, [10, 0, 0])
  assert.equal(oracle[5].input.amplitudes[0], 0.5)
  assert.deepEqual(oracle[3], { ...oracle[6], t: 2 })
  for (const t of [5, 12, 25]) {
    const sample = await page.evaluate(t => {
      const evaluated = window.harmonicSync.evaluate(t)
      const drawn = window.harmonicSync.drawAt(t)
      return { t, evaluated, drawn }
    }, t)
    assert.equal(sample.drawn.mode, 'following-video')
    assert.equal(sample.drawn.modelTime, t)
    assert.equal(sample.evaluated.input.crankTurns, sample.drawn.input.crankTurns)
    if (sample.evaluated.views.length) {
      const camera = sample.evaluated.views.at(-1).camera
      assert.deepEqual(camera.positionMetres, sample.drawn.camera.positionMetres)
      assert.ok(Math.abs(camera.quaternion.reduce((sum, x, i) => sum + x * sample.drawn.camera.quaternion[i], 0)) > 0.999999)
    }
    samples.push(sample)
    console.error(JSON.stringify({ event: 'runtime-evaluation', ...sample }))
    await page.screenshot({ path: join(output, `runtime-${t}s.png`) })
  }

  await page.goto(new URL('align.html?video=synthesis', base).href)
  await page.waitForFunction(() => window.harmonicAlign?.snapshot().loaded && window.harmonicAlign.snapshot().modelState === 'available' && window.harmonicAlign.snapshot().videoReadyState >= 2, undefined, { timeout: 90000 })
  await page.waitForFunction(() => !document.querySelector('#original').seeking)
  const initial = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.ok(initial.shotId && initial.viewId)
  await assert.doesNotReject(page.locator('#overlay').waitFor({ state: 'visible' }))
  const videoResponse = await page.request.get(new URL('/__sync/video/8KmVDxkia_w.mp4', base).href, { headers: { Range: 'bytes=0-31' } })
  assert.equal(videoResponse.status(), 206)
  assert.equal((await videoResponse.body()).length, 32)
  const width = await page.locator('#overlay').evaluate(canvas => canvas.width)
  assert.ok(width > 0)
  await page.locator('#next-frame').click()
  await page.waitForFunction(t => window.harmonicAlign.snapshot().t > t && !document.querySelector('#original').seeking, initial.t)
  const stepped = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.ok(stepped.t - initial.t < 0.05)
  await page.locator('#fov').fill('36.25')
  await page.locator('#fov').dispatchEvent('input')
  await page.locator('#pp-right').click()
  const authored = await page.evaluate(() => ({ ...window.harmonicAlign.snapshot(), segmentId: document.getElementById('segment-id').value }))
  assert.equal(authored.camera.verticalFovDegrees, 36.25)
  assert.equal(authored.camera.principalPointViewportPixels[0], initial.camera.principalPointViewportPixels[0] + 1)
  for (const id of ['save-camera', 'save-segment', 'save-crank']) {
    modifiedManual = true
    await page.locator(`#${id}`).click()
    await page.waitForFunction(() => document.getElementById('align-status').dataset.state === 'saved')
  }
  const saved = JSON.parse(await readFile(manualPath, 'utf8'))
  const key = saved.cameraKeys.find(key => key.shotId === authored.shotId && key.viewId === authored.viewId && key.t === authored.t)
  assert.deepEqual(key.camera, authored.camera)
  assert.equal(key.provenance, 'manual')
  assert.ok(saved.segments.some(segment => segment.id === authored.segmentId && segment.init.amplitudes.length === 20))
  assert.ok(saved.crank.some(key => key.t === authored.t && key.turns === authored.input.crankTurns))
  // Saving the same identity replaces, rather than appending a duplicate.
  await page.locator('#save-camera').click()
  await page.waitForFunction(() => document.getElementById('align-status').dataset.state === 'saved')
  const reSaved = JSON.parse(await readFile(manualPath, 'utf8'))
  assert.equal(reSaved.cameraKeys.filter(key => key.shotId === authored.shotId && key.viewId === authored.viewId && key.t === authored.t).length, 1)
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Alignment overflow at ${width}px`)
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.screenshot({ path: join(output, 'align-overlay.png') })
  await page.reload()
  await page.waitForFunction(() => window.harmonicAlign?.snapshot().loaded && window.harmonicAlign.snapshot().modelState === 'available', undefined, { timeout: 90000 })
  await page.waitForFunction(() => !document.querySelector('#original').seeking)
  await page.evaluate(t => window.harmonicAlign.seek(t), authored.t)
  await page.locator('#reset-camera').click()
  const roundTrip = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.equal(roundTrip.camera.verticalFovDegrees, authored.camera.verticalFovDegrees)
  assert.deepEqual(roundTrip.camera.principalPointViewportPixels, authored.camera.principalPointViewportPixels)
  assert.ok(Math.abs(authored.camera.quaternion.reduce((sum, x, i) => sum + x * roundTrip.camera.quaternion[i], 0)) > 0.999999)
  const proposalUrl = new URL('/__sync/proposals/8KmVDxkia_w', base).href
  const proposalResponse = await page.request.get(proposalUrl)
  assert.equal(proposalResponse.status(), 200)
  const actualProposals = await proposalResponse.json()
  assert.ok(Array.isArray(actualProposals.cameras))
  assert.equal((await page.request.head(proposalUrl)).status(), 200)
  const census = JSON.parse(await readFile(join(root, 'sync/videos/8KmVDxkia_w/shots.json'), 'utf8'))
  const fps = census.fps[0] / census.fps[1]
  const entries = census.shots.filter(shot => shot.classification === 'machine' || shot.classification === 'transition')
    .flatMap(shot => shot.views.map(view => ({ shotId: shot.id, viewId: view.viewId, frame: Math.floor((shot.startFrame + shot.endFrame - 1) / 2), rect: view.rectSourcePixels })))
    .sort((a, b) => a.frame - b.frame)
  assert.ok(entries.length >= 2)
  const first = entries[0]
  const proposedCamera = { ...authored.camera, positionMetres: [authored.camera.positionMetres[0] + 0.05, ...authored.camera.positionMetres.slice(1)], verticalFovDegrees: 38.5, principalPointViewportPixels: [first.rect[2] / 2 + 7, first.rect[3] / 2 - 3] }
  // Only the browser's proposal GET is replaced. Real POST/manual endpoints and
  // original video remain exercised; generated proposal files are never edited.
  const proposalFixture = { cameras: [{ shotId: first.shotId, viewId: first.viewId, frame: first.frame, camera: proposedCamera, iou: 0, s2rPx: 0, r2sPx: 0, pnpInliers: 0, pnpInlierFraction: 0 }] }
  await page.route('**/__sync/proposals/8KmVDxkia_w', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(proposalFixture) }))
  await page.locator('#review-mode').click()
  await page.waitForFunction(() => window.harmonicAlign.snapshot().review.enabled && !window.harmonicAlign.snapshot().review.busy)
  const proposed = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.equal(proposed.review.total, entries.length)
  assert.equal(proposed.review.frame, first.frame)
  assert.equal(Math.round(proposed.t * fps), first.frame)
  assert.equal(proposed.review.seedSource, 'proposal')
  assert.deepEqual(proposed.camera.positionMetres, proposedCamera.positionMetres)
  assert.equal(proposed.camera.verticalFovDegrees, proposedCamera.verticalFovDegrees)
  assert.deepEqual(proposed.camera.principalPointViewportPixels, proposedCamera.principalPointViewportPixels)
  assert.equal(await page.locator('#review-list button').count(), entries.length)
  const beforeAccept = JSON.parse(await readFile(manualPath, 'utf8'))
  const wasReviewed = beforeAccept.cameraKeys.some(key => key.shotId === first.shotId && key.viewId === first.viewId)
  const expectedAfterAccept = entries.map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => !(entry.shotId === first.shotId && entry.viewId === first.viewId) && !beforeAccept.cameraKeys.some(key => key.shotId === entry.shotId && key.viewId === entry.viewId))
    .map(({ index }) => index)
  const acceptedIndex = expectedAfterAccept.find(index => index > 0) ?? expectedAfterAccept[0] ?? 0
  await page.keyboard.press('a')
  await page.waitForFunction(index => !window.harmonicAlign.snapshot().review.busy && window.harmonicAlign.snapshot().review.index === index, acceptedIndex)
  const acceptedManual = JSON.parse(await readFile(manualPath, 'utf8'))
  const acceptedKey = acceptedManual.cameraKeys.find(key => key.shotId === first.shotId && key.viewId === first.viewId && key.t === first.frame * census.fps[1] / census.fps[0])
  assert.equal(acceptedKey.provenance, 'proposal-accepted')
  assert.deepEqual(acceptedKey.camera.positionMetres, proposedCamera.positionMetres)
  assert.equal(acceptedKey.camera.verticalFovDegrees, 38.5)
  const accepted = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.equal(accepted.review.reviewed, proposed.review.reviewed + (wasReviewed ? 0 : 1))
  assert.equal(await page.locator('#review-count').textContent(), `${accepted.review.reviewed} of ${entries.length} reviewed`)
  assert.equal(await page.locator('#review-list button').nth(0).getAttribute('data-reviewed'), 'true')
  await page.locator('#camera-review summary').click()
  await page.locator('#review-list button').nth(0).click()
  await page.waitForFunction(() => window.harmonicAlign.snapshot().review.index === 0 && !window.harmonicAlign.snapshot().review.busy)
  const manualBeforeNavigation = await readFile(manualPath)
  await page.keyboard.press('n')
  await page.waitForFunction(() => window.harmonicAlign.snapshot().review.index === 1 && !window.harmonicAlign.snapshot().review.busy)
  const next = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.equal(next.shotId, entries[1].shotId)
  assert.equal(next.viewId, entries[1].viewId)
  assert.ok(next.review.seedSource.startsWith('accepted camera from '))
  const preceding = acceptedManual.cameraKeys.filter(key => Math.round(key.t * fps) <= entries[1].frame).sort((a, b) => b.t - a.t)[0]
    ?? acceptedManual.cameraKeys.toSorted((a, b) => Math.abs(Math.round(a.t * fps) - entries[1].frame) - Math.abs(Math.round(b.t * fps) - entries[1].frame))[0]
  assert.equal(next.camera.verticalFovDegrees, preceding.camera.verticalFovDegrees)
  assert.deepEqual(await readFile(manualPath), manualBeforeNavigation)
  await page.keyboard.press('p')
  await page.waitForFunction(() => window.harmonicAlign.snapshot().review.index === 0 && !window.harmonicAlign.snapshot().review.busy)
  assert.deepEqual(await readFile(manualPath), manualBeforeNavigation)
  await page.keyboard.press('n')
  await page.waitForFunction(() => window.harmonicAlign.snapshot().review.index === 1 && !window.harmonicAlign.snapshot().review.busy)
  await page.locator('#fov').fill('39.25')
  await page.locator('#fov').dispatchEvent('input')
  await page.locator('#overlay').focus()
  await page.keyboard.press('c')
  await page.waitForFunction(() => !window.harmonicAlign.snapshot().review.busy && document.getElementById('align-status').dataset.state === 'saved')
  const adjusted = await page.evaluate(() => window.harmonicAlign.snapshot())
  assert.equal(adjusted.review.index, 1)
  const adjustedManual = JSON.parse(await readFile(manualPath, 'utf8'))
  const adjustedKey = adjustedManual.cameraKeys.find(key => key.shotId === entries[1].shotId && key.viewId === entries[1].viewId && key.t === entries[1].frame * census.fps[1] / census.fps[0])
  assert.equal(adjustedKey.provenance, 'manual')
  assert.equal(adjustedKey.camera.verticalFovDegrees, 39.25)
  const remaining = entries.map((entry, index) => ({ entry, index })).filter(({ entry }) => !adjustedManual.cameraKeys.some(key => key.shotId === entry.shotId && key.viewId === entry.viewId)).map(({ index }) => index)
  const shiftedIndex = remaining.find(index => index > 1) ?? remaining[0] ?? 1
  await page.keyboard.press('Shift+C')
  await page.waitForFunction(index => !window.harmonicAlign.snapshot().review.busy && window.harmonicAlign.snapshot().review.index === index, shiftedIndex)
  const shifted = await page.evaluate(() => window.harmonicAlign.snapshot())
  const shiftedManual = JSON.parse(await readFile(manualPath, 'utf8'))
  assert.equal(shiftedManual.cameraKeys.filter(key => key.shotId === entries[1].shotId && key.viewId === entries[1].viewId && key.t === adjustedKey.t).length, 1)
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Review queue overflow at ${width}px`)
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.locator('.align-panel').evaluate(panel => { panel.scrollTop = 0 })
  await page.screenshot({ path: join(output, 'review-queue.png') })
  assert.deepEqual(errors, [])
  await writeFile(join(output, 'evaluations.json'), JSON.stringify({ oracle, samples, alignment: { authored, roundTrip }, review: { proposalEndpointCameraCount: actualProposals.cameras.length, proposalFixture, proposed, acceptedKey, accepted, next, adjustedKey, adjusted, shifted }, errors }, null, 2) + '\n')
  console.error(`PASS: runtime oracle + three evaluations, original overlay/seek, manual save/reload, review proposal acceptance + next-unreviewed, N/P without saves, C stays, Shift+C advances; ${output}`)
} catch (error) {
  const state = await page.evaluate(() => ({ alignment: window.harmonicAlign?.snapshot(), status: document.getElementById('align-status')?.textContent })).catch(() => null)
  await writeFile(join(output, 'failure.json'), JSON.stringify({ error: String(error), state, errors }, null, 2) + '\n')
  throw error
} finally {
  await browser.close()
  if (modifiedManual) {
    if (previousManual) { await mkdir(dirname(manualPath), { recursive: true }); await writeFile(manualPath, previousManual) }
    else await unlink(manualPath).catch(error => { if (error.code !== 'ENOENT') throw error })
  }
}
