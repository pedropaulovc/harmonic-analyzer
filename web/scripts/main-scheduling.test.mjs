import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import ts from 'typescript'

// Execute the production functions, isolating DOM/WebGL side effects. No source
// text assertions: counters below represent publication, solve/draw and DOM work.
const filename = new URL('../src/main.ts', import.meta.url)
const source = await readFile(filename, 'utf8')
const ast = ts.createSourceFile(filename.pathname, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
function productionFunctions(names) {
  const selected = ast.statements.filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name?.text))
  assert.equal(selected.length, names.length)
  return ts.transpileModule(selected.map(node => node.getText(ast)).join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText
}
const scheduling = productionFunctions(['renderFollowingSource', 'renderSource', 'tick'])
const hud = productionFunctions(['setControlValue', 'updateHud'])

function fixture() {
  const counts = { prepare: 0, commit: 0, draw: 0, solve: 0, pending: 0, controls: 0, raf: 0 }
  const view = { id: 'main', input: { crankTurns: 1 }, sourceLayout: [] }
  let sample = { state: 'approximate', timeSeconds: 4, views: [view] }
  const publication = {
    prepareAt(time) { counts.prepare++; sample.timeSeconds = time; return sample },
    commitPrepared() { counts.commit++; return sample },
    approximationMessage: 'Chosen inputs, not recovered history',
  }
  const context = vm.createContext({
    reference: publication, machine: { availability: 'available' }, player: { getTime: () => 4, getState: () => 'buffering' },
    mode: 'following-video', referenceState: 'approximate', physicsState: 'available', paintRevision: 'pending',
    activeViews: [], sourceDrawRevision: 0, modelTime: 0, sourceSampleTimeSeconds: 0,
    followingPollReference: null, followingPollMachine: null, followingPollTime: NaN,
    followingPollExposureTime: NaN, followingPollPresentedFrame: -1, followingPollSeekState: '', followingPollDrawRevision: -1,
    nativeDiagnosticLeaseActive: false, nativeDiagnosticRefusal: null,
    lastTick: 0, lastHud: 0, manualSourceSeek: 'idle', manualMotion: 'idle', manualRevision: 'clean', manualSceneOwnership: 'owned',
    referenceSeek: 'idle', input: { crankTurns: 0 }, speed: { value: '2' }, manualRunButton: {}, physicsError: {}, sourceError: {},
    requestAnimationFrame() { counts.raf++ }, initializeColdHeldOriginalSource() {}, retryFollowing() {},
    isSourceVideoPlayer: player => Boolean(player.native), originalPresentedSampleTime: presented => presented.sampleTime,
    configureLandmarkProbe() {}, validateSourceViews() {}, copyInput() {}, primaryView: () => view,
    viewer: { preflightViews() {}, controls: { enableDamping: false, autoRotate: false, update() { counts.controls++ } } },
    updateMachine() { counts.solve++; context.paintRevision = 'pending' },
    drawSourceViews() { counts.draw++; counts.solve++; context.sourceDrawRevision++ },
    renderPending() { if (context.paintRevision === 'pending') { counts.pending++; context.paintRevision = 'clean' } },
    notice(target, message) { target.textContent = message }, updateHud() {}, ViewCapacityError: class extends Error {},
  })
  vm.runInContext(scheduling, context)
  return { context, counts, publication, unavailable() { sample = { state: 'unavailable', timeSeconds: 4, views: [], reason: 'No source pose' } } }
}

test('unchanged following time does not republish, solve or redraw; real time changes do', () => {
  const { context: c, counts } = fixture()
  c.tick(16)
  for (let frame = 2; frame < 20; frame++) c.tick(frame * 16)
  assert.deepEqual([counts.prepare, counts.commit, counts.solve, counts.draw], [1, 1, 1, 1])
  c.player.getTime = () => 4.1
  c.tick(320)
  assert.deepEqual([counts.prepare, counts.commit, counts.solve, counts.draw], [2, 2, 2, 2])
  assert.equal(c.modelTime, 4.1)
})

