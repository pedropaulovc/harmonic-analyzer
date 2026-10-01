import { MECHANISM_DATA } from './mechanics-data'

/**
 * Taut, inextensible, non-slipping output wires, on the installed branch.
 *
 * Evidence: Michelson & Stratton, A New Harmonic Analyzer (1898), pp. 3–4,
 * figure 1, connects the summing extension to the recorder by a fine wire.
 * The surviving twenty-channel machine adds the coaxial pulley: Synthesis
 * https://www.youtube.com/watch?v=8KmVDxkia_w&t=243 and Operation
 * https://www.youtube.com/watch?v=jfH-NbsmvD4&t=330 show the separate hub and
 * rim wires. The 100/20 mm diameters give the nominal unsigned thin-wire gain;
 * source-video handedness must be checked against the released routing below.
 *
 * Geometry is the released CAD's lever_wire_geom.py, pen_wire_geom.py and
 * magnifying_wheel_geom.py at MECHANISM_DATA.provenance.sourceCommit. Its
 * exaggerated 0.8 mm wire is retained, including its finite pitch radius;
 * the 0.25 mm interference-check stand-off is VISUAL ONLY, never extra gain.
 * The source CAD's point/plane yokes are rest-linearized motion-study aids,
 * not the physical winding law. Neither a Fourier output nor a yoke sine
 * enters this solver.
 *
 * At a hook H, the selected circle tangent has azimuth a and free length L.
 * An unknown initial number of turns cancels in the inextensible constraint:
 *   L + r * (a - wheelAngle) = L0 + r * a0.
 * The source hub lane fixes contact Z. Include the small fleet-angle depth
 * offset in L; the circumferential wrap remains in that lane. This is the
 * quasistatic installed/guided-wrap branch, not a simulation of slack, slip,
 * unravelling, axial wrap migration, elastic wire or contact-force dynamics.
 *
 * On the released minus tangent, hub -> hook points along the wheel's +Z
 * circumferential velocity. The left-rim hanging run also leaves along that
 * velocity (global -Y). Positive global +Z spin therefore pays out both runs:
 * the pen descends, so penTravel = -rimPitchRadius * wheelAngle.
 * Changing clamp position does NOT secretly reset the wire's installed length.
 */

const M = MECHANISM_DATA.magnifier
const CX = M.wheelCentreMm[0] / 1000
const CY = M.wheelCentreMm[1] / 1000
const CZ = M.wheelCentreMm[2] / 1000
const CONTACT_Z = M.hubTangentMm[2] / 1000

// Source lever_wire_geom.YOKE_PITCH_R and magnifying_wheel_geom diameters.
// Keep physical pitch and the CAD's artificial visual separation distinct.
export const MAGNIFIER_WIRE_DIAMETER_M = 0.0008
const WIRE_RADIUS = MAGNIFIER_WIRE_DIAMETER_M / 2
const HUB_RADIUS = 0.020 / 2 + WIRE_RADIUS
const RIM_RADIUS = 0.100 / 2 + WIRE_RADIUS
const VISUAL_CLEARANCE = 0.00025
const VISUAL_HUB_RADIUS = HUB_RADIUS + VISUAL_CLEARANCE
const REST_HOOK_X = M.hookMm[0] / 1000
const REST_HOOK_Y = M.hookMm[1] / 1000
const REST_HOOK_Z = M.hookMm[2] / 1000
const REST_D2 = (REST_HOOK_X - CX) ** 2 + (REST_HOOK_Y - CY) ** 2
const REST_AZIMUTH = Math.atan2(REST_HOOK_Y - CY, REST_HOOK_X - CX)
  - Math.acos(HUB_RADIUS / Math.sqrt(REST_D2))
const REST_LENGTH = Math.sqrt(REST_D2 - HUB_RADIUS ** 2 + (REST_HOOK_Z - CONTACT_Z) ** 2)
const REST_PEN_WIRE_Y = M.penWireBottomMm[1] / 1000

// build_pen_assembly.MARKER_POS: the nib is the marker part's local origin.
// Checked against released GLB world translation, maximum delta 0.000013 mm.
const PEN_X = -0.01035
const PEN_Y = 0.36325
const PEN_Z = -0.14365

export interface MagnifierInput {
  /** Actual moving hook, not the clamp centre or a normalized Fourier sum. */
  magnifierHookM: ArrayLike<number>
  /** The upstream rigid group supplies these for a common pose contract. */
  magnifierClampM: ArrayLike<number>
  summingAngleRad: number
}

