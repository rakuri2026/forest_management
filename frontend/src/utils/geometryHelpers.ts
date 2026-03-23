/**
 * Geometry Helper Utilities
 *
 * Provides safe, reusable functions for geometry operations using Turf.js
 * Handles common issues like Feature vs Geometry, MultiPolygon conversion,
 * and floating-point precision tolerance.
 */

import * as turf from '@turf/turf';

/**
 * Configuration constants for geometry operations
 */
export const GEOMETRY_CONFIG = {
  // Snapping tolerance in degrees (~1mm at equator)
  SNAP_TOLERANCE: 1e-8,

  // Inward buffer to ensure blocks stay inside boundary (degrees)
  BUFFER_INWARD: -0.000001,

  // Area ratio threshold for containment validation (99.99%)
  AREA_THRESHOLD: 0.9999,

  // Minimum area to consider an overlap significant (sq degrees)
  MIN_OVERLAP_AREA: 1e-6,

  // Coordinate precision (decimal places)
  COORDINATE_PRECISION: 8,
};

/**
 * Safely extract geometry from various GeoJSON formats
 * Handles Feature, Geometry, Polygon, MultiPolygon, and raw coordinates
 *
 * @param geoData - Any GeoJSON-like object
 * @returns Geometry object or null if invalid
 */
export function getSafeGeometry(geoData: any): any | null {
  if (!geoData) {
    console.warn('[getSafeGeometry] Received null/undefined geometry');
    return null;
  }

  try {
    // If it's a Feature, extract the geometry
    if (geoData.type === 'Feature') {
      return geoData.geometry;
    }

    // If it's already a Geometry (Polygon, MultiPolygon, etc.)
    if (geoData.type === 'Polygon' || geoData.type === 'MultiPolygon' ||
        geoData.type === 'LineString' || geoData.type === 'Point') {
      return geoData;
    }

    // If it's raw coordinates (array), assume Polygon
    if (Array.isArray(geoData)) {
      return {
        type: 'Polygon',
        coordinates: geoData,
      };
    }

    console.warn('[getSafeGeometry] Unknown geometry format:', geoData);
    return null;
  } catch (error) {
    console.error('[getSafeGeometry] Error extracting geometry:', error);
    return null;
  }
}

/**
 * Convert any polygon-like geometry to a single Polygon Feature
 * Handles MultiPolygon by taking the largest part or merging
 *
 * @param geoData - GeoJSON Feature, Geometry, or coordinates
 * @returns Turf Polygon Feature or null if invalid
 */
export function ensurePolygon(geoData: any): turf.Feature<turf.Polygon> | null {
  try {
    const geometry = getSafeGeometry(geoData);

    if (!geometry) {
      return null;
    }

    // Handle Polygon
    if (geometry.type === 'Polygon') {
      return turf.polygon(geometry.coordinates);
    }

    // Handle MultiPolygon - merge into single polygon
    if (geometry.type === 'MultiPolygon') {
      const polygons = geometry.coordinates.map((coords: any) =>
        turf.polygon(coords)
      );

      if (polygons.length === 0) {
        return null;
      }

      if (polygons.length === 1) {
        return polygons[0];
      }

      // Union all polygons into one
      let combined = polygons[0];
      for (let i = 1; i < polygons.length; i++) {
        const union = turf.union(turf.featureCollection([combined, polygons[i]]));
        if (union) {
          combined = union as turf.Feature<turf.Polygon>;
        }
      }

      return combined;
    }

    console.warn('[ensurePolygon] Geometry is not a Polygon or MultiPolygon:', geometry.type);
    return null;
  } catch (error) {
    console.error('[ensurePolygon] Error converting to polygon:', error);
    return null;
  }
}

/**
 * Safe wrapper for turf.intersect with proper error handling
 * Compatible with Turf.js v7+ API
 *
 * @param geom1 - First geometry (Feature, Geometry, or coordinates)
 * @param geom2 - Second geometry (Feature, Geometry, or coordinates)
 * @returns Intersection Feature or null if no intersection or error
 */
export function safeIntersect(
  geom1: any,
  geom2: any
): turf.Feature<turf.Polygon | turf.MultiPolygon> | null {
  try {
    // Ensure both are valid polygon features
    const poly1 = ensurePolygon(geom1);
    const poly2 = ensurePolygon(geom2);

    if (!poly1 || !poly2) {
      console.warn('[safeIntersect] One or both geometries are invalid');
      return null;
    }

    // Clean coordinates before intersection
    const cleaned1 = turf.cleanCoords(poly1);
    const cleaned2 = turf.cleanCoords(poly2);

    // Perform intersection
    const intersection = turf.intersect(turf.featureCollection([cleaned1, cleaned2]));

    return intersection;
  } catch (error) {
    console.error('[safeIntersect] Intersection failed:', error);
    return null;
  }
}

/**
 * Round coordinates to specified precision to avoid floating-point drift
 *
 * @param geometry - Any geometry object
 * @param precision - Number of decimal places (default: 8)
 * @returns Geometry with rounded coordinates
 */
export function roundCoordinates(geometry: any, precision: number = GEOMETRY_CONFIG.COORDINATE_PRECISION): any {
  try {
    const geom = getSafeGeometry(geometry);
    if (!geom) return geometry;

    const round = (coord: number) => Number(coord.toFixed(precision));

    const roundCoords = (coords: any): any => {
      if (typeof coords[0] === 'number') {
        return coords.map(round);
      }
      return coords.map(roundCoords);
    };

    return {
      ...geom,
      coordinates: roundCoords(geom.coordinates),
    };
  } catch (error) {
    console.error('[roundCoordinates] Error rounding coordinates:', error);
    return geometry;
  }
}

