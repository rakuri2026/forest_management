import React, { useEffect, useMemo } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';
import { GPSPoint } from '../../utils/gpsUtils';

export type LabelMode = 'sn' | 'description' | 'both' | 'none';

interface GPSPointLayerProps {
  points: GPSPoint[];
  visible: boolean;
  labelMode: LabelMode;
  pointSize?: number; // 20-32px
  selectedPointId?: string;
  onPointClick?: (point: GPSPoint) => void;
  showDescriptionField?: boolean; // Toggle for description field
  additionalFieldsVisible?: Record<string, boolean>; // Toggle for additional fields
}

const GPSPointLayer: React.FC<GPSPointLayerProps> = ({
  points,
  visible,
  labelMode,
  pointSize = 24,
  selectedPointId,
  onPointClick,
  showDescriptionField = false,
  additionalFieldsVisible = {},
}) => {
  const map = useMap();
  const layerGroupRef = React.useRef<L.LayerGroup | null>(null);

  // Determine if point is selected
  const isSelected = (point: GPSPoint): boolean => {
    return point.id === selectedPointId;
  };

  // Get color based on selection status
  const getStatusColor = (selected: boolean): { border: string; bg: string } => {
    if (selected) {
      return { border: '#F59E0B', bg: 'transparent' }; // Yellow/Amber border, transparent bg (selected)
    }
    return { border: '#FFFFFF', bg: 'transparent' }; // White border, transparent bg (default)
  };

  // Create custom marker icon
  const createMarkerIcon = (point: GPSPoint): L.DivIcon => {
    const selected = isSelected(point);
    const colors = getStatusColor(selected);

    // Determine label text
    let labelText = '';
    if (labelMode === 'sn' || labelMode === 'both') {
      labelText = String(point.sn ?? (point.order !== undefined ? point.order + 1 : '?'));
    }

    let descText = '';
    if ((labelMode === 'description' || labelMode === 'both') && showDescriptionField) {
      descText = point.description || '';
    }

    // Additional fields to display
    const additionalFieldsHtml = point.additionalFields
      ? Object.entries(point.additionalFields)
          .filter(([key]) => additionalFieldsVisible[key])
          .map(([key, value]) => `
            <div style="
              font-size: 9px;
              color: #FFFFFF;
              text-shadow:
                -1px -1px 0 #000,
                1px -1px 0 #000,
                -1px 1px 0 #000,
                1px 1px 0 #000,
                0 0 2px #000;
            ">
              ${key}: ${value}
            </div>
          `)
          .join('')
      : '';

    const html = `
      <div style="
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        cursor: pointer;
        opacity: 0.6;
      ">
        <!-- Circular Marker -->
        <div style="
          background-color: ${colors.bg};
          width: ${pointSize}px;
          height: ${pointSize}px;
          border-radius: 50%;
          border: 3px solid ${colors.border};
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: ${pointSize > 28 ? '13px' : '12px'};
          color: #FFFFFF;
          text-shadow:
            -1px -1px 0 #000,
            1px -1px 0 #000,
            -1px 1px 0 #000,
            1px 1px 0 #000,
            0 0 3px #000,
            0 0 6px rgba(0,0,0,0.8);
          box-shadow:
            0 0 0 1px rgba(0,0,0,0.8),
            0 2px 8px rgba(0,0,0,0.6),
            inset 0 0 0 1px rgba(255,255,255,0.3);
          ${selected ? 'animation: pulse 1.5s infinite;' : ''}
        ">
          ${labelMode !== 'none' && labelMode !== 'description' ? labelText : ''}
        </div>

        <!-- Description below marker -->
        ${descText && (labelMode === 'description' || labelMode === 'both') ? `
          <div style="
            margin-top: 3px;
            font-size: 10px;
            color: #FFFFFF;
            font-weight: 600;
            text-shadow:
              -1px -1px 0 #000,
              1px -1px 0 #000,
              -1px 1px 0 #000,
              1px 1px 0 #000,
              0 0 3px #000,
              0 0 5px rgba(0,0,0,0.7);
            padding: 2px 6px;
            border-radius: 3px;
            max-width: 80px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            background-color: rgba(0, 0, 0, 0.3);
          ">
            ${descText}
          </div>
        ` : ''}

        <!-- Additional fields -->
        ${additionalFieldsHtml ? `
          <div style="
            margin-top: 2px;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 3px 6px;
            border-radius: 3px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
          ">
            ${additionalFieldsHtml}
          </div>
        ` : ''}
      </div>

      <style>
        @keyframes pulse {
          0%, 100% {
            transform: scale(1);
            opacity: 1;
          }
          50% {
            transform: scale(1.15);
            opacity: 0.85;
          }
        }
      </style>
    `;

    return new L.DivIcon({
      className: 'custom-gps-marker',
      html,
      iconSize: [pointSize + 10, pointSize + 30], // Extra space for description
      iconAnchor: [pointSize / 2 + 5, pointSize / 2],
      popupAnchor: [0, -(pointSize / 2)],
    });
  };

  // Create popup content
  const createPopupContent = (point: GPSPoint): string => {
    const fields = [
      `<strong>Point ${point.sn ?? (point.order !== undefined ? point.order + 1 : '?')}</strong>`,
      `Lat: ${point.latitude.toFixed(6)}`,
      `Lon: ${point.longitude.toFixed(6)}`,
    ];

    if (point.description) {
      fields.push(`Description: ${point.description}`);
    }

    if (point.elevation) {
      fields.push(`Elevation: ${point.elevation.toFixed(1)}m`);
    }

    if (point.additionalFields) {
      Object.entries(point.additionalFields).forEach(([key, value]) => {
        fields.push(`${key}: ${value}`);
      });
    }

    return fields.join('<br/>');
  };

  // Auto-zoom to GPS points when they are first loaded
  useEffect(() => {
    if (!map || points.length === 0) return;

    // Create bounds from all GPS points
    const bounds = L.latLngBounds(points.map(p => [p.latitude, p.longitude]));

    // Zoom to bounds with padding
    map.fitBounds(bounds, {
      padding: [50, 50],
      maxZoom: 16 // Don't zoom in too much
    });
  }, [map, points.length]); // Only run when points are first loaded or count changes

  // Render markers on map
  useEffect(() => {
    if (!map) return;

    // Remove existing layer if any
    if (layerGroupRef.current) {
      map.removeLayer(layerGroupRef.current);
      layerGroupRef.current = null;
    }

    // Don't render if not visible or no points
    if (!visible || points.length === 0) return;

    // Create new layer group
    const layerGroup = new L.LayerGroup();

    points.forEach(point => {
      const marker = L.marker([point.latitude, point.longitude], {
        icon: createMarkerIcon(point),
      });

      // Add popup
      marker.bindPopup(createPopupContent(point));

      // Add click handler
      if (onPointClick) {
        marker.on('click', () => onPointClick(point));
      }

      marker.addTo(layerGroup);
    });

    layerGroup.addTo(map);
    layerGroupRef.current = layerGroup;

    // Cleanup
    return () => {
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }
    };
  }, [
    map,
    points,
    visible,
    labelMode,
    pointSize,
    selectedPointId,
    showDescriptionField,
    additionalFieldsVisible,
  ]);

  return null; // This is a layer component, doesn't render DOM
};

export default GPSPointLayer;
