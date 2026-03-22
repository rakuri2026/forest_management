import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Marker, LayersControl, Popup, Tooltip, FeatureGroup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const { BaseLayer, Overlay } = LayersControl;

// Component to handle auto-zoom to boundaries
function AutoZoom({ forestBoundary, extentBoundary }: { forestBoundary: any; extentBoundary?: any }) {
  const map = useMap();

  useEffect(() => {
    if (forestBoundary || extentBoundary) {
      try {
        const bounds = L.latLngBounds([]);

        // Add forest boundary coordinates to bounds
        if (forestBoundary && forestBoundary.coordinates) {
          const coords = forestBoundary.type === 'Polygon'
            ? forestBoundary.coordinates[0]
            : forestBoundary.coordinates[0][0];
          coords.forEach((coord: number[]) => {
            bounds.extend([coord[1], coord[0]]);
          });
        }

        // Add extent boundary coordinates to bounds
        if (extentBoundary && extentBoundary.coordinates) {
          const coords = extentBoundary.type === 'Polygon'
            ? extentBoundary.coordinates[0]
            : extentBoundary.coordinates[0][0];
          coords.forEach((coord: number[]) => {
            bounds.extend([coord[1], coord[0]]);
          });
        }

        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [50, 50] });
        }
      } catch (e) {
        console.error('Error calculating bounds:', e);
      }
    }
  }, [map, forestBoundary, extentBoundary]);

  return null;
}

interface UserGroupMapVisualizationProps {
  calculationId: string;
  forestBoundary: any;
  extentBoundary?: any;
  settlements?: any[];
  buildings?: any[];
  poiData?: any;
}

