import React, { useState, useEffect } from 'react';
import { TreesNeedingAssignmentResponse, TreeReassignmentResponse } from './types';
import { compartmentApi } from '../../services/api';

interface TreeReassignmentDialogProps {
  blockId: string;
  blockName: string;
  onComplete: (result?: TreeReassignmentResponse) => void;
  onCancel: () => void;
}

export function TreeReassignmentDialog({
  blockId,
  blockName,
  onComplete,
  onCancel,
}: TreeReassignmentDialogProps) {
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [data, setData] = useState<TreesNeedingAssignmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TreeReassignmentResponse | null>(null);

  useEffect(() => {
    loadTreesNeedingAssignment();
  }, [blockId]);

  const loadTreesNeedingAssignment = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await compartmentApi.getTreesNeedingAssignment(blockId);
      setData(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load trees');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoAssign = async () => {
    try {
      setProcessing(true);
      setError(null);
      const response = await compartmentApi.reassignTrees({
        block_id: blockId,
        auto_assign: true,
      });
      setResult(response);
      onComplete(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to reassign trees');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
            <p className="mt-4 text-gray-600">Loading trees...</p>
          </div>
        </div>
      </div>
    );
  }

  if (result) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
          <div className="flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Trees Reassigned</h3>
            <p className="text-gray-600 mb-4">
              Successfully assigned {result.trees_assigned} trees to compartments
            </p>
            {result.trees_unassigned > 0 && (
              <p className="text-sm text-yellow-600 mb-4">
                {result.trees_unassigned} trees could not be assigned (outside compartment boundaries)
              </p>
            )}
            <button
              onClick={() => onComplete(result)}
              className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Reassign Trees to Compartments</h3>
            <p className="text-sm text-gray-500">
              Block: {blockName} • {data?.total_trees || 0} trees need assignment
            </p>
          </div>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="flex-1 overflow-auto">
          {data?.trees && data.trees.length > 0 ? (
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800">
                  <strong>Note:</strong> Trees uploaded before compartments were created need to be 
                  assigned to specific compartments. Click "Auto-Assign" to automatically assign 
                  each tree to the compartment where its GPS location falls.
                </p>
              </div>

              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Species
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Location
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Suggested Compartment
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {data.trees.slice(0, 20).map((tree) => (
                      <tr key={tree.tree_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm text-gray-900">
                          {tree.species || 'Unknown'}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">
                          {tree.location.lat.toFixed(5)}, {tree.location.lon.toFixed(5)}
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {tree.suggested_compartment_name ? (
                            <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">
                              {tree.suggested_compartment_name}
                            </span>
                          ) : (
                            <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
                              Outside boundaries
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.trees.length > 20 && (
                  <div className="bg-gray-50 px-4 py-2 text-sm text-gray-500 text-center">
                    ... and {data.trees.length - 20} more trees
                  </div>
                )}
              </div>

              <div className="p-4 bg-gray-50 rounded-lg">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Compartments:</h4>
                <div className="flex flex-wrap gap-2">
                  {data.compartments.map((comp) => (
                    <span key={comp.id} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                      {comp.name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>No trees need reassignment</p>
              <p className="text-sm mt-1">All trees have been assigned to compartments</p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-4 pt-4 border-t">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
          >
            Skip for Now
          </button>
          {data?.trees && data.trees.length > 0 && (
            <button
              onClick={handleAutoAssign}
              disabled={processing}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 flex items-center gap-2"
            >
              {processing ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Assigning...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Auto-Assign All
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
