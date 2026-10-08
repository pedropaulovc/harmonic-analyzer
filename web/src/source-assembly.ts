import nativeInventory from '../content/v39-source/native-inventory.json'
import { BINDINGS } from './bindings'
import { MECHANISM_DATA } from './mechanics-data'
import type { PartOverride, Point3, Quaternion4 } from './scene'

/**
 * Source display/attachment state is NOT the operating mechanism's 51 inputs.
 * Only released v39 bodies and the two existing genuine T18 instances occur here.
 * Source: jfH-NbsmvD4 setup 43..74, service 170..230, photos 234..285,
 * pen assembly 565..649; approved CAD 81539e53 / raw 60a62a2e.
 *
 * Runtime contract: on EVERY view/state change, Machine.update first restores
 * every native part, performs the normal operating solve, then calls this solver
 * with those baseline world matrices and applies its existing simultaneous world
 * override block. Never feed last view's overridden matrices back into this
 * solver. Operating emits no overrides; it does not restore an already-mutated
 * scene by itself. The machine's normal reset is the sole restoration authority.
 * No geometry, topology, material, scale, camera or raster tolerance is changed.
 */
export interface SourceAssemblyProvenance {
  kind: 'chosen-feasible'
  videoId: 'jfH-NbsmvD4'
  frameIndex: number
  evidence: string
  /** Explicitly unknown source DOFs, not claims of recovered 3D history. */
  unobservedDegreesOfFreedom: readonly string[]
}
/** World pose of the named domain's native reference body, not an arbitrary mesh. */
export interface SourceRigidPose {
  positionMetres: Point3
  quaternion: Quaternion4
}
export type SourceAxialAttachment =
  | { attachment: 'installed' }
  | { attachment: 'withdrawing' | 'inserting'; travelMetres: number }
  | { attachment: 'held'; pose: SourceRigidPose }
export interface SourceCrankAssembly {
  /** MHA-024 tapered pin + its ring; NOT MHA-138 arm/hub seam key. */
  pin: SourceAxialAttachment
  /** MHA-137 reference; MHA-138 and the eye/anchor screw remain on this carrier. */
  carrier: SourceAxialAttachment
  /** The released keeper mesh is a monolithic drape, not 68 articulated links. */
  keeper?: { retainedAnchor: 'eye' | 'ring'; loopPose: SourceRigidPose; connectorPose: SourceRigidPose }
}
export type SourceRetainingNut =
  | { attachment: 'threaded'; releaseTurns: number }
  | { attachment: 'held'; pose: SourceRigidPose }
export interface SourceHangerAssembly {
  attachment: 'latched' | 'unlatched' | 'open' | 'returning'
  swingRad: number
  /** Rigid root-hinge gauge at the two actual rivets; not an elastic leaf solve. */
  hookReleaseRad: number
}
export type SourceGearId = 'T24' | 'T12' | 'T18-upper' | 'T18-crank'
export type SourceGearAttachment =
  | { attachment: 'upper' | 'crank'; phaseRad: number }
  | { attachment: 'upper-withdrawing' | 'crank-withdrawing' | 'upper-inserting' | 'crank-inserting'; phaseRad: number; travelMetres: number }
  | { attachment: 'held' | 'stored'; pose: SourceRigidPose }
export interface SourceGearAssembly {
  /** All four genuine bodies remain accounted for, including removed/held gears. */
  members: Readonly<Record<SourceGearId, SourceGearAttachment>>
}
export type SourceChainContact =
  | { kind: 'held'; joint: number; positionMetres: Point3 }
  | { kind: 'sprocket'; joint: number; gear: SourceGearId; tooth: number }
export interface SourceChainAssembly {
  attachment: 'slack-on-sprockets' | 'held-off-sprockets' | 'reinstalling'
  /** Exactly 68 hinge positions, in SOURCE_CHAIN_PART_PATHS connectivity order. */
  jointsMetres: readonly Point3[]
  /** Actual parallel hinge axes: a freely posed plane, not independent link roll. */
  planeNormal: Point3
  contacts: readonly SourceChainContact[]
}
export type SourceMeasuringTool =
  | { attachment: 'held' | 'withdrawn'; stickPose: SourceRigidPose; stopAtStickMetres: number }
  | { attachment: 'on-rocker' | 'bar-at-tool-end'; station: number; stopAtStickMetres: number }
  | { attachment: 'bar-setting'; station: number; stopAtStickMetres: number; barFootStationMetres: number }
export interface SourceManualBarSetting {
  station: number
  /** Literal foot-midpoint X relative to the current native rocker origin. */
  barFootStationMetres: number
}
export interface SourcePenAssembly {
  rod: SourceAxialAttachment
  /** Native authored block yaw is 45deg; this is a relative rotation about the
   * rod CENTRE line (local z=2.5mm), never about a camera or the rod corner. */
  yawDeltaRad: number
  vBlock: { attachment: 'rod' } | { attachment: 'held'; pose: SourceRigidPose }
  frame: { attachment: 'v-block' } | { attachment: 'inserting'; travelMetres: number } | { attachment: 'held'; pose: SourceRigidPose }
  marker: { attachment: 'frame' } | { attachment: 'inserting'; travelMetres: number } | { attachment: 'held'; pose: SourceRigidPose }
  /** A withdrawn rod releases its wire tie; the fixed hanger is not withdrawn. */
  wire: { attachment: 'connected' } | { attachment: 'released'; pose: SourceRigidPose }
}
export type SourceGearPhotoPair = 'T24-T12' | 'T18-T18' | 'T12-T24'
export interface SourceGearPhotograph {
  pair: SourceGearPhotoPair | 'four-gears'
  /** Explicit chosen world placement of the frontal display coordinate frame. */
  displayPose: SourceRigidPose
  /** Four-part photograph has no measured centres in the pair receipt. */
  fourGearPoses?: Readonly<Record<SourceGearId, SourceRigidPose>>
}
export type SourceAssemblyState =
  | { kind: 'operating' }
  | {
    kind: 'source-assembly'
    provenance: SourceAssemblyProvenance
    crank?: SourceCrankAssembly
    retainingNut?: SourceRetainingNut
    hanger?: SourceHangerAssembly
    gears?: SourceGearAssembly
    chain?: SourceChainAssembly
    measuringTool?: SourceMeasuringTool
    manualBars?: readonly SourceManualBarSetting[]
    pen?: SourcePenAssembly
    /** Genuine photograph subject scope only; all bodies still enter capture census. */
    photograph?: SourceGearPhotograph
  }
export interface SourceAssemblyContext {
  readonly partPaths: readonly string[]
  /** Exact copied current normal-solve world matrix; available only inside the
   * immediate Machine.update provider, never a retained/live matrix reference. */
  readWorldMatrix(partPath: string, out: Float64Array): boolean
  readVisibility(partPath: string, mode?: 'self' | 'effective'): boolean | null
  /** Exact current sprocketAt seat, selected from the actually mounted visible
   * native wheel, including root transforms; never an inactive T12/T24 body. */
  readGearSeatWorldMatrix(seat: 'upper' | 'crank', out: Float64Array): boolean
  readSeatedGearPartPath(seat: 'upper' | 'crank'): string | null
}
export interface CompiledSourceAssembly {
  readonly state: SourceAssemblyState
  readonly requiredPartPaths: readonly string[]
  /** Canonical physical descriptor, excluding support witness/provenance only. */
  readonly physicalKey: string
}
const ROOT = 'ha-harmonic-analyzer'
const DRIVE = `${ROOT}/dt-drive-train/`
const PAPER = `${ROOT}/pd-paper-drive/`
const PEN = `${ROOT}/pn-pen/`
const STICK = `${ROOT}/ha-measuring-stick-1`
const STOP = `${ROOT}/ha-measuring-stick-stop-1`
const HUB = `${DRIVE}dt-crank-hub-1`
const PIN = `${DRIVE}dt-crank-pin-1`
const NUT = `${PAPER}pd-transgear-thumbnut-1`
const ROD = `${PEN}pn-pen-rod-1`
const BLOCK = `${PEN}pn-pen-v-block-1`
const FRAME = `${PEN}pn-pen-frame-1`
const CHANNEL_CHASSIS = `${ROOT}/ch-channel`
const CHANNEL_STATIONS = Object.freeze(Array.from({ length: 20 }, (_, index) => Object.freeze({
  rocker: `${CHANNEL_CHASSIS}/ch-rocker-arm-${index + 1}`,
  bar: `${CHANNEL_CHASSIS}/ch-amplitude-bar-${index + 1}`,
  lever: `${CHANNEL_CHASSIS}/ch-channel-lever-${index + 1}`,
})))
const MARKER = `${PEN}pn-pen-marker-1`
const WIRE = `${PEN}pn-pen-wire-1`
const SPARE = `${PAPER}pd-transgear-removable-3`
const GEAR_IDS: readonly SourceGearId[] = ['T24', 'T12', 'T18-upper', 'T18-crank']
/** Sole declaration of the two genuine existing Scene/template instances. */
export const NATIVE_RUNTIME_INSTANCES: Readonly<Record<'upperMedium' | 'crankMedium', Readonly<{
  partPath: string
  templatePartPath: string
  localGeometryBinding: 'shared-decoded-native-template-attributes-and-index'
}>>> = Object.freeze({
  upperMedium: Object.freeze({ partPath: `${SPARE}@upper`, templatePartPath: SPARE, localGeometryBinding: 'shared-decoded-native-template-attributes-and-index' }),
  crankMedium: Object.freeze({ partPath: `${SPARE}@crank`, templatePartPath: SPARE, localGeometryBinding: 'shared-decoded-native-template-attributes-and-index' }),
})
export const SOURCE_GEAR_PART_PATHS: Readonly<Record<SourceGearId, string>> = Object.freeze({
  T24: `${PAPER}pd-transgear-removable-1`, T12: `${PAPER}pd-transgear-removable-2`,
  'T18-upper': NATIVE_RUNTIME_INSTANCES.upperMedium.partPath, 'T18-crank': NATIVE_RUNTIME_INSTANCES.crankMedium.partPath,
})
const GEAR_SEATS = ['upper', 'crank'] as const
const REST = new Map(nativeInventory.inventory.map(row => [row.path, row.world as readonly number[]]))
const NATIVE_PATHS = Object.freeze(nativeInventory.inventory.map(row => row.path))
if (nativeInventory.sha256 !== MECHANISM_DATA.provenance.modelSha256
  || nativeInventory.source.sourceCommit !== MECHANISM_DATA.provenance.sourceCommit
  || nativeInventory.identity.mapSha256 !== MECHANISM_DATA.provenance.nativeIdentityMapSha256
  || NATIVE_PATHS.length !== 457 || REST.size !== 457) throw new Error('Source assembly requires the exact released v39 native inventory, not an alias/rest fallback.')
function bindingGroup(id: string): readonly string[] {
  const binding = BINDINGS.find(value => value.id === id)
  if (!binding) throw new Error(`Source assembly has no canonical binding ${id}.`)
  const paths = NATIVE_PATHS.filter(path => binding.pattern.test(path))
  if (paths.length !== binding.expected) throw new Error(`Source assembly ${id}: native census ${paths.length}/${binding.expected}.`)
  return Object.freeze(paths)
}
const CRANK_CARRIER = Object.freeze([
  HUB, `${DRIVE}dt-crank-arm-1`, `${DRIVE}vn-crank-hub-pin-1`, `${DRIVE}dt-crank-pin-eye-1`,
  `${DRIVE}vn-fillister-screw-1`, `${DRIVE}dt-crank-handle-1`, `${DRIVE}dt-crank-handle-ferrule-1`,
  `${DRIVE}dt-crank-handle-butt-cup-1`, `${DRIVE}dt-crank-handle-pivot-screw-1`,
])
const CRANK_PIN = Object.freeze([PIN, `${DRIVE}dt-crank-pin-ring-1`])
const KEEPER = Object.freeze([`${DRIVE}vn-keeper-chain-1`, `${DRIVE}vn-keeper-chain-link-1`])
const HANGER = Object.freeze([...bindingGroup('paperHanger'), ...bindingGroup('paperKnob').filter(path => path !== NUT), ...bindingGroup('paperFeed')])
const HOOK = `${PAPER}pd-latch-hook-1`
const RIVETS = Object.freeze([`${PAPER}vn-latch-hook-rivet-1`, `${PAPER}vn-latch-hook-rivet-2`])
const FRAME_GROUP = Object.freeze([FRAME, `${PEN}vn-pen-set-screw-1`])
const NATIVE_LINKS = [...MECHANISM_DATA.paperDrive.chain.nativeLinks].sort((a, b) => a.restStationMm - b.restStationMm)
export const SOURCE_CHAIN_PART_PATHS = Object.freeze(NATIVE_LINKS.map(link => link.partPath))
if (NATIVE_LINKS.length !== 68) throw new Error('Source assembly requires exactly 68 native chain links.')
for (let i = 0; i < 68; i++) {
  const link = NATIVE_LINKS[i]!, next = NATIVE_LINKS[(i + 1) % 68]!
  if (link.nextPartPath !== next.partPath || !REST.has(link.partPath)
    || link.partPath.includes('outer') === next.partPath.includes('outer')) throw new Error('Source assembly native chain connectivity/alternation is incompatible.')
}
export const SOURCE_ASSEMBLY_GROUPS = Object.freeze({ crankCarrier: CRANK_CARRIER, crankPin: CRANK_PIN, keeper: KEEPER, hanger: HANGER, penFrame: FRAME_GROUP })
export const OPERATING_SOURCE_ASSEMBLY: CompiledSourceAssembly = Object.freeze({ state: Object.freeze({ kind: 'operating' }), requiredPartPaths: Object.freeze([]), physicalKey: '{"kind":"operating"}' })
const EMPTY_OVERRIDES: readonly PartOverride[] = Object.freeze([])
const CHORD_M = MECHANISM_DATA.paperDrive.chain.pitchMm / 1000
/** Numerical closure tolerance only (0.1 micrometre), NOT a native/raster waiver. */
const CONTACT_EPS_M = 1e-7
const THREAD_PITCH_M = 0.0254 / 20 // Actual MHA-126 1/4-20 UNC.
// Actual MHA-078 stud: tip station23.9mm, 45deg chamfer from6.22mm blank
// to the 1/4-20 basic minor diameter. Last full thread, not nut body length.
const STUD_TIP_CHAMFER_M = (0.00622 - (0.00635 - 1.082532 * THREAD_PITCH_M)) / 2
const NUT_THREAD_RELEASE_M = 0.0239 - STUD_TIP_CHAMFER_M
  - (rest(`${PAPER}pd-transgear-knob-shaft-1`)[14]! - rest(NUT)[14]!)
const ROD_AXIS_LOCAL: Point3 = [0, 0, 0.0024999999441206455]
const ZERO: Point3 = [0, 0, 0]
const X: Point3 = [1, 0, 0]
const Y: Point3 = [0, 1, 0]
const Z: Point3 = [0, 0, 1]
/** Actual raw geometry/datums, not source-measured world coordinates. */
export const SOURCE_ASSEMBLY_DATUMS = Object.freeze({
  rodAxisLocalMetres: ROD_AXIS_LOCAL,
  chainChordMetres: CHORD_M,
  nutThreadReleaseTurns: NUT_THREAD_RELEASE_M / THREAD_PITCH_M,
  stickLengthMetres: 0.20000000298023224,
  stickEngravedZeroMetres: 0.0575,
  stickEngravedDivisionMetres: 0.0142,
  /** Finite released-source service families; use held after shaft clearance. */
  pinWithdrawalMaxMetres: 0.04355,
  carrierWithdrawalMaxMetres: 0.0272,
  upperGearWithdrawalMaxMetres: 0.0177,
  crankGearWithdrawalMaxMetres: 0.0307,
  rodLengthMetres: 0.15000000596046448,
  stopCentreMinMetres: 0.006000001664460358,
  stopCentreMaxMetres: 0.19400000131577188,
  gearFaceLocalZMetres: 0.00279999990016222,
  gearOuterRadiusMetres: { T24: 0.02601769007742405, T12: 0.013742903247475624, T18: 0.019905386492609978 },
})
const DATUM_WORK: V3 = [0, 0, 0]
const KEEPER_CONNECTOR_LOCAL_ENDS: readonly Point3[] = [[-0.00285, 0, 0], [0.00285, 0, 0]]
const KEEPER_LOOP_LOCAL_ENDS: readonly V3[] = [[0, 0, 0], [0, 0, 0]]
for (let i = 0; i < 2; i++) {
  point(DATUM_WORK, rest(KEEPER[1]!), KEEPER_CONNECTOR_LOCAL_ENDS[i]!)
  inversePoint(KEEPER_LOOP_LOCAL_ENDS[i]!, rest(KEEPER[0]!), DATUM_WORK)
}
/** Reconstructed actual keeper contact, not a claim of a flexible live drape. */
const RING_DIAMETER_AT_HOLE = 0.0059375 - (0.0059375 - 0.005) * 0.0037 / 0.045
const RING_BOTTOM = 0.010 - (0.005 - Math.sqrt(0.005 ** 2 - (RING_DIAMETER_AT_HOLE / 2) ** 2)) / 2
export const SOURCE_KEEPER_ANCHORS = {
  eye: { partPath: `${DRIVE}dt-crank-pin-eye-1`, localPointMetres: [0, -0.00123, -0.002] as Point3, localAxis: X, loopLocalPointMetres: [0, 0, 0] as V3, loopLocalAxis: [0, 0, 0] as V3 },
  ring: { partPath: `${DRIVE}dt-crank-pin-ring-1`, localPointMetres: [RING_BOTTOM - 0.00077, 0, 0] as Point3, localAxis: Y, loopLocalPointMetres: [0, 0, 0] as V3, loopLocalAxis: [0, 0, 0] as V3 },
}
for (const anchor of Object.values(SOURCE_KEEPER_ANCHORS)) {
  point(DATUM_WORK, rest(anchor.partPath), anchor.localPointMetres)
  inversePoint(anchor.loopLocalPointMetres, rest(KEEPER[0]!), DATUM_WORK)
  direction(DATUM_WORK, rest(anchor.partPath), anchor.localAxis)
  point(anchor.loopLocalAxis, rest(KEEPER[0]!), ZERO)
  for (let i = 0; i < 3; i++) anchor.loopLocalAxis[i] = anchor.loopLocalAxis[i]! + DATUM_WORK[i]!
  inversePoint(anchor.loopLocalAxis, rest(KEEPER[0]!), anchor.loopLocalAxis)
  const length = Math.hypot(...anchor.loopLocalAxis)
  for (let i = 0; i < 3; i++) anchor.loopLocalAxis[i] = anchor.loopLocalAxis[i]! / length
}
freeze(SOURCE_KEEPER_ANCHORS)
export const SOURCE_GEAR_PHOTO_FRAMING = Object.freeze({
  sourceFrameIndex: 7343, verticalFovDegrees: 28,
  principalPointViewportPixels: [320, 180] as const,
  photographStartSeconds: 234.10053333333335, platenPanelsStartSeconds: 239.30573333333334,
})
/** Source centres and withheld second radii: raw frame7343 (not7393), actual
 * native face centres, chosen frontal depth/clock gauge. Not GPU fit acceptance. */
export const SOURCE_GEAR_PHOTOGRAPHS = Object.freeze({
  'T24-T12': { ids: ['T24', 'T12'] as const, rectSourcePixels: [0, 0, 640, 360] as const,
    centresSourcePixels: [[385.82862393751435, 150.02710774178726], [477.80490600641906, 265.16918844566715]] as const,
    pixelsPerMetre: 2982.5130940843546, cameraDistanceMetres: 0.24205780335663243, secondRadiusResidualPixels: 0.04631723423280931 },
  'T18-T18': { ids: ['T18-upper', 'T18-crank'] as const, rectSourcePixels: [0, 360, 640, 360] as const,
    centresSourcePixels: [[348.694179172351, 484.1643929058663], [440.72778913883207, 599.4312656214497]] as const,
    pixelsPerMetre: 2981.8040999116574, cameraDistanceMetres: 0.24211535830198946, secondRadiusResidualPixels: 0.731935761467355 },
  'T12-T24': { ids: ['T12', 'T24'] as const, rectSourcePixels: [0, 720, 640, 360] as const,
    centresSourcePixels: [[347.8680602382558, 822.7012811867835], [439.55449807387265, 938.1296170405619]] as const,
    pixelsPerMetre: 3024.6784432515965, cameraDistanceMetres: 0.23868341100760115, secondRadiusResidualPixels: 2.032759805465247 },
})