test('resize/control invalidation redraws at unchanged source time', () => {
  const { context: c, counts } = fixture()
  c.tick(16)
  c.paintRevision = 'pending'
  c.tick(32)
  assert.equal(counts.draw, 2)
  assert.equal(c.paintRevision, 'clean')
})

test('new reference, model and explicit publications invalidate the following poll', () => {
  const { context: c, counts, publication } = fixture()
  c.tick(16)
  c.reference = { ...publication }
  c.tick(32)
  c.machine = { availability: 'available' }
  c.tick(48)
  c.renderSource(4)
  c.tick(64)
  assert.equal(counts.prepare, 5)
  assert.equal(counts.draw, 5)
})

test('native exposure identity and seek state cannot be hidden by an unchanged media clock', () => {
  const { context: c, counts } = fixture()
  let presented = { frameIndex: 1, sampleTime: 4 }
  let seekState = 'idle'
  c.player = { native: true, getTime: () => 4, getState: () => 'buffering', getSeekState: () => seekState, getPresentation: () => presented }
  c.tick(16)
  c.tick(32)
  presented = { frameIndex: 2, sampleTime: 4 }
  c.tick(48)
  presented = { frameIndex: 2, sampleTime: 4.02 }
  c.tick(64)
  seekState = 'seeking'
  c.tick(80)
  assert.equal(counts.prepare, 4)
  presented = null
  seekState = 'idle'
  assert.throws(() => c.renderFollowingSource(4), /no current owned presented exposure/)
})

test('unavailable source or mechanical state is never considered an accepted cached draw', () => {
  const { context: c, counts, unavailable } = fixture()
  unavailable()
  c.tick(16)
  c.tick(32)
  assert.equal(counts.prepare, 2)
  assert.equal(counts.draw, 0)
  c.referenceState = 'approximate'
  c.physicsState = 'unavailable'
  c.tick(48)
  assert.equal(counts.prepare, 3)
})

test('manual crank remains delta-driven and solves/renders each changed input; idle stays clean', () => {
  const { context: c, counts } = fixture()
  c.mode = 'exploring'
  c.manualMotion = 'turning'
  c.tick(100)
  c.tick(200)
  assert.equal(c.input.crankTurns, 0.4)
  assert.equal(counts.solve, 2)
  assert.equal(counts.pending, 2)
  assert.equal(counts.prepare, 0)
  c.manualMotion = 'idle'
  c.tick(300)
  assert.equal(counts.solve, 2)
  assert.equal(counts.pending, 2)
  c.viewer.controls.enableDamping = true
  c.tick(400)
  assert.equal(counts.controls, 1)
})

test('diagnostic lease and native review preroll retain scheduling ownership', () => {
  const { context: c, counts } = fixture()
  c.nativeDiagnosticLeaseActive = true
  c.tick(16)
  assert.equal(counts.prepare, 0)
  c.nativeDiagnosticLeaseActive = false
  c.mode = 'reference-review'
  c.referenceSeek = 'preroll'
  c.tick(32)
  assert.equal(counts.draw, 0)
  assert.equal(counts.pending, 0)
})

