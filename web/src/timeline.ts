import { Quaternion } from 'three'
import { createMechanismInput, createMechanismPose, MECHANISM_DATA, type MechanismInput, type MechanismPose } from './mechanics'
import { assertSourceCompositeWeights, type CameraRecord, type PartOverride, type SourceComposite, type SourceView } from './scene'
import { compileInput, compileWitness, equalRecord, inputValue, solveSourceInput, validateVisibilityProof, validateNativeGeometryAssumptions, SETUP_KEYS, type InputField, type MechanicalObservation, type MechanicalProvenance, type SerializedInput, type SourceConstraint, type SourceImageIdentity, type NativeLineCheck, type SourceContourCheck, type NativeGeometryAssumption, type SourceNonIdentifiableFixedPart } from './source-witness'
export type { MechanicalObservation, SerializedInput } from './source-witness'
import type { Video } from './video-catalog'

export const SOURCE_WIDTH = 1920
export const SOURCE_HEIGHT = 1080
export const LANDMARK_LIMIT_PX = SOURCE_WIDTH * 0.02
/**
 * matched: a required source frame with a passing camera and complete observed or constrained input per view.
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
export interface SourcePartOverride extends PartOverride {
  evidence: string
  sourceTimeSeconds: number
  landmarkIds: string[]
}
export interface ObservedView {
  id: string
  rectSourcePixels: [number, number, number, number]
  presentation: 'native' | 'horizontal-mirror'
  camera: ObservedCamera | null
  mechanicalState: MechanicalObservation
  partOverrides?: SourcePartOverride[]
  composite?: SourceComposite
  compositeEvidence?: string
  nativeLineChecks?: NativeLineCheck[]
  sourceContourChecks?: SourceContourCheck[]
}
export interface ReferenceFrame {
  timeSeconds: number
  decodedTimeSeconds: number
  shotId: string
  sourceImage?: SourceImageIdentity
  classification: Classification
  landmarks: Landmark[]
  unavailable: { anchorId: string; reason: string }[]
  mechanicalState: MechanicalObservation
  camera: ObservedCamera | null
  views?: ObservedView[]
  partOverrides?: SourcePartOverride[]
  composite?: SourceComposite
  compositeEvidence?: string
  nativeLineChecks?: NativeLineCheck[]
  sourceContourChecks?: SourceContourCheck[]
}
export interface ReferenceFile {
  schemaVersion: 1
  source: { videoId: string; sha256: string; width: number; height: number; durationSeconds: number; fps: number }
  model: { sha256: string; sourceCommit: string; units: 'metres'; axes: string }
  anchors: ReferenceAnchor[]
  shots: { id: string; startSeconds: number; endSeconds: number; classification: Classification; hasCorrespondingMachine?: boolean; reason: string }[]
  frames: ReferenceFrame[]
  coverage: { status: 'complete' | 'blocked'; blockers: (string | { reason: string; intervalSeconds?: [number, number] })[]; requiredEveryIntegerSecond: true }
  nativeGeometryAssumptions?: NativeGeometryAssumption[]
}
interface CompiledView {
  observation: ObservedView
  input: MechanismInput | null
  pose: MechanismPose | null
  blendedConstraints: SourceConstraint[]
}
interface CompiledFrame {
  reference: ReferenceFrame
  requirement: 'required' | 'not-required'
  views: CompiledView[]
  /** Required frame whose every view has a passing camera and complete source reconstruction. */
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
export interface PlaybackView extends SourceView, MechanicalProvenance {
  id: string
  camera: PlaybackCamera
  rectSourcePixels: [number, number, number, number]
  input: MechanismInput
  partOverrides: readonly PartOverride[]
  compositeEvidence: string | null
  sourceSampling: { fromTimeSeconds: number; toTimeSeconds: number; mix: number }
  visibilityProofEnd: MechanicalProvenance['visibilityProof'] | null
  constraintSummary: SourceConstraint[]
  nativeLineChecks: readonly NativeLineCheck[]
  sourceContourChecks: readonly SourceContourCheck[]
}
export interface SourceSample {
  state: ReferenceState
  timeSeconds: number
  reason: string
  views: PlaybackView[]
  mechanicalProvenance: MechanicalProvenance['mechanicalProvenance'] | null
  unobservedInputFields: InputField[]
  constraintSummary: Record<string, readonly SourceConstraint[]>
  nativeGeometryAssumptions: readonly NativeGeometryAssumption[]
  sourceNonIdentifiableFixedParts: Record<string, readonly SourceNonIdentifiableFixedPart[]>
}