function object(value: unknown, allowed: readonly string[], label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label}: expected an object.`)
  const record = value as Record<string, unknown>
  for (const key of Object.keys(record)) if (!allowed.includes(key)) throw new Error(`${label}: unsupported key ${key}.`)
  return record
}
function number(value: unknown, label: string, min = -Infinity, max = Infinity): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`${label}: invalid finite physical value.`)
  return value
}
function choice(value: unknown, choices: readonly string[], label: string): string {
  if (typeof value !== 'string' || !choices.includes(value)) throw new Error(`${label}: unsupported state.`)
  return value
}
function vector(value: unknown, n: number, label: string, unit = false): void {
  if (!Array.isArray(value) || value.length !== n) throw new Error(`${label}: invalid dimensions.`)
  let squared = 0
  for (const item of value) { const component = number(item, label); if (unit) squared += component * component }
  if (unit) {
    const length = Math.sqrt(squared)
    if (Math.abs(length - 1) > 1e-8) throw new Error(`${label}: must be unit length.`)
    // Normalize only the owned compiled copy, as the existing override consumer
    // does. Repeated composition must not turn permitted roundoff into scaling.
    for (let i = 0; i < n; i++) value[i] /= length
  }
}
function rigid(value: unknown, label: string): void {
  const pose = object(value, ['positionMetres', 'quaternion'], label)
  vector(pose.positionMetres, 3, label); vector(pose.quaternion, 4, label, true)
}
function axial(value: unknown, label: string, maxTravel: number): void {
  const state = object(value, ['attachment', 'travelMetres', 'pose'], label)
  const attachment = choice(state.attachment, ['installed', 'withdrawing', 'inserting', 'held'], label)
  if (attachment === 'held') { rigid(state.pose, label); if (state.travelMetres !== undefined) throw new Error(`${label}: held pose cannot have axis travel.`) }
  else if (attachment === 'installed') { if (state.pose !== undefined || state.travelMetres !== undefined) throw new Error(`${label}: installed has no free pose/travel.`) }
  else { number(state.travelMetres, label, 0, maxTravel); if (state.pose !== undefined) throw new Error(`${label}: axis motion cannot have a free pose.`) }
}
function member(value: unknown, label: string, attached: string, maxTravel: number): void {
  const state = object(value, ['attachment', 'travelMetres', 'pose'], label)
  const attachment = choice(state.attachment, [attached, 'inserting', 'held'], label)
  if (attachment === 'held') { rigid(state.pose, label); if (state.travelMetres !== undefined) throw new Error(`${label}: held has no insertion travel.`) }
  else if (attachment === 'inserting') { number(state.travelMetres, label, 0, maxTravel); if (state.pose !== undefined) throw new Error(`${label}: insertion has no free pose.`) }
  else if (state.pose !== undefined || state.travelMetres !== undefined) throw new Error(`${label}: attached has no free pose/travel.`)
}
function freeze(value: unknown): void {
  if (!value || typeof value !== 'object') return
  for (const child of Object.values(value)) freeze(child)
  Object.freeze(value)
}
freeze(SOURCE_ASSEMBLY_DATUMS)
freeze(SOURCE_GEAR_PHOTOGRAPHS)
freeze(SOURCE_GEAR_PHOTO_FRAMING)
// Only states created and deeply frozen by this compiler bypass validation.
// Scene's captured descriptor and Main's re-entered descriptor must be the
// same exact object, not a second rounded normalization/clone.
const COMPILED_STATES = new WeakMap<SourceAssemblyState, CompiledSourceAssembly>()
COMPILED_STATES.set(OPERATING_SOURCE_ASSEMBLY.state, OPERATING_SOURCE_ASSEMBLY)

/** Validate once when loading source data; never accept serialized arbitrary overrides. */
export function compileSourceAssemblyState(value: unknown): CompiledSourceAssembly {
  if (value === undefined) return OPERATING_SOURCE_ASSEMBLY
  if (value && typeof value === 'object') {
    const compiled = COMPILED_STATES.get(value as SourceAssemblyState)
    if (compiled) return compiled
  }
  const initial = object(value, ['kind', 'provenance', 'crank', 'retainingNut', 'hanger', 'gears', 'chain', 'measuringTool', 'manualBars', 'pen', 'photograph'], 'Source assembly')
  if (initial.kind === 'operating') {
    if (Object.keys(initial).length !== 1) throw new Error('Operating assembly cannot contain source controls.')
    return OPERATING_SOURCE_ASSEMBLY
  }
  choice(initial.kind, ['source-assembly'], 'Source assembly')
  const record = structuredClone(initial)
  const provenance = object(record.provenance, ['kind', 'videoId', 'frameIndex', 'evidence', 'unobservedDegreesOfFreedom'], 'Assembly provenance')
  if (provenance.kind !== 'chosen-feasible' || provenance.videoId !== 'jfH-NbsmvD4' || !Number.isInteger(number(provenance.frameIndex, 'Assembly source frame', 0, 21189))) throw new Error('Assembly source witness must identify the actual operation video/frame.')
  if (typeof provenance.evidence !== 'string' || !provenance.evidence.trim() || !Array.isArray(provenance.unobservedDegreesOfFreedom) || !provenance.unobservedDegreesOfFreedom.length || provenance.unobservedDegreesOfFreedom.some(value => typeof value !== 'string' || !value.trim())) throw new Error('Assembly must name source evidence and unknown chosen-feasible DOFs.')
  const required = new Set<string>()
  function need(paths: readonly string[]): void { for (const path of paths) required.add(path) }
  if (record.crank !== undefined) {
    const crank = object(record.crank, ['pin', 'carrier', 'keeper'], 'Crank')
    axial(crank.pin, 'Crank pin', SOURCE_ASSEMBLY_DATUMS.pinWithdrawalMaxMetres); axial(crank.carrier, 'Crank carrier', SOURCE_ASSEMBLY_DATUMS.carrierWithdrawalMaxMetres)
    const pin = crank.pin as SourceAxialAttachment, carrier = crank.carrier as SourceAxialAttachment
    if (carrier.attachment !== 'installed' && pin.attachment === 'installed') throw new Error('Withdraw the tapered service pin before withdrawing its carrier.')
    if (carrier.attachment !== 'installed' && pin.attachment !== 'held'
      && pin.attachment !== 'installed' && pin.travelMetres < 0.04055) throw new Error('The actual 45mm tapered pin must clear the 22.25mm hub barrel before carrier withdrawal.')
    if (pin.attachment !== 'installed' || carrier.attachment !== 'installed') {
      const keeper = object(crank.keeper, ['retainedAnchor', 'loopPose', 'connectorPose'], 'Keeper rigid-display gauges')
      choice(keeper.retainedAnchor, ['eye', 'ring'], 'Keeper retained native anchor')
      rigid(keeper.loopPose, 'Keeper loop'); rigid(keeper.connectorPose, 'Keeper connector')
    } else if (crank.keeper !== undefined) throw new Error('Installed crank uses its unchanged native keeper drape.')
    need(CRANK_CARRIER); need(CRANK_PIN); need(KEEPER); need([`${DRIVE}dt-crankshaft-1`]); need(Object.values(SOURCE_GEAR_PART_PATHS))
  }
  if (record.retainingNut !== undefined) {
    const nut = object(record.retainingNut, ['attachment', 'releaseTurns', 'pose'], 'Retaining nut')
    const attachment = choice(nut.attachment, ['threaded', 'held'], 'Retaining nut')
    if (attachment === 'held') { rigid(nut.pose, 'Retaining nut'); if (nut.releaseTurns !== undefined) throw new Error('Held nut cannot have thread advance.') }
    else { number(nut.releaseTurns, 'Nut release turns', 0, NUT_THREAD_RELEASE_M / THREAD_PITCH_M); if (nut.pose !== undefined) throw new Error('Threaded nut cannot have a free pose.') }
    need([NUT, `${PAPER}pd-transgear-knob-shaft-1`]); need(Object.values(SOURCE_GEAR_PART_PATHS))
  }
  if (record.hanger !== undefined) {
    const hanger = object(record.hanger, ['attachment', 'swingRad', 'hookReleaseRad'], 'Hanger')
    choice(hanger.attachment, ['latched', 'unlatched', 'open', 'returning'], 'Hanger')
    // The archive does not model a physical free-swing stop; ±pi is a chosen
    // finite display gauge. Hook release, unlike swing, has a sourced + sign.
    number(hanger.swingRad, 'Chosen finite hanger swing gauge', -Math.PI, Math.PI); number(hanger.hookReleaseRad, 'Positive hook root-hinge gauge', 0, Math.PI / 2)
    if (hanger.attachment === 'latched' && (hanger.swingRad !== 0 || hanger.hookReleaseRad !== 0)) throw new Error('Latched hanger must use native engaged pose.')
    if (hanger.attachment !== 'latched' && hanger.hookReleaseRad === 0 && hanger.swingRad === 0) throw new Error('Unlatched hanger must release the native hook/pin contact.')
    if (hanger.swingRad !== 0 && record.chain === undefined) throw new Error('Moving the upper hanger requires an explicit native chain state.')
    need(HANGER); need([NUT, HOOK, `${PAPER}vn-transgear-latch-pin-1`, `${PAPER}pd-transgear-pivot-spacer-1`]); need(RIVETS); need(Object.values(SOURCE_GEAR_PART_PATHS))
  }
  if (record.gears !== undefined) {
    const gears = object(record.gears, ['members'], 'Gear exchange'), members = object(gears.members, GEAR_IDS, 'Gear members')
    let upper = false, crank = false
    for (const id of GEAR_IDS) {
      const gear = object(members[id], ['attachment', 'phaseRad', 'travelMetres', 'pose'], id)
      const attachment = choice(gear.attachment, ['upper', 'crank', 'upper-withdrawing', 'crank-withdrawing', 'upper-inserting', 'crank-inserting', 'held', 'stored'], id)
      if (attachment === 'held' || attachment === 'stored') { rigid(gear.pose, id); if (gear.phaseRad !== undefined || gear.travelMetres !== undefined) throw new Error(`${id}: free gear has no axis controls.`) }
      else {
        number(gear.phaseRad, `${id} clock`)
        if (attachment.includes('-')) number(gear.travelMetres, `${id} shaft-linked withdrawal`, 0, attachment.startsWith('upper') ? SOURCE_ASSEMBLY_DATUMS.upperGearWithdrawalMaxMetres : SOURCE_ASSEMBLY_DATUMS.crankGearWithdrawalMaxMetres)
        else if (gear.travelMetres !== undefined) throw new Error(`${id}: seated gear has no withdrawal.`)
        if (gear.pose !== undefined) throw new Error(`${id}: shaft-attached gear has no free pose.`)
        if (attachment.startsWith('upper')) { if (upper) throw new Error('Two gears cannot occupy the same upper shaft.'); upper = true }
        else { if (crank) throw new Error('Two gears cannot occupy the same crank shaft.'); crank = true }
      }
    }
    if (record.retainingNut === undefined) throw new Error('Gear exchange must state the nut attachment independently.')
    need(Object.values(SOURCE_GEAR_PART_PATHS)); need([SPARE, NUT, `${DRIVE}dt-crankshaft-1`, `${PAPER}pd-transgear-knob-shaft-1`]); need(CRANK_CARRIER)
  }
  if (record.chain !== undefined) {
    const chain = object(record.chain, ['attachment', 'jointsMetres', 'planeNormal', 'contacts'], 'Native chain')
    choice(chain.attachment, ['slack-on-sprockets', 'held-off-sprockets', 'reinstalling'], 'Native chain')
    vector(chain.planeNormal, 3, 'Chain hinge normal', true)
    if (!Array.isArray(chain.jointsMetres) || chain.jointsMetres.length !== 68) throw new Error('Native chain requires all 68 joint positions.')
    for (const point of chain.jointsMetres) vector(point, 3, 'Chain hinge')
    if (!Array.isArray(chain.contacts) || !chain.contacts.length) throw new Error('Loose/held chain must declare actual attachment contacts.')
    let held = false, sprocket = false
    for (const contact of chain.contacts) {
      const item = object(contact, ['kind', 'joint', 'positionMetres', 'gear', 'tooth'], 'Chain contact')
      if (!Number.isInteger(number(item.joint, 'Chain joint', 0, 67))) throw new Error('Chain joint must be an integer.')
      if (item.kind === 'held') { vector(item.positionMetres, 3, 'Held chain contact'); held = true; if (item.gear !== undefined || item.tooth !== undefined) throw new Error('Held contact has no sprocket tooth.') }
      else {
        choice(item.kind, ['sprocket'], 'Chain contact'); choice(item.gear, GEAR_IDS, 'Chain gear')
        const teeth = item.gear === 'T24' ? 24 : item.gear === 'T12' ? 12 : 18
        if (!Number.isInteger(number(item.tooth, 'Chain tooth', 0, teeth - 1))) throw new Error('Chain tooth must be an integer.')
        if (item.positionMetres !== undefined) throw new Error('Sprocket contact is computed from actual wheel datum, not a free contact point.')
        sprocket = true
      }
    }
    if (chain.attachment === 'held-off-sprockets' && (!held || sprocket) || chain.attachment === 'slack-on-sprockets' && !sprocket) throw new Error('Chain contact topology disagrees with its attachment state.')
    validateChainPath(chain as unknown as SourceChainAssembly)
    need(SOURCE_CHAIN_PART_PATHS)
    for (const contact of chain.contacts as SourceChainContact[]) if (contact.kind === 'sprocket') need([SOURCE_GEAR_PART_PATHS[contact.gear]])
  }
  if (record.measuringTool !== undefined) {
    const tool = object(record.measuringTool, ['attachment', 'stickPose', 'stopAtStickMetres', 'station', 'barFootStationMetres'], 'Measuring tool')
    const attachment = choice(tool.attachment, ['held', 'withdrawn', 'on-rocker', 'bar-at-tool-end', 'bar-setting'], 'Measuring tool')
    object(tool, attachment === 'held' || attachment === 'withdrawn'
      ? ['attachment', 'stickPose', 'stopAtStickMetres']
      : attachment === 'bar-setting'
        ? ['attachment', 'station', 'stopAtStickMetres', 'barFootStationMetres']
        : ['attachment', 'station', 'stopAtStickMetres'], 'Measuring tool variant')
    number(tool.stopAtStickMetres, 'Finite stop centre on real stick', SOURCE_ASSEMBLY_DATUMS.stopCentreMinMetres, SOURCE_ASSEMBLY_DATUMS.stopCentreMaxMetres)
    if (attachment === 'held' || attachment === 'withdrawn') rigid(tool.stickPose, 'Stick pose')
    else {
      if (!Number.isInteger(number(tool.station, 'Physical station', 1, 20))) throw new Error('Physical station must be an integer.')
      // This is a literal native-unit foot position. The finite roof, upper
      // pin loop and whole-body guard provide its tighter per-baseline domain.
      if (attachment === 'bar-setting') number(tool.barFootStationMetres, 'Native setup foot station', -0.15, 0.15)
      const parts = CHANNEL_STATIONS[(tool.station as number) - 1]!
      need([CHANNEL_CHASSIS, parts.rocker, parts.bar, parts.lever])
    }
    need([STICK, STOP])
  }
  if (record.manualBars !== undefined) {
    if (!Array.isArray(record.manualBars) || !record.manualBars.length || record.manualBars.length > 20) throw new Error('Retained native setup requires one through twenty explicit stations.')
    const stations = new Set<number>()
    for (const raw of record.manualBars) {
      const bar = object(raw, ['station', 'barFootStationMetres'], 'Retained native bar')
      const station = number(bar.station, 'Retained bar station', 1, 20)
      if (!Number.isInteger(station) || stations.has(station)) throw new Error('Retained native setup stations must be unique integers.')
      stations.add(station)
      number(bar.barFootStationMetres, 'Retained native foot station', -0.15, 0.15)
      if (record.measuringTool && 'station' in (record.measuringTool as object) && (record.measuringTool as SourceMeasuringTool & { station: number }).station === station) throw new Error('A tool station cannot also claim an independent retained bar constraint.')
      const parts = CHANNEL_STATIONS[station - 1]!
      need([CHANNEL_CHASSIS, parts.rocker, parts.bar, parts.lever])
    }
    record.manualBars.sort((a, b) => (a as SourceManualBarSetting).station - (b as SourceManualBarSetting).station)
  }
  if (record.pen !== undefined) {
    const pen = object(record.pen, ['rod', 'yawDeltaRad', 'vBlock', 'frame', 'marker', 'wire'], 'Pen assembly')
    axial(pen.rod, 'Pen rod', SOURCE_ASSEMBLY_DATUMS.rodLengthMetres); number(pen.yawDeltaRad, 'Native rod-axis yaw', -Math.PI, Math.PI)
    const block = object(pen.vBlock, ['attachment', 'pose'], 'Pen V block'); choice(block.attachment, ['rod', 'held'], 'Pen V block')
    if (block.attachment === 'held') rigid(block.pose, 'Pen V block'); else if (block.pose !== undefined) throw new Error('Attached V block has no free pose.')
    if (block.attachment === 'held' && pen.yawDeltaRad !== 0) throw new Error('Detached V block uses its explicit pose, not an ignored rod-axis yaw.')
    member(pen.frame, 'Pen frame', 'v-block', 0.036); member(pen.marker, 'Pen marker', 'frame', 0.10999999940395355)
    const wire = object(pen.wire, ['attachment', 'pose'], 'Pen wire'); choice(wire.attachment, ['connected', 'released'], 'Pen wire')
    if (wire.attachment === 'released') rigid(wire.pose, 'Pen wire'); else if (wire.pose !== undefined) throw new Error('Connected wire has no free pose.')
    if ((pen.rod as SourceAxialAttachment).attachment !== 'installed' && wire.attachment !== 'released') throw new Error('Release the rod wire tie before withdrawing the square rod from its fixed hanger.')
    need([ROD, BLOCK, MARKER, WIRE, `${PEN}pn-pen-hanger-1`, `${PEN}vn-hanger-screw-1`]); need(FRAME_GROUP)
  }
  if (record.photograph !== undefined) {
    if (Object.keys(record).some(key => !['kind', 'provenance', 'photograph'].includes(key))) throw new Error('Photograph subject scope cannot masquerade as machine disassembly.')
    const photo = object(record.photograph, ['pair', 'displayPose', 'fourGearPoses'], 'Gear photograph')
    choice(photo.pair, ['T24-T12', 'T18-T18', 'T12-T24', 'four-gears'], 'Gear photograph'); rigid(photo.displayPose, 'Photo world gauge')
    if (photo.pair === 'four-gears') {
      const poses = object(photo.fourGearPoses, GEAR_IDS, 'Four native gear poses')
      for (const id of GEAR_IDS) rigid(poses[id], id)
    } else if (photo.fourGearPoses !== undefined) throw new Error('Measured pair views cannot contain unrelated four-gear poses.')
    need(NATIVE_PATHS); need(Object.values(SOURCE_GEAR_PART_PATHS))
  }
  if (!required.size) throw new Error('Source assembly must contain a bounded physical domain; use operating for no-op.')
  for (const path of required) if (!REST.has(path) && !Object.values(SOURCE_GEAR_PART_PATHS).includes(path)) throw new Error(`Source assembly references a missing released native part: ${path}.`)
  freeze(record)
  const physical = physicalDescriptor(record as unknown as Exclude<SourceAssemblyState, { kind: 'operating' }>)
  const compiled = Object.freeze({ state: record as unknown as SourceAssemblyState, requiredPartPaths: Object.freeze([...required]), physicalKey: canonicalPhysicalKey(physical) })
  COMPILED_STATES.set(compiled.state, compiled)
  return compiled
}
function periodic(angle: number): number {
  const result = angle % (2 * Math.PI)
  return result === 0 ? 0 : result < 0 ? result + 2 * Math.PI : result
}
function physicalAxial(state: SourceAxialAttachment): unknown {
  return state.attachment === 'held' ? { pose: state.pose } : { travelMetres: state.attachment === 'installed' ? 0 : state.travelMetres }
}
/** Attachment/history labels and contact witnesses do not move native bodies.
 * Every descriptor must still be compiled and solved, even when these match. */
function physicalDescriptor(state: Exclude<SourceAssemblyState, { kind: 'operating' }>): Record<string, unknown> {
  const result: Record<string, unknown> = { kind: state.kind }
  if (state.crank) result.crank = { pin: physicalAxial(state.crank.pin), carrier: physicalAxial(state.crank.carrier), ...(state.crank.keeper ? { keeper: { loopPose: state.crank.keeper.loopPose, connectorPose: state.crank.keeper.connectorPose } } : {}) }
  if (state.retainingNut) result.retainingNut = state.retainingNut.attachment === 'held' ? { pose: state.retainingNut.pose } : { releaseTurns: state.retainingNut.releaseTurns }
  if (state.hanger) result.hanger = { swingRad: periodic(state.hanger.swingRad), hookReleaseRad: state.hanger.hookReleaseRad }
  if (state.gears) {
    const members: Record<string, unknown> = {}
    for (const id of GEAR_IDS) {
      const member = state.gears.members[id]
      switch (member.attachment) {
        case 'held':
        case 'stored':
          members[id] = { pose: member.pose }
          break
        default:
          members[id] = { seat: member.attachment.startsWith('upper') ? 'upper' : 'crank', phaseRad: periodic(member.phaseRad), travelMetres: 'travelMetres' in member ? member.travelMetres : 0 }
      }
    }
    result.gears = { members }
  }
  if (state.chain) result.chain = { jointsMetres: state.chain.jointsMetres, planeNormal: state.chain.planeNormal }
  if (state.measuringTool) result.measuringTool = state.measuringTool.attachment === 'held' || state.measuringTool.attachment === 'withdrawn'
    ? { stickPose: state.measuringTool.stickPose, stopAtStickMetres: state.measuringTool.stopAtStickMetres } : state.measuringTool
  if (state.manualBars) result.manualBars = state.manualBars
  if (state.pen) result.pen = { rod: physicalAxial(state.pen.rod), yawDeltaRad: periodic(state.pen.yawDeltaRad), vBlock: state.pen.vBlock,
    frame: 'pose' in state.pen.frame ? { pose: state.pen.frame.pose } : { travelMetres: 'travelMetres' in state.pen.frame ? state.pen.frame.travelMetres : 0 },
    marker: 'pose' in state.pen.marker ? { pose: state.pen.marker.pose } : { travelMetres: 'travelMetres' in state.pen.marker ? state.pen.marker.travelMetres : 0 }, wire: state.pen.wire }
  if (state.photograph) result.photograph = state.photograph
  return result
}

function canonicalPhysicalKey(value: unknown, field = ''): string {
  if (!value || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) {
    // Native links are mirror-symmetric across their hinge plane. Reversing
    // that single plane normal changes no physical chain geometry.
    if (field === 'quaternion' || field === 'planeNormal') {
      const sign = (value[3] || value[2] || value[1] || value[0]) < 0 ? -1 : 1
      return JSON.stringify(value.map(component => sign * component))
    }
    return `[${value.map(item => canonicalPhysicalKey(item)).join(',')}]`
  }
  const record = value as Record<string, unknown>
  return `{${Object.keys(record).sort().map(key => `${JSON.stringify(key)}:${canonicalPhysicalKey(record[key], key)}`).join(',')}}`
}
/** Stable change-census contract; support evidence changes alone are not motion. */
export function sourceAssemblyPhysicalKey(compiled: CompiledSourceAssembly): string {
  return compiled.physicalKey
}

function validateChainPath(chain: SourceChainAssembly): void {
  const origin = chain.jointsMetres[0]!, normal = chain.planeNormal
  for (let i = 0; i < 68; i++) {
    const a = chain.jointsMetres[i]!, b = chain.jointsMetres[(i + 1) % 68]!
    if (Math.abs(Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) - CHORD_M) > CONTACT_EPS_M) throw new Error(`Native chain chord ${i}, including closure, must remain 6.35mm.`)
    if (Math.abs((a[0] - origin[0]) * normal[0] + (a[1] - origin[1]) * normal[1] + (a[2] - origin[2]) * normal[2]) > CONTACT_EPS_M) throw new Error('Native parallel chain hinges require a single rigidly posed plane.')
  }
}

type V3 = [number, number, number]
type Q4 = [number, number, number, number]
interface Delta { p: V3; q: Q4 }
interface MutableOverride extends PartOverride { worldPositionMetres: V3; worldQuaternion: Q4 }
export interface SourceAssemblyBuffer {
  /** Reused output; consumed immediately, never saved as source evidence. */
  readonly overrides: PartOverride[]
  readonly entries: Map<string, MutableOverride>
  readonly activeEntries: Set<MutableOverride>
  readonly baselineMatrices: Map<string, Float64Array>
  readonly baselineVisibility: Map<string, boolean>
  readonly loadedBaselinePaths: Set<string>
  readonly gearSeats: Readonly<Record<'upper' | 'crank', { readonly matrix: Float64Array; partPath: string | null }>>
  readonly toolContact: NativeToolContactBuffer
  readonly toolInput: NativeToolBarFrameInput & { kind: NativeToolContactInput['kind']; stopAt: number; stopRelative: Float64Array; footStation: number }
  readonly toolWorldMatrix: Float64Array
  readonly contactMatrices: readonly Float64Array[]
  readonly deltas: readonly Delta[]
  readonly points: readonly V3[]
  readonly quaternions: readonly Q4[]
}
export function createSourceAssemblyBuffer(): SourceAssemblyBuffer {
  const paths = [...NATIVE_PATHS, SOURCE_GEAR_PART_PATHS['T18-upper'], SOURCE_GEAR_PART_PATHS['T18-crank']]
  return { overrides: [], entries: new Map<string, MutableOverride>(paths.map(partPath => [partPath, { partPath, worldPositionMetres: [0, 0, 0], worldQuaternion: [0, 0, 0, 1] }])),
    activeEntries: new Set(), baselineMatrices: new Map(paths.map(path => [path, new Float64Array(16)])), baselineVisibility: new Map(), loadedBaselinePaths: new Set(),
    gearSeats: { upper: { matrix: new Float64Array(16), partPath: null }, crank: { matrix: new Float64Array(16), partPath: null } },
    toolContact: createNativeToolContactBuffer(),
    toolInput: { kind: 'on-rocker', stopAt: 0, stopRelative: new Float64Array(16), footStation: 0,
      rockerInChassis: new Float64Array(16), barInChassis: new Float64Array(16), leverInChassis: new Float64Array(16) },
    toolWorldMatrix: new Float64Array(16), contactMatrices: Array.from({ length: 4 }, () => new Float64Array(16)),
    deltas: Array.from({ length: 8 }, () => ({ p: [0, 0, 0] as V3, q: [0, 0, 0, 1] as Q4 })),
    points: Array.from({ length: 7 }, () => [0, 0, 0] as V3), quaternions: Array.from({ length: 4 }, () => [0, 0, 0, 1] as Q4) }
}
function rest(path: string): readonly number[] {
  const matrix = REST.get(path)
  if (!matrix) throw new Error(`Missing exact native rest matrix: ${path}.`)
  return matrix
}
function baseline(out: SourceAssemblyBuffer, path: string): Float64Array {
  const matrix = out.baselineMatrices.get(path)
  if (!matrix || !out.loadedBaselinePaths.has(path)) throw new Error(`Source assembly baseline missing canonical part ${path}.`)
  return matrix
}
function point(out: V3, matrix: ArrayLike<number>, p: Point3): void {
  for (let row = 0; row < 3; row++) out[row] = matrix[row]! * p[0] + matrix[row + 4]! * p[1] + matrix[row + 8]! * p[2] + matrix[row + 12]!
}
function inversePoint(out: V3, m: ArrayLike<number>, p: Point3): void {
  const a = m[0]!, b = m[4]!, c = m[8]!, d = m[1]!, e = m[5]!, f = m[9]!, g = m[2]!, h = m[6]!, i = m[10]!
  const determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
  if (Math.abs(determinant) < 1e-12) throw new Error('Native datum frame is singular.')
  const x = p[0] - m[12]!, y = p[1] - m[13]!, z = p[2] - m[14]!
  out[0] = ((e * i - f * h) * x + (c * h - b * i) * y + (b * f - c * e) * z) / determinant
  out[1] = ((f * g - d * i) * x + (a * i - c * g) * y + (c * d - a * f) * z) / determinant
  out[2] = ((d * h - e * g) * x + (b * g - a * h) * y + (a * e - b * d) * z) / determinant
}
function rotate(out: V3, q: Quaternion4, p: Point3): void {
  const [x, y, z, w] = q, [a, b, c] = p
  const tx = 2 * (y * c - z * b), ty = 2 * (z * a - x * c), tz = 2 * (x * b - y * a)
  out[0] = a + w * tx + y * tz - z * ty; out[1] = b + w * ty + z * tx - x * tz; out[2] = c + w * tz + x * ty - y * tx
}
function multiply(out: Q4, a: Quaternion4, b: Quaternion4): void {
  const [x, y, z, w] = a, [u, v, t, s] = b
  out[0] = w * u + x * s + y * t - z * v; out[1] = w * v - x * t + y * s + z * u
  out[2] = w * t + x * v - y * u + z * s; out[3] = w * s - x * u - y * v - z * t
}
function quaternion(out: Q4, m: ArrayLike<number>): void {
  const sx = Math.hypot(m[0]!, m[1]!, m[2]!), sy = Math.hypot(m[4]!, m[5]!, m[6]!), sz = Math.hypot(m[8]!, m[9]!, m[10]!)
  if (sx === 0 || sy === 0 || sz === 0) throw new Error('Native rigid frame has zero scale.')
  const a = m[0]! / sx, b = m[4]! / sy, c = m[8]! / sz, d = m[1]! / sx, e = m[5]! / sy, f = m[9]! / sz, g = m[2]! / sx, h = m[6]! / sy, i = m[10]! / sz
  const trace = a + e + i
  if (trace > 0) { const s = 2 * Math.sqrt(trace + 1); out[0] = (h - f) / s; out[1] = (c - g) / s; out[2] = (d - b) / s; out[3] = s / 4 }
  else if (a > e && a > i) { const s = 2 * Math.sqrt(1 + a - e - i); out[0] = s / 4; out[1] = (b + d) / s; out[2] = (c + g) / s; out[3] = (h - f) / s }
  else if (e > i) { const s = 2 * Math.sqrt(1 + e - a - i); out[0] = (b + d) / s; out[1] = s / 4; out[2] = (f + h) / s; out[3] = (c - g) / s }
  else { const s = 2 * Math.sqrt(1 + i - a - e); out[0] = (c + g) / s; out[1] = (f + h) / s; out[2] = s / 4; out[3] = (d - b) / s }
  const length = Math.hypot(...out); for (let k = 0; k < 4; k++) out[k] = out[k]! / length
}
function direction(out: V3, m: ArrayLike<number>, local: Point3): void {
  for (let row = 0; row < 3; row++) out[row] = m[row]! * local[0] + m[row + 4]! * local[1] + m[row + 8]! * local[2]
  const length = Math.hypot(...out); if (!length) throw new Error('Native axis has zero length.')
  for (let row = 0; row < 3; row++) out[row] = out[row]! / length
}
function identity(delta: Delta): void { delta.p[0] = delta.p[1] = delta.p[2] = 0; delta.q[0] = delta.q[1] = delta.q[2] = 0; delta.q[3] = 1 }
function around(delta: Delta, origin: Point3, axis: Point3, angle: number, work: V3): void {
  angle = periodic(angle)
  const s = Math.sin(angle / 2); delta.q[0] = axis[0] * s; delta.q[1] = axis[1] * s; delta.q[2] = axis[2] * s; delta.q[3] = Math.cos(angle / 2)
  rotate(work, delta.q, origin); for (let i = 0; i < 3; i++) delta.p[i] = origin[i]! - work[i]!
}
function poseDelta(out: Delta, matrix: ArrayLike<number>, pose: SourceRigidPose, q: Q4, p: V3): void {
  quaternion(q, matrix); q[0] = -q[0]; q[1] = -q[1]; q[2] = -q[2]
  multiply(out.q, pose.quaternion, q)
  point(p, matrix, ZERO); rotate(p, out.q, p)
  for (let i = 0; i < 3; i++) out.p[i] = pose.positionMetres[i]! - p[i]!
}
function entry(out: SourceAssemblyBuffer, path: string): MutableOverride {
  const item = out.entries.get(path)
  if (!item) throw new Error(`Source assembly output has no canonical native body ${path}.`)
  if (!out.activeEntries.has(item)) { delete item.visibility; out.overrides.push(item); out.activeEntries.add(item) }
  return item
}
function transformed(out: SourceAssemblyBuffer, path: string, matrix: ArrayLike<number>, delta: Delta): void {
  const item = entry(out, path); point(item.worldPositionMetres, matrix, ZERO); rotate(item.worldPositionMetres, delta.q, item.worldPositionMetres)
  for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! + delta.p[i]!
  quaternion(item.worldQuaternion, matrix); multiply(item.worldQuaternion, delta.q, item.worldQuaternion)
}
function group(out: SourceAssemblyBuffer, paths: readonly string[], delta: Delta): void {
  for (const path of paths) transformed(out, path, baseline(out, path), delta)
}
function axialDelta(out: Delta, state: SourceAxialAttachment, matrix: ArrayLike<number>, localAxis: Point3, sign: number, buffer: SourceAssemblyBuffer): void {
  identity(out)
  if (state.attachment === 'held') poseDelta(out, matrix, state.pose, buffer.quaternions[0]!, buffer.points[0]!)
  else if (state.attachment !== 'installed') {
    for (let row = 0; row < 3; row++) out.p[row] = sign * state.travelMetres
      * (matrix[row]! * localAxis[0] + matrix[row + 4]! * localAxis[1] + matrix[row + 8]! * localAxis[2])
  }
}
function distance(a: Point3, b: Point3): number { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) }
function mappedPoint(out: V3, matrix: ArrayLike<number>, local: Point3, delta: Delta): void {
  point(out, matrix, local); rotate(out, delta.q, out); for (let i = 0; i < 3; i++) out[i] = out[i]! + delta.p[i]!
}
function align(out: Q4, a: Point3, b: Point3): void {
  let r = 1 + a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
  if (r < 1e-12) { r = 0; if (Math.abs(a[0]) > Math.abs(a[2])) { out[0] = -a[1]; out[1] = a[0]; out[2] = 0 } else { out[0] = 0; out[1] = -a[2]; out[2] = a[1] } }
  else { out[0] = a[1] * b[2] - a[2] * b[1]; out[1] = a[2] * b[0] - a[0] * b[2]; out[2] = a[0] * b[1] - a[1] * b[0] }
  out[3] = r; const length = Math.hypot(...out); for (let i = 0; i < 4; i++) out[i] = out[i]! / length
}

/** Pure constraint solve: only the supplied output/scratch buffer is mutated. */
export function solveSourceAssembly(compiled: CompiledSourceAssembly, context: SourceAssemblyContext, out: SourceAssemblyBuffer): readonly PartOverride[] {
  out.overrides.length = 0; out.activeEntries.clear()
  const state = compiled.state
  if (state.kind === 'operating') return EMPTY_OVERRIDES
  out.loadedBaselinePaths.clear()
  for (const path of compiled.requiredPartPaths) {
    const matrix = out.baselineMatrices.get(path)
    if (!matrix || !context.readWorldMatrix(path, matrix)) throw new Error(`Source assembly cannot silently omit canonical native body ${path}.`)
    for (let i = 0; i < 16; i++) if (!Number.isFinite(matrix[i])) throw new Error(`Nonfinite source assembly baseline for ${path}.`)
    const visibility = context.readVisibility(path, 'effective')
    if (visibility === null) throw new Error(`Source assembly baseline visibility missing canonical native body ${path}.`)
    out.baselineVisibility.set(path, visibility)
    out.loadedBaselinePaths.add(path)
  }
  if (state.gears || state.crank || state.retainingNut || state.hanger || state.chain?.contacts.some(contact => contact.kind === 'sprocket')) {
    for (const seat of GEAR_SEATS) {
      const current = out.gearSeats[seat]
      current.partPath = context.readSeatedGearPartPath(seat)
      if (!current.partPath || !Object.values(SOURCE_GEAR_PART_PATHS).includes(current.partPath)
        || !context.readGearSeatWorldMatrix(seat, current.matrix)) throw new Error(`Missing genuine current normal ${seat} gear seat.`)
      for (const component of current.matrix) if (!Number.isFinite(component)) throw new Error(`Nonfinite current normal ${seat} gear seat.`)
    }
    if (state.gears && !state.chain) {
      for (const seat of GEAR_SEATS) {
        const member = GEAR_IDS.find(id => state.gears!.members[id].attachment.startsWith(seat))
        const placed = member === undefined ? undefined : state.gears.members[member]
        if (!member || !placed || SOURCE_GEAR_PART_PATHS[member] !== out.gearSeats[seat].partPath
          || placed.attachment !== seat || ('phaseRad' in placed && placed.phaseRad % (2 * Math.PI) !== 0)) throw new Error('Changing a native gear seat requires an explicit native chain state.')
      }
    }
  }
  const hanger = out.deltas[0]!, carrier = out.deltas[1]!, pin = out.deltas[2]!, rod = out.deltas[3]!, block = out.deltas[4]!, frame = out.deltas[5]!, workDelta = out.deltas[6]!, toolDelta = out.deltas[7]!
  const p = out.points, q = out.quaternions
  identity(hanger)
  if (state.hanger) {
    const pivot = baseline(out, `${PAPER}pd-transgear-pivot-spacer-1`)
    point(p[0]!, pivot, ZERO); direction(p[1]!, pivot, Z); around(hanger, p[0]!, p[1]!, state.hanger.swingRad, p[2]!)
    group(out, HANGER, hanger)
    point(p[0]!, baseline(out, RIVETS[0]!), ZERO); point(p[1]!, baseline(out, RIVETS[1]!), ZERO)
    for (let i = 0; i < 3; i++) p[2]![i] = p[1]![i]! - p[0]![i]!
    const length = Math.hypot(...p[2]!); for (let i = 0; i < 3; i++) p[2]![i] = p[2]![i]! / length
    around(workDelta, p[0]!, p[2]!, state.hanger.hookReleaseRad, p[3]!); transformed(out, HOOK, baseline(out, HOOK), workDelta)
    // Rivet centres stay fixed. This is a chosen rigid root-hinge display family,
    // not a claim that the actual spring strip bends as a rigid plate.
  }
  if (state.crank) {
    axialDelta(carrier, state.crank.carrier, baseline(out, HUB), Y, -1, out)
    axialDelta(pin, state.crank.pin, baseline(out, PIN), X, -1, out)
    group(out, CRANK_CARRIER, carrier); group(out, CRANK_PIN, pin)
    if (state.crank.keeper) {
      poseDelta(workDelta, baseline(out, KEEPER[0]!), state.crank.keeper.loopPose, q[0]!, p[0]!); transformed(out, KEEPER[0]!, baseline(out, KEEPER[0]!), workDelta)
      poseDelta(workDelta, baseline(out, KEEPER[1]!), state.crank.keeper.connectorPose, q[0]!, p[0]!); transformed(out, KEEPER[1]!, baseline(out, KEEPER[1]!), workDelta)
      const loopMatrix = out.contactMatrices[0]!, connectorMatrix = out.contactMatrices[1]!, anchorMatrix = out.contactMatrices[2]!
      currentPosedMatrix(KEEPER[0]!, out, loopMatrix); currentPosedMatrix(KEEPER[1]!, out, connectorMatrix)
      for (let i = 0; i < 2; i++) {
        point(p[0]!, loopMatrix, KEEPER_LOOP_LOCAL_ENDS[i]!); point(p[1]!, connectorMatrix, KEEPER_CONNECTOR_LOCAL_ENDS[i]!)
        if (distance(p[0]!, p[1]!) > CONTACT_EPS_M) throw new Error('Rigid keeper display must preserve both actual loop-link bead seats.')
      }
      const anchor = SOURCE_KEEPER_ANCHORS[state.crank.keeper.retainedAnchor]
      currentPosedMatrix(anchor.partPath, out, anchorMatrix)
      point(p[0]!, anchorMatrix, anchor.localPointMetres)
      point(p[1]!, loopMatrix, anchor.loopLocalPointMetres)
      if (distance(p[0]!, p[1]!) > CONTACT_EPS_M) throw new Error('Rigid native keeper must remain at its explicitly retained eye/ring contact.')
      direction(p[0]!, anchorMatrix, anchor.localAxis)
      direction(p[1]!, loopMatrix, anchor.loopLocalAxis)
      if (Math.abs(p[0]![0] * p[1]![0] + p[0]![1] * p[1]![1] + p[0]![2] * p[1]![2]) < 1 - 1e-8) throw new Error('Native keeper rod must align with its retained hardware aperture axis.')
      // Only actual released keeper geometry is posed. Its internal bead drape
      // cannot change through rigid PartOverride; no hidden flexible mesh is added.
    }
  }
  if (state.retainingNut || state.hanger) {
    const matrix = baseline(out, NUT)
    const nut = state.retainingNut
    if (nut?.attachment === 'held') { poseDelta(workDelta, matrix, nut.pose, q[0]!, p[0]!); transformed(out, NUT, matrix, workDelta) }
    else {
      const turns = nut?.releaseTurns ?? 0
      point(p[0]!, matrix, ZERO); direction(p[1]!, matrix, Y); around(workDelta, p[0]!, p[1]!, turns * 2 * Math.PI, p[2]!)
      const nativeAxisLength = Math.hypot(matrix[4]!, matrix[5]!, matrix[6]!)
      for (let i = 0; i < 3; i++) workDelta.p[i] = workDelta.p[i]! + p[1]![i]! * turns * THREAD_PITCH_M * nativeAxisLength
      transformed(out, NUT, matrix, workDelta)
      if (state.hanger) {
        const item = entry(out, NUT); rotate(item.worldPositionMetres, hanger.q, item.worldPositionMetres)
        for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! + hanger.p[i]!
        multiply(item.worldQuaternion, hanger.q, item.worldQuaternion)
      }
    }
  }
  if (state.gears) {
    for (const id of GEAR_IDS) {
      const gear = state.gears.members[id], path = SOURCE_GEAR_PART_PATHS[id], item = entry(out, path)
      switch (gear.attachment) {
        case 'held':
        case 'stored':
          for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = gear.pose.positionMetres[i]!
          for (let i = 0; i < 4; i++) item.worldQuaternion[i] = gear.pose.quaternion[i]!
          break
        default: {
          const upper = gear.attachment.startsWith('upper'), reference = out.gearSeats[upper ? 'upper' : 'crank'].matrix
          identity(workDelta)
          transformed(out, path, reference, workDelta)
          // Additional phase relative to this exact current NORMAL seat, never
          // accumulated from a preceding view or guessed from the shaft origin.
          direction(p[1]!, reference, Z)
          const s = Math.sin(periodic(gear.phaseRad) / 2); q[0]![0] = p[1]![0] * s; q[0]![1] = p[1]![1] * s; q[0]![2] = p[1]![2] * s; q[0]![3] = Math.cos(periodic(gear.phaseRad) / 2)
          multiply(item.worldQuaternion, q[0]!, item.worldQuaternion)
          const travel = 'travelMetres' in gear ? gear.travelMetres : 0
          for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! - reference[i + 8]! * travel
          if (upper && state.hanger) { rotate(item.worldPositionMetres, hanger.q, item.worldPositionMetres); for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! + hanger.p[i]!; multiply(item.worldQuaternion, hanger.q, item.worldQuaternion) }
          break
        }
      }
      item.visibility = 'visible'
    }
    identity(workDelta); transformed(out, SPARE, baseline(out, SPARE), workDelta); entry(out, SPARE).visibility = 'hidden'
  } else if (state.hanger) {
    // Installed current wheels follow the upper carrier; inactive wheel
    // visibility remains the operating solver's, never guessed here.
    const path = out.gearSeats.upper.partPath!
    transformed(out, path, baseline(out, path), hanger)
  }
  if (state.chain) solveChain(state.chain, state.gears, out)
  if (state.manualBars) for (const setting of state.manualBars) solveManualBar(setting, out)
  if (state.measuringTool) solveTool(state.measuringTool, out, toolDelta)
  if (state.pen) {
    const pen = state.pen, rodMatrix = baseline(out, ROD)
    if (pen.rod.attachment !== 'installed' && pen.rod.attachment !== 'held') {
      point(p[0]!, baseline(out, `${PEN}pn-pen-hanger-1`), [0, -0.006000000052154064, 0])
      inversePoint(p[1]!, rodMatrix, p[0]!)
      const guideClearance = Math.max(0, SOURCE_ASSEMBLY_DATUMS.rodLengthMetres - p[1]![1])
      if (pen.rod.travelMetres > guideClearance + CONTACT_EPS_M) throw new Error('Square rod axis travel ends when it clears the actual current fixed guide; use an explicit held pose beyond that point.')
    }
    axialDelta(rod, pen.rod, rodMatrix, Y, -1, out); transformed(out, ROD, rodMatrix, rod)
    mappedPoint(p[0]!, rodMatrix, ROD_AXIS_LOCAL, rod); direction(p[1]!, rodMatrix, Y); rotate(p[1]!, rod.q, p[1]!)
    around(workDelta, p[0]!, p[1]!, pen.yawDeltaRad, p[2]!)
    multiply(block.q, workDelta.q, rod.q); rotate(block.p, workDelta.q, rod.p); for (let i = 0; i < 3; i++) block.p[i] = block.p[i]! + workDelta.p[i]!
    if (pen.vBlock.attachment === 'held') poseDelta(block, baseline(out, BLOCK), pen.vBlock.pose, q[0]!, p[0]!)
    transformed(out, BLOCK, baseline(out, BLOCK), block)
    for (let i = 0; i < 3; i++) frame.p[i] = block.p[i]!
    for (let i = 0; i < 4; i++) frame.q[i] = block.q[i]!
    if (pen.frame.attachment === 'held') poseDelta(frame, baseline(out, FRAME), pen.frame.pose, q[0]!, p[0]!)
    else if (pen.frame.attachment === 'inserting') {
      direction(p[0]!, baseline(out, BLOCK), X); rotate(p[0]!, block.q, p[0]!)
      for (let i = 0; i < 3; i++) frame.p[i] = frame.p[i]! + p[0]![i]! * pen.frame.travelMetres
    }
    group(out, FRAME_GROUP, frame)
    if (pen.marker.attachment === 'held') { poseDelta(workDelta, baseline(out, MARKER), pen.marker.pose, q[0]!, p[0]!); transformed(out, MARKER, baseline(out, MARKER), workDelta) }
    else {
      transformed(out, MARKER, baseline(out, MARKER), frame)
      if (pen.marker.attachment === 'inserting') {
        const marker = entry(out, MARKER); direction(p[0]!, baseline(out, MARKER), Y); rotate(p[0]!, frame.q, p[0]!)
        for (let i = 0; i < 3; i++) marker.worldPositionMetres[i] = marker.worldPositionMetres[i]! + p[0]![i]! * pen.marker.travelMetres
      }
    }
    if (pen.wire.attachment === 'released') { poseDelta(workDelta, baseline(out, WIRE), pen.wire.pose, q[0]!, p[0]!); transformed(out, WIRE, baseline(out, WIRE), workDelta) }
  }
  validateNativeServiceContacts(state, out)
  if (state.photograph) solvePhotograph(state.photograph, out)
  for (const override of out.overrides) {
    for (const coordinate of override.worldPositionMetres!) if (!Number.isFinite(coordinate)) throw new Error(`Nonfinite solved native position: ${override.partPath}.`)
    const rotation = override.worldQuaternion!
    if (!rotation.every(Number.isFinite) || Math.abs(Math.hypot(...rotation) - 1) > 1e-8) throw new Error(`Invalid solved native rigid rotation: ${override.partPath}.`)
  }
  return out.overrides
}

function solveChain(chain: SourceChainAssembly, gears: SourceGearAssembly | undefined, out: SourceAssemblyBuffer): void {
  const p = out.points, q = out.quaternions
  for (const contact of chain.contacts) {
    const target = chain.jointsMetres[contact.joint]!
    if (contact.kind === 'held') { if (distance(target, contact.positionMetres) > CONTACT_EPS_M) throw new Error('Chain misses its explicit held contact.'); continue }
    const path = SOURCE_GEAR_PART_PATHS[contact.gear], current = out.entries.get(path)!, posed = out.activeEntries.has(current)
    const attachment = gears?.members[contact.gear].attachment
    const explicitlySeated = attachment !== undefined && attachment !== 'held' && attachment !== 'stored'
    if (!explicitlySeated && (!out.baselineVisibility.get(path)
      || !GEAR_SEATS.some(seat => out.gearSeats[seat].partPath === path))) throw new Error(`Native chain contact requires a genuinely seated visible ${contact.gear} wheel.`)
    const teeth = contact.gear === 'T24' ? 24 : contact.gear === 'T12' ? 12 : 18
    // Approved build_transgear_removable.py35..39: tooth on local+X;
    // the roller pocket following tooth k is at pi/N + k*2pi/N.
    const radius = CHORD_M / (2 * Math.sin(Math.PI / teeth)), angle = Math.PI / teeth + 2 * Math.PI * contact.tooth / teeth
    p[0]![0] = radius * Math.cos(angle); p[0]![1] = radius * Math.sin(angle); p[0]![2] = 0.00139999995008111
    if (posed) { rotate(p[1]!, current.worldQuaternion, p[0]!); for (let i = 0; i < 3; i++) p[1]![i] = p[1]![i]! + current.worldPositionMetres[i]! }
    else point(p[1]!, baseline(out, path), p[0]!)
    if (distance(target, p[1]!) > CONTACT_EPS_M) throw new Error(`Chain joint ${contact.joint} misses native ${contact.gear} roller-pocket contact.`)
    if (posed) rotate(p[2]!, current.worldQuaternion, Z); else direction(p[2]!, baseline(out, path), Z)
    if (Math.abs(Math.abs(p[2]![0] * chain.planeNormal[0] + p[2]![1] * chain.planeNormal[1] + p[2]![2] * chain.planeNormal[2]) - 1) > 1e-8) throw new Error('Wrapped chain hinge axes disagree with the native sprocket axle.')
  }
  // Native hinge0/hinge1 are exactly [0,0,0] and [6.35mm,0,0]
  // (inverse approved release matrices, max chord error4.34e-17m). Local +Z
  // is the pin axis. All 68 actual frames, including their outer/inner offsets,
  // are kept; rest-neighbour gaps are NOT reused as a loose closed path.
  for (let i = 0; i < 68; i++) {
    const path = SOURCE_CHAIN_PART_PATHS[i]!, a = chain.jointsMetres[i]!, b = chain.jointsMetres[(i + 1) % 68]!
    const chord = distance(a, b)
    for (let k = 0; k < 3; k++) p[0]![k] = (b[k]! - a[k]!) / chord
    align(q[0]!, X, p[0]!); rotate(p[1]!, q[0]!, Z)
    const normal = chain.planeNormal
    const cosine = p[1]![0] * normal[0] + p[1]![1] * normal[1] + p[1]![2] * normal[2]
    p[2]![0] = p[1]![1] * normal[2] - p[1]![2] * normal[1]; p[2]![1] = p[1]![2] * normal[0] - p[1]![0] * normal[2]; p[2]![2] = p[1]![0] * normal[1] - p[1]![1] * normal[0]
    const sine = p[0]![0] * p[2]![0] + p[0]![1] * p[2]![1] + p[0]![2] * p[2]![2], half = Math.atan2(sine, cosine) / 2, s = Math.sin(half)
    q[1]![0] = p[0]![0] * s; q[1]![1] = p[0]![1] * s; q[1]![2] = p[0]![2] * s; q[1]![3] = Math.cos(half); multiply(q[2]!, q[1]!, q[0]!)
    const item = entry(out, path)
    for (let k = 0; k < 3; k++) item.worldPositionMetres[k] = a[k]!
    for (let k = 0; k < 4; k++) item.worldQuaternion[k] = q[2]![k]!
    item.visibility = 'visible'
    // Reconfirm the native end without extending/scaling its mesh.
    const nativeFrame = baseline(out, path)
    p[3]![0] = CHORD_M * Math.hypot(nativeFrame[0]!, nativeFrame[1]!, nativeFrame[2]!); p[3]![1] = p[3]![2] = 0; rotate(p[3]!, item.worldQuaternion, p[3]!)
    for (let k = 0; k < 3; k++) p[3]![k] = p[3]![k]! + a[k]!
    if (distance(p[3]!, b) > CONTACT_EPS_M) throw new Error('Rigid native chain link cannot meet supplied hinge path.')
  }
}

function prepareNativeBar(station: number, out: SourceAssemblyBuffer): void {
  const parts = CHANNEL_STATIONS[station - 1]!, chassis = baseline(out, CHANNEL_CHASSIS), input = out.toolInput
  relativeMatrix(baseline(out, parts.rocker), chassis, input.rockerInChassis)
  relativeMatrix(baseline(out, parts.bar), chassis, input.barInChassis)
  relativeMatrix(baseline(out, parts.lever), chassis, input.leverInChassis)
}
function nativeToolWorldPose(path: string, nativeMatrix: Float64Array, out: SourceAssemblyBuffer): void {
  multiplyMatrix(baseline(out, CHANNEL_CHASSIS), nativeMatrix, out.toolWorldMatrix)
  const item = entry(out, path)
  point(item.worldPositionMetres, out.toolWorldMatrix, ZERO)
  quaternion(item.worldQuaternion, out.toolWorldMatrix)
}
function applyNativeBar(station: number, out: SourceAssemblyBuffer): void {
  const parts = CHANNEL_STATIONS[station - 1]!, lever = baseline(out, parts.lever), chassis = baseline(out, CHANNEL_CHASSIS)
  const input = out.toolInput, contact = out.toolContact, p = out.points
  nativeToolWorldPose(parts.bar, contact.barMatrix, out)
  const currentAngle = Math.atan2(input.leverInChassis[1]!, -input.leverInChassis[0]!)
  point(p[0]!, lever, ZERO); direction(p[1]!, chassis, Z)
  around(out.deltas[7]!, p[0]!, p[1]!, currentAngle - contact.leverAngle, p[2]!)
  transformed(out, parts.lever, lever, out.deltas[7]!)
  // Scene refreshes the existing genuine channel spring from this posed
  // lever eye and its unchanged current summing hook after all overrides.
  // Rod/rocker, normal force metadata, native stock and topology stay normal.
}
function solveManualBar(setting: SourceManualBarSetting, out: SourceAssemblyBuffer): void {
  prepareNativeBar(setting.station, out)
  const input = out.toolInput
  input.kind = 'bar-retained'; input.footStation = setting.barFootStationMetres
  solveNativeToolContact(input as NativeToolRetainedBarInput, out.toolContact)
  applyNativeBar(setting.station, out)
}
function solveTool(tool: SourceMeasuringTool, out: SourceAssemblyBuffer, delta: Delta): void {
  const input = out.toolInput, stick = baseline(out, STICK), stop = baseline(out, STOP), p = out.points
  relativeMatrix(stop, stick, input.stopRelative)
  const stopOriginX = input.stopRelative[12]!
  // The whole actual native stop, not just its centre, stays on the rule.
  const extent = Math.abs(input.stopRelative[0]!) * 0.006000000052154064
    + Math.abs(input.stopRelative[4]!) * 0.012000000104308128
    + Math.abs(input.stopRelative[8]!) * 0.006000000052154064
  if (tool.stopAtStickMetres < extent - CONTACT_EPS_M || tool.stopAtStickMetres > SOURCE_ASSEMBLY_DATUMS.stickLengthMetres - extent + CONTACT_EPS_M) throw new Error('Actual current stop footprint must fit entirely on the native rule.')
  switch (tool.attachment) {
    case 'held':
    case 'withdrawn': {
      poseDelta(delta, stick, tool.stickPose, out.quaternions[0]!, p[0]!)
      transformed(out, STICK, stick, delta); transformed(out, STOP, stop, delta)
      for (let row = 0; row < 3; row++) p[0]![row] = stick[row]!
      rotate(p[0]!, delta.q, p[0]!)
      const item = entry(out, STOP), slide = tool.stopAtStickMetres - stopOriginX
      for (let k = 0; k < 3; k++) item.worldPositionMetres[k] = item.worldPositionMetres[k]! + p[0]![k]! * slide
      break
    }
    default: {
      prepareNativeBar(tool.station, out)
      input.kind = tool.attachment; input.stopAt = tool.stopAtStickMetres; input.stopRelative[12] = tool.stopAtStickMetres
      input.footStation = tool.attachment === 'bar-setting' ? tool.barFootStationMetres : 0
      solveNativeToolContact(input as NativeToolContactWithToolInput, out.toolContact)
      nativeToolWorldPose(STICK, out.toolContact.toolMatrix, out)
      nativeToolWorldPose(STOP, out.toolContact.stopMatrix, out)
      if (out.toolContact.posesBar) applyNativeBar(tool.station, out)
      break
    }
  }
  entry(out, STOP).visibility = 'visible'; entry(out, STICK).visibility = 'visible'
}

function solvePhotograph(photo: SourceGearPhotograph, out: SourceAssemblyBuffer): void {
  const delta = out.deltas[6]!, p = out.points
  identity(delta)
  // Subject scope is genuine photograph composition only. Native capture still
  // enumerates every original and generated body with explicit visibility.
  for (const path of NATIVE_PATHS) { transformed(out, path, baseline(out, path), delta); entry(out, path).visibility = 'hidden' }
  for (const id of GEAR_IDS) { const path = SOURCE_GEAR_PART_PATHS[id]; transformed(out, path, baseline(out, path), delta); entry(out, path).visibility = 'hidden' }
  const pair = photo.pair === 'four-gears' ? null : SOURCE_GEAR_PHOTOGRAPHS[photo.pair]
  for (let i = 0; i < (pair ? 2 : 4); i++) {
    const id = pair ? pair.ids[i]! : GEAR_IDS[i]!, path = SOURCE_GEAR_PART_PATHS[id], item = entry(out, path)
    if (pair) {
      const centre = pair.centresSourcePixels[i]!
      p[0]![0] = (centre[0] - 320) / pair.pixelsPerMetre; p[0]![1] = (180 - (centre[1] - pair.rectSourcePixels[1])) / pair.pixelsPerMetre; p[0]![2] = -SOURCE_ASSEMBLY_DATUMS.gearFaceLocalZMetres
      rotate(item.worldPositionMetres, photo.displayPose.quaternion, p[0]!)
      for (let k = 0; k < 4; k++) item.worldQuaternion[k] = photo.displayPose.quaternion[k]!
    } else {
      const local = photo.fourGearPoses![id]; rotate(item.worldPositionMetres, photo.displayPose.quaternion, local.positionMetres); multiply(item.worldQuaternion, photo.displayPose.quaternion, local.quaternion)
    }
    for (let k = 0; k < 3; k++) item.worldPositionMetres[k] = item.worldPositionMetres[k]! + photo.displayPose.positionMetres[k]!
    item.visibility = 'visible'
    // A hidden assembly parent must never erase a selected child.
    let parent = path.slice(0, path.lastIndexOf('/'))
    while (parent !== ROOT && parent) { if (REST.has(parent)) entry(out, parent).visibility = 'visible'; parent = parent.slice(0, parent.lastIndexOf('/')) }
  }
}

/** Closed chosen native tool family, not recovery of an observed hidden pose.
 * Geometry is the unchanged approved 60a62a2e raw GLB, metres, native chassis
 * frame. The source-derived triangle tables below are immutable module data.
 * No world fulcrum, operating coefficient, spring model or renderer lives here.
 */
interface NativeToolBarFrameInput {
  rockerInChassis: Float64Array
  barInChassis: Float64Array
  leverInChassis: Float64Array
  footStation?: number
}
export interface NativeToolContactWithToolInput extends NativeToolBarFrameInput {
  kind: 'on-rocker' | 'bar-at-tool-end' | 'bar-setting'
  stopAt: number
  stopRelative: Float64Array
}
/** A retained manual setting has no hypothetical measuring tool. */
export interface NativeToolRetainedBarInput extends NativeToolBarFrameInput {
  kind: 'bar-retained'
  footStation: number
  /** Shared per-buffer scratch fields are ignored for retained bars. */
  stopAt?: number
  stopRelative?: Float64Array
}
export type NativeToolContactInput = NativeToolContactWithToolInput | NativeToolRetainedBarInput
export interface NativeToolContactBuffer {
  toolMatrix: Float64Array
  stopMatrix: Float64Array
  barMatrix: Float64Array
  leverAngle: number
  beta: number
  footStation: number
  posesBar: boolean
  /** False for retained bars; toolMatrix/stopMatrix then remain untouched/unused. */
  hasTool: boolean
  loopResidual: number
  ruleEndGap: number
  /** Per-instance scratch; never shared by different assembly solvers. */
  _roof: Float64Array
  _pair: Float64Array
  _polygonA: Float64Array
  _polygonB: Float64Array
  _tipX: number
  _tipY: number
  _tipZ: number
  _roofMinX: number
  _roofMaxX: number
  _seatY: number
}
export const NATIVE_TOOL_CONTACT_DATUMS = Object.freeze({
  rawSha256: '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c',
  stopFrontEdge: 0.006000000052154064,
  ruleLength: 0.20000000298023224,
  ruleWidth: 0.00800000037997961,
  ruleThickness: 0.003000000026077032,
  barWidth: 0.00634999992325902,
  notchRoof: 0.0023812500294297934,
  shaftTop: 0.7955999970436096,
  upperPinHeight: 0.80195,
  leverPinRadius: 0.127,
  numericalContactTolerance: 1e-8,
})
const D = NATIVE_TOOL_CONTACT_DATUMS
const EPS = D.numericalContactTolerance
const SHRINK = 1e-9
const ROOF = new Float64Array([
  -0.14524006843566895, 0.029294639825820923,
  -0.12604920566082, 0.025992659851908684,
  -0.1067836731672287, 0.02315874956548214,
  -0.08745487034320831, 0.020794589072465897,
  -0.06807424873113632, 0.018901577219367027,
  -0.048653289675712585, 0.01748083531856537,
  -0.0292035099118948, 0.016533205285668373,
  -0.009736426174640656, 0.016059251502156258,
  0.009736426174640656, 0.016059251502156258,
  0.0292035099118948, 0.016533205285668373,
  0.048653289675712585, 0.01748083531856537,
  0.06807424873113632, 0.018901577219367027,
  0.08745487034320831, 0.020794589072465897,
  0.1067836731672287, 0.02315874956548214,
  0.12604920566082, 0.025992659851908684,
  0.14524006843566895, 0.029294639825820923,
])
// Exact native clevis/shaft prisms. Upper-bar circular features are represented
// by their actual surface triangles, not these lower-seat material boxes.
const BAR_BOXES = new Float64Array([
  0, D.notchRoof, 0, D.barWidth, D.shaftTop, D.barWidth,
  0, 0, 0, 0.0015750000020489097, D.notchRoof, D.barWidth,
  0.004774999804794788, 0, 0, D.barWidth, D.notchRoof, D.barWidth,
])
// Native stop slot-surrounding prisms, plus the advisor's conservative knob
// envelope. This bound can reject marginal knob clearance; never certify an
// overlapping knob. It does not substitute any rendered solid.
const STOP_BOXES = new Float64Array([
  -0.006, 0, -0.006, 0.006, 0.004, 0.006,
  -0.006, 0.0074, -0.006, 0.006, 0.012, 0.006,
  -0.006, 0.004, -0.006, 0.006, 0.0074, -0.0042,
  -0.006, 0.004, 0.0042, 0.006, 0.0074, 0.006,
  -0.0035, -0.0035, -0.0035, 0.0035, 0, 0.0035,
])
const RULE_BOX = new Float64Array([0, 0, 0, D.ruleLength, D.ruleWidth, D.ruleThickness])

export function createNativeToolContactBuffer(): NativeToolContactBuffer {
  return {
    toolMatrix: new Float64Array(16), stopMatrix: new Float64Array(16),
    barMatrix: new Float64Array(16), leverAngle: 0, beta: 0,
    footStation: 0, posesBar: false, hasTool: false, loopResidual: 0, ruleEndGap: 0,
    _roof: new Float64Array(48), _pair: new Float64Array(16),
    _polygonA: new Float64Array(48), _polygonB: new Float64Array(48),
    _tipX: 0, _tipY: 0, _tipZ: 0, _roofMinX: 0, _roofMaxX: 0, _seatY: 0,
  }
}
function matrixFinite(m: Float64Array): boolean {
  if (m.length !== 16) return false
  for (let i = 0; i < 16; i++) if (!Number.isFinite(m[i]!)) return false
  return true
}
function multiplyMatrix(a: Float64Array, b: Float64Array, out: Float64Array): void {
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
    out[c * 4 + r] = a[r]! * b[c * 4]! + a[r + 4]! * b[c * 4 + 1]!
      + a[r + 8]! * b[c * 4 + 2]! + a[r + 12]! * b[c * 4 + 3]!
  }
}
/** inverse(target) * source, including actual small affine roundoff/scales. */
function relativeMatrix(source: Float64Array, target: Float64Array, out: Float64Array): void {
  const a = target[0]!, b = target[4]!, c = target[8]!
  const d = target[1]!, e = target[5]!, f = target[9]!
  const g = target[2]!, h = target[6]!, i = target[10]!
  const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
  const x0 = (e * i - f * h) / det, x1 = (c * h - b * i) / det, x2 = (b * f - c * e) / det
  const y0 = (f * g - d * i) / det, y1 = (a * i - c * g) / det, y2 = (c * d - a * f) / det
  const z0 = (d * h - e * g) / det, z1 = (b * g - a * h) / det, z2 = (a * e - b * d) / det
  for (let col = 0; col < 4; col++) {
    const offset = col * 4
    const x = source[offset]! - (col === 3 ? target[12]! : 0)
    const y = source[offset + 1]! - (col === 3 ? target[13]! : 0)
    const z = source[offset + 2]! - (col === 3 ? target[14]! : 0)
    out[offset] = x0 * x + x1 * y + x2 * z
    out[offset + 1] = y0 * x + y1 * y + y2 * z
    out[offset + 2] = z0 * x + z1 * y + z2 * z
    out[offset + 3] = col === 3 ? 1 : 0
  }
}
function prepareRoof(input: NativeToolContactInput, out: NativeToolContactBuffer): void {
  const r = input.rockerInChassis, roof = out._roof
  out._roofMinX = Infinity; out._roofMaxX = -Infinity
  for (let v = 0; v < 16; v++) {
    const x = ROOF[v * 2]!, y = ROOF[v * 2 + 1]!
    const k = v * 3
    roof[k] = r[0]! * x + r[4]! * y + r[12]!
    roof[k + 1] = r[1]! * x + r[5]! * y + r[13]!
    roof[k + 2] = r[2]! * x + r[6]! * y + r[14]!
    out._roofMinX = Math.min(out._roofMinX, roof[k]!)
    out._roofMaxX = Math.max(out._roofMaxX, roof[k]!)
  }
  out._tipX = roof[45]!; out._tipY = roof[46]!; out._tipZ = roof[47]!
}
function toolAtPitch(input: NativeToolContactWithToolInput, out: NativeToolContactBuffer, beta: number): void {
  const c = Math.cos(beta), s = Math.sin(beta), m = out.toolMatrix, rel = input.stopRelative
  m[0] = c; m[1] = -s; m[2] = 0; m[3] = 0
  m[4] = 0; m[5] = 0; m[6] = 1; m[7] = 0
  m[8] = -s; m[9] = -c; m[10] = 0; m[11] = 0
  // Actual stop-relative orientation and centre, including baseline roundoff.
  const x = rel[0]! * D.stopFrontEdge + rel[12]!
  const y = rel[1]! * D.stopFrontEdge + rel[13]!
  const z = rel[2]! * D.stopFrontEdge + rel[14]!
  m[12] = out._tipX - c * x + s * z
  m[13] = out._tipY + s * x + c * z
  m[14] = out._tipZ - y; m[15] = 1
  multiplyMatrix(m, rel, out.stopMatrix)
  out.beta = beta
}
function barAt(input: NativeToolContactInput, out: NativeToolContactBuffer, beta: number, x: number, y: number): number {
  const c = Math.cos(beta), s = Math.sin(beta), m = out.barMatrix, f = input.leverInChassis
  m[0] = 0; m[1] = 0; m[2] = 1; m[3] = 0
  m[4] = s; m[5] = c; m[6] = 0; m[7] = 0
  m[8] = -c; m[9] = s; m[10] = 0; m[11] = 0
  m[12] = x; m[13] = y; m[14] = out._tipZ - D.barWidth / 2; m[15] = 1
  const pinX = x + D.upperPinHeight * s - D.barWidth / 2 * c
  const pinY = y + D.upperPinHeight * c + D.barWidth / 2 * s
  out.leverAngle = Math.atan2(pinY - f[13]!, f[12]! - pinX)
  out.footStation = x - D.barWidth / 2 * c - input.rockerInChassis[12]!
  out.loopResidual = Math.hypot(pinX - f[12]!, pinY - f[13]!) - D.leverPinRadius
  out.ruleEndGap = input.kind === 'bar-retained' ? NaN
    : -c * (out.toolMatrix[12]! + D.ruleLength * c - x)
      + s * (out.toolMatrix[13]! - D.ruleLength * s - y) - D.barWidth
  // The bounded family uses the upper lever's left-side circle branch only.
  return pinX <= f[12]! + EPS ? out.loopResidual : NaN
}
/** Exact finite envelope of the 16 native roof vertices under the notch plane. */
function finiteSeat(out: NativeToolContactBuffer, beta: number, originX: number): boolean {
  const c = Math.cos(beta), s = Math.sin(beta)
  if (!(c > 1e-10)) return false
  const left = originX + D.notchRoof * s - D.barWidth * c
  const right = originX + D.notchRoof * s
  if (left < out._roofMinX - EPS || right > out._roofMaxX + EPS) return false
  const roof = out._roof, tangent = s / c
  let maximum = -Infinity
  for (let v = 0; v < 15; v++) {
    const k = v * 3, ax = roof[k]!, ay = roof[k + 1]!, bx = roof[k + 3]!, by = roof[k + 4]!
    const lo = Math.max(left, Math.min(ax, bx)), hi = Math.min(right, Math.max(ax, bx))
    if (lo > hi) continue
    const slope = (by - ay) / (bx - ax)
    const atLo = ay + (lo - ax) * slope - D.notchRoof / c - (originX - lo) * tangent
    const atHi = ay + (hi - ax) * slope - D.notchRoof / c - (originX - hi) * tangent
    maximum = Math.max(maximum, atLo, atHi)
  }
  out._seatY = maximum
  return Number.isFinite(maximum)
}
/** One trial edge; its raw finite footprint must still pass certification. */
function contactCandidate(input: NativeToolContactWithToolInput, out: NativeToolContactBuffer, beta: number, edge: number): number {
  toolAtPitch(input, out, beta)
  const c = Math.cos(beta), s = Math.sin(beta), roof = out._roof, tool = out.toolMatrix
  const endX = tool[12]! + c * D.ruleLength, endY = tool[13]! - s * D.ruleLength
  const k = -c * endX + s * endY - D.barWidth + edge
  let cx = NaN, cy = -Infinity
  for (let v = 0; v < 15; v++) {
    const j = v * 3, ax = roof[j]!, ay = roof[j + 1]!, bx = roof[j + 3]!, by = roof[j + 4]!
    const fa = -c * ax + s * ay - k, fb = -c * bx + s * by - k
    if (fa * fb > 0 || fa === fb) continue
    const fraction = fa / (fa - fb), x = ax + (bx - ax) * fraction, y = ay + (by - ay) * fraction
    if (y > cy) { cx = x; cy = y }
  }
  if (!Number.isFinite(cx)) return NaN
  return barAt(input, out, beta, cx - s * D.notchRoof + c * edge, cy - c * D.notchRoof - s * edge)
}
function stationCandidate(input: NativeToolContactInput, out: NativeToolContactBuffer, beta: number): number {
  if (input.kind === 'bar-retained') out.beta = beta
  else toolAtPitch(input, out, beta)
  const x = input.rockerInChassis[12]! + input.footStation! + D.barWidth / 2 * Math.cos(beta)
  if (!finiteSeat(out, beta, x)) return NaN
  return barAt(input, out, beta, x, out._seatY)
}
function evaluate(input: NativeToolContactInput, out: NativeToolContactBuffer, beta: number, edge: number): number {
  return input.kind === 'bar-setting' || input.kind === 'bar-retained'
    ? stationCandidate(input, out, beta) : contactCandidate(input, out, beta, edge)
}
/** Clip an actual triangle into a shrunken native material prism. */
function triangleInsideBox(out: NativeToolContactBuffer, boxes: Float64Array, box: number): boolean {
  let a = out._polygonA, b = out._polygonB, count = 3
  for (let plane = 0; plane < 6; plane++) {
    const axis = plane % 3, lower = plane < 3
    const bound = boxes[box + plane]! + (lower ? SHRINK : -SHRINK)
    let next = 0
    for (let v = 0; v < count; v++) {
      const p = v * 3, q = ((v + 1) % count) * 3
      const fa = lower ? a[p + axis]! - bound : bound - a[p + axis]!
      const fb = lower ? a[q + axis]! - bound : bound - a[q + axis]!
      if (fa >= 0) {
        b[next * 3] = a[p]!; b[next * 3 + 1] = a[p + 1]!; b[next * 3 + 2] = a[p + 2]!; next++
      }
      if ((fa >= 0) !== (fb >= 0)) {
        const t = fa / (fa - fb)
        for (let r = 0; r < 3; r++) b[next * 3 + r] = a[p + r]! + t * (a[q + r]! - a[p + r]!)
        next++
      }
    }
    if (next < 3) return false
    const swap = a; a = b; b = swap; count = next
  }
  let area = 0
  for (let v = 1; v < count - 1; v++) {
    const j = v * 3, k = j + 3
    const ax = a[j]! - a[0]!, ay = a[j + 1]! - a[1]!, az = a[j + 2]! - a[2]!
    const bx = a[k]! - a[0]!, by = a[k + 1]! - a[1]!, bz = a[k + 2]! - a[2]!
    area += Math.hypot(ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx) / 2
  }
  return area > 1e-16
}
function meshPenetratesBoxes(triangles: Float64Array, source: Float64Array, target: Float64Array,
  boxes: Float64Array, out: NativeToolContactBuffer): boolean {
  relativeMatrix(source, target, out._pair)
  const m = out._pair, p = out._polygonA
  for (let box = 0; box < boxes.length; box += 6) for (let triangle = 0; triangle < triangles.length; triangle += 9) {
    // Refill the same scratch polygon for every box, never clone a candidate.
    let minX = Infinity, minY = Infinity, minZ = Infinity, maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity
    for (let v = 0; v < 3; v++) {
      const j = triangle + v * 3, k = v * 3, x = triangles[j]!, y = triangles[j + 1]!, z = triangles[j + 2]!
      const px = m[0]! * x + m[4]! * y + m[8]! * z + m[12]!
      const py = m[1]! * x + m[5]! * y + m[9]! * z + m[13]!
      const pz = m[2]! * x + m[6]! * y + m[10]! * z + m[14]!
      p[k] = px; p[k + 1] = py; p[k + 2] = pz
      minX = Math.min(minX, px); maxX = Math.max(maxX, px)
      minY = Math.min(minY, py); maxY = Math.max(maxY, py)
      minZ = Math.min(minZ, pz); maxZ = Math.max(maxZ, pz)
    }
    if (maxX <= boxes[box]! + SHRINK || minX >= boxes[box + 3]! - SHRINK
      || maxY <= boxes[box + 1]! + SHRINK || minY >= boxes[box + 4]! - SHRINK
      || maxZ <= boxes[box + 2]! + SHRINK || minZ >= boxes[box + 5]! - SHRINK) continue
    if (triangleInsideBox(out, boxes, box)) return true
  }
  return false
}
function physicalError(input: NativeToolContactInput, out: NativeToolContactBuffer): string | null {
  const stop = out.stopMatrix, r = input.rockerInChassis, b = out.barMatrix, tool = out.toolMatrix
  if (input.kind !== 'bar-retained') {
    const sx = stop[12]! + stop[0]! * D.stopFrontEdge
    const sy = stop[13]! + stop[1]! * D.stopFrontEdge
    const sz = stop[14]! + stop[2]! * D.stopFrontEdge
    if (Math.hypot(sx - out._tipX, sy - out._tipY, sz - out._tipZ) > EPS) return 'Actual stop front-bottom edge is not on the native positive roof tip.'
    const roof = out._roof, dx = roof[45]! - roof[42]!, dy = roof[46]! - roof[43]!
    // Roof outward normal is transformed from its actual final native facet.
    const nativeDx = ROOF[30]! - ROOF[28]!, nativeDy = ROOF[31]! - ROOF[29]!
    const nx = -nativeDy * r[0]! + nativeDx * r[4]!, ny = -nativeDy * r[1]! + nativeDx * r[5]!
    if (!(Math.cos(out.beta) > 1e-10) || !(stop[4]! * nx + stop[5]! * ny > 0)
      || Math.abs(dx) < EPS || !Number.isFinite(dy)) return 'Native stop support must oppose the upward roof facet; inverted/vertical tools are outside this family.'
    if (meshPenetratesBoxes(ROCKER_TRIANGLES, r, tool, RULE_BOX, out)) return 'Rule penetrates the actual finite native rocker.'
    if (meshPenetratesBoxes(ROCKER_TRIANGLES, r, stop, STOP_BOXES, out)) return 'Stop penetrates the actual finite native rocker.'
    if (meshPenetratesBoxes(BAR_TRIANGLES, b, tool, RULE_BOX, out)) return 'Rule penetrates the actual finite native bar.'
    if (meshPenetratesBoxes(BAR_TRIANGLES, b, stop, STOP_BOXES, out)) return 'Stop penetrates the actual finite native bar.'
    if (input.kind === 'on-rocker') return null
  }
  if (!finiteSeat(out, out.beta, b[12]!) || Math.abs(b[13]! - out._seatY) > EPS) return 'Native bar clevis does not seat on the complete finite roof envelope.'
  if (meshPenetratesBoxes(ROCKER_TRIANGLES, r, b, BAR_BOXES, out)) return 'Actual native bar clevis/shaft penetrates the rocker.'
  const c = Math.cos(out.beta), s = Math.sin(out.beta), f = input.leverInChassis
  const px = b[12]! + D.upperPinHeight * s - D.barWidth / 2 * c
  const py = b[13]! + D.upperPinHeight * c + D.barWidth / 2 * s
  const pz = b[14]! + D.barWidth / 2
  if (px > f[12]! + EPS || Math.abs(pz - f[14]!) > EPS
    || Math.abs(Math.hypot(px - f[12]!, py - f[13]!) - D.leverPinRadius) > EPS) return 'Actual bar upper pin does not close the current 127 mm left-side lever loop.'
  if (input.kind === 'bar-retained') { out.ruleEndGap = NaN; return null }
  relativeMatrix(tool, b, out._pair)
  const m = out._pair
  const endY = m[1]! * D.ruleLength + m[13]!, endZ = m[2]! * D.ruleLength + m[14]!
  const y1 = endY + m[5]! * D.ruleWidth, y2 = endY + m[9]! * D.ruleThickness
  const y3 = y1 + m[9]! * D.ruleThickness
  const endX = m[0]! * D.ruleLength + m[12]!
  const x1 = endX + m[4]! * D.ruleWidth, x2 = endX + m[8]! * D.ruleThickness, x3 = x1 + m[8]! * D.ruleThickness
  if (Math.min(endY, y1, y2, y3) < D.notchRoof - EPS
    || Math.max(endY, y1, y2, y3) > D.shaftTop + EPS
    || Math.min(endX, x1, x2, x3) > EPS || Math.max(endX, x1, x2, x3) < D.barWidth - EPS) return 'The actual rule end does not cover the finite native bar shaft face.'
  out.ruleEndGap = endZ - D.barWidth
  if (out.ruleEndGap < -EPS) return 'Manual foot station has passed through the native rule-end contact.'
  if (input.kind === 'bar-at-tool-end' && Math.abs(out.ruleEndGap) > EPS) return 'Actual rule +X end is not contacting the native bar +Z shaft face.'
  return null
}
/** Also available for private countercontrols; callers normally use solve. */
export function assertNativeToolContact(input: NativeToolContactInput, out: NativeToolContactBuffer): void {
  prepareRoof(input, out)
  const error = physicalError(input, out)
  if (error) throw new Error(error)
}

export function solveNativeToolContact(input: NativeToolContactInput, out: NativeToolContactBuffer): void {
  if (!matrixFinite(input.rockerInChassis) || !matrixFinite(input.barInChassis)
    || !matrixFinite(input.leverInChassis)) throw new Error('Native tool contact requires finite current chassis-frame matrices.')
  if (input.kind !== 'bar-retained') {
    if (!Number.isFinite(input.stopAt) || !matrixFinite(input.stopRelative)) throw new Error('Native measuring tool requires its finite actual stop-relative matrix and station.')
    if (Math.abs(input.stopRelative[12]! - input.stopAt) > EPS) throw new Error('Actual stop-relative X translation must already equal stopAt.')
  }
  if ((input.kind === 'bar-setting' || input.kind === 'bar-retained') && !Number.isFinite(input.footStation)) throw new Error('Native manual bar setting requires its finite foot station in metres.')
  prepareRoof(input, out)
  out.posesBar = input.kind !== 'on-rocker'
  out.hasTool = input.kind !== 'bar-retained'
  if (input.kind === 'on-rocker') {
    const normal = input.barInChassis
    const beta = Math.atan2(normal[4]!, normal[5]!)
    toolAtPitch(input, out, beta)
    for (let i = 0; i < 16; i++) out.barMatrix[i] = normal[i]!
    out.footStation = normal[12]! + normal[8]! * D.barWidth / 2 - input.rockerInChassis[12]!
    out.leverAngle = Math.atan2(input.leverInChassis[1]!, -input.leverInChassis[0]!)
    out.loopResidual = 0; out.ruleEndGap = NaN
    const error = physicalError(input, out)
    if (error) throw new Error(error)
    return
  }
  const fx = input.leverInChassis[12]!, length = D.upperPinHeight
  let loSin: number, hiSin: number
  if (input.kind === 'bar-setting' || input.kind === 'bar-retained') {
    const footX = input.rockerInChassis[12]! + input.footStation!
    loSin = (fx - D.leverPinRadius - footX) / length
    hiSin = (fx - footX) / length
  } else {
    const extent = D.notchRoof + D.barWidth * 1.5
    loSin = (fx - D.leverPinRadius - out._roofMaxX - extent) / length
    hiSin = (fx - out._roofMinX + extent) / length
  }
  if (loSin >= 1 || hiSin <= -1) throw new Error('Current native lever circle cannot reach this finite rocker foot station.')
  const low = Math.asin(Math.max(-1 + 1e-12, loSin))
  const high = Math.asin(Math.min(1 - 1e-12, hiSin))
  if (!(high > low)) throw new Error('No finite native left-side lever-loop bracket.')
  let rejection = 'No bracketed current 127 mm lever loop exists on the finite native rocker roof.'
  const edgeCount = input.kind === 'bar-setting' || input.kind === 'bar-retained' ? 1 : 2
  for (let edgeIndex = 0; edgeIndex < edgeCount; edgeIndex++) {
    const edge = edgeIndex === 0 ? 0 : D.barWidth
    let previousBeta = low, previousGap = evaluate(input, out, low, edge)
    // A bounded scan locates only continuous finite-roof brackets. It never
    // extrapolates a point contact beyond the native roof or lever branch.
    for (let step = 1; step <= 256; step++) {
      const beta = low + (high - low) * step / 256
      const gap = evaluate(input, out, beta, edge)
      if (Number.isFinite(gap) && Number.isFinite(previousGap) && gap * previousGap <= 0) {
        let a = previousBeta, ga = previousGap, b = beta
        for (let iteration = 0; iteration < 56; iteration++) {
          const mid = (a + b) / 2, gm = evaluate(input, out, mid, edge)
          if (!Number.isFinite(gm)) break
          if (ga * gm <= 0) b = mid
          else { a = mid; ga = gm }
        }
        const root = (a + b) / 2
        const residual = evaluate(input, out, root, edge)
        if (Number.isFinite(residual) && Math.abs(residual) <= EPS) {
          const error = physicalError(input, out)
          if (!error) return
          // Keep the whole-object blocker rather than a wrong-edge seat error.
          if (rejection.startsWith('No bracketed') || error.startsWith('Rule penetrates')) rejection = error
        }
      }
      previousBeta = beta; previousGap = gap
    }
  }
  throw new Error(rejection)
}

// Full actual raw rocker_triangles surface triangles; approved GLB hash above.
const ROCKER_TRIANGLES = new Float64Array([
  -0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, -0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  -0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, -0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, -0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, 0.0012499999720603228,
  -0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, -0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, -0.0012499999720603228,
  -0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, 0.0012499999720603228,
  -0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, -0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228,
  -0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, -0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, -0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228,
  -0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, -0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228,
  -0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228,
  -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228,
  -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, 1.4989677369763336e-16, 0.0, -0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, 1.4989677369763336e-16, 0.0, -0.0012499999720603228, 1.4989677369763336e-16, 0.0, 0.0012499999720603228,
  1.4989677369763336e-16, 0.0, 0.0012499999720603228, 1.4989677369763336e-16, 0.0, -0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228,
  1.4989677369763336e-16, 0.0, 0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228,
  0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, 0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228,
  0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, 0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, 0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228,
  0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, 0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, -0.0012499999720603228,
  0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, 0.0012499999720603228,
  0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, -0.0012499999720603228,
  0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, -0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, 0.0012499999720603228,
  0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, -0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, 0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228,
  0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, -0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.12604920566082, 0.025992659851908684, 0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.12604920566082, 0.025992659851908684, -0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.12604920566082, 0.025992659851908684, -0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, 0.0012499999720603228,
  0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, 0.12604920566082, 0.025992659851908684, -0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, -0.0012499999720603228,
  0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, 0.0012499999720603228,
  0.08745487034320831, 0.020794589072465897, 0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, -0.0012499999720603228,
  0.08745487034320831, 0.020794589072465897, 0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, 0.06807424873113632, 0.018901577219367027, 0.0012499999720603228,
  0.06807424873113632, 0.018901577219367027, 0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, 0.06807424873113632, 0.018901577219367027, -0.0012499999720603228,
  0.06807424873113632, 0.018901577219367027, 0.0012499999720603228, 0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, 0.0012499999720603228,
  0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, 0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, -0.0012499999720603228,
  0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, 0.0012499999720603228,
  0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, -0.0012499999720603228,
  0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, 0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, 0.0012499999720603228,
  -0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228,
  -0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, 0.0012499999720603228,
  -0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, -0.0012499999720603228,
  -0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, 0.0012499999720603228,
  -0.06807424873113632, 0.018901577219367027, 0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, -0.0012499999720603228,
  -0.06807424873113632, 0.018901577219367027, 0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, -0.08745487034320831, 0.020794589072465897, 0.0012499999720603228,
  -0.08745487034320831, 0.020794589072465897, 0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, -0.08745487034320831, 0.020794589072465897, -0.0012499999720603228,
  -0.08745487034320831, 0.020794589072465897, 0.0012499999720603228, -0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, 0.0012499999720603228,
  -0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, -0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, -0.0012499999720603228,
  -0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, -0.12604920566082, 0.025992659851908684, 0.0012499999720603228,
  -0.12604920566082, 0.025992659851908684, 0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, -0.12604920566082, 0.025992659851908684, -0.0012499999720603228,
  -0.12604920566082, 0.025992659851908684, 0.0012499999720603228, -0.12604920566082, 0.025992659851908684, -0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, 0.0012499999720603228,
  -0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, -0.12604920566082, 0.025992659851908684, -0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, -0.0012499999720603228,
  -0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, -0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  -0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, -0.0012499999720603228,
  -0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, -0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, -0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  -0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, -0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, -0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  0.13403038680553436, 0.01671409420669079, 0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228,
  0.1337723582983017, 0.01575111411511898, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, 0.0012499999720603228,
  0.13393078744411469, 0.015957588329911232, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228,
  0.13393078744411469, 0.015957588329911232, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.13403038680553436, 0.016198035329580307, 0.0012499999720603228,
  0.13403038680553436, 0.016198035329580307, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, 0.0012499999720603228,
  0.13356587290763855, 0.0173194482922554, 0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, 0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, 0.0012499999720603228,
  0.1337723582983017, 0.01575111411511898, 0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, 0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, 0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, 0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, 0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, 0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, 0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, 0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, 0.0012499999720603228,
  0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, 0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, 0.0012499999720603228,
  0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, 0.0012499999720603228, 0.13403038680553436, 0.01671409420669079, 0.0012499999720603228,
  0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228,
  0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228,
  0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228,
  0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, 0.0012499999720603228,
  0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, 0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228,
  0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, 0.0012499999720603228, 1.4989677369763336e-16, 0.0, 0.0012499999720603228,
  1.4989677369763336e-16, 0.0, 0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, 0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228,
  1.4989677369763336e-16, 0.0, 0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, -0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228,
  0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, 1.4989677369763336e-16, 0.0, 0.0012499999720603228, 0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228,
  0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, 1.4989677369763336e-16, 0.0, 0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228,
  0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, 0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, -0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228,
  0.13256892561912537, 0.0173194482922554, 0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, 0.0012499999720603228, 0.12604920566082, 0.025992659851908684, 0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, 0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, 0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, 0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, 0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, 0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, 0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, 0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, 0.0012499999720603228,
  0.13306739926338196, 0.015459113754332066, 0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, 0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, 0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, 0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, 0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, 0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, 0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228,
  0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, 0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, 0.0012499999720603228,
  -0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, 0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, 0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, 0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, 0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228,
  0.1323624551296234, 0.017161013558506966, 0.0012499999720603228, 0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, 0.0012499999720603228,
  0.13220401108264923, 0.016954539343714714, 0.0012499999720603228, 0.12604920566082, 0.025992659851908684, 0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, 0.0012499999720603228,
  0.13220401108264923, 0.016954539343714714, 0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, 0.0012499999720603228,
  0.06807424873113632, 0.018901577219367027, 0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, 0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, 0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, 0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, 0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, 0.0012499999720603228,
  0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228,
  0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228,
  0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, 0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, 0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, 0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, 0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, 0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, 0.0012499999720603228,
  -0.06807424873113632, 0.018901577219367027, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, 0.0012499999720603228,
  -0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  -0.048653289675712585, 0.01748083531856537, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, 0.0012499999720603228,
  -0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228,
  -0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, 0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, 0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, 0.0012499999720603228,
  -0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, 0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, 0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, 0.0012499999720603228,
  0.13210442662239075, 0.01671409420669079, 0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, 0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, 0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, 0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, 0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, 0.0012499999720603228, 0.06807424873113632, 0.018901577219367027, 0.0012499999720603228,
  -0.0760893002152443, 0.003555282950401306, 0.0012499999720603228, -0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.057103291153907776, 0.0020004825200885534, 0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228,
  -0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, 0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, 0.0012499999720603228,
  -0.14524006843566895, 0.029294639825820923, 0.0012499999720603228, -0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, -0.12604920566082, 0.025992659851908684, 0.0012499999720603228,
  -0.12604920566082, 0.025992659851908684, 0.0012499999720603228, -0.14625456929206848, 0.023799503222107887, 0.0012499999720603228, -0.1327572613954544, 0.010871742852032185, 0.0012499999720603228,
  -0.12604920566082, 0.025992659851908684, 0.0012499999720603228, -0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, 0.0012499999720603228,
  -0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, -0.1327572613954544, 0.010871742852032185, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228,
  -0.1067836731672287, 0.02315874956548214, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.08745487034320831, 0.020794589072465897, 0.0012499999720603228,
  -0.08745487034320831, 0.020794589072465897, 0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, 0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, 0.0012499999720603228,
  -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, 0.0012499999720603228,
  0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, 0.0012499999720603228,
  0.0292035099118948, 0.016533205285668373, 0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, 0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, 0.0012499999720603228,
  0.13403038680553436, 0.016198035329580307, -0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, -0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  0.1328093707561493, 0.01741904392838478, -0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, -0.0012499999720603228, 0.12604920566082, 0.025992659851908684, -0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, -0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, -0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, -0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, -0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, -0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, -0.0012499999720603228,
  -0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, 1.4989677369763336e-16, 0.0, -0.0012499999720603228, -0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228,
  -0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, 1.4989677369763336e-16, 0.0, -0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228,
  -0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, -0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, -0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, -0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, -0.0012499999720603228,
  0.13256892561912537, 0.015592680312693119, -0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, -0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, -0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, -0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, -0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, -0.0012499999720603228,
  0.13332542777061462, 0.01549308467656374, -0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, -0.0012499999720603228, 0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, -0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, -0.0012499999720603228,
  0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, -0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, -0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, -0.0012499999720603228,
  0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, -0.0012499999720603228, 0.13403038680553436, 0.016198035329580307, -0.0012499999720603228,
  0.1337723582983017, 0.017161013558506966, -0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, -0.0012499999720603228,
  0.13393078744411469, 0.016954539343714714, -0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228,
  0.13393078744411469, 0.016954539343714714, -0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, 0.13403038680553436, 0.01671409420669079, -0.0012499999720603228,
  0.13403038680553436, 0.01671409420669079, -0.0012499999720603228, 0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, -0.0012499999720603228,
  0.1337723582983017, 0.017161013558506966, -0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, -0.0012499999720603228, 0.14524006843566895, 0.029294639825820923, -0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, -0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, -0.0012499999720603228,
  0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, -0.0012499999720603228, 0.12604920566082, 0.025992659851908684, -0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, -0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, -0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, -0.0012499999720603228,
  0.12604920566082, 0.025992659851908684, -0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, -0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, -0.0012499999720603228,
  0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.0292035099118948, 0.016533205285668373, -0.0012499999720603228,
  0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  -0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, -0.0012499999720603228, 1.4989677369763336e-16, 0.0, -0.0012499999720603228,
  1.4989677369763336e-16, 0.0, -0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, -0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228,
  1.4989677369763336e-16, 0.0, -0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, 0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228,
  0.1323624551296234, 0.017161013558506966, -0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, -0.0012499999720603228, 0.1067836731672287, 0.02315874956548214, -0.0012499999720603228,
  0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, -0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, -0.0012499999720603228,
  0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, -0.0012499999720603228, 0.08745487034320831, 0.020794589072465897, -0.0012499999720603228,
  0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228,
  0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.06807424873113632, 0.018901577219367027, -0.0012499999720603228,
  0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.048653289675712585, 0.01748083531856537, -0.0012499999720603228,
  -0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, -0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.09503384679555893, 0.005552859045565128, -0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  -0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, -0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228,
  -0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228,
  -0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228,
  -0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, -0.0012499999720603228,
  -0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, -0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, -0.0012499999720603228,
  0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, -0.0012499999720603228, 0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, -0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, -0.0012499999720603228,
  0.01904826983809471, 0.00022235662618186325, -0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, -0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228,
  0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, -0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, 0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228,
  -0.08745487034320831, 0.020794589072465897, -0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, -0.06807424873113632, 0.018901577219367027, -0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, -0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.048653289675712585, 0.01748083531856537, -0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228,
  -0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, -0.0292035099118948, 0.016533205285668373, -0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, -0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, -0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, -0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, -0.0012499999720603228,
  0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, -0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, -0.0012499999720603228,
  0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, 0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, -0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, -0.0012499999720603228, -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, -0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228,
  -0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, -0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228,
  -0.14625456929206848, 0.023799503222107887, -0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, -0.1327572613954544, 0.010871742852032185, -0.0012499999720603228,
  -0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, -0.14524006843566895, 0.029294639825820923, -0.0012499999720603228, -0.12604920566082, 0.025992659851908684, -0.0012499999720603228,
  -0.1327572613954544, 0.010871742852032185, -0.0012499999720603228, -0.12604920566082, 0.025992659851908684, -0.0012499999720603228, -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, -0.12604920566082, 0.025992659851908684, -0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, -0.0012499999720603228,
  -0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, -0.1067836731672287, 0.02315874956548214, -0.0012499999720603228, -0.08745487034320831, 0.020794589072465897, -0.0012499999720603228,
  0.0760893002152443, 0.003555282950401306, -0.0012499999720603228, 0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, -0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, 0.057103291153907776, 0.0020004825200885534, -0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228,
  0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, 0.03808615729212761, 0.0008893053163774312, -0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, -0.0012499999720603228,
  0.009736426174640656, 0.016059251502156258, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228,
  0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228,
  0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, -0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, 0.11392659693956375, 0.007992122322320938, -0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, -0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, 0.09503384679555893, 0.005552859045565128, -0.0012499999720603228, 0.0760893002152443, 0.003555282950401306, -0.0012499999720603228,
  0.002298097126185894, 0.005701902788132429, -0.00352824991568923, 0.003606244456022978, 0.004393755458295345, -0.00352824991568923, 0.0016250000335276127, 0.005185417365282774, -0.00352824991568923,
  0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, 0.003606244456022978, 0.004393755458295345, -0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, -0.00352824991568923,
  0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, 0.0008411618764512241, 0.004860741086304188, -0.00352824991568923,
  0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, -0.00352824991568923,
  0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, -3.483595049150721e-18, 0.004749999847263098, -0.00352824991568923,
  -3.483595049150721e-18, 0.004749999847263098, -0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, -0.00352824991568923,
  -3.483595049150721e-18, 0.004749999847263098, -0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, -0.00352824991568923, -0.0008411618764512241, 0.004860741086304188, -0.00352824991568923,
  -0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, -0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, -0.00352824991568923,
  -0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, -0.0016250000335276127, 0.005185417365282774, -0.00352824991568923,
  -0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, -0.00352824991568923,
  -0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, -0.002298097126185894, 0.005701902788132429, -0.00352824991568923,
  -0.002298097126185894, 0.005701902788132429, -0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, -0.003606244456022978, 0.004393755458295345, -0.00352824991568923,
  -0.002298097126185894, 0.005701902788132429, -0.00352824991568923, -0.003606244456022978, 0.004393755458295345, -0.00352824991568923, -0.002814582549035549, 0.0063749998807907104, -0.00352824991568923,
  -0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, -0.003606244456022978, 0.004393755458295345, -0.00352824991568923, -0.00441672932356596, 0.005450000055134296, -0.00352824991568923,
  -0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, -0.00441672932356596, 0.005450000055134296, -0.00352824991568923, -0.0031392588280141354, 0.007158838212490082, -0.00352824991568923,
  -0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, -0.00441672932356596, 0.005450000055134296, -0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923,
  -0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, -0.0032500000670552254, 0.00800000037997961, -0.00352824991568923,
  -0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, -0.005100000184029341, 0.00800000037997961, -0.00352824991568923,
  -0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, -0.005100000184029341, 0.00800000037997961, -0.00352824991568923, -0.0031392588280141354, 0.008841161616146564, -0.00352824991568923,
  -0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, -0.005100000184029341, 0.00800000037997961, -0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, -0.00352824991568923,
  -0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, -0.002814582549035549, 0.009624999947845936, -0.00352824991568923,
  -0.002814582549035549, 0.009624999947845936, -0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, -0.00441672932356596, 0.01054999977350235, -0.00352824991568923,
  -0.002814582549035549, 0.009624999947845936, -0.00352824991568923, -0.00441672932356596, 0.01054999977350235, -0.00352824991568923, -0.002298097126185894, 0.01029809657484293, -0.00352824991568923,
  -0.002298097126185894, 0.01029809657484293, -0.00352824991568923, -0.00441672932356596, 0.01054999977350235, -0.00352824991568923, -0.003606244456022978, 0.011606244370341301, -0.00352824991568923,
  -0.002298097126185894, 0.01029809657484293, -0.00352824991568923, -0.003606244456022978, 0.011606244370341301, -0.00352824991568923, -0.0016250000335276127, 0.01081458292901516, -0.00352824991568923,
  -0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, -0.003606244456022978, 0.011606244370341301, -0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, -0.00352824991568923,
  -0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, -0.0008411618764512241, 0.011139258742332458, -0.00352824991568923,
  -0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, -0.00352824991568923,
  -0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, 9.20650057217565e-19, 0.011249999515712261, -0.00352824991568923,
  9.20650057217565e-19, 0.011249999515712261, -0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, -0.00352824991568923,
  9.20650057217565e-19, 0.011249999515712261, -0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, -0.00352824991568923, 0.0008411618764512241, 0.011139258742332458, -0.00352824991568923,
  0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, -0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, -0.00352824991568923,
  0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, 0.0016250000335276127, 0.01081458292901516, -0.00352824991568923,
  0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, -0.00352824991568923,
  0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, 0.002298097126185894, 0.01029809657484293, -0.00352824991568923,
  0.002298097126185894, 0.01029809657484293, -0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, 0.003606244456022978, 0.011606244370341301, -0.00352824991568923,
  0.002298097126185894, 0.01029809657484293, -0.00352824991568923, 0.003606244456022978, 0.011606244370341301, -0.00352824991568923, 0.002814582549035549, 0.009624999947845936, -0.00352824991568923,
  0.002814582549035549, 0.009624999947845936, -0.00352824991568923, 0.003606244456022978, 0.011606244370341301, -0.00352824991568923, 0.00441672932356596, 0.01054999977350235, -0.00352824991568923,
  0.002814582549035549, 0.009624999947845936, -0.00352824991568923, 0.00441672932356596, 0.01054999977350235, -0.00352824991568923, 0.0031392588280141354, 0.008841161616146564, -0.00352824991568923,
  0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, 0.00441672932356596, 0.01054999977350235, -0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, -0.00352824991568923,
  0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, 0.0032500000670552254, 0.00800000037997961, -0.00352824991568923,
  0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, 0.005100000184029341, 0.00800000037997961, -0.00352824991568923,
  0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, 0.005100000184029341, 0.00800000037997961, -0.00352824991568923, 0.0031392588280141354, 0.007158838212490082, -0.00352824991568923,
  0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, 0.005100000184029341, 0.00800000037997961, -0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923,
  0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, 0.002814582549035549, 0.0063749998807907104, -0.00352824991568923,
  0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, 0.00441672932356596, 0.005450000055134296, -0.00352824991568923,
  0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, 0.00441672932356596, 0.005450000055134296, -0.00352824991568923, 0.002298097126185894, 0.005701902788132429, -0.00352824991568923,
  0.002298097126185894, 0.005701902788132429, -0.00352824991568923, 0.00441672932356596, 0.005450000055134296, -0.00352824991568923, 0.003606244456022978, 0.004393755458295345, -0.00352824991568923,
  -0.005100000184029341, 0.00800000037997961, -0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, -0.00352824991568923,
  -0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, -0.0012499999720603228,
  -0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, -0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, -0.00352824991568923,
  -0.00441672932356596, 0.01054999977350235, -0.00352824991568923, -0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, -0.0012499999720603228,
  -0.00441672932356596, 0.01054999977350235, -0.00352824991568923, -0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, -0.00352824991568923,
  -0.003606244456022978, 0.011606244370341301, -0.00352824991568923, -0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, -0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228,
  -0.003606244456022978, 0.011606244370341301, -0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228, -0.0025500000920146704, 0.01241672970354557, -0.00352824991568923,
  -0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228,
  -0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, -0.00352824991568923,
  -0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, -0.0012499999720603228,
  -0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, -0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, -0.00352824991568923,
  -1.444712402252067e-18, 0.013100000098347664, -0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, -0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228,
  -1.444712402252067e-18, 0.013100000098347664, -0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, -0.00352824991568923,
  0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, -0.0012499999720603228, 0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228,
  0.0013199771055951715, 0.012926221825182438, -0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228, 0.0025500000920146704, 0.01241672970354557, -0.00352824991568923,
  0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, -0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, -0.0012499999720603228,
  0.0025500000920146704, 0.01241672970354557, -0.00352824991568923, 0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, -0.00352824991568923,
  0.003606244456022978, 0.011606244370341301, -0.00352824991568923, 0.003606244456022978, 0.011606244370341301, -0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, -0.0012499999720603228,
  0.003606244456022978, 0.011606244370341301, -0.00352824991568923, 0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, -0.00352824991568923,
  0.00441672932356596, 0.01054999977350235, -0.00352824991568923, 0.00441672932356596, 0.01054999977350235, -0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228,
  0.00441672932356596, 0.01054999977350235, -0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, -0.00352824991568923,
  0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, -0.0012499999720603228,
  0.0049262214452028275, 0.009319976903498173, -0.00352824991568923, 0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, -0.00352824991568923,
  0.005100000184029341, 0.00800000037997961, -0.00352824991568923, 0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, -0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923,
  0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, -0.0012499999720603228,
  0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, 0.00441672932356596, 0.005450000055134296, -0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, -0.00352824991568923,
  0.00441672932356596, 0.005450000055134296, -0.00352824991568923, 0.00441672932356596, 0.005450000055134296, -0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, -0.0012499999720603228,
  0.00441672932356596, 0.005450000055134296, -0.00352824991568923, 0.003606244456022978, 0.004393755458295345, -0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, -0.00352824991568923,
  0.003606244456022978, 0.004393755458295345, -0.00352824991568923, 0.003606244456022978, 0.004393755458295345, -0.0012499999720603228, 0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228,
  0.003606244456022978, 0.004393755458295345, -0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, 0.0025500000920146704, 0.003583270590752363, -0.00352824991568923,
  0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228,
  0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, -0.00352824991568923,
  0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, -0.0012499999720603228,
  0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, -0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, -0.00352824991568923,
  5.46656452594143e-18, 0.002899999963119626, -0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, -0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228,
  5.46656452594143e-18, 0.002899999963119626, -0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, -0.00352824991568923,
  -0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, -0.0012499999720603228, -0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228,
  -0.0013199771055951715, 0.003073778236284852, -0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, -0.0025500000920146704, 0.003583270590752363, -0.00352824991568923,
  -0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, -0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, -0.0012499999720603228,
  -0.0025500000920146704, 0.003583270590752363, -0.00352824991568923, -0.003606244456022978, 0.004393755458295345, -0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, -0.00352824991568923,
  -0.003606244456022978, 0.004393755458295345, -0.00352824991568923, -0.003606244456022978, 0.004393755458295345, -0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, -0.0012499999720603228,
  -0.003606244456022978, 0.004393755458295345, -0.00352824991568923, -0.00441672932356596, 0.005450000055134296, -0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, -0.00352824991568923,
  -0.00441672932356596, 0.005450000055134296, -0.00352824991568923, -0.00441672932356596, 0.005450000055134296, -0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228,
  -0.00441672932356596, 0.005450000055134296, -0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923,
  -0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, -0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228,
  -0.0049262214452028275, 0.0066800229251384735, -0.00352824991568923, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, -0.00352824991568923,
  -0.005100000184029341, 0.00800000037997961, -0.00352824991568923, -0.005100000184029341, 0.00800000037997961, -0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, -0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228,
  -0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228, -0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, -0.00441672932356596, 0.01054999977350235, 0.00352824991568923,
  -0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, 0.00352824991568923, -0.00441672932356596, 0.01054999977350235, 0.0012499999720603228,
  -0.00441672932356596, 0.01054999977350235, 0.0012499999720603228, -0.00441672932356596, 0.01054999977350235, 0.00352824991568923, -0.003606244456022978, 0.011606244370341301, 0.00352824991568923,
  -0.00441672932356596, 0.01054999977350235, 0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, 0.00352824991568923, -0.003606244456022978, 0.011606244370341301, 0.0012499999720603228,
  -0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, -0.003606244456022978, 0.011606244370341301, 0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, 0.00352824991568923,
  -0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, -0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228,
  -0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, -0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, 0.00352824991568923,
  -0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228,
  -0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, -0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, 0.00352824991568923,
  -0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, 0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228,
  -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228, -1.444712402252067e-18, 0.013100000098347664, 0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, 0.00352824991568923,
  -1.444712402252067e-18, 0.013100000098347664, 0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228,
  0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, 0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, 0.00352824991568923,
  0.0013199771055951715, 0.012926221825182438, 0.0012499999720603228, 0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228,
  0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, 0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, 0.003606244456022978, 0.011606244370341301, 0.00352824991568923,
  0.0025500000920146704, 0.01241672970354557, 0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, 0.00352824991568923, 0.003606244456022978, 0.011606244370341301, 0.0012499999720603228,
  0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, 0.003606244456022978, 0.011606244370341301, 0.00352824991568923, 0.00441672932356596, 0.01054999977350235, 0.00352824991568923,
  0.003606244456022978, 0.011606244370341301, 0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, 0.00352824991568923, 0.00441672932356596, 0.01054999977350235, 0.0012499999720603228,
  0.00441672932356596, 0.01054999977350235, 0.0012499999720603228, 0.00441672932356596, 0.01054999977350235, 0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, 0.00352824991568923,
  0.00441672932356596, 0.01054999977350235, 0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228,
  0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228, 0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, 0.005100000184029341, 0.00800000037997961, 0.00352824991568923,
  0.0049262214452028275, 0.009319976903498173, 0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, 0.00352824991568923, 0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.005100000184029341, 0.00800000037997961, 0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923,
  0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228,
  0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, 0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, 0.00441672932356596, 0.005450000055134296, 0.00352824991568923,
  0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, 0.00352824991568923, 0.00441672932356596, 0.005450000055134296, 0.0012499999720603228,
  0.00441672932356596, 0.005450000055134296, 0.0012499999720603228, 0.00441672932356596, 0.005450000055134296, 0.00352824991568923, 0.003606244456022978, 0.004393755458295345, 0.00352824991568923,
  0.00441672932356596, 0.005450000055134296, 0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, 0.00352824991568923, 0.003606244456022978, 0.004393755458295345, 0.0012499999720603228,
  0.003606244456022978, 0.004393755458295345, 0.0012499999720603228, 0.003606244456022978, 0.004393755458295345, 0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, 0.00352824991568923,
  0.003606244456022978, 0.004393755458295345, 0.0012499999720603228, 0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228,
  0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, 0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, 0.00352824991568923,
  0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228,
  0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, 0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, 0.00352824991568923,
  0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, 0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, 0.0012499999720603228,
  5.46656452594143e-18, 0.002899999963119626, 0.0012499999720603228, 5.46656452594143e-18, 0.002899999963119626, 0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, 0.00352824991568923,
  5.46656452594143e-18, 0.002899999963119626, 0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228,
  -0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, -0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, 0.00352824991568923,
  -0.0013199771055951715, 0.003073778236284852, 0.0012499999720603228, -0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228,
  -0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, -0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, -0.003606244456022978, 0.004393755458295345, 0.00352824991568923,
  -0.0025500000920146704, 0.003583270590752363, 0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, 0.00352824991568923, -0.003606244456022978, 0.004393755458295345, 0.0012499999720603228,
  -0.003606244456022978, 0.004393755458295345, 0.0012499999720603228, -0.003606244456022978, 0.004393755458295345, 0.00352824991568923, -0.00441672932356596, 0.005450000055134296, 0.00352824991568923,
  -0.003606244456022978, 0.004393755458295345, 0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, 0.00352824991568923, -0.00441672932356596, 0.005450000055134296, 0.0012499999720603228,
  -0.00441672932356596, 0.005450000055134296, 0.0012499999720603228, -0.00441672932356596, 0.005450000055134296, 0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923,
  -0.00441672932356596, 0.005450000055134296, 0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228,
  -0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, -0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, -0.005100000184029341, 0.00800000037997961, 0.00352824991568923,
  -0.0049262214452028275, 0.0066800229251384735, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.00352824991568923, -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228,
  -0.005100000184029341, 0.00800000037997961, 0.0012499999720603228, -0.005100000184029341, 0.00800000037997961, 0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, 0.00352824991568923,
  -3.483595049150721e-18, 0.004749999847263098, 0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, 0.00352824991568923, 0.0008411618764512241, 0.004860741086304188, 0.00352824991568923,
  0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, 0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, 0.00352824991568923,
  0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, 0.0016250000335276127, 0.005185417365282774, 0.00352824991568923,
  0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, 0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, 0.00352824991568923,
  0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, 0.002298097126185894, 0.005701902788132429, 0.00352824991568923,
  0.002298097126185894, 0.005701902788132429, 0.00352824991568923, 0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, 0.003606244456022978, 0.004393755458295345, 0.00352824991568923,
  0.002298097126185894, 0.005701902788132429, 0.00352824991568923, 0.003606244456022978, 0.004393755458295345, 0.00352824991568923, 0.002814582549035549, 0.0063749998807907104, 0.00352824991568923,
  0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, 0.003606244456022978, 0.004393755458295345, 0.00352824991568923, 0.00441672932356596, 0.005450000055134296, 0.00352824991568923,
  0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, 0.00441672932356596, 0.005450000055134296, 0.00352824991568923, 0.0031392588280141354, 0.007158838212490082, 0.00352824991568923,
  0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, 0.00441672932356596, 0.005450000055134296, 0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923,
  0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, 0.0032500000670552254, 0.00800000037997961, 0.00352824991568923,
  0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, 0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, 0.005100000184029341, 0.00800000037997961, 0.00352824991568923,
  0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, 0.005100000184029341, 0.00800000037997961, 0.00352824991568923, 0.0031392588280141354, 0.008841161616146564, 0.00352824991568923,
  0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, 0.005100000184029341, 0.00800000037997961, 0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, 0.00352824991568923,
  0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, 0.002814582549035549, 0.009624999947845936, 0.00352824991568923,
  0.002814582549035549, 0.009624999947845936, 0.00352824991568923, 0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, 0.00441672932356596, 0.01054999977350235, 0.00352824991568923,
  0.002814582549035549, 0.009624999947845936, 0.00352824991568923, 0.00441672932356596, 0.01054999977350235, 0.00352824991568923, 0.002298097126185894, 0.01029809657484293, 0.00352824991568923,
  0.002298097126185894, 0.01029809657484293, 0.00352824991568923, 0.00441672932356596, 0.01054999977350235, 0.00352824991568923, 0.003606244456022978, 0.011606244370341301, 0.00352824991568923,
  0.002298097126185894, 0.01029809657484293, 0.00352824991568923, 0.003606244456022978, 0.011606244370341301, 0.00352824991568923, 0.0016250000335276127, 0.01081458292901516, 0.00352824991568923,
  0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, 0.003606244456022978, 0.011606244370341301, 0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, 0.00352824991568923,
  0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, 0.0008411618764512241, 0.011139258742332458, 0.00352824991568923,
  0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, 0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, 0.00352824991568923,
  0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, 9.20650057217565e-19, 0.011249999515712261, 0.00352824991568923,
  9.20650057217565e-19, 0.011249999515712261, 0.00352824991568923, 0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, 0.00352824991568923,
  9.20650057217565e-19, 0.011249999515712261, 0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, 0.00352824991568923, -0.0008411618764512241, 0.011139258742332458, 0.00352824991568923,
  -0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, -1.444712402252067e-18, 0.013100000098347664, 0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, 0.00352824991568923,
  -0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, -0.0016250000335276127, 0.01081458292901516, 0.00352824991568923,
  -0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, -0.0013199771055951715, 0.012926221825182438, 0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, 0.00352824991568923,
  -0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, -0.002298097126185894, 0.01029809657484293, 0.00352824991568923,
  -0.002298097126185894, 0.01029809657484293, 0.00352824991568923, -0.0025500000920146704, 0.01241672970354557, 0.00352824991568923, -0.003606244456022978, 0.011606244370341301, 0.00352824991568923,
  -0.002298097126185894, 0.01029809657484293, 0.00352824991568923, -0.003606244456022978, 0.011606244370341301, 0.00352824991568923, -0.002814582549035549, 0.009624999947845936, 0.00352824991568923,
  -0.002814582549035549, 0.009624999947845936, 0.00352824991568923, -0.003606244456022978, 0.011606244370341301, 0.00352824991568923, -0.00441672932356596, 0.01054999977350235, 0.00352824991568923,
  -0.002814582549035549, 0.009624999947845936, 0.00352824991568923, -0.00441672932356596, 0.01054999977350235, 0.00352824991568923, -0.0031392588280141354, 0.008841161616146564, 0.00352824991568923,
  -0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, -0.00441672932356596, 0.01054999977350235, 0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, 0.00352824991568923,
  -0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, -0.0032500000670552254, 0.00800000037997961, 0.00352824991568923,
  -0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, -0.0049262214452028275, 0.009319976903498173, 0.00352824991568923, -0.005100000184029341, 0.00800000037997961, 0.00352824991568923,
  -0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, -0.005100000184029341, 0.00800000037997961, 0.00352824991568923, -0.0031392588280141354, 0.007158838212490082, 0.00352824991568923,
  -0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, -0.005100000184029341, 0.00800000037997961, 0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923,
  -0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, -0.002814582549035549, 0.0063749998807907104, 0.00352824991568923,
  -0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, -0.0049262214452028275, 0.0066800229251384735, 0.00352824991568923, -0.00441672932356596, 0.005450000055134296, 0.00352824991568923,
  -0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, -0.00441672932356596, 0.005450000055134296, 0.00352824991568923, -0.002298097126185894, 0.005701902788132429, 0.00352824991568923,
  -0.002298097126185894, 0.005701902788132429, 0.00352824991568923, -0.00441672932356596, 0.005450000055134296, 0.00352824991568923, -0.003606244456022978, 0.004393755458295345, 0.00352824991568923,
  -0.002298097126185894, 0.005701902788132429, 0.00352824991568923, -0.003606244456022978, 0.004393755458295345, 0.00352824991568923, -0.0016250000335276127, 0.005185417365282774, 0.00352824991568923,
  -0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, -0.003606244456022978, 0.004393755458295345, 0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, 0.00352824991568923,
  -0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, -0.0008411618764512241, 0.004860741086304188, 0.00352824991568923,
  -0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, -0.0025500000920146704, 0.003583270590752363, 0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, 0.00352824991568923,
  -0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, -3.483595049150721e-18, 0.004749999847263098, 0.00352824991568923,
  -3.483595049150721e-18, 0.004749999847263098, 0.00352824991568923, -0.0013199771055951715, 0.003073778236284852, 0.00352824991568923, 5.46656452594143e-18, 0.002899999963119626, 0.00352824991568923,
  0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, 0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, 0.0031392588280141354, 0.008841161616146564, -0.00352824991568923,
  0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, 0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, 0.0031392588280141354, 0.008841161616146564, 0.00352824991568923,
  0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, 0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, 0.002814582549035549, 0.009624999947845936, -0.00352824991568923,
  0.002814582549035549, 0.009624999947845936, -0.00352824991568923, 0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, 0.002814582549035549, 0.009624999947845936, 0.00352824991568923,
  0.002814582549035549, 0.009624999947845936, -0.00352824991568923, 0.002814582549035549, 0.009624999947845936, 0.00352824991568923, 0.002298097126185894, 0.01029809657484293, -0.00352824991568923,
  0.002298097126185894, 0.01029809657484293, -0.00352824991568923, 0.002814582549035549, 0.009624999947845936, 0.00352824991568923, 0.002298097126185894, 0.01029809657484293, 0.00352824991568923,
  0.002298097126185894, 0.01029809657484293, -0.00352824991568923, 0.002298097126185894, 0.01029809657484293, 0.00352824991568923, 0.0016250000335276127, 0.01081458292901516, -0.00352824991568923,
  0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, 0.002298097126185894, 0.01029809657484293, 0.00352824991568923, 0.0016250000335276127, 0.01081458292901516, 0.00352824991568923,
  0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, 0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, 0.0008411618764512241, 0.011139258742332458, -0.00352824991568923,
  0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, 0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, 0.0008411618764512241, 0.011139258742332458, 0.00352824991568923,
  0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, 0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, 9.20650057217565e-19, 0.011249999515712261, -0.00352824991568923,
  9.20650057217565e-19, 0.011249999515712261, -0.00352824991568923, 0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, 9.20650057217565e-19, 0.011249999515712261, 0.00352824991568923,
  9.20650057217565e-19, 0.011249999515712261, -0.00352824991568923, 9.20650057217565e-19, 0.011249999515712261, 0.00352824991568923, -0.0008411618764512241, 0.011139258742332458, -0.00352824991568923,
  -0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, 9.20650057217565e-19, 0.011249999515712261, 0.00352824991568923, -0.0008411618764512241, 0.011139258742332458, 0.00352824991568923,
  -0.0008411618764512241, 0.011139258742332458, -0.00352824991568923, -0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, -0.0016250000335276127, 0.01081458292901516, -0.00352824991568923,
  -0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, -0.0008411618764512241, 0.011139258742332458, 0.00352824991568923, -0.0016250000335276127, 0.01081458292901516, 0.00352824991568923,
  -0.0016250000335276127, 0.01081458292901516, -0.00352824991568923, -0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, -0.002298097126185894, 0.01029809657484293, -0.00352824991568923,
  -0.002298097126185894, 0.01029809657484293, -0.00352824991568923, -0.0016250000335276127, 0.01081458292901516, 0.00352824991568923, -0.002298097126185894, 0.01029809657484293, 0.00352824991568923,
  -0.002298097126185894, 0.01029809657484293, -0.00352824991568923, -0.002298097126185894, 0.01029809657484293, 0.00352824991568923, -0.002814582549035549, 0.009624999947845936, -0.00352824991568923,
  -0.002814582549035549, 0.009624999947845936, -0.00352824991568923, -0.002298097126185894, 0.01029809657484293, 0.00352824991568923, -0.002814582549035549, 0.009624999947845936, 0.00352824991568923,
  -0.002814582549035549, 0.009624999947845936, -0.00352824991568923, -0.002814582549035549, 0.009624999947845936, 0.00352824991568923, -0.0031392588280141354, 0.008841161616146564, -0.00352824991568923,
  -0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, -0.002814582549035549, 0.009624999947845936, 0.00352824991568923, -0.0031392588280141354, 0.008841161616146564, 0.00352824991568923,
  -0.0031392588280141354, 0.008841161616146564, -0.00352824991568923, -0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, -0.0032500000670552254, 0.00800000037997961, -0.00352824991568923,
  -0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, -0.0031392588280141354, 0.008841161616146564, 0.00352824991568923, -0.0032500000670552254, 0.00800000037997961, 0.00352824991568923,
  -0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, -0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, -0.0031392588280141354, 0.007158838212490082, -0.00352824991568923,
  -0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, -0.0032500000670552254, 0.00800000037997961, 0.00352824991568923, -0.0031392588280141354, 0.007158838212490082, 0.00352824991568923,
  -0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, -0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, -0.002814582549035549, 0.0063749998807907104, -0.00352824991568923,
  -0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, -0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, -0.002814582549035549, 0.0063749998807907104, 0.00352824991568923,
  -0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, -0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, -0.002298097126185894, 0.005701902788132429, -0.00352824991568923,
  -0.002298097126185894, 0.005701902788132429, -0.00352824991568923, -0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, -0.002298097126185894, 0.005701902788132429, 0.00352824991568923,
  -0.002298097126185894, 0.005701902788132429, -0.00352824991568923, -0.002298097126185894, 0.005701902788132429, 0.00352824991568923, -0.0016250000335276127, 0.005185417365282774, -0.00352824991568923,
  -0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, -0.002298097126185894, 0.005701902788132429, 0.00352824991568923, -0.0016250000335276127, 0.005185417365282774, 0.00352824991568923,
  -0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, -0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, -0.0008411618764512241, 0.004860741086304188, -0.00352824991568923,
  -0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, -0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, -0.0008411618764512241, 0.004860741086304188, 0.00352824991568923,
  -0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, -0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, -3.483595049150721e-18, 0.004749999847263098, -0.00352824991568923,
  -3.483595049150721e-18, 0.004749999847263098, -0.00352824991568923, -0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, -3.483595049150721e-18, 0.004749999847263098, 0.00352824991568923,
  -3.483595049150721e-18, 0.004749999847263098, -0.00352824991568923, -3.483595049150721e-18, 0.004749999847263098, 0.00352824991568923, 0.0008411618764512241, 0.004860741086304188, -0.00352824991568923,
  0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, -3.483595049150721e-18, 0.004749999847263098, 0.00352824991568923, 0.0008411618764512241, 0.004860741086304188, 0.00352824991568923,
  0.0008411618764512241, 0.004860741086304188, -0.00352824991568923, 0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, 0.0016250000335276127, 0.005185417365282774, -0.00352824991568923,
  0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, 0.0008411618764512241, 0.004860741086304188, 0.00352824991568923, 0.0016250000335276127, 0.005185417365282774, 0.00352824991568923,
  0.0016250000335276127, 0.005185417365282774, -0.00352824991568923, 0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, 0.002298097126185894, 0.005701902788132429, -0.00352824991568923,
  0.002298097126185894, 0.005701902788132429, -0.00352824991568923, 0.0016250000335276127, 0.005185417365282774, 0.00352824991568923, 0.002298097126185894, 0.005701902788132429, 0.00352824991568923,
  0.002298097126185894, 0.005701902788132429, -0.00352824991568923, 0.002298097126185894, 0.005701902788132429, 0.00352824991568923, 0.002814582549035549, 0.0063749998807907104, -0.00352824991568923,
  0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, 0.002298097126185894, 0.005701902788132429, 0.00352824991568923, 0.002814582549035549, 0.0063749998807907104, 0.00352824991568923,
  0.002814582549035549, 0.0063749998807907104, -0.00352824991568923, 0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, 0.0031392588280141354, 0.007158838212490082, -0.00352824991568923,
  0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, 0.002814582549035549, 0.0063749998807907104, 0.00352824991568923, 0.0031392588280141354, 0.007158838212490082, 0.00352824991568923,
  0.0031392588280141354, 0.007158838212490082, -0.00352824991568923, 0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, 0.0032500000670552254, 0.00800000037997961, -0.00352824991568923,
  0.0032500000670552254, 0.00800000037997961, -0.00352824991568923, 0.0031392588280141354, 0.007158838212490082, 0.00352824991568923, 0.0032500000670552254, 0.00800000037997961, 0.00352824991568923,
  0.13406434655189514, 0.016456063836812973, -0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, 0.0012499999720603228, 0.13403038680553436, 0.01671409420669079, -0.0012499999720603228,
  0.13403038680553436, 0.01671409420669079, -0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, 0.0012499999720603228, 0.13403038680553436, 0.01671409420669079, 0.0012499999720603228,
  0.13403038680553436, 0.01671409420669079, -0.0012499999720603228, 0.13403038680553436, 0.01671409420669079, 0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, -0.0012499999720603228,
  0.13393078744411469, 0.016954539343714714, -0.0012499999720603228, 0.13403038680553436, 0.01671409420669079, 0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, 0.0012499999720603228,
  0.13393078744411469, 0.016954539343714714, -0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, 0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, -0.0012499999720603228,
  0.1337723582983017, 0.017161013558506966, -0.0012499999720603228, 0.13393078744411469, 0.016954539343714714, 0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, 0.0012499999720603228,
  0.1337723582983017, 0.017161013558506966, -0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, 0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, -0.0012499999720603228,
  0.13356587290763855, 0.0173194482922554, -0.0012499999720603228, 0.1337723582983017, 0.017161013558506966, 0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, 0.0012499999720603228,
  0.13356587290763855, 0.0173194482922554, -0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, 0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, -0.0012499999720603228,
  0.13332542777061462, 0.01741904392838478, -0.0012499999720603228, 0.13356587290763855, 0.0173194482922554, 0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, 0.0012499999720603228,
  0.13332542777061462, 0.01741904392838478, -0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, 0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, -0.0012499999720603228,
  0.13306739926338196, 0.017453014850616455, -0.0012499999720603228, 0.13332542777061462, 0.01741904392838478, 0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, 0.0012499999720603228,
  0.13306739926338196, 0.017453014850616455, -0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, 0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, -0.0012499999720603228,
  0.1328093707561493, 0.01741904392838478, -0.0012499999720603228, 0.13306739926338196, 0.017453014850616455, 0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, 0.0012499999720603228,
  0.1328093707561493, 0.01741904392838478, -0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, 0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, -0.0012499999720603228,
  0.13256892561912537, 0.0173194482922554, -0.0012499999720603228, 0.1328093707561493, 0.01741904392838478, 0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, 0.0012499999720603228,
  0.13256892561912537, 0.0173194482922554, -0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, 0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, -0.0012499999720603228,
  0.1323624551296234, 0.017161013558506966, -0.0012499999720603228, 0.13256892561912537, 0.0173194482922554, 0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, 0.0012499999720603228,
  0.1323624551296234, 0.017161013558506966, -0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, 0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, -0.0012499999720603228,
  0.13220401108264923, 0.016954539343714714, -0.0012499999720603228, 0.1323624551296234, 0.017161013558506966, 0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, 0.0012499999720603228,
  0.13220401108264923, 0.016954539343714714, -0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, 0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, -0.0012499999720603228,
  0.13210442662239075, 0.01671409420669079, -0.0012499999720603228, 0.13220401108264923, 0.016954539343714714, 0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, 0.0012499999720603228,
  0.13210442662239075, 0.01671409420669079, -0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, 0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, -0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.13210442662239075, 0.01671409420669079, 0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, 0.0012499999720603228,
  0.13207045197486877, 0.016456063836812973, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, 0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, -0.0012499999720603228,
  0.13210442662239075, 0.016198035329580307, -0.0012499999720603228, 0.13207045197486877, 0.016456063836812973, 0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, 0.0012499999720603228,
  0.13210442662239075, 0.016198035329580307, -0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, 0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, -0.0012499999720603228,
  0.13220401108264923, 0.015957588329911232, -0.0012499999720603228, 0.13210442662239075, 0.016198035329580307, 0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, 0.0012499999720603228,
  0.13220401108264923, 0.015957588329911232, -0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, -0.0012499999720603228,
  0.1323624551296234, 0.01575111411511898, -0.0012499999720603228, 0.13220401108264923, 0.015957588329911232, 0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228,
  0.1323624551296234, 0.01575111411511898, -0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, -0.0012499999720603228,
  0.13256892561912537, 0.015592680312693119, -0.0012499999720603228, 0.1323624551296234, 0.01575111411511898, 0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, 0.0012499999720603228,
  0.13256892561912537, 0.015592680312693119, -0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, 0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, -0.0012499999720603228,
  0.1328093707561493, 0.01549308467656374, -0.0012499999720603228, 0.13256892561912537, 0.015592680312693119, 0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, 0.0012499999720603228,
  0.1328093707561493, 0.01549308467656374, -0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, 0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, -0.0012499999720603228,
  0.13306739926338196, 0.015459113754332066, -0.0012499999720603228, 0.1328093707561493, 0.01549308467656374, 0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, 0.0012499999720603228,
  0.13306739926338196, 0.015459113754332066, -0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, 0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, -0.0012499999720603228,
  0.13332542777061462, 0.01549308467656374, -0.0012499999720603228, 0.13306739926338196, 0.015459113754332066, 0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, 0.0012499999720603228,
  0.13332542777061462, 0.01549308467656374, -0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, 0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, -0.0012499999720603228,
  0.13356587290763855, 0.015592680312693119, -0.0012499999720603228, 0.13332542777061462, 0.01549308467656374, 0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, 0.0012499999720603228,
  0.13356587290763855, 0.015592680312693119, -0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, 0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, -0.0012499999720603228,
  0.1337723582983017, 0.01575111411511898, -0.0012499999720603228, 0.13356587290763855, 0.015592680312693119, 0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, 0.0012499999720603228,
  0.1337723582983017, 0.01575111411511898, -0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, 0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, -0.0012499999720603228,
  0.13393078744411469, 0.015957588329911232, -0.0012499999720603228, 0.1337723582983017, 0.01575111411511898, 0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, 0.0012499999720603228,
  0.13393078744411469, 0.015957588329911232, -0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, 0.0012499999720603228, 0.13403038680553436, 0.016198035329580307, -0.0012499999720603228,
  0.13403038680553436, 0.016198035329580307, -0.0012499999720603228, 0.13393078744411469, 0.015957588329911232, 0.0012499999720603228, 0.13403038680553436, 0.016198035329580307, 0.0012499999720603228,
  0.13403038680553436, 0.016198035329580307, -0.0012499999720603228, 0.13403038680553436, 0.016198035329580307, 0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, -0.0012499999720603228,
  0.13406434655189514, 0.016456063836812973, -0.0012499999720603228, 0.13403038680553436, 0.016198035329580307, 0.0012499999720603228, 0.13406434655189514, 0.016456063836812973, 0.0012499999720603228,

])

// Full actual raw bar_triangles surface triangles; approved GLB hash above.
const BAR_TRIANGLES = new Float64Array([
  -2.3453770232691167e-28, 0.8028134107589722, 0.002676524920389056, -2.345667838690719e-28, 0.8029129505157471, 0.0029169702902436256, -2.3614058159725225e-28, 0.8083000183105469, 0.0,
  -2.339942048966056e-28, 0.8009530305862427, 0.00317499996162951, -2.340041234358192e-28, 0.8009870052337646, 0.0029169702902436256, 0.0, 0.0, 0.0,
  0.0, 0.0, 0.0, -2.340041234358192e-28, 0.8009870052337646, 0.0029169702902436256, -2.3403322905210374e-28, 0.8010866045951843, 0.002676524920389056,
  0.0, 0.0, 0.0, -2.3403322905210374e-28, 0.8010866045951843, 0.002676524920389056, -2.3407952359314195e-28, 0.8012450337409973, 0.0024700500071048737,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, -2.345667838690719e-28, 0.8029129505157471, 0.0029169702902436256, -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902,
  -2.3407952359314195e-28, 0.8012450337409973, 0.00387995014898479, -2.3403322905210374e-28, 0.8010866045951843, 0.0036734750028699636, 0.0, 0.0, 0.0,
  0.0, 0.0, 0.0, -2.3403322905210374e-28, 0.8010866045951843, 0.0036734750028699636, -2.340041234358192e-28, 0.8009870052337646, 0.003433029633015394,
  0.0, 0.0, 0.0, -2.340041234358192e-28, 0.8009870052337646, 0.003433029633015394, -2.339942048966056e-28, 0.8009530305862427, 0.00317499996162951,
  -2.345667838690719e-28, 0.8029129505157471, 0.0029169702902436256, -2.345767264824098e-28, 0.802946925163269, 0.00317499996162951, -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, -2.345767264824098e-28, 0.802946925163269, 0.00317499996162951, -2.345667838690719e-28, 0.8029129505157471, 0.003433029633015394,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, -2.345667838690719e-28, 0.8029129505157471, 0.003433029633015394, -2.3453770232691167e-28, 0.8028134107589722, 0.0036734750028699636,
  -2.3407952359314195e-28, 0.8012450337409973, 0.0024700500071048737, -2.3413982927452557e-28, 0.8014515042304993, 0.0023116159718483686, 0.0, 0.0, 0.0,
  0.0, 0.0, 0.0, -2.3413982927452557e-28, 0.8014515042304993, 0.0023116159718483686, -2.342100775692471e-28, 0.8016919493675232, 0.0022120203357189894,
  0.0, 0.0, 0.0, -2.342100775692471e-28, 0.8016919493675232, 0.0022120203357189894, -2.3614058159725225e-28, 0.8083000183105469, 0.0,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, -2.342100775692471e-28, 0.8016919493675232, 0.0022120203357189894, 5.204170427930421e-18, 0.8019499778747559, 0.002178050111979246,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, 5.204170427930421e-18, 0.8019499778747559, 0.002178050111979246, -2.343608538097683e-28, 0.8022080063819885, 0.0022120203357189894,
  -2.343608538097683e-28, 0.8022080063819885, 0.0022120203357189894, -2.3443107803036553e-28, 0.8024484515190125, 0.0023116159718483686, -2.3614058159725225e-28, 0.8083000183105469, 0.0,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, -2.3443107803036553e-28, 0.8024484515190125, 0.0023116159718483686, -2.3449140778587346e-28, 0.8026549220085144, 0.0024700500071048737,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, -2.3449140778587346e-28, 0.8026549220085144, 0.0024700500071048737, -2.3453770232691167e-28, 0.8028134107589722, 0.002676524920389056,
  -2.3453770232691167e-28, 0.8028134107589722, 0.0036734750028699636, -2.3449140778587346e-28, 0.8026549220085144, 0.00387995014898479, -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, -2.3449140778587346e-28, 0.8026549220085144, 0.00387995014898479, -2.3443107803036553e-28, 0.8024484515190125, 0.004038384184241295,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, -2.3443107803036553e-28, 0.8024484515190125, 0.004038384184241295, -2.343608538097683e-28, 0.8022080063819885, 0.004137979820370674,
  0.0, 0.0, 0.0, 0.0, 0.0, 0.00634999992325902, -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902,
  -2.343608538097683e-28, 0.8022080063819885, 0.004137979820370674, -2.3428545365244555e-28, 0.8019499778747559, 0.004171949811279774, -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, -2.3428545365244555e-28, 0.8019499778747559, 0.004171949811279774, -2.342100775692471e-28, 0.8016919493675232, 0.004137979820370674,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, -2.342100775692471e-28, 0.8016919493675232, 0.004137979820370674, 0.0, 0.0, 0.0,
  0.0, 0.0, 0.0, -2.342100775692471e-28, 0.8016919493675232, 0.004137979820370674, -2.3413982927452557e-28, 0.8014515042304993, 0.004038384184241295,
  0.0, 0.0, 0.0, -2.3413982927452557e-28, 0.8014515042304993, 0.004038384184241295, -2.3407952359314195e-28, 0.8012450337409973, 0.00387995014898479,
  0.0016200001118704677, 0.0, 0.00634999992325902, 0.0, 0.0, 0.00634999992325902, 0.0016200001118704677, 0.0, 0.0,
  0.0016200001118704677, 0.0, 0.0, 0.0, 0.0, 0.00634999992325902, 0.0, 0.0, 0.0,
  0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902, 0.0016200001118704677, 0.0, 0.00634999992325902, 0.0016200001118704677, 0.0023812500294297934, 0.0,
  0.0016200001118704677, 0.0023812500294297934, 0.0, 0.0016200001118704677, 0.0, 0.00634999992325902, 0.0016200001118704677, 0.0, 0.0,
  0.004730000160634518, 0.0023812500294297934, 0.00634999992325902, 0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902, 0.004730000160634518, 0.0023812500294297934, 0.0,
  0.004730000160634518, 0.0023812500294297934, 0.0, 0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902, 0.0016200001118704677, 0.0023812500294297934, 0.0,
  0.004730000160634518, 1.925929944387236e-34, 0.00634999992325902, 0.004730000160634518, 0.0023812500294297934, 0.00634999992325902, 0.004730000160634518, 1.925929944387236e-34, 0.0,
  0.004730000160634518, 1.925929944387236e-34, 0.0, 0.004730000160634518, 0.0023812500294297934, 0.00634999992325902, 0.004730000160634518, 0.0023812500294297934, 0.0,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.004730000160634518, 1.925929944387236e-34, 0.00634999992325902, 0.00634999992325902, 0.0, 0.0,
  0.00634999992325902, 0.0, 0.0, 0.004730000160634518, 1.925929944387236e-34, 0.00634999992325902, 0.004730000160634518, 1.925929944387236e-34, 0.0,
  0.00634999992325902, 0.8012450337409973, 0.0024700500071048737, 0.00634999992325902, 0.8010866045951843, 0.002676524920389056, 0.00634999992325902, 0.0, 0.00634999992325902,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8010866045951843, 0.002676524920389056, 0.00634999992325902, 0.8009870052337646, 0.0029169702902436256,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8009870052337646, 0.0029169702902436256, 0.00634999992325902, 0.8009530305862427, 0.00317499996162951,
  0.00634999992325902, 0.8009530305862427, 0.00317499996162951, 0.00634999992325902, 0.8009870052337646, 0.003433029633015394, 0.00634999992325902, 0.0, 0.00634999992325902,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8009870052337646, 0.003433029633015394, 0.00634999992325902, 0.8010866045951843, 0.0036734750028699636,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8010866045951843, 0.0036734750028699636, 0.00634999992325902, 0.8012450337409973, 0.00387995014898479,
  0.00634999992325902, 0.8028134107589722, 0.0036734750028699636, 0.00634999992325902, 0.8029129505157471, 0.003433029633015394, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8029129505157471, 0.003433029633015394, 0.00634999992325902, 0.802946925163269, 0.00317499996162951,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.802946925163269, 0.00317499996162951, 0.00634999992325902, 0.8083000183105469, 0.0,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.00634999992325902, 0.802946925163269, 0.00317499996162951, 0.00634999992325902, 0.8029129505157471, 0.0029169702902436256,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.00634999992325902, 0.8029129505157471, 0.0029169702902436256, 0.00634999992325902, 0.8028134107589722, 0.002676524920389056,
  0.00634999992325902, 0.8012450337409973, 0.00387995014898479, 0.00634999992325902, 0.8014515042304993, 0.004038384184241295, 0.00634999992325902, 0.0, 0.00634999992325902,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8014515042304993, 0.004038384184241295, 0.00634999992325902, 0.8016919493675232, 0.004137979820370674,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8016919493675232, 0.004137979820370674, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8016919493675232, 0.004137979820370674, 0.00634999992325902, 0.8019499778747559, 0.004171949811279774,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8019499778747559, 0.004171949811279774, 0.00634999992325902, 0.8022080063819885, 0.004137979820370674,
  0.00634999992325902, 0.8022080063819885, 0.004137979820370674, 0.00634999992325902, 0.8024484515190125, 0.004038384184241295, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8024484515190125, 0.004038384184241295, 0.00634999992325902, 0.8026549220085144, 0.00387995014898479,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8026549220085144, 0.00387995014898479, 0.00634999992325902, 0.8028134107589722, 0.0036734750028699636,
  0.00634999992325902, 0.8028134107589722, 0.002676524920389056, 0.00634999992325902, 0.8026549220085144, 0.0024700500071048737, 0.00634999992325902, 0.8083000183105469, 0.0,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.00634999992325902, 0.8026549220085144, 0.0024700500071048737, 0.00634999992325902, 0.8024484515190125, 0.0023116159718483686,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.00634999992325902, 0.8024484515190125, 0.0023116159718483686, 0.00634999992325902, 0.8022080063819885, 0.0022120203357189894,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.0, 0.0, 0.00634999992325902, 0.8083000183105469, 0.0,
  0.00634999992325902, 0.8022080063819885, 0.0022120203357189894, 0.00634999992325902, 0.8019499778747559, 0.002178050111979246, 0.00634999992325902, 0.8083000183105469, 0.0,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.00634999992325902, 0.8019499778747559, 0.002178050111979246, 0.00634999992325902, 0.8016919493675232, 0.0022120203357189894,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.00634999992325902, 0.8016919493675232, 0.0022120203357189894, 0.00634999992325902, 0.0, 0.00634999992325902,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8016919493675232, 0.0022120203357189894, 0.00634999992325902, 0.8014515042304993, 0.0023116159718483686,
  0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8014515042304993, 0.0023116159718483686, 0.00634999992325902, 0.8012450337409973, 0.0024700500071048737,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8083000183105469, 0.0,
  0.004774999804794788, 0.8083000183105469, 0.0, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.00634999992325902, 0.8083000183105469, 0.0,
  0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.8009530305862427, 0.00317499996162951, 0.004774999804794788, 0.7955999970436096, 0.0,
  0.004774999804794788, 0.7955999970436096, 0.0, 0.004774999804794788, 0.8009530305862427, 0.00317499996162951, 0.004774999804794788, 0.8009870052337646, 0.0029169702902436256,
  0.004774999804794788, 0.8024484515190125, 0.0023116159718483686, 0.004774999804794788, 0.8026549220085144, 0.0024700500071048737, 0.004774999804794788, 0.8083000183105469, 0.0,
  0.004774999804794788, 0.8014515042304993, 0.004038384184241295, 0.004774999804794788, 0.8012450337409973, 0.00387995014898479, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902,
  0.004774999804794788, 0.8026549220085144, 0.0024700500071048737, 0.004774999804794788, 0.8028134107589722, 0.002676524920389056, 0.004774999804794788, 0.8083000183105469, 0.0,
  0.004774999804794788, 0.8083000183105469, 0.0, 0.004774999804794788, 0.8028134107589722, 0.002676524920389056, 0.004774999804794788, 0.8029129505157471, 0.0029169702902436256,
  0.004774999804794788, 0.8083000183105469, 0.0, 0.004774999804794788, 0.8029129505157471, 0.0029169702902436256, 0.004774999804794788, 0.8083000183105469, 0.00634999992325902,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8029129505157471, 0.0029169702902436256, 0.004774999804794788, 0.802946925163269, 0.00317499996162951,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.802946925163269, 0.00317499996162951, 0.004774999804794788, 0.8029129505157471, 0.003433029633015394,
  0.004774999804794788, 0.8012450337409973, 0.00387995014898479, 0.004774999804794788, 0.8010866045951843, 0.0036734750028699636, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902,
  0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.8010866045951843, 0.0036734750028699636, 0.004774999804794788, 0.8009870052337646, 0.003433029633015394,
  0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.8009870052337646, 0.003433029633015394, 0.004774999804794788, 0.8009530305862427, 0.00317499996162951,
  0.004774999804794788, 0.8009870052337646, 0.0029169702902436256, 0.004774999804794788, 0.8010866045951843, 0.002676524920389056, 0.004774999804794788, 0.7955999970436096, 0.0,
  0.004774999804794788, 0.7955999970436096, 0.0, 0.004774999804794788, 0.8010866045951843, 0.002676524920389056, 0.004774999804794788, 0.8012450337409973, 0.0024700500071048737,
  0.004774999804794788, 0.7955999970436096, 0.0, 0.004774999804794788, 0.8012450337409973, 0.0024700500071048737, 0.004774999804794788, 0.8014515042304993, 0.0023116159718483686,
  0.004774999804794788, 0.8014515042304993, 0.0023116159718483686, 0.004774999804794788, 0.8016919493675232, 0.0022120203357189894, 0.004774999804794788, 0.7955999970436096, 0.0,
  0.004774999804794788, 0.7955999970436096, 0.0, 0.004774999804794788, 0.8016919493675232, 0.0022120203357189894, 0.004774999804794788, 0.8019499778747559, 0.002178050111979246,
  0.004774999804794788, 0.7955999970436096, 0.0, 0.004774999804794788, 0.8019499778747559, 0.002178050111979246, 0.004774999804794788, 0.8083000183105469, 0.0,
  0.004774999804794788, 0.8083000183105469, 0.0, 0.004774999804794788, 0.8019499778747559, 0.002178050111979246, 0.004774999804794788, 0.8022080063819885, 0.0022120203357189894,
  0.004774999804794788, 0.8083000183105469, 0.0, 0.004774999804794788, 0.8022080063819885, 0.0022120203357189894, 0.004774999804794788, 0.8024484515190125, 0.0023116159718483686,
  0.004774999804794788, 0.8029129505157471, 0.003433029633015394, 0.004774999804794788, 0.8028134107589722, 0.0036734750028699636, 0.004774999804794788, 0.8083000183105469, 0.00634999992325902,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8028134107589722, 0.0036734750028699636, 0.004774999804794788, 0.8026549220085144, 0.00387995014898479,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8026549220085144, 0.00387995014898479, 0.004774999804794788, 0.8024484515190125, 0.004038384184241295,
  0.004774999804794788, 0.8024484515190125, 0.004038384184241295, 0.004774999804794788, 0.8022080063819885, 0.004137979820370674, 0.004774999804794788, 0.8083000183105469, 0.00634999992325902,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8022080063819885, 0.004137979820370674, 0.004774999804794788, 0.8019499778747559, 0.004171949811279774,
  0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8019499778747559, 0.004171949811279774, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902,
  0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.8019499778747559, 0.004171949811279774, 0.004774999804794788, 0.8016919493675232, 0.004137979820370674,
  0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.8016919493675232, 0.004137979820370674, 0.004774999804794788, 0.8014515042304993, 0.004038384184241295,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.7955999970436096, 0.0,
  0.0015750000020489097, 0.7955999970436096, 0.0, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.004774999804794788, 0.7955999970436096, 0.0,
  0.0015750000020489097, 0.8014515042304993, 0.0023116159718483686, 0.0015750000020489097, 0.8012450337409973, 0.0024700500071048737, 0.0015750000020489097, 0.7955999970436096, 0.0,
  0.0015750000020489097, 0.8012450337409973, 0.0024700500071048737, 0.0015750000020489097, 0.8010866045951843, 0.002676524920389056, 0.0015750000020489097, 0.7955999970436096, 0.0,
  0.0015750000020489097, 0.7955999970436096, 0.0, 0.0015750000020489097, 0.8010866045951843, 0.002676524920389056, 0.0015750000020489097, 0.8009870052337646, 0.0029169702902436256,
  0.0015750000020489097, 0.7955999970436096, 0.0, 0.0015750000020489097, 0.8009870052337646, 0.0029169702902436256, 0.0015750000020489097, 0.7955999970436096, 0.00634999992325902,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8009870052337646, 0.0029169702902436256, 0.0015750000020489097, 0.8009530305862427, 0.00317499996162951,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8009530305862427, 0.00317499996162951, 0.0015750000020489097, 0.8009870052337646, 0.003433029633015394,
  0.0015750000020489097, 0.8024484515190125, 0.004038384184241295, 0.0015750000020489097, 0.8026549220085144, 0.00387995014898479, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902,
  0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8026549220085144, 0.00387995014898479, 0.0015750000020489097, 0.8028134107589722, 0.0036734750028699636,
  0.0015750000020489097, 0.8029129505157471, 0.0029169702902436256, 0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.802946925163269, 0.00317499996162951,
  0.0015750000020489097, 0.802946925163269, 0.00317499996162951, 0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902,
  0.0015750000020489097, 0.802946925163269, 0.00317499996162951, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8029129505157471, 0.003433029633015394,
  0.0015750000020489097, 0.8029129505157471, 0.003433029633015394, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8028134107589722, 0.0036734750028699636,
  0.0015750000020489097, 0.8009870052337646, 0.003433029633015394, 0.0015750000020489097, 0.8010866045951843, 0.0036734750028699636, 0.0015750000020489097, 0.7955999970436096, 0.00634999992325902,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8010866045951843, 0.0036734750028699636, 0.0015750000020489097, 0.8012450337409973, 0.00387995014898479,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8012450337409973, 0.00387995014898479, 0.0015750000020489097, 0.8014515042304993, 0.004038384184241295,
  0.0015750000020489097, 0.8029129505157471, 0.0029169702902436256, 0.0015750000020489097, 0.8028134107589722, 0.002676524920389056, 0.0015750000020489097, 0.8083000183105469, 0.0,
  0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8028134107589722, 0.002676524920389056, 0.0015750000020489097, 0.8026549220085144, 0.0024700500071048737,
  0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8026549220085144, 0.0024700500071048737, 0.0015750000020489097, 0.8024484515190125, 0.0023116159718483686,
  0.0015750000020489097, 0.8024484515190125, 0.0023116159718483686, 0.0015750000020489097, 0.8022080063819885, 0.0022120203357189894, 0.0015750000020489097, 0.8083000183105469, 0.0,
  0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8022080063819885, 0.0022120203357189894, 0.0015750000020489097, 0.8019499778747559, 0.002178050111979246,
  0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8019499778747559, 0.002178050111979246, 0.0015750000020489097, 0.7955999970436096, 0.0,
  0.0015750000020489097, 0.7955999970436096, 0.0, 0.0015750000020489097, 0.8019499778747559, 0.002178050111979246, 0.0015750000020489097, 0.8016919493675232, 0.0022120203357189894,
  0.0015750000020489097, 0.7955999970436096, 0.0, 0.0015750000020489097, 0.8016919493675232, 0.0022120203357189894, 0.0015750000020489097, 0.8014515042304993, 0.0023116159718483686,
  0.0015750000020489097, 0.8014515042304993, 0.004038384184241295, 0.0015750000020489097, 0.8016919493675232, 0.004137979820370674, 0.0015750000020489097, 0.7955999970436096, 0.00634999992325902,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8016919493675232, 0.004137979820370674, 0.0015750000020489097, 0.8019499778747559, 0.004171949811279774,
  0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8019499778747559, 0.004171949811279774, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902,
  0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8019499778747559, 0.004171949811279774, 0.0015750000020489097, 0.8022080063819885, 0.004137979820370674,
  0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8022080063819885, 0.004137979820370674, 0.0015750000020489097, 0.8024484515190125, 0.004038384184241295,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, -2.3614058159725225e-28, 0.8083000183105469, 0.0,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.8083000183105469, 0.0,
  0.0, 0.0, 0.00634999992325902, 0.0016200001118704677, 0.0, 0.00634999992325902, 0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902,
  0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902,
  0.004730000160634518, 1.925929944387236e-34, 0.00634999992325902, 0.00634999992325902, 0.0, 0.00634999992325902, 0.004730000160634518, 0.0023812500294297934, 0.00634999992325902,
  0.004730000160634518, 0.0023812500294297934, 0.00634999992325902, 0.00634999992325902, 0.0, 0.00634999992325902, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902,
  0.004730000160634518, 0.0023812500294297934, 0.00634999992325902, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902,
  0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902, 0.00634999992325902, 0.8083000183105469, 0.00634999992325902, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902,
  0.0016200001118704677, 0.0023812500294297934, 0.00634999992325902, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.0, 0.0, 0.00634999992325902,
  0.0, 0.0, 0.00634999992325902, 0.004774999804794788, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.7955999970436096, 0.00634999992325902,
  0.0, 0.0, 0.00634999992325902, 0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902,
  -2.3614058159725225e-28, 0.8083000183105469, 0.00634999992325902, 0.0015750000020489097, 0.7955999970436096, 0.00634999992325902, 0.0015750000020489097, 0.8083000183105469, 0.00634999992325902,
  -2.3614058159725225e-28, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.7955999970436096, 0.0,
  0.00634999992325902, 0.0, 0.0, 0.004730000160634518, 1.925929944387236e-34, 0.0, 0.004730000160634518, 0.0023812500294297934, 0.0,
  0.0016200001118704677, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0016200001118704677, 0.0023812500294297934, 0.0,
  0.0016200001118704677, 0.0023812500294297934, 0.0, 0.0, 0.0, 0.0, -2.3614058159725225e-28, 0.8083000183105469, 0.0,
  0.0016200001118704677, 0.0023812500294297934, 0.0, -2.3614058159725225e-28, 0.8083000183105469, 0.0, 0.004730000160634518, 0.0023812500294297934, 0.0,
  0.004730000160634518, 0.0023812500294297934, 0.0, -2.3614058159725225e-28, 0.8083000183105469, 0.0, 0.0015750000020489097, 0.7955999970436096, 0.0,
  0.004730000160634518, 0.0023812500294297934, 0.0, 0.0015750000020489097, 0.7955999970436096, 0.0, 0.00634999992325902, 0.0, 0.0,
  0.00634999992325902, 0.0, 0.0, 0.0015750000020489097, 0.7955999970436096, 0.0, 0.004774999804794788, 0.7955999970436096, 0.0,
  0.00634999992325902, 0.0, 0.0, 0.004774999804794788, 0.7955999970436096, 0.0, 0.00634999992325902, 0.8083000183105469, 0.0,
  0.00634999992325902, 0.8083000183105469, 0.0, 0.004774999804794788, 0.7955999970436096, 0.0, 0.004774999804794788, 0.8083000183105469, 0.0,
  0.004774999804794788, 0.8019499778747559, 0.002178050111979246, 0.00634999992325902, 0.8019499778747559, 0.002178050111979246, 0.004774999804794788, 0.8022080063819885, 0.0022120203357189894,
  0.004774999804794788, 0.8022080063819885, 0.0022120203357189894, 0.00634999992325902, 0.8019499778747559, 0.002178050111979246, 0.00634999992325902, 0.8022080063819885, 0.0022120203357189894,
  0.004774999804794788, 0.8022080063819885, 0.0022120203357189894, 0.00634999992325902, 0.8022080063819885, 0.0022120203357189894, 0.004774999804794788, 0.8024484515190125, 0.0023116159718483686,
  0.004774999804794788, 0.8024484515190125, 0.0023116159718483686, 0.00634999992325902, 0.8022080063819885, 0.0022120203357189894, 0.00634999992325902, 0.8024484515190125, 0.0023116159718483686,
  0.004774999804794788, 0.8024484515190125, 0.0023116159718483686, 0.00634999992325902, 0.8024484515190125, 0.0023116159718483686, 0.004774999804794788, 0.8026549220085144, 0.0024700500071048737,
  0.004774999804794788, 0.8026549220085144, 0.0024700500071048737, 0.00634999992325902, 0.8024484515190125, 0.0023116159718483686, 0.00634999992325902, 0.8026549220085144, 0.0024700500071048737,
  0.004774999804794788, 0.8026549220085144, 0.0024700500071048737, 0.00634999992325902, 0.8026549220085144, 0.0024700500071048737, 0.004774999804794788, 0.8028134107589722, 0.002676524920389056,
  0.004774999804794788, 0.8028134107589722, 0.002676524920389056, 0.00634999992325902, 0.8026549220085144, 0.0024700500071048737, 0.00634999992325902, 0.8028134107589722, 0.002676524920389056,
  0.004774999804794788, 0.8028134107589722, 0.002676524920389056, 0.00634999992325902, 0.8028134107589722, 0.002676524920389056, 0.004774999804794788, 0.8029129505157471, 0.0029169702902436256,
  0.004774999804794788, 0.8029129505157471, 0.0029169702902436256, 0.00634999992325902, 0.8028134107589722, 0.002676524920389056, 0.00634999992325902, 0.8029129505157471, 0.0029169702902436256,
  0.004774999804794788, 0.8029129505157471, 0.0029169702902436256, 0.00634999992325902, 0.8029129505157471, 0.0029169702902436256, 0.004774999804794788, 0.802946925163269, 0.00317499996162951,
  0.004774999804794788, 0.802946925163269, 0.00317499996162951, 0.00634999992325902, 0.8029129505157471, 0.0029169702902436256, 0.00634999992325902, 0.802946925163269, 0.00317499996162951,
  0.004774999804794788, 0.802946925163269, 0.00317499996162951, 0.00634999992325902, 0.802946925163269, 0.00317499996162951, 0.004774999804794788, 0.8029129505157471, 0.003433029633015394,
  0.004774999804794788, 0.8029129505157471, 0.003433029633015394, 0.00634999992325902, 0.802946925163269, 0.00317499996162951, 0.00634999992325902, 0.8029129505157471, 0.003433029633015394,
  0.004774999804794788, 0.8029129505157471, 0.003433029633015394, 0.00634999992325902, 0.8029129505157471, 0.003433029633015394, 0.004774999804794788, 0.8028134107589722, 0.0036734750028699636,
  0.004774999804794788, 0.8028134107589722, 0.0036734750028699636, 0.00634999992325902, 0.8029129505157471, 0.003433029633015394, 0.00634999992325902, 0.8028134107589722, 0.0036734750028699636,
  0.004774999804794788, 0.8028134107589722, 0.0036734750028699636, 0.00634999992325902, 0.8028134107589722, 0.0036734750028699636, 0.004774999804794788, 0.8026549220085144, 0.00387995014898479,
  0.004774999804794788, 0.8026549220085144, 0.00387995014898479, 0.00634999992325902, 0.8028134107589722, 0.0036734750028699636, 0.00634999992325902, 0.8026549220085144, 0.00387995014898479,
  0.004774999804794788, 0.8026549220085144, 0.00387995014898479, 0.00634999992325902, 0.8026549220085144, 0.00387995014898479, 0.004774999804794788, 0.8024484515190125, 0.004038384184241295,
  0.004774999804794788, 0.8024484515190125, 0.004038384184241295, 0.00634999992325902, 0.8026549220085144, 0.00387995014898479, 0.00634999992325902, 0.8024484515190125, 0.004038384184241295,
  0.004774999804794788, 0.8024484515190125, 0.004038384184241295, 0.00634999992325902, 0.8024484515190125, 0.004038384184241295, 0.004774999804794788, 0.8022080063819885, 0.004137979820370674,
  0.004774999804794788, 0.8022080063819885, 0.004137979820370674, 0.00634999992325902, 0.8024484515190125, 0.004038384184241295, 0.00634999992325902, 0.8022080063819885, 0.004137979820370674,
  0.004774999804794788, 0.8022080063819885, 0.004137979820370674, 0.00634999992325902, 0.8022080063819885, 0.004137979820370674, 0.004774999804794788, 0.8019499778747559, 0.004171949811279774,
  0.004774999804794788, 0.8019499778747559, 0.004171949811279774, 0.00634999992325902, 0.8022080063819885, 0.004137979820370674, 0.00634999992325902, 0.8019499778747559, 0.004171949811279774,
  0.004774999804794788, 0.8019499778747559, 0.004171949811279774, 0.00634999992325902, 0.8019499778747559, 0.004171949811279774, 0.004774999804794788, 0.8016919493675232, 0.004137979820370674,
  0.004774999804794788, 0.8016919493675232, 0.004137979820370674, 0.00634999992325902, 0.8019499778747559, 0.004171949811279774, 0.00634999992325902, 0.8016919493675232, 0.004137979820370674,
  0.004774999804794788, 0.8016919493675232, 0.004137979820370674, 0.00634999992325902, 0.8016919493675232, 0.004137979820370674, 0.004774999804794788, 0.8014515042304993, 0.004038384184241295,
  0.004774999804794788, 0.8014515042304993, 0.004038384184241295, 0.00634999992325902, 0.8016919493675232, 0.004137979820370674, 0.00634999992325902, 0.8014515042304993, 0.004038384184241295,
  0.004774999804794788, 0.8014515042304993, 0.004038384184241295, 0.00634999992325902, 0.8014515042304993, 0.004038384184241295, 0.004774999804794788, 0.8012450337409973, 0.00387995014898479,
  0.004774999804794788, 0.8012450337409973, 0.00387995014898479, 0.00634999992325902, 0.8014515042304993, 0.004038384184241295, 0.00634999992325902, 0.8012450337409973, 0.00387995014898479,
  0.004774999804794788, 0.8012450337409973, 0.00387995014898479, 0.00634999992325902, 0.8012450337409973, 0.00387995014898479, 0.004774999804794788, 0.8010866045951843, 0.0036734750028699636,
  0.004774999804794788, 0.8010866045951843, 0.0036734750028699636, 0.00634999992325902, 0.8012450337409973, 0.00387995014898479, 0.00634999992325902, 0.8010866045951843, 0.0036734750028699636,
  0.004774999804794788, 0.8010866045951843, 0.0036734750028699636, 0.00634999992325902, 0.8010866045951843, 0.0036734750028699636, 0.004774999804794788, 0.8009870052337646, 0.003433029633015394,
  0.004774999804794788, 0.8009870052337646, 0.003433029633015394, 0.00634999992325902, 0.8010866045951843, 0.0036734750028699636, 0.00634999992325902, 0.8009870052337646, 0.003433029633015394,
  0.004774999804794788, 0.8009870052337646, 0.003433029633015394, 0.00634999992325902, 0.8009870052337646, 0.003433029633015394, 0.004774999804794788, 0.8009530305862427, 0.00317499996162951,
  0.004774999804794788, 0.8009530305862427, 0.00317499996162951, 0.00634999992325902, 0.8009870052337646, 0.003433029633015394, 0.00634999992325902, 0.8009530305862427, 0.00317499996162951,
  0.004774999804794788, 0.8009530305862427, 0.00317499996162951, 0.00634999992325902, 0.8009530305862427, 0.00317499996162951, 0.004774999804794788, 0.8009870052337646, 0.0029169702902436256,
  0.004774999804794788, 0.8009870052337646, 0.0029169702902436256, 0.00634999992325902, 0.8009530305862427, 0.00317499996162951, 0.00634999992325902, 0.8009870052337646, 0.0029169702902436256,
  0.004774999804794788, 0.8009870052337646, 0.0029169702902436256, 0.00634999992325902, 0.8009870052337646, 0.0029169702902436256, 0.004774999804794788, 0.8010866045951843, 0.002676524920389056,
  0.004774999804794788, 0.8010866045951843, 0.002676524920389056, 0.00634999992325902, 0.8009870052337646, 0.0029169702902436256, 0.00634999992325902, 0.8010866045951843, 0.002676524920389056,
  0.004774999804794788, 0.8010866045951843, 0.002676524920389056, 0.00634999992325902, 0.8010866045951843, 0.002676524920389056, 0.004774999804794788, 0.8012450337409973, 0.0024700500071048737,
  0.004774999804794788, 0.8012450337409973, 0.0024700500071048737, 0.00634999992325902, 0.8010866045951843, 0.002676524920389056, 0.00634999992325902, 0.8012450337409973, 0.0024700500071048737,
  0.004774999804794788, 0.8012450337409973, 0.0024700500071048737, 0.00634999992325902, 0.8012450337409973, 0.0024700500071048737, 0.004774999804794788, 0.8014515042304993, 0.0023116159718483686,
  0.004774999804794788, 0.8014515042304993, 0.0023116159718483686, 0.00634999992325902, 0.8012450337409973, 0.0024700500071048737, 0.00634999992325902, 0.8014515042304993, 0.0023116159718483686,
  0.004774999804794788, 0.8014515042304993, 0.0023116159718483686, 0.00634999992325902, 0.8014515042304993, 0.0023116159718483686, 0.004774999804794788, 0.8016919493675232, 0.0022120203357189894,
  0.004774999804794788, 0.8016919493675232, 0.0022120203357189894, 0.00634999992325902, 0.8014515042304993, 0.0023116159718483686, 0.00634999992325902, 0.8016919493675232, 0.0022120203357189894,
  0.004774999804794788, 0.8016919493675232, 0.0022120203357189894, 0.00634999992325902, 0.8016919493675232, 0.0022120203357189894, 0.004774999804794788, 0.8019499778747559, 0.002178050111979246,
  0.004774999804794788, 0.8019499778747559, 0.002178050111979246, 0.00634999992325902, 0.8016919493675232, 0.0022120203357189894, 0.00634999992325902, 0.8019499778747559, 0.002178050111979246,
  5.204170427930421e-18, 0.8019499778747559, 0.002178050111979246, 0.0015750000020489097, 0.8019499778747559, 0.002178050111979246, 5.204170427930421e-18, 0.8022080063819885, 0.0022120203357189894,
  5.204170427930421e-18, 0.8022080063819885, 0.0022120203357189894, 0.0015750000020489097, 0.8019499778747559, 0.002178050111979246, 0.0015750000020489097, 0.8022080063819885, 0.0022120203357189894,
  5.204170427930421e-18, 0.8022080063819885, 0.0022120203357189894, 0.0015750000020489097, 0.8022080063819885, 0.0022120203357189894, 5.204170427930421e-18, 0.8024484515190125, 0.0023116159718483686,
  5.204170427930421e-18, 0.8024484515190125, 0.0023116159718483686, 0.0015750000020489097, 0.8022080063819885, 0.0022120203357189894, 0.0015750000020489097, 0.8024484515190125, 0.0023116159718483686,
  5.204170427930421e-18, 0.8024484515190125, 0.0023116159718483686, 0.0015750000020489097, 0.8024484515190125, 0.0023116159718483686, 5.204170427930421e-18, 0.8026549220085144, 0.0024700500071048737,
  5.204170427930421e-18, 0.8026549220085144, 0.0024700500071048737, 0.0015750000020489097, 0.8024484515190125, 0.0023116159718483686, 0.0015750000020489097, 0.8026549220085144, 0.0024700500071048737,
  5.204170427930421e-18, 0.8026549220085144, 0.0024700500071048737, 0.0015750000020489097, 0.8026549220085144, 0.0024700500071048737, 5.204170427930421e-18, 0.8028134107589722, 0.002676524920389056,
  5.204170427930421e-18, 0.8028134107589722, 0.002676524920389056, 0.0015750000020489097, 0.8026549220085144, 0.0024700500071048737, 0.0015750000020489097, 0.8028134107589722, 0.002676524920389056,
  5.204170427930421e-18, 0.8028134107589722, 0.002676524920389056, 0.0015750000020489097, 0.8028134107589722, 0.002676524920389056, 5.204170427930421e-18, 0.8029129505157471, 0.0029169702902436256,
  5.204170427930421e-18, 0.8029129505157471, 0.0029169702902436256, 0.0015750000020489097, 0.8028134107589722, 0.002676524920389056, 0.0015750000020489097, 0.8029129505157471, 0.0029169702902436256,
  5.204170427930421e-18, 0.8029129505157471, 0.0029169702902436256, 0.0015750000020489097, 0.8029129505157471, 0.0029169702902436256, 5.204170427930421e-18, 0.802946925163269, 0.00317499996162951,
  5.204170427930421e-18, 0.802946925163269, 0.00317499996162951, 0.0015750000020489097, 0.8029129505157471, 0.0029169702902436256, 0.0015750000020489097, 0.802946925163269, 0.00317499996162951,
  5.204170427930421e-18, 0.802946925163269, 0.00317499996162951, 0.0015750000020489097, 0.802946925163269, 0.00317499996162951, 5.204170427930421e-18, 0.8029129505157471, 0.003433029633015394,
  5.204170427930421e-18, 0.8029129505157471, 0.003433029633015394, 0.0015750000020489097, 0.802946925163269, 0.00317499996162951, 0.0015750000020489097, 0.8029129505157471, 0.003433029633015394,
  5.204170427930421e-18, 0.8029129505157471, 0.003433029633015394, 0.0015750000020489097, 0.8029129505157471, 0.003433029633015394, 5.204170427930421e-18, 0.8028134107589722, 0.0036734750028699636,
  5.204170427930421e-18, 0.8028134107589722, 0.0036734750028699636, 0.0015750000020489097, 0.8029129505157471, 0.003433029633015394, 0.0015750000020489097, 0.8028134107589722, 0.0036734750028699636,
  5.204170427930421e-18, 0.8028134107589722, 0.0036734750028699636, 0.0015750000020489097, 0.8028134107589722, 0.0036734750028699636, 5.204170427930421e-18, 0.8026549220085144, 0.00387995014898479,
  5.204170427930421e-18, 0.8026549220085144, 0.00387995014898479, 0.0015750000020489097, 0.8028134107589722, 0.0036734750028699636, 0.0015750000020489097, 0.8026549220085144, 0.00387995014898479,
  5.204170427930421e-18, 0.8026549220085144, 0.00387995014898479, 0.0015750000020489097, 0.8026549220085144, 0.00387995014898479, 5.204170427930421e-18, 0.8024484515190125, 0.004038384184241295,
  5.204170427930421e-18, 0.8024484515190125, 0.004038384184241295, 0.0015750000020489097, 0.8026549220085144, 0.00387995014898479, 0.0015750000020489097, 0.8024484515190125, 0.004038384184241295,
  5.204170427930421e-18, 0.8024484515190125, 0.004038384184241295, 0.0015750000020489097, 0.8024484515190125, 0.004038384184241295, 5.204170427930421e-18, 0.8022080063819885, 0.004137979820370674,
  5.204170427930421e-18, 0.8022080063819885, 0.004137979820370674, 0.0015750000020489097, 0.8024484515190125, 0.004038384184241295, 0.0015750000020489097, 0.8022080063819885, 0.004137979820370674,
  5.204170427930421e-18, 0.8022080063819885, 0.004137979820370674, 0.0015750000020489097, 0.8022080063819885, 0.004137979820370674, 5.204170427930421e-18, 0.8019499778747559, 0.004171949811279774,
  5.204170427930421e-18, 0.8019499778747559, 0.004171949811279774, 0.0015750000020489097, 0.8022080063819885, 0.004137979820370674, 0.0015750000020489097, 0.8019499778747559, 0.004171949811279774,
  5.204170427930421e-18, 0.8019499778747559, 0.004171949811279774, 0.0015750000020489097, 0.8019499778747559, 0.004171949811279774, 5.204170427930421e-18, 0.8016919493675232, 0.004137979820370674,
  5.204170427930421e-18, 0.8016919493675232, 0.004137979820370674, 0.0015750000020489097, 0.8019499778747559, 0.004171949811279774, 0.0015750000020489097, 0.8016919493675232, 0.004137979820370674,
  5.204170427930421e-18, 0.8016919493675232, 0.004137979820370674, 0.0015750000020489097, 0.8016919493675232, 0.004137979820370674, 5.204170427930421e-18, 0.8014515042304993, 0.004038384184241295,
  5.204170427930421e-18, 0.8014515042304993, 0.004038384184241295, 0.0015750000020489097, 0.8016919493675232, 0.004137979820370674, 0.0015750000020489097, 0.8014515042304993, 0.004038384184241295,
  5.204170427930421e-18, 0.8014515042304993, 0.004038384184241295, 0.0015750000020489097, 0.8014515042304993, 0.004038384184241295, 5.204170427930421e-18, 0.8012450337409973, 0.00387995014898479,
  5.204170427930421e-18, 0.8012450337409973, 0.00387995014898479, 0.0015750000020489097, 0.8014515042304993, 0.004038384184241295, 0.0015750000020489097, 0.8012450337409973, 0.00387995014898479,
  5.204170427930421e-18, 0.8012450337409973, 0.00387995014898479, 0.0015750000020489097, 0.8012450337409973, 0.00387995014898479, 5.204170427930421e-18, 0.8010866045951843, 0.0036734750028699636,
  5.204170427930421e-18, 0.8010866045951843, 0.0036734750028699636, 0.0015750000020489097, 0.8012450337409973, 0.00387995014898479, 0.0015750000020489097, 0.8010866045951843, 0.0036734750028699636,
  5.204170427930421e-18, 0.8010866045951843, 0.0036734750028699636, 0.0015750000020489097, 0.8010866045951843, 0.0036734750028699636, 5.204170427930421e-18, 0.8009870052337646, 0.003433029633015394,
  5.204170427930421e-18, 0.8009870052337646, 0.003433029633015394, 0.0015750000020489097, 0.8010866045951843, 0.0036734750028699636, 0.0015750000020489097, 0.8009870052337646, 0.003433029633015394,
  5.204170427930421e-18, 0.8009870052337646, 0.003433029633015394, 0.0015750000020489097, 0.8009870052337646, 0.003433029633015394, 5.204170427930421e-18, 0.8009530305862427, 0.00317499996162951,
  5.204170427930421e-18, 0.8009530305862427, 0.00317499996162951, 0.0015750000020489097, 0.8009870052337646, 0.003433029633015394, 0.0015750000020489097, 0.8009530305862427, 0.00317499996162951,
  5.204170427930421e-18, 0.8009530305862427, 0.00317499996162951, 0.0015750000020489097, 0.8009530305862427, 0.00317499996162951, 5.204170427930421e-18, 0.8009870052337646, 0.0029169702902436256,
  5.204170427930421e-18, 0.8009870052337646, 0.0029169702902436256, 0.0015750000020489097, 0.8009530305862427, 0.00317499996162951, 0.0015750000020489097, 0.8009870052337646, 0.0029169702902436256,
  5.204170427930421e-18, 0.8009870052337646, 0.0029169702902436256, 0.0015750000020489097, 0.8009870052337646, 0.0029169702902436256, 5.204170427930421e-18, 0.8010866045951843, 0.002676524920389056,
  5.204170427930421e-18, 0.8010866045951843, 0.002676524920389056, 0.0015750000020489097, 0.8009870052337646, 0.0029169702902436256, 0.0015750000020489097, 0.8010866045951843, 0.002676524920389056,
  5.204170427930421e-18, 0.8010866045951843, 0.002676524920389056, 0.0015750000020489097, 0.8010866045951843, 0.002676524920389056, 5.204170427930421e-18, 0.8012450337409973, 0.0024700500071048737,
  5.204170427930421e-18, 0.8012450337409973, 0.0024700500071048737, 0.0015750000020489097, 0.8010866045951843, 0.002676524920389056, 0.0015750000020489097, 0.8012450337409973, 0.0024700500071048737,
  5.204170427930421e-18, 0.8012450337409973, 0.0024700500071048737, 0.0015750000020489097, 0.8012450337409973, 0.0024700500071048737, 5.204170427930421e-18, 0.8014515042304993, 0.0023116159718483686,
  5.204170427930421e-18, 0.8014515042304993, 0.0023116159718483686, 0.0015750000020489097, 0.8012450337409973, 0.0024700500071048737, 0.0015750000020489097, 0.8014515042304993, 0.0023116159718483686,
  5.204170427930421e-18, 0.8014515042304993, 0.0023116159718483686, 0.0015750000020489097, 0.8014515042304993, 0.0023116159718483686, 5.204170427930421e-18, 0.8016919493675232, 0.0022120203357189894,
  5.204170427930421e-18, 0.8016919493675232, 0.0022120203357189894, 0.0015750000020489097, 0.8014515042304993, 0.0023116159718483686, 0.0015750000020489097, 0.8016919493675232, 0.0022120203357189894,
  5.204170427930421e-18, 0.8016919493675232, 0.0022120203357189894, 0.0015750000020489097, 0.8016919493675232, 0.0022120203357189894, 5.204170427930421e-18, 0.8019499778747559, 0.002178050111979246,
  5.204170427930421e-18, 0.8019499778747559, 0.002178050111979246, 0.0015750000020489097, 0.8016919493675232, 0.0022120203357189894, 0.0015750000020489097, 0.8019499778747559, 0.002178050111979246,

])

/** Named finite service-contact certificates, not whole-machine collision physics.
 * Source: approved 81539e53 crank_hub_geometry.py (hub rear 25.2mm,
 * 0.7mm nominal removable gap), 1/4-20 nut, latch-hook/pressed-pin datums.
 * Bounds/radius enclose actual raw 60a62a2e native POSITION attributes.
 */
type NativeContactBounds = readonly [number, number, number, number, number, number]
const NATIVE_CONTACT_CARRIER_BOUNDS: readonly NativeContactBounds[] = [
  [-.011125000193715096, 0, -.011125000193715096, .011125000193715096, .025200000032782555, .011125000193715096],
  [-.012664488516747952, -.01269999984651804, 0, .08766448497772217, .01269999984651804, .00800000037997961],
  [-.0020000000949949026, -.0020000000949949026, -3.6739405267362306e-19, .0020000000949949026, .0020000000949949026, .004000000189989805],
  [-.0005000000237487257, -.002497736131772399, -.0044977362267673016, .0005000000237487257, .004000000189989805, .0005000000237487257],
  [-.002324099885299802, -.0023212109226733446, -.0026892763562500477, .002324099885299802, .002324099885299802, .00634999992325902],
  [.0020000000949949026, -.010499999858438969, -.010496518574655056, .057999998331069946, .010486077517271042, .010496518574655056],
  [0, -.006247035693377256, -.0062500000931322575, .00699999975040555, .006247035693377256, .0062500000931322575],
  [-.008100000210106373, -.004100000020116568, -.004100000020116568, 9.460396423368442e-19, .004100000020116568, .004100000020116568],
  [-.002987202489748597, -.003000000026077032, -5.554451121856694e-19, .002987202489748597, .003000000026077032, .06499999761581421],
]
const NATIVE_CONTACT_PIN_BOUNDS: NativeContactBounds = [-1.0179877314432918e-27, -.002968749962747097, -.002968749962747097, .044999998062849045, .002968749962747097, .002968749962747097]
const NATIVE_CONTACT_SHAFT_BOUNDS: NativeContactBounds = [-.0102907195687294, -.0020000000949949026, -.010300000198185444, .0102907195687294, .13750000298023224, .010300000198185444]
const NATIVE_CONTACT_NUT_BOUNDS: NativeContactBounds = [-.010250000283122063, -3.5636223244025614e-28, -.010250000283122063, .010250000283122063, .016100000590085983, .010250000283122063]
const NATIVE_CONTACT_STUD_BOUNDS: NativeContactBounds = [-.0046716127544641495, -.0046716127544641495, -.023900000378489494, .0046716127544641495, .0046716127544641495, .04683750122785568]
const NATIVE_CONTACT_GEAR_BOUNDS: Readonly<Record<SourceGearId, NativeContactBounds>> = {
  T24: [-.02601769007742405, -.02601769007742405, -1e-30, .02601769007742405, .02601769007742405, .00279999990016222],
  T12: [-.013742903247475624, -.013742903247475624, -1e-30, .013742903247475624, .013742903247475624, .00279999990016222],
  'T18-upper': [-.019905386492609978, -.019905386492609978, -1e-30, .019905386492609978, .019905386492609978, .00279999990016222],
  'T18-crank': [-.019905386492609978, -.019905386492609978, -1e-30, .019905386492609978, .019905386492609978, .00279999990016222],
}
const NATIVE_CONTACT_HUB_REAR: Point3 = [0, .025200000032782555, 0]
const NATIVE_CONTACT_SHAFT = `${DRIVE}dt-crankshaft-1`
const NATIVE_CONTACT_STUD = `${PAPER}pd-transgear-knob-shaft-1`
const NATIVE_CONTACT_LATCH_PIN = `${PAPER}vn-transgear-latch-pin-1`
const NATIVE_CONTACT_LATCH_TIP: Point3 = [0, .022224999964237213, 0]
// Pinned raw maximum sqrt(x*x+z*z), rounded OUTWARD. A larger 1.59131mm
// display envelope falsely rejects the native engaged fit; it is not native size.
const NATIVE_CONTACT_LATCH_RADIUS = .001587500050
const NATIVE_CONTACT_HOLE_X = -.076543
const NATIVE_CONTACT_HOLE_Y = -.0036917
const NATIVE_CONTACT_HOLE_RADIUS = .0027
const NATIVE_CONTACT_STRIP_THICKNESS = .0006000000867061317

function nativeContactGearBoundsForPath(path: string): NativeContactBounds {
  for (const id of GEAR_IDS) if (SOURCE_GEAR_PART_PATHS[id] === path) return NATIVE_CONTACT_GEAR_BOUNDS[id]
  throw new Error('Native service contact requires a genuine released wheel path.')
}

/** Read current output only when ACTIVE. Reading must never create an override.
 * Keep baseline axis lengths, exactly as Scene applies world position/rotation
 * while retaining each native body's authored scale. No REST/world seat guess.
 */
function currentPosedMatrix(path: string, out: SourceAssemblyBuffer, target: Float64Array): void {
  const matrix = baseline(out, path)
  target.set(matrix)
  const posed = out.entries.get(path)
  if (!posed || !out.activeEntries.has(posed)) return
  const q = posed.worldQuaternion, x = q[0], y = q[1], z = q[2], w = q[3]
  const sx = Math.hypot(matrix[0]!, matrix[1]!, matrix[2]!), sy = Math.hypot(matrix[4]!, matrix[5]!, matrix[6]!), sz = Math.hypot(matrix[8]!, matrix[9]!, matrix[10]!)
  target[0] = (1 - 2 * (y * y + z * z)) * sx; target[1] = 2 * (x * y + z * w) * sx; target[2] = 2 * (x * z - y * w) * sx
  target[4] = 2 * (x * y - z * w) * sy; target[5] = (1 - 2 * (x * x + z * z)) * sy; target[6] = 2 * (y * z + x * w) * sy
  target[8] = 2 * (x * z + y * w) * sz; target[9] = 2 * (y * z - x * w) * sz; target[10] = (1 - 2 * (x * x + y * y)) * sz
  target[12] = posed.worldPositionMetres[0]; target[13] = posed.worldPositionMetres[1]; target[14] = posed.worldPositionMetres[2]
}

/** A separating support plane is a sufficient finite native-box certificate.
 * Affine face normals plus edge crosses also handle baseline axis roundoff and
 * scales. Intentional installed bores use the named axial face test instead.
 */
function nativeContactSeparatedOnAxis(a: ArrayLike<number>, ab: NativeContactBounds, b: ArrayLike<number>, bb: NativeContactBounds, x: number, y: number, z: number): boolean {
  const length = Math.hypot(x, y, z)
  if (length < 1e-12) return false
  const ax = x * a[0]! + y * a[1]! + z * a[2]!, ay = x * a[4]! + y * a[5]! + z * a[6]!, az = x * a[8]! + y * a[9]! + z * a[10]!
  const bx = x * b[0]! + y * b[1]! + z * b[2]!, by = x * b[4]! + y * b[5]! + z * b[6]!, bz = x * b[8]! + y * b[9]! + z * b[10]!
  const centre = x * (a[12]! - b[12]!) + y * (a[13]! - b[13]!) + z * (a[14]! - b[14]!)
    + .5 * (ax * (ab[0] + ab[3]) + ay * (ab[1] + ab[4]) + az * (ab[2] + ab[5]) - bx * (bb[0] + bb[3]) - by * (bb[1] + bb[4]) - bz * (bb[2] + bb[5]))
  const radius = .5 * (Math.abs(ax) * (ab[3] - ab[0]) + Math.abs(ay) * (ab[4] - ab[1]) + Math.abs(az) * (ab[5] - ab[2])
    + Math.abs(bx) * (bb[3] - bb[0]) + Math.abs(by) * (bb[4] - bb[1]) + Math.abs(bz) * (bb[5] - bb[2]))
  return Math.abs(centre) >= radius - CONTACT_EPS_M * length
}
function nativeContactBoxesSeparated(a: ArrayLike<number>, ab: NativeContactBounds, b: ArrayLike<number>, bb: NativeContactBounds): boolean {
  for (let i = 0; i < 3; i++) {
    const j = ((i + 1) % 3) * 4, k = ((i + 2) % 3) * 4
    if (nativeContactSeparatedOnAxis(a, ab, b, bb, a[j + 1]! * a[k + 2]! - a[j + 2]! * a[k + 1]!, a[j + 2]! * a[k]! - a[j]! * a[k + 2]!, a[j]! * a[k + 1]! - a[j + 1]! * a[k]!)) return true
    if (nativeContactSeparatedOnAxis(a, ab, b, bb, b[j + 1]! * b[k + 2]! - b[j + 2]! * b[k + 1]!, b[j + 2]! * b[k]! - b[j]! * b[k + 2]!, b[j]! * b[k + 1]! - b[j + 1]! * b[k]!)) return true
  }
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
    const k = i * 4, l = j * 4
    if (nativeContactSeparatedOnAxis(a, ab, b, bb, a[k + 1]! * b[l + 2]! - a[k + 2]! * b[l + 1]!, a[k + 2]! * b[l]! - a[k]! * b[l + 2]!, a[k]! * b[l + 1]! - a[k + 1]! * b[l]!)) return true
  }
  return false
}
function nativeContactCarrierClear(body: ArrayLike<number>, bounds: NativeContactBounds, out: SourceAssemblyBuffer): boolean {
  const carrier = out.contactMatrices[3]!
  for (let i = 0; i < CRANK_CARRIER.length; i++) {
    currentPosedMatrix(CRANK_CARRIER[i]!, out, carrier)
    if (!nativeContactBoxesSeparated(body, bounds, carrier, NATIVE_CONTACT_CARRIER_BOUNDS[i]!)) return false
  }
  return true
}

/** Coaxial finite service families share the actual CURRENT axes. The rear
 * hub/front gear gap is C0 + carrierTravel - gearTravel, never C0 + gearTravel.
 * Nut local+Y points opposite gear local+Z; its actual seat origin gives the
 * thread gap, including current hanger/root motion and real thread advance.
 */
function nativeContactAxialGap(gear: ArrayLike<number>, retainer: ArrayLike<number>, hub: boolean, out: SourceAssemblyBuffer): number {
  const p = out.points
  direction(p[0]!, gear, Z); direction(p[1]!, retainer, Y)
  const dot = p[0]![0] * p[1]![0] + p[0]![1] * p[1]![1] + p[0]![2] * p[1]![2]
  if (Math.abs(dot - (hub ? 1 : -1)) > 1e-8) throw new Error('Native retainer and seated gear require their actual parallel service axes.')
  point(p[2]!, gear, ZERO); point(p[3]!, retainer, hub ? NATIVE_CONTACT_HUB_REAR : ZERO)
  // The exact normal seat is authoritative. Its released bore clearance is
  // physical; CONTACT_EPS_M must not impose fictitious 100nm coaxial fit.
  // Parallel face separation is sufficient regardless of transverse offset.
  const dx = p[2]![0] - p[3]![0], dy = p[2]![1] - p[3]![1], dz = p[2]![2] - p[3]![2]
  const gap = dx * p[0]![0] + dy * p[0]![1] + dz * p[0]![2]
  return gap
}

/** Rigorous ellipse-in-circle sufficient bound. In principal axes let offset
 * be (d,e), ellipse semiaxes (a,b). cos(theta)<=1-sin(theta)^2/2 bounds
 * squared radius by (a+|d|)^2+e^2-K*s^2+2*b*|e|*s,
 * K=a^2-b^2+a*|d|, 0<=s<=1. Maximising that quadratic is allocation-free
 * and preserves the actual off-axis latched fit (a loose radius-sum does not).
 */
function nativeContactEllipseFits(dx: number, dy: number, a: number, b: number, cosine: number, sine: number): boolean {
  const d = Math.abs(dx * cosine + dy * sine), e = Math.abs(-dx * sine + dy * cosine), k = Math.max(0, a * a - b * b + a * d)
  const station = k === 0 ? 1 : Math.min(1, b * e / k)
  const radiusSquared = (a + d) ** 2 + e * e - k * station * station + 2 * b * e * station
  return radiusSquared <= (NATIVE_CONTACT_HOLE_RADIUS + CONTACT_EPS_M) ** 2
}
function validateNativeLatchContact(out: SourceAssemblyBuffer): void {
  const hook = out.contactMatrices[0]!, pin = out.contactMatrices[1]!, p = out.points
  currentPosedMatrix(HOOK, out, hook); currentPosedMatrix(NATIVE_CONTACT_LATCH_PIN, out, pin)
  point(p[0]!, pin, ZERO); inversePoint(p[0]!, hook, p[0]!)
  point(p[1]!, pin, NATIVE_CONTACT_LATCH_TIP); inversePoint(p[1]!, hook, p[1]!)
  point(p[2]!, pin, X); inversePoint(p[2]!, hook, p[2]!)
  point(p[3]!, pin, Z); inversePoint(p[3]!, hook, p[3]!)
  for (let i = 0; i < 3; i++) { p[2]![i] = p[2]![i]! - p[0]![i]!; p[3]![i] = p[3]![i]! - p[0]![i]! }
  const radialZ = NATIVE_CONTACT_LATCH_RADIUS * Math.hypot(p[2]![2], p[3]![2])
  if (Math.max(p[0]![2], p[1]![2]) + radialZ <= CONTACT_EPS_M
    || Math.min(p[0]![2], p[1]![2]) - radialZ >= NATIVE_CONTACT_STRIP_THICKNESS - CONTACT_EPS_M) return
  const ax = p[1]![0] - p[0]![0], ay = p[1]![1] - p[0]![1], az = p[1]![2] - p[0]![2]
  if (Math.abs(az) < 1e-12) throw new Error('Current finite latch pin crosses the strip without a certifiable aperture axis.')
  const midStation = (NATIVE_CONTACT_STRIP_THICKNESS / 2 - p[0]![2]) / az
  if (midStation < 0 || midStation > 1) throw new Error('Latch aperture cannot use an infinite extrapolation of the finite pressed pin.')
  // Exact affine infinite-cylinder sections bound every finite native pin
  // section. The full hook inverse keeps this root/scale covariant.
  const bxx = NATIVE_CONTACT_LATCH_RADIUS * (p[2]![0] - ax / az * p[2]![2]), bxz = NATIVE_CONTACT_LATCH_RADIUS * (p[3]![0] - ax / az * p[3]![2])
  const byx = NATIVE_CONTACT_LATCH_RADIUS * (p[2]![1] - ay / az * p[2]![2]), byz = NATIVE_CONTACT_LATCH_RADIUS * (p[3]![1] - ay / az * p[3]![2])
  const xx = bxx * bxx + bxz * bxz, xy = bxx * byx + bxz * byz, yy = byx * byx + byz * byz
  const spread = Math.hypot(xx - yy, 2 * xy), a = Math.sqrt(Math.max(0, (xx + yy + spread) / 2)), b = Math.sqrt(Math.max(0, (xx + yy - spread) / 2))
  const angle = .5 * Math.atan2(2 * xy, xx - yy), cosine = Math.cos(angle), sine = Math.sin(angle)
  for (let face = 0; face < 2; face++) {
    const station = (face * NATIVE_CONTACT_STRIP_THICKNESS - p[0]![2]) / az
    const dx = p[0]![0] + station * ax - NATIVE_CONTACT_HOLE_X, dy = p[0]![1] + station * ay - NATIVE_CONTACT_HOLE_Y
    if (!nativeContactEllipseFits(dx, dy, a, b, cosine, sine)) throw new Error('Current finite latch pin neither clears the actual strip planes nor fits its actual aperture.')
  }
}

function validateNativeServiceContacts(state: Exclude<SourceAssemblyState, { kind: 'operating' }>, out: SourceAssemblyBuffer): void {
  const body = out.contactMatrices[0]!, retainer = out.contactMatrices[1]!, fixed = out.contactMatrices[2]!
  if (state.crank) {
    // A held label is a claim of actual release, not a bypass at installed pose.
    if (state.crank.pin.attachment === 'held') {
      currentPosedMatrix(PIN, out, body); currentPosedMatrix(HUB, out, retainer)
      if (!nativeContactBoxesSeparated(body, NATIVE_CONTACT_PIN_BOUNDS, retainer, NATIVE_CONTACT_CARRIER_BOUNDS[0]!)) throw new Error('Held tapered pin must actually clear the current native hub barrel.')
      currentPosedMatrix(NATIVE_CONTACT_SHAFT, out, fixed)
      if (!nativeContactBoxesSeparated(body, NATIVE_CONTACT_PIN_BOUNDS, fixed, NATIVE_CONTACT_SHAFT_BOUNDS)) throw new Error('Held tapered pin must actually clear the current native crankshaft.')
    }
    if (state.crank.carrier.attachment === 'held') {
      currentPosedMatrix(NATIVE_CONTACT_SHAFT, out, fixed)
      if (!nativeContactCarrierClear(fixed, NATIVE_CONTACT_SHAFT_BOUNDS, out)) throw new Error('Held crank carrier must actually clear the current native fixed shaft.')
    }
  }
  if (state.retainingNut?.attachment === 'held') {
    // The installed native nut already has 0.1mm plate air. Plate separation
    // alone cannot certify release from the intentional threaded bore overlap.
    currentPosedMatrix(NUT, out, body); currentPosedMatrix(NATIVE_CONTACT_STUD, out, fixed)
    if (!nativeContactBoxesSeparated(body, NATIVE_CONTACT_NUT_BOUNDS, fixed, NATIVE_CONTACT_STUD_BOUNDS)) throw new Error('Held retaining nut must actually clear the current native threaded stud.')
  }
  const gears = state.gears
  if (gears) {
    for (const id of GEAR_IDS) {
      const member = gears.members[id], bounds = NATIVE_CONTACT_GEAR_BOUNDS[id]
      currentPosedMatrix(SOURCE_GEAR_PART_PATHS[id], out, body)
      const axial = member.attachment !== 'held' && member.attachment !== 'stored'
      if (axial && member.attachment.startsWith('crank') && state.crank?.carrier.attachment !== 'held') {
        currentPosedMatrix(HUB, out, retainer)
        if (nativeContactAxialGap(body, retainer, true, out) < -CONTACT_EPS_M) throw new Error('Current crank gear front crosses the actual carrier rear retaining face.')
      } else if (!nativeContactCarrierClear(body, bounds, out)) throw new Error('Current free/offset native gear requires finite clearance from every actual crank carrier body.')
      if (axial && member.attachment.startsWith('upper') && state.retainingNut?.attachment !== 'held') {
        currentPosedMatrix(NUT, out, retainer)
        if (nativeContactAxialGap(body, retainer, false, out) < -CONTACT_EPS_M) throw new Error('Current upper gear front crosses the actual threaded nut retaining seat.')
      } else {
        currentPosedMatrix(NUT, out, retainer)
        if (!nativeContactBoxesSeparated(body, bounds, retainer, NATIVE_CONTACT_NUT_BOUNDS)) throw new Error('Current free/offset native gear requires finite clearance from the actual retaining nut.')
      }
    }
  } else {
    // Unchanged visible current occupants also matter when only their retainer
    // moves; never substitute inactive T12/T24 inventory poses or REST shafts.
    if (state.crank) {
      const path = out.gearSeats.crank.partPath
      if (!path) throw new Error('Crank service contact requires the actual current native wheel seat.')
      currentPosedMatrix(path, out, body)
      if (state.crank.carrier.attachment === 'held') {
        if (!nativeContactCarrierClear(body, nativeContactGearBoundsForPath(path), out)) throw new Error('Held carrier must actually clear the current seated native crank gear.')
      } else {
        currentPosedMatrix(HUB, out, retainer)
        if (nativeContactAxialGap(body, retainer, true, out) < -CONTACT_EPS_M) throw new Error('Current crank gear front crosses the actual carrier rear retaining face.')
      }
    }
    if (state.retainingNut || state.hanger) {
      const path = out.gearSeats.upper.partPath
      if (!path) throw new Error('Nut service contact requires the actual current native upper wheel seat.')
      currentPosedMatrix(path, out, body); currentPosedMatrix(NUT, out, retainer)
      if (state.retainingNut?.attachment === 'held') {
        if (!nativeContactBoxesSeparated(body, nativeContactGearBoundsForPath(path), retainer, NATIVE_CONTACT_NUT_BOUNDS)) throw new Error('Held nut must actually clear the current seated native upper gear.')
      } else if (nativeContactAxialGap(body, retainer, false, out) < -CONTACT_EPS_M) throw new Error('Current upper gear front crosses the actual threaded nut retaining seat.')
    }
  }
  if (state.hanger) validateNativeLatchContact(out)
}
