import Papa from 'papaparse';
import proj4 from 'proj4';
import { parseString } from 'xml2js';

// Define common EPSG codes used in Nepal
proj4.defs([
  ['EPSG:4326', '+proj=longlat +datum=WGS84 +no_defs'],
  ['EPSG:32644', '+proj=utm +zone=44 +datum=WGS84 +units=m +no_defs'], // UTM Zone 44N
  ['EPSG:32645', '+proj=utm +zone=45 +datum=WGS84 +units=m +no_defs'], // UTM Zone 45N
]);

export interface GPSPoint {
  id: string;
  latitude: number;
  longitude: number;
  name?: string;
  elevation?: number;
  order?: number;
  sn?: string | number; // Serial number (auto-detected)
  description?: string; // Description field (auto-detected)
  additionalFields?: Record<string, any>; // Other fields from CSV
}

export interface FieldDetectionResult {
  snField?: string; // Name of detected SN field
  descriptionField?: string; // Name of detected description field
  additionalFields: string[]; // Other available fields
  rawData: any[]; // Original CSV data
}

export interface CoordinateTransformOptions {
  fromEPSG: string;
  toEPSG?: string; // defaults to EPSG:4326
}

/**
 * Detect SN (serial number) field from CSV columns
 * Priority: sn, serial_no, serial_number, point_no, point_number, no, number, id
 * Returns field name if numeric values found, undefined otherwise
 */
export const detectSNField = (data: any[]): string | undefined => {
  if (!data || data.length === 0) return undefined;

  const firstRow = data[0];
  const columns = Object.keys(firstRow);

  // Priority order for SN field detection
  const snFieldPatterns = [
    /^sn$/i,
    /^serial[_\s]?no$/i,
    /^serial[_\s]?number$/i,
    /^point[_\s]?no$/i,
    /^point[_\s]?number$/i,
    /^no$/i,
    /^number$/i,
    /^id$/i,
  ];

  // Try to find field matching patterns
  for (const pattern of snFieldPatterns) {
    const field = columns.find(col => pattern.test(col));
    if (field) {
      // Verify it contains numeric-like values
      const value = firstRow[field];
      if (value !== undefined && value !== null) {
        const numValue = typeof value === 'number' ? value : parseFloat(String(value));
        if (!isNaN(numValue)) {
          return field;
        }
      }
    }
  }

  // Look for any field that looks like a number in all rows
  for (const col of columns) {
    const allNumeric = data.slice(0, Math.min(5, data.length)).every(row => {
      const value = row[col];
      if (value === undefined || value === null || value === '') return false;
      const numValue = typeof value === 'number' ? value : parseFloat(String(value));
      return !isNaN(numValue);
    });

    if (allNumeric) {
      return col;
    }
  }

  return undefined;
};

/**
 * Detect description field from CSV columns
 * Priority: description, desc, name, label, remarks, note, comment
 * Returns field name if text values found, undefined otherwise
 */
export const detectDescriptionField = (data: any[], snField?: string): string | undefined => {
  if (!data || data.length === 0) return undefined;

  const firstRow = data[0];
  const columns = Object.keys(firstRow);

  // Priority order for description field detection
  const descFieldPatterns = [
    /^description$/i,
    /^desc$/i,
    /^name$/i,
    /^label$/i,
    /^remarks?$/i,
    /^notes?$/i,
    /^comments?$/i,
  ];

  // Try to find field matching patterns (excluding SN field)
  for (const pattern of descFieldPatterns) {
    const field = columns.find(col => pattern.test(col) && col !== snField);
    if (field) {
      // Verify it contains text values
      const value = String(firstRow[field] || '').trim();
      if (value.length > 0) {
        return field;
      }
    }
  }

  // Find first text column that's not lat/lon/elevation/sn
  const excludedPatterns = [
    /^(lat|latitude|lon|longitude|lng|x|y)$/i,
    /^(elevation|elev|alt|altitude|z)$/i,
  ];

  for (const col of columns) {
    if (col === snField) continue;
    if (excludedPatterns.some(pattern => pattern.test(col))) continue;

    const value = String(firstRow[col] || '').trim();
    if (value.length > 0 && isNaN(parseFloat(value))) {
      return col;
    }
  }

  return undefined;
};

/**
 * Detect additional fields (elevation, timestamp, etc.)
 */
export const detectAdditionalFields = (
  data: any[],
  excludeFields: string[]
): string[] => {
  if (!data || data.length === 0) return [];

  const firstRow = data[0];
  const columns = Object.keys(firstRow);

  const standardFields = [
    /^(lat|latitude|lon|longitude|lng|x|y)$/i,
  ];

  return columns.filter(col => {
    // Exclude already detected fields
    if (excludeFields.includes(col)) return false;

    // Exclude standard coordinate fields
    if (standardFields.some(pattern => pattern.test(col))) return false;

    // Include if has value
    const value = firstRow[col];
    return value !== undefined && value !== null && String(value).trim() !== '';
  });
};

/**
 * Parse CSV file with field detection
 * Returns GPS points and detected field information
 */
export const parseCSVWithFieldDetection = (
  file: File
): Promise<{ points: GPSPoint[]; fieldDetection: FieldDetectionResult }> => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        try {
          const rawData = results.data as any[];

          // Detect fields
          const snField = detectSNField(rawData);
          const descriptionField = detectDescriptionField(rawData, snField);
          const additionalFields = detectAdditionalFields(
            rawData,
            [snField, descriptionField, 'latitude', 'lat', 'longitude', 'lon', 'lng', 'x', 'y'].filter(Boolean) as string[]
          );

          const points: GPSPoint[] = rawData.map((row: any, index: number) => {
            // Try different column name variations
            const lat = parseFloat(
              row.latitude || row.lat || row.Latitude || row.LAT || row.y || row.Y
            );
            const lon = parseFloat(
              row.longitude || row.lon || row.lng || row.Longitude || row.LON || row.x || row.X
            );

            if (isNaN(lat) || isNaN(lon)) {
              throw new Error(`Invalid coordinates in row ${index + 1}: lat=${lat}, lon=${lon}`);
            }

            // Get SN value (prefer detected field, fallback to index)
            let snValue: string | number = index + 1;
            if (snField && row[snField] !== undefined && row[snField] !== null) {
              const parsed = parseFloat(String(row[snField]));
              snValue = isNaN(parsed) ? String(row[snField]) : parsed;
            }

            // Get description value
            const description = descriptionField ? String(row[descriptionField] || '') : undefined;

            // Collect additional fields
            const additionalFieldsData: Record<string, any> = {};
            additionalFields.forEach(field => {
              if (row[field] !== undefined && row[field] !== null) {
                additionalFieldsData[field] = row[field];
              }
            });

            return {
              id: `gps-${index}`,
              latitude: lat,
              longitude: lon,
              sn: snValue,
              description: description,
              name: row.name || row.Name || row.point_name || `Point ${index + 1}`,
              elevation: row.elevation || row.elev || row.alt || row.altitude ?
                parseFloat(row.elevation || row.elev || row.alt || row.altitude) : undefined,
              order: index,
              additionalFields: Object.keys(additionalFieldsData).length > 0 ? additionalFieldsData : undefined,
            };
          });

          resolve({
            points,
            fieldDetection: {
              snField,
              descriptionField,
              additionalFields,
              rawData,
            },
          });
        } catch (error) {
          reject(error);
        }
      },
      error: (error) => {
        reject(new Error(`CSV parsing error: ${error.message}`));
      },
    });
  });
};

/**
 * Parse CSV file containing GPS coordinates (legacy function for backward compatibility)
 * Expected columns: latitude, longitude, name (optional), elevation (optional)
 */
export const parseCSVCoordinates = (
  file: File
): Promise<GPSPoint[]> => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        try {
          const points: GPSPoint[] = results.data.map((row: any, index: number) => {
            // Try different column name variations
            const lat = parseFloat(
              row.latitude || row.lat || row.Latitude || row.LAT || row.y || row.Y
            );
            const lon = parseFloat(
              row.longitude || row.lon || row.lng || row.Longitude || row.LON || row.x || row.X
            );

            if (isNaN(lat) || isNaN(lon)) {
              throw new Error(`Invalid coordinates in row ${index + 1}: lat=${lat}, lon=${lon}`);
            }

            return {
              id: `gps-${index}`,
              latitude: lat,
              longitude: lon,
              name: row.name || row.Name || row.point_name || `Point ${index + 1}`,
              elevation: row.elevation || row.elev || row.alt || row.altitude ?
                parseFloat(row.elevation || row.elev || row.alt || row.altitude) : undefined,
              order: index,
            };
          });

          resolve(points);
        } catch (error) {
          reject(error);
        }
      },
      error: (error) => {
        reject(new Error(`CSV parsing error: ${error.message}`));
      },
    });
  });
};

