import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import { forestApi } from '../services/api';
import type { CommunityForest } from '../types';
import 'leaflet/dist/leaflet.css';

const ForestDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [forest, setForest] = useState<CommunityForest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadForest = async () => {
      if (!id) return;

      try {
        const data = await forestApi.getCommunityForest(parseInt(id));
        setForest(data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load forest details');
      } finally {
        setIsLoading(false);
      }
    };

    loadForest();
  }, [id]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading forest details...</p>
      </div>
    );
  }

  if (error || !forest) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 p-4 rounded-md">
          <p className="text-sm text-red-800">{error || 'Forest not found'}</p>
          <Link to="/forests" className="mt-2 inline-block text-sm text-green-600 hover:text-green-800">
            Back to forests
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-4">
            <Link to="/forests" className="text-sm text-green-600 hover:text-green-800">
              ← Back to all forests
            </Link>
          </div>

          <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
            <div className="px-4 py-5 sm:px-6">
              <h1 className="text-2xl font-bold text-gray-900">{forest.name}</h1>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Community Forest Details
              </p>
            </div>
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              <dl className="grid grid-cols-1 gap-x-4 gap-y-8 sm:grid-cols-2">
                <div>
                  <dt className="text-sm font-medium text-gray-500">Forest Code</dt>
                  <dd className="mt-1 text-sm text-gray-900">{forest.code}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Regime</dt>
                  <dd className="mt-1 text-sm text-gray-900">{forest.regime}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Area</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {forest.area_hectares?.toFixed(2)} hectares
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Forest ID</dt>
                  <dd className="mt-1 text-sm text-gray-900">{forest.id}</dd>
                </div>
              </dl>
            </div>
          </div>

          {forest.geometry && (
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <div className="px-4 py-5 sm:px-6">
                <h2 className="text-lg font-medium text-gray-900">Forest Boundary Map</h2>
              </div>
              <div className="border-t border-gray-200">
                <div style={{ height: '500px' }}>
                  <MapContainer
                    center={[28.3949, 84.124]}
                    zoom={7}
                    style={{ height: '100%', width: '100%' }}
                  >
                    <TileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    <GeoJSON
                      data={forest.geometry}
                      style={{
                        color: '#10b981',
                        weight: 2,
                        fillOpacity: 0.3,
                      }}
                    />
                  </MapContainer>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForestDetail;
