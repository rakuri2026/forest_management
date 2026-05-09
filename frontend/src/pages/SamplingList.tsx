import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

interface SamplingRecord {
  id: string;
  calculation_id: string;
  forest_name: string;
  design_type: string;
  plot_count: number;
  plot_size: number;
  created_at: string;
}

const SamplingList: React.FC = () => {
  const [samplings, setSamplings] = useState<SamplingRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSamplings();
  }, []);

  const fetchSamplings = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/sampling');
      setSamplings(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching samplings:', err);
      setError(err.response?.data?.detail || 'Failed to load sampling designs');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
          <p className="mt-2 text-gray-600">Loading sampling designs...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">{error}</p>
        </div>
      </div>
    );
  }

  const getDesignTypeBadge = (type: string) => {
    const badges: { [key: string]: string } = {
      systematic: 'bg-blue-100 text-blue-800',
      random: 'bg-purple-100 text-purple-800',
      stratified: 'bg-orange-100 text-orange-800',
    };
    return badges[type.toLowerCase()] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Sampling Designs</h1>
        <p className="mt-2 text-gray-600">
          View and manage sampling plot locations for forest inventory
        </p>
      </div>

      {samplings.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <p className="text-gray-500">No sampling designs found.</p>
          <p className="text-sm text-gray-400 mt-2">
            Upload a forest boundary and create a sampling design.
          </p>
          <Link
            to="/upload"
            className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700"
          >
            Upload Boundary
          </Link>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {samplings.map((sampling) => (
              <li key={sampling.id}>
                <Link
                  to={`/calculations/${sampling.calculation_id}`}
                  className="block hover:bg-gray-50"
                >
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center">
                          <p className="text-lg font-medium text-green-600 truncate">
                            {sampling.forest_name}
                          </p>
                          <span
                            className={`ml-3 px-2 py-1 text-xs font-medium rounded-full ${getDesignTypeBadge(
                              sampling.design_type
                            )}`}
                          >
                            {sampling.design_type}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center text-sm text-gray-500">
                          <span>
                            {sampling.plot_count} plots • Plot size: {sampling.plot_size}m²
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-gray-400">
                          Created: {new Date(sampling.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="ml-4">
                        <svg
                          className="h-5 w-5 text-gray-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default SamplingList;
