import React, { useState, useMemo } from 'react';
import { TileLayer } from 'react-leaflet';

interface LegendItem {
  color: string;
  label: string;
  range?: string;
}

// --- HELPER FUNCTION ---
// This ensures "Stressed ", "stressed", and "Stressed" all map to the exact same hex code
// Prevents grey boxes from case sensitivity or trailing space issues
const getNormalizedColor = (
  colorMap: Record<string, string>,
  key: string,
  fallback: string = '#CCCCCC' // Grey fallback for missing data
): string => {
  if (!key) return fallback;

  // Clean the incoming key
  const normalizedKey = String(key).trim().toLowerCase();

  // Create a lowercase version of the dictionary keys for safe comparison
  const normalizedMap = Object.entries(colorMap).reduce((acc, [k, v]) => {
    acc[k.toLowerCase()] = v;
    return acc;
  }, {} as Record<string, string>);

  return normalizedMap[normalizedKey] || fallback;
};

// Function to generate dynamic elevation legend based on actual min/max values
function generateDynamicElevationLegend(minElev: number, maxElev: number): LegendItem[] {
  // Round to nearest 10 for cleaner values
  const min = Math.floor(minElev / 10) * 10;
  const max = Math.ceil(maxElev / 10) * 10;
  const range = max - min;

  // If range is very small (< 100m), use finer divisions
  if (range < 100) {
    const quarter = range / 4;
    return [
      { color: '#D2691E', label: 'Low', range: `${min.toFixed(0)}-${(min + quarter).toFixed(0)}m` },
      { color: '#FFA500', label: 'Medium-Low', range: `${(min + quarter).toFixed(0)}-${(min + 2*quarter).toFixed(0)}m` },
      { color: '#90EE90', label: 'Medium-High', range: `${(min + 2*quarter).toFixed(0)}-${(min + 3*quarter).toFixed(0)}m` },
      { color: '#4682B4', label: 'High', range: `${(min + 3*quarter).toFixed(0)}-${max.toFixed(0)}m` }
    ];
  }

  // Standard 4-class division for larger ranges
  const quarter = range / 4;
  return [
    { color: '#8B4513', label: 'Low', range: `${min.toFixed(0)}-${(min + quarter).toFixed(0)}m` },
    { color: '#FFA500', label: 'Medium-Low', range: `${(min + quarter).toFixed(0)}-${(min + 2*quarter).toFixed(0)}m` },
    { color: '#7FFF00', label: 'Medium-High', range: `${(min + 2*quarter).toFixed(0)}-${(min + 3*quarter).toFixed(0)}m` },
    { color: '#87CEEB', label: 'High', range: `${(min + 3*quarter).toFixed(0)}-${max.toFixed(0)}m` }
  ];
}

// Function to generate dynamic canopy height legend based on ABSOLUTE ecological thresholds
// Only shows classes that actually exist in the forest
function generateDynamicCanopyLegend(minHeight: number, maxHeight: number): LegendItem[] {
  // Absolute ecological thresholds (based on forestry science)
  const ecologicalClasses = [
    { minH: 0, maxH: 5, color: '#DC143C', label: 'Sparse/Regeneration', range: '0-5m' },        // Crimson Red
    { minH: 5, maxH: 15, color: '#FF8C00', label: 'Young Forest', range: '5-15m' },             // Dark Orange
    { minH: 15, maxH: 30, color: '#90EE90', label: 'Mature Forest', range: '15-30m' },          // Light Green
    { minH: 30, maxH: 1000, color: '#228B22', label: 'Old Growth', range: '>30m' }              // Forest Green
  ];

  // Filter to show ONLY classes that overlap with actual min/max canopy in this forest
  const relevantClasses = ecologicalClasses.filter(cls => {
    // A class is relevant if it overlaps with [minHeight, maxHeight]
    return cls.maxH > minHeight && cls.minH < maxHeight;
  });

  // If no classes match (edge case), return a single generic class
  if (relevantClasses.length === 0) {
    const minVal = minHeight != null ? minHeight.toFixed(1) : 'N/A';
    const maxVal = maxHeight != null ? maxHeight.toFixed(1) : 'N/A';
    return [
      { color: '#228B22', label: 'Forest Canopy', range: `${minVal}-${maxVal}m` }
    ];
  }

  return relevantClasses.map(cls => ({
    color: cls.color,
    label: cls.label,
    range: cls.range
  }));
}

// Function to generate dynamic temperature legend based on actual min/max values
// Only shows temperature classes that actually exist in the forest
function generateDynamicTemperatureLegend(minTemp: number, maxTemp: number): LegendItem[] {
  // Absolute temperature classification (based on Nepal climate zones)
  const temperatureClasses = [
    { minT: -100, maxT: 0, color: '#0000FF', label: 'Very Cold', range: '< 0°C' },          // Blue
    { minT: 0, maxT: 10, color: '#00BFFF', label: 'Cold', range: '0-10°C' },               // Deep Sky Blue
    { minT: 10, maxT: 20, color: '#90EE90', label: 'Moderate', range: '10-20°C' },         // Light Green
    { minT: 20, maxT: 25, color: '#FFD700', label: 'Warm', range: '20-25°C' },             // Gold
    { minT: 25, maxT: 100, color: '#FF4500', label: 'Hot', range: '> 25°C' }               // Orange Red
  ];

  // Filter to show ONLY classes that overlap with actual min/max temperature in this forest
  const relevantClasses = temperatureClasses.filter(cls => {
    return cls.maxT > minTemp && cls.minT < maxTemp;
  });

  // If no classes match (edge case), return a single generic class
  if (relevantClasses.length === 0) {
    const minVal = minTemp != null ? minTemp.toFixed(1) : 'N/A';
    const maxVal = maxTemp != null ? maxTemp.toFixed(1) : 'N/A';
    return [
      { color: '#90EE90', label: 'Temperature', range: `${minVal}-${maxVal}°C` }
    ];
  }

  return relevantClasses.map(cls => ({
    color: cls.color,
    label: cls.label,
    range: cls.range
  }));
}

// Function to generate dynamic precipitation legend based on actual min/max values
// Only shows precipitation classes that actually exist in the forest
function generateDynamicPrecipitationLegend(minPrecip: number, maxPrecip: number): LegendItem[] {
  // Absolute precipitation classification (based on Nepal climate zones)
  const precipClasses = [
    { minP: 0, maxP: 500, color: '#8B4513', label: 'Very Dry', range: '< 500mm' },         // Saddle Brown
    { minP: 500, maxP: 1000, color: '#D2B48C', label: 'Dry', range: '500-1000mm' },        // Tan
    { minP: 1000, maxP: 2000, color: '#90EE90', label: 'Moderate', range: '1000-2000mm' }, // Light Green
    { minP: 2000, maxP: 3000, color: '#4169E1', label: 'Wet', range: '2000-3000mm' },      // Royal Blue
    { minP: 3000, maxP: 10000, color: '#0000CD', label: 'Very Wet', range: '> 3000mm' }    // Medium Blue
  ];

  // Filter to show ONLY classes that overlap with actual min/max precipitation in this forest
  const relevantClasses = precipClasses.filter(cls => {
    return cls.maxP > minPrecip && cls.minP < maxPrecip;
  });

  // If no classes match (edge case), return a single generic class
  if (relevantClasses.length === 0) {
    const minVal = minPrecip != null ? minPrecip.toFixed(0) : 'N/A';
    const maxVal = maxPrecip != null ? maxPrecip.toFixed(0) : 'N/A';
    return [
      { color: '#90EE90', label: 'Precipitation', range: `${minVal}-${maxVal}mm` }
    ];
  }

  return relevantClasses.map(cls => ({
    color: cls.color,
    label: cls.label,
    range: cls.range
  }));
}