const files = import.meta.glob('../content/*.observations.json', { import: 'default' })
const classifications: Record<Classification, true> = { machine: true, 'non-machine': true, transition: true, unobservable: true }
const setupKeys = SETUP_KEYS
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
    && view.input !== null && ['observed', 'constrained'].includes(mechanicalState?.status) && mechanicalState.visiblePoseCompleteness === 'complete'
}

function newPlaybackView(view: CompiledView, nativeGeometryAssumptions: readonly NativeGeometryAssumption[]): PlaybackView {
  const camera = view.observation.camera!
  const proof = view.observation.mechanicalState.status === 'observed' ? view.observation.mechanicalState.visibilityProof : view.observation.mechanicalState.runtimeWitness!.visibilityProof
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
    composite: view.observation.composite ?? { mode: 'opaque' },
    compositeEvidence: view.observation.compositeEvidence ?? null,
    mechanicalProvenance: view.observation.mechanicalState.status === 'constrained' ? 'constrained' : 'observed',
    unobservedInputFields: view.observation.mechanicalState.runtimeWitness?.unobservedInputFields ?? [],
    constraintSummary: view.blendedConstraints,
    visibilityProof: proof,
    sourceNonIdentifiableFixedParts: proof.sourceNonIdentifiableFixedParts,
    continuity: view.observation.mechanicalState.runtimeWitness?.continuity ?? null,
    sourceSampling: { fromTimeSeconds: 0, toTimeSeconds: 0, mix: 0 },
    visibilityProofEnd: null,
    nativeGeometryAssumptions,
    nativeLineChecks: view.observation.nativeLineChecks ?? [],
    sourceContourChecks: view.observation.sourceContourChecks ?? [],
  }
}

function compatibleConstraint(a: SourceConstraint, b: SourceConstraint): boolean {
  if (a.kind !== b.kind || a.evidence !== b.evidence) return false
  switch (a.kind) {
    case 'input-value': return b.kind === a.kind && a.field === b.field && typeof a.value === typeof b.value
    case 'input-interval': return b.kind === a.kind && a.field === b.field
    case 'effective-bank-drive': return b.kind === a.kind && a.winding === 'unwrapped' && b.winding === 'unwrapped'
    case 'channel-angle': return b.kind === a.kind && a.channelIndex === b.channelIndex && a.winding === 'unwrapped' && b.winding === 'unwrapped'
    case 'paper-travel': return true
    case 'pen-travel': return true
  }
}

function compatibleViews(a: CompiledView, b: CompiledView, time: number): boolean {
  const av = a.observation
  const bv = b.observation
  if (av.id !== bv.id || av.presentation !== bv.presentation || !equalRecord(av.composite ?? { mode: 'opaque' }, bv.composite ?? { mode: 'opaque' })
    || !equalRecord(av.partOverrides ?? noOverrides, bv.partOverrides ?? noOverrides)) return false
  const ap = av.mechanicalState.status === 'observed' ? av.mechanicalState.visibilityProof : av.mechanicalState.runtimeWitness!.visibilityProof
  const bp = bv.mechanicalState.status === 'observed' ? bv.mechanicalState.visibilityProof : bv.mechanicalState.runtimeWitness!.visibilityProof
  if (!equalRecord(ap.sourceNonIdentifiableFixedParts, bp.sourceNonIdentifiableFixedParts)) return false
  const ai = a.input!
  const bi = b.input!
  if (ai.gearing !== bi.gearing || (ai.setup.counterHeightM === null) !== (bi.setup.counterHeightM === null)
    || (ai.setup.coneSwingRad === 0) !== (bi.setup.coneSwingRad === 0) || ai.setup.driveCrankOffsetTurns !== bi.setup.driveCrankOffsetTurns) return false
  const aw = av.mechanicalState.runtimeWitness
  const bw = bv.mechanicalState.runtimeWitness
  if (!aw && !bw) {
    for (const state of [av.mechanicalState, bv.mechanicalState]) {
      if (state.status !== 'observed') return false
      const [start, end] = state.visibilityProof.binding.intervalSeconds
      if (time < start || time > end) return false
    }
    return true
  }
  if (!aw || !bw || !aw.continuity || !bw.continuity || av.presentation !== 'native' || !equalRecord(aw.continuity, bw.continuity)
    || aw.unobservedInputFields.length !== bw.unobservedInputFields.length
    || !aw.unobservedInputFields.every((field) => bw.unobservedInputFields.includes(field))
    || aw.constraints.length !== bw.constraints.length
    || !aw.constraints.every((constraint, i) => compatibleConstraint(constraint, bw.constraints[i]!))) return false
  for (const field of aw.unobservedInputFields) {
    if (field !== 'crankTurns' && field !== 'setup.heldChannelTurns' && inputValue(ai, field) !== inputValue(bi, field)) return false
  }
  for (const witness of [aw, bw]) {
    const [start, end] = witness.visibilityProof.binding.intervalSeconds
    if (time < start || time > end) return false
  }
  return true
}

