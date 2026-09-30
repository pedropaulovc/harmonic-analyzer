import { Quaternion } from 'three'
import { createMechanismInput, MECHANISM_DATA, type MechanismInput } from './mechanics'
import type { CameraRecord, PartOverride, SourceView } from './scene'
import type { Video } from './video-catalog'

export const SOURCE_WIDTH = 1920
export const SOURCE_HEIGHT = 1080
export const LANDMARK_LIMIT_PX = SOURCE_WIDTH * 0.02
/**
 * matched: a required source frame with a passing camera and complete measured input per view.
 * held: an exempt source frame showing an actual earlier matched pose.
 * no-machine: an exempt source frame with no earlier matched pose; no source pose is asserted.
 * unavailable: required but incompletely measured, or outside the observation record.
 */
export type ReferenceState = 'matched' | 'held' | 'no-machine' | 'unavailable'
export type Classification = 'machine' | 'non-machine' | 'transition' | 'unobservable'
export interface ReferenceAnchor {
  id: string
  kind: 'section-center' | 'physical-feature'
  partPath?: string
  partLocalMetres?: [number, number, number]
  worldMetres?: [number, number, number]
  description: string
  correspondenceEvidence: string
}
export interface Landmark {
  anchorId: string
  viewId?: string
  role: 'fit' | 'check'
  pixel: [number, number]
  status: 'observed'
  method: 'manual' | 'optical-flow' | 'image-edge'
  uncertaintyPx: number
}
export interface ObservedCamera extends CameraRecord {
  fitRmsPx: number
  heldOutMaxPx: number
  status: 'passed' | 'failed'
}
export interface SerializedInput {
  crankTurns: number
  amplitudes: number[]
  phases: number[]
  gearing: MechanismInput['gearing']
  magnification: number
  setup: MechanismInput['setup']
}
export interface MechanicalObservation {
  status: 'observed' | 'unobservable' | 'not-applicable'
  visiblePoseCompleteness?: 'complete' | 'partial'
  evidence: string
  input: SerializedInput | null
}
export interface ObservedView {
  id: string
  rectSourcePixels: [number, number, number, number]
  presentation: 'native' | 'horizontal-mirror'
  camera: ObservedCamera | null
  mechanicalState: MechanicalObservation
  partOverrides?: PartOverride[]
}
export interface ReferenceFrame {
  timeSeconds: number
  decodedTimeSeconds: number
  shotId: string
  classification: Classification
  landmarks: Landmark[]
  unavailable: { anchorId: string; reason: string }[]
  mechanicalState: MechanicalObservation
  camera: ObservedCamera | null
  views?: ObservedView[]
}
export interface ReferenceFile {
  schemaVersion: 1
  source: { videoId: string; sha256: string; width: number; height: number; durationSeconds: number; fps: number }
  model: { sha256: string; sourceCommit: string; units: 'metres'; axes: string }
  anchors: ReferenceAnchor[]
  shots: { id: string; startSeconds: number; endSeconds: number; classification: Classification; hasCorrespondingMachine?: boolean; reason: string }[]
  frames: ReferenceFrame[]
  coverage: { status: 'complete' | 'blocked'; blockers: (string | { reason: string; intervalSeconds?: [number, number] })[]; requiredEveryIntegerSecond: true }
}
interface CompiledView {
  observation: ObservedView
  input: MechanismInput | null
}
interface CompiledFrame {
  reference: ReferenceFrame
  requirement: 'required' | 'not-required'
  views: CompiledView[]
  /** Required frame whose every view has a passing camera and complete measured input. */
  matched: boolean
  /** Operator-facing reason for every non-matched outcome of this frame. */
  reason: string
  /** Latest required frame at or before this one, or -1; exempt frames hold it only if matched. */
  heldFrom: number
}
interface PlaybackCamera extends CameraRecord {
  positionMetres: [number, number, number]
  quaternion: [number, number, number, number]
  principalPointViewportPixels: [number, number]
}
export interface PlaybackView extends SourceView {
  id: string
  camera: PlaybackCamera
  rectSourcePixels: [number, number, number, number]
  input: MechanismInput
  partOverrides: readonly PartOverride[]
}
export interface SourceSample {
  state: ReferenceState
  timeSeconds: number
  reason: string
  views: PlaybackView[]
}

