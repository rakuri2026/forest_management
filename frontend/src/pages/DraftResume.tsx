import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import MapCreationWizard from '../components/MapCreation/MapCreationWizard';
import { forestApi } from '../services/api';

interface DraftData {
  id: string;
  forest_name: string;
  draft_data: {
    islands: Array<{
      id: string;
      geometry: any;
      area: number;
    }>;
    mode: string;
    islands_count: number;
    total_area: number;
  };
  created_at: string;
  updated_at: string;
}

export default function DraftResume() {
  const { draftId } = useParams<{ draftId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftData | null>(null);
  const [forestName, setForestName] = useState('');

  useEffect(() => {
    loadDraft();
  }, [draftId]);

  const loadDraft = async () => {
    if (!draftId) return;
    
    try {
      setLoading(true);
      const data = await forestApi.getDraft(draftId);
      setDraft(data);
      setForestName(data.forest_name || 'Untitled Draft');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load draft');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async (data: {
    outerBoundary: any;
    gpsPoints: any[];
    blocks: any[];
    subAreas: any[];
  }) => {
    if (!draftId) return;

    // Debug: check the geometry
    console.log('[DraftResume] handleComplete - outerBoundary:', data.outerBoundary);
    console.log('[DraftResume] handleComplete - outerBoundary type:', data.outerBoundary?.type);
    console.log('[DraftResume] handleComplete - outerBoundary coordinates:', data.outerBoundary?.coordinates);

    if (!data.outerBoundary || !data.outerBoundary.type || !data.outerBoundary.coordinates) {
      setError('Invalid geometry: boundary is missing or corrupted');
      return;
    }

    try {
      // Convert draft to calculation
      const response = await fetch(`http://localhost:8001/api/forests/drafts/${draftId}/convert`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          outer_boundary: data.outerBoundary,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to convert draft');
      }

      const result = await response.json();
      navigate(`/calculations/${result.id}/block-naming`);
    } catch (err: any) {
      setError(err.message || 'Failed to save forest');
    }
  };

  const handleCancel = () => {
    navigate('/upload');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading draft...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h2 className="text-red-800 font-semibold">Error</h2>
          <p className="text-red-600 mt-2">{error}</p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Back to Upload
          </button>
        </div>
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h2 className="text-yellow-800 font-semibold">Draft not found</h2>
          <p className="text-yellow-600 mt-2">This draft may have been deleted or does not exist.</p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-4 px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700"
          >
            Back to Upload
          </button>
        </div>
      </div>
    );
  }

  // Get initial polygon from draft data
  const islands = draft.draft_data?.islands || [];
  let initialPolygon: any = null;

  if (islands.length === 1) {
    initialPolygon = islands[0].geometry;
  } else if (islands.length > 1) {
    // Combine into MultiPolygon
    initialPolygon = {
      type: 'MultiPolygon',
      coordinates: islands.map(i => i.geometry.coordinates),
    };
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Resume Draft</h1>
        <p className="text-gray-600 mt-1">
          Continuing work on: <strong>{draft.forest_name}</strong>
        </p>
        {draft.draft_data?.islands_count > 0 && (
          <p className="text-sm text-gray-500 mt-1">
            {draft.draft_data.islands_count} island(s), Total area: {draft.draft_data.total_area?.toFixed(2)} ha
          </p>
        )}
      </div>

      <MapCreationWizard
        forestName={draft.forest_name || 'Untitled Draft'}
        onComplete={handleComplete}
        onCancel={handleCancel}
        initialPolygon={initialPolygon}
        initialDraftId={draft.id}
        isDraft={true}
      />
    </div>
  );
}
