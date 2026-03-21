import * as turf from '@turf/turf';
import {
  ensurePolygon,
  getSafeGeometry,
  safeIntersect,
  applyInwardBuffer,
  validateAndFixGeometry,
  roundCoordinates,
  GEOMETRY_CONFIG,
} from './geometryHelpers';

export interface ValidationResult {
  valid: boolean;
  error?: string;
  warnings?: string[];
}

/**
 * Calculate area of a polygon in hectares
 */
export const calculateAreaHectares = (geometry: any): number => {
  try {
    const feature = turf.feature(geometry);
    const areaSquareMeters = turf.area(feature);
    return areaSquareMeters / 10000; // Convert to hectares
  } catch (error) {
    throw new Error(`Failed to calculate area: ${error}`);
  }
};

/**
 * Check if two polygons overlap
 */
export const checkPolygonOverlap = (
  polygon1: any,
  polygon2: any
): { overlaps: boolean; overlapArea?: number } => {
  try {
    const feature1 = turf.feature(polygon1);
    const feature2 = turf.feature(polygon2);

    const intersection = turf.intersect(feature1, feature2);

    if (intersection) {
      const overlapArea = turf.area(intersection) / 10000; // hectares
      return { overlaps: true, overlapArea };
    }

    return { overlaps: false };
  } catch (error) {
    console.error('Error checking overlap:', error);
    return { overlaps: false };
  }
};

/**
 * Check if a point is inside a polygon
 */
export const isPointInPolygon = (
  point: [number, number], // [lon, lat]
  polygon: any
): boolean => {
  try {
    const pt = turf.point(point);
    const poly = turf.feature(polygon);
    return turf.booleanPointInPolygon(pt, poly);
  } catch (error) {
    console.error('Error checking point in polygon:', error);
    return false;
  }
};

/**
 * Validate that blocks don't overlap
 */
export const validateBlocksNoOverlap = (
  blocks: Array<{ name: string; geometry: any }>
): ValidationResult => {
  const warnings: string[] = [];

  for (let i = 0; i < blocks.length; i++) {
    for (let j = i + 1; j < blocks.length; j++) {
      const block1 = blocks[i];
      const block2 = blocks[j];

      const { overlaps, overlapArea } = checkPolygonOverlap(
        block1.geometry,
        block2.geometry
      );

      if (overlaps && overlapArea && overlapArea > 0.01) {
        // Tolerance: 0.01 hectares (100 sq meters)
        return {
          valid: false,
          error: `Blocks "${block1.name}" and "${block2.name}" overlap by ${overlapArea.toFixed(2)} hectares`,
        };
      }
    }
  }

  return { valid: true, warnings };
};

/**
 * Validate that sum of block areas approximately equals outer boundary area
 */
export const validateBlockAreaSum = (
  outerBoundary: any,
  blocks: Array<{ name: string; geometry: any }>,
  tolerancePercent: number = 1 // 1% tolerance
): ValidationResult => {
  const outerArea = calculateAreaHectares(outerBoundary);
  const blocksArea = blocks.reduce((sum, block) => {
    return sum + calculateAreaHectares(block.geometry);
  }, 0);

  const difference = Math.abs(outerArea - blocksArea);
  const percentDiff = (difference / outerArea) * 100;

  if (percentDiff > tolerancePercent) {
    return {
      valid: false,
      error: `Sum of block areas (${blocksArea.toFixed(2)} ha) differs from outer boundary area (${outerArea.toFixed(2)} ha) by ${percentDiff.toFixed(1)}%`,
    };
  }

  const warnings: string[] = [];
  if (percentDiff > 0.1) {
    warnings.push(
      `Small area difference detected: ${difference.toFixed(2)} ha (${percentDiff.toFixed(2)}%)`
    );
  }

  return { valid: true, warnings };
};

/**
 * Validate that sub-areas don't overlap within the same block
 */
