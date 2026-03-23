import React, { useState } from 'react';
import { useMapEvents, Popup } from 'react-leaflet';
import { LatLng } from 'leaflet';
import * as turf from '@turf/turf';

interface RasterData {
  location: {
    lat: number;
    lon: number;
  };
  elevation_m: number | null;
  slope_degrees: number | null;
  aspect_direction: string | null;
  canopy_height_m: number | null;
  biomass_mg_ha: number | null;
  forest_type_class: number | null;
  temperature_c: number | null;
  precipitation_mm: number | null;
}

interface RasterClickInfoProps {
  calculationId: string;
  boundaryGeometry: any;
}

export const RasterClickInfo: React.FC<RasterClickInfoProps> = ({ calculationId, boundaryGeometry }) => {
  const [clickedData, setClickedData] = useState<RasterData | null>(null);
  const [clickPosition, setClickPosition] = useState<LatLng | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useMapEvents({
    click: async (e) => {
      const { lat, lng } = e.latlng;

      // Check if click is inside boundary geometry
      if (boundaryGeometry) {
        const clickPoint = turf.point([lng, lat]);
        let isInside = false;

        try {
          // Handle both single polygon and multi-polygon geometries
          if (boundaryGeometry.type === 'FeatureCollection') {
            isInside = boundaryGeometry.features.some((feature: any) => {
              try {
                return turf.booleanPointInPolygon(clickPoint, feature);
              } catch {
                return false;
              }
            });
          } else if (boundaryGeometry.type === 'Feature') {
            isInside = turf.booleanPointInPolygon(clickPoint, boundaryGeometry);
          } else if (boundaryGeometry.type === 'Polygon' || boundaryGeometry.type === 'MultiPolygon') {
            isInside = turf.booleanPointInPolygon(clickPoint, turf.feature(boundaryGeometry));
          }
        } catch (err) {
          console.error('Error checking point in polygon:', err);
          isInside = false;
        }

        if (!isInside) {
          // Click is outside the boundary, don't show popup
          setClickPosition(null);
          setClickedData(null);
          return;
        }
      }

      setClickPosition(e.latlng);
      setLoading(true);
      setError(null);

      try {
        // Query all raster values at this point
        const response = await fetch(
          `http://localhost:8001/api/calculations/${calculationId}/query?lat=${lat}&lon=${lng}`
        );

        if (!response.ok) {
          throw new Error('Failed to fetch raster data');
        }

        const data: RasterData = await response.json();
        setClickedData(data);
      } catch (err) {
        console.error('Error fetching raster data:', err);
        setError('No data available at this location');
        setClickedData(null);
      } finally {
        setLoading(false);
      }
    }
  });

  if (!clickPosition) {
    return null;
  }

  return (
    <Popup position={clickPosition} onClose={() => setClickPosition(null)}>
      <div style={{
        minWidth: '250px',
        maxWidth: '300px',
        fontFamily: 'Arial, sans-serif'
      }}>
        <h4 style={{
          margin: '0 0 10px 0',
          fontSize: '16px',
          fontWeight: 'bold',
          borderBottom: '2px solid #4caf50',
          paddingBottom: '5px'
        }}>
          Location Info
        </h4>

        {loading && (
          <div style={{ padding: '10px', textAlign: 'center', color: '#666' }}>
            Loading data...
          </div>
        )}

        {error && (
          <div style={{ padding: '10px', color: '#d32f2f', fontSize: '14px' }}>
            {error}
          </div>
        )}

        {clickedData && !loading && (
          <table style={{
            width: '100%',
            fontSize: '13px',
            borderCollapse: 'collapse'
          }}>
            <tbody>
              <tr style={{ backgroundColor: '#f5f5f5' }}>
                <td style={{ padding: '6px', fontWeight: '600' }}>Coordinates:</td>
                <td style={{ padding: '6px' }}>
                  {clickedData.location.lat.toFixed(5)}°, {clickedData.location.lon.toFixed(5)}°
                </td>
              </tr>

              {clickedData.elevation_m !== null && (
                <tr>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Elevation:</td>
                  <td style={{ padding: '6px' }}>{clickedData.elevation_m} m</td>
                </tr>
              )}

              {clickedData.slope_degrees !== null && (
                <tr style={{ backgroundColor: '#f5f5f5' }}>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Slope:</td>
                  <td style={{ padding: '6px' }}>{clickedData.slope_degrees}°</td>
                </tr>
              )}

              {clickedData.aspect_direction && (
                <tr>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Aspect:</td>
                  <td style={{ padding: '6px' }}>{clickedData.aspect_direction}</td>
                </tr>
              )}

              {clickedData.canopy_height_m !== null && (
                <tr style={{ backgroundColor: '#f5f5f5' }}>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Canopy Height:</td>
                  <td style={{ padding: '6px' }}>{clickedData.canopy_height_m} m</td>
                </tr>
              )}

              {clickedData.biomass_mg_ha !== null && (
                <tr>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Biomass:</td>
                  <td style={{ padding: '6px' }}>{clickedData.biomass_mg_ha} Mg/ha</td>
                </tr>
              )}

              {clickedData.temperature_c !== null && (
                <tr style={{ backgroundColor: '#f5f5f5' }}>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Temperature:</td>
                  <td style={{ padding: '6px' }}>{clickedData.temperature_c}°C</td>
                </tr>
              )}

              {clickedData.precipitation_mm !== null && (
                <tr>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Precipitation:</td>
                  <td style={{ padding: '6px' }}>{clickedData.precipitation_mm} mm/year</td>
                </tr>
              )}

              {clickedData.forest_type_class !== null && (
                <tr style={{ backgroundColor: '#f5f5f5' }}>
                  <td style={{ padding: '6px', fontWeight: '600' }}>Forest Type:</td>
                  <td style={{ padding: '6px' }}>Class {clickedData.forest_type_class}</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </Popup>
  );
};