// Function to generate dynamic biomass legend based on actual min/max values
// Only shows biomass classes that actually exist in the forest
function generateDynamicBiomassLegend(minBiomass: number, maxBiomass: number): LegendItem[] {
  // Absolute biomass classification (based on forestry standards)
  const biomassClasses = [
    { minB: 0, maxB: 50, color: '#DC143C', label: 'Very Low', range: '0-50 Mg/ha' },      // Crimson Red
    { minB: 50, maxB: 100, color: '#FFD700', label: 'Low', range: '50-100 Mg/ha' },       // Gold
    { minB: 100, maxB: 200, color: '#90EE90', label: 'Medium', range: '100-200 Mg/ha' },  // Light Green
    { minB: 200, maxB: 300, color: '#228B22', label: 'High', range: '200-300 Mg/ha' },    // Forest Green
    { minB: 300, maxB: 10000, color: '#1E90FF', label: 'Very High', range: '>300 Mg/ha' } // Dodger Blue
  ];

  // Filter to show ONLY classes that overlap with actual min/max biomass in this forest
  const relevantClasses = biomassClasses.filter(cls => {
    return cls.maxB > minBiomass && cls.minB < maxBiomass;
  });

  // If no classes match (edge case), return a single generic class
  if (relevantClasses.length === 0) {
    const minVal = minBiomass != null ? minBiomass.toFixed(0) : 'N/A';
    const maxVal = maxBiomass != null ? maxBiomass.toFixed(0) : 'N/A';
    return [
      { color: '#90EE90', label: 'Biomass', range: `${minVal}-${maxVal} Mg/ha` }
    ];
  }

  return relevantClasses.map(cls => ({
    color: cls.color,
    label: cls.label,
    range: cls.range
  }));
}

// Function to generate dynamic slope legend based on which slope codes are present
// Only shows slope classes that actually exist in the forest
function generateDynamicSlopeLegend(minCode: number, maxCode: number): LegendItem[] {
  // Slope classes (categorical codes)
  const slopeClasses = [
    { code: 1, color: '#2ECC71', label: 'Gentle', range: '0-19°' },           // Green
    { code: 2, color: '#F1C40F', label: 'Moderate', range: '19-30°' },         // Yellow
    { code: 3, color: '#E67E22', label: 'Highly Steep', range: '30-45°' },    // Orange
    { code: 4, color: '#E74C3C', label: 'Extreme', range: '>45°' }             // Red
  ];

  // Filter to show ONLY codes that exist in the forest (minCode <= code <= maxCode)
  const relevantClasses = slopeClasses.filter(cls => {
    return cls.code >= minCode && cls.code <= maxCode;
  });

  // If no classes match (edge case), return all classes as fallback
  if (relevantClasses.length === 0) {
    return slopeClasses;
  }

  return relevantClasses.map(cls => ({
    color: cls.color,
    label: cls.label,
    range: cls.range
  }));
}

// Function to generate dynamic min temperature (coldest month) legend
// Only shows temperature classes that actually exist in the forest
function generateDynamicMinTempColdestLegend(minTemp: number, maxTemp: number): LegendItem[] {
  // Absolute temperature classification for coldest month
  const tempClasses = [
    { minT: -100, maxT: -10, color: '#0000CD', label: 'Extreme Cold', range: '< -10°C' },      // Medium Blue
    { minT: -10, maxT: 0, color: '#4169E1', label: 'Very Cold', range: '-10 to 0°C' },        // Royal Blue
    { minT: 0, maxT: 5, color: '#87CEEB', label: 'Cold', range: '0 to 5°C' },                 // Sky Blue
    { minT: 5, maxT: 10, color: '#90EE90', label: 'Cool', range: '5 to 10°C' },               // Light Green
    { minT: 10, maxT: 15, color: '#FFD700', label: 'Mild', range: '10 to 15°C' },             // Gold
    { minT: 15, maxT: 100, color: '#FF8C00', label: 'Warm', range: '> 15°C' }                 // Dark Orange
  ];

  // Filter to show ONLY classes that overlap with actual min/max temperature in this forest
  const relevantClasses = tempClasses.filter(cls => {
    return cls.maxT > minTemp && cls.minT < maxTemp;
  });

  // If no classes match (edge case), return a single generic class
  if (relevantClasses.length === 0) {
    const minVal = minTemp != null ? minTemp.toFixed(1) : 'N/A';
    const maxVal = maxTemp != null ? maxTemp.toFixed(1) : 'N/A';
    return [
      { color: '#87CEEB', label: 'Min Temperature', range: `${minVal}-${maxVal}°C` }
    ];
  }

  return relevantClasses.map(cls => ({
    color: cls.color,
    label: cls.label,
    range: cls.range
  }));
}

// Function to generate dynamic land cover legend - only shows classes present in the data
function generateDynamicLandcoverLegend(landcoverPercentages: Record<string, number>): LegendItem[] {
  const landcoverColors: Record<string, string> = {
    'Tree cover': '#006400',
    'Shrubland': '#FFBB22',
    'Grassland': '#FFFF4C',
    'Cropland': '#F096FF',
    'Built-up': '#FA0000',
    'Bare/sparse vegetation': '#B4B4B4',
    'Snow and ice': '#F0F0F0',
    'Permanent water bodies': '#0064C8',
    'Herbaceous wetland': '#0096A0',
    'Mangroves': '#00CF75',
    'Moss and lichen': '#FAE6A0'
  };

  const landcoverCodes: Record<string, string> = {
    'Tree cover': '10',
    'Shrubland': '20',
    'Grassland': '30',
    'Cropland': '40',
    'Built-up': '50',
    'Bare/sparse vegetation': '60',
    'Snow and ice': '70',
    'Permanent water bodies': '80',
    'Herbaceous wetland': '90',
    'Mangroves': '95',
    'Moss and lichen': '100'
  };

  if (!landcoverPercentages || Object.keys(landcoverPercentages).length === 0) {
    return []; // Return empty if no data
  }

  // Generate legend items only for classes present in the data
  return Object.entries(landcoverPercentages)
    .filter(([_, percentage]) => percentage > 0)
    .sort((a, b) => b[1] - a[1]) // Sort by percentage descending
    .map(([className, percentage]) => ({
      color: landcoverColors[className] || '#808080',
      label: className,
      range: `${landcoverCodes[className] || '?'} (${percentage.toFixed(1)}%)`
    }));
}

// Function to generate dynamic NASA Forest 2020 legend - only shows classes present
// FIXED: Works like slope - colors embedded directly, no dictionary lookup
function generateDynamicNasaForestLegend(nasaPercentages: Record<string, number>): LegendItem[] {
  // Define classes with colors embedded directly (like slope layer)
  const nasaClasses = [
    {
      name: 'Primary Forest',
      color: '#00FF00',
      description: 'Class 1 - Old-growth, highest carbon',
      aliases: ['primary forest', 'Primary Forest', 'PRIMARY FOREST']
    },
    {
      name: 'Young Secondary Forest',
      color: '#FF0000',
      description: 'Class 2 - Regenerating, low carbon',
      aliases: ['young secondary forest', 'Young Secondary Forest', 'YOUNG SECONDARY FOREST']
    },
    {
      name: 'Old Secondary Forest',
      color: '#6666FF',
      description: 'Class 3 - Mature regrowth, medium carbon',
      aliases: ['old secondary forest', 'Old Secondary Forest', 'OLD SECONDARY FOREST']
    }
  ];

  if (!nasaPercentages || Object.keys(nasaPercentages).length === 0) {
    return []; // Return empty if no data
  }

  // Match incoming data to classes and return with colors directly
  const legendItems: LegendItem[] = [];

  for (const [className, percentage] of Object.entries(nasaPercentages)) {
    if (percentage > 0) {
      // Find matching class by checking aliases (case-insensitive)
      const matchedClass = nasaClasses.find(cls =>
        cls.aliases.some(alias => alias.toLowerCase() === className.toLowerCase())
      );

      if (matchedClass) {
        legendItems.push({
          color: matchedClass.color,  // Direct access - no lookup!
          label: className,
          range: `${matchedClass.description} (${percentage.toFixed(1)}%)`
        });
      }
    }
  }

  // Sort by percentage descending
  return legendItems.sort((a, b) => {
    const aPercent = parseFloat(a.range.match(/\(([\d.]+)%\)/)?.[1] || '0');
    const bPercent = parseFloat(b.range.match(/\(([\d.]+)%\)/)?.[1] || '0');
    return bPercent - aPercent;
  });
}

