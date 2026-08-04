/**
 * The machine's kinematics, in one place, derived from the source and not from
 * the CAD model.
 *
 * The geometry comes from the GLB; the *motion* comes from here. Keeping them
 * separate means a re-export of the model can never silently change the maths,
 * and the maths can be unit-tested without a renderer.
 *
 * Source of the ratios: Michelson & Stratton, "A New Harmonic Analyzer" (1898),
 * and the gear train as modelled in `cad/config/machine/gear_train.yaml`.
 *
 *   "The analyzer's gears are sized such that a single full turn of the crank
 *    rotates the first gear of the cylindrical set through 1/80th of a full
 *    rotation, the second 2/80ths, the third 3/80ths, etc."
 *
 * So for cylinder gear k (k = 1..20), after `turns` full crank revolutions:
 *
 *     theta_k = turns * k * 2*PI / 80  =  turns * k * PI / 40
 *
 * Two crank turns therefore advance gear k by k*PI/20 — which is exactly the
 * argument of the k-th cosine in the machine's sum. That identity is why
 * reading the output every two turns performs Fourier *analysis*.
 */

/** Number of channels in this machine. The 80-element variant used 80. */
export const CHANNELS = 20

/** Crank revolutions per unit advance of the Fourier argument x. */
export const TURNS_PER_X_UNIT = 80 / (2 * Math.PI)

/**
 * Angle of cylinder gear `k` (1-based) after `turns` crank revolutions, radians.
 */
export function channelAngle(turns: number, k: number): number {
  return (turns * k * Math.PI) / 40
}

/**
 * The Fourier argument x corresponding to a crank position.
 * x advances by PI/20 every two turns, so one full period (2*PI) takes 80 turns.
 */
export function fourierArgument(turns: number): number {
  return (turns * Math.PI) / 40
}

/**
 * Vertical displacement of rocker-arm k's tip, normalised to +/-1.
 *
 * The cam is a plain eccentric circle, so the rocker motion is *near*
 * sinusoidal, not exactly sinusoidal — the book is explicit about this and it
 * is a real error source in the machine. `camHarmonic` below models the first
 * correction; set it to 0 for the idealised cosine.
 */
export function rockerDisplacement(turns: number, k: number, camHarmonic = 0): number {
  const t = channelAngle(turns, k)
  return Math.cos(t) + camHarmonic * Math.cos(2 * t)
}

/**
 * The summing lever's output: the weighted sum of all channels.
 *
 * `amplitudes[k-1]` is the coefficient a_k set by the position of amplitude bar
 * k on its rocker arm. The measuring stick divides each half of a rocker arm
 * into ten, so the usable range is [-10, +10]; the sign is which side of the
 * rocker pivot the bar sits on, and a bar at the pivot is exactly zero.
 */
export function output(turns: number, amplitudes: readonly number[], camHarmonic = 0): number {
  let sum = 0
  for (let k = 1; k <= CHANNELS; k++) {
    sum += (amplitudes[k - 1] ?? 0) * rockerDisplacement(turns, k, camHarmonic)
  }
  return sum
}

/** Magnification: x4 at the magnifying lever (settable), x5 at the wheel (fixed). */
export const WHEEL_MAGNIFICATION = 5
export const LEVER_MAGNIFICATION_MAX = 4

/** Magnifying-wheel rotation, radians, for a given summing-lever travel in mm. */
export function wheelAngle(leverTravelMm: number, leverMagnification = LEVER_MAGNIFICATION_MAX): number {
  const HUB_RADIUS_MM = 10 // inner wheel: 20 mm diameter
  return (leverTravelMm * leverMagnification) / HUB_RADIUS_MM
}

/**
 * The three translational-gearing options. The operator swaps two removable
 * gears (small/medium/large) to set how far the paper travels per crank turn,
 * which is the horizontal scale of the plot.
 */
export type Gearing = 'small-large' | 'medium-medium' | 'large-small'

/** Periods of the fundamental drawn across the full platen travel. */
export const GEARING_PERIODS: Record<Gearing, number> = {
  'small-large': 2,
  'medium-medium': 1,
  'large-small': 0.5,
}

/** Platen position, normalised 0..1 across its travel. */
export function platenPosition(turns: number, gearing: Gearing): number {
  const turnsPerPeriod = 80
  const full = turnsPerPeriod * GEARING_PERIODS[gearing]
  return Math.min(1, turns / full)
}

/**
 * Sample a coefficient set from a function, the way an operator does it:
 * the function is sampled at twenty discrete points and each sample becomes
 * one amplitude-bar position.
 */
export function sampleToAmplitudes(f: (x: number) => number, scale = 10): number[] {
  const out: number[] = []
  for (let k = 1; k <= CHANNELS; k++) {
    out.push(scale * f((k * Math.PI) / CHANNELS))
  }
  return out
}

/** Coefficients for a square wave: odd harmonics falling as 1/n. */
export function squareWave(scale = 10): number[] {
  return Array.from({ length: CHANNELS }, (_, i) => {
    const n = i + 1
    return n % 2 === 1 ? scale / n : 0
  })
}