export const validateSubAreasNoOverlap = (
  subAreas: Array<{ name: string; category: string; geometry: any }>
): ValidationResult => {
  for (let i = 0; i < subAreas.length; i++) {
    for (let j = i + 1; j < subAreas.length; j++) {
      const area1 = subAreas[i];
      const area2 = subAreas[j];

      const { overlaps, overlapArea } = checkPolygonOverlap(
        area1.geometry,
        area2.geometry
      );

      if (overlaps && overlapArea && overlapArea > 0.01) {
        return {
          valid: false,
          error: `Sub-areas "${area1.name}" (${area1.category}) and "${area2.name}" (${area2.category}) overlap by ${overlapArea.toFixed(2)} hectares`,
        };
      }
    }
  }

  return { valid: true };
};

/**
 * Validate that sum of sub-area areas doesn't exceed block area
 */
export const validateSubAreaSum = (
  blockGeometry: any,
  subAreas: Array<{ name: string; geometry: any }>,
  tolerancePercent: number = 1
): ValidationResult => {
  const blockArea = calculateAreaHectares(blockGeometry);
  const subAreasTotal = subAreas.reduce((sum, subArea) => {
    return sum + calculateAreaHectares(subArea.geometry);
  }, 0);

  if (subAreasTotal > blockArea * (1 + tolerancePercent / 100)) {
    return {
      valid: false,
      error: `Sum of sub-areas (${subAreasTotal.toFixed(2)} ha) exceeds block area (${blockArea.toFixed(2)} ha)`,
    };
  }

  return { valid: true };
};

/**
 * Detect which block a sub-area belongs to
 */
export const detectBlockForSubArea = (
  subAreaGeometry: any,
  blocks: Array<{ id: string; name: string; geometry: any }>
): { blockId?: string; blockName?: string; confidence: number } => {
  try {
    const subAreaFeature = turf.feature(subAreaGeometry);
    const subAreaCentroid = turf.centroid(subAreaFeature);

    // Check which block contains the centroid
    for (const block of blocks) {
      if (isPointInPolygon(subAreaCentroid.geometry.coordinates, block.geometry)) {
        return {
          blockId: block.id,
          blockName: block.name,
          confidence: 1.0,
        };
      }
    }

    // If centroid method fails, check for intersection
    for (const block of blocks) {
      const blockFeature = turf.feature(block.geometry);
      const intersection = turf.intersect(subAreaFeature, blockFeature);

      if (intersection) {
        const intersectionArea = turf.area(intersection);
        const subAreaArea = turf.area(subAreaFeature);
        const confidence = intersectionArea / subAreaArea;

        if (confidence > 0.5) {
          // More than 50% of sub-area is in this block
          return {
            blockId: block.id,
            blockName: block.name,
            confidence,
          };
        }
      }
    }

    return { confidence: 0 };
  } catch (error) {
    console.error('Error detecting block for sub-area:', error);
    return { confidence: 0 };
  }
};

/**
 * Validate polygon geometry
 */
export const validatePolygonGeometry = (geometry: any): ValidationResult => {
  try {
    const feature = turf.feature(geometry);

    // Check if it's a valid polygon
    if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
      return {
        valid: false,
        error: 'Geometry must be a Polygon or MultiPolygon',
      };
    }

    // Check for self-intersections using kinks
    const kinks = turf.kinks(feature);
    if (kinks.features.length > 0) {
      return {
        valid: false,
        error: `Polygon has ${kinks.features.length} self-intersection(s)`,
      };
    }

    // Calculate area
    const area = turf.area(feature);
    if (area === 0) {
      return {
        valid: false,
        error: 'Polygon has zero area',
      };
    }

    // Check minimum area (0.1 hectares = 1000 sq meters)
    if (area < 1000) {
      return {
        valid: false,
        error: `Polygon area too small: ${(area / 10000).toFixed(4)} hectares (minimum: 0.1 ha)`,
      };
    }

    const warnings: string[] = [];

    // Check if polygon is very small (warning)
    if (area < 5000) {
      // Less than 0.5 hectares
      warnings.push(`Small polygon area: ${(area / 10000).toFixed(2)} hectares`);
    }

    return { valid: true, warnings };
  } catch (error) {
    return {
      valid: false,
      error: `Invalid polygon geometry: ${error}`,
    };
  }
};