const files = import.meta.glob('../content/*.observations.json', { import: 'default' })
const classifications: Record<Classification, true> = { machine: true, 'non-machine': true, transition: true, unobservable: true }
const setupKeys: readonly (keyof MechanismInput['setup'])[] = [
  'counterHeightM', 'meanLineAngleRad', 'platenOffsetM', 'wireFixtureOffsetM',
  'coneSwingRad', 'pinionCamRad', 'heldChannelTurns', 'driveCrankOffsetTurns',
]
const noOverrides: readonly PartOverride[] = []
const qa = new Quaternion()
const qb = new Quaternion()
const qi = new Quaternion()

function finite(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label} must be finite.`)
  return value
}

function requireCamera(camera: ObservedCamera, label: string): void {
  if (camera.positionMetres?.length !== 3 || camera.quaternion?.length !== 4) throw new Error(`${label}: invalid camera dimensions.`)
  camera.positionMetres.forEach((value) => finite(value, label))
  camera.quaternion.forEach((value) => finite(value, label))
  if (camera.principalPointViewportPixels) {
    if (camera.principalPointViewportPixels.length !== 2) throw new Error(`${label}: invalid principal point.`)
    camera.principalPointViewportPixels.forEach((value) => finite(value, label))
  }
  const norm = Math.hypot(...camera.quaternion)
  if (Math.abs(norm - 1) > 0.002) throw new Error(`${label}: camera quaternion is not normalized.`)
  const fov = finite(camera.verticalFovDegrees, label)
  if (fov <= 0 || fov >= 179) throw new Error(`${label}: invalid field of view.`)
  finite(camera.fitRmsPx, label)
  finite(camera.heldOutMaxPx, label)
}

function compileInput(raw: SerializedInput, label: string): MechanismInput {
  if (raw.amplitudes?.length !== 20 || raw.phases?.length !== 20) throw new Error(`${label}: exactly twenty physical stations are required.`)
  const input = createMechanismInput()
  input.crankTurns = finite(raw.crankTurns, label)
  raw.amplitudes.forEach((value, i) => {
    finite(value, label)
    if (value < -1 || value > 1) throw new Error(`${label}: amplitude outside [-1,1].`)
    input.amplitudes[i] = value
  })
  raw.phases.forEach((value, i) => { input.phases[i] = finite(value, label) })
  if (!['small-large', 'medium-medium', 'large-small'].includes(raw.gearing)) throw new Error(`${label}: unknown gearing.`)
  input.gearing = raw.gearing
  input.magnification = finite(raw.magnification, label)
  if (!raw.setup || typeof raw.setup !== 'object') throw new Error(`${label}: missing physical setup.`)
  for (const key of setupKeys) {
    const value = raw.setup[key]
    if (key === 'counterHeightM' && value === null) { input.setup.counterHeightM = null; continue }
    // Older measurements cannot silently invent a newly required setup coordinate.
    input.setup[key] = finite(value, `${label}.${key}`)
  }
  return input
}

function copyInput(target: MechanismInput, source: MechanismInput): void {
  target.crankTurns = source.crankTurns
  target.amplitudes.set(source.amplitudes)
  target.phases.set(source.phases)
  target.gearing = source.gearing
  target.magnification = source.magnification
  Object.assign(target.setup, source.setup)
}

function blendInput(target: MechanismInput, a: MechanismInput, b: MechanismInput, mix: number): void {
  copyInput(target, a)
  target.crankTurns += (b.crankTurns - a.crankTurns) * mix
  target.magnification += (b.magnification - a.magnification) * mix
  for (let i = 0; i < 20; i++) {
    target.amplitudes[i] = a.amplitudes[i]! + (b.amplitudes[i]! - a.amplitudes[i]!) * mix
    target.phases[i] = a.phases[i]! + (b.phases[i]! - a.phases[i]!) * mix
  }
  for (const key of setupKeys) {
    const from = a.setup[key]
    const to = b.setup[key]
    if (from !== null && to !== null) target.setup[key] = from + (to - from) * mix
  }
}

/**
 * Physical matching is required unless the shot census explicitly exempts it. Classification
 * alone never exempts a shot declared to contain the mechanism (transitions, photographs).
 * Must agree with sourceNeedsMachine in scripts/verify-reference.mjs.
 */
function requiresMachine(classification: Classification, hasCorrespondingMachine: boolean | undefined): boolean {
  if (classification === 'machine') return true
  if (classification === 'non-machine') return hasCorrespondingMachine === true
  return hasCorrespondingMachine !== false
}

function viewMatchable(view: CompiledView): boolean {
  const { camera, mechanicalState } = view.observation
  return camera !== null && camera.status === 'passed' && camera.heldOutMaxPx <= LANDMARK_LIMIT_PX
    && view.input !== null && mechanicalState?.status === 'observed' && mechanicalState.visiblePoseCompleteness !== 'partial'
}

function newPlaybackView(view: CompiledView): PlaybackView {
  const camera = view.observation.camera!
  return {
    id: view.observation.id,
    rectSourcePixels: [...view.observation.rectSourcePixels],
    presentation: view.observation.presentation,
    camera: {
      positionMetres: [...camera.positionMetres], quaternion: [...camera.quaternion],
      verticalFovDegrees: camera.verticalFovDegrees,
      principalPointViewportPixels: camera.principalPointViewportPixels ? [...camera.principalPointViewportPixels] : [view.observation.rectSourcePixels[2] / 2, view.observation.rectSourcePixels[3] / 2],
    },
    input: createMechanismInput(),
    partOverrides: view.observation.partOverrides ?? noOverrides,
  }
}

/** Measured reference samples are consumed identically by playback and frame review. */
export class VideoReference {
  readonly data: ReferenceFile
  readonly coverageMessage: string
  private readonly frames: CompiledFrame[]
  private readonly sample: SourceSample = { state: 'unavailable', timeSeconds: 0, reason: '', views: [] }
  private readonly pools = new Map<string, PlaybackView>()

  constructor(data: ReferenceFile, video: Video) {
    if (data.schemaVersion !== 1 || data.source?.videoId !== video.id || data.source.sha256 !== video.sourceSha256) throw new Error('Reference footage identity does not match this video.')
    if (data.source.width !== SOURCE_WIDTH || data.source.height !== SOURCE_HEIGHT || Math.abs(data.source.durationSeconds - video.durationSeconds) > 0.05) throw new Error('Reference dimensions or duration do not match the decoded footage.')
    if (data.model?.sha256 !== MECHANISM_DATA.provenance.modelSha256 || data.model.sourceCommit !== MECHANISM_DATA.provenance.sourceCommit || data.model.units !== 'metres') throw new Error('Reference measurements target a different CAD export.')
    if (!Array.isArray(data.frames) || data.frames.length === 0 || !Array.isArray(data.anchors) || !Array.isArray(data.shots)) throw new Error('No measured reference frames are available.')
    if (!data.coverage || !['complete', 'blocked'].includes(data.coverage.status) || !Array.isArray(data.coverage.blockers)) throw new Error('Missing source-coverage evidence.')
    this.data = data
    this.coverageMessage = data.coverage.blockers.map((blocker) => typeof blocker === 'string' ? blocker : blocker.reason).join(' ')
    let previous = -Infinity
    const shotsById = new Map(data.shots.map((shot) => [shot.id, shot]))
    const frames: CompiledFrame[] = []
    data.frames.forEach((reference, index) => {
      const t = finite(reference.timeSeconds, 'Reference time')
      finite(reference.decodedTimeSeconds, 'Decoded reference time')
      if (t <= previous || t < 0 || t > video.durationSeconds + 0.05) throw new Error('Reference timestamps must be strictly increasing within the source duration.')
      previous = t
      if (!classifications[reference.classification]) throw new Error(`Unknown source classification at ${t}s.`)
      const shot = shotsById.get(reference.shotId)
      if (!shot) throw new Error(`Unknown source shot at ${t}s.`)
      const requirement = requiresMachine(reference.classification, shot.hasCorrespondingMachine) ? 'required' : 'not-required'
      const observations = reference.views ?? [{
        id: 'main', rectSourcePixels: [0, 0, SOURCE_WIDTH, SOURCE_HEIGHT] as [number, number, number, number],
        presentation: 'native' as const, camera: reference.camera, mechanicalState: reference.mechanicalState,
      }]
      const views = observations.map((observation) => {
        if (observation.camera) requireCamera(observation.camera, `${video.id}@${t}s/${observation.id}`)
        if (observation.rectSourcePixels?.length !== 4) throw new Error(`Invalid source viewport at ${t}s.`)
        observation.rectSourcePixels.forEach((value) => finite(value, 'Source viewport'))
        const [x, y, w, h] = observation.rectSourcePixels
        if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > SOURCE_WIDTH || y + h > SOURCE_HEIGHT) throw new Error(`Source viewport exceeds the frame at ${t}s.`)
        if (!['native', 'horizontal-mirror'].includes(observation.presentation)) throw new Error('Unknown source presentation.')
        const raw = observation.mechanicalState?.input
        return { observation, input: raw ? compileInput(raw, `${video.id}@${t}s`) : null }
      })
      const failed = views.find((view) => !viewMatchable(view))
      const matched = requirement === 'required' && views.length > 0 && !failed
      if (matched) {
        for (const view of views) {
          if (!this.pools.has(view.observation.id)) this.pools.set(view.observation.id, newPlaybackView(view))
        }
      }
      const heldFrom = requirement === 'required' ? index : index > 0 ? frames[index - 1]!.heldFrom : -1
      let reason = ''
      if (requirement === 'required' && !matched) {
        reason = `Required ${reference.classification} source frame at ${t.toFixed(3)}s lacks an independently matched camera or complete measured mechanism state${failed ? ` (${failed.observation.id})` : ''}.`
      } else if (requirement === 'not-required') {
        const last = heldFrom < 0 ? undefined : frames[heldFrom]!
        // Never skip back over an unmatched required frame to an older, possibly stale pose.
        reason = !last
          ? 'Source shows no corresponding mechanism here and no earlier required source frame exists; the exploratory model is shown without asserting a source pose.'
          : last.matched
            ? `No corresponding physical mechanism in this source interval; holding the pose matched at ${last.reference.timeSeconds.toFixed(3)}s.`
            : `No corresponding physical mechanism here, but the preceding required source frame at ${last.reference.timeSeconds.toFixed(3)}s was not matched; no pose can be held.`
      }
      frames.push({ reference, requirement, views, matched, reason, heldFrom })
    })
    this.frames = frames
  }

  at(timeSeconds: number): SourceSample {
    const t = Math.max(0, Math.min(this.data.source.durationSeconds, finite(timeSeconds, 'Playback time')))
    let lo = 0
    let hi = this.frames.length
    while (lo < hi) {
      const mid = (lo + hi) >>> 1
      if (this.frames[mid]!.reference.timeSeconds <= t) lo = mid + 1
      else hi = mid
    }
    const index = Math.max(0, lo - 1)
    const current = this.frames[index]!
    this.sample.timeSeconds = t
    this.sample.views.length = 0
    if (current.reference.timeSeconds > t) {
      this.sample.state = 'unavailable'
      this.sample.reason = `No source observation exists before ${current.reference.timeSeconds.toFixed(3)}s.`
      return this.sample
    }
    this.sample.reason = current.reason
    let from = current
    if (current.requirement === 'not-required') {
      // Exempt source: show an actual earlier matched pose, or explicitly assert none.
      if (current.heldFrom < 0) {
        this.sample.state = 'no-machine'
        return this.sample
      }
      from = this.frames[current.heldFrom]!
      if (!from.matched) {
        this.sample.state = 'unavailable'
        return this.sample
      }
      this.sample.state = 'held'
    } else if (!current.matched) {
      this.sample.state = 'unavailable'
      return this.sample
    } else {
      this.sample.state = 'matched'
    }
    const next = this.sample.state === 'matched' ? this.frames[index + 1] : undefined
    const continuous = next !== undefined && next.matched && next.reference.shotId === from.reference.shotId
    const mix = continuous ? Math.max(0, Math.min(1, (t - from.reference.timeSeconds) / (next.reference.timeSeconds - from.reference.timeSeconds))) : 0
    for (const view of from.views) {
      const a = view.observation
      const aCamera = a.camera!
      const aInput = view.input!
      const out = this.pools.get(a.id)!
      let other: CompiledView | undefined
      if (continuous) {
        for (const candidate of next.views) {
          if (candidate.observation.id === a.id) { other = candidate; break }
        }
      }
      const b = other?.observation
      copyInput(out.input, aInput)
      out.partOverrides = a.partOverrides ?? noOverrides
      out.presentation = a.presentation
      for (let k = 0; k < 4; k++) out.rectSourcePixels[k] = a.rectSourcePixels[k]!
      const camera = out.camera
      for (let k = 0; k < 3; k++) camera.positionMetres[k] = aCamera.positionMetres[k]!
      for (let k = 0; k < 4; k++) camera.quaternion[k] = aCamera.quaternion[k]!
      camera.verticalFovDegrees = aCamera.verticalFovDegrees
      camera.principalPointViewportPixels[0] = aCamera.principalPointViewportPixels?.[0] ?? a.rectSourcePixels[2] / 2
      camera.principalPointViewportPixels[1] = aCamera.principalPointViewportPixels?.[1] ?? a.rectSourcePixels[3] / 2
      // `next.matched` guarantees every next view has a passing camera and complete input.
      if (mix > 0 && other && b?.camera && other.input && b.presentation === a.presentation) {
        blendInput(out.input, aInput, other.input, mix)
        for (let k = 0; k < 3; k++) camera.positionMetres[k] = camera.positionMetres[k]! + (b.camera.positionMetres[k]! - aCamera.positionMetres[k]!) * mix
        for (let k = 0; k < 4; k++) out.rectSourcePixels[k] = out.rectSourcePixels[k]! + (b.rectSourcePixels[k]! - a.rectSourcePixels[k]!) * mix
        for (let k = 0; k < 2; k++) {
          const fromPoint = camera.principalPointViewportPixels[k]!
          const toPoint = b.camera.principalPointViewportPixels?.[k] ?? b.rectSourcePixels[k + 2]! / 2
          camera.principalPointViewportPixels[k] = fromPoint + (toPoint - fromPoint) * mix
        }
        qa.fromArray(aCamera.quaternion)
        qb.fromArray(b.camera.quaternion)
        qi.slerpQuaternions(qa, qb, mix).toArray(camera.quaternion)
        camera.verticalFovDegrees += (b.camera.verticalFovDegrees - aCamera.verticalFovDegrees) * mix
      }
      this.sample.views.push(out)
    }
    return this.sample
  }
}

export async function loadReference(video: Video): Promise<VideoReference> {
  const load = files[`../content/${video.id}.observations.json`]
  if (!load) throw new Error(`Measured source observations are not available for ${video.title}.`)
  return new VideoReference(await load() as ReferenceFile, video)
}

export function serializeInput(input: MechanismInput): SerializedInput {
  return { crankTurns: input.crankTurns, amplitudes: Array.from(input.amplitudes), phases: Array.from(input.phases), gearing: input.gearing, magnification: input.magnification, setup: { ...input.setup } }
}