function blendConstraints(target: SourceConstraint[], a: readonly SourceConstraint[], b: readonly SourceConstraint[], mix: number): void {
  for (let i = 0; i < a.length; i++) {
    const from = a[i]!
    const to = b[i]!
    const out = target[i]!
    // Source evidence names this continuous regime; branch/provenance never changes.
    for (const key of Object.keys(from)) {
      const start = (from as unknown as Record<string, unknown>)[key]
      const end = (to as unknown as Record<string, unknown>)[key]
      if (typeof start === 'number' && typeof end === 'number') (out as unknown as Record<string, unknown>)[key] = start + (end - start) * mix
    }
  }
}

/** Measured reference samples are consumed identically by playback and frame review. */
export class VideoReference {
  readonly data: ReferenceFile
  readonly coverageMessage: string
  readonly sourcePartOverrides: readonly PartOverride[]
  private readonly frames: CompiledFrame[]
  private readonly sample: SourceSample = { state: 'unavailable', timeSeconds: 0, reason: '', views: [], mechanicalProvenance: null, unobservedInputFields: [], constraintSummary: {}, nativeGeometryAssumptions: [], sourceNonIdentifiableFixedParts: {} }
  private readonly pools = new Map<string, PlaybackView>()
  /** Private scratch for select(); never exposed, so getState() stays observably side-effect free. */
  private readonly selection: { t: number, index: number, state: ReferenceState, from: CompiledFrame | null } = { t: 0, index: 0, state: 'unavailable', from: null }