/**
 * Snap a point to the nearest position on a line with tolerance
 *
 * @param point - Point to snap
 * @param line - Line to snap to
 * @param tolerance - Maximum snap distance (default: SNAP_TOLERANCE)
 * @returns Snapped point coordinates or original if too far
 */
export function snapPointToLine(
  point: [number, number],
  line: any,
  tolerance: number = GEOMETRY_CONFIG.SNAP_TOLERANCE
): [number, number] {
  try {
    const ptFeature = turf.point(point);
    const lineGeom = getSafeGeometry(line);

    if (!lineGeom) {
      return point;
    }

    // Convert polygon to line if needed
    let lineFeature;
    if (lineGeom.type === 'Polygon') {
      lineFeature = turf.polygonToLine(turf.polygon(lineGeom.coordinates));
    } else {
      lineFeature = turf.lineString(lineGeom.coordinates);
    }

    // Find nearest point on line
    const snapped = turf.nearestPointOnLine(lineFeature, ptFeature);

    // Check if within tolerance
    const distance = turf.distance(ptFeature, snapped, { units: 'degrees' });

    if (distance <= tolerance) {
      return snapped.geometry.coordinates as [number, number];
    }

    return point;
  } catch (error) {
    console.error('[snapPointToLine] Error snapping point:', error);
    return point;
  }
}

/**
 * Apply micro-buffer inward to ensure geometry stays within boundary
 *
 * @param geometry - Geometry to buffer
 * @param bufferAmount - Buffer distance (default: BUFFER_INWARD)
 * @returns Buffered geometry or original if buffer fails
 */
export function applyInwardBuffer(
  geometry: any,
  bufferAmount: number = GEOMETRY_CONFIG.BUFFER_INWARD
): any {
  try {
    const geom = getSafeGeometry(geometry);
    if (!geom) return geometry;

    const feature = turf.feature(geom);
    const buffered = turf.buffer(feature, bufferAmount, { units: 'degrees' });

    if (buffered && buffered.geometry) {
      // If buffer creates MultiPolygon, take largest part
      if (buffered.geometry.type === 'MultiPolygon') {
        const polygons = buffered.geometry.coordinates.map((coords: any) => ({
          type: 'Polygon',
          coordinates: coords,
        }));

        const largest = polygons.reduce((max: any, current: any) => {
          const maxArea = turf.area(turf.feature(max));
          const currentArea = turf.area(turf.feature(current));
          return currentArea > maxArea ? current : max;
        });

        return largest;
      }

      return buffered.geometry;
    }

    return geom;
  } catch (error) {
    console.warn('[applyInwardBuffer] Buffer operation failed, using original geometry:', error);
    return geometry;
  }
}

/**
 * Check if a geometry is valid and fix if possible
 *
 * @param geometry - Geometry to validate
 * @returns Object with valid flag and fixed geometry
 */
export function validateAndFixGeometry(geometry: any): { valid: boolean; geometry: any; errors: string[] } {
  const errors: string[] = [];

  try {
    let geom = getSafeGeometry(geometry);
    if (!geom) {
      errors.push('Geometry is null or invalid format');
      return { valid: false, geometry, errors };
    }

    // Clean coordinates (remove duplicates)
    try {
      const feature = turf.feature(geom);
      const cleaned = turf.cleanCoords(feature);
      geom = cleaned.geometry;
    } catch (e) {
      errors.push(`Failed to clean coordinates: ${e}`);
    }

    // Check for minimum area
    try {
      const feature = turf.feature(geom);
      const area = turf.area(feature);
      if (area === 0) {
        errors.push('Geometry has zero area');
        return { valid: false, geometry: geom, errors };
      }
    } catch (e) {
      errors.push(`Failed to calculate area: ${e}`);
    }

    // Try to fix with micro-buffer
    if (errors.length > 0) {
      try {
        const feature = turf.feature(geom);
        let buffered = turf.buffer(feature, 0.00001, { units: 'meters' });
        if (buffered) {
          buffered = turf.buffer(buffered, -0.00001, { units: 'meters' });
          if (buffered && buffered.geometry) {
            geom = buffered.geometry.type === 'MultiPolygon'
              ? buffered.geometry.coordinates[0] // Take first part
              : buffered.geometry;
            errors.length = 0; // Clear errors if fix worked
          }
        }
      } catch (e) {
        errors.push(`Buffer fix failed: ${e}`);
      }
    }

    return {
      valid: errors.length === 0,
      geometry: geom,
      errors,
    };
  } catch (error) {
    errors.push(`Validation error: ${error}`);
    return { valid: false, geometry, errors };
  }
}

/**
 * Calculate the percentage of geom1 that overlaps with geom2
 *
 * @param geom1 - First geometry
 * @param geom2 - Second geometry
 * @returns Overlap percentage (0-1) or null if error
 */
export function calculateOverlapRatio(geom1: any, geom2: any): number | null {
  try {
    const poly1 = ensurePolygon(geom1);
    const poly2 = ensurePolygon(geom2);

    if (!poly1 || !poly2) {
      return null;
    }

    const area1 = turf.area(poly1);
    if (area1 === 0) {
      return null;
    }

    const intersection = safeIntersect(poly1, poly2);
    if (!intersection) {
      return 0;
    }

    const intersectionArea = turf.area(intersection);
    return intersectionArea / area1;
  } catch (error) {
    console.error('[calculateOverlapRatio] Error calculating overlap:', error);
    return null;
  }
}
