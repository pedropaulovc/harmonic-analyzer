import type { MechanismInput } from './mechanics'
import type { CameraRecord, ImagePlaneWarp, SourceLayoutEntry, SourceView } from './scene'
import type { InputField, NativeGeometryAssumption, SerializedInput } from './source-witness'
import { CompactVideoReference, type CompactSourceTrack } from './source-track'
import type { Video } from './video-catalog'

export { SOURCE_WIDTH, SOURCE_HEIGHT, LANDMARK_LIMIT_PX, SOURCE_STAGE_PERCENTAGES } from './source-track'

/** Approximation never asserts recovered history or a passed rendered tolerance stage. */
export type ReferenceState = 'approximate' | 'hold-last-readable' | 'unavailable'
export type Classification = 'machine' | 'non-machine' | 'transition' | 'unobservable'
export interface SourceIdentity {
  videoId: string
  sha256: string
  width: number
  height: number
  durationSeconds: number
  fps: number
}
export interface NativeModelIdentity {
  sha256: string
  sourceCommit: string
  units: 'metres'
  axes: string
}
export interface SourceShot {
  id: string
  startSeconds: number
  endSeconds: number
  classification: Classification
  hasCorrespondingMachine?: boolean
  reason: string
}
export interface ReferenceAnchor {
  id: string
  kind: 'section-center' | 'physical-feature'
  /** Unknown source motion remains null/absent, never an implied moving/fixed label. */
  motion?: 'fixed' | 'moving' | null
  partPath?: string
  /** Exact native template association for a declared runtime instance; local coordinates only. */
  runtimeTemplatePartPath?: string
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
  method: 'manual' | 'optical-flow' | 'image-edge' | 'template-match'
  uncertaintyPx: number
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
  mechanicalProvenance: 'chosen'
  unobservedInputFields: readonly InputField[]
  sourceSampling: {
    fromTimeSeconds: number
    toTimeSeconds: number
    mix: number
    selection: 'continuous' | 'decoded-exposure'
    cameraSelection: 'continuous' | 'decoded-exposure'
  }
  authoredImagePlaneWarp: ImagePlaneWarp | null
  sourceLayout: readonly SourceLayoutEntry[]
  nativeGeometryAssumptions: readonly NativeGeometryAssumption[]
}
export interface SourceSample {
  state: ReferenceState
  timeSeconds: number
  reason: string
  views: PlaybackView[]
  mechanicalProvenance: 'chosen' | null
  unobservedInputFields: InputField[]
  nativeGeometryAssumptions: readonly NativeGeometryAssumption[]
}

const compactFiles = import.meta.glob('../content/*.source-track.json', { import: 'default' })

export async function loadReference(video: Video): Promise<CompactVideoReference> {
  const load = compactFiles[`../content/${video.id}.source-track.json`]
  if (!load) throw new Error(`Compact source-following tracks are not available for ${video.title}.`)
  return new CompactVideoReference(await load() as CompactSourceTrack, video)
}

export function serializeInput(input: MechanismInput): SerializedInput {
  return { crankTurns: input.crankTurns, amplitudes: Array.from(input.amplitudes), phases: Array.from(input.phases), gearing: input.gearing, magnification: input.magnification, setup: { ...input.setup } }
}
