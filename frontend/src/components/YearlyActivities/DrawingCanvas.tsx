import React, { useRef, useState, useEffect } from 'react';
import { MapContainer, TileLayer, useMap, useMapEvents, Marker, Polyline, Polygon, GeoJSON, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import * as turf from '@turf/turf';
import { Button, Radio, Space, List, Card, message, Popconfirm, Input, Divider } from 'antd';
import { yearlyActivitiesApi } from '../../services/api';

interface BlockSubArea {
  id: string;
  name: string;
  type: 'block' | 'sub_area';
  geometry?: any;
}

interface YearData {
  year: number;
}

interface DrawingCanvasProps {
  calculationId: string;
  activityId: string;
  featureType: 'point' | 'line' | 'polygon';
  onFeatureTypeChange: (type: 'point' | 'line' | 'polygon') => void;
  drawnFeatures: any[];
  onFeaturesChange: () => void;
  blocksWithSubAreas?: BlockSubArea[];
  availableYears?: YearData[];
  baseMap?: 'satellite' | 'osm' | 'topo';
  boundaryGeometry?: any;
  blockLayers?: any[];
  subAreaLayers?: any[];
}

const BASE_MAPS = {
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri'
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap'
  },
  topo: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap'
  }
};

const DrawingCanvas: React.FC<DrawingCanvasProps> = ({
  calculationId,
  activityId,
  featureType,
  onFeatureTypeChange,
  drawnFeatures,
  onFeaturesChange,
  blocksWithSubAreas = [],
  availableYears = [],
  baseMap = 'satellite',
  boundaryGeometry,
  blockLayers = [],
  subAreaLayers = [],
}) => {
  const mapRef = useRef<L.Map | null>(null);
  const [drawingMode, setDrawingMode] = useState(true);
  const [currentPoints, setCurrentPoints] = useState<L.LatLng[]>([]);
  const [tempLayer, setTempLayer] = useState<L.Polyline | L.Polygon | L.Marker | null>(null);
  const [featureName, setFeatureName] = useState('');
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  
  // Live measurements state
  const [currentLength, setCurrentLength] = useState(0);
  const [currentArea, setCurrentArea] = useState(0);
  const [measurementUnit, setMeasurementUnit] = useState<'metric' | 'imperial'>('metric');
  const [editMode, setEditMode] = useState<'draw' | 'edit'>('draw');
  
  // Feature selection for editing
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null);
  const [editingFeature, setEditingFeature] = useState<any | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editingFeatureId, setEditingFeatureId] = useState<string | null>(null);
  const [editingLayers, setEditingLayers] = useState<Map<string, any>>(new Map());
  const featureLayersRef = useRef<Map<string, L.Layer>>(new Map());
  
  // Vertex editing state (for draggable vertices)
  const [editingVertices, setEditingVertices] = useState<L.LatLng[]>([]);
  const [vertexBeingDragged, setVertexBeingDragged] = useState<number | null>(null);
  
  // Calculate live geodesic measurements using turf.js
  const calculateMeasurements = (points: L.LatLng[], type: string) => {
    if (points.length < 2) {
      setCurrentLength(0);
      setCurrentArea(0);
      return;
    }
    
    if (type === 'line' && points.length >= 2) {
      // Use turf.js for geodesic length
      const coords = points.map(p => [p.lng, p.lng] as [number, number]);
      const lineCoords = points.map(p => [p.lng, p.lat] as [number, number]);
      const lineFeature = turf.lineString(lineCoords);
      const length = turf.length(lineFeature, { units: 'meters' });
      setCurrentLength(length);
    } else if (type === 'polygon' && points.length >= 3) {
      // Use turf.js for geodesic area (spherical)
      const polyCoords = [...points.map(p => [p.lng, p.lat] as [number, number])];
      // Close the polygon if needed
      if (polyCoords.length > 0) {
        const first = polyCoords[0];
        const last = polyCoords[polyCoords.length - 1];
        if (first[0] !== last[0] || first[1] !== last[1]) {
          polyCoords.push([...first]);
        }
      }
      const polygonFeature = turf.polygon([polyCoords]);
      const area = turf.area(polygonFeature); // Returns area in square meters
      setCurrentArea(area);
    }
  };
  
  const formatLength = (meters: number) => {
    if (measurementUnit === 'imperial') {
      const feet = meters * 3.28084;
      return `${feet.toFixed(1)} ft`;
    }
    return `${meters.toFixed(1)} m`;
  };
  
  const formatArea = (sqMeters: number) => {
    const sqMetersDisplay = sqMeters;
    const hectaresDisplay = sqMeters / 10000;
    const acresDisplay = sqMeters * 0.000247105;
    
    if (measurementUnit === 'imperial') {
      return `${acresDisplay.toFixed(2)} acres`;
    }
    return `${sqMetersDisplay.toFixed(1)} m² (${hectaresDisplay.toFixed(2)} ha)`;
  };

  const handleMapClick = (e: L.LeafletMouseEvent) => {
    // Handle edit mode clicks
    if (editingFeatureId) {
      handleMapClickForEdit(e);
      return;
    }
    
    if (!featureName || !selectedYear || !drawingMode) return;
    const latlng = e.latlng;
    const newPoints = [...currentPoints, latlng];
    setCurrentPoints(newPoints);
    
    // Calculate live measurements
    calculateMeasurements(newPoints, featureType);

    if (featureType === 'point') {
      createPoint(latlng);
    }
  };

  const createPoint = async (latlng: L.LatLng) => {
    try {
      const geometry = JSON.stringify({
        type: 'Point',
        coordinates: [latlng.lng, latlng.lat]
      });

      await yearlyActivitiesApi.createDrawnFeature(activityId, {
        feature_type: 'point',
        geometry,
        properties: { label: featureName || `Point at ${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`, name: featureName, year: selectedYear }
      });

      message.success('Point added');
      onFeaturesChange();
      setCurrentPoints([]);
      setFeatureName('');
      setSelectedYear(null);
    } catch (error: any) {
      message.error('Failed to add point');
    }
  };

  const handleDoubleClick = async (e: any) => {
    // Stop editing when double-clicking (for line/polygon vertices)
    if (editingFeatureId) {
      handleStopEdit();
      return;
    }
    
    if (!featureName || !selectedYear || currentPoints.length < 2) return;
    e.originalEvent?.preventDefault();

    if (featureType === 'line') {
      await createLine();
    } else if (featureType === 'polygon') {
      await createPolygon();
    }
  };

  const createLine = async () => {
    try {
      const geometry = JSON.stringify({
        type: 'LineString',
        coordinates: currentPoints.map(p => [p.lng, p.lat])
      });

      const length = currentPoints.reduce((acc, p, i) => {
        if (i === 0) return 0;
        return acc + currentPoints[i - 1].distanceTo(p);
      }, 0);

await yearlyActivitiesApi.createDrawnFeature(activityId, {
          feature_type: 'line',
          geometry,
          properties: { length_m: Math.round(length), name: featureName, year: selectedYear }
        });

      message.success('Line added');
      onFeaturesChange();
      setCurrentPoints([]);
      setFeatureName('');
      setSelectedYear(null);
    } catch (error: any) {
      message.error('Failed to add line');
    }
  };

  const createPolygon = async () => {
    try {
      const coords = currentPoints.map(p => [p.lng, p.lat]);
      const firstPoint = currentPoints[0];
      const lastPoint = currentPoints[currentPoints.length - 1];
      if (firstPoint.distanceTo(lastPoint) > 1) {
        coords.push([firstPoint.lng, firstPoint.lat]);
      }

      const polygon = L.polygon(currentPoints.map(p => [p.lat, p.lng]));
      const bounds = polygon.getBounds();
      const latSpan = bounds.getNorthEast().lat - bounds.getSouthWest().lat;
      const lngSpan = bounds.getNorthEast().lng - bounds.getSouthWest().lng;
      const centerLat = bounds.getSouthWest().lat + latSpan / 2;
      const metersPerDegreeLat = 111320;
      const metersPerDegreeLng = 111320 * Math.cos(centerLat * Math.PI / 180);
      const areaSqM = Math.abs(latSpan * metersPerDegreeLat) * Math.abs(lngSpan * metersPerDegreeLng);

      const geometry = JSON.stringify({
        type: 'Polygon',
        coordinates: [coords]
      });

      console.log('[createPolygon] saving geometry:', geometry);

      await yearlyActivitiesApi.createDrawnFeature(activityId, {
        feature_type: 'polygon',
        geometry,
        properties: { area_sqm: Math.round(areaSqM), name: featureName, year: selectedYear }
      });

      message.success('Polygon added');
      onFeaturesChange();
      setCurrentPoints([]);
      setFeatureName('');
      setSelectedYear(null);
    } catch (error: any) {
      console.error('[createPolygon] error:', error);
      message.error('Failed to add polygon');
    }
  };

  const handleDeleteFeature = async (featureId: string) => {
    try {
      await yearlyActivitiesApi.deleteDrawnFeature(activityId, featureId);
      message.success('Feature deleted');
      onFeaturesChange();
    } catch (error: any) {
      message.error('Failed to delete feature');
    }
  };

  const handleCopyFeature = async (targetYear: number) => {
    if (!editingFeature) return;
    try {
      await yearlyActivitiesApi.createDrawnFeature(activityId, {
        feature_type: editingFeature.feature_type,
        geometry: editingFeature.geometry,
        properties: { 
          ...editingFeature.properties,
          name: `${editingFeature.properties?.name || editingFeature.feature_type} (Y${targetYear})`,
          year: targetYear
        }
      });
      message.success(`Copied to Year ${targetYear}`);
      onFeaturesChange();
    } catch (error: any) {
      message.error('Failed to copy feature');
    }
  };

  const handleStartEdit = (feature: any) => {
    setEditingFeatureId(feature.id);
    setEditingFeature(feature);
    
    // Initialize editing vertices from existing feature
    const coords = parseGeometry(feature.geometry, feature.feature_type);
    if (coords) {
      if (feature.feature_type === 'polygon') {
        // For polygon, coords[0] contains the ring
        setEditingVertices(coords[0] || coords);
      } else {
        setEditingVertices(coords);
      }
    }
    
    message.info('Drag vertices to move. Right-click vertex to delete.');
  };

  const handleStopEdit = () => {
    setEditingFeatureId(null);
    setEditingFeature(null);
    setEditingVertices([]);
    message.info('Edit mode exited');
  };

  // Handle vertex drag during drawing (draggable markers)
  const handleVertexDrag = (index: number, e: L.DragEndEvent) => {
    const newLatLng = e.target.getLatLng();
    const newPoints = [...currentPoints];
    newPoints[index] = newLatLng;
    setCurrentPoints(newPoints);
    calculateMeasurements(newPoints, featureType);
  };

  // Handle right-click on vertex to delete it
  const handleVertexDelete = (index: number) => {
    // Prevent breaking shapes - minimum points
    if (featureType === 'polygon' && currentPoints.length <= 3) {
      message.warning('Polygon must have at least 3 vertices');
      return;
    }
    if (featureType === 'line' && currentPoints.length <= 2) {
      message.warning('Line must have at least 2 vertices');
      return;
    }
    
    const newPoints = currentPoints.filter((_, i) => i !== index);
    setCurrentPoints(newPoints);
    calculateMeasurements(newPoints, featureType);
    message.success('Vertex deleted (right-click)');
  };

  // Handle vertex drag for editing existing features
  const handleEditingVertexDrag = (index: number, e: L.DragEndEvent) => {
    const newLatLng = e.target.getLatLng();
    const newVertices = [...editingVertices];
    newVertices[index] = newLatLng;
    setEditingVertices(newVertices);
    
    if (featureType === 'line' || featureType === 'polygon') {
      calculateMeasurements(newVertices, featureType);
    }
  };

  // Handle right-click on editing vertex
  const handleEditingVertexDelete = (index: number) => {
    if (!editingFeatureId || !editingFeature) return;
    
    const minPoints = featureType === 'polygon' ? 4 : 3;
    if (editingVertices.length <= minPoints) {
      message.warning(`Cannot delete - ${featureType} needs at least ${minPoints - 1} vertices`);
      return;
    }

    const newVertices = editingVertices.filter((_, i) => i !== index);
    setEditingVertices(newVertices);
    
    // Update the feature on the server
    const coords = newVertices.map(p => [p.lng, p.lat]);
    let newGeometry: string;
    
    if (featureType === 'polygon') {
      coords.push(coords[0]); // Close polygon
      newGeometry = JSON.stringify({
        type: 'Polygon',
        coordinates: [coords]
      });
    } else {
      newGeometry = JSON.stringify({
        type: 'LineString',
        coordinates: coords
      });
    }
    
    yearlyActivitiesApi.updateDrawnFeature(activityId, editingFeatureId, {
      geometry: newGeometry,
      feature_type: featureType
    }).then(() => {
      message.success('Vertex deleted and feature updated');
      onFeaturesChange();
    }).catch((err) => {
      console.error('Error updating feature:', err);
      message.error('Failed to delete vertex');
      // Restore the vertex
      setEditingVertices(editingVertices);
    });
  };

