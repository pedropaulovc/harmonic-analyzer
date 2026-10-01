import { Matrix4, Quaternion } from 'three'
import { deriveImagePlaneWarp, projectImagePlanePixel } from './image-plane-homography'
import { createMechanismInput, createMechanismPose, MECHANISM_DATA, type MechanismInput, type MechanismPose } from './mechanics'
import { assertSourceCompositeWeights, type CameraRecord, type ImagePlaneWarp, type PartOverride, type SourceComposite, type SourceLayoutEntry, type SourceView } from './scene'
import { compileInput, compileWitness, equalRecord, inputValue, solveSourceInput, validateVisibilityProof, validateNativeGeometryAssumptions, validateNativeLineAxisBiasComponents, SETUP_KEYS, type InputField, type MechanicalObservation, type MechanicalProvenance, type SerializedInput, type SourceConstraint, type SourceImageIdentity, type SourceImagePlaneWarp, type NativeLineCheck, type SourceContourCheck, type NativeGeometryAssumption, type SourceNonIdentifiableFixedPart } from './source-witness'
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
export type CameraReference = { timeSeconds: number; viewId: string | null } | { rigId: string; phaseIndex: number }
export type CameraEvidence =
  | { kind: 'direct-fit' }
  | { kind: 'shared-rigid-sequence'; rigId: string; phaseIndex: number }
  | { kind: 'source-registered'; reference: CameraReference; sourceToViewportPixels: [number, number, number, number, number, number]; sourceImage: SourceImageIdentity; referenceSourceImage: SourceImageIdentity; correspondences: Array<{ id: string; role: 'fit' | 'check'; sourcePixel: [number, number]; viewportPixel: [number, number]; method: string; uncertaintyPx: number; measurementEvidence: { sourceImage: SourceImageIdentity; evidence: string } }> }
  | { kind: 'source-image-plane-registered'; reference: CameraReference }
interface SourceCameraRig {
  id: string
  kind: 'turntable'
  phaseCount: 71
  worldToReferenceCameraCV: { rotationVectorRad: [number, number, number]; translationMetres: [number, number, number]; focalPixels: number }
  axisPointWorldMetres: [number, number, number]
  phaseImages: Array<{ phaseIndex: number; sourceImage: SourceImageIdentity }>
  measurements: Array<Landmark & { phaseIndex: number }>
  independentLoopEvidence: { sourceSha256: string; evidence: string; sourceFrameMap: Array<{ sourceImage: SourceImageIdentity; referencePhaseIndex: number; phaseAccepted: boolean }> }
}
export interface ObservedView {
  id: string
  rectSourcePixels: [number, number, number, number]
  presentation: 'native' | 'horizontal-mirror'
  camera: ObservedCamera | null
  cameraEvidence?: CameraEvidence
  cameraFit?: Record<string, unknown>
  imagePlaneWarp?: SourceImagePlaneWarp
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
  sourceMachineRequirement?: 'required'
  landmarks: Landmark[]
  unavailable: { anchorId: string; reason: string }[]
  mechanicalState: MechanicalObservation
  camera: ObservedCamera | null
  cameraEvidence?: CameraEvidence
  cameraFit?: Record<string, unknown>
  imagePlaneWarp?: SourceImagePlaneWarp
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
  sourceCameraRigs?: SourceCameraRig[]
  nativeGeometryAssumptions?: NativeGeometryAssumption[]
}
interface CompiledView {
  observation: ObservedView
  resolvedImagePlaneWarp: ImagePlaneWarp | null
  sourceLayout: readonly SourceLayoutEntry[]
  input: MechanismInput | null
  pose: MechanismPose | null
  blendedConstraints: [SourceConstraint[], SourceConstraint[]]
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
  sourceSampling: { fromTimeSeconds: number; toTimeSeconds: number; mix: number; selection: 'continuous' | 'decoded-exposure' }
  authoredImagePlaneWarp: SourceImagePlaneWarp | null
  sourceLayout: readonly SourceLayoutEntry[]
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

function exactFields(value: unknown, fields: readonly string[], label: string): void {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== fields.length
    || fields.some((field) => !Object.hasOwn(value, field))) throw new Error(`${label}: missing or unknown fields.`)
}

function requireImage(image: SourceImageIdentity | undefined, sha256: string, label: string): asserts image is SourceImageIdentity {
  const digest = image?.pixelFormat === 'bgr8' ? 'sha256Bgr8' : image?.pixelFormat === 'gray8' ? 'sha256Gray8' : null
  if (!digest) throw new Error(`${label}: exact decoded source image identity is required.`)
  exactFields(image, ['frameIndex', 'width', 'height', 'sourceSha256', 'pixelFormat', digest], label)
  if (image!.sourceSha256 !== sha256 || image!.width !== SOURCE_WIDTH || image!.height !== SOURCE_HEIGHT
    || !Number.isInteger(image!.frameIndex) || image!.frameIndex < 0
    || typeof image![digest as keyof SourceImageIdentity] !== 'string'
    || !/^[a-f0-9]{64}$/.test(image![digest as keyof SourceImageIdentity] as string)) throw new Error(`${label}: stale or invalid decoded image identity.`)
}

function frameObservations(frame: ReferenceFrame): ObservedView[] {
  return frame.views ?? [{
    id: 'main', rectSourcePixels: [0, 0, SOURCE_WIDTH, SOURCE_HEIGHT], presentation: 'native',
    camera: frame.camera, cameraEvidence: frame.cameraEvidence, cameraFit: frame.cameraFit, imagePlaneWarp: frame.imagePlaneWarp,
    mechanicalState: frame.mechanicalState, partOverrides: frame.partOverrides, composite: frame.composite,
    compositeEvidence: frame.compositeEvidence, nativeLineChecks: frame.nativeLineChecks, sourceContourChecks: frame.sourceContourChecks,
  }]
}

interface ResolvedReferenceCamera {
  camera: CameraRecord
  viewport: readonly [number, number]
  sourceImage: SourceImageIdentity
  rect: readonly [number, number, number, number]
}

/** Resolve only the new branch and its independently qualified ordinary ancestors. */
function compileImagePlaneWarps(data: ReferenceFile, observations: readonly ObservedView[][]): Map<ObservedView, ImagePlaneWarp> {
  const contexts = new Map<string, { frame: ReferenceFrame; view: ObservedView }>()
  const resolved = new Map<string, ResolvedReferenceCamera>()
  const active = new Set<string>()
  const warps = new Map<ObservedView, ImagePlaneWarp>()
  const rigs = new Map((data.sourceCameraRigs ?? []).map((rig) => [rig.id, rig]))
  if (rigs.size !== (data.sourceCameraRigs?.length ?? 0)) throw new Error('Duplicate source camera rig identity.')
  for (let i = 0; i < data.frames.length; i++) {
    const frame = data.frames[i]!
    for (const view of observations[i]!) {
      const key = `${frame.timeSeconds}/${view.id}`
      if (!view.id?.trim() || contexts.has(key)) throw new Error('Duplicate or missing source view identity.')
      contexts.set(key, { frame, view })
    }
  }
  function matchingCamera(actual: ObservedCamera, expected: CameraRecord, viewport: readonly [number, number], label: string): void {
    requireCamera(actual, label)
    const delta = (a: readonly number[], b: readonly number[]) => Math.hypot(...a.map((value, i) => value - b[i]!))
    const quaternionError = Math.min(delta(actual.quaternion, expected.quaternion), Math.hypot(...actual.quaternion.map((value, i) => value + expected.quaternion[i]!)))
    const principal = actual.principalPointViewportPixels ?? [viewport[0] / 2, viewport[1] / 2]
    if (actual.status !== 'passed' || actual.heldOutMaxPx > LANDMARK_LIMIT_PX || delta(actual.positionMetres, expected.positionMetres) > 1e-6
      || quaternionError > 1e-6 || Math.abs(actual.verticalFovDegrees - expected.verticalFovDegrees) > 1e-7
      || delta(principal, expected.principalPointViewportPixels!) > 1e-4) throw new Error(`${label}: camera does not preserve independently calibrated pose/FOV/intrinsics.`)
  }
  function resolveRig(reference: { rigId: string; phaseIndex: number }, label: string): ResolvedReferenceCamera {
    const rig = rigs.get(reference.rigId)
    if (!rig || rig.kind !== 'turntable' || rig.phaseCount !== 71 || !Number.isInteger(reference.phaseIndex) || reference.phaseIndex < 0 || reference.phaseIndex >= 71
      || rig.phaseImages?.length !== 71 || new Set(rig.phaseImages.map((phase) => phase.phaseIndex)).size !== 71
      || rig.independentLoopEvidence?.sourceSha256 !== data.source.sha256 || !rig.independentLoopEvidence.evidence?.trim()
      || (rig as unknown as Record<string, unknown>).imagePlaneWarp !== undefined) throw new Error(`${label}: missing independently identifiable ordinary rig phase.`)
    const image = rig.phaseImages.find((phase) => phase.phaseIndex === reference.phaseIndex)?.sourceImage
    requireImage(image, data.source.sha256, label)
    const checks = rig.measurements?.filter((measurement) => measurement.role === 'check' && measurement.phaseIndex === reference.phaseIndex) ?? []
    const fits = rig.measurements?.filter((measurement) => measurement.role === 'fit') ?? []
    if (fits.length < 6 || checks.length < 2 || new Set(checks.map((check) => check.anchorId)).size < 2) throw new Error(`${label}: rig lacks independent fit and phase interior held-out evidence.`)
    const parameters = rig.worldToReferenceCameraCV
    if (parameters?.rotationVectorRad?.length !== 3 || parameters.translationMetres?.length !== 3 || rig.axisPointWorldMetres?.length !== 3) throw new Error(`${label}: invalid rig camera dimensions.`)
    parameters.rotationVectorRad.forEach((value) => finite(value, label)); parameters.translationMetres.forEach((value) => finite(value, label)); rig.axisPointWorldMetres.forEach((value) => finite(value, label))
    const focal = finite(parameters.focalPixels, label)
    if (focal <= 0) throw new Error(`${label}: rig focal must be positive.`)
    const angle = Math.hypot(...parameters.rotationVectorRad), vector = parameters.rotationVectorRad
    const rotation = new Matrix4()
    if (angle > 1e-15) {
      const x = vector[0] / angle, y = vector[1] / angle, z = vector[2] / angle, c = Math.cos(angle), s = Math.sin(angle), t = 1 - c
      rotation.set(t*x*x+c,t*x*y-s*z,t*x*z+s*y,0,t*x*y+s*z,t*y*y+c,t*y*z-s*x,0,t*x*z-s*y,t*y*z+s*x,t*z*z+c,0,0,0,0,1)
    }
    rotation.multiply(new Matrix4().makeRotationY(2 * Math.PI * reference.phaseIndex / 71))
    const r = rotation.elements, translation = parameters.translationMetres
    const position = rig.axisPointWorldMetres.map((value, i) => value - (r[i * 4]! * translation[0] + r[i * 4 + 1]! * translation[1] + r[i * 4 + 2]! * translation[2])) as [number, number, number]
    rotation.transpose().multiply(new Matrix4().makeScale(1, -1, -1))
    const quaternion = new Quaternion().setFromRotationMatrix(rotation).toArray() as [number, number, number, number]
    return { camera: { positionMetres: position, quaternion, verticalFovDegrees: 2 * Math.atan(SOURCE_HEIGHT / (2 * focal)) * 180 / Math.PI, principalPointViewportPixels: [960, 540] }, viewport: [1920, 1080], rect: [0, 0, 1920, 1080], sourceImage: image }
  }
  function parent(reference: CameraReference, label: string): ResolvedReferenceCamera {
    if (Object.hasOwn(reference ?? {}, 'rigId')) {
      exactFields(reference, ['rigId', 'phaseIndex'], label)
      return resolveRig(reference as { rigId: string; phaseIndex: number }, label)
    }
    exactFields(reference, ['timeSeconds', 'viewId'], label)
    const ref = reference as { timeSeconds: number; viewId: string | null }
    finite(ref.timeSeconds, label)
    if (ref.viewId !== null && (typeof ref.viewId !== 'string' || !ref.viewId.trim())) throw new Error(`${label}: invalid explicit parent view identity.`)
    const key = `${ref.timeSeconds}/${ref.viewId ?? 'main'}`, context = contexts.get(key)
    if (!context || context.view.imagePlaneWarp !== undefined || (context.view.cameraEvidence ?? context.frame.cameraEvidence)?.kind === 'source-image-plane-registered'
      || context.view.presentation !== 'native') throw new Error(`${label}: missing, mirrored or warped reference parent.`)
    return resolve(key)
  }
  function resolve(key: string): ResolvedReferenceCamera {
    const cached = resolved.get(key)
    if (cached) return cached
    if (active.has(key)) throw new Error('Camera registration dependency cycle.')
    const context = contexts.get(key)
    if (!context?.view.camera) throw new Error(`Missing independently calibrated camera ${key}.`)
    const observedCamera = context.view.camera
    active.add(key)
    const { frame, view } = context, label = `Source camera ${key}`, evidence = view.cameraEvidence ?? frame.cameraEvidence ?? { kind: 'direct-fit' as const }
    requireImage(frame.sourceImage, data.source.sha256, label)
    requireCamera(observedCamera, label)
    if (observedCamera.status !== 'passed' || observedCamera.heldOutMaxPx > LANDMARK_LIMIT_PX) throw new Error(`${label}: reference camera is not independently qualified.`)
    let result: ResolvedReferenceCamera
    if (evidence.kind === 'direct-fit') {
      exactFields(evidence, ['kind'], label)
      if (view.imagePlaneWarp !== undefined) throw new Error(`${label}: ordinary cameras cannot author an image-plane warp.`)
      const landmarks = frame.landmarks.filter((landmark) => (landmark.viewId ?? 'main') === view.id)
      const fits = landmarks.filter((landmark) => landmark.role === 'fit'), checks = landmarks.filter((landmark) => landmark.role === 'check')
      const fitIds = new Set(fits.map((landmark) => landmark.anchorId)), checkIds = new Set(checks.map((landmark) => landmark.anchorId))
      if (fitIds.size < 6 || checkIds.size < 2 || checks.some((check) => fitIds.has(check.anchorId))) throw new Error(`${label}: direct parent needs six fits and two disjoint independent held-outs.`)
      result = { camera: { positionMetres: [...observedCamera.positionMetres], quaternion: [...observedCamera.quaternion], verticalFovDegrees: observedCamera.verticalFovDegrees, principalPointViewportPixels: observedCamera.principalPointViewportPixels ? [...observedCamera.principalPointViewportPixels] : [view.rectSourcePixels[2] / 2, view.rectSourcePixels[3] / 2] }, viewport: [view.rectSourcePixels[2], view.rectSourcePixels[3]], rect: view.rectSourcePixels, sourceImage: frame.sourceImage }
    } else {
      if (Object.keys(view.cameraFit ?? {}).length || Object.keys(frame.cameraFit ?? {}).length) throw new Error(`${label}: derived camera cannot specify a new fit.`)
      const reference = evidence.kind === 'shared-rigid-sequence' ? { rigId: evidence.rigId, phaseIndex: evidence.phaseIndex } : evidence.reference
      const base = parent(reference, label)
      let camera = base.camera, viewport: readonly [number, number] = [view.rectSourcePixels[2], view.rectSourcePixels[3]]
      if (evidence.kind === 'shared-rigid-sequence') {
        exactFields(evidence, ['kind', 'rigId', 'phaseIndex'], label)
        const phase = rigs.get(evidence.rigId)?.independentLoopEvidence.sourceFrameMap.find((entry) => equalRecord(entry.sourceImage, frame.sourceImage))
        if (!equalRecord(view.rectSourcePixels, base.rect) || view.presentation !== 'native' || !phase?.phaseAccepted || phase.referencePhaseIndex !== evidence.phaseIndex || view.imagePlaneWarp !== undefined) throw new Error(`${label}: actual exposure does not establish claimed ordinary rig phase.`)
      } else if (evidence.kind === 'source-registered') {
        exactFields(evidence, ['kind', 'reference', 'sourceToViewportPixels', 'sourceImage', 'referenceSourceImage', 'correspondences'], label)
        if (view.imagePlaneWarp !== undefined || !equalRecord(evidence.sourceImage, frame.sourceImage) || !equalRecord(evidence.referenceSourceImage, base.sourceImage)) throw new Error(`${label}: stale or mixed ordinary source registration.`)
        const affine = evidence.sourceToViewportPixels
        if (!Array.isArray(affine) || affine.length !== 6) throw new Error(`${label}: invalid affine dimensions.`)
        affine.forEach((value) => finite(value, label))
        if (affine[0] <= 0 || Math.abs(affine[1]) > 1e-9 || Math.abs(affine[3]) > 1e-9 || Math.abs(affine[4] - affine[0]) > 1e-9) throw new Error(`${label}: ordinary affine must be positive uniform without shear/rotation.`)
        const ids = new Set<string>(), pixels = new Set<string>(), targets = new Set<string>(), roles = { fit: 0, check: 0 }
        for (const correspondence of evidence.correspondences ?? []) {
          const source = correspondence.sourcePixel, target = correspondence.viewportPixel
          if (!correspondence.id?.trim() || ids.has(correspondence.id) || !['fit', 'check'].includes(correspondence.role) || !Array.isArray(source) || source.length !== 2 || !Array.isArray(target) || target.length !== 2
            || !equalRecord(correspondence.measurementEvidence?.sourceImage, frame.sourceImage) || !correspondence.measurementEvidence.evidence?.trim()) throw new Error(`${label}: independent affine correspondences required.`)
          source.forEach((value) => finite(value, label)); target.forEach((value) => finite(value, label))
          const a = JSON.stringify(source), b = JSON.stringify(target)
          if (pixels.has(a) || targets.has(b) || finite(correspondence.uncertaintyPx, label) < 0 || correspondence.uncertaintyPx > LANDMARK_LIMIT_PX
            || Math.hypot(affine[0] * source[0] + affine[2] - target[0], affine[0] * source[1] + affine[5] - target[1]) > LANDMARK_LIMIT_PX) throw new Error(`${label}: disjoint affine check failed.`)
          ids.add(correspondence.id); pixels.add(a); targets.add(b); roles[correspondence.role]++
        }
        if (roles.fit < 2 || roles.check < 2) throw new Error(`${label}: affine reference lacks fit/held-out evidence.`)
        const focal = base.viewport[1] / (2 * Math.tan(camera.verticalFovDegrees * Math.PI / 360)) * affine[0]
        camera = { ...camera, verticalFovDegrees: 2 * Math.atan(viewport[1] / (2 * focal)) * 180 / Math.PI, principalPointViewportPixels: camera.principalPointViewportPixels!.map((value, i) => affine[0] * (value + base.rect[i]!) + affine[i === 0 ? 2 : 5]) as [number, number] }
      } else if (evidence.kind === 'source-image-plane-registered') {
        exactFields(evidence, ['kind', 'reference'], label)
        const authored = view.imagePlaneWarp
        exactFields(authored, ['kind', 'unwarpedViewportPixels', 'cornersSourcePixels', 'sourceImage', 'referenceSourceImage', 'cornerMeasurementEvidence', 'correspondences'], label)
        if (authored!.kind !== 'homography' || !equalRecord(authored!.sourceImage, frame.sourceImage) || !equalRecord(authored!.referenceSourceImage, base.sourceImage)) throw new Error(`${label}: stale or mixed image-plane exposure identity.`)
        const warp = deriveImagePlaneWarp(authored!.unwarpedViewportPixels, authored!.cornersSourcePixels, label)
        viewport = warp.unwarpedViewportPixels
        const scale = viewport[0] / base.viewport[0], scaleY = viewport[1] / base.viewport[1]
        if (!Number.isFinite(scale) || scale <= 0 || Math.abs(scale - scaleY) > 1e-9 * Math.max(scale, scaleY)) throw new Error(`${label}: unwarped viewport must uniformly scale reference aspect/intrinsics.`)
        camera = { ...camera, principalPointViewportPixels: camera.principalPointViewportPixels!.map((value) => value * scale) as [number, number] }
        const measurement = (record: SourceImagePlaneWarp['cornerMeasurementEvidence']) => {
          if (!record || !equalRecord(record.sourceImage, frame.sourceImage) || !equalRecord(record.referenceSourceImage, base.sourceImage) || typeof record.evidence !== 'string' || !record.evidence.trim()) throw new Error(`${label}: actual target/reference measurement evidence required.`)
        }
        measurement(authored!.cornerMeasurementEvidence)
        const ids = new Set<string>(), pixels = new Set<string>(), targets = new Set<string>(), checks: [number, number][] = []
        if (!Array.isArray(authored!.correspondences)) throw new Error(`${label}: actual independent interior correspondences are required.`)
        for (const correspondence of authored!.correspondences) {
          exactFields(correspondence, ['id', 'role', 'referencePixelSource', 'pixelSource', 'method', 'uncertaintyPx', 'measurementEvidence'], label)
          const source = correspondence.referencePixelSource, target = correspondence.pixelSource
          if (typeof correspondence.id !== 'string' || !correspondence.id.trim() || ids.has(correspondence.id) || !['fit', 'check'].includes(correspondence.role)
            || !['manual', 'optical-flow', 'image-edge', 'template-match'].includes(correspondence.method) || !Array.isArray(source) || source.length !== 2 || !Array.isArray(target) || target.length !== 2) throw new Error(`${label}: invalid independent homography correspondence.`)
          source.forEach((value) => finite(value, label)); target.forEach((value) => finite(value, label)); measurement(correspondence.measurementEvidence)
          const a = JSON.stringify(source), b = JSON.stringify(target), native: [number, number] = [(source[0] - base.rect[0]) * scale, (source[1] - base.rect[1]) * scale]
          if (pixels.has(a) || targets.has(b) || native[0] < 0 || native[0] >= viewport[0] || native[1] < 0 || native[1] >= viewport[1]
            || target[0] < 0 || target[0] >= SOURCE_WIDTH || target[1] < 0 || target[1] >= SOURCE_HEIGHT
            || finite(correspondence.uncertaintyPx, label) < 0 || correspondence.uncertaintyPx > LANDMARK_LIMIT_PX) throw new Error(`${label}: fit/check pairs must be disjoint actual image features.`)
          if (correspondence.role === 'check') {
            let direction = 0
            const inside = authored!.cornersSourcePixels.every((corner, i, corners) => {
              const next = corners[(i + 1) % 4]!
              const cross = (next[0] - corner[0]) * (target[1] - corner[1]) - (next[1] - corner[1]) * (target[0] - corner[0])
              if (Math.abs(cross) <= 1e-9 || (direction && Math.sign(cross) !== direction)) return false
              direction = Math.sign(cross)
              return true
            })
            if (native[0] === 0 || native[1] === 0 || !inside) throw new Error(`${label}: boundary/corner constraints are fits, not independent interior held-outs.`)
          }
          const predicted = projectImagePlanePixel(warp, native)
          if (Math.hypot(predicted[0] - target[0], predicted[1] - target[1]) + correspondence.uncertaintyPx > LANDMARK_LIMIT_PX) throw new Error(`${label}: actual interior image-plane error exceeds ${LANDMARK_LIMIT_PX}px including source uncertainty.`)
          ids.add(correspondence.id); pixels.add(a); targets.add(b)
          if (correspondence.role === 'check') checks.push(native)
        }
        if (checks.length < 2 || !checks.some((point, i) => checks.slice(i + 1).some((other) => Math.hypot(point[0] - other[0], point[1] - other[1]) >= 0.1 * Math.hypot(...viewport)))) throw new Error(`${label}: two spread independently measured interior checks required.`)
        warps.set(view, warp)
      } else throw new Error(`${label}: unknown camera evidence branch.`)
      matchingCamera(observedCamera, camera, viewport, label)
      result = { camera, viewport, rect: view.rectSourcePixels, sourceImage: frame.sourceImage }
    }
    active.delete(key); resolved.set(key, result)
    return result
  }
  for (const [key, { frame, view }] of contexts) {
    const kind = (view.cameraEvidence ?? frame.cameraEvidence)?.kind
    if (view.imagePlaneWarp !== undefined || kind === 'source-image-plane-registered') {
      if (kind !== 'source-image-plane-registered') throw new Error(`${key}: authored warp requires explicit image-plane camera evidence.`)
      resolve(key)
    }
  }
  return warps
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
 * Physical matching is required unless the shot census explicitly exempts it. An actual-source
 * per-frame required annotation can only strengthen coverage; it never grants an absence waiver.
 * Must agree with sourceNeedsMachine in scripts/verify-reference.mjs.
 */
function requiresMachine(classification: Classification, hasCorrespondingMachine: boolean | undefined, sourceMachineRequirement?: 'required'): boolean {
  if (sourceMachineRequirement === 'required' || classification === 'machine') return true
  if (classification === 'non-machine') return hasCorrespondingMachine === true
  return hasCorrespondingMachine !== false
}

function viewMatchable(view: CompiledView): boolean {
  const { camera, mechanicalState } = view.observation
  return camera !== null && camera.status === 'passed' && camera.heldOutMaxPx <= LANDMARK_LIMIT_PX
    && view.input !== null && ['observed', 'constrained'].includes(mechanicalState?.status) && mechanicalState.visiblePoseCompleteness === 'complete'
}

function newPlaybackView(view: CompiledView, nativeGeometryAssumptions: readonly NativeGeometryAssumption[], bufferIndex: 0 | 1): PlaybackView {
  const camera = view.observation.camera!
  const proof = view.observation.mechanicalState.status === 'observed' ? view.observation.mechanicalState.visibilityProof : view.observation.mechanicalState.runtimeWitness!.visibilityProof
  return {
    id: view.observation.id,
    rectSourcePixels: [...view.observation.rectSourcePixels],
    presentation: view.observation.presentation,
    authoredImagePlaneWarp: view.observation.imagePlaneWarp ?? null,
    imagePlaneWarp: view.resolvedImagePlaneWarp ?? undefined,
    sourceLayout: view.sourceLayout,
    camera: {
      positionMetres: [...camera.positionMetres], quaternion: [...camera.quaternion],
      verticalFovDegrees: camera.verticalFovDegrees,
      principalPointViewportPixels: camera.principalPointViewportPixels ? [...camera.principalPointViewportPixels] : [
        (view.resolvedImagePlaneWarp?.unwarpedViewportPixels[0] ?? view.observation.rectSourcePixels[2]) / 2,
        (view.resolvedImagePlaneWarp?.unwarpedViewportPixels[1] ?? view.observation.rectSourcePixels[3]) / 2,
      ],
    },
    input: createMechanismInput(),
    partOverrides: view.observation.partOverrides ?? noOverrides,
    composite: view.observation.composite ?? { mode: 'opaque' },
    compositeEvidence: view.observation.compositeEvidence ?? null,
    mechanicalProvenance: view.observation.mechanicalState.status === 'constrained' ? 'constrained' : 'observed',
    unobservedInputFields: view.observation.mechanicalState.runtimeWitness?.unobservedInputFields ?? [],
    constraintSummary: view.blendedConstraints[bufferIndex],
    visibilityProof: proof,
    sourceNonIdentifiableFixedParts: proof.sourceNonIdentifiableFixedParts,
    continuity: view.observation.mechanicalState.runtimeWitness?.continuity ?? null,
    sourceSampling: { fromTimeSeconds: 0, toTimeSeconds: 0, mix: 0, selection: view.resolvedImagePlaneWarp ? 'decoded-exposure' : 'continuous' },
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
  const ai = a.input!
  const bi = b.input!
  if (av.id !== bv.id || av.presentation !== bv.presentation || !equalRecord(av.composite ?? { mode: 'opaque' }, bv.composite ?? { mode: 'opaque' })
    || !equalRecord(av.partOverrides ?? noOverrides, bv.partOverrides ?? noOverrides)
    || !equalRecord(a.sourceLayout, b.sourceLayout)) return false
  if (a.resolvedImagePlaneWarp || b.resolvedImagePlaneWarp) {
    if (!equalRecord(a.resolvedImagePlaneWarp, b.resolvedImagePlaneWarp) || !equalRecord(av.camera, bv.camera)
      || !equalRecord(av.cameraEvidence, bv.cameraEvidence) || !equalRecord(av.imagePlaneWarp?.referenceSourceImage, bv.imagePlaneWarp?.referenceSourceImage)
      || !equalRecord(av.mechanicalState.runtimeWitness?.constraints ?? [], bv.mechanicalState.runtimeWitness?.constraints ?? [])
      || ai.crankTurns !== bi.crankTurns || ai.gearing !== bi.gearing || ai.magnification !== bi.magnification) return false
    for (let i = 0; i < 20; i++) if (ai.amplitudes[i] !== bi.amplitudes[i] || ai.phases[i] !== bi.phases[i]) return false
    for (const key of setupKeys) if (ai.setup[key] !== bi.setup[key]) return false
  }
  const ap = av.mechanicalState.status === 'observed' ? av.mechanicalState.visibilityProof : av.mechanicalState.runtimeWitness!.visibilityProof
  const bp = bv.mechanicalState.status === 'observed' ? bv.mechanicalState.visibilityProof : bv.mechanicalState.runtimeWitness!.visibilityProof
  if (!equalRecord(ap.sourceNonIdentifiableFixedParts, bp.sourceNonIdentifiableFixedParts)) return false
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
  if (!aw || !bw || !aw.continuity || !bw.continuity || (!a.resolvedImagePlaneWarp && av.presentation !== 'native') || !equalRecord(aw.continuity, bw.continuity)
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

interface PlaybackBuffer {
  sample: SourceSample
  pools: Map<string, PlaybackView>
}

function newPlaybackBuffer(): PlaybackBuffer {
  return {
    sample: { state: 'unavailable', timeSeconds: 0, reason: '', views: [], mechanicalProvenance: null, unobservedInputFields: [], constraintSummary: {}, nativeGeometryAssumptions: [], sourceNonIdentifiableFixedParts: {} },
    pools: new Map<string, PlaybackView>(),
  }
}

/** Measured reference samples are consumed identically by playback and frame review. */
export class VideoReference {
  readonly data: ReferenceFile
  readonly coverageMessage: string
  readonly sourcePartOverrides: readonly PartOverride[]
  private readonly frames: CompiledFrame[]
  private readonly buffers: readonly [PlaybackBuffer, PlaybackBuffer] = [newPlaybackBuffer(), newPlaybackBuffer()]
  private publishedIndex: 0 | 1 = 0
  private preparedIndex: 0 | 1 | null = null
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
    const observationsByFrame = data.frames.map(frameObservations)
    const imagePlaneWarps = compileImagePlaneWarps(data, observationsByFrame)
    data.frames.forEach((reference, index) => {
      const t = finite(reference.timeSeconds, 'Reference time')
      finite(reference.decodedTimeSeconds, 'Decoded reference time')
      if (t <= previous || t < 0 || t > video.durationSeconds + 0.05) throw new Error('Reference timestamps must be strictly increasing within the source duration.')
      previous = t
      if (!classifications[reference.classification]) throw new Error(`Unknown source classification at ${t}s.`)
      if (Object.hasOwn(reference, 'sourceMachineRequirement') && reference.sourceMachineRequirement !== 'required') throw new Error(`Invalid source machine requirement at ${t}s; only required can strengthen source coverage.`)
      const shot = shotsById.get(reference.shotId)
      if (!shot) throw new Error(`Unknown source shot at ${t}s.`)
      const requirement = requiresMachine(reference.classification, shot.hasCorrespondingMachine, reference.sourceMachineRequirement) ? 'required' : 'not-required'
      const observations = observationsByFrame[index]!
      const sourceLayout: SourceLayoutEntry[] = observations.map((observation) => ({
        viewId: observation.id, rectSourcePixels: [...observation.rectSourcePixels], presentation: observation.presentation,
        composite: observation.composite ?? { mode: 'opaque' }, resolvedImagePlaneWarp: imagePlaneWarps.get(observation) ?? null,
      }))
      assertSourceCompositeWeights(sourceLayout.map((entry) => ({ rectSourcePixels: entry.rectSourcePixels, presentation: entry.presentation, composite: entry.composite ?? undefined, imagePlaneWarp: entry.resolvedImagePlaneWarp ?? undefined })))
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
        for (const line of observation.nativeLineChecks ?? []) {
          validateNativeLineAxisBiasComponents(line, observation.imagePlaneWarp != null, `${label}/${line.id}`)
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
            if (Object.keys(composite).some((key) => !['mode', 'groupId', 'imageLayerId', 'opacity'].includes(key)) || typeof composite.groupId !== 'string' || !composite.groupId.trim()
              || typeof composite.imageLayerId !== 'string' || !composite.imageLayerId.trim() || finite(composite.opacity, label) < 0 || composite.opacity > 1 || !observation.compositeEvidence?.trim()) throw new Error(`${label}: explicit measured composite image identity and opacity evidence are required.`)
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
            imagePlaneWarp: observation.imagePlaneWarp ?? null, resolvedImagePlaneWarp: imagePlaneWarps.get(observation) ?? null, sourceLayout,
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
        const constraints = state.runtimeWitness?.constraints ?? []
        return { observation, resolvedImagePlaneWarp: imagePlaneWarps.get(observation) ?? null, sourceLayout, input, pose, blendedConstraints: [
          constraints.map((constraint) => ({ ...constraint })), constraints.map((constraint) => ({ ...constraint })),
        ] as [SourceConstraint[], SourceConstraint[]] }
      })
      const failed = views.find((view) => !viewMatchable(view))
      const matched = requirement === 'required' && views.length > 0 && !failed
      if (matched) {
        for (const view of views) {
          for (const bufferIndex of [0, 1] as const) {
            const pools = this.buffers[bufferIndex].pools
            if (!pools.has(view.observation.id)) pools.set(view.observation.id, newPlaybackView(view, data.nativeGeometryAssumptions ?? [], bufferIndex))
          }
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
      // A certified decoded exposure may be held only inside every current view's
      // explicit certificate. Point endpoints never authorize the gap or the tail.
      for (const view of current.views) {
        const state = view.observation.mechanicalState
        const proof = state.status === 'observed' ? state.visibilityProof : state.runtimeWitness!.visibilityProof
        const [start, end] = proof.binding.intervalSeconds
        if (t < start || t > end) {
          s.state = 'unavailable'
          return s
        }
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

  /** Prepare in the spare bank; failed caller preflight cannot poison published views. */
  prepareAt(timeSeconds: number): SourceSample {
    this.preparedIndex = null
    const bufferIndex = this.publishedIndex === 0 ? 1 : 0
    const sample = this.sampleAt(timeSeconds, bufferIndex)
    this.preparedIndex = bufferIndex
    return sample
  }

  /** Publish only after the caller's native/support preflight succeeds. */
  commitPrepared(): SourceSample {
    if (this.preparedIndex === null) throw new Error('No successfully prepared source sample is available.')
    this.publishedIndex = this.preparedIndex
    this.preparedIndex = null
    return this.buffers[this.publishedIndex].sample
  }

  /** Immediate publication for consumers that do not perform external preflight. */
  at(timeSeconds: number): SourceSample {
    this.prepareAt(timeSeconds)
    return this.commitPrepared()
  }

  private sampleAt(timeSeconds: number, bufferIndex: 0 | 1): SourceSample {
    const { sample, pools } = this.buffers[bufferIndex]
    const { t, index, state, from } = this.select(timeSeconds)
    const current = this.frames[index]!
    sample.timeSeconds = t
    sample.views.length = 0
    sample.mechanicalProvenance = null
    sample.unobservedInputFields.length = 0
    for (const id in sample.constraintSummary) delete sample.constraintSummary[id]
    for (const id in sample.sourceNonIdentifiableFixedParts) delete sample.sourceNonIdentifiableFixedParts[id]
    sample.nativeGeometryAssumptions = this.data.nativeGeometryAssumptions ?? []
    sample.state = state
    if (current.reference.timeSeconds > t) {
      sample.reason = `No source observation exists before ${current.reference.timeSeconds.toFixed(3)}s.`
      return sample
    }
    sample.reason = current.reason
    if (state === 'unavailable' && current.matched) sample.reason = 'The requested source time is outside its explicit decoded-exposure visibility certificate; no matched pose is asserted.'
    if (!from) return sample
    const next = state === 'matched' ? this.frames[index + 1] : undefined
    const continuous = next !== undefined && next.matched && next.reference.shotId === from.reference.shotId && from.views.length === next.views.length
    const mix = continuous ? Math.max(0, Math.min(1, (t - from.reference.timeSeconds) / (next.reference.timeSeconds - from.reference.timeSeconds))) : 0
    for (const view of from.views) {
      const a = view.observation
      const aCamera = a.camera!
      const aInput = view.input!
      const out = pools.get(a.id)!
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
      out.authoredImagePlaneWarp = a.imagePlaneWarp ?? null
      out.imagePlaneWarp = view.resolvedImagePlaneWarp ?? undefined
      out.sourceLayout = view.sourceLayout
      out.nativeLineChecks = a.nativeLineChecks ?? []
      out.sourceContourChecks = a.sourceContourChecks ?? []
      out.mechanicalProvenance = a.mechanicalState.status === 'constrained' ? 'constrained' : 'observed'
      out.unobservedInputFields = a.mechanicalState.runtimeWitness?.unobservedInputFields ?? []
      out.constraintSummary = view.blendedConstraints[bufferIndex]
      out.visibilityProof = a.mechanicalState.status === 'observed' ? a.mechanicalState.visibilityProof : a.mechanicalState.runtimeWitness!.visibilityProof
      out.sourceNonIdentifiableFixedParts = out.visibilityProof.sourceNonIdentifiableFixedParts
      out.visibilityProofEnd = null
      out.continuity = a.mechanicalState.runtimeWitness?.continuity ?? null
      out.sourceSampling.fromTimeSeconds = from.reference.timeSeconds
      out.sourceSampling.toTimeSeconds = from.reference.timeSeconds
      out.sourceSampling.mix = 0
      out.sourceSampling.selection = 'decoded-exposure'
      for (let k = 0; k < 4; k++) out.rectSourcePixels[k] = a.rectSourcePixels[k]!
      const camera = out.camera
      for (let k = 0; k < 3; k++) camera.positionMetres[k] = aCamera.positionMetres[k]!
      for (let k = 0; k < 4; k++) camera.quaternion[k] = aCamera.quaternion[k]!
      camera.verticalFovDegrees = aCamera.verticalFovDegrees
      camera.principalPointViewportPixels[0] = aCamera.principalPointViewportPixels?.[0] ?? (view.resolvedImagePlaneWarp?.unwarpedViewportPixels[0] ?? a.rectSourcePixels[2]) / 2
      camera.principalPointViewportPixels[1] = aCamera.principalPointViewportPixels?.[1] ?? (view.resolvedImagePlaneWarp?.unwarpedViewportPixels[1] ?? a.rectSourcePixels[3]) / 2
      // `next.matched` guarantees every next view has a passing camera and complete input.
      if (!view.resolvedImagePlaneWarp && mix > 0 && other && b?.camera && other.input && compatibleViews(view, other, t)) {
        blendInput(out.input, aInput, other.input, mix)
        blendConstraints(out.constraintSummary, a.mechanicalState.runtimeWitness?.constraints ?? [], b.mechanicalState.runtimeWitness?.constraints ?? [], mix)
        out.visibilityProofEnd = b.mechanicalState.status === 'observed' ? b.mechanicalState.visibilityProof : b.mechanicalState.runtimeWitness!.visibilityProof
        out.sourceSampling.toTimeSeconds = next!.reference.timeSeconds
        out.sourceSampling.mix = mix
        out.sourceSampling.selection = 'continuous'
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
      if (sample.mechanicalProvenance !== 'constrained') sample.mechanicalProvenance = out.mechanicalProvenance
      for (const field of out.unobservedInputFields) if (!sample.unobservedInputFields.includes(field)) sample.unobservedInputFields.push(field)
      sample.constraintSummary[out.id] = out.constraintSummary
      sample.sourceNonIdentifiableFixedParts[out.id] = out.sourceNonIdentifiableFixedParts
      sample.views.push(out)
    }
    return sample
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
