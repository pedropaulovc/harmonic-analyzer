import { Quaternion } from 'three'
import { createMechanismInput, createMechanismPose, MECHANISM_DATA, type MechanismInput } from './mechanics'
import { assertSourceCompositeWeights, type CameraRecord, type ImagePlaneWarp, type SourceComposite, type SourceLayoutEntry, type LandmarkAnchor } from './scene'
import { compileSourceAssemblyState } from './source-assembly'
import type { SourceAssemblyState } from './source-assembly'
import { compileInput, equalRecord, INPUT_FIELDS, SETUP_KEYS, solveSourceInput, validateNativeGeometryAssumptions, type InputField, type NativeGeometryAssumption, type NativeLineCheck, type SerializedInput, type SourceConstraint, type SourceImageIdentity } from './source-witness'
import type { Classification, Landmark, PlaybackView, ReferenceAnchor, SourceIdentity, NativeModelIdentity, SourceShot, ReferenceState, SourceSample } from './timeline'
import type { Video } from './video-catalog'
import { requiredSourceViews, sourceVisibilityError, physicalSourceFrameRequired, type SourceVisibilityQualification } from '../source-visibility.mjs'
import { NATIVE_LINE_STATIONS, nativeLineEndpointId } from '../native-line-checks.mjs'

export const SOURCE_WIDTH = 1920
export const SOURCE_HEIGHT = 1080
export const SOURCE_STAGE_PERCENTAGES = [50, 20, 10, 5] as const
export const LANDMARK_LIMIT_PX = SOURCE_WIDTH * 0.05
const EMPTY_CONSTRAINTS: readonly SourceConstraint[] = []
const EMPTY_GEOMETRY_ASSUMPTIONS: readonly NativeGeometryAssumption[] = []
const OPAQUE_COMPOSITE: SourceComposite = { mode: 'opaque' }
const PHASE_PERIOD_RAD = 2 * Math.PI
const UNMEASURED_STAGE = Object.freeze({ status: 'unmeasured' as const })
const UNMEASURED_STAGES = Object.freeze({ 50: UNMEASURED_STAGE, 20: UNMEASURED_STAGE, 10: UNMEASURED_STAGE, 5: UNMEASURED_STAGE })
export type SourceStagePercentage = typeof SOURCE_STAGE_PERCENTAGES[number]
export interface SourceStageMeasurement {
  status: 'unmeasured' | 'failed' | 'passed'
  /** Authored diagnostics only; runtime never treats a report string as verified evidence. */
  report?: string
  maximumErrorPx?: number
  measuredSamples?: number
  requiredSamples?: number
}
export interface CompactSourceView {
  id: string
  /** Explicit source-view identities represented by this rendered layer; never inferred aliases. */
  sourceViewIds?: string[]
  /** Source/layout evidence for the declared mapping, including authored decomposition. */
  sourceViewMappingEvidence?: string
  rectSourcePixels: [number, number, number, number]
  sourceVisibility?: SourceVisibilityQualification
  presentation: 'native' | 'horizontal-mirror'
  camera: CameraRecord | null
  input: SerializedInput | null
  /** Separate physical attachment/display state; omitted means the normal operating assembly. */
  sourceAssembly?: SourceAssemblyState
  provenance: { kind: 'chosen-feasible'; evidence: string; unobservedInputFields: InputField[] }
  cameraProvenance?: { kind: 'source-fit' | 'source-transfer' | 'source-informed-framing'; evidence: string; family: string }
  cameraContinuityFamily?: string
  /** Held vetoes blending; source-informed framing requires continuous-shot at both endpoints. */
  cameraInterpolation?: 'continuous-shot' | 'held'
  /** Nonblank source evidence required for continuous-shot interpolation. */
  cameraInterpolationEvidence?: string
  composite?: SourceComposite
  imagePlaneWarp?: ImagePlaneWarp
  nativeLineChecks?: NativeLineCheck[]
}
export interface CompactSourceFrame {
  timeSeconds: number
  decodedTimeSeconds: number | null
  sourceSampleUnavailable?: true
  unavailableReason?: string
  shotId: string
  classification: Classification
  sourceMachineRequirement?: 'required'
  sourceImage?: SourceImageIdentity
  landmarks: Landmark[]
  views: CompactSourceView[]
}
export interface CompactSourceTrack {
  schemaVersion: 1
  kind: 'compact-source-track'
  source: SourceIdentity
  model: NativeModelIdentity
  anchors: ReferenceAnchor[]
  shots: SourceShot[]
  frames: CompactSourceFrame[]
  coverage: { status: 'complete' | 'blocked'; blockers: string[]; requiredEveryIntegerSecond: true }
  stages: Record<SourceStagePercentage, SourceStageMeasurement>
  sourceMeasurements?: { status: 'incomplete' | 'partial'; blockers: string[] }
  nativeGeometryAssumptions?: NativeGeometryAssumption[]
}

