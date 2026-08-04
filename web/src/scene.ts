import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { BINDINGS, instanceIndex, type Binding } from './bindings'
import * as kin from './kinematics'

/** A joint resolved against the loaded scene graph, with its rest transform. */
interface Joint {
  binding: Binding
  nodes: THREE.Object3D[]
  restQuaternion: THREE.Quaternion[]
  restPosition: THREE.Vector3[]
}

export interface Machine {
  update(turns: number, amplitudes: readonly number[]): void
  missing: string[]
}

const MODEL_URL = 'models/harmonic-analyzer.glb'

export function createViewer(canvas: HTMLCanvasElement) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x11131a)

  const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 100)
  camera.position.set(1.2, 1.0, 1.6)

  const controls = new OrbitControls(camera, canvas)
  controls.enableDamping = true

  scene.add(new THREE.HemisphereLight(0xffffff, 0x404050, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(2, 3, 2)
  scene.add(key)

  function resize() {
    const { clientWidth: w, clientHeight: h } = canvas
    if (w === 0 || h === 0) return
    renderer.setSize(w, h, false)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
  }
  addEventListener('resize', resize)

  return { renderer, scene, camera, controls, resize }
}

/**
 * Load the exported machine and resolve every binding.
 *
 * Missing bindings are collected, not thrown: a re-export that renames one
 * component should degrade to "that joint doesn't move", never to a blank page.
 */
export async function loadMachine(scene: THREE.Scene): Promise<Machine> {
  const gltf = await new GLTFLoader().loadAsync(MODEL_URL)
  const root = gltf.scene
  scene.add(root)
  frame(root, scene)

  const joints: Joint[] = []
  const missing: string[] = []

  for (const binding of BINDINGS) {
    const nodes: THREE.Object3D[] = []
    root.traverse((o) => {
      if (binding.pattern.test(o.name)) nodes.push(o)
    })
    if (binding.kind === 'indexed') {
      nodes.sort(
        (a, b) => instanceIndex(a.name, binding.pattern) - instanceIndex(b.name, binding.pattern),
      )
    }
    if (nodes.length === 0) {
      missing.push(`${binding.id} (${binding.pattern})`)
      continue
    }
    joints.push({
      binding,
      nodes,
      restQuaternion: nodes.map((n) => n.quaternion.clone()),
      restPosition: nodes.map((n) => n.position.clone()),
    })
  }

  if (missing.length > 0) {
    console.warn(
      `[machine] ${missing.length} binding(s) did not resolve; those joints stay static:\n` +
        missing.map((m) => `  - ${m}`).join('\n') +
        '\nSee src/bindings.ts — the node names come from the SolidWorks component instances.',
    )
  }

  const axis = new THREE.Vector3()
  const q = new THREE.Quaternion()

  function drive(joint: Joint, i: number, value: number) {
    const node = joint.nodes[i]
    const restQ = joint.restQuaternion[i]
    const restP = joint.restPosition[i]
    if (!node || !restQ || !restP) return
    axis.fromArray(joint.binding.axis)
    if (joint.binding.motion === 'rotate') {
      node.quaternion.copy(restQ).multiply(q.setFromAxisAngle(axis, value))
    } else {
      node.position.copy(restP).addScaledVector(axis, value)
    }
  }

  function update(turns: number, amplitudes: readonly number[]) {
    const sum = kin.output(turns, amplitudes)
    for (const joint of joints) {
      switch (joint.binding.id) {
        case 'crank':
          drive(joint, 0, turns * 2 * Math.PI)
          break
        case 'coneGears':
          // 4:1 reduction from the crank: one turn = a quarter revolution.
          joint.nodes.forEach((_, i) => drive(joint, i, (turns * Math.PI) / 2))
          break
        case 'cylinderGears':
        case 'rockerArms':
        case 'connectingRods':
        case 'channelLevers':
          joint.nodes.forEach((_, i) => {
            const k = i + 1
            const scale = joint.binding.motion === 'rotate' ? 1 : 0.008
            const v =
              joint.binding.id === 'cylinderGears'
                ? kin.channelAngle(turns, k)
                : kin.rockerDisplacement(turns, k) * scale * ((amplitudes[i] ?? 0) / 10)
            drive(joint, i, v)
          })
          break
        case 'summingLever':
          drive(joint, 0, sum * 0.0004)
          break
        case 'magnifyingLever':
          drive(joint, 0, sum * 0.0016)
          break
        case 'magnifyingWheel':
          drive(joint, 0, kin.wheelAngle(sum * 0.05))
          break
        case 'penRod':
          drive(joint, 0, sum * 0.002)
          break
        case 'platen':
          drive(joint, 0, kin.platenPosition(turns, 'medium-medium') * 0.2)
          break
      }
    }
  }

  return { update, missing }
}

/** Fit the camera-facing group to the origin so orbiting behaves. */
function frame(object: THREE.Object3D, scene: THREE.Scene) {
  const box = new THREE.Box3().setFromObject(object)
  const centre = box.getCenter(new THREE.Vector3())
  object.position.sub(centre)
  scene.userData.size = box.getSize(new THREE.Vector3()).length()
}
