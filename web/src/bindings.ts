/**
 * Which GLB nodes move, and how. Patterns match the full node path under the
 * release GLB root (current CAD stems, e.g. ha-harmonic-analyzer/ch-channel/
 * ch-rocker-arm-7). A node no binding matches stays at its authored pose. A
 * binding that resolves fewer nodes than expected is reported as a warning;
 * the rest of the machine still animates.
 */
export type Motion =
  | 'crank' | 'cone-spin' | 'cone-swing' | 'cylinder' | 'rod' | 'rocker'
  | 'bar' | 'lever' | 'channel-spring' | 'summing' | 'counter-spring'
  | 'gooseneck' | 'magnifier-fixed' | 'magnifier-clamp' | 'magnifier-rod' | 'magnifier-fixture'
  | 'wheel' | 'lever-wire' | 'pen-wire' | 'pen' | 'platen'
  | 'pinion-swing' | 'pinion-cam' | 'pinion-lever'
  | 'paper-knob' | 'paper-feed' | 'paper-sprocket' | 'chain-link'

export interface Binding {
  id: string
  pattern: RegExp
  /** indexed: one node per channel station, numbered 1..20 by the trailing instance number. */
  kind: 'indexed' | 'group'
  motion: Motion
  expected: number
}

const channel = 'ha-harmonic-analyzer/ch-channel/'
const drive = 'ha-harmonic-analyzer/dt-drive-train/'
const magnifier = 'ha-harmonic-analyzer/mg-magnifier/'
const summing = 'ha-harmonic-analyzer/sm-summing/'
const pen = 'ha-harmonic-analyzer/pn-pen/'
const paper = 'ha-harmonic-analyzer/pd-paper-drive/'

function family(id: string, group: string, name: string, motion: Motion): Binding {
  return { id, pattern: new RegExp(`^${group}${name}-(\\d+)$`), kind: 'indexed', motion, expected: 20 }
}

function group(id: string, path: string, names: string, motion: Motion, expected: number): Binding {
  return { id, pattern: new RegExp(`^${path}(?:${names})$`), kind: 'group', motion, expected }
}

export const BINDINGS: readonly Binding[] = [
  group('crank', drive, '(?:dt-crankshaft|dt-crank-arm|dt-crank-hub|dt-vn-crank-hub-pin|dt-crank-pin|dt-crank-handle-pivot-screw|dt-crank-pin-ring|dt-crank-handle|dt-crank-handle-butt-cup|dt-crank-handle-ferrule|dt-crank-pinion|dt-crank-pinion-pin|dt-vn-keeper-chain|dt-vn-keeper-chain-screw)-1|dt-vn-crank-seat-drive-pin-[12]', 'crank', 16),
  group('coneGears', drive, 'dt-cone-gear-\\d+|dt-cone-tip-gear-1', 'cone-spin', 20),
  group('coneShaft', drive, '(?:dt-cone-gear-shaft|dt-crank-drive-gear|dt-vn-cone-shaft-key)-1', 'cone-spin', 3),
  group('conePlatform', drive, '(?:dt-cone-swing-platform|dt-cone-tip-block|dt-vn-cone-tip-pinch-screw|dt-vn-cone-tip-block-screw|dt-cone-pivot-post|dt-cone-tip-bushing|dt-cone-tip-end-screw)-1|dt-vn-post-mount-screw-[12]', 'cone-swing', 9),
  family('cylinderGears', drive, 'dt-cylinder-gear', 'cylinder'),
  family('connectingRods', channel, 'ch-connecting-rod', 'rod'),
  family('rockerArms', channel, 'ch-rocker-arm', 'rocker'),
  family('amplitudeBars', channel, 'ch-amplitude-bar', 'bar'),
  family('channelLevers', channel, 'ch-channel-lever', 'lever'),
  family('channelSprings', channel, 'ch-vn-channel-spring-installed-stretch00', 'channel-spring'),
  family('springSupports', channel, 'ch-vn-spring-hook', 'summing'),
  group('summingLever', summing, '(?:sm-summing-lever|sm-vn-boss-hook)-1', 'summing', 2),
  group('gooseneck', summing, '(?:sm-gooseneck|sm-gooseneck-end-plug|sm-vn-gooseneck-shoulder-screw)-1', 'gooseneck', 3),
  group('counterSpring', summing, 'sm-vn-counter-spring-1', 'counter-spring', 1),
  group('magnifierLever', magnifier, '(?:mg-magnifying-lever|mg-magnifying-bracket)-1', 'magnifier-fixed', 2),
  group('magnifierClamp', magnifier, '(?:mg-magnifying-clamp|sh-vn-thumb-screw)-1', 'magnifier-clamp', 2),
  group('magnifierRod', magnifier, 'mg-magnifying-vertical-rod-1', 'magnifier-rod', 1),
  group('magnifierFixture', magnifier, 'mg-output-fixture-1|sh-vn-thumb-screw-2', 'magnifier-fixture', 2),
  group('magnifyingWheel', magnifier, '(?:mg-magnifying-wheel|mg-wheel-drum)-1', 'wheel', 2),
  group('leverWire', magnifier, 'sh-vn-music-wire-1', 'lever-wire', 1),
  group('penWire', pen, 'sh-vn-music-wire-1', 'pen-wire', 1),
  group('pen', pen, '(?:pn-pen-rod|pn-pen-v-block|pn-pen-frame|pn-vn-pen-marker|pn-vn-pen-set-screw)-1', 'pen', 5),
  // The carriage: platen, rack, paper, clips, guides and their screws.
  group('platen', paper, '(?:pd-platen|pd-platen-rack|pd-platen-paper)-1|(?:pd-platen-clip|pd-platen-guide)-[12]|pd-guide-lock-[1-4]|sh-vn-brass-fillister-screw-(?:[1-9]|10)|pd-vn-guide-lock-screw-[1-8]|pd-vn-platen-clip-screw-[1-4]', 'platen', 33),
  group('alignmentPinionSwing', drive, 'dt-pinion-bracket-[12]|dt-alignment-pinion-1|dt-pinion-arbor-1|dt-vn-pinion-strap-pin-[123]|dt-pinion-handle-1|dt-pinion-arbor-collar-1', 'pinion-swing', 9),
  group('alignmentPinionCam', drive, 'dt-pinion-cam-[12]|dt-pinion-lift-rod-1|dt-pinion-cam-pin-[12]', 'pinion-cam', 5),
  group('alignmentPinionLever', drive, 'dt-pinion-lever-1|dt-pinion-lever-pin-1', 'pinion-lever', 2),
  // Knob shaft hardware turns about the knob axis; feed hardware about the disc stud.
  // The arm plate and its pressed MHA-PD-28 knob bush stay static (no binding).
  group('paperKnob', paper, '(?:pd-transgear-knob-shaft|pd-transgear-thumbnut|pd-transgear-drive-collar|pd-vn-transgear-collar-flat-pin|pd-transgear-knob-cup|pd-vn-transgear-knob-cup-screw|pd-transgear-knob-thrust-ring)-1|pd-vn-transgear-knob-drive-pin-[12]', 'paper-knob', 9),
  group('paperFeed', paper, '(?:pd-rack-pinion|pd-transgear-feed-pinion|pd-transgear-disc-hub|pd-vn-transgear-hub-key-pin)-1|pd-vn-transgear-disc-screw-[123]', 'paper-feed', 7),
  group('paperChain', paper, 'sh-vn-chain-link-\\d+|pd-vn-chain-connecting-link-1', 'chain-link', 66),
  group('paperSprockets', paper, 'pd-transgear-removable-[123]', 'paper-sprocket', 3),
]

/** Physical station number, not harmonic number (instance 1 is harmonic 20). */
export function instanceIndex(name: string, pattern: RegExp): number {
  const captured = name.match(pattern)?.[1]
  return captured ? Number.parseInt(captured, 10) : 0
}
