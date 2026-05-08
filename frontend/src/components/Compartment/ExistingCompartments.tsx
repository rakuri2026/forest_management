import React, { useState } from 'react';
import { compartmentApi } from '../../services/api';

interface ExistingCompartmentsProps {
  blockId: string;
  blockName: string;
  compartmentCount: number;
  compartments: Array<{
    id: string;
    name: string;
    area_hectares: number;
    area_sqm: number;
    tree_count: number;
    compartment_code: string;
    is_compartment: boolean;
  }>;
  onDeleteCompartments: (blockId: string, blockName: string) => void;
  onRenameSuccess?: () => void;
}

export function ExistingCompartments({
  blockId,
  blockName,
  compartmentCount,
  compartments,
  onDeleteCompartments,
  onRenameSuccess,
}: ExistingCompartmentsProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleStartEdit = (compartment: any) => {
    setEditingId(compartment.id);
    setEditingName(compartment.name);
    setError(null);
    setSuccessMessage(null);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingName('');
    setError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingId || !editingName.trim()) {
      setError('Name cannot be empty');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await compartmentApi.renameCompartment(editingId, editingName.trim());
      setSuccessMessage(`Renamed to "${editingName.trim()}"`);
      setEditingId(null);
      setEditingName('');
      setTimeout(() => setSuccessMessage(null), 3000);
      onRenameSuccess?.();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to rename');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="font-medium text-green-900">
              {blockName}
            </span>
          </div>
          <button
            onClick={() => onDeleteCompartments(blockId, blockName)}
            className="px-3 py-1 text-xs font-medium text-red-700 bg-red-100 rounded hover:bg-red-200 transition-colors"
            title="Delete all compartments"
          >
            Delete All Compartments
          </button>
        </div>
        <p className="text-sm text-green-700 mt-1 ml-7">
          Split into {compartmentCount} compartments
        </p>
      </div>

      {/* Success message */}
      {successMessage && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
          <span className="text-sm text-green-800">{successMessage}</span>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
          <span className="text-sm text-red-800">{error}</span>
        </div>
      )}

      {/* Compartments list */}
      <div className="bg-white border border-gray-200 rounded-lg">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h4 className="text-sm font-semibold text-gray-900">Compartments</h4>
          <p className="text-xs text-gray-500 mt-1">Click on a compartment name to edit it</p>
        </div>
        
        <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
          {compartments.map((compartment) => (
            <div key={compartment.id} className="p-4 hover:bg-gray-50 transition-colors">
              {editingId === compartment.id ? (
                // Editing mode
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      onKeyDown={handleKeyDown}
                      className="flex-1 px-3 py-2 border border-green-400 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                      placeholder="Enter new name"
                      autoFocus
                    />
                    <button
                      onClick={handleSaveEdit}
                      disabled={saving}
                      className="px-3 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 text-sm"
                    >
                      {saving ? (
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      ) : (
                        'Save'
                      )}
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      className="px-3 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                  <p className="text-xs text-gray-500">Press Enter to save, Escape to cancel</p>
                </div>
              ) : (
                // Display mode
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div 
                      className="flex items-center gap-2 cursor-pointer group"
                      onClick={() => handleStartEdit(compartment)}
                    >
                      <h5 className="font-medium text-gray-900 group-hover:text-green-700 transition-colors">
                        {compartment.name}
                      </h5>
                      <svg 
                        className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" 
                        fill="none" 
                        viewBox="0 0 24 24" 
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {compartment.area_hectares.toFixed(2)} ha ({compartment.area_sqm.toLocaleString()} m²)
                    </p>
                    {compartment.tree_count > 0 && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {compartment.tree_count} trees
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800">
                      C{compartments.indexOf(compartment) + 1}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStartEdit(compartment);
                      }}
                      className="p-1 rounded transition-colors text-gray-400 hover:text-green-600 hover:bg-green-50"
                      title="Rename compartment"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