function hudFixture() {
  let writes = 0
  function control() {
    let value = '', title = '', text = ''
    return {
      dataset: new Proxy({}, { set(object, key, next) { writes++; object[key] = next; return true } }),
      get value() { return value }, set value(next) { writes++; value = next },
      get title() { return title }, set title(next) { writes++; title = next },
      get textContent() { return text }, set textContent(next) { writes++; text = next },
    }
  }
  const names = ['sourceScrub', 'sourceScrubTime', 'crank', 'crankValue', 'gearing', 'magnification', 'fixture', 'cone', 'pinion', 'platen', 'magnificationValue', 'fixtureValue', 'coneValue', 'pinionValue', 'platenValue', 'forceReadout', 'playbackStatus', 'playbackClock']
  const c = vm.createContext({
    controlValueCache: new WeakMap(),
    ...Object.fromEntries(names.map(name => [name, control()])),
    player: { getTime: () => 4 }, isSourceVideoPlayer: () => true, manualSourceSeek: 'idle', document: { activeElement: null },
    mode: 'exploring', explorationOrigin: 'interactive-default', referenceSeek: 'idle', referenceState: 'approximate',
    reference: null, playbackState: 'paused', stateLabels: { paused: 'Paused' }, modelState: 'ready', physicsState: 'available',
    machine: { availability: 'available', pose: { springForcesN: [1, 2], equilibriumResidualNm: 0.001, platenTravelM: 0.01 } },
    input: { crankTurns: 1, gearing: 'direct', magnification: 1, setup: { wireFixtureOffsetM: 0, coneSwingRad: 0, pinionCamRad: 0, platenOffsetM: 0 }, amplitudes: [0.1], phases: [0] },
    channelInputs: [{ amplitude: control(), phase: control(), value: control() }],
    MECHANISM_DATA: { channel: { maximumStationMm: 10 } }, primaryView: () => undefined, lastContributingView: () => undefined,
  })
  vm.runInContext(hud, c)
  return { context: c, writes: () => writes }
}

test('unchanged HUD performs no DOM writes and changed manual input is synchronized', () => {
  const { context: c, writes } = hudFixture()
  c.updateHud()
  const firstWrites = writes()
  assert.ok(firstWrites > 0)
  c.updateHud()
  assert.equal(writes(), firstWrites)
  c.input.crankTurns = 2
  c.updateHud()
  assert.equal(c.crank.value, '2')
  assert.equal(c.crankValue.value, '2.000 turns')
  assert.equal(writes(), firstWrites + 2)
})

test('HUD preserves superseding controls and focused scrub, while provenance transitions remain visible', () => {
  const { context: c } = hudFixture()
  c.updateHud()
  c.crank.value = '99'
  c.sourceScrub.value = '9'
  c.document.activeElement = c.sourceScrub
  c.mode = 'following-video'
  c.primaryView = () => ({ unobservedInputFields: ['crankTurns'] })
  c.updateHud('preserve')
  assert.equal(c.crank.value, '99')
  assert.equal(c.sourceScrub.value, '9')
  assert.equal(c.crank.dataset.provenance, 'chosen')
  c.document.activeElement = null
  c.updateHud()
  assert.equal(c.sourceScrub.value, '4')
  assert.match(c.crankValue.value, /chosen, not measured/)
})

test('sanitized range values do not repeat writes, but external edits are restored', () => {
  const c = vm.createContext({ controlValueCache: new WeakMap() })
  vm.runInContext(productionFunctions(['setControlValue']), c)
  let writes = 0
  let observed = '0'
  const range = {
    get value() { return observed },
    set value(raw) {
      writes++
      // The range value sanitization algorithm clamps to bounds, then rounds to
      // the nearest permitted step (here min=0, max=90, step=0.1).
      const numeric = Math.max(0, Math.min(90, Number(raw)))
      observed = String(Math.round(numeric * 10) / 10)
    },
  }
  c.setControlValue(range, '30.000000000004')
  assert.equal(range.value, '30')
  assert.equal(writes, 1)
  c.setControlValue(range, '30.000000000004')
  assert.equal(writes, 1, 'same raw model value and sanitized DOM result require no assignment')
  range.value = '40'
  c.setControlValue(range, '30.000000000004')
  assert.equal(range.value, '30')
  assert.equal(writes, 3, 'superseding user/diagnostic edits are not mistaken for the cached DOM result')
  c.setControlValue(range, '30.000000000005')
  assert.equal(writes, 4, 'changed raw model input is submitted even when it has the same stepped result')
  c.setControlValue(range, '120')
  assert.equal(range.value, '90')
  c.setControlValue(range, '120')
  assert.equal(writes, 5, 'clamped values are also stable')
})