  constructor(data: ReferenceFile, video: Video) {
    validateNativeGeometryAssumptions(data.nativeGeometryAssumptions)
    if (data.schemaVersion !== 1 || data.source?.videoId !== video.id || data.source.sha256 !== video.sourceSha256) throw new Error('Reference footage identity does not match this video.')
    if (data.source.width !== SOURCE_WIDTH || data.source.height !== SOURCE_HEIGHT || Math.abs(data.source.durationSeconds - video.durationSeconds) > 0.05) throw new Error('Reference dimensions or duration do not match the decoded footage.')
    if (data.model?.sha256 !== MECHANISM_DATA.provenance.modelSha256 || data.model.sourceCommit !== MECHANISM_DATA.provenance.sourceCommit || data.model.units !== 'metres') throw new Error('Reference measurements target a different CAD export.')
    if (!Array.isArray(data.frames) || data.frames.length === 0 || !Array.isArray(data.anchors) || !Array.isArray(data.shots)) throw new Error('No measured reference frames are available.')
    if (!data.coverage || !['complete', 'blocked'].includes(data.coverage.status) || !Array.isArray(data.coverage.blockers)) throw new Error('Missing source-coverage evidence.')
    this.data = data
    this.sourcePartOverrides = data.frames.flatMap((frame) => [...(frame.partOverrides ?? []), ...(frame.views?.flatMap((view) => view.partOverrides ?? []) ?? [])])
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
      const observations: ObservedView[] = reference.views ?? [{
        id: 'main', rectSourcePixels: [0, 0, SOURCE_WIDTH, SOURCE_HEIGHT] as [number, number, number, number],
        presentation: 'native' as const, camera: reference.camera, mechanicalState: reference.mechanicalState,
        partOverrides: reference.partOverrides, composite: reference.composite, compositeEvidence: reference.compositeEvidence,
        nativeLineChecks: reference.nativeLineChecks, sourceContourChecks: reference.sourceContourChecks,
      }]
      assertSourceCompositeWeights(observations)
      const views = observations.map((observation) => {
        if (observation.camera) requireCamera(observation.camera, `${video.id}@${t}s/${observation.id}`)
        if (observation.rectSourcePixels?.length !== 4) throw new Error(`Invalid source viewport at ${t}s.`)
        observation.rectSourcePixels.forEach((value) => finite(value, 'Source viewport'))
        const [x, y, w, h] = observation.rectSourcePixels
        if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > SOURCE_WIDTH || y + h > SOURCE_HEIGHT) throw new Error(`Source viewport exceeds the frame at ${t}s.`)
        if (!['native', 'horizontal-mirror'].includes(observation.presentation)) throw new Error('Unknown source presentation.')
        const label = `${video.id}@${t}s/${observation.id}`
        const state = observation.mechanicalState
        if (!state || !['observed', 'constrained', 'unobservable', 'not-applicable'].includes(state.status) || typeof state.evidence !== 'string' || !state.evidence.trim()) throw new Error(`${label}: invalid mechanical provenance.`)
        const stateKeys = ['status', 'input', 'evidence', 'visiblePoseCompleteness', ...(state.status === 'observed' ? ['visibilityProof'] : state.status === 'constrained' ? ['runtimeWitness'] : [])]
        if (Object.keys(state).some((key) => !stateKeys.includes(key)) || (state.visiblePoseCompleteness !== undefined && !['complete', 'partial'].includes(state.visiblePoseCompleteness))) throw new Error(`${label}: mechanical observation has unknown or conflicting fields.`)
        if (new Set((observation.partOverrides ?? noOverrides).map((override) => override.partPath)).size !== (observation.partOverrides ?? noOverrides).length) throw new Error(`${label}: duplicate part override.`)
        for (const checks of [observation.nativeLineChecks ?? [], observation.sourceContourChecks ?? []]) {
          if (new Set(checks.map((check) => check.id)).size !== checks.length) throw new Error(`${label}: duplicate source geometry check ID.`)
        }
        for (const override of observation.partOverrides ?? noOverrides) {
          const sourced = override as SourcePartOverride
          if (!sourced.evidence?.trim() || sourced.sourceTimeSeconds !== reference.decodedTimeSeconds || !Array.isArray(sourced.landmarkIds) || !sourced.landmarkIds.length
            || new Set(sourced.landmarkIds).size !== sourced.landmarkIds.length
            || sourced.landmarkIds.some((id) => !reference.landmarks.some((landmark) => landmark.anchorId === id && landmark.role === 'check' && (landmark.viewId ?? 'main') === observation.id))) throw new Error(`${label}: part override lacks current-frame source evidence and independent checks.`)
          if (!sourced.partPath?.includes('/')) throw new Error(`${label}: part override needs a qualified native path.`)
        }
        const composite = observation.composite
        if (composite) {
          if (composite.mode === 'crossfade') {
            if (Object.keys(composite).some((key) => !['mode', 'groupId', 'opacity'].includes(key)) || !composite.groupId?.trim() || finite(composite.opacity, label) < 0 || composite.opacity > 1 || !observation.compositeEvidence?.trim()) throw new Error(`${label}: measured composite opacity evidence is required.`)
          } else if (composite.mode !== 'opaque' || Object.keys(composite).length !== 1) throw new Error(`${label}: unknown source composite.`)
        }
        let input: MechanismInput | null = null
        if (state.status === 'observed') {
          if (state.runtimeWitness || !state.input || !state.visibilityProof || state.visiblePoseCompleteness !== 'complete') throw new Error(`${label}: observed input needs an exclusive complete source visibility proof.`)
          input = compileInput(state.input, label)
          if (input.setup.counterHeightM === null) throw new Error(`${label}: auto-level counter is a chosen algorithm, not a measured height; use constrained provenance.`)
        } else if (state.status === 'constrained') {
          if (state.input !== null || state.visibilityProof || state.visiblePoseCompleteness !== 'complete') throw new Error(`${label}: constrained input must remain null with exactly one complete witness proof.`)
          input = compileWitness(state.runtimeWitness, label)
        } else if (state.input !== null || state.runtimeWitness || state.visibilityProof) throw new Error(`${label}: unobserved state cannot contain runtime input or a visibility proof.`)
        const proof = state.status === 'observed' ? state.visibilityProof : state.runtimeWitness?.visibilityProof
        if (input) {
          if (!proof || !observation.camera || !reference.sourceImage) throw new Error(`${label}: source reconstruction needs its bound camera and actual decoded source image.`)
          validateVisibilityProof(proof, {
            sourceVideoId: data.source.videoId, sourceSha256: data.source.sha256, sourceImage: reference.sourceImage,
            modelSha256: data.model.sha256, modelSourceCommit: data.model.sourceCommit,
            shotId: reference.shotId, viewId: observation.id, timeSeconds: t, decodedTimeSeconds: reference.decodedTimeSeconds,
            input: state.status === 'observed' ? state.input : state.runtimeWitness!.input, camera: observation.camera,
            rectSourcePixels: observation.rectSourcePixels, presentation: observation.presentation,
            composite: observation.composite ?? { mode: 'opaque' }, partOverrides: observation.partOverrides ?? noOverrides,
            constraints: state.runtimeWitness?.constraints ?? [], continuity: state.runtimeWitness?.continuity ?? null,
            nativeGeometryAssumptions: data.nativeGeometryAssumptions ?? [],
            sourceNonIdentifiableFixedParts: proof.sourceNonIdentifiableFixedParts,
          }, data.anchors, label)
          for (const part of proof.sourceVisibleParts) {
            const coverage = part.sourceCoverage
            if (coverage.kind === 'landmarks') {
              if (coverage.landmarkIds.some((id) => !reference.landmarks.some((landmark) => landmark.anchorId === id && landmark.status === 'observed' && (landmark.viewId ?? 'main') === observation.id))) throw new Error(`${label}: visibility census lacks current-frame source correspondences.`)
            } else if (coverage.kind === 'native-line-checks') {
              for (const id of coverage.lineCheckIds) {
                const line = observation.nativeLineChecks?.find((candidate) => candidate.id === id && candidate.partPath === part.partPath)
                if (!line || !equalRecord(line.measurementEvidence?.sourceImage, reference.sourceImage) || finite(line.uncertaintyPx, label) < 0
                  || line.partLocalLineMetres?.length !== 2 || line.sourceLinePixels?.length !== 2) throw new Error(`${label}: native line coverage lacks bound actual source evidence.`)
                for (const point of line.partLocalLineMetres) {
                  if (point.length !== 3) throw new Error(`${label}: invalid native line endpoint.`)
                  point.forEach((value) => finite(value, label))
                }
                for (const point of line.sourceLinePixels) {
                  if (point.length !== 2 || point[0] < x || point[0] >= x + w || point[1] < y || point[1] >= y + h) throw new Error(`${label}: actual source line is outside its viewport.`)
                  point.forEach((value) => finite(value, label))
                }
                if (equalRecord(line.partLocalLineMetres[0], line.partLocalLineMetres[1]) || equalRecord(line.sourceLinePixels[0], line.sourceLinePixels[1])) throw new Error(`${label}: degenerate native/source line.`)
              }
            } else if (coverage.kind === 'source-contour') {
              for (const id of coverage.contourCheckIds) {
                const contour = observation.sourceContourChecks?.find((candidate) => candidate.id === id && candidate.partPath === part.partPath)
                if (!contour || !equalRecord(contour.measurementEvidence?.sourceImage, reference.sourceImage) || !contour.measurementEvidence.evidence?.trim()
                  || finite(contour.uncertaintyPx, label) < 0 || !Array.isArray(contour.sourceContourPixels) || contour.sourceContourPixels.length < 2) throw new Error(`${label}: contour coverage lacks bound actual source evidence.`)
                for (const point of contour.sourceContourPixels) {
                  if (point.length !== 2 || point[0] < x || point[0] >= x + w || point[1] < y || point[1] >= y + h) throw new Error(`${label}: actual source contour is outside its viewport.`)
                  point.forEach((value) => finite(value, label))
                }
                if (contour.sourceContourPixels.every((point) => equalRecord(point, contour.sourceContourPixels[0]))) throw new Error(`${label}: degenerate source contour.`)
              }
            }
          }
        }
        const pose = input ? solveSourceInput(input, state.runtimeWitness?.constraints ?? []) : null
        return { observation, input, pose, blendedConstraints: state.runtimeWitness?.constraints.map((constraint) => ({ ...constraint })) ?? [] }
      })
      const failed = views.find((view) => !viewMatchable(view))
      const matched = requirement === 'required' && views.length > 0 && !failed
      if (matched) {
        for (const view of views) {
          if (!this.pools.has(view.observation.id)) this.pools.set(view.observation.id, newPlaybackView(view, data.nativeGeometryAssumptions ?? []))
        }
      }
      const heldFrom = requirement === 'required' ? index : index > 0 ? frames[index - 1]!.heldFrom : -1
      let reason = ''
      if (requirement === 'required' && !matched) {
        reason = `Required ${reference.classification} source frame at ${t.toFixed(3)}s lacks an independently matched camera or complete source-visible mechanism reconstruction${failed ? ` (${failed.observation.id})` : ''}.`
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

  /** Frame index plus required/held/no-machine selection shared by at() and getState(). */
  private select(timeSeconds: number): typeof this.selection {
    const s = this.selection
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
    s.t = t
    s.index = index
    s.from = null
    if (current.reference.timeSeconds > t) {
      s.state = 'unavailable'
    } else if (current.requirement === 'not-required') {
      // Exempt source: show an actual earlier matched pose, or explicitly assert none.
      if (current.heldFrom < 0) {
        s.state = 'no-machine'
      } else {
        const held = this.frames[current.heldFrom]!
        s.state = held.matched ? 'held' : 'unavailable'
        if (held.matched) s.from = held
      }
    } else if (!current.matched) {
      s.state = 'unavailable'
    } else {
      const next = this.frames[index + 1]
      const needsContinuity = current.views.some((view) => view.observation.mechanicalState.status === 'constrained')
      const discreteChange = next?.matched && current.views.some((view, i) => {
        const other = next.views[i]
        return !other || !equalRecord(view.observation.composite ?? { mode: 'opaque' }, other.observation.composite ?? { mode: 'opaque' })
          || !equalRecord(view.observation.partOverrides ?? noOverrides, other.observation.partOverrides ?? noOverrides)
          || view.input!.gearing !== other.input!.gearing || view.input!.setup.driveCrankOffsetTurns !== other.input!.setup.driveCrankOffsetTurns
          || (view.input!.setup.coneSwingRad === 0) !== (other.input!.setup.coneSwingRad === 0)
      })
      if (t > current.reference.timeSeconds && (needsContinuity || discreteChange) && (!next?.matched || next.reference.shotId !== current.reference.shotId
        || current.views.length !== next.views.length || !current.views.every((view, i) => compatibleViews(view, next.views[i]!, t)))) {
        s.state = 'unavailable'
        return s
      }
      s.state = 'matched'
      s.from = current
    }
    return s
  }

  /** Reference state at a time without touching the sample, its views, or the pooled draw state. */
  getState(timeSeconds: number): ReferenceState {
    return this.select(timeSeconds).state
  }

  at(timeSeconds: number): SourceSample {
    const { t, index, state, from } = this.select(timeSeconds)
    const current = this.frames[index]!
    this.sample.timeSeconds = t
    this.sample.views.length = 0
    this.sample.mechanicalProvenance = null
    this.sample.unobservedInputFields.length = 0
    for (const id in this.sample.constraintSummary) delete this.sample.constraintSummary[id]
    for (const id in this.sample.sourceNonIdentifiableFixedParts) delete this.sample.sourceNonIdentifiableFixedParts[id]
    this.sample.nativeGeometryAssumptions = this.data.nativeGeometryAssumptions ?? []
    this.sample.state = state
    if (current.reference.timeSeconds > t) {
      this.sample.reason = `No source observation exists before ${current.reference.timeSeconds.toFixed(3)}s.`
      return this.sample
    }
    this.sample.reason = current.reason
    if (state === 'unavailable' && current.matched) this.sample.reason = 'No source-evidenced compatible continuous reconstruction exists between these samples; an actual source-change sample is required.'
    if (!from) return this.sample
    const next = state === 'matched' ? this.frames[index + 1] : undefined
    const continuous = next !== undefined && next.matched && next.reference.shotId === from.reference.shotId && from.views.length === next.views.length
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
      out.composite = a.composite ?? { mode: 'opaque' }
      out.compositeEvidence = a.compositeEvidence ?? null
      out.nativeLineChecks = a.nativeLineChecks ?? []
      out.sourceContourChecks = a.sourceContourChecks ?? []
      out.mechanicalProvenance = a.mechanicalState.status === 'constrained' ? 'constrained' : 'observed'
      out.unobservedInputFields = a.mechanicalState.runtimeWitness?.unobservedInputFields ?? []
      out.constraintSummary = view.blendedConstraints
      out.visibilityProof = a.mechanicalState.status === 'observed' ? a.mechanicalState.visibilityProof : a.mechanicalState.runtimeWitness!.visibilityProof
      out.sourceNonIdentifiableFixedParts = out.visibilityProof.sourceNonIdentifiableFixedParts
      out.visibilityProofEnd = null
      out.continuity = a.mechanicalState.runtimeWitness?.continuity ?? null
      out.sourceSampling.fromTimeSeconds = from.reference.timeSeconds
      out.sourceSampling.toTimeSeconds = from.reference.timeSeconds
      out.sourceSampling.mix = 0
      for (let k = 0; k < 4; k++) out.rectSourcePixels[k] = a.rectSourcePixels[k]!
      const camera = out.camera
      for (let k = 0; k < 3; k++) camera.positionMetres[k] = aCamera.positionMetres[k]!
      for (let k = 0; k < 4; k++) camera.quaternion[k] = aCamera.quaternion[k]!
      camera.verticalFovDegrees = aCamera.verticalFovDegrees
      camera.principalPointViewportPixels[0] = aCamera.principalPointViewportPixels?.[0] ?? a.rectSourcePixels[2] / 2
      camera.principalPointViewportPixels[1] = aCamera.principalPointViewportPixels?.[1] ?? a.rectSourcePixels[3] / 2
      // `next.matched` guarantees every next view has a passing camera and complete input.
      if (mix > 0 && other && b?.camera && other.input && compatibleViews(view, other, t)) {
        blendInput(out.input, aInput, other.input, mix)
        blendConstraints(out.constraintSummary, a.mechanicalState.runtimeWitness?.constraints ?? [], b.mechanicalState.runtimeWitness?.constraints ?? [], mix)
        out.visibilityProofEnd = b.mechanicalState.status === 'observed' ? b.mechanicalState.visibilityProof : b.mechanicalState.runtimeWitness!.visibilityProof
        out.sourceSampling.toTimeSeconds = next!.reference.timeSeconds
        out.sourceSampling.mix = mix
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
      } else {
        blendConstraints(out.constraintSummary, a.mechanicalState.runtimeWitness?.constraints ?? [], a.mechanicalState.runtimeWitness?.constraints ?? [], 0)
      }
      solveSourceInput(out.input, out.constraintSummary, view.pose ?? createMechanismPose())
      if (this.sample.mechanicalProvenance !== 'constrained') this.sample.mechanicalProvenance = out.mechanicalProvenance
      for (const field of out.unobservedInputFields) if (!this.sample.unobservedInputFields.includes(field)) this.sample.unobservedInputFields.push(field)
      this.sample.constraintSummary[out.id] = out.constraintSummary
      this.sample.sourceNonIdentifiableFixedParts[out.id] = out.sourceNonIdentifiableFixedParts
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
