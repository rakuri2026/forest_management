import React, { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { AvailableBlock, CompartmentPreview } from './types';
import BaseMapSelector from '../MapCreation/BaseMapSelector';

interface SplitPreviewMapProps {
  block: AvailableBlock;
  compartments: CompartmentPreview[];
  onCompartmentClick?: (compartment: CompartmentPreview) => void;
}

const COMPARTMENT_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

function getCompartmentColor(index: number): string {
  return COMPARTMENT_COLORS[index % COMPARTMENT_COLORS.length];
}

function MapController({ geometry }: { geometry: GeoJSON.Polygon }) {
  const map = useMap();

  useEffect(() => {
    try {
      const layer = L.geoJSON(geometry);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [50, 50] });
      }
    } catch (e) {
      console.error('Error fitting bounds:', e);
    }
  }, [geometry, map]);

  return null;
}

export function SplitPreviewMap({
  block,
  compartments,
  onCompartmentClick,
}: SplitPreviewMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const getGeometryCenter = (geometry: GeoJSON.Polygon): [number, number] => {
    try {
      const layer = L.geoJSON(geometry);
      const bounds = layer.getBounds();
      return bounds.getCenter();
    } catch {
      return [27.7172, 85.3240];
    }
  };

  const center = getGeometryCenter(block.geometry);

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <h4 className="text-sm font-medium text-gray-700">Preview Map</h4>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>Parent Block:</span>
          <span className="inline-block w-4 h-4 rounded border border-green-600 bg-green-100"></span>
          <span>Compartments:</span>
          {compartments.slice(0, 3).map((_, idx) => (
            <span
              key={idx}
              className="inline-block w-4 h-4 rounded"
              style={{ backgroundColor: getCompartmentColor(idx) }}
            ></span>
          ))}
          {compartments.length > 3 && (
            <span>+{compartments.length - 3} more</span>
          )}
        </div>
      </div>

      <div className="h-[400px] rounded-lg overflow-hidden border border-gray-300">
        <MapContainer
          center={center}
          zoom={15}
          style={{ height: '100%', width: '100%' }}
          ref={mapRef}
          whenReady={() => setMapReady(true)}
        >
          <BaseMapSelector />

          {/* Parent block boundary */}
          <GeoJSON
            data={block.geometry}
            style={{
              color: '#10b981',
              weight: 3,
              fillOpacity: 0.1,
              dashArray: '5, 5',
            }}
          />

          {/* Compartments */}
          {compartments.map((comp, index) => (
            <GeoJSON
              key={comp.name}
              data={comp.geometry}
              style={{
                color: getCompartmentColor(index),
                weight: 2,
                fillOpacity: 0.35,
                fillColor: getCompartmentColor(index),
              }}
              eventHandlers={{
                click: () => onCompartmentClick?.(comp),
              }}
            />
          ))}

          {/* Labels for compartments */}
          {mapReady &&
            compartments.map((comp, index) => {
              try {
                const layer = L.geoJSON(comp.geometry);
                const bounds = layer.getBounds();
                const center = bounds.getCenter();

                const icon = L.divIcon({
                  className: 'compartment-label',
                  html: `<div style="
                    font-size: 12px;
                    font-weight: bold;
                    color: white;
                    text-shadow: 1px 1px 2px black, -1px -1px 2px black, 1px -1px 2px black, -1px 1px 2px black;
                    white-space: nowrap;
                  ">
                    ${comp.name} (${comp.area_hectares.toFixed(1)} ha)
                  </div>`,
                  iconAnchor: [40, 10],
                });

                return <Marker position={center} icon={icon} key={`label-${comp.name}`} />;
              } catch {
                return null;
              }
            })}

          <MapController geometry={block.geometry} />
        </MapContainer>
      </div>

      <div className="text-xs text-gray-500 text-center">
        Click on a compartment to see details • Zoom and pan to inspect
      </div>
    </div>
  );
}

function Marker({ position, icon }: { position: [number, number]; icon: L.DivIcon }) {
  const map = useMap();
  const markerRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!markerRef.current) {
      markerRef.current = L.marker(position, { icon }).addTo(map);
    }
    return () => {
      if (markerRef.current) {
        map.removeLayer(markerRef.current);
        markerRef.current = null;
      }
    };
  }, [map, position, icon]);

  return null;
}
