import { MECHANISM_DATA as archivedMechanismData } from './mechanics-data'
import { projectCurrentNativeMetadata } from '../current-native-identity.mjs'

/**
 * Released v39 geometry/kinematics and their source/model/identity-map hashes stay
 * archived verbatim in mechanics-data.ts. Only native path metadata is projected
 * into the current parent-scoped naming used by runtime bindings. This is not a
 * geometry regeneration; numeric arrays and historical provenance are unchanged.
 */
export const MECHANISM_DATA = projectCurrentNativeMetadata(archivedMechanismData)
export { CURRENT_NATIVE_IDENTITY_PROJECTION } from '../current-native-identity.mjs'
