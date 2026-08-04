/**
 * The contract between the CAD export and the simulator.
 *
 * `doit export` writes `cad/out/gltf/harmonic-analyzer.glb` from the SolidWorks
 * assembly, so every node in the scene graph is named after its component
 * instance (`cone-gear-1`, `cylinder-gear-7`, `crank-arm-1`, ...). The
 * simulator drives named nodes; it does NOT hardcode indices into the glTF, so
 * a re-export that adds or reorders components cannot silently break it.
 *
 * If a binding does not resolve, the simulator warns once and keeps running
 * with that joint static — a partially animated machine is much better than a
 * blank screen, and the warning names exactly which node pattern went missing.
 */

/** A joint the simulator drives, and how to find it in the glTF. */
export interface Binding {
  /** Logical joint id used by the animation code. */
  id: string
  /**
   * Case-insensitive regex matched against node names. The first match wins for
   * `single`; every match is collected, ordered by the trailing instance
   * number, for `indexed`.
   */
  pattern: RegExp
  kind: 'single' | 'indexed'
  /** Local axis the joint rotates or translates about, in model space. */
  axis: [number, number, number]
  motion: 'rotate' | 'translate'
  note?: string
}

export const BINDINGS: Binding[] = [
  {
    id: 'crank',
    pattern: /^crank-arm/i,
    kind: 'single',
    axis: [0, 0, 1],
    motion: 'rotate',
    note: 'The sole input. Everything else is a function of this angle.',
  },
  {
    id: 'coneGears',
    pattern: /^cone-gear-(\d+)/i,
    kind: 'indexed',
    axis: [1, 0, 0],
    motion: 'rotate',
    note: 'All twenty rotate together on one shaft at crank/4.',
  },
  {
    id: 'cylinderGears',
    pattern: /^cylinder-gear-(\d+)/i,
    kind: 'indexed',
    axis: [1, 0, 0],
    motion: 'rotate',
    note: 'Gear k turns at k times the fundamental — the twenty frequencies.',
  },
  {
    id: 'connectingRods',
    pattern: /^connecting-rod-(\d+)/i,
    kind: 'indexed',
    axis: [0, 1, 0],
    motion: 'translate',
    note: 'Driven by the eccentric cam on the cylinder gear to its right.',
  },
  {
    id: 'rockerArms',
    pattern: /^rocker-arm-(\d+)/i,
    kind: 'indexed',
    axis: [1, 0, 0],
    motion: 'rotate',
    note: 'Seesaws; the tip traces a near-sinusoid.',
  },
  {
    id: 'channelLevers',
    pattern: /^channel-lever-(\d+)/i,
    kind: 'indexed',
    axis: [1, 0, 0],
    motion: 'rotate',
    note: 'Third-class lever; motion scaled by the amplitude-bar position.',
  },
  {
    id: 'summingLever',
    pattern: /^summing-lever/i,
    kind: 'single',
    axis: [1, 0, 0],
    motion: 'rotate',
    note: 'Rocks on the knife edge. Range is only a few millimetres.',
  },
  {
    id: 'magnifyingLever',
    pattern: /^magnifying-lever/i,
    kind: 'single',
    axis: [1, 0, 0],
    motion: 'rotate',
  },
  {
    id: 'magnifyingWheel',
    pattern: /^magnifying-wheel/i,
    kind: 'single',
    axis: [0, 0, 1],
    motion: 'rotate',
    note: 'Fixed x5: 100 mm outer over 20 mm hub.',
  },
  {
    id: 'penRod',
    pattern: /^pen-rod/i,
    kind: 'single',
    axis: [0, 1, 0],
    motion: 'translate',
    note: 'Vertical only. The paper supplies the horizontal.',
  },
  {
    id: 'platen',
    pattern: /^platen-1|^platen$/i,
    kind: 'single',
    axis: [1, 0, 0],
    motion: 'translate',
    note: 'Horizontal travel, driven off the crank through the transgear train.',
  },
]

/**
 * Sort key for indexed bindings: the trailing instance number in the node name,
 * so `cylinder-gear-2` comes before `cylinder-gear-10` (a plain string sort
 * would not).
 */
export function instanceIndex(name: string, pattern: RegExp): number {
  const m = name.match(pattern)
  const captured = m?.[1]
  return captured ? Number.parseInt(captured, 10) : 0
}