/**
 * Simplify polygon to reduce vertices (useful for large GPS tracks)
 */
export const simplifyPolygon = (
  geometry: any,
  tolerance: number = 0.0001 // degrees (~11 meters)
): any => {
  try {
    const feature = turf.feature(geometry);
    const simplified = turf.simplify(feature, { tolerance, highQuality: true });
    return simplified.geometry;
  } catch (error) {
    console.error('Error simplifying polygon:', error);
    return geometry;
  }
};

/**
 * Get polygon centroid
 */
export const getPolygonCentroid = (geometry: any): [number, number] => {
  try {
    const feature = turf.feature(geometry);
    const centroid = turf.centroid(feature);
    return centroid.geometry.coordinates as [number, number];
  } catch (error) {
    throw new Error(`Failed to calculate centroid: ${error}`);
  }
};

/**
 * Get polygon bounding box
 */
export const getPolygonBounds = (
  geometry: any
): { north: number; south: number; east: number; west: number } => {
  try {
    const feature = turf.feature(geometry);
    const bbox = turf.bbox(feature);
    return {
      west: bbox[0],
      south: bbox[1],
      east: bbox[2],
      north: bbox[3],
    };
  } catch (error) {
    throw new Error(`Failed to calculate bounds: ${error}`);
  }
};

/**
 * Check if a polygon is completely within another polygon
 */
export const isPolygonWithin = (innerPolygon: any, outerPolygon: any): boolean => {
  try {
    const inner = turf.feature(innerPolygon);
    const outer = turf.feature(outerPolygon);
    return turf.booleanWithin(inner, outer);
  } catch (error) {
    console.error('Error checking polygon containment:', error);
    return false;
  }
};

/**
 * Validate that all blocks are within the outer boundary
 */
export const validateBlocksWithinBoundary = (
  outerBoundary: any,
  blocks: Array<{ name: string; geometry: any }>
): ValidationResult => {
  for (const block of blocks) {
    if (!isPolygonWithin(block.geometry, outerBoundary)) {
      return {
        valid: false,
        error: `Block "${block.name}" extends outside the outer boundary`,
      };
    }
  }

  return { valid: true };
};

/**
 * Format area for display
 */
export const formatArea = (hectares: number): string => {
  if (hectares < 0.01) {
    return `${(hectares * 10000).toFixed(0)} m²`;
  } else if (hectares < 1) {
    return `${hectares.toFixed(3)} ha`;
  } else if (hectares < 100) {
    return `${hectares.toFixed(2)} ha`;
  } else {
    return `${hectares.toFixed(1)} ha`;
  }
};

/**
 * Split a polygon using a line
 * Returns array of resulting polygons after the split
 */