const handleMapClickForEdit = (e: L.LeafletMouseEvent) => {
    if (!editingFeatureId || !editingFeature) return;
    const latlng = e.latlng;
    
    if (editingFeature.feature_type === 'point') {
      handleMovePoint(editingFeatureId, latlng, 0);
    } else if (editingFeature.feature_type === 'line') {
      const coords = parseGeometry(editingFeature.geometry, editingFeature.feature_type);
      if (!coords) return;
      
      const newCoord = [latlng.lng, latlng.lat];
      const coordsLngLat = coords.map((c: number[]) => [c[1], c[0]]);
      coordsLngLat.push(newCoord);
      const newGeometry = JSON.stringify({
        type: 'LineString',
        coordinates: coordsLngLat
      });
      
      yearlyActivitiesApi.updateDrawnFeature(activityId, editingFeatureId, {
        geometry: newGeometry,
        feature_type: 'line'
      }).then(() => {
        message.success('Vertex added to line');
        onFeaturesChange();
      }).catch((err) => {
        console.error('[handleMapClickForEdit] error:', err);
        message.error('Failed to add vertex');
      });
} else {
      message.info('Polygon edit not yet supported - delete and redraw');
    }
  };

  // Parse WKT or GeoJSON to coordinates - return [lat, lng] for Leaflet
  const parseGeometry = (geom: string, featureType: string): number[][] | null => {
    if (!geom) return null;
    try {
      const geoJson = JSON.parse(geom);
      if (geoJson && geoJson.coordinates) {
        const coords = geoJson.coordinates;
        if (featureType === 'point') {
          return [[coords[1], coords[0]]];
        } else if (featureType === 'polygon') {
          const ring = coords[0] || coords;
          return ring.map((c: any) => [c[1], c[0]]);
        } else {
          return coords.map((c: any) => [c[1], c[0]]);
        }
      }
    } catch {
      // ignore
    }
    // Try WKT format
    const upperGeom = geom.toUpperCase();
    if (upperGeom.startsWith('POINT')) {
      const match = geom.match(/POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)/i);
      if (match && match[1] && match[2]) {
        const lng = parseFloat(match[1]);
        const lat = parseFloat(match[2]);
        return [[lat, lng]];
      }
    } else if (upperGeom.startsWith('LINESTRING')) {
      const m = geom.match(/LINESTRING\s*\((.*)\)/i);
      if (m) {
        const coords: any = m[1].split(',').map((c: string) => {
          const parts = c.trim().split(/\s+/).map(Number);
          return parts.length >= 2 ? [parts[1], parts[0]] : null;
        }).filter(Boolean);
        return coords;
      }
    } else if (upperGeom.startsWith('POLYGON')) {
      const m = geom.match(/POLYGON\s*\(\((.*)\)/i);
      if (m) {
        const ring = m[1].split(',').map((c: string) => {
          const parts = c.trim().split(/\s+/).map(Number);
          return parts.length >= 2 ? [parts[1], parts[0]] as number[] : [];
        }) as any;
        return [ring];
      }
    }
    return null;
  };

  // Render block/subarea layers
  const renderBlockLayers = () => {
    return blocksWithSubAreas?.map((block: BlockSubArea, index: number) => {
      if (!block.geometry) return null;
      try {
        const gj = typeof block.geometry === 'string' ? JSON.parse(block.geometry) : block.geometry;
        const coords = gj.type === 'Polygon' ? gj.coordinates[0] : gj.coordinates;
        const latlngs = coords.map((c: number[]) => [c[1], c[0]]);
        return (
          <Polygon
            key={block.id || index}
            positions={latlngs}
            pathOptions={{
              color: block.type === 'block' ? '#2563eb' : '#059669',
              fillColor: block.type === 'block' ? '#2563eb' : '#059669',
              fillOpacity: 0.1,
              weight: 2
            }}
          />
        );
      } catch (e) { return null; }
    });
  };

  // Handle feature click for selection in edit mode
  const handleFeatureClick = (feature: any) => {
    if (editMode === 'edit') {
      setSelectedFeatureId(feature.id);
      setEditingFeature(feature);
      setIsEditing(true);
    }
  };

  const handleMovePoint = async (featureId: string, newLatLng: L.LatLng, pointIndex: number) => {
    try {
      const feature = drawnFeatures.find((f: any) => f.id === featureId);
      if (!feature) return;
      
      const coords = parseGeometry(feature.geometry, feature.feature_type);
      if (!coords) return;
      
      const newCoord = [newLatLng.lng, newLatLng.lat];
      let newGeometry: string;
      
      if (feature.feature_type === 'point') {
        newGeometry = JSON.stringify({
          type: 'Point',
          coordinates: newCoord
        });
      } else if (feature.feature_type === 'line') {
        const coordsLngLat: any = coords.map((c: any) => [c[1], c[0]]);
        coordsLngLat[pointIndex] = newCoord;
        newGeometry = JSON.stringify({
          type: 'LineString',
          coordinates: coordsLngLat
        });
      } else if (feature.feature_type === 'polygon') {
        message.info('Polygon edit not supported - delete and redraw');
        return;
      } else {
        return;
      }
      
      console.log('[handleMovePoint] newGeometry:', newGeometry);
      
      await yearlyActivitiesApi.updateDrawnFeature(activityId, featureId, {
        geometry: newGeometry,
        feature_type: feature.feature_type
      });
      
      message.success('Feature moved');
      onFeaturesChange();
    } catch (error) {
      message.error('Failed to move feature');
    }
  };

  // Render existing features on map
  const renderFeatures = () => {
    return drawnFeatures.map((feature: any, index: number) => {
      const coords = parseGeometry(feature.geometry, feature.feature_type);
      console.log('[renderFeatures] type:', feature.feature_type, 'parsed coords:', coords, 'original:', feature.geometry);
      if (!coords || !coords[0] || coords.length < 2) {
        console.warn('Invalid coords for feature:', feature.id, feature.geometry);
        return null;
      }
      
      const isSelected = selectedFeatureId === feature.id;
      
      try {
        // Show editing indicator for selected feature
      const isBeingEdited = editingFeatureId === feature.id;
      
      if (feature.feature_type === 'point') {
        const lat = coords[0][0];
        const lng = coords[0][1];
        if (isNaN(lat) || isNaN(lng)) return null;
        return (
          <Marker
            key={feature.id || index}
            position={[lat, lng]}
            opacity={isBeingEdited ? 0.5 : 1}
            eventHandlers={{
              click: () => isBeingEdited ? null : handleFeatureClick(feature)
            }}
          />
        );
      } else if (feature.feature_type === 'line') {
        const lineCoords = coords as [number, number][];
        return (
          <>
            <Polyline
              key={`line-${feature.id || index}`}
              positions={lineCoords}
              color={isBeingEdited ? '#ff9900' : '#e11d48'}
              weight={isBeingEdited ? 5 : 3}
              dashArray={isBeingEdited ? "5, 5" : undefined}
              eventHandlers={{
                click: () => handleFeatureClick(feature)
              }}
            />
            {/* Draggable vertex markers when editing */}
            {isBeingEdited && lineCoords && lineCoords.map((pos, vidx) => (
              <Marker
                key={`v-${feature.id}-${vidx}`}
                position={pos}
                draggable={true}
                opacity={0.8}
                eventHandlers={{
                  dragend: (e) => handleEditingVertexDrag(vidx, e),
                  contextmenu: () => handleEditingVertexDelete(vidx)
                }}
              />
            ))}
          </>
        );
      } else if (feature.feature_type === 'polygon') {
        const polyCoords: any = coords;
        return (
          <>
            <Polygon
              key={`poly-${feature.id || index}`}
              positions={polyCoords}
              color={isBeingEdited ? '#ff9900' : '#059669'}
              weight={isBeingEdited ? 4 : 2}
              fillOpacity={isBeingEdited ? 0.4 : 0.3}
              dashArray={isBeingEdited ? "5, 5" : undefined}
              eventHandlers={{
                click: () => handleFeatureClick(feature)
              }}
            />
            {/* Draggable vertex markers when editing - right-click to delete */}
            {isBeingEdited && polyCoords && polyCoords.map((pos: number[], vidx: number) => (
              <Marker
                key={`v-${feature.id}-${vidx}`}
                position={pos}
                draggable={true}
                opacity={0.8}
                eventHandlers={{
                  dragend: (e) => handleEditingVertexDrag(vidx, e),
                  contextmenu: () => handleEditingVertexDelete(vidx)
                }}
              />
            ))}
          </>
        );
      }
      } catch (e) {
        console.warn('Error rendering feature:', e);
      }
      return null;
    });
  };

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{ width: '350px', padding: '12px', borderRight: '1px solid #ddd', overflowY: 'auto' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="Enter feature name first"
            value={featureName}
            onChange={(e) => setFeatureName(e.target.value)}
            suffix={featureName ? <span style={{ color: 'green' }}>✓</span> : null}
          />

          {availableYears && availableYears.length > 0 && (
            <Radio.Group
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
              buttonStyle="solid"
            >
              {availableYears.map(y => (
                <Radio.Button key={y.year} value={y.year}>{y.year}</Radio.Button>
              ))}
            </Radio.Group>
          )}

          <Radio.Group
            value={featureType}
            onChange={(e) => onFeatureTypeChange(e.target.value)}
            buttonStyle="solid"
            disabled={!featureName || !selectedYear}
          >
            <Radio.Button value="point">Point</Radio.Button>
            <Radio.Button value="line">Line</Radio.Button>
            <Radio.Button value="polygon">Polygon</Radio.Button>
          </Radio.Group>

          {/* Unit Toggle */}
          <Button
            type={measurementUnit === 'metric' ? 'primary' : 'default'}
            size="small"
            onClick={() => setMeasurementUnit(measurementUnit === 'metric' ? 'imperial' : 'metric')}
          >
            {measurementUnit === 'metric' ? 'Metric' : 'Imperial'}
          </Button>

          {/* Stop Edit Button - shows when editing */}
          {editingFeatureId && (
            <Button
              type="default"
              danger
              size="small"
              onClick={handleStopEdit}
              block
            >
              Stop Editing
            </Button>
          )}

          <Button
            type={drawingMode ? 'primary' : 'default'}
            onClick={() => setDrawingMode(!drawingMode)}
            disabled={!featureName}
            block
          >
            {drawingMode ? 'Drawing Active ✓' : 'Start Drawing'}
          </Button>

          <Card size="small">
            <p style={{ margin: 0, color: '#666', fontSize: '12px' }}>
              {featureType === 'point' && 'Click map to place point'}
              {featureType === 'line' && currentPoints.length < 2 && 'Click map to add at least 2 points, then double-click'}
              {featureType === 'line' && currentPoints.length >= 2 && 'Double-click to finish line'}
              {featureType === 'polygon' && currentPoints.length < 3 && 'Click map to add at least 3 points, then double-click'}
              {featureType === 'polygon' && currentPoints.length >= 3 && 'Double-click to close polygon'}
            </p>
          </Card>
        </Space>

        <Card title="Drawn Features" size="small" style={{ marginTop: '12px' }}>
          {drawnFeatures.length === 0 ? (
            <p style={{ color: '#999' }}>No features drawn</p>
          ) : (
            <List
              size="small"
              dataSource={drawnFeatures}
              renderItem={(feature: any) => (
                <List.Item
                  style={{ 
                    backgroundColor: selectedFeatureId === feature.id ? '#e6f7ff' : undefined,
                    cursor: editMode === 'edit' ? 'pointer' : 'default'
                  }}
                  onClick={() => editMode === 'edit' && handleFeatureClick(feature)}
                  actions={[
                    <Button 
                      type="link" 
                      size="small"
                      onClick={() => handleStartEdit(feature)}
                      title="Click then click map to add/move"
                    >
                      {editingFeatureId === feature.id ? 'Editing...' : 'Edit'}
                    </Button>,
                    <Popconfirm
                      title="Delete this feature?"
                      onConfirm={() => handleDeleteFeature(feature.id)}
                    >
                      <Button type="link" danger size="small">Delete</Button>
                    </Popconfirm>
                  ]}
                >
                  <List.Item.Meta
                    title={feature.properties?.name || feature.feature_type}
                    description={`Year ${feature.properties?.year || '-'} • ${feature.feature_type === 'point' ? '1 point' : feature.feature_type === 'line' ? `${feature.properties?.length_m || 0} m` : `${feature.properties?.area_sqm || 0} m²`}`}
                  />
                </List.Item>
              )}
            />
          )}
        </Card>

        {/* Copy to year popup */}
        {selectedFeatureId && (
          <Card 
            title="Feature Options" 
            size="small" 
            style={{ marginTop: '12px', borderColor: '#2563eb' }}
            extra={
              <Button size="small" onClick={() => { setSelectedFeatureId(null); setIsEditing(false); }}>
                Close
              </Button>
            }
          >
            {/* Copy to another year */}
            {availableYears && availableYears.length > 1 && (
              <div style={{ marginTop: 8 }}>
                <p style={{ fontSize: 11, marginBottom: 4, color: '#666' }}>Copy to year:</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {availableYears
                    .filter(y => y.year !== editingFeature?.properties?.year)
                    .map(y => (
                      <Button 
                        key={y.year} 
                        size="small" 
                        onClick={() => handleCopyFeature(y.year)}
                      >
                        Y{y.year}
                      </Button>
                    ))}
                </div>
              </div>
            )}
            
            <Button 
              type="primary" 
              danger 
              block
              style={{ marginTop: 12 }}
              onClick={() => handleDeleteFeature(selectedFeatureId)}
            >
              Delete
            </Button>
          </Card>
        )}
      </div>

      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer
          center={[27.7172, 85.3240]}
          zoom={13}
          style={{ height: '100%' }}
          ref={mapRef}
        >
          <TileLayer
            attribution={BASE_MAPS[baseMap].attribution}
            url={BASE_MAPS[baseMap].url}
          />
          
          {/* Forest Boundary Layer */}
          {boundaryGeometry && (
            <GeoJSON
              data={boundaryGeometry}
              style={{
                color: '#666666',
                weight: 2,
                fillColor: '#cccccc',
                fillOpacity: 0.1
              }}
            />
          )}

          {/* Block Layers */}
          {blockLayers.map((block: any, index: number) => (
            block.geometry && (
              <GeoJSON
                key={`block-${index}`}
                data={block.geometry}
                style={{
                  color: '#2563eb',
                  weight: 2,
                  fillColor: '#2563eb',
                  fillOpacity: 0.15
                }}
              />
            )
          ))}

          {/* Sub-Area Layers */}
          {subAreaLayers.map((subArea: any, index: number) => (
            subArea.geometry && (
              <GeoJSON
                key={`subarea-${index}`}
                data={subArea.geometry}
                style={{
                  color: '#059669',
                  weight: 2,
                  fillColor: '#059669',
                  fillOpacity: 0.2
                }}
              />
            )
          ))}
          
          <MapEventsHandler onClick={handleMapClick} onDoubleClick={handleDoubleClick} blocksWithSubAreas={blocksWithSubAreas} />
          {renderBlockLayers()}
          {renderFeatures()}
          {currentPoints.length > 1 && (featureType === 'line' || featureType === 'polygon') && (
            <Polyline
              positions={currentPoints.map(p => [p.lat, p.lng])}
              color="#2563eb"
              weight={3}
              dashArray="5, 10"
            />
          )}
          {/* Draggable vertex markers during drawing - right-click to delete */}
          {currentPoints.length > 0 && (featureType === 'line' || featureType === 'polygon') && (
            <>
              {currentPoints.map((pos, index) => (
                <Marker
                  key={`draw-vertex-${index}`}
                  position={pos}
                  draggable={true}
                  opacity={0.9}
                  eventHandlers={{
                    dragend: (e) => handleVertexDrag(index, e),
                    contextmenu: () => handleVertexDelete(index)
                  }}
                />
              ))}
              {/* Show live measurement tooltip on the shape */}
              {featureType === 'polygon' && currentPoints.length >= 3 && (
                <Polygon
                  positions={currentPoints.map(p => [p.lat, p.lng])}
                  color="#2563eb"
                  weight={2}
                  fillOpacity={0.1}
                >
                  <Tooltip permanent direction="center" opacity={0.9}>
                    {formatArea(currentArea)}
                  </Tooltip>
                </Polygon>
              )}
              {featureType === 'line' && currentPoints.length >= 2 && (
                <Polyline
                  positions={currentPoints.map(p => [p.lat, p.lng])}
                  color="#2563eb"
                  weight={3}
                >
                  <Tooltip permanent direction="top" opacity={0.9}>
                    {formatLength(currentLength)}
                  </Tooltip>
                </Polyline>
              )}
            </>
          )}
        </MapContainer>
        
        {/* Live Measurement Overlay */}
        <div style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 1000,
          backgroundColor: 'rgba(255,255,255,0.95)',
          padding: '8px 12px',
          borderRadius: 4,
          boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
          fontSize: '13px'
        }}>
          {/* Show editing vertices measurements */}
          {editingVertices.length > 0 && (
            <>
              {featureType === 'line' && editingVertices.length >= 2 && (
                <div><strong>Length:</strong> {formatLength(currentLength)}</div>
              )}
              {featureType === 'polygon' && editingVertices.length >= 3 && (
                <div><strong>Area:</strong> {formatArea(currentArea)}</div>
              )}
              <div style={{ marginTop: 4, fontSize: 11, color: '#666' }}>
                Vertices: {editingVertices.length} (drag to move, right-click to delete)
              </div>
            </>
          )}
          {/* Show current drawing measurements */}
          {editingVertices.length === 0 && (
            <>
              {featureType === 'line' && currentPoints.length >= 2 && (
                <div><strong>Length:</strong> {formatLength(currentLength)}</div>
              )}
              {featureType === 'polygon' && currentPoints.length >= 3 && (
                <div><strong>Area:</strong> {formatArea(currentArea)}</div>
              )}
              {(featureType === 'line' || featureType === 'polygon') && currentPoints.length > 0 && (
                <div style={{ marginTop: 4, fontSize: 11, color: '#666' }}>
                  Points: {currentPoints.length} (drag to move, right-click to delete)
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

interface MapEventsHandlerProps {
  onClick: (e: L.LeafletMouseEvent) => void;
  onDoubleClick: (e: L.LeafletEvent) => void;
}

const MapEventsHandler: React.FC<MapEventsHandlerProps & { blocksWithSubAreas?: BlockSubArea[] }> = ({ onClick, onDoubleClick, blocksWithSubAreas }) => {
  const map = useMap();
  const [zoomDone, setZoomDone] = useState(false);
  
  useEffect(() => {
    if (map && !zoomDone && blocksWithSubAreas && blocksWithSubAreas.length > 0) {
      const bounds = L.latLngBounds([]);
      let hasCoords = false;
      blocksWithSubAreas.forEach((block: BlockSubArea) => {
        if (block.geometry) {
          try {
            const gj = typeof block.geometry === 'string' ? JSON.parse(block.geometry) : block.geometry;
            if (gj.coordinates) {
              const coords = gj.type === 'Polygon' ? gj.coordinates[0] : gj.coordinates;
              coords.forEach((c: number[]) => {
                bounds.extend([c[1], c[0]]);
                hasCoords = true;
              });
            }
          } catch (e) { console.warn('Block bounds error', e); }
        }
      });
      if (hasCoords && bounds.isValid()) {
        map.fitBounds(bounds, { padding: [50, 50] });
        setZoomDone(true);
      }
    }
  }, [map, blocksWithSubAreas, zoomDone]);
  
  useMapEvents({
    click: onClick,
    dblclick: (e) => {
      onDoubleClick(e);
    }
  });
  return null;
};

export default DrawingCanvas;