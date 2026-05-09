import React, { useState } from 'react';
import { Settings } from 'lucide-react';
import api from '../../services/api';

interface AutoBufferSectionProps {
  calculationId: string;
  defaultDistance: number;
  onExtentCreated: (extentId: number) => void;
}

export function AutoBufferSection({
  calculationId,
  defaultDistance,
  onExtentCreated
}: AutoBufferSectionProps) {
  const [distance, setDistance] = useState(defaultDistance);
  const [creating, setCreating] = useState(false);

  const handleCreateBuffer = async () => {
    setCreating(true);
    try {
      const response = await api.post(
        `/api/calculations/${calculationId}/user-group/auto-buffer`,
        null,
        { params: { buffer_distance: distance } }
      );

      onExtentCreated(response.data.extent_id);
      alert(`Auto-buffer extent created (${distance}m)`);
    } catch (error: any) {
      console.error('Buffer creation failed:', error);
      const errorMsg = error.response?.data?.detail || 'Failed to create auto-buffer extent';
      alert(errorMsg);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="auto-buffer-section border border-gray-300 rounded p-4 bg-white">
      <h3 className="text-lg font-semibold mb-3">Auto-Buffer from Forest Boundary</h3>

      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">
          Buffer Distance (meters)
        </label>
        <input
          type="number"
          value={distance}
          onChange={(e) => setDistance(Number(e.target.value))}
          min={100}
          max={5000}
          step={100}
          className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-sm text-gray-500 mt-1">
          Default: 1000m (adjustable between 100m - 5000m)
        </p>
      </div>

      <button
        onClick={handleCreateBuffer}
        disabled={creating}
        className={`${
          creating ? 'bg-gray-400' : 'bg-blue-600 hover:bg-blue-700'
        } text-white px-6 py-2 rounded transition-colors flex items-center gap-2`}
      >
        <Settings size={16} />
        {creating ? 'Creating Buffer...' : 'Create Auto-Buffer'}
      </button>
    </div>
  );
}