export const splitPolygonWithLine = (
  polygon: any,
  line: any
): any[] => {
  try {
    const polygonFeature = turf.feature(polygon);
    const lineFeature = turf.feature(line);

    // Get polygon boundary
    const polygonBoundary = turf.polygonToLine(polygonFeature);

    // Find intersection points between line and polygon boundary
    const intersections = turf.lineIntersect(lineFeature, polygonBoundary);

    console.log(`Found ${intersections.features.length} intersection points`);

    if (intersections.features.length < 2) {
      // Line doesn't fully cross the polygon, try buffer method directly
      console.log('Line does not have 2+ intersections, using buffer method');
      return splitPolygonWithBuffer(polygon, line);
    }

    // Get the two intersection points (use first and last if multiple)
    const point1 = intersections.features[0];
    const point2 = intersections.features[intersections.features.length - 1];

    // Get ALL coordinates from the drawn line (to preserve curves)
    const lineCoords = line.coordinates;
    console.log(`Line has ${lineCoords.length} coordinate points`);

    // Get polygon coordinates
    const polyCoords = polygon.coordinates[0];

    // Find indices of intersection points on polygon boundary
    const indices = findInsertionIndices(polyCoords, point1.geometry.coordinates, point2.geometry.coordinates);

    // Split polygon into two parts
    const part1Coords = [];
    const part2Coords = [];

    // First polygon: from point1 to point2 along boundary, then back via cutting line
    for (let i = indices.idx1; i !== indices.idx2; ) {
      part1Coords.push(polyCoords[i]);
      i = (i + 1) % (polyCoords.length - 1);
      if (i === indices.idx2) {
        part1Coords.push(polyCoords[i]);
        break;
      }
    }
    // Add intersection point
    part1Coords.push(point2.geometry.coordinates);
    // Add ALL intermediate points from the drawn line (in REVERSE order)
    for (let i = lineCoords.length - 1; i >= 0; i--) {
      part1Coords.push(lineCoords[i]);
    }
    // Add starting intersection point
    part1Coords.push(point1.geometry.coordinates);
    part1Coords.push(part1Coords[0]); // Close polygon

    // Second polygon: from point2 to point1 along boundary (the other way)
    for (let i = indices.idx2; i !== indices.idx1; ) {
      part2Coords.push(polyCoords[i]);
      i = (i + 1) % (polyCoords.length - 1);
      if (i === indices.idx1) {
        part2Coords.push(polyCoords[i]);
        break;
      }
    }
    // Add intersection point
    part2Coords.push(point1.geometry.coordinates);
    // Add ALL intermediate points from the drawn line (in FORWARD order)
    for (let i = 0; i < lineCoords.length; i++) {
      part2Coords.push(lineCoords[i]);
    }
    // Add ending intersection point
    part2Coords.push(point2.geometry.coordinates);
    part2Coords.push(part2Coords[0]); // Close polygon

    // Create polygon geometries
    const polygon1 = {
      type: 'Polygon',
      coordinates: [part1Coords],
    };

    const polygon2 = {
      type: 'Polygon',
      coordinates: [part2Coords],
    };

    // Validate resulting polygons
    try {
      const p1 = turf.feature(polygon1);
      const p2 = turf.feature(polygon2);

      if (turf.area(p1) > 0 && turf.area(p2) > 0) {
        console.log('Primary split method succeeded');

        // Clean geometries before returning
        const cleaned1 = cleanPolygonGeometry(polygon1);
        const cleaned2 = cleanPolygonGeometry(polygon2);

        // Try to clip to original polygon boundary (optional improvement)
        try {
          const originalFeature = turf.feature(polygon);
          const clipped1 = turf.intersect(turf.feature(cleaned1), originalFeature);
          const clipped2 = turf.intersect(turf.feature(cleaned2), originalFeature);

          if (clipped1 && clipped2 && clipped1.geometry && clipped2.geometry) {
            console.log('Successfully clipped to original boundary');
            return [clipped1.geometry, clipped2.geometry];
          }
        } catch (clipError) {
          console.warn('Clipping failed, using cleaned geometries:', clipError);
        }

        // If clipping failed, return cleaned versions
        return [cleaned1, cleaned2];
      } else {
        console.log('Primary method produced invalid areas, trying buffer method');
      }
    } catch (e) {
      console.log('Primary method validation failed, trying buffer method:', e);
    }

    // Alternative method: use buffer and difference
    return splitPolygonWithBuffer(polygon, line);
  } catch (error) {
    console.error('Error splitting polygon:', error);
    throw error; // Re-throw the original error with its message
  }
};

/**
 * Find insertion indices for intersection points on polygon boundary
 */
function findInsertionIndices(
  polyCoords: number[][],
  point1: number[],
  point2: number[]
): { idx1: number; idx2: number } {
  let idx1 = -1;
  let idx2 = -1;
  let minDist1 = Infinity;
  let minDist2 = Infinity;

  for (let i = 0; i < polyCoords.length - 1; i++) {
    const dist1 = turf.distance(turf.point(point1), turf.point(polyCoords[i]));
    const dist2 = turf.distance(turf.point(point2), turf.point(polyCoords[i]));

    if (dist1 < minDist1) {
      minDist1 = dist1;
      idx1 = i;
    }

    if (dist2 < minDist2) {
      minDist2 = dist2;
      idx2 = i;
    }
  }

  return { idx1, idx2 };
}

