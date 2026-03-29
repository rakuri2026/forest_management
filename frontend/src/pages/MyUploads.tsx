import { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { forestApi } from '../services/api';
import type { Calculation } from '../types';

export default function MyUploads() {
  const [calculations, setCalculations] = useState<Calculation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCalculations();
  }, []);

  const loadCalculations = async () => {
    try {
      setLoading(true);
      const data = await forestApi.listCalculations();
      setCalculations(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load uploads');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, forestName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${forestName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await forestApi.deleteCalculation(id);
      await loadCalculations();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete calculation');
    }
  };

  // Deduplicate: show only one entry per forest, preferring completed over pending/processing over draft
  const uniqueForests = useMemo(() => {
    const forestMap = new Map<string, Calculation>();

    // Sort: completed first, then pending, then processing, then draft
    const sorted = [...calculations].sort((a, b) => {
      // Priority: completed > pending > processing > draft
      const getPriority = (calc: Calculation) => {
        if (calc.status === 'completed') return 0;
        if (calc.status === 'pending') return 1;
        if (calc.status === 'processing') return 2;
        if (calc.is_draft) return 3;
        return 4;
      };
      const priorityDiff = getPriority(a) - getPriority(b);
      if (priorityDiff !== 0) return priorityDiff;
      // If same priority, use most recent
      return new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime();
    });

    for (const calc of sorted) {
      const key = calc.forest_name || 'Unnamed Forest';
      if (!forestMap.has(key)) {
        forestMap.set(key, calc);
      }
    }

    return Array.from(forestMap.values());
  }, [calculations]);

  const getStatusBadge = (calc: Calculation) => {
    if (calc.is_draft) {
      return { class: 'bg-blue-100 text-blue-800', text: 'Draft' };
    }
    const styles: Record<string, { class: string; text: string }> = {
      processing: { class: 'bg-yellow-100 text-yellow-800', text: 'Processing' },
      completed: { class: 'bg-green-100 text-green-800', text: 'Completed' },
      failed: { class: 'bg-red-100 text-red-800', text: 'Failed' },
      pending: { class: 'bg-gray-100 text-gray-800', text: 'Pending' },
    };
    return styles[calc.status] || { class: 'bg-gray-100 text-gray-800', text: calc.status };
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getActions = (calc: Calculation) => {
    const actions: React.ReactNode[] = [];

    if (calc.is_draft) {
      actions.push(
        <Link
          key="resume"
          to={`/drafts/${calc.id}/resume`}
          className="text-purple-600 hover:text-purple-900 font-semibold"
        >
          Resume
        </Link>
      );
    } else if (calc.status === 'completed') {
      actions.push(
        <Link
          key="view"
          to={`/calculations/${calc.id}`}
          className="text-green-600 hover:text-green-900"
        >
          View Details
        </Link>
      );
    } else if (calc.status === 'pending') {
      actions.push(
        <button
          key="analyze"
          onClick={() => {
            window.location.href = `/calculations/${calc.id}/block-naming`;
          }}
          className="text-blue-600 hover:text-blue-900 font-semibold"
        >
          Analyze
        </button>
      );
      actions.push(
        <Link
          key="view"
          to={`/calculations/${calc.id}`}
          className="text-gray-600 hover:text-gray-900"
        >
          View
        </Link>
      );
    } else if (calc.status === 'processing') {
      actions.push(
        <span key="processing" className="text-yellow-600 font-semibold">
          Processing...
        </span>
      );
    }

    actions.push(
      <button
        key="delete"
        onClick={() => handleDelete(calc.id, calc.forest_name || 'Unnamed Forest')}
        className="text-red-600 hover:text-red-900"
      >
        Delete
      </button>
    );

    return actions;
  };

  return (
    <div className="max-w-7xl mx-auto py-8 px-4">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My CFOPs</h1>
          <p className="mt-2 text-gray-600">
            Community Forest Operational Plans - View and manage your CF boundary uploads
          </p>
        </div>
        <Link
          to="/upload"
          className="bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 font-medium transition-colors"
        >
          Upload New CF Boundary
        </Link>
      </div>

      {loading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading your uploads...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      ) : uniqueForests.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No CFOPs yet</h3>
          <p className="mt-2 text-gray-500">
            Get started by uploading your first community forest boundary
          </p>
          <Link
            to="/upload"
            className="mt-6 inline-block bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 font-medium transition-colors"
          >
            Upload Your First CF Boundary
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Forest Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Source
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Updated
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {uniqueForests.map((calc) => {
                const statusInfo = getStatusBadge(calc);
                return (
                  <tr key={calc.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {calc.forest_name || 'Unnamed Forest'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {calc.is_draft 
                          ? 'Map Creation' 
                          : (calc.uploaded_filename?.replace(/\.(kml|geojson|shp)$/i, '') || 'Imported')}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${statusInfo.class}`}>
                        {statusInfo.text}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(calc.updated_at || calc.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-4">
                        {getActions(calc)}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