/** Every dependent native part still uses the existing complete mechanism input and solve. */
function copyInput(target: MechanismInput, source: MechanismInput): void {
  target.crankTurns = source.crankTurns
  target.amplitudes.set(source.amplitudes)
  target.phases.set(source.phases)
  target.gearing = source.gearing
  target.magnification = source.magnification
  Object.assign(target.setup, source.setup)
}

function blendInput(target: MechanismInput, a: MechanismInput, b: MechanismInput, phaseDeltas: Float64Array, mix: number): void {
  copyInput(target, a)
  // Crank turns are cumulative physical drive, unlike periodic cam phase offsets.
  target.crankTurns += (b.crankTurns - a.crankTurns) * mix
  target.magnification += (b.magnification - a.magnification) * mix
  for (let i = 0; i < 20; i++) {
    target.amplitudes[i] = a.amplitudes[i]! + (b.amplitudes[i]! - a.amplitudes[i]!) * mix
    target.phases[i] = a.phases[i]! + phaseDeltas[i]! * mix
  }
  for (const key of SETUP_KEYS) {
    const from = a.setup[key]
    const to = b.setup[key]
    if (from !== null && to !== null) target.setup[key] = from + (to - from) * mix
  }
}

/** Chosen interpolation only, not recovered source rotation direction. Half-turn ties go negative. */
function compilePhaseDeltas(a: MechanismInput, b: MechanismInput): Float64Array {
  const deltas = new Float64Array(a.phases.length)
  for (let i = 0; i < deltas.length; i++) {
    // Reduce each finite endpoint first so their difference cannot overflow.
    let delta = (b.phases[i]! % PHASE_PERIOD_RAD - a.phases[i]! % PHASE_PERIOD_RAD) % PHASE_PERIOD_RAD
    if (delta >= Math.PI) delta -= PHASE_PERIOD_RAD
    else if (delta < -Math.PI) delta += PHASE_PERIOD_RAD
    deltas[i] = delta
  }
  return deltas
}

