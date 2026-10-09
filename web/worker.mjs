import manifest from './.vite/deployment-assets.json' with { type: 'json' }
import { createAssetWorker } from './deployment-asset-worker.mjs'

export default createAssetWorker(manifest)
