import { createViewer, loadMachine, type Machine } from './scene'
import { CHAPTERS, type Chapter } from './narration'
import { output } from './kinematics'

const canvas = document.querySelector<HTMLCanvasElement>('#stage')!
const trace = document.querySelector<HTMLCanvasElement>('#trace')!
const loading = document.querySelector<HTMLElement>('#loading')!
const panel = document.querySelector<HTMLElement>('#panel')!
const title = document.querySelector<HTMLElement>('#chapter-title')!
const bodyEl = document.querySelector<HTMLElement>('#chapter-body')!
const chapters = document.querySelector<HTMLElement>('#chapters')!
const crank = document.querySelector<HTMLInputElement>('#crank')!
const readout = document.querySelector<HTMLOutputElement>('#readout')!
const play = document.querySelector<HTMLButtonElement>('#play')!

const viewer = createViewer(canvas)
let machine: Machine | null = null
let current: Chapter = CHAPTERS[0]!
let turns = 0
let running = false

/** Every chapter is reachable — otherwise narration.ts is unreachable data. */
function buildChapterNav() {
  for (const c of CHAPTERS) {
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'chapter-tab'
    b.textContent = c.title
    b.dataset.id = c.id
    b.addEventListener('click', () => showChapter(c))
    chapters.append(b)
  }
}

function showChapter(c: Chapter) {
  current = c
  title.textContent = c.title
  bodyEl.textContent = c.body
  crank.min = String(c.turns[0])
  crank.max = String(c.turns[1])
  turns = c.turns[0]
  crank.value = String(turns)
  running = false
  play.textContent = 'Play'
  for (const tab of chapters.querySelectorAll<HTMLButtonElement>('.chapter-tab')) {
    tab.setAttribute('aria-current', String(tab.dataset.id === c.id))
  }
  clearTrace()
}

function clearTrace() {
  const ctx = trace.getContext('2d')
  if (ctx) ctx.clearRect(0, 0, trace.width, trace.height)
}

/** Draw the pen's output the way the platen does: time left to right. */
function drawTrace() {
  const ctx = trace.getContext('2d')
  if (!ctx) return
  const { width: w, height: h } = trace
  ctx.clearRect(0, 0, w, h)
  ctx.strokeStyle = '#e8b04b'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  const [from, to] = current.turns
  const span = to - from || 1
  for (let px = 0; px <= w; px++) {
    const t = from + (px / w) * span
    if (t > turns) break
    const y = h / 2 - (output(t, current.amplitudes) / 20) * (h / 2) * 0.9
    px === 0 ? ctx.moveTo(px, y) : ctx.lineTo(px, y)
  }
  ctx.stroke()
}

function tick() {
  requestAnimationFrame(tick)
  if (running) {
    const [, to] = current.turns
    turns = Math.min(to, turns + 0.02)
    crank.value = String(turns)
    if (turns >= to) running = false, (play.textContent = 'Play')
  }
  machine?.update(turns, current.amplitudes)
  readout.textContent = `crank ${turns.toFixed(2)} turns · output ${output(turns, current.amplitudes).toFixed(2)}`
  drawTrace()
  viewer.controls.update()
  viewer.renderer.render(viewer.scene, viewer.camera)
}

crank.addEventListener('input', () => {
  turns = Number(crank.value)
  running = false
  play.textContent = 'Play'
})

play.addEventListener('click', () => {
  running = !running
  play.textContent = running ? 'Pause' : 'Play'
})

async function start() {
  viewer.resize()
  trace.width = trace.clientWidth
  trace.height = trace.clientHeight
  buildChapterNav()
  showChapter(current)
  tick()
  try {
    machine = await loadMachine(viewer.scene)
    loading.hidden = true
    panel.hidden = false
  } catch (err) {
    // No GLB yet is the normal state of a fresh checkout, not a crash: the
    // model is a build artefact. Say what to run.
    loading.innerHTML =
      '<p>No model loaded.</p><p class="hint">Run <code>doit export</code> on the ' +
      'SolidWorks seat, then <code>npm run fetch-model</code>.</p>'
    panel.hidden = false
    console.warn('[machine] model not loaded:', err)
  }
}

void start()
