/**
 * Analysis Presets for Community Forest Management System
 *
 * Defines preset combinations of analysis options to make it easier for users
 * to select common analysis configurations.
 */

export interface AnalysisOptions {
  // Master switches
  run_raster_analysis: boolean;

  // Raster analyses
  run_elevation: boolean;
  run_slope: boolean;
  run_aspect: boolean;
  run_canopy: boolean;
  run_biomass: boolean;
  run_forest_health: boolean;
  run_forest_type: boolean;
  run_landcover: boolean;
  run_forest_loss: boolean;
  run_forest_gain: boolean;
  run_fire_loss: boolean;
  run_temperature: boolean;
  run_precipitation: boolean;
  run_soil: boolean;

  // Vector analyses
  run_proximity: boolean;

  // Auto-generation
  auto_generate_fieldbook: boolean;
  auto_generate_sampling: boolean;
}

export interface MapOptions {
  generate_boundary_map: boolean;
  generate_topographic_map: boolean;
  generate_slope_map: boolean;
  generate_aspect_map: boolean;
  generate_forest_type_map: boolean;
  generate_canopy_height_map: boolean;
  generate_landcover_change_map: boolean;
  generate_soil_map: boolean;
  generate_forest_health_map: boolean;
}

export type PresetName = 'quick' | 'standard' | 'complete' | 'custom';

export interface AnalysisPreset {
  name: PresetName;
  label: string;
  description: string;
  estimatedTime: string;
  options: AnalysisOptions;
}

/**
 * Quick Preset - Essential analyses only
 * Estimated time: ~30 seconds
 * Use case: Quick overview, initial assessment
 */
export const QUICK_PRESET: AnalysisPreset = {
  name: 'quick',
  label: 'Quick',
  description: 'Essential analyses only - Elevation, Slope, Aspect, Administrative location',
  estimatedTime: '~30 seconds',
  options: {
    run_raster_analysis: true,
    run_elevation: true,
    run_slope: true,
    run_aspect: true,
    run_canopy: false,
    run_biomass: false,
    run_forest_health: false,
    run_forest_type: false,
    run_landcover: false,
    run_forest_loss: false,
    run_forest_gain: false,
    run_fire_loss: false,
    run_temperature: false,
    run_precipitation: false,
    run_soil: false,
    run_proximity: false,
    auto_generate_fieldbook: false,
    auto_generate_sampling: false,
  }
};

/**
 * Standard Preset - Most commonly used analyses
 * Estimated time: ~2 minutes
 * Use case: Regular forest assessments, CFOP preparation
 */
export const STANDARD_PRESET: AnalysisPreset = {
  name: 'standard',
  label: 'Standard',
  description: 'Most common analyses - Terrain, Forest structure, Land cover, Climate, Auto-fieldbook',
  estimatedTime: '~2 minutes',
  options: {
    run_raster_analysis: true,
    run_elevation: true,
    run_slope: true,
    run_aspect: true,
    run_canopy: true,
    run_biomass: true,
    run_forest_health: true,
    run_forest_type: true,
    run_landcover: true,
    run_forest_loss: false,
    run_forest_gain: false,
    run_fire_loss: false,
    run_temperature: false,
    run_precipitation: false,
    run_soil: true,
    run_proximity: false,
    auto_generate_fieldbook: true,
    auto_generate_sampling: false,
  }
};

/**
 * Complete Preset - All available analyses
 * Estimated time: ~5 minutes
 * Use case: Comprehensive assessments, research, detailed CFOP
 */
export const COMPLETE_PRESET: AnalysisPreset = {
  name: 'complete',
  label: 'Complete',
  description: 'All analyses including change detection, climate, proximity, and auto-sampling',
  estimatedTime: '~5 minutes',
  options: {
    run_raster_analysis: true,
    run_elevation: true,
    run_slope: true,
    run_aspect: true,
    run_canopy: true,
    run_biomass: true,
    run_forest_health: true,
    run_forest_type: true,
    run_landcover: true,
    run_forest_loss: true,
    run_forest_gain: true,
    run_fire_loss: true,
    run_temperature: true,
    run_precipitation: true,
    run_soil: true,
    run_proximity: true,
    auto_generate_fieldbook: true,
    auto_generate_sampling: true,
  }
};

/**
 * Custom Preset - User-defined selection
 * Allows manual selection of individual analyses
 */
export const CUSTOM_PRESET: AnalysisPreset = {
  name: 'custom',
  label: 'Custom',
  description: 'Select individual analyses manually',
  estimatedTime: 'Varies',
  options: {
    run_raster_analysis: true,
    run_elevation: true,
    run_slope: true,
    run_aspect: true,
    run_canopy: true,
    run_biomass: true,
    run_forest_health: true,
    run_forest_type: true,
    run_landcover: true,
    run_forest_loss: true,
    run_forest_gain: true,
    run_fire_loss: true,
    run_temperature: true,
    run_precipitation: true,
    run_soil: true,
    run_proximity: true,
    auto_generate_fieldbook: true,
    auto_generate_sampling: true,
  }
};

/**
 * All available presets
 */
export const ANALYSIS_PRESETS: AnalysisPreset[] = [
  QUICK_PRESET,
  STANDARD_PRESET,
  COMPLETE_PRESET,
  CUSTOM_PRESET,
];

/**
 * Get preset by name
 */
export function getPresetByName(name: PresetName): AnalysisPreset | undefined {
  return ANALYSIS_PRESETS.find(p => p.name === name);
}

/**
 * Default analysis options (all enabled for backward compatibility)
 */
export const DEFAULT_ANALYSIS_OPTIONS: AnalysisOptions = COMPLETE_PRESET.options;

/**
 * Default map options (all disabled for on-demand generation)
 */
export const DEFAULT_MAP_OPTIONS: MapOptions = {
  generate_boundary_map: false,
  generate_topographic_map: false,
  generate_slope_map: false,
  generate_aspect_map: false,
  generate_forest_type_map: false,
  generate_canopy_height_map: false,
  generate_landcover_change_map: false,
  generate_soil_map: false,
  generate_forest_health_map: false,
};

/**
 * Analysis option labels and descriptions for UI display
 */
export const ANALYSIS_OPTION_INFO: Record<keyof Omit<AnalysisOptions, 'run_raster_analysis' | 'auto_generate_fieldbook' | 'auto_generate_sampling'>, {label: string, description: string, category: string}> = {
  run_elevation: {
    label: 'Elevation (DEM)',
    description: 'Min, max, and mean elevation from digital elevation model',
    category: 'Terrain'
  },
  run_slope: {
    label: 'Slope',
    description: '4-class slope classification (Gentle, Moderate, Steep, Very Steep)',
    category: 'Terrain'
  },
  run_aspect: {
    label: 'Aspect',
    description: '8-directional aspect distribution (N, NE, E, SE, S, SW, W, NW)',
    category: 'Terrain'
  },
  run_canopy: {
    label: 'Canopy Height',
    description: 'Forest canopy structure classification (Open, Medium, Dense, Very Dense)',
    category: 'Forest Structure'
  },
  run_biomass: {
    label: 'Above-ground Biomass',
    description: 'Biomass and carbon stock estimation',
    category: 'Forest Structure'
  },
  run_forest_health: {
    label: 'Forest Health',
    description: '5-class forest health assessment',
    category: 'Forest Structure'
  },
  run_forest_type: {
    label: 'Forest Type',
    description: 'Species-based forest type classification',
    category: 'Classification'
  },
  run_landcover: {
    label: 'Land Cover',
    description: 'ESA WorldCover land cover classes',
    category: 'Classification'
  },
  run_forest_loss: {
    label: 'Forest Loss',
    description: 'Hansen forest loss detection by year',
    category: 'Change Detection'
  },
  run_forest_gain: {
    label: 'Forest Gain',
    description: 'Hansen forest gain detection',
    category: 'Change Detection'
  },
  run_fire_loss: {
    label: 'Fire Loss',
    description: 'Fire-related forest loss by year',
    category: 'Change Detection'
  },
  run_temperature: {
    label: 'Temperature',
    description: 'Annual mean temperature and minimum coldest month',
    category: 'Climate'
  },
  run_precipitation: {
    label: 'Precipitation',
    description: 'Annual precipitation',
    category: 'Climate'
  },
  run_soil: {
    label: 'Soil Texture',
    description: 'SoilGrids soil texture classification',
    category: 'Soil'
  },
  run_proximity: {
    label: 'Proximity Analysis',
    description: 'Distance to settlements, roads, and rivers',
    category: 'Vector'
  },
};

/**
 * Map type labels and descriptions for UI display
 */
export const MAP_TYPE_INFO: Record<keyof MapOptions, {label: string, description: string, implemented: boolean}> = {
  generate_boundary_map: {
    label: 'Boundary Map',
    description: 'Forest boundary with surrounding context',
    implemented: true
  },
  generate_topographic_map: {
    label: 'Topographic Map',
    description: 'Elevation contours and terrain visualization',
    implemented: false // TODO: Implement
  },
  generate_slope_map: {
    label: 'Slope Map',
    description: 'Slope classification (4 classes)',
    implemented: true
  },
  generate_aspect_map: {
    label: 'Aspect Map',
    description: 'Directional aspect distribution (8 directions)',
    implemented: true
  },
  generate_forest_type_map: {
    label: 'Forest Type Map',
    description: 'Species-based forest type classification',
    implemented: false // TODO: Implement
  },
  generate_canopy_height_map: {
    label: 'Canopy Height Map',
    description: 'Forest structure visualization (4 classes)',
    implemented: false // TODO: Implement
  },
  generate_landcover_change_map: {
    label: 'Land Cover Map',
    description: 'ESA WorldCover land cover classes',
    implemented: true
  },
  generate_soil_map: {
    label: 'Soil Map',
    description: 'Soil texture classification',
    implemented: false // TODO: Implement
  },
  generate_forest_health_map: {
    label: 'Forest Health Map',
    description: 'Forest health status visualization (5 classes)',
    implemented: false // TODO: Implement
  },
};