// Function to generate dynamic aspect legend - only shows directions present
function generateDynamicAspectLegend(aspectPercentages: Record<string, number>): LegendItem[] {
  const aspectColors: Record<string, string> = {
    'Flat': '#CCCCCC',
    'N': '#1A5490',
    'NE': '#3498DB',
    'E': '#1ABC9C',
    'SE': '#F1C40F',
    'S': '#E74C3C',
    'SW': '#E67E22',
    'W': '#F39C12',
    'NW': '#9B59B6'
  };

  const aspectLabels: Record<string, string> = {
    'Flat': 'Flat',
    'N': 'North (N)',
    'NE': 'Northeast (NE)',
    'E': 'East (E)',
    'SE': 'Southeast (SE)',
    'S': 'South (S)',
    'SW': 'Southwest (SW)',
    'W': 'West (W)',
    'NW': 'Northwest (NW)'
  };

  if (!aspectPercentages || Object.keys(aspectPercentages).length === 0) {
    return []; // Return empty if no data
  }

  // Generate legend items only for directions present in the data
  return Object.entries(aspectPercentages)
    .filter(([_, percentage]) => percentage > 0)
    .sort((a, b) => {
      // Sort by compass order: Flat, N, NE, E, SE, S, SW, W, NW
      const order = ['Flat', 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
      return order.indexOf(a[0]) - order.indexOf(b[0]);
    })
    .map(([direction, percentage]) => ({
      color: aspectColors[direction] || '#808080',
      label: aspectLabels[direction] || direction,
      range: `${percentage.toFixed(1)}%`
    }));
}

// Function to generate dynamic forest health legend - only shows health classes present
// FIXED: Works like slope - colors embedded directly, no dictionary lookup
function generateDynamicForestHealthLegend(healthPercentages: Record<string, number>): LegendItem[] {
  // Define classes with colors embedded directly (like slope layer)
  // EXACT hex equivalents of RGB tuples in tile_service.py
  const healthClasses = [
    {
      name: 'Stressed',
      color: '#DC143C',  // RGB(220, 20, 60)
      range: 'NDVI < 0.2',
      order: 1,
      aliases: ['stressed', 'Stressed', 'STRESSED']
    },
    {
      name: 'Poor',
      color: '#FF8C00',  // RGB(255, 140, 0)
      range: 'NDVI 0.2-0.4',
      order: 2,
      aliases: ['poor', 'Poor', 'POOR']
    },
    {
      name: 'Moderate',
      color: '#FFD700',  // RGB(255, 215, 0)
      range: 'NDVI 0.4-0.6',
      order: 3,
      aliases: ['moderate', 'Moderate', 'MODERATE']
    },
    {
      name: 'Healthy',
      color: '#90EE90',  // RGB(144, 238, 144)
      range: 'NDVI 0.6-0.8',
      order: 4,
      aliases: ['healthy', 'Healthy', 'HEALTHY']
    },
    {
      name: 'Excellent',
      color: '#228B22',  // RGB(34, 139, 34)
      range: 'NDVI > 0.8',
      order: 5,
      aliases: ['excellent', 'Excellent', 'EXCELLENT']
    }
  ];

  if (!healthPercentages || Object.keys(healthPercentages).length === 0) {
    return []; // Return empty if no data
  }

  // Match incoming data to classes and return with colors directly
  const legendItems: LegendItem[] = [];

  for (const [healthClass, percentage] of Object.entries(healthPercentages)) {
    if (percentage > 0) {
      // Find matching class by checking aliases (case-insensitive)
      const matchedClass = healthClasses.find(cls =>
        cls.aliases.some(alias => alias.toLowerCase() === healthClass.toLowerCase())
      );

      if (matchedClass) {
        legendItems.push({
          color: matchedClass.color,  // Direct access - no lookup!
          label: healthClass,
          range: `${matchedClass.range} (${percentage.toFixed(1)}%)`,
          __order: matchedClass.order  // For sorting
        } as any);
      }
    }
  }

  // Sort by health order: Stressed → Excellent
  return legendItems.sort((a: any, b: any) => a.__order - b.__order);
}

// Function to generate dynamic forest type legend - only shows types present in data
// FIXED: Works like slope - colors embedded directly, no dictionary lookup
function generateDynamicForestTypeLegend(forestTypePercentages: Record<string, number>): LegendItem[] {
  // Define all 26 forest types with colors embedded directly (like slope layer)
  const forestTypeClasses = [
    // Tropical Zone (1-5): Dark Green shades
    { name: 'Shorea robusta Forest', color: '#006400' },
    { name: 'Alnus nepalensis Forest', color: '#0B7A0B' },
    { name: 'Schima-Castanopsis Forest', color: '#118F11' },
    { name: 'Quercus semecarpifolia Forest', color: '#17A517' },
    { name: 'Larix/Abies spectabilis Forest', color: '#1DBB1D' },

    // Sub-tropical Zone (6-10): Yellow-Green shades
    { name: 'Pinus wallichiana-Tsuga dumosa Forest', color: '#9ACD32' },
    { name: 'Plantation (Pinus-Eucalyptus) Forest', color: '#A4D73C' },
    { name: 'Ficus-Other Tropical Riverine Forest', color: '#AEE146' },
    { name: 'Tropical Mixed Broadleaved Forest', color: '#B8EB50' },
    { name: 'Quercus-Pinus Forest', color: '#C2F55A' },

    // Temperate Zone (11-15): Blue-Green shades
    { name: 'Abies spectabilis Forest', color: '#2E8B57' },
    { name: 'Pinus roxburghii-Mixed Broadleaved Forest', color: '#349B61' },
    { name: 'Pinus wallichiana Forest', color: '#3AAB6B' },
    { name: 'Warm Temperate Mixed Broadleaved Forest', color: '#40BB75' },
    { name: 'Upper Temperate Quercus Forest', color: '#46CB7F' },

    // Sub-alpine Zone (16-20): Purple-Blue shades
    { name: 'Rhododendron arboreum Forest', color: '#6A5ACD' },
    { name: 'Temperate Rhododendron Mixed Broadleaved Forest', color: '#7565D4' },
    { name: 'Dalbergia sissoo-Senegelia catechu Forest', color: '#8070DB' },
    { name: 'Terminalia-Tropical Mixed Broadleaved Forest', color: '#8B7BE2' },
    { name: 'Temperate Mixed Broadleaved Forest', color: '#9686E9' },

    // Alpine Zone (21-25): Brown-Red shades
    { name: 'Tropical Deciduous Indigenous Riverine Forest', color: '#8B4513' },
    { name: 'Tropical Riverine Forest', color: '#9B5923' },
    { name: 'Lower Temperate Mixed robusta Forest', color: '#AB6D33' },
    { name: 'Pinus roxburghii-Shorea robusta Forest', color: '#BB8143' },
    { name: 'Lower Temperate Pinus roxburghii-Quercus Forest', color: '#CB9553' },

    // Special (26)
    { name: 'Data Not Available', color: '#BDBDBD' }
  ];

  if (!forestTypePercentages || Object.keys(forestTypePercentages).length === 0) {
    return []; // Return empty if no data
  }

  // DEBUG: Log what forest types we received
  console.log('[Forest Type Legend] Received data:', forestTypePercentages);

  // Match incoming data to classes and return with colors directly
  const legendItems: LegendItem[] = [];

  for (const [typeName, percentage] of Object.entries(forestTypePercentages)) {
    if (percentage > 0) {
      // Try matching with flexible name matching:
      // Backend might send "Shorea robusta" or "Shorea robusta Forest"
      let matchedClass = forestTypeClasses.find(cls =>
        cls.name.toLowerCase() === typeName.toLowerCase()
      );

      // If no match, try adding " Forest" suffix
      if (!matchedClass) {
        const typeNameWithForest = typeName.endsWith(' Forest') || typeName.endsWith(' forest')
          ? typeName
          : typeName + ' Forest';
        matchedClass = forestTypeClasses.find(cls =>
          cls.name.toLowerCase() === typeNameWithForest.toLowerCase()
        );
      }

      // If still no match, try removing " Forest" suffix from class name
      if (!matchedClass) {
        const typeNameWithoutForest = typeName.replace(' Forest', '').replace(' forest', '');
        matchedClass = forestTypeClasses.find(cls =>
          cls.name.replace(' Forest', '').replace(' forest', '').toLowerCase() === typeNameWithoutForest.toLowerCase()
        );
      }

      if (matchedClass) {
        console.log(`[Forest Type] Matched "${typeName}" -> color ${matchedClass.color}`);
        legendItems.push({
          color: matchedClass.color,  // Direct access - no lookup!
          label: typeName.replace(' Forest', '').replace(' forest', ''),  // Shorten label
          range: `${percentage.toFixed(1)}%`
        });
      } else {
        // FALLBACK: If no match found, still show it with a default color
        console.warn(`Forest type "${typeName}" not found in color map, using fallback grey`);
        legendItems.push({
          color: '#808080',  // Grey fallback
          label: typeName.replace(' Forest', '').replace(' forest', ''),
          range: `${percentage.toFixed(1)}%`
        });
      }
    }
  }

  // Sort by percentage descending
  return legendItems.sort((a, b) => {
    const aPercent = parseFloat(a.range) || 0;
    const bPercent = parseFloat(b.range) || 0;
    return bPercent - aPercent;
  });
}

// Function to generate dynamic fire loss legend - shows years with fire activity
function generateDynamicFireLossLegend(fireByYear: Record<string, number>): LegendItem[] {
  if (!fireByYear || Object.keys(fireByYear).length === 0) {
    return []; // Return empty if no data
  }

  // Group years into time periods
  const periods = [
    { label: '2001-2008', color: '#FF8C00', years: Array.from({length: 8}, (_, i) => String(2001 + i)), hectares: 0 },
    { label: '2009-2016', color: '#FF4500', years: Array.from({length: 8}, (_, i) => String(2009 + i)), hectares: 0 },
    { label: '2017-2024', color: '#8B0000', years: Array.from({length: 8}, (_, i) => String(2017 + i)), hectares: 0 }
  ];

  // Sum hectares for each period
  for (const [year, hectares] of Object.entries(fireByYear)) {
    for (const period of periods) {
      if (period.years.includes(year)) {
        period.hectares += hectares;
      }
    }
  }

  // Return legend items only for periods with fire activity
  return periods
    .filter(p => p.hectares > 0)
    .map(p => ({
      color: p.color,
      label: p.label,
      range: `${p.hectares.toFixed(2)} ha`
    }));
}

// Function to generate dynamic soil pH legend - shows ONLY the active pH category
function generateDynamicSoilPHLegend(soilData: any): LegendItem[] {
  const categories = [
    { color: '#DC143C', label: 'Extremely Acidic', range: '< 4.5', min: 0, max: 4.5 },
    { color: '#FF8C00', label: 'Strongly Acidic', range: '4.5-5.5', min: 4.5, max: 5.5 },
    { color: '#FFD700', label: 'Slightly Acidic', range: '5.5-6.5', min: 5.5, max: 6.5 },
    { color: '#228B22', label: 'Neutral (Optimal)', range: '6.5-7.5', min: 6.5, max: 7.5 },
    { color: '#4682B4', label: 'Slightly Alkaline', range: '7.5-8.5', min: 7.5, max: 8.5 },
    { color: '#9370DB', label: 'Strongly Alkaline', range: '> 8.5', min: 8.5, max: 14 }
  ];

  const phValue = soilData?.soil_properties?.ph_h2o;

  if (phValue === null || phValue === undefined) {
    return []; // Return empty if no data
  }

  // Find and return ONLY the active category
  const activeCategory = categories.find(c => phValue >= c.min && phValue < c.max);

  if (!activeCategory) return [];

  return [{
    color: activeCategory.color,
    label: activeCategory.label,
    range: `${activeCategory.range} (pH ${phValue.toFixed(1)})`
  }];
}

// Function to generate dynamic soil texture legend - shows ONLY the active texture
function generateDynamicSoilTextureLegend(soilData: any): LegendItem[] {
  const categories = [
    { color: '#654321', label: 'Clay', range: 'Heavy', keywords: ['clay'] },
    { color: '#8B4513', label: 'Clay Loam', range: 'Moderate', keywords: ['clay loam'] },
    { color: '#A0522D', label: 'Loam (Optimal)', range: 'Balanced', keywords: ['loam', 'silt loam', 'sandy loam'] },
    { color: '#D2B48C', label: 'Sandy', range: 'Light', keywords: ['sand', 'sandy'] }
  ];

  const texture = soilData?.soil_texture?.toLowerCase();

  if (!texture) {
    return []; // Return empty if no data
  }

  // Find and return ONLY the active category
  const activeCategory = categories.find(c => c.keywords.some(keyword => texture.includes(keyword)));

  if (!activeCategory) return [];

  return [{
    color: activeCategory.color,
    label: activeCategory.label,
    range: `${activeCategory.range} (${soilData.soil_texture})`
  }];
}

// Function to generate dynamic soil carbon legend - shows ONLY the active carbon category
function generateDynamicSoilCarbonLegend(soilData: any): LegendItem[] {
  const categories = [
    { color: '#DC143C', label: 'Very Low', range: '< 0.5%', max: 0.5 },
    { color: '#FF8C00', label: 'Low', range: '0.5-1.0%', min: 0.5, max: 1.0 },
    { color: '#FFD700', label: 'Medium', range: '1.0-2.0%', min: 1.0, max: 2.0 },
    { color: '#90EE90', label: 'High', range: '2.0-3.0%', min: 2.0, max: 3.0 },
    { color: '#228B22', label: 'Very High (Forest)', range: '> 3.0%', min: 3.0 }
  ];

  // Use actual SOC percentage from soil_properties instead of converting carbon stock
  const socValue = soilData?.soil_properties?.soc_dg_kg;

  if (socValue === null || socValue === undefined) {
    return []; // Return empty if no data
  }

  // Convert SOC from dg/kg to percentage (same as backend: 1 dg/kg = 0.1%)
  const socPercent = socValue > 10 ? socValue / 10.0 : socValue;

  // Find and return ONLY the active category
  const activeCategory = categories.find(c => {
    if (c.max !== undefined && c.min !== undefined) {
      return socPercent >= c.min && socPercent < c.max;
    } else if (c.max !== undefined) {
      return socPercent < c.max;
    } else if (c.min !== undefined) {
      return socPercent >= c.min;
    }
    return false;
  });

  if (!activeCategory) return [];

  return [{
    color: activeCategory.color,
    label: activeCategory.label,
    range: `${activeCategory.range} (${socPercent.toFixed(1)}% SOC)`
  }];
}

// Function to generate dynamic soil fertility legend - shows ONLY the active fertility category
function generateDynamicSoilFertilityLegend(soilData: any): LegendItem[] {
  const categories = [
    { color: '#DC143C', label: 'Very Low', range: '0-20', min: 0, max: 20 },
    { color: '#FF8C00', label: 'Low', range: '20-40', min: 20, max: 40 },
    { color: '#FFD700', label: 'Medium', range: '40-60', min: 40, max: 60 },
    { color: '#90EE90', label: 'High', range: '60-80', min: 60, max: 80 },
    { color: '#228B22', label: 'Very High', range: '80-100', min: 80, max: 100 }
  ];

  const fertilityScore = soilData?.fertility_score;

  if (fertilityScore === null || fertilityScore === undefined) {
    return []; // Return empty if no data
  }

  // Find and return ONLY the active category
  const activeCategory = categories.find(c => fertilityScore >= c.min && fertilityScore <= c.max);

  if (!activeCategory) return [];

  return [{
    color: activeCategory.color,
    label: activeCategory.label,
    range: `${activeCategory.range} (Score: ${fertilityScore})`
  }];
}

// Function to generate dynamic soil density legend - shows ONLY the active density category
function generateDynamicSoilDensityLegend(soilData: any): LegendItem[] {
  const categories = [
    { color: '#228B22', label: 'Low (Good)', range: '< 1.2 g/cm³', max: 1.2 },
    { color: '#FFD700', label: 'Moderate', range: '1.2-1.4 g/cm³', min: 1.2, max: 1.4 },
    { color: '#FF8C00', label: 'Elevated', range: '1.4-1.6 g/cm³', min: 1.4, max: 1.6 },
    { color: '#DC143C', label: 'High Risk', range: '> 1.6 g/cm³', min: 1.6 }
  ];

  // Backend stores as cg/cm³, need to convert to g/cm³ (divide by 100)
  const bulkDensityCG = soilData?.soil_properties?.bulk_density_cg_cm3;

  if (bulkDensityCG === null || bulkDensityCG === undefined) {
    return []; // Return empty if no data
  }

  const bulkDensityG = bulkDensityCG / 100;

  // Find and return ONLY the active category
  const activeCategory = categories.find(c => {
    if (c.max !== undefined && c.min !== undefined) {
      return bulkDensityG >= c.min && bulkDensityG < c.max;
    } else if (c.max !== undefined) {
      return bulkDensityG < c.max;
    } else if (c.min !== undefined) {
      return bulkDensityG >= c.min;
    }
    return false;
  });

  if (!activeCategory) return [];

  return [{
    color: activeCategory.color,
    label: activeCategory.label,
    range: `${activeCategory.range} (${bulkDensityG.toFixed(2)} g/cm³)`
  }];
}

interface RasterLayer {
  id: string;
  name: string;
  description: string;
  legend: LegendItem[];
  source?: string;  // Data source citation
  resolution?: string;  // Spatial resolution
  year?: string;  // Data year
}

// Layer definitions with predefined color legends (from backend)
const RASTER_LAYERS: RasterLayer[] = [
  {
    id: 'slope',
    name: 'Slope',
    description: 'Terrain slope in degrees',
    source: 'Derived from SRTM DEM',
    resolution: '30m',
    legend: [] // Will be populated dynamically based on which slope codes are present
  },
  {
    id: 'aspect',
    name: 'Aspect',
    description: 'Slope direction (compass bearing)',
    source: 'Derived from SRTM DEM',
    resolution: '30m',
    legend: [
      { color: '#CCCCCC', label: 'Flat' },
      { color: '#1A5490', label: 'North (N)' },
      { color: '#3498DB', label: 'Northeast (NE)' },
      { color: '#1ABC9C', label: 'East (E)' },
      { color: '#F1C40F', label: 'Southeast (SE)' },
      { color: '#E74C3C', label: 'South (S)' },
      { color: '#E67E22', label: 'Southwest (SW)' },
      { color: '#F39C12', label: 'West (W)' },
      { color: '#9B59B6', label: 'Northwest (NW)' }
    ]
  },
  {
    id: 'dem',
    name: 'Elevation (DEM)',
    description: 'Height above sea level',
    source: 'SRTM 1 Arc-Second Global',
    resolution: '30m',
    year: '2000',
    legend: [] // Will be populated dynamically based on actual min/max elevation
  },
  {
    id: 'canopy',
    name: 'Canopy Height',
    description: 'Tree canopy height in meters',
    source: 'ETH Zurich / GEDI',
    resolution: '30m',
    year: '2020',
    legend: [] // Will be populated dynamically based on actual min/max canopy height
  },
  {
    id: 'biomass',
    name: 'Biomass (AGB)',
    description: 'Above-ground biomass in Mg/ha',
    source: 'ESA CCI AGB V6',
    resolution: '100m',
    year: '2022',
    legend: [] // Will be populated dynamically based on actual min/max biomass
  },
  {
    id: 'temperature',
    name: 'Temperature',
    description: 'Mean annual temperature',
    source: 'WorldClim 2.1',
    resolution: '1km',
    year: '1970-2000',
    legend: [] // Will be populated dynamically based on actual min/max temperature
  },
  {
    id: 'precipitation',
    name: 'Precipitation',
    description: 'Annual precipitation in mm',
    source: 'WorldClim 2.1',
    resolution: '1km',
    year: '1970-2000',
    legend: [] // Will be populated dynamically based on actual min/max precipitation
  },
  {
    id: 'forest_health',
    name: 'Forest Health (NDVI)',
    description: 'Forest health based on NDVI values',
    source: 'Sentinel-2/Landsat NDVI',
    resolution: '10-30m',
    year: '2023',
    legend: [
      { color: '#DC143C', label: 'Stressed', range: 'NDVI < 0.2' },
      { color: '#FF8C00', label: 'Poor', range: 'NDVI 0.2-0.4' },
      { color: '#FFD700', label: 'Moderate', range: 'NDVI 0.4-0.6' },
      { color: '#90EE90', label: 'Healthy', range: 'NDVI 0.6-0.8' },
      { color: '#228B22', label: 'Excellent', range: 'NDVI > 0.8' }
    ]
  },
  {
    id: 'min_temp_coldest',
    name: 'Min Temperature (Coldest Month)',
    description: 'Minimum temperature of coldest month',
    source: 'WorldClim 2.1',
    resolution: '1km',
    year: '1970-2000',
    legend: [] // Will be populated dynamically based on actual min/max values
  },
  {
    id: 'nasa_forest_2020',
    name: 'Forest Quality (NASA 2020)',
    description: 'Primary vs Secondary forest (IPCC Tier 1)',
    source: 'NASA/ORNL DAAC',
    resolution: '30m',
    year: '2020',
    legend: [
      { color: '#00FF00', label: 'Primary Forest', range: 'Class 1 - Old-growth, highest carbon' },
      { color: '#FF0000', label: 'Young Secondary', range: 'Class 2 - Regenerating, low carbon' },
      { color: '#6666FF', label: 'Old Secondary', range: 'Class 3 - Mature regrowth, medium carbon' }
    ]
  },
  {
    id: 'forest_type',
    name: 'Forest Type (FRTC)',
    description: 'Forest type classification (25 classes)',
    source: 'Nepal FRTC',
    resolution: '30m',
    year: '2015',
    legend: [] // Will be populated dynamically based on forest_type_percentages
  },
  {
    id: 'landcover',
    name: 'Land Cover (ESA WorldCover)',
    description: 'ESA WorldCover 2021 land cover classification',
    source: 'ESA WorldCover',
    resolution: '10m',
    year: '2021',
    legend: [
      { color: '#006400', label: 'Tree Cover', range: '10' },
      { color: '#FFBB22', label: 'Shrubland', range: '20' },
      { color: '#FFFF4C', label: 'Grassland', range: '30' },
      { color: '#F096FF', label: 'Cropland', range: '40' },
      { color: '#FA0000', label: 'Built-up', range: '50' },
      { color: '#B4B4B4', label: 'Bare/Sparse', range: '60' },
      { color: '#F0F0F0', label: 'Snow/Ice', range: '70' },
      { color: '#0064C8', label: 'Water', range: '80' },
      { color: '#0096A0', label: 'Wetland', range: '90' },
      { color: '#00CF75', label: 'Mangroves', range: '95' },
      { color: '#FAE6A0', label: 'Moss/Lichen', range: '100' }
    ]
  },
  {
    id: 'forest_loss',
    name: 'Forest Loss (Hansen)',
    description: 'Year of forest loss 2001-2024',
    source: 'Hansen Global Forest Change',
    resolution: '30m',
    year: '2001-2024',
    legend: [
      { color: '#FFD700', label: '2001-2008', range: 'Early Loss' },
      { color: '#FF8C00', label: '2009-2016', range: 'Mid Loss' },
      { color: '#DC143C', label: '2017-2024', range: 'Recent Loss' }
    ]
  },
  {
    id: 'forest_gain',
    name: 'Forest Gain (Hansen)',
    description: 'Forest regrowth 2000-2012',
    source: 'Hansen Global Forest Change',
    resolution: '30m',
    year: '2000-2012',
    legend: [
      { color: '#32CD32', label: 'Forest Regrowth', range: '2000-2012' }
    ]
  },
  {
    id: 'fire',
    name: 'Fire Loss',
    description: 'Forest loss from fire 2001-2024',
    source: 'Hansen Global Forest Change',
    resolution: '30m',
    year: '2001-2024',
    legend: [
      { color: '#FF8C00', label: '2001-2008', range: 'Old Burns' },
      { color: '#FF4500', label: '2009-2016', range: 'Mid Burns' },
      { color: '#8B0000', label: '2017-2024', range: 'Recent Burns - Priority' }
    ]
  },
  {
    id: 'soil_ph',
    name: 'Soil pH',
    description: 'Soil acidity/alkalinity (0-30cm depth)',
    source: 'SoilGrids 2.0 (ISRIC)',
    resolution: '250m',
    year: '2020',
    legend: [
      { color: '#DC143C', label: 'Extremely Acidic', range: '< 4.5' },
      { color: '#FF8C00', label: 'Strongly Acidic', range: '4.5-5.5' },
      { color: '#FFD700', label: 'Slightly Acidic', range: '5.5-6.5' },
      { color: '#228B22', label: 'Neutral (Optimal)', range: '6.5-7.5' },
      { color: '#4682B4', label: 'Slightly Alkaline', range: '7.5-8.5' },
      { color: '#9370DB', label: 'Strongly Alkaline', range: '> 8.5' }
    ]
  },
  {
    id: 'soil_texture',
    name: 'Soil Texture',
    description: 'USDA soil texture classification',
    source: 'SoilGrids 2.0 (ISRIC)',
    resolution: '250m',
    year: '2020',
    legend: [
      { color: '#654321', label: 'Clay', range: 'Heavy' },
      { color: '#8B4513', label: 'Clay Loam', range: 'Moderate' },
      { color: '#A0522D', label: 'Loam (Optimal)', range: 'Balanced' },
      { color: '#D2B48C', label: 'Sandy', range: 'Light' }
    ]
  },
  {
    id: 'soil_carbon',
    name: 'Soil Organic Carbon',
    description: 'SOC percentage (0-30cm depth)',
    source: 'SoilGrids 2.0 (ISRIC)',
    resolution: '250m',
    year: '2020',
    legend: [
      { color: '#DC143C', label: 'Very Low', range: '< 0.5%' },
      { color: '#FF8C00', label: 'Low', range: '0.5-1.0%' },
      { color: '#FFD700', label: 'Medium', range: '1.0-2.0%' },
      { color: '#90EE90', label: 'High', range: '2.0-3.0%' },
      { color: '#228B22', label: 'Very High (Forest)', range: '> 3.0%' }
    ]
  },
  {
    id: 'soil_fertility',
    name: 'Soil Fertility Index',
    description: 'Fertility score based on pH, SOC, N, CEC',
    source: 'SoilGrids 2.0 (ISRIC)',
    resolution: '250m',
    year: '2020',
    legend: [
      { color: '#DC143C', label: 'Very Low', range: '0-20' },
      { color: '#FF8C00', label: 'Low', range: '20-40' },
      { color: '#FFD700', label: 'Medium', range: '40-60' },
      { color: '#90EE90', label: 'High', range: '60-80' },
      { color: '#228B22', label: 'Very High', range: '80-100' }
    ]
  },
  {
    id: 'soil_density',
    name: 'Bulk Density (Compaction)',
    description: 'Soil compaction risk',
    source: 'SoilGrids 2.0 (ISRIC)',
    resolution: '250m',
    year: '2020',
    legend: [
      { color: '#228B22', label: 'Low (Good)', range: '< 1.2 g/cm³' },
      { color: '#FFD700', label: 'Moderate', range: '1.2-1.4 g/cm³' },
      { color: '#FF8C00', label: 'Elevated', range: '1.4-1.6 g/cm³' },
      { color: '#DC143C', label: 'High Risk', range: '> 1.6 g/cm³' }
    ]
  }
];

interface RasterLayerControlProps {
  calculationId: string;
  calculation?: any;
}

export const RasterLayerControl: React.FC<RasterLayerControlProps> = ({ calculationId, calculation }) => {
  const [activeLayers, setActiveLayers] = useState<Set<string>>(new Set());
  const [selectedLayer, setSelectedLayer] = useState<string | null>(null);
  const [isPanelMinimized, setIsPanelMinimized] = useState(false);
  const [layerOpacity, setLayerOpacity] = useState<number>(0.5); // Default 50% opacity
  
  // Slope class filter state (default: all classes 1-4)
  const [slopeFilters, setSlopeFilters] = useState<Set<number>>(new Set([1, 2, 3, 4]));
  
  // Slope class definitions (Forest Regulation 2079)
  const slopeClassOptions = [
    { code: 1, label: 'Gentle', range: '0-19°', color: '#2ECC71' },
    { code: 2, label: 'Moderate', range: '19-30°', color: '#F1C40F' },
    { code: 3, label: 'Highly Steep', range: '30-45°', color: '#E67E22' },
    { code: 4, label: 'Extreme', range: '>45°', color: '#E74C3C' }
  ];

  // Generate dynamic legends based on calculation data
  const dynamicRasterLayers = useMemo(() => {
    const layers = [...RASTER_LAYERS];

    // Update DEM layer with dynamic elevation legend
    const demLayerIndex = layers.findIndex(l => l.id === 'dem');
    if (demLayerIndex !== -1 && calculation?.result_data) {
      const { elevation_min_m, elevation_max_m } = calculation.result_data;

      // Only use dynamic legend if we have valid elevation data
      if (elevation_min_m !== undefined && elevation_max_m !== undefined &&
          elevation_min_m > -32000 && elevation_max_m > -32000) {
        layers[demLayerIndex] = {
          ...layers[demLayerIndex],
          legend: generateDynamicElevationLegend(elevation_min_m, elevation_max_m)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[demLayerIndex] = {
          ...layers[demLayerIndex],
          legend: [
            { color: '#8B4513', label: 'Low', range: '< 500m' },
            { color: '#FFA500', label: 'Medium', range: '500-1500m' },
            { color: '#7FFF00', label: 'High', range: '1500-3000m' },
            { color: '#87CEEB', label: 'Very High', range: '> 3000m' }
          ]
        };
      }
    }

    // Update Canopy layer with dynamic canopy legend (absolute ecological thresholds)
    const canopyLayerIndex = layers.findIndex(l => l.id === 'canopy');
    if (canopyLayerIndex !== -1 && calculation?.result_data) {
      const { canopy_min_m, canopy_max_m } = calculation.result_data;

      // Only use dynamic legend if we have valid canopy data
      if (canopy_min_m !== undefined && canopy_max_m !== undefined &&
          canopy_min_m >= 0 && canopy_max_m >= 0) {
        layers[canopyLayerIndex] = {
          ...layers[canopyLayerIndex],
          legend: generateDynamicCanopyLegend(canopy_min_m, canopy_max_m)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[canopyLayerIndex] = {
          ...layers[canopyLayerIndex],
          legend: [
            { color: '#DC143C', label: 'Sparse/Regeneration', range: '0-5m' },
            { color: '#FF8C00', label: 'Young Forest', range: '5-15m' },
            { color: '#90EE90', label: 'Mature Forest', range: '15-30m' },
            { color: '#228B22', label: 'Old Growth', range: '>30m' }
          ]
        };
      }
    }

    // Update Temperature layer with dynamic temperature legend
    const temperatureLayerIndex = layers.findIndex(l => l.id === 'temperature');
    if (temperatureLayerIndex !== -1 && calculation?.result_data) {
      const { temperature_min_c, temperature_max_c } = calculation.result_data;

      // Only use dynamic legend if we have valid temperature data
      if (temperature_min_c !== undefined && temperature_max_c !== undefined &&
          temperature_min_c > -100 && temperature_max_c < 100) {
        layers[temperatureLayerIndex] = {
          ...layers[temperatureLayerIndex],
          legend: generateDynamicTemperatureLegend(temperature_min_c, temperature_max_c)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[temperatureLayerIndex] = {
          ...layers[temperatureLayerIndex],
          legend: [
            { color: '#0000FF', label: 'Very Cold', range: '< 0°C' },
            { color: '#00BFFF', label: 'Cold', range: '0-10°C' },
            { color: '#90EE90', label: 'Moderate', range: '10-20°C' },
            { color: '#FFD700', label: 'Warm', range: '20-25°C' },
            { color: '#FF4500', label: 'Hot', range: '> 25°C' }
          ]
        };
      }
    }

    // Update Precipitation layer with dynamic precipitation legend
    const precipitationLayerIndex = layers.findIndex(l => l.id === 'precipitation');
    if (precipitationLayerIndex !== -1 && calculation?.result_data) {
      const { precipitation_min_mm, precipitation_max_mm } = calculation.result_data;

      // Only use dynamic legend if we have valid precipitation data
      if (precipitation_min_mm !== undefined && precipitation_max_mm !== undefined &&
          precipitation_min_mm >= 0 && precipitation_max_mm >= 0) {
        layers[precipitationLayerIndex] = {
          ...layers[precipitationLayerIndex],
          legend: generateDynamicPrecipitationLegend(precipitation_min_mm, precipitation_max_mm)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[precipitationLayerIndex] = {
          ...layers[precipitationLayerIndex],
          legend: [
            { color: '#8B4513', label: 'Very Dry', range: '< 500mm' },
            { color: '#D2B48C', label: 'Dry', range: '500-1000mm' },
            { color: '#90EE90', label: 'Moderate', range: '1000-2000mm' },
            { color: '#4169E1', label: 'Wet', range: '2000-3000mm' },
            { color: '#0000CD', label: 'Very Wet', range: '> 3000mm' }
          ]
        };
      }
    }

    // Update Biomass layer with dynamic biomass legend
    const biomassLayerIndex = layers.findIndex(l => l.id === 'biomass');
    if (biomassLayerIndex !== -1 && calculation?.result_data) {
      const { agb_min_mg_ha, agb_max_mg_ha } = calculation.result_data;

      // Only use dynamic legend if we have valid biomass data
      if (agb_min_mg_ha !== undefined && agb_max_mg_ha !== undefined &&
          agb_min_mg_ha >= 0 && agb_max_mg_ha >= 0) {
        layers[biomassLayerIndex] = {
          ...layers[biomassLayerIndex],
          legend: generateDynamicBiomassLegend(agb_min_mg_ha, agb_max_mg_ha)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[biomassLayerIndex] = {
          ...layers[biomassLayerIndex],
          legend: [
            { color: '#DC143C', label: 'Very Low', range: '0-50 Mg/ha' },
            { color: '#FFD700', label: 'Low', range: '50-100 Mg/ha' },
            { color: '#90EE90', label: 'Medium', range: '100-200 Mg/ha' },
            { color: '#228B22', label: 'High', range: '200-300 Mg/ha' },
            { color: '#1E90FF', label: 'Very High', range: '>300 Mg/ha' }
          ]
        };
      }
    }

    // Update Slope layer with dynamic slope legend
    const slopeLayerIndex = layers.findIndex(l => l.id === 'slope');
    if (slopeLayerIndex !== -1 && calculation?.result_data) {
      const { slope_min_code, slope_max_code } = calculation.result_data;

      // Only use dynamic legend if we have valid slope code data
      if (slope_min_code !== undefined && slope_max_code !== undefined &&
          slope_min_code >= 1 && slope_max_code <= 4) {
        layers[slopeLayerIndex] = {
          ...layers[slopeLayerIndex],
          legend: generateDynamicSlopeLegend(slope_min_code, slope_max_code)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[slopeLayerIndex] = {
          ...layers[slopeLayerIndex],
          legend: [
            { color: '#2ECC71', label: 'Gentle', range: '0-19°' },
            { color: '#F1C40F', label: 'Moderate', range: '19-30°' },
            { color: '#E67E22', label: 'Highly Steep', range: '30-45°' },
            { color: '#E74C3C', label: 'Extreme', range: '>45°' }
          ]
        };
      }
    }

    // Update Min Temperature (Coldest Month) layer with dynamic legend
    const minTempColdestLayerIndex = layers.findIndex(l => l.id === 'min_temp_coldest');
    if (minTempColdestLayerIndex !== -1 && calculation?.result_data) {
      const { min_temp_coldest_min_c, min_temp_coldest_max_c } = calculation.result_data;

      // Only use dynamic legend if we have valid min temp coldest data
      if (min_temp_coldest_min_c !== undefined && min_temp_coldest_max_c !== undefined &&
          min_temp_coldest_min_c > -100 && min_temp_coldest_max_c < 100) {
        layers[minTempColdestLayerIndex] = {
          ...layers[minTempColdestLayerIndex],
          legend: generateDynamicMinTempColdestLegend(min_temp_coldest_min_c, min_temp_coldest_max_c)
        };
      } else {
        // Fallback to default static legend if no data available
        layers[minTempColdestLayerIndex] = {
          ...layers[minTempColdestLayerIndex],
          legend: [
            { color: '#0000CD', label: 'Extreme Cold', range: '< -10°C' },
            { color: '#4169E1', label: 'Very Cold', range: '-10 to 0°C' },
            { color: '#87CEEB', label: 'Cold', range: '0 to 5°C' },
            { color: '#90EE90', label: 'Cool', range: '5 to 10°C' },
            { color: '#FFD700', label: 'Mild', range: '10 to 15°C' },
            { color: '#FF8C00', label: 'Warm', range: '> 15°C' }
          ]
        };
      }
    }

    // Update Land Cover layer with dynamic legend - only show classes present in data
    const landcoverLayerIndex = layers.findIndex(l => l.id === 'landcover');
    if (landcoverLayerIndex !== -1 && calculation?.result_data) {
      const { landcover_percentages } = calculation.result_data;

      if (landcover_percentages && Object.keys(landcover_percentages).length > 0) {
        layers[landcoverLayerIndex] = {
          ...layers[landcoverLayerIndex],
          legend: generateDynamicLandcoverLegend(landcover_percentages)
        };
      }
    }

    // Update NASA Forest 2020 layer with dynamic legend - only show classes present
    const nasaForestLayerIndex = layers.findIndex(l => l.id === 'nasa_forest_2020');
    if (nasaForestLayerIndex !== -1 && calculation?.result_data) {
      // Check both whole forest and block-level percentages
      const nasaPercentages = calculation.result_data.whole_nasa_forest_2020_percentages ||
                              calculation.result_data.nasa_forest_2020_percentages;

      if (nasaPercentages && Object.keys(nasaPercentages).length > 0) {
        layers[nasaForestLayerIndex] = {
          ...layers[nasaForestLayerIndex],
          legend: generateDynamicNasaForestLegend(nasaPercentages)
        };
      }
    }

    // Update Aspect layer with dynamic legend - only show directions present
    const aspectLayerIndex = layers.findIndex(l => l.id === 'aspect');
    if (aspectLayerIndex !== -1 && calculation?.result_data) {
      const { aspect_percentages } = calculation.result_data;

      if (aspect_percentages && Object.keys(aspect_percentages).length > 0) {
        layers[aspectLayerIndex] = {
          ...layers[aspectLayerIndex],
          legend: generateDynamicAspectLegend(aspect_percentages)
        };
      }
    }

    // Update Forest Health layer with dynamic legend - only show health classes present
    const forestHealthLayerIndex = layers.findIndex(l => l.id === 'forest_health');
    if (forestHealthLayerIndex !== -1 && calculation?.result_data) {
      const { forest_health_percentages } = calculation.result_data;

      if (forest_health_percentages && Object.keys(forest_health_percentages).length > 0) {
        layers[forestHealthLayerIndex] = {
          ...layers[forestHealthLayerIndex],
          legend: generateDynamicForestHealthLegend(forest_health_percentages)
        };
      }
    }

    // Update Forest Type layer with dynamic legend - only show types present in data
    const forestTypeLayerIndex = layers.findIndex(l => l.id === 'forest_type');
    if (forestTypeLayerIndex !== -1 && calculation?.result_data) {
      const { forest_type_percentages } = calculation.result_data;

      if (forest_type_percentages && Object.keys(forest_type_percentages).length > 0) {
        layers[forestTypeLayerIndex] = {
          ...layers[forestTypeLayerIndex],
          legend: generateDynamicForestTypeLegend(forest_type_percentages)
        };
      }
    }

    // Update Fire Loss layer with dynamic legend - show fire activity by time period
    const fireLayerIndex = layers.findIndex(l => l.id === 'fire');
    if (fireLayerIndex !== -1 && calculation?.result_data) {
      const { fire_loss_by_year } = calculation.result_data;

      if (fire_loss_by_year && Object.keys(fire_loss_by_year).length > 0) {
        layers[fireLayerIndex] = {
          ...layers[fireLayerIndex],
          legend: generateDynamicFireLossLegend(fire_loss_by_year)
        };
      }
    }

    // Soil layers: Use static legends showing all categories
    // (Map tiles show actual raster data with full range of values,
    //  so legends should show all possible categories, not just the dominant one)

    return layers;
  }, [calculation]);

  const toggleLayer = (layerId: string) => {
    setActiveLayers(prev => {
      const newSet = new Set(prev);
      if (newSet.has(layerId)) {
        newSet.delete(layerId);
      } else {
        newSet.add(layerId);
      }
      return newSet;
    });
  };

  const showLegend = (layerId: string) => {
    setSelectedLayer(layerId);
  };

  const currentLegend = selectedLayer
    ? dynamicRasterLayers.find(l => l.id === selectedLayer)?.legend || []
    : [];

  const currentLayerName = selectedLayer
    ? dynamicRasterLayers.find(l => l.id === selectedLayer)?.name || ''
    : '';

  return (
    <>
      {/* Compact Layer Toggle Panel */}
      <div style={{
        position: 'absolute',
        top: '80px',
        right: '10px',
        backgroundColor: 'white',
        padding: isPanelMinimized ? '8px' : '12px',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        minWidth: isPanelMinimized ? 'auto' : '200px',
        maxHeight: '600px',
        overflowY: 'auto'
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: isPanelMinimized ? '0' : '8px'
        }}>
          <h3 style={{
            margin: 0,
            fontSize: '14px',
            fontWeight: 'bold',
            display: isPanelMinimized ? 'none' : 'block'
          }}>
            Raster Layers
          </h3>
          <button
            onClick={() => setIsPanelMinimized(!isPanelMinimized)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '16px',
              padding: '2px 4px'
            }}
            title={isPanelMinimized ? 'Expand' : 'Minimize'}
          >
            {isPanelMinimized ? '📍' : '─'}
          </button>
        </div>

        {/* Layer checkboxes */}
        {!isPanelMinimized && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {dynamicRasterLayers.map(layer => (
                <div key={layer.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 6px',
                  borderRadius: '4px',
                  backgroundColor: activeLayers.has(layer.id) ? '#e8f5e9' : 'transparent',
                  border: activeLayers.has(layer.id) ? '1px solid #4caf50' : '1px solid transparent'
                }}>
                  <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    flex: 1,
                    fontSize: '13px'
                  }}>
                    <input
                      type="checkbox"
                      checked={activeLayers.has(layer.id)}
                      onChange={() => toggleLayer(layer.id)}
                      style={{ marginRight: '6px', cursor: 'pointer', width: '14px', height: '14px' }}
                    />
                    <span>{layer.name}</span>
                  </label>
                  <button
                    onClick={() => showLegend(layer.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '14px',
                      padding: '2px 4px',
                      opacity: 0.6
                    }}
                    title="Show legend"
                  >
                    🗺️
                  </button>
                </div>
              ))}
            </div>

            {/* Opacity Slider - Only show when at least one layer is active */}
            {activeLayers.size > 0 && (
              <div style={{
                marginTop: '12px',
                padding: '8px',
                backgroundColor: '#f0f0f0',
                borderRadius: '6px',
                border: '1px solid #ddd'
              }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '6px'
                }}>
                  <label style={{
                    fontSize: '12px',
                    fontWeight: '600',
                    color: '#333'
                  }}>
                    Opacity
                  </label>
                  <span style={{
                    fontSize: '12px',
                    fontWeight: 'bold',
                    color: '#4caf50'
                  }}>
                    {Math.round(layerOpacity * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={layerOpacity * 100}
                  onChange={(e) => setLayerOpacity(Number(e.target.value) / 100)}
                  style={{
                    width: '100%',
                    cursor: 'pointer'
                  }}
                  title={`Opacity: ${Math.round(layerOpacity * 100)}%`}
                />
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '10px',
                  color: '#666',
                  marginTop: '2px'
                }}>
                  <span>Transparent</span>
                  <span>Opaque</span>
                </div>
              </div>
            )}

            {/* Slope Class Filter - Only show when slope layer is active */}
            {activeLayers.has('slope') && (
              <div style={{
                marginTop: '12px',
                padding: '8px',
                backgroundColor: '#fff8e1',
                borderRadius: '6px',
                border: '1px solid #ffc107'
              }}>
                <div style={{
                  fontSize: '12px',
                  fontWeight: '600',
                  color: '#333',
                  marginBottom: '8px'
                }}>
                  Slope Classes:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {slopeClassOptions.map(cls => (
                    <label
                      key={cls.code}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={slopeFilters.has(cls.code)}
                        onChange={() => {
                          const newFilters = new Set(slopeFilters);
                          if (newFilters.has(cls.code)) {
                            if (newFilters.size > 1) {  // Keep at least one
                              newFilters.delete(cls.code);
                            }
                          } else {
                            newFilters.add(cls.code);
                          }
                          setSlopeFilters(newFilters);
                        }}
                        style={{ cursor: 'pointer' }}
                      />
                      <div style={{
                        width: '12px',
                        height: '12px',
                        backgroundColor: cls.color,
                        border: '1px solid #999',
                        borderRadius: '2px'
                      }} />
                      <span>{cls.label} ({cls.range})</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Active layer count when minimized */}
        {isPanelMinimized && activeLayers.size > 0 && (
          <div style={{
            fontSize: '11px',
            color: '#4caf50',
            fontWeight: 'bold',
            textAlign: 'center',
            marginTop: '4px'
          }}>
            {activeLayers.size}
          </div>
        )}
      </div>

      {/* Separate Floating Legend Panel */}
      {selectedLayer && (
        <div style={{
          position: 'absolute',
          bottom: '20px',
          left: '20px',
          backgroundColor: 'white',
          padding: '12px',
          borderRadius: '8px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
          zIndex: 1000,
          maxWidth: '280px',
          border: '2px solid #4caf50'
        }}>
          {/* Legend Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '10px',
            borderBottom: '2px solid #4caf50',
            paddingBottom: '6px'
          }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 'bold', color: '#333' }}>
              {currentLayerName}
            </h4>
            <button
              onClick={() => setSelectedLayer(null)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '18px',
                padding: '0 4px',
                color: '#666'
              }}
              title="Close legend"
            >
              ✕
            </button>
          </div>

          {/* Legend Items */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {currentLegend.map((item, idx) => (
              <div key={idx} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <div style={{
                  width: '20px',
                  height: '20px',
                  backgroundColor: item.color,
                  border: '1px solid #999',
                  borderRadius: '3px',
                  opacity: 0.6,
                  flexShrink: 0
                }} />
                <span style={{ fontSize: '12px', flex: 1 }}>
                  <strong>{item.label}</strong>
                  {item.range && (
                    <span style={{ color: '#666', marginLeft: '4px', fontSize: '11px' }}>
                      {item.range}
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>

          {/* Slope Class Filter (only for slope layer) */}
          {selectedLayer === 'slope' && (
            <div style={{
              marginTop: '12px',
              paddingTop: '8px',
              borderTop: '1px solid #ddd'
            }}>
              <div style={{
                fontSize: '11px',
                fontWeight: 'bold',
                color: '#666',
                marginBottom: '8px'
              }}>
                Filter Classes:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {slopeClassOptions.map(cls => (
                  <label
                    key={cls.code}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer',
                      fontSize: '11px'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={slopeFilters.has(cls.code)}
                      onChange={() => {
                        const newFilters = new Set(slopeFilters);
                        if (newFilters.has(cls.code)) {
                          newFilters.delete(cls.code);
                        } else {
                          newFilters.add(cls.code);
                        }
                        setSlopeFilters(newFilters);
                      }}
                      style={{ cursor: 'pointer' }}
                    />
                    <div style={{
                      width: '14px',
                      height: '14px',
                      backgroundColor: cls.color,
                      border: '1px solid #999',
                      borderRadius: '2px'
                    }} />
                    <span>{cls.label} ({cls.range})</span>
                  </label>
                ))}
              </div>
              {slopeFilters.size === 0 && (
                <div style={{
                  fontSize: '10px',
                  color: '#e74c3c',
                  marginTop: '4px'
                }}>
                  At least one class must be selected
                </div>
              )}
            </div>
          )}

          {/* Data Source Attribution */}
          {(() => {
            const currentLayerData = dynamicRasterLayers.find(l => l.id === selectedLayer);
            if (currentLayerData && (currentLayerData.source || currentLayerData.resolution || currentLayerData.year)) {
              return (
                <div style={{
                  marginTop: '12px',
                  paddingTop: '8px',
                  borderTop: '1px solid #ddd',
                  fontSize: '10px',
                  color: '#666'
                }}>
                  {currentLayerData.source && (
                    <div><strong>Source:</strong> {currentLayerData.source}</div>
                  )}
                  {currentLayerData.resolution && (
                    <div><strong>Resolution:</strong> {currentLayerData.resolution}</div>
                  )}
                  {currentLayerData.year && (
                    <div><strong>Year:</strong> {currentLayerData.year}</div>
                  )}
                </div>
              );
            }
            return null;
          })()}
        </div>
      )}

      {/* Render active tile layers */}
      {Array.from(activeLayers).map(layerId => {
        // Build URL with optional filter for slope layer
        let url = `http://localhost:8001/api/calculations/${calculationId}/tiles/${layerId}/{z}/{x}/{y}.png?alpha=${Math.round(layerOpacity * 255)}&cb=${Date.now()}`;
        
        // Add filter_classes parameter for slope layer (only if not all classes selected)
        if (layerId === 'slope' && slopeFilters.size < 4) {
          const filterStr = Array.from(slopeFilters).sort().join(',');
          url += `&filter_classes=${filterStr}`;
        }
        
        return (
          <TileLayer
            key={layerId}
            url={url}
            opacity={layerOpacity}
            zIndex={500}
            maxZoom={18}
            minZoom={10}
          />
        );
      })}
    </>
  );
};