/**
 * Parse pasted coordinates from text
 * Supports formats:
 * - "lat, lon" (one per line)
 * - "lat lon" (space-separated)
 * - "lon, lat" (if lon is negative or > 90)
 */
export const parsePastedCoordinates = (text: string): GPSPoint[] => {
  const lines = text.split('\n').filter(line => line.trim());
  const points: GPSPoint[] = [];

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    // Split by comma or whitespace
    const parts = trimmed.split(/[,\s]+/).map(p => parseFloat(p.trim()));

    if (parts.length < 2) {
      throw new Error(`Invalid format in line ${index + 1}: "${line}"`);
    }

    let lat = parts[0];
    let lon = parts[1];

    // Auto-detect if coordinates are swapped (lon, lat instead of lat, lon)
    // If first number is > 90 or < -90, it's likely longitude
    if (Math.abs(lat) > 90 && Math.abs(lon) <= 90) {
      [lat, lon] = [lon, lat]; // swap
    }

    if (isNaN(lat) || isNaN(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      throw new Error(`Invalid coordinates in line ${index + 1}: lat=${lat}, lon=${lon}`);
    }

    points.push({
      id: `pasted-${index}`,
      latitude: lat,
      longitude: lon,
      name: `Point ${index + 1}`,
      order: index,
    });
  });

  return points;
};

/**
 * Parse GPX file (GPS exchange format)
 */
export const parseGPXFile = (file: File): Promise<GPSPoint[]> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      const xmlText = e.target?.result as string;

      parseString(xmlText, { explicitArray: false }, (err, result) => {
        if (err) {
          reject(new Error(`GPX parsing error: ${err.message}`));
          return;
        }

        try {
          const points: GPSPoint[] = [];

          // Parse waypoints (wpt)
          if (result.gpx?.wpt) {
            const waypoints = Array.isArray(result.gpx.wpt) ? result.gpx.wpt : [result.gpx.wpt];
            waypoints.forEach((wpt: any, index: number) => {
              points.push({
                id: `gpx-wpt-${index}`,
                latitude: parseFloat(wpt.$.lat),
                longitude: parseFloat(wpt.$.lon),
                name: wpt.name || `Waypoint ${index + 1}`,
                elevation: wpt.ele ? parseFloat(wpt.ele) : undefined,
                order: index,
              });
            });
          }

          // Parse track points (trkpt)
          if (result.gpx?.trk?.trkseg?.trkpt) {
            const trackpoints = Array.isArray(result.gpx.trk.trkseg.trkpt)
              ? result.gpx.trk.trkseg.trkpt
              : [result.gpx.trk.trkseg.trkpt];

            trackpoints.forEach((trkpt: any, index: number) => {
              points.push({
                id: `gpx-trk-${index}`,
                latitude: parseFloat(trkpt.$.lat),
                longitude: parseFloat(trkpt.$.lon),
                name: `Track Point ${index + 1}`,
                elevation: trkpt.ele ? parseFloat(trkpt.ele) : undefined,
                order: points.length + index,
              });
            });
          }

          // Parse route points (rtept)
          if (result.gpx?.rte?.rtept) {
            const routepoints = Array.isArray(result.gpx.rte.rtept)
              ? result.gpx.rte.rtept
              : [result.gpx.rte.rtept];

            routepoints.forEach((rtept: any, index: number) => {
              points.push({
                id: `gpx-rte-${index}`,
                latitude: parseFloat(rtept.$.lat),
                longitude: parseFloat(rtept.$.lon),
                name: rtept.name || `Route Point ${index + 1}`,
                elevation: rtept.ele ? parseFloat(rtept.ele) : undefined,
                order: points.length + index,
              });
            });
          }

          if (points.length === 0) {
            reject(new Error('No GPS points found in GPX file'));
            return;
          }

          resolve(points);
        } catch (error) {
          reject(new Error(`Error extracting GPX data: ${error}`));
        }
      });
    };

    reader.onerror = () => {
      reject(new Error('Failed to read GPX file'));
    };

    reader.readAsText(file);
  });
};

/**
 * Transform coordinates from one EPSG code to another
 */
export const transformCoordinates = (
  points: GPSPoint[],
  options: CoordinateTransformOptions
): GPSPoint[] => {
  const { fromEPSG, toEPSG = 'EPSG:4326' } = options;

  // If already in target projection, return as-is
  if (fromEPSG === toEPSG) {
    return points;
  }

  try {
    return points.map(point => {
      // For UTM, input is (easting, northing) i.e., (x, y) i.e., (lon, lat)
      // For WGS84, input is (longitude, latitude) i.e., (lon, lat)
      const inputCoords = fromEPSG.includes('326')
        ? [point.longitude, point.latitude]  // UTM: treat as easting, northing
        : [point.longitude, point.latitude]; // WGS84: lon, lat

      const [lon, lat] = proj4(fromEPSG, toEPSG, inputCoords);

      return {
        ...point,
        latitude: lat,
        longitude: lon,
      };
    });
  } catch (error) {
    throw new Error(`Coordinate transformation failed: ${error}`);
  }
};

/**
 * Validate GPS point coordinates
 */
export const validateGPSPoint = (point: GPSPoint): { valid: boolean; error?: string } => {
  // Check latitude range (-90 to 90)
  if (point.latitude < -90 || point.latitude > 90) {
    return { valid: false, error: `Invalid latitude: ${point.latitude} (must be between -90 and 90)` };
  }

  // Check longitude range (-180 to 180)
  if (point.longitude < -180 || point.longitude > 180) {
    return { valid: false, error: `Invalid longitude: ${point.longitude} (must be between -180 and 180)` };
  }

  // Check if coordinates are not zero (common error)
  if (point.latitude === 0 && point.longitude === 0) {
    return { valid: false, error: 'Coordinates cannot be (0, 0)' };
  }

  return { valid: true };
};

/**
 * Convert GPS points to GeoJSON Point features
 */
export const gpsPointsToGeoJSON = (points: GPSPoint[]) => {
  return {
    type: 'FeatureCollection',
    features: points.map(point => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [point.longitude, point.latitude],
      },
      properties: {
        id: point.id,
        name: point.name,
        elevation: point.elevation,
        order: point.order,
      },
    })),
  };
};

/**
 * Convert GPS points to polygon by connecting them in order
 */
export const gpsPointsToPolygon = (points: GPSPoint[]) => {
  if (points.length < 3) {
    throw new Error('At least 3 points are required to create a polygon');
  }

  // Sort by order
  const sorted = [...points].sort((a, b) => (a.order || 0) - (b.order || 0));

  // Create coordinate array
  const coordinates = sorted.map(p => [p.longitude, p.latitude]);

  // Close the polygon (first point = last point)
  if (
    coordinates[0][0] !== coordinates[coordinates.length - 1][0] ||
    coordinates[0][1] !== coordinates[coordinates.length - 1][1]
  ) {
    coordinates.push(coordinates[0]);
  }

  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [coordinates],
    },
    properties: {
      created_from: 'gps_points',
      point_count: points.length,
    },
  };
};

/**
 * Detect likely EPSG code based on coordinate ranges
 * Nepal is roughly between:
 * - Latitude: 26-31°N
 * - Longitude: 80-89°E
 * - UTM Zone 44N: ~200,000-900,000 easting, ~2,800,000-3,500,000 northing
 * - UTM Zone 45N: ~200,000-900,000 easting, ~2,800,000-3,500,000 northing
 */
export const detectEPSG = (points: GPSPoint[]): string => {
  if (points.length === 0) return 'EPSG:4326';

  const firstPoint = points[0];
  const lat = firstPoint.latitude;
  const lon = firstPoint.longitude;

  // Check if it's WGS84 (lat/lon in degrees)
  if (lat >= 26 && lat <= 31 && lon >= 80 && lon <= 89) {
    return 'EPSG:4326';
  }

  // Check if it's UTM (very large numbers)
  if (lat > 1000000 && lon > 100000 && lon < 1000000) {
    // Likely UTM - easting is lon, northing is lat
    // Zone 44 covers 81-87°E, Zone 45 covers 87-93°E
    // Estimate zone based on easting
    if (lon < 500000) {
      return 'EPSG:32644'; // UTM Zone 44N
    } else {
      return 'EPSG:32645'; // UTM Zone 45N
    }
  }

  // Default to WGS84
  return 'EPSG:4326';
};