/**
 * Clean and fix polygon geometry
 * Removes duplicate coordinates, fixes self-intersections, and ensures validity
 */
export function cleanPolygonGeometry(polygon: any): any {
  try {
    let feature = turf.feature(polygon);

    // Remove duplicate/redundant coordinates
    feature = turf.cleanCoords(feature);

    // Use a tiny buffer(0) trick to fix self-intersections and topology issues
    // Buffer by 0.00001 meters then back - this cleans up invalid geometries
    let buffered = turf.buffer(feature, 0.00001, { units: 'meters' });
    if (buffered) {
      buffered = turf.buffer(buffered, -0.00001, { units: 'meters' });
      if (buffered && (buffered.geometry.type === 'Polygon' || buffered.geometry.type === 'MultiPolygon')) {
        // If it's a MultiPolygon, take the largest part
        if (buffered.geometry.type === 'MultiPolygon') {
          const polygons = buffered.geometry.coordinates.map((coords: any) => ({
            type: 'Polygon',
            coordinates: coords,
          }));
          // Return the polygon with the largest area
          const largest = polygons.reduce((max: any, current: any) => {
            const maxArea = turf.area(turf.feature(max));
            const currentArea = turf.area(turf.feature(current));
            return currentArea > maxArea ? current : max;
          });
          return largest;
        }
        return buffered.geometry;
      }
    }

    // If buffer didn't work, return cleaned original
    return feature.geometry;
  } catch (error) {
    console.error('Error cleaning polygon geometry:', error);
    // Return original if cleaning fails
    return polygon;
  }
}

/**
 * Alternative splitting method using buffer
 */
function splitPolygonWithBuffer(polygon: any, line: any): any[] {
  try {
    const lineFeature = turf.feature(line);

    // Extend the line to ensure it crosses the polygon
    const extendedLine = extendLine(lineFeature, 1); // Extend 1km on each end

    // Create a very thin buffer around the line (1 meter)
    const lineBand = turf.buffer(extendedLine, 0.001, { units: 'kilometers' });

    if (!lineBand) {
      throw new Error('Failed to create line buffer');
    }

    // Use difference to split
    const polygonFeature = turf.feature(polygon);
    const difference = turf.difference(polygonFeature, lineBand);

    if (!difference) {
      throw new Error('Line does not intersect polygon');
    }

    if (difference.geometry.type === 'MultiPolygon') {
      // Successfully split into multiple polygons
      const splitPolygons = difference.geometry.coordinates.map((coords: any) => ({
        type: 'Polygon',
        coordinates: coords,
      }));

      // Clean each resulting polygon
      const cleanedPolygons = splitPolygons.map((poly) => {
        try {
          return cleanPolygonGeometry(poly);
        } catch (cleanError) {
          console.warn('Could not clean polygon, using original:', cleanError);
          return poly;
        }
      });

      return cleanedPolygons;
    } else if (difference.geometry.type === 'Polygon') {
      // Still one polygon, split failed
      throw new Error('Line does not split the polygon (still one piece after difference)');
    }

    throw new Error(`Unexpected result type from splitting: ${difference.geometry.type}`);
  } catch (error: any) {
    console.error('Buffer split error details:', error);
    throw new Error(`Failed to split polygon using buffer method: ${error.message}`);
  }
}

/**
 * Extend a line on both ends
 */
function extendLine(line: any, distanceKm: number): any {
  const coords = line.geometry.coordinates;

  if (!coords || coords.length < 2) {
    throw new Error('Line must have at least 2 coordinates');
  }

  // Extend start
  const bearing1 = turf.bearing(turf.point(coords[1]), turf.point(coords[0]));
  const extendedStart = turf.destination(turf.point(coords[0]), distanceKm, bearing1);

  // Extend end
  const bearing2 = turf.bearing(
    turf.point(coords[coords.length - 2]),
    turf.point(coords[coords.length - 1])
  );
  const extendedEnd = turf.destination(
    turf.point(coords[coords.length - 1]),
    distanceKm,
    bearing2
  );

  return turf.lineString([
    extendedStart.geometry.coordinates,
    ...coords,
    extendedEnd.geometry.coordinates,
  ]);
}