export const UserGroupMapVisualization = forwardRef(function UserGroupMapVisualization({
  calculationId,
  forestBoundary,
  extentBoundary,
  settlements = [],
  buildings = [],
  poiData = null
}: UserGroupMapVisualizationProps, ref) {
  const mapInstanceRef = useRef<L.Map | null>(null);

  useImperativeHandle(ref, () => ({
    getMap: () => mapInstanceRef.current,
    invalidateSize: () => mapInstanceRef.current?.invalidateSize(),
    fitBounds: (bounds: L.LatLngBoundsExpression, options?: L.FitBoundsOptions) => {
      mapInstanceRef.current?.fitBounds(bounds, options);
    },
    getBounds: () => mapInstanceRef.current?.getBounds() || null
  }));
  // Custom house icon for settlements
  const houseIcon = L.divIcon({
    html: `<div style="font-size: 24px; text-align: center;">🏠</div>`,
    className: 'settlement-marker',
    iconSize: [30, 30],
    iconAnchor: [15, 30],
    popupAnchor: [0, -30]
  });

  // POI icons (blue pin instead of red)
  const poiIcon = L.divIcon({
    html: `<div style="font-size: 16px; filter: hue-rotate(200deg);">📍</div>`,
    className: 'poi-marker',
    iconSize: [20, 20],
    iconAnchor: [10, 20]
  });

  const educationIcon = L.divIcon({
    html: `<div style="font-size: 16px;">🏫</div>`,
    className: 'education-marker',
    iconSize: [20, 20],
    iconAnchor: [10, 20]
  });

  const healthIcon = L.divIcon({
    html: `<div style="font-size: 16px;">🏥</div>`,
    className: 'health-marker',
    iconSize: [20, 20],
    iconAnchor: [10, 20]
  });

  // Calculate map center from forest boundary
  const getMapCenter = (): [number, number] => {
    if (forestBoundary && forestBoundary.coordinates) {
      // Simple centroid calculation for polygon
      try {
        const coords = forestBoundary.type === 'Polygon'
          ? forestBoundary.coordinates[0]
          : forestBoundary.coordinates[0][0];

        const lats = coords.map((c: number[]) => c[1]);
        const lngs = coords.map((c: number[]) => c[0]);

        const centerLat = (Math.max(...lats) + Math.min(...lats)) / 2;
        const centerLng = (Math.max(...lngs) + Math.min(...lngs)) / 2;

        return [centerLat, centerLng];
      } catch (e) {
        return [28.3949, 84.1240]; // Nepal center fallback
      }
    }
    return [28.3949, 84.1240]; // Nepal center fallback
  };

  return (
    <div className="user-group-map-container" style={{ height: '600px', width: '100%', marginTop: '20px' }}>
      <MapContainer
        center={getMapCenter()}
        zoom={12}
        preferCanvas={true}
        style={{ height: '100%', width: '100%' }}
        ref={(map) => { if (map) mapInstanceRef.current = map; }}
      >
        {/* Auto-zoom to fit boundaries */}
        <AutoZoom forestBoundary={forestBoundary} extentBoundary={extentBoundary} />

        <LayersControl position="topright">
          {/* TERRAIN BASE MAP - DEFAULT (OpenTopoMap) */}
          <BaseLayer checked name="Terrain">
            <TileLayer
              attribution='Map data: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: © <a href="https://opentopomap.org">OpenTopoMap</a>'
              url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
              maxZoom={17}
            />
          </BaseLayer>

          {/* ESRI Terrain Alternative */}
          <BaseLayer name="ESRI Terrain">
            <TileLayer
              attribution='© <a href="https://www.esri.com/">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}"
              maxZoom={13}
            />
          </BaseLayer>

          {/* Street Map */}
          <BaseLayer name="Street Map">
            <TileLayer
              attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              maxZoom={19}
            />
          </BaseLayer>

          {/* Satellite */}
          <BaseLayer name="Satellite">
            <TileLayer
              attribution='© <a href="https://www.esri.com/">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />
          </BaseLayer>

          {/* Forest Boundary - Green with 40% transparency */}
          {forestBoundary && (
            <Overlay checked name="Community Forest Boundary">
              <GeoJSON
                data={forestBoundary}
                style={{
                  fillColor: '#00ff00',
                  fillOpacity: 0.4,
                  color: '#00aa00',
                  weight: 2
                }}
              />
            </Overlay>
          )}

          {/* User Group Extent - Blue dashed */}
          {extentBoundary && (
            <Overlay checked name="User Group Extent">
              <GeoJSON
                data={extentBoundary}
                style={{
                  fillColor: 'transparent',
                  color: '#0000ff',
                  weight: 3,
                  dashArray: '5, 5'
                }}
              />
            </Overlay>
          )}

          {/* Buildings - Small red circles */}
          {buildings.length > 0 && (
            <Overlay checked name="Buildings">
              <FeatureGroup>
                {buildings.map((building, idx) => (
                  <CircleMarker
                    key={`building-${idx}`}
                    center={[building.lat, building.lon]}
                    radius={2}
                    pathOptions={{
                      fillColor: '#ff0000',
                      fillOpacity: 0.7,
                      color: '#cc0000',
                      weight: 0.5
                    }}
                  >
                    {building.area && (
                      <Popup>
                        <div>
                          <strong>Building</strong><br />
                          Area: {building.area.toFixed(2)} m²
                        </div>
                      </Popup>
                    )}
                  </CircleMarker>
                ))}
              </FeatureGroup>
            </Overlay>
          )}

          {/* Settlements - House icons with permanent plain text labels */}
          {settlements.length > 0 && (
            <Overlay checked name="Settlements">
              <FeatureGroup>
                {settlements.map((settlement, idx) => (
                  <Marker
                    key={`settlement-${idx}`}
                    position={[settlement.lat, settlement.lon]}
                    icon={houseIcon}
                  >
                    <Tooltip
                      permanent
                      direction="bottom"
                      className="settlement-label-plain"
                      opacity={1}
                    >
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 'bold',
                        color: '#000',
                        textShadow: '1px 1px 2px white, -1px -1px 2px white, 1px -1px 2px white, -1px 1px 2px white'
                      }}>
                        {settlement.settlement_name}
                      </span>
                    </Tooltip>
                    <Popup>
                      <div>
                        <strong>{settlement.settlement_name}</strong><br />
                        Buildings: {settlement.building_count}<br />
                        Total Area: {settlement.total_area_m2?.toFixed(2)} m²<br />
                        Direction: {settlement.direction_from_forest}
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </FeatureGroup>
            </Overlay>
          )}

          {/* POI Layers */}
          {poiData && poiData.poi && poiData.poi.length > 0 && (
            <Overlay name="Points of Interest (POI)">
              <FeatureGroup>
                {poiData.poi.map((poi: any, idx: number) => (
                  <Marker
                    key={`poi-${idx}`}
                    position={[poi.lat, poi.lon]}
                    icon={poiIcon}
                  >
                    <Tooltip direction="top">
                      <div style={{ fontSize: '11px', fontWeight: 'bold' }}>
                        {poi.name}
                      </div>
                    </Tooltip>
                    <Popup>
                      <div>
                        <strong>{poi.name}</strong><br />
                        Type: {poi.type || 'N/A'}
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </FeatureGroup>
            </Overlay>
          )}

          {/* Education Facilities */}
          {poiData && poiData.education && poiData.education.length > 0 && (
            <Overlay name="Education Facilities">
              <FeatureGroup>
                {poiData.education.map((edu: any, idx: number) => (
                  <Marker
                    key={`edu-${idx}`}
                    position={[edu.lat, edu.lon]}
                    icon={educationIcon}
                  >
                    <Tooltip direction="top">
                      <div style={{ fontSize: '11px', fontWeight: 'bold' }}>
                        {edu.name}
                      </div>
                    </Tooltip>
                    <Popup>
                      <div>
                        <strong>{edu.name}</strong>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </FeatureGroup>
            </Overlay>
          )}

          {/* Health Facilities */}
          {poiData && poiData.health && poiData.health.length > 0 && (
            <Overlay name="Health Facilities">
              <FeatureGroup>
                {poiData.health.map((health: any, idx: number) => (
                  <Marker
                    key={`health-${idx}`}
                    position={[health.lat, health.lon]}
                    icon={healthIcon}
                  >
                    <Tooltip direction="top">
                      <div style={{ fontSize: '11px', fontWeight: 'bold' }}>
                        {health.name}
                      </div>
                    </Tooltip>
                    <Popup>
                      <div>
                        <strong>{health.name}</strong>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </FeatureGroup>
            </Overlay>
          )}

          {/* Rivers - Checked by default */}
          {poiData && poiData.rivers && poiData.rivers.length > 0 && (
            <Overlay checked name="Rivers">
              <FeatureGroup>
                {poiData.rivers.map((river: any, idx: number) => (
                  <GeoJSON
                    key={`river-${idx}`}
                    data={river.geometry}
                    style={{
                      color: '#0066ff',
                      weight: 2,
                      opacity: 0.8
                    }}
                  >
                    <Tooltip direction="top">
                      <div style={{ fontSize: '11px', fontWeight: 'bold' }}>
                        {river.name}
                      </div>
                    </Tooltip>
                    <Popup>
                      <div>
                        <strong>{river.name}</strong>
                      </div>
                    </Popup>
                  </GeoJSON>
                ))}
              </FeatureGroup>
            </Overlay>
          )}
        </LayersControl>
      </MapContainer>
    </div>
  );
});
