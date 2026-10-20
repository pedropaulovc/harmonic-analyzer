import { MECHANISM_DATA as archivedMechanismData } from './mechanics-data'
import { projectCurrentNativeMetadata } from '../current-native-identity.mjs'

/**
 * Released v39 geometry/kinematics and their source/model/identity-map hashes stay
 * archived verbatim in mechanics-data.ts. Only path metadata is projected into
 * current shared/member archive-role-local selectors used by runtime bindings,
 * not rebuilt-native Name2. Numeric arrays and historical provenance are unchanged.
 */
export const MECHANISM_DATA = projectCurrentNativeMetadata(archivedMechanismData)
export { CURRENT_NATIVE_IDENTITY_PROJECTION } from '../current-native-identity.mjs'