function finite(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label} must be finite.`)
  return value
}

function requireCamera(camera: CameraRecord, label: string): void {
  if (camera.positionMetres?.length !== 3 || camera.quaternion?.length !== 4) throw new Error(`${label}: invalid camera dimensions.`)
  camera.positionMetres.forEach((value) => finite(value, label))
  camera.quaternion.forEach((value) => finite(value, label))
  if (Math.abs(Math.hypot(...camera.quaternion) - 1) > 0.002) throw new Error(`${label}: camera quaternion is not normalized.`)
  if (finite(camera.verticalFovDegrees, label) <= 0 || camera.verticalFovDegrees >= 179) throw new Error(`${label}: invalid field of view.`)
  if (camera.principalPointViewportPixels) {
    if (camera.principalPointViewportPixels.length !== 2) throw new Error(`${label}: invalid principal point.`)
    camera.principalPointViewportPixels.forEach((value) => finite(value, label))
  }
}

interface CompiledTrackView {
  observation: CompactSourceView
  input: MechanismInput | null
  sourceAssembly: SourceAssemblyState
  unobservedInputFields: InputField[]
  inputChangesToNext: boolean
  phaseDeltasToNext: Float64Array | null
  cameraInterpolatesToNext: boolean
}
interface CompiledTrackFrame {
  observation: CompactSourceFrame
  required: boolean
  available: boolean
  lastReadableIndex: number
  shotStartSeconds: number
  shotEndSeconds: number
  continuousToNext: boolean
  layout: SourceLayoutEntry[]
  views: CompiledTrackView[]
}
interface TrackBuffer {
  sample: SourceSample
  views: Map<string, PlaybackView>
}

interface PublicationBanks {
  buffers: [TrackBuffer, TrackBuffer]
  publishedIndex: 0 | 1
  preparedIndex: 0 | 1 | null
  inputValidated: WeakSet<CompiledTrackView>
  diagnostic: DiagnosticSourceLease | null
}

export interface SourcePublicationReference {
  readonly approximationMessage: string
  prepareAt(timeSeconds: number): SourceSample
  /** Cold-start fallback only; never replace an already displayed held pose. */
  prepareLastReadableAt(timeSeconds: number): SourceSample | null
  /** Initial unreadable exposure only: draw the first authored readable pose, never claim its source time. */
  prepareInitialReadable(): SourceSample | null
  commitPrepared(): SourceSample
}

export interface DiagnosticSourcePublicationSnapshot {
  /** Actual method-entry attempts, including rejected calls; the bank records publication. */
  prepareCount: number
  commitCount: number
  publishedBank: 0 | 1
  /** Owned copy of the actual published diagnostic bank, never a live buffer. */
  publishedSample: SourceSample
}
export interface DiagnosticSourcePublicationState {
  readonly sourceProof: false
  readonly sourceAcceptance: false
  readonly prepareAtImplementation: string
  readonly commitPreparedImplementation: string
  /** Detached banks using the same production preparation/commit implementation. */
  readonly reference: SourcePublicationReference
  snapshot(): DiagnosticSourcePublicationSnapshot
}
interface DiagnosticSourceLease {
  samples: readonly SourceSample[]
  prepareCount: number
  commitCount: number
}

function buffer(): TrackBuffer {
  return {
    sample: { state: 'unavailable', timeSeconds: 0, reason: '', views: [], mechanicalProvenance: null, unobservedInputFields: [], nativeGeometryAssumptions: [] },
    views: new Map(),
  }
}

/**
 * Source-following choices are renderable without a per-part source certificate. They are
 * never promoted to matched history, even when a separately rendered stage report passes.
 */
export class CompactVideoReference {
  readonly kind = 'compact-source-track' as const
  readonly coverageMessage: string
  readonly approximationMessage: string
  readonly stageStatus = UNMEASURED_STAGES
  /** Probe-only exact native line endpoints never enter the source point/role census. */
  readonly landmarkProbeAnchors: readonly LandmarkAnchor[]
  private readonly frames: CompiledTrackFrame[]
  private readonly firstReadableIndex: number
  private readonly publication: PublicationBanks = { buffers: [buffer(), buffer()], publishedIndex: 0, preparedIndex: null, inputValidated: new WeakSet(), diagnostic: null }
  private readonly qa = new Quaternion()
  private readonly qb = new Quaternion()
  private readonly qi = new Quaternion()
  private readonly pose = createMechanismPose()

  constructor(readonly data: CompactSourceTrack, video: Video) {
    if (data.kind !== 'compact-source-track' || data.schemaVersion !== 1 || data.source?.videoId !== video.id || data.source.sha256 !== video.sourceSha256) throw new Error('Compact track footage identity does not match this video.')
    if (data.source.width !== SOURCE_WIDTH || data.source.height !== SOURCE_HEIGHT || Math.abs(data.source.durationSeconds - video.durationSeconds) > 0.05) throw new Error('Compact track dimensions or duration do not match the footage.')
    if (data.model?.sha256 !== MECHANISM_DATA.provenance.modelSha256 || data.model.sourceCommit !== MECHANISM_DATA.provenance.sourceCommit || data.model.units !== 'metres') throw new Error('Compact track targets a different native CAD export.')
    if (!Array.isArray(data.frames) || !data.frames.length || !Array.isArray(data.anchors) || !Array.isArray(data.shots)) throw new Error('Compact source track has no sample or shot record.')
    if (!data.coverage || !['complete', 'blocked'].includes(data.coverage.status) || !Array.isArray(data.coverage.blockers) || data.coverage.requiredEveryIntegerSecond !== true) throw new Error('Compact source coverage must retain every-second measurements.')
    validateNativeGeometryAssumptions(data.nativeGeometryAssumptions)
    const blockers = data.coverage.blockers
    const preview = blockers.slice(0, 2).map((reason) => reason.length > 220 ? `${reason.slice(0, 217)}...` : reason).join(' ')
    this.coverageMessage = blockers.length ? `${blockers.length} source coverage ${blockers.length === 1 ? 'issue' : 'issues'} remain. ${preview}${blockers.length > 2 || blockers.some((reason) => reason.length > 220) ? ' Full details remain in the source track and verification report.' : ''}` : ''
    if (data.sourceMeasurements && (!['incomplete', 'partial'].includes(data.sourceMeasurements.status) || !Array.isArray(data.sourceMeasurements.blockers))) throw new Error('Source measurement availability must remain explicit.')
    const measurementBlockers = data.sourceMeasurements?.blockers ?? []
    const measurementPreview = measurementBlockers.slice(0, 2).map((reason) => reason.length > 220 ? `${reason.slice(0, 217)}...` : reason).join(' ')
    const measurementStatus = data.sourceMeasurements?.status ?? 'unmeasured'
    this.approximationMessage = `Approximate source-following; chosen feasible inputs, not recovered history. Rendered stages 50% / 20% / 10% / 5%: unmeasured; measurement report required.${data.coverage.status === 'blocked' ? ` Runtime coverage incomplete: ${this.coverageMessage}` : ''} Source measurements ${measurementStatus}${measurementBlockers.length ? `: ${measurementBlockers.length} issues. ${measurementPreview} Full details remain in the source track/report.` : '.'}`
    const shotMap = new Map(data.shots.map((shot) => [shot.id, shot]))
    if (shotMap.size !== data.shots.length) throw new Error('Compact source shot IDs must be unique.')
    for (let i = 0; i < data.shots.length; i++) {
      const shot = data.shots[i]!
      if (finite(shot.startSeconds, 'Shot start') < 0 || finite(shot.endSeconds, 'Shot end') <= shot.startSeconds
        || shot.endSeconds > data.source.durationSeconds + 0.05 || (i > 0 && shot.startSeconds < data.shots[i - 1]!.endSeconds - 1e-6)) throw new Error('Compact source shot intervals must be ordered and nonoverlapping.')
    }
    const anchorIds = new Set(data.anchors.map((anchor) => anchor.id))
    if (anchorIds.size !== data.anchors.length) throw new Error('Compact anchor IDs must be unique.')
    let previous = -Infinity, lastReadableIndex = -1, firstReadableIndex = -1
    this.frames = data.frames.map((frame, frameIndex) => {
      const t = finite(frame.timeSeconds, 'Compact sample time')
      const pts = frame.decodedTimeSeconds === null ? null : finite(frame.decodedTimeSeconds, 'Decoded source PTS')
      const shot = shotMap.get(frame.shotId)
      if (t <= previous || t < 0 || t > data.source.durationSeconds + 0.05 || pts !== null && (pts < 0 || pts > data.source.durationSeconds + 0.05 || Math.abs(pts - t) > 0.5)) throw new Error('Compact source timestamps must be ordered and within the 0.5s timing tolerance.')
      if (pts === null && (frame.sourceSampleUnavailable !== true || frame.sourceImage || frame.views?.length !== 0 || frame.landmarks?.length !== 0)
        || pts !== null && frame.sourceSampleUnavailable !== undefined) throw new Error('A missing source PTS must remain explicitly unavailable without fabricated views or landmarks.')
      previous = t
      if (!shot || t < shot.startSeconds - 1e-6 || t > shot.endSeconds + 1e-6) throw new Error(`Compact source sample ${t}s is outside its shot.`)
      if (pts !== null && (pts < shot.startSeconds || pts >= shot.endSeconds)) throw new Error(`${video.id}@${t}s: decoded PTS ${pts} is outside its own half-open source shot ${shot.id}.`)
      if (!['machine', 'non-machine', 'transition', 'unobservable'].includes(frame.classification)) throw new Error(`Unknown source classification at ${t}s.`)
      if (frame.sourceMachineRequirement !== undefined && frame.sourceMachineRequirement !== 'required') throw new Error('Compact tracks cannot weaken required source-machine coverage.')
      if (!Array.isArray(frame.views) || !Array.isArray(frame.landmarks)) throw new Error(`Missing source layout or landmarks at ${t}s.`)
      const sourceRequired = physicalSourceFrameRequired(frame, frame.sourceMachineRequirement === 'required' || frame.classification === 'machine' || (frame.classification === 'non-machine' ? shot.hasCorrespondingMachine === true : shot.hasCorrespondingMachine !== false))
      if (new Set(frame.views.map((view) => view.id)).size !== frame.views.length) throw new Error(`Duplicate source view at ${t}s.`)
      for (const view of frame.views) {
        const error = sourceVisibilityError(frame, view)
        if (error) throw new Error(`${video.id}@${t}s/${view.id}: ${error}`)
        if (view.sourceVisibility && frame.sourceImage?.sourceSha256 !== data.source.sha256) throw new Error('Source visibility audit belongs to different footage.')
      }
      const requiredViews = requiredSourceViews(frame)
      const required = sourceRequired && (frame.views.length === 0 || requiredViews.length > 0)
      const layout: SourceLayoutEntry[] = requiredViews.map((view) => {
        if (view.rectSourcePixels?.length !== 4) throw new Error(`Invalid source viewport at ${t}s.`)
        view.rectSourcePixels.forEach((value) => finite(value, 'Source viewport'))
        const [x, y, w, h] = view.rectSourcePixels
        if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > SOURCE_WIDTH || y + h > SOURCE_HEIGHT || !['native', 'horizontal-mirror'].includes(view.presentation)) throw new Error(`Source viewport exceeds the source frame at ${t}s.`)
        return { viewId: view.id, rectSourcePixels: view.rectSourcePixels, presentation: view.presentation, composite: view.composite ?? OPAQUE_COMPOSITE, resolvedImagePlaneWarp: view.imagePlaneWarp ?? null }
      })
      try {
        assertSourceCompositeWeights(frame.views)
      } catch (error) {
        throw new Error(`${video.id}@${t}s (decoded PTS ${pts ?? 'unavailable'}): ${error instanceof Error ? error.message : String(error)}`)
      }
      for (const landmark of frame.landmarks) {
        if (!anchorIds.has(landmark.anchorId) || !frame.views.some((view) => view.id === (landmark.viewId ?? 'main')) || landmark.pixel?.length !== 2 || landmark.status !== 'observed' || !['fit', 'check'].includes(landmark.role)) throw new Error(`Invalid source landmark at ${t}s.`)
        landmark.pixel.forEach((value) => finite(value, 'Source landmark pixel'))
        if (finite(landmark.uncertaintyPx, 'Source landmark uncertainty') < 0) throw new Error('Source landmark uncertainty cannot be negative.')
      }
      const views = requiredViews.map((view) => {
        const label = `${video.id}@${t}s/${view.id}`
        let sourceAssembly: SourceAssemblyState
        try {
          sourceAssembly = compileSourceAssemblyState(view.sourceAssembly).state
          if (sourceAssembly.kind === 'source-assembly' && sourceAssembly.provenance.videoId !== data.source.videoId) throw new Error('Source assembly witness must belong to this footage.')
        } catch (error) {
          throw new Error(`${video.id}@${t}s/${view.id}: ${error instanceof Error ? error.message : String(error)}`)
        }
        if (view.sourceViewIds !== undefined || view.sourceViewMappingEvidence !== undefined) {
          if (!Array.isArray(view.sourceViewIds) || !view.sourceViewIds.length
            || view.sourceViewIds.some((id) => typeof id !== 'string' || !id.trim())
            || new Set(view.sourceViewIds).size !== view.sourceViewIds.length
            || typeof view.sourceViewMappingEvidence !== 'string' || !view.sourceViewMappingEvidence.trim()) throw new Error(`${label}: source-view mapping needs nonempty unique identities and explicit evidence.`)
        }
        if (view.camera) requireCamera(view.camera, label)
        if (!view.provenance || view.provenance.kind !== 'chosen-feasible' || !view.provenance.evidence?.trim() || !Array.isArray(view.provenance.unobservedInputFields)
          || new Set(view.provenance.unobservedInputFields).size !== view.provenance.unobservedInputFields.length || view.provenance.unobservedInputFields.some((field) => !INPUT_FIELDS.includes(field))) throw new Error(`${label}: chosen inputs need explicit unobserved provenance.`)
        const input = view.input === null ? null : compileInput(view.input, label)
        const unobservedInputFields = [...view.provenance.unobservedInputFields]
        if (input?.setup.counterHeightM === null && !unobservedInputFields.includes('setup.counterHeightM')) unobservedInputFields.push('setup.counterHeightM')
        if (view.cameraProvenance && (!['source-fit', 'source-transfer', 'source-informed-framing'].includes(view.cameraProvenance.kind) || !view.cameraProvenance.evidence?.trim() || !view.cameraProvenance.family?.trim())) throw new Error(`${label}: camera family provenance is incomplete.`)
        if (view.cameraContinuityFamily !== undefined && !view.cameraContinuityFamily.trim()) throw new Error(`${label}: camera continuity family is empty.`)
        if (view.cameraInterpolation !== undefined && (typeof view.cameraInterpolation !== 'string' || !['continuous-shot', 'held'].includes(view.cameraInterpolation))) throw new Error(`${label}: unknown camera interpolation policy.`)
        if (view.cameraInterpolation === 'continuous-shot' && (typeof view.cameraInterpolationEvidence !== 'string' || !view.cameraInterpolationEvidence.trim())) throw new Error(`${label}: continuous-shot camera interpolation needs explicit evidence.`)
        return { observation: view, input, sourceAssembly, unobservedInputFields, inputChangesToNext: false, phaseDeltasToNext: null as Float64Array | null, cameraInterpolatesToNext: false }
      })
      const available = pts !== null && (!required || views.length > 0 && views.every((view) => view.input !== null && view.observation.camera !== null))
      if (required && available) {
        lastReadableIndex = frameIndex
        if (firstReadableIndex < 0) firstReadableIndex = frameIndex
      }
      return { observation: frame, required, layout, views, lastReadableIndex, shotStartSeconds: shot.startSeconds, shotEndSeconds: shot.endSeconds, continuousToNext: false, available }
    })
    this.firstReadableIndex = firstReadableIndex
    for (let i = 0; i < this.frames.length - 1; i++) {
      const from = this.frames[i]!
      const next = this.frames[i + 1]!
      from.continuousToNext = from.available && next.available && from.required && next.required && next.observation.shotId === from.observation.shotId
        && next.views.length === from.views.length && equalRecord(from.layout, next.layout)
        && from.views.every((view, index) => view.observation.id === next.views[index]!.observation.id && view.input?.gearing === next.views[index]!.input?.gearing
          && (view.input?.setup.counterHeightM === null) === (next.views[index]!.input?.setup.counterHeightM === null))
      if (from.continuousToNext) {
        for (let index = 0; index < from.views.length; index++) {
          from.views[index]!.inputChangesToNext = !equalRecord(from.views[index]!.observation.input, next.views[index]!.observation.input)
          const a = from.views[index]!
          const b = next.views[index]!
          if (a.inputChangesToNext) a.phaseDeltasToNext = compilePhaseDeltas(a.input!, b.input!)
          const provenance = a.observation.cameraProvenance
          const nextProvenance = b.observation.cameraProvenance
          a.cameraInterpolatesToNext = a.observation.cameraInterpolation !== 'held' && b.observation.cameraInterpolation !== 'held'
            && typeof a.observation.cameraContinuityFamily === 'string'
            && a.observation.cameraContinuityFamily === b.observation.cameraContinuityFamily
            && provenance !== undefined && nextProvenance !== undefined
            && (provenance.kind !== 'source-informed-framing' && nextProvenance.kind !== 'source-informed-framing'
              || a.observation.cameraInterpolation === 'continuous-shot' && b.observation.cameraInterpolation === 'continuous-shot')
            && provenance.family === nextProvenance.family
        }
      }
    }
    const lineAnchors = new Map<string, LandmarkAnchor>()
    for (const frame of this.frames) for (const view of frame.views) for (const line of view.observation.nativeLineChecks ?? []) {
      for (const station of NATIVE_LINE_STATIONS) {
        const id = nativeLineEndpointId(view.observation.id, line.id, station)
        const [a, b] = line.partLocalLineMetres
        const anchor: LandmarkAnchor = { id, partPath: line.partPath, partLocalMetres: [
          a[0] + station * (b[0] - a[0]), a[1] + station * (b[1] - a[1]), a[2] + station * (b[2] - a[2]),
        ] }
        const prior = lineAnchors.get(id)
        if (anchorIds.has(id) || prior && !equalRecord(prior, anchor)) throw new Error('Native line diagnostic endpoint identity conflicts with another geometry/source point.')
        lineAnchors.set(id, anchor)
      }
    }
    this.landmarkProbeAnchors = lineAnchors.size ? [...data.anchors, ...lineAnchors.values()] : data.anchors
  }

  private indexAt(timeSeconds: number): number {
    const t = Math.max(0, Math.min(this.data.source.durationSeconds, finite(timeSeconds, 'Playback time')))
    let lo = 0
    let hi = this.frames.length
    while (lo < hi) {
      const mid = (lo + hi) >>> 1
      if (this.frames[mid]!.observation.timeSeconds <= t) lo = mid + 1
      else hi = mid
    }
    return Math.max(0, lo - 1)
  }

  getState(timeSeconds: number): ReferenceState {
    const t = Math.max(0, Math.min(this.data.source.durationSeconds, finite(timeSeconds, 'Playback time')))
    const frame = this.frames[this.indexAt(t)]!
    return this.stateFor(t, frame)
  }

  private stateFor(t: number, frame: CompiledTrackFrame): ReferenceState {
    if (frame.observation.timeSeconds > t || t < frame.shotStartSeconds || t > frame.shotEndSeconds || t === frame.shotEndSeconds && t < this.data.source.durationSeconds || !frame.available) return 'unavailable'
    return frame.required ? 'approximate' : 'hold-last-readable'
  }

  prepareAt(timeSeconds: number): SourceSample {
    return this.prepareAtIn(timeSeconds, this.publication)
  }

  prepareLastReadableAt(timeSeconds: number): SourceSample | null {
    return this.prepareLastReadableAtIn(timeSeconds, this.publication)
  }

  prepareInitialReadable(): SourceSample | null {
    return this.prepareInitialReadableIn(this.publication)
  }

  private prepareInitialReadableIn(publication: PublicationBanks): SourceSample | null {
    return this.firstReadableIndex < 0 ? null
      : this.prepareAtIn(this.frames[this.firstReadableIndex]!.observation.timeSeconds, publication)
  }

  private prepareLastReadableAtIn(timeSeconds: number, publication: PublicationBanks): SourceSample | null {
    const index = this.frames[this.indexAt(timeSeconds)]!.lastReadableIndex
    if (index < 0) return null
    const frame = this.frames[index]!
    return frame.observation.timeSeconds <= timeSeconds ? this.prepareAtIn(frame.observation.timeSeconds, publication) : null
  }

  private prepareAtIn(timeSeconds: number, publication: PublicationBanks): SourceSample {
    const diagnostic = publication.diagnostic
    if (diagnostic) diagnostic.prepareCount++
    publication.preparedIndex = null
    const nextIndex = publication.publishedIndex === 0 ? 1 : 0
    const { sample, views: pool } = publication.buffers[nextIndex]
    const t = Math.max(0, Math.min(this.data.source.durationSeconds, finite(timeSeconds, 'Playback time')))
    const index = this.indexAt(t)
    const from = this.frames[index]!
    const next = this.frames[index + 1]
    sample.timeSeconds = t
    sample.state = this.stateFor(t, from)
    sample.views.length = 0
    sample.mechanicalProvenance = null
    sample.unobservedInputFields.length = 0
    sample.nativeGeometryAssumptions = this.data.nativeGeometryAssumptions ?? EMPTY_GEOMETRY_ASSUMPTIONS
    sample.reason = sample.state === 'approximate' ? this.approximationMessage
      : sample.state === 'hold-last-readable' ? 'Source physical ROIs are individually policy-excluded, noncontributing, or no physical view is shown; retain the preceding displayed pose, not a current source match.' : from.observation.unavailableReason ?? 'This required source interval has no available camera and complete feasible input.'
    if (sample.state === 'approximate') {
      const continuous = from.continuousToNext
      const mix = continuous ? (t - from.observation.timeSeconds) / (next!.observation.timeSeconds - from.observation.timeSeconds) : 0
      for (let i = 0; i < from.views.length; i++) {
        const a = from.views[i]!
        const camera = a.observation.camera!
        let out = pool.get(a.observation.id)
        if (!out) {
          out = {
            id: a.observation.id, camera: { positionMetres: [0, 0, 0], quaternion: [0, 0, 0, 1], verticalFovDegrees: 45, principalPointViewportPixels: [0, 0] },
            rectSourcePixels: [0, 0, SOURCE_WIDTH, SOURCE_HEIGHT], presentation: 'native', input: createMechanismInput(),
            sourceAssembly: a.sourceAssembly,
            mechanicalProvenance: 'chosen', unobservedInputFields: [],
            sourceSampling: { fromTimeSeconds: 0, toTimeSeconds: 0, mix: 0, selection: 'decoded-exposure', cameraSelection: 'decoded-exposure' },
            authoredImagePlaneWarp: null, sourceLayout: [], nativeGeometryAssumptions: [],
          }
          pool.set(out.id, out)
        }
        const b = continuous ? next!.views[i]! : null
        if (b && a.inputChangesToNext && mix > 0) {
          blendInput(out.input, a.input!, b.input!, a.phaseDeltasToNext!, mix)
          // A changed/interpolated input must be feasible before any published state changes.
          solveSourceInput(out.input, EMPTY_CONSTRAINTS, this.pose)
        } else {
          copyInput(out.input, a.input!)
          if (!publication.inputValidated.has(a)) {
            solveSourceInput(out.input, EMPTY_CONSTRAINTS, this.pose)
            publication.inputValidated.add(a)
          }
        }
        // No declared feasible assembly interpolation API: hold the exact source exposure.
        // Machine.update solves this descriptor against its freshly normal-solved baseline.
        out.sourceAssembly = a.sourceAssembly
        out.rectSourcePixels = a.observation.rectSourcePixels
        out.presentation = a.observation.presentation
        out.composite = a.observation.composite ?? OPAQUE_COMPOSITE
        out.imagePlaneWarp = a.observation.imagePlaneWarp
        out.authoredImagePlaneWarp = a.observation.imagePlaneWarp ?? null
        out.sourceLayout = from.layout
        out.nativeGeometryAssumptions = sample.nativeGeometryAssumptions
        out.unobservedInputFields = a.unobservedInputFields
        out.sourceSampling.fromTimeSeconds = from.observation.timeSeconds
        out.sourceSampling.toTimeSeconds = b ? next!.observation.timeSeconds : from.observation.timeSeconds
        out.sourceSampling.mix = mix
        out.sourceSampling.selection = b ? 'continuous' : 'decoded-exposure'
        const cameraNext = b && a.cameraInterpolatesToNext ? b.observation.camera : null
        out.sourceSampling.cameraSelection = cameraNext ? 'continuous' : 'decoded-exposure'
        for (let k = 0; k < 3; k++) out.camera.positionMetres[k] = camera.positionMetres[k]! + (cameraNext ? (cameraNext.positionMetres[k]! - camera.positionMetres[k]!) * mix : 0)
        this.qa.fromArray(camera.quaternion)
        if (cameraNext) {
          this.qb.fromArray(cameraNext.quaternion)
          this.qi.slerpQuaternions(this.qa, this.qb, mix).toArray(out.camera.quaternion)
        } else this.qa.toArray(out.camera.quaternion)
        out.camera.verticalFovDegrees = camera.verticalFovDegrees + (cameraNext ? (cameraNext.verticalFovDegrees - camera.verticalFovDegrees) * mix : 0)
        for (let k = 0; k < 2; k++) {
          const centre = (a.observation.imagePlaneWarp?.unwarpedViewportPixels[k] ?? a.observation.rectSourcePixels[k + 2]!) / 2
          const value = camera.principalPointViewportPixels?.[k] ?? centre
          out.camera.principalPointViewportPixels[k] = value + (cameraNext ? ((cameraNext.principalPointViewportPixels?.[k] ?? centre) - value) * mix : 0)
        }
        sample.views.push(out)
        sample.mechanicalProvenance = 'chosen'
        for (const field of a.unobservedInputFields) if (!sample.unobservedInputFields.includes(field)) sample.unobservedInputFields.push(field)
      }
    }
    if (diagnostic) {
      let lo = 0
      let hi = diagnostic.samples.length
      while (lo < hi) {
        const mid = (lo + hi) >>> 1
        if (diagnostic.samples[mid]!.timeSeconds <= t) lo = mid + 1
        else hi = mid
      }
      if (lo === 0) throw new Error('No diagnostic source exposure is available at this playback time.')
      const held = structuredClone(diagnostic.samples[lo - 1]!)
      sample.state = held.state
      sample.reason = held.reason
      sample.views = held.views
      sample.mechanicalProvenance = held.mechanicalProvenance
      sample.unobservedInputFields = held.unobservedInputFields
      sample.nativeGeometryAssumptions = held.nativeGeometryAssumptions
    }
    publication.preparedIndex = nextIndex
    return sample
  }

  commitPrepared(): SourceSample {
    return this.commitPreparedIn(this.publication)
  }

  private commitPreparedIn(publication: PublicationBanks): SourceSample {
    if (publication.diagnostic) publication.diagnostic.commitCount++
    if (publication.preparedIndex === null) throw new Error('No successfully prepared compact source sample is available.')
    publication.publishedIndex = publication.preparedIndex
    publication.preparedIndex = null
    return publication.buffers[publication.publishedIndex].sample
  }

  at(timeSeconds: number): SourceSample {
    this.prepareAt(timeSeconds)
    return this.commitPrepared()
  }

  /**
   * Diagnostic-only materialization in detached banks. Compiled observations are
   * shared read-only; pools and feasibility-validation caches belong to each
   * publication. Preparation is synchronous, so solver/quaternion scratch never
   * escapes a call or crosses an asynchronous callback boundary.
   */
  async withDiagnosticSamples<T>(samples: readonly SourceSample[], run: (state: DiagnosticSourcePublicationState) => T | Promise<T>): Promise<T> {
    if (!Array.isArray(samples) || !samples.length) throw new Error('Diagnostic source publication requires exposure samples.')
    let previous = -Infinity
    const ownedSamples = samples.map((sample) => {
      const time = finite(sample.timeSeconds, 'Diagnostic source exposure time')
      if (time < 0 || time > this.data.source.durationSeconds || time <= previous) throw new Error('Diagnostic source exposures must be ordered within the current footage.')
      previous = time
      return structuredClone(sample)
    })
    const lease: DiagnosticSourceLease = { samples: ownedSamples, prepareCount: 0, commitCount: 0 }
    const publication: PublicationBanks = { buffers: [buffer(), buffer()], publishedIndex: 0, preparedIndex: null, inputValidated: new WeakSet(), diagnostic: lease }
    let active = true
    const requirePublication = () => { if (!active) throw new Error('The diagnostic source publication lease is no longer active.') }
    const scopedReference: SourcePublicationReference = Object.freeze({
      approximationMessage: this.approximationMessage,
      prepareAt: (timeSeconds: number) => { requirePublication(); return this.prepareAtIn(timeSeconds, publication) },
      prepareLastReadableAt: (timeSeconds: number) => { requirePublication(); return this.prepareLastReadableAtIn(timeSeconds, publication) },
      prepareInitialReadable: () => { requirePublication(); return this.prepareInitialReadableIn(publication) },
      commitPrepared: () => { requirePublication(); return this.commitPreparedIn(publication) },
    })
    const state: DiagnosticSourcePublicationState = Object.freeze({
      sourceProof: false,
      sourceAcceptance: false,
      reference: scopedReference,
      prepareAtImplementation: this.prepareAtIn.toString(),
      commitPreparedImplementation: this.commitPreparedIn.toString(),
      snapshot: (): DiagnosticSourcePublicationSnapshot => {
        requirePublication()
        return {
          prepareCount: lease.prepareCount,
          commitCount: lease.commitCount,
          publishedBank: publication.publishedIndex,
          publishedSample: structuredClone(publication.buffers[publication.publishedIndex].sample),
        }
      },
    })
    try {
      return await run(state)
    } finally {
      active = false
    }
  }
}
