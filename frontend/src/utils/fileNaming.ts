export function sanitizeFileName(name: string): string {
  if (!name) return 'UnknownForest';
  
  let sanitized = name.trim();
  
  sanitized = sanitized.replace(/\s+/g, '_');
  
  const invalidChars = /[<>:"/\\|?*\x00-\x1F]/g;
  sanitized = sanitized.replace(invalidChars, '');
  
  sanitized = sanitized.replace(/_{2,}/g, '_');
  
  sanitized = sanitized.replace(/^_|_$/g, '');
  
  return sanitized || 'UnknownForest';
}

export function generateExportFileName(
  forestName: string,
  contentType: string,
  extension: string
): string {
  const sanitizedForestName = sanitizeFileName(forestName);
  const today = new Date().toISOString().split('T')[0].replace(/-/g, '');
  const time = new Date().toTimeString().split(' ')[0].replace(/:/g, '');
  
  return `${sanitizedForestName}_${contentType}_${today}_${time}.${extension}`;
}

export function getDownloadAttribute(filename: string): string {
  return filename;
}

export const CONTENT_TYPES = {
  SAMPLING: 'SamplingDesign',
  TREE_MAPPING: 'TreeMapping',
  COMPARTMENT: 'Compartments',
  USER_GROUP_MAP: 'UserGroupMap',
  HOUSEHOLD_ANALYSIS: 'HouseholdAnalysis',
  TREE_MODEL: 'TreeModel',
  GRID: 'Grid',
  INVENTORY: 'Inventory',
  MAP: 'Map',
  SPECIES: 'SpeciesList',
} as const;

export type ContentType = typeof CONTENT_TYPES[keyof typeof CONTENT_TYPES];