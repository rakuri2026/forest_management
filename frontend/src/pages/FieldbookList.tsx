import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

interface FieldbookRecord {
  id: string;
  calculation_id: string;
  forest_name: string;
  vertex_count: number;
  interpolated_count: number;
  created_at: string;
}

const FieldbookList: React.FC = () => {
  const [fieldbooks, setFieldbooks] = useState<FieldbookRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFieldbooks();
  }, []);

  const fetchFieldbooks = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/fieldbook');
      setFieldbooks(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching fieldbooks:', err);
      setError(err.response?.data?.detail || 'Failed to load fieldbooks');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
          <p className="mt-2 text-gray-600">Loading fieldbooks...</p>
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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Fieldbook Records</h1>
        <p className="mt-2 text-gray-600">
          View boundary vertices and interpolated points for field surveys
        </p>
      </div>

      {fieldbooks.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-6 text-center">
          <p className="text-gray-500">No fieldbook records found.</p>
          <p className="text-sm text-gray-400 mt-2">
            Upload a forest boundary to generate fieldbook records.
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
            {fieldbooks.map((fieldbook) => (
              <li key={fieldbook.id}>
                <Link
                  to={`/calculations/${fieldbook.calculation_id}`}
                  className="block hover:bg-gray-50"
                >
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <p className="text-lg font-medium text-green-600 truncate">
                          {fieldbook.forest_name}
                        </p>
                        <div className="mt-2 flex items-center text-sm text-gray-500">
                          <span>
                            {fieldbook.vertex_count} vertices • {fieldbook.interpolated_count} interpolated points
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-gray-400">
                          Created: {new Date(fieldbook.created_at).toLocaleString()}
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

export default FieldbookList;
