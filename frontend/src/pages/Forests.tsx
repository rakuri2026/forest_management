import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { forestApi } from '../services/api';
import type { CommunityForest } from '../types';

const Forests: React.FC = () => {
  const [forests, setForests] = useState<CommunityForest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [regime, setRegime] = useState('');

  useEffect(() => {
    loadForests();
  }, [searchTerm, regime]);

  const loadForests = async () => {
    setIsLoading(true);
    try {
      const data = await forestApi.listCommunityForests({
        search: searchTerm || undefined,
        regime: regime || undefined,
        limit: 50,
      });
      setForests(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load forests');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">
              Community Forests
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              Explore 3,922 community forests in Nepal
            </p>
          </div>

          <div className="bg-white shadow rounded-lg mb-6">
            <div className="px-4 py-5 sm:p-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="search" className="block text-sm font-medium text-gray-700">
                    Search by name
                  </label>
                  <input
                    type="text"
                    id="search"
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm"
                    placeholder="Enter forest name..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="regime" className="block text-sm font-medium text-gray-700">
                    Filter by regime
                  </label>
                  <select
                    id="regime"
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm"
                    value={regime}
                    onChange={(e) => setRegime(e.target.value)}
                  >
                    <option value="">All regimes</option>
                    <option value="CF">CF - Community Forest</option>
                    <option value="CFM">CFM - Collaborative Forest Management</option>
                    <option value="LHF">LHF - Leasehold Forest</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {isLoading ? (
            <div className="text-center py-12">
              <p className="text-gray-500">Loading forests...</p>
            </div>
          ) : error ? (
            <div className="bg-red-50 p-4 rounded-md">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          ) : (
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <ul className="divide-y divide-gray-200">
                {forests.map((forest) => (
                  <li key={forest.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <Link
                          to={`/forests/${forest.id}`}
                          className="text-sm font-medium text-green-600 hover:text-green-800 truncate"
                        >
                          {forest.name}
                        </Link>
                        <p className="mt-1 text-sm text-gray-500">
                          Code: {forest.code} | Regime: {forest.regime}
                        </p>
                      </div>
                      <div className="ml-4 flex-shrink-0 text-right">
                        <span className="text-sm font-medium text-gray-900">
                          {forest.area_hectares?.toFixed(2) || 'N/A'} ha
                        </span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              {forests.length === 0 && (
                <div className="text-center py-12">
                  <p className="text-gray-500">No forests found</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Forests;
