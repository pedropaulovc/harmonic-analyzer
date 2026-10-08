import representation from './content/model-representation.json' with { type: 'json' }
import { validateModelRepresentation } from './model-representation.mjs'

// Release authority remains the reviewed source/representation pair, not upstream metadata.
export const DEPLOYMENT_MODEL = validateModelRepresentation(representation)
if (DEPLOYMENT_MODEL.source.sourceCommit !== '81539e53f5146c06a77541415bd79da673806d96'
  || DEPLOYMENT_MODEL.source.sha256 !== '60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c') {
  throw new Error('Deployment model release association must be reviewed before changing the approved v39 source')
}
export const MODEL_RELEASE_URL = `https://github.com/pedropaulovc/harmonic-analyzer/releases/download/v39/ha-harmonic-analyzer-${DEPLOYMENT_MODEL.representation.sha256}.glb`
export const MODEL_ROUTE = `/${DEPLOYMENT_MODEL.representation.path}`