export interface MagnifierPose {
  /** Rotation about global +Z through the source wheel centre, radians. */
  wheelAngleRad: number
  /** Signed global +Y translation of every moving pen-carriage component. */
  penTravelM: number
  /** Marker nib in the original CAD frame, metres. */
  penM: Float64Array
  /** Physical wire-centreline contacts, without the CAD display stand-off. */
  hubContactM: Float64Array
  rimContactM: Float64Array
  /** Visible authentic straight runs: hook -> hub; rim -> rod. XYZ pairs. */
  leverWirePathM: Float64Array
  penWirePathM: Float64Array
  /** Circumferential wrap-angle change; initial wrap count is not invented. */
  wrapAngleDeltaRad: number
  /** Net hub payout including the migrating tangent's wrap contribution. */
  cablePayoutM: number
  /** Free hook-to-hub span (not constant: the wheel pays wire in/out). */
  leverWireLengthM: number
}

export function createMagnifierPose(): MagnifierPose {
  const pose: MagnifierPose = {
    wheelAngleRad: 0,
    penTravelM: 0,
    penM: new Float64Array(3),
    hubContactM: new Float64Array(3),
    rimContactM: new Float64Array(3),
    leverWirePathM: new Float64Array(6),
    penWirePathM: new Float64Array(6),
    wrapAngleDeltaRad: 0,
    cablePayoutM: 0,
    leverWireLengthM: REST_LENGTH,
  }
  solveMagnifier({
    magnifierHookM: [REST_HOOK_X, REST_HOOK_Y, REST_HOOK_Z],
    magnifierClampM: [0.150, 0.9797, -0.1283],
    summingAngleRad: 0,
  }, pose)
  return pose
}

/** Mutate stable buffers. No per-frame objects, arrays, or geometry are made. */
export function solveMagnifier(input: MagnifierInput, pose: MagnifierPose): void {
  const hx = input.magnifierHookM[0]!
  const hy = input.magnifierHookM[1]!
  const hz = input.magnifierHookM[2]!
  if (!Number.isFinite(hx) || !Number.isFinite(hy) || !Number.isFinite(hz)) {
    throw new RangeError('Magnifier hook must contain three finite CAD metre coordinates')
  }
  const dx = hx - CX
  const dy = hy - CY
  const d2 = dx * dx + dy * dy
  if (d2 <= VISUAL_HUB_RADIUS * VISUAL_HUB_RADIUS || dy <= 0) {
    throw new RangeError('Magnifier hook has left the installed upper hub-tangent branch')
  }
  const d = Math.sqrt(d2)
  const bearing = Math.atan2(dy, dx)
  const azimuth = bearing - Math.acos(HUB_RADIUS / d)
  const length = Math.sqrt(d2 - HUB_RADIUS * HUB_RADIUS + (hz - CONTACT_Z) ** 2)
  const wheelAngle = azimuth - REST_AZIMUTH + (length - REST_LENGTH) / HUB_RADIUS
  const penTravel = -RIM_RADIUS * wheelAngle
  const penWireY = REST_PEN_WIRE_Y + penTravel
  if (penWireY >= CY) {
    throw new RangeError('Pen wire has exhausted its hanging run; reset the physical output fixture before using this clamp setting')
  }

  pose.wheelAngleRad = wheelAngle
  pose.penTravelM = penTravel
  pose.penM[0] = PEN_X
  pose.penM[1] = PEN_Y + penTravel
  pose.penM[2] = PEN_Z
  pose.hubContactM[0] = CX + HUB_RADIUS * Math.cos(azimuth)
  pose.hubContactM[1] = CY + HUB_RADIUS * Math.sin(azimuth)
  pose.hubContactM[2] = CONTACT_Z
  pose.rimContactM[0] = CX - RIM_RADIUS
  pose.rimContactM[1] = CY
  pose.rimContactM[2] = CZ
  pose.wrapAngleDeltaRad = azimuth - REST_AZIMUTH - wheelAngle
  pose.cablePayoutM = HUB_RADIUS * wheelAngle
  pose.leverWireLengthM = length

  // Source model deliberately shows a stand-off. Recompute its source-nominal
  // tangent separately from the physical pitch contact. The saved GLB's hub
  // endpoint is 0.028394 mm shallower in Z than lever_wire_geom.WIRE_END
  // (hook differs by 0.000012 mm); this solver retains the explicit source
  // lane instead of baking a native assembly-solver residual into the law.
  const visualAzimuth = bearing - Math.acos(VISUAL_HUB_RADIUS / d)
  const lever = pose.leverWirePathM
  lever[0] = hx; lever[1] = hy; lever[2] = hz
  lever[3] = CX + VISUAL_HUB_RADIUS * Math.cos(visualAzimuth)
  lever[4] = CY + VISUAL_HUB_RADIUS * Math.sin(visualAzimuth)
  lever[5] = CONTACT_Z
  const pen = pose.penWirePathM
  pen[0] = M.penWireBottomMm[0] / 1000; pen[1] = CY; pen[2] = CZ
  pen[3] = pen[0]; pen[4] = penWireY; pen[5] = CZ
}