/**
 * Calculate sub-area breakdown by blocks for cross-block sub-areas
 * Returns an array of block associations with their respective areas
 */
export const calculateSubAreaByBlock = (
  subAreaGeometry: any,
  blocks: Array<{ id: string; name: string; geometry: any }>
): Array<{ blockId: string; blockName: string; area: number; percentage: number }> => {
  try {
    console.log('[calculateSubAreaByBlock] Starting grid-based calculation');
    console.log('[calculateSubAreaByBlock] Sub-area geometry:', subAreaGeometry);
    console.log('[calculateSubAreaByBlock] Number of blocks:', blocks.length);

    // Validate sub-area geometry
    if (!subAreaGeometry || !subAreaGeometry.type || !subAreaGeometry.coordinates) {
      console.error('[calculateSubAreaByBlock] Invalid sub-area geometry:', subAreaGeometry);
      return [];
    }

    const subAreaFeature = turf.feature(subAreaGeometry);
    const subAreaTotalArea = calculateAreaHectares(subAreaGeometry);
    console.log('[calculateSubAreaByBlock] Sub-area total area:', subAreaTotalArea, 'ha');

    // Use grid-based sampling approach for reliable intersection calculation
    // This avoids turf.intersect() issues by testing points instead of polygon intersection

    // Step 1: Get bounding box of sub-area
    const bbox = turf.bbox(subAreaFeature);
    console.log('[calculateSubAreaByBlock] Sub-area bbox:', bbox);

    // Step 2: Create grid of points with fine resolution for accurate results
    // Use 50 points per side for better accuracy, or 20m minimum grid
    const cellSize = Math.sqrt(subAreaTotalArea) / 50; // ~50 points per side
    const gridSize = Math.max(cellSize, 0.02); // Minimum 20m grid (0.02 km)
    console.log('[calculateSubAreaByBlock] Grid size:', gridSize, 'km');

    const pointGrid = turf.pointGrid(bbox, gridSize, { units: 'kilometers' });
    console.log('[calculateSubAreaByBlock] Created grid with', pointGrid.features.length, 'points');

    // Step 3: Filter points that are inside the sub-area
    const pointsInSubArea = pointGrid.features.filter(point =>
      turf.booleanPointInPolygon(point, subAreaFeature)
    );
    console.log('[calculateSubAreaByBlock] Points inside sub-area:', pointsInSubArea.length);

    if (pointsInSubArea.length === 0) {
      console.warn('[calculateSubAreaByBlock] No points found in sub-area - grid might be too coarse');
      return [];
    }

    // Step 4: Count how many points fall in each block
    const blockPointCounts = new Map<string, number>();

    for (const block of blocks) {
      if (!block.geometry || !block.geometry.type || !block.geometry.coordinates) {
        continue;
      }

      const blockFeature = turf.feature(block.geometry);
      let pointsInBlock = 0;

      for (const point of pointsInSubArea) {
        if (turf.booleanPointInPolygon(point, blockFeature)) {
          pointsInBlock++;
        }
      }

      if (pointsInBlock > 0) {
        blockPointCounts.set(block.id, pointsInBlock);
        console.log(`[calculateSubAreaByBlock] Block ${block.name}: ${pointsInBlock} points`);
      }
    }

    // Step 5: Calculate proportional areas based on point distribution
    const breakdown: Array<{ blockId: string; blockName: string; area: number; percentage: number }> = [];
    const totalPointsDistributed = Array.from(blockPointCounts.values()).reduce((sum, count) => sum + count, 0);

    if (totalPointsDistributed === 0) {
      console.warn('[calculateSubAreaByBlock] No points matched any blocks');
      return [];
    }

    for (const block of blocks) {
      const pointCount = blockPointCounts.get(block.id) || 0;
      if (pointCount > 0) {
        const percentage = (pointCount / totalPointsDistributed) * 100;
        const area = (percentage / 100) * subAreaTotalArea;

        breakdown.push({
          blockId: block.id,
          blockName: block.name,
          area: parseFloat(area.toFixed(4)),
          percentage: parseFloat(percentage.toFixed(2))
        });

        console.log(`[calculateSubAreaByBlock] ✓ Block ${block.name}: ${area.toFixed(4)} ha (${percentage.toFixed(2)}%)`);
      }
    }

    return breakdown;
  } catch (error) {
    console.error('[calculateSubAreaByBlock] Error calculating sub-area by block:', error);
    return [];
  }
};

/**
 * Clean and validate blocks before sending to backend
 * Fixes geometry issues, clips to outer boundary, and removes overlaps
 * UPDATED: Now uses geometryHelpers for safer geometry operations
 */
export const cleanAndValidateBlocks = (
  blocks: Array<{ id: string; name: string; geometry: any; area: number }>,
  outerBoundary: any
): Array<{ id: string; name: string; geometry: any; area: number }> => {
  console.log('[cleanAndValidateBlocks] Starting validation with', blocks.length, 'blocks');

  try {
    // Validate outer boundary
    if (!outerBoundary) {
      console.warn('[cleanAndValidateBlocks] No outer boundary provided, skipping cleaning');
      return blocks;
    }

    // Safely extract and convert outer boundary to polygon
    const outerPoly = ensurePolygon(outerBoundary);
    if (!outerPoly) {
      console.error('[cleanAndValidateBlocks] Failed to convert outer boundary to polygon');
      return blocks;
    }

    console.log('[cleanAndValidateBlocks] Outer boundary validated successfully');

    const cleanedBlocks: Array<{ id: string; name: string; geometry: any; area: number }> = [];

    for (const block of blocks) {
      try {
        console.log(`[cleanAndValidateBlocks] Processing block: ${block.name}`);

        // Step 1: Validate and fix geometry
        const validation = validateAndFixGeometry(block.geometry);
        if (!validation.valid) {
          console.warn(`[cleanAndValidateBlocks] Block ${block.name} has invalid geometry:`, validation.errors);
          // Try to use original if fix failed
          cleanedBlocks.push(block);
          continue;
        }

        let cleanedGeometry = validation.geometry;
        console.log(`[cleanAndValidateBlocks] Block ${block.name} geometry validated`);

        // Step 2: Round coordinates to avoid floating-point drift
        cleanedGeometry = roundCoordinates(cleanedGeometry);

        // Step 3: Clip to outer boundary using safe intersection
        const clipped = safeIntersect(cleanedGeometry, outerPoly);

        if (clipped && clipped.geometry) {
          cleanedGeometry = clipped.geometry;
          console.log(`[cleanAndValidateBlocks] Block ${block.name} clipped to boundary successfully`);
        } else {
          console.warn(`[cleanAndValidateBlocks] Block ${block.name} intersection returned null, keeping original`);
          // Block might be completely inside - check if it needs inward buffer
        }

        // Step 4: Apply micro-inward buffer to ensure it's strictly inside boundary
        const safeGeometry = applyInwardBuffer(cleanedGeometry, GEOMETRY_CONFIG.BUFFER_INWARD);
        if (safeGeometry) {
          cleanedGeometry = safeGeometry;
          console.log(`[cleanAndValidateBlocks] Block ${block.name} inward buffer applied`);
        }

        // Step 5: Recalculate area after cleaning
        const newArea = calculateAreaHectares(cleanedGeometry);
        console.log(`[cleanAndValidateBlocks] Block ${block.name} area: ${newArea.toFixed(4)} ha`);

        // Only add if significant area remains (> 0.01 ha)
        if (newArea > 0.01) {
          cleanedBlocks.push({
            id: block.id,
            name: block.name,
            geometry: cleanedGeometry,
            area: newArea,
          });
        } else {
          console.warn(`[cleanAndValidateBlocks] Block ${block.name} has negligible area (${newArea.toFixed(4)} ha), skipping`);
        }
      } catch (error) {
        console.error(`[cleanAndValidateBlocks] Error processing block ${block.name}:`, error);
        // Keep original block if cleaning fails
        cleanedBlocks.push(block);
      }
    }

    console.log(`[cleanAndValidateBlocks] Cleaned ${cleanedBlocks.length} blocks, now fixing overlaps`);

    // Step 6: Fix overlaps between blocks
    const nonOverlappingBlocks = fixBlockOverlaps(cleanedBlocks);

    console.log(`[cleanAndValidateBlocks] Final result: ${nonOverlappingBlocks.length} blocks`);
    return nonOverlappingBlocks;
  } catch (error) {
    console.error('[cleanAndValidateBlocks] Critical error in validation:', error);
    // Return original blocks if processing fails
    return blocks;
  }
};

/**
 * Fix overlaps between blocks by subtracting intersections
 * UPDATED: Now uses safeIntersect and proper error handling
 */
function fixBlockOverlaps(
  blocks: Array<{ id: string; name: string; geometry: any; area: number }>
): Array<{ id: string; name: string; geometry: any; area: number }> {
  console.log(`[fixBlockOverlaps] Processing ${blocks.length} blocks for overlaps`);
  const result: Array<{ id: string; name: string; geometry: any; area: number }> = [];

  for (let i = 0; i < blocks.length; i++) {
    let currentGeometry = blocks[i].geometry;

    // Convert to polygon feature safely
    let currentFeature = ensurePolygon(currentGeometry);
    if (!currentFeature) {
      console.warn(`[fixBlockOverlaps] Block ${blocks[i].name} has invalid geometry, skipping`);
      result.push(blocks[i]);
      continue;
    }

    // Subtract any overlaps with previously processed blocks
    for (let j = 0; j < i; j++) {
      try {
        const previousFeature = ensurePolygon(result[j].geometry);
        if (!previousFeature) continue;

        // Check if they intersect
        if (turf.booleanIntersects(currentFeature, previousFeature)) {
          // Use safe intersection
          const intersection = safeIntersect(currentFeature, previousFeature);

          // Only process significant overlaps (> configurable threshold)
          const minOverlapArea = GEOMETRY_CONFIG.MIN_OVERLAP_AREA * 1e10; // Convert to sq meters
          if (intersection && turf.area(intersection) > minOverlapArea) {
            console.log(
              `[fixBlockOverlaps] Found overlap between ${blocks[i].name} and ${result[j].name}: ` +
              `${turf.area(intersection).toFixed(2)} sqm`
            );

            // Subtract the overlap from current block
            const difference = turf.difference(
              turf.featureCollection([currentFeature, previousFeature])
            );

            if (difference) {
              if (difference.geometry.type === 'Polygon') {
                currentGeometry = difference.geometry;
                currentFeature = difference as turf.Feature<turf.Polygon>;
              } else if (difference.geometry.type === 'MultiPolygon') {
                // Take the largest part
                const polygons = difference.geometry.coordinates.map((coords: any) =>
                  turf.polygon(coords)
                );
                const largest = polygons.reduce((max: any, current: any) => {
                  const maxArea = turf.area(max);
                  const currentArea = turf.area(current);
                  return currentArea > maxArea ? current : max;
                });
                currentGeometry = largest.geometry;
                currentFeature = largest;
              }
              console.log(`[fixBlockOverlaps] Removed overlap from ${blocks[i].name}`);
            }
          }
        }
      } catch (error) {
        console.error(`[fixBlockOverlaps] Error fixing overlap between blocks ${i} and ${j}:`, error);
      }
    }

    // Recalculate area after fixing overlaps
    const finalArea = calculateAreaHectares(currentGeometry);

    // Only add if significant area remains
    if (finalArea > 0.01) {
      result.push({
        id: blocks[i].id,
        name: blocks[i].name,
        geometry: currentGeometry,
        area: finalArea,
      });
      console.log(`[fixBlockOverlaps] Added ${blocks[i].name} with final area: ${finalArea.toFixed(4)} ha`);
    } else {
      console.warn(`[fixBlockOverlaps] Block ${blocks[i].name} has negligible area after fixing overlaps (${finalArea.toFixed(4)} ha), skipping`);
    }
  }

  console.log(`[fixBlockOverlaps] Completed: ${result.length} blocks after overlap resolution`);
  return result;
}
