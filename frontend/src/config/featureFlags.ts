/**
 * Feature Flags for Forest Management System
 *
 * Usage:
 *   import { isUnifiedMappingEnabled } from '../config/featureFlags';
 *
 *   if (isUnifiedMappingEnabled()) {
 *     // New unified mapping UI
 *   } else {
 *     // Old UI
 *   }
 */

export const isUnifiedMappingEnabled = (): boolean => {
  return import.meta.env.VITE_USE_UNIFIED_MAPPING === 'true';
};

export const isFeatureEnabled = (flagName: string): boolean => {
  const envKey = `VITE_${flagName}`;
  return import.meta.env[envKey] === 'true';
};
