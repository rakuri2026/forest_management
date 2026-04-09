import React from 'react';
import { TileLayer } from 'react-leaflet';

interface BaseMapSelectorProps {
  baseMap: string;
}

/**
 * BaseMapSelector provides base layer tiles with switchable basemaps
 * Usage: Add this component inside MapContainer alongside other map elements
 */
export const BaseMapSelector: React.FC<BaseMapSelectorProps> = ({ baseMap = 'osm' }) => {
  const getTileUrl = () => {
    switch (baseMap) {
      case 'satellite':
        return 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      case 'terrain':
        return 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png';
      case 'osm':
      default:
        return 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    }
  };

  const getAttribution = () => {
    switch (baseMap) {
      case 'satellite':
        return '&copy; Esri';
      case 'terrain':
        return '&copy; OpenStreetMap contributors';
      case 'osm':
      default:
        return '&copy; OpenStreetMap contributors';
    }
  };

  const getMaxZoom = () => {
    switch (baseMap) {
      case 'terrain':
        return 17;
      default:
        return 19;
    }
  };

  return (
    <TileLayer
      attribution={getAttribution()}
      url={getTileUrl()}
      maxZoom={getMaxZoom()}
    />
  );
};

export default BaseMapSelector;