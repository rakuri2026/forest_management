import React from 'react';
import { AvailableBlock } from './types';

interface BlockSelectionPanelProps {
  blocks: AvailableBlock[];
  selectedBlock: AvailableBlock | null;
  onSelectBlock: (block: AvailableBlock) => void;
  onDeleteCompartments: (blockId: string, blockName: string) => void;
  loading?: boolean;
}

export function BlockSelectionPanel({
  blocks,
  selectedBlock,
  onSelectBlock,
  onDeleteCompartments,
  loading = false,
}: BlockSelectionPanelProps) {
  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
      </div>
    );
  }

  const availableBlocks = blocks.filter(b => !b.has_compartments);
  const blocksWithCompartments = blocks.filter(b => b.has_compartments);
  const hasAnyCompartments = blocksWithCompartments.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Forest Blocks</h3>
        <span className="text-sm text-gray-500">{blocks.length} blocks</span>
      </div>

      {hasAnyCompartments && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">
            <strong>Note:</strong> {blocksWithCompartments.length} block(s) already have compartments.
            You can only create compartments if no other block has compartments.
          </p>
        </div>
      )}

      {blocks.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
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
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
            />
          </svg>
          <p className="mt-2 text-sm">No blocks available for splitting</p>
          <p className="text-xs text-gray-400 mt-1">
            Create forest blocks first from the Map Creation tab
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {blocks.map((block) => {
            const isDisabled = hasAnyCompartments && !block.has_compartments;
            return (
              <div
                key={block.id}
                onClick={() => !isDisabled && onSelectBlock(block)}
                className={`p-4 border rounded-lg transition-all ${
                  isDisabled
                    ? 'opacity-50 cursor-not-allowed bg-gray-50'
                    : selectedBlock?.id === block.id
                      ? 'border-green-500 bg-green-50 ring-2 ring-green-200 cursor-pointer'
                      : 'border-gray-200 hover:border-green-300 hover:bg-gray-50 cursor-pointer'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{block.name}</h4>
                    <p className="text-sm text-gray-500 mt-1">
                      {block.area_hectares.toFixed(2)} ha ({block.area_sqm.toLocaleString()} m²)
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {block.has_compartments ? (
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 text-xs font-medium rounded bg-blue-100 text-blue-800">
                          {block.compartment_count} compartments
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            const totalTrees = block.total_trees_in_calculation || 0;
                            if (totalTrees > 0) {
                              alert(`Cannot delete compartments: ${totalTrees} trees are associated with this calculation. Please delete the tree inventory upload first, then come back to delete the compartments.`);
                              return;
                            }
                            if (confirm(`Delete all compartments for "${block.name}"?`)) {
                              onDeleteCompartments(block.id, block.name);
                            }
                          }}
                          className={`p-1 rounded transition-colors ${
                            (block.total_trees_in_calculation || 0) > 0 
                              ? 'text-gray-400 cursor-not-allowed' 
                              : 'text-red-600 hover:text-red-800 hover:bg-red-50'
                          }`}
                          title={(block.total_trees_in_calculation || 0) > 0 ? "Delete tree inventory first" : "Delete compartments"}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    ) : isDisabled ? (
                      <span className="px-2 py-1 text-xs font-medium rounded bg-gray-200 text-gray-500">
                        Has existing compartments
                      </span>
                    ) : (
                      <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-700">
                        Ready to split
                      </span>
                    )}
                    {block.tree_count > 0 && (
                      <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800">
                        {block.tree_count} trees
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
        <h4 className="text-sm font-medium text-yellow-900 mb-2">Important Rules:</h4>
        <ul className="text-xs text-yellow-800 space-y-1 list-disc list-inside">
          <li>Only ONE block can have compartments at a time</li>
          <li>To create compartments for a different block, first delete existing compartments</li>
          <li>Once compartments are created, they cannot be re-split until deleted</li>
          <li>If trees are associated with compartments, you must first delete the tree inventory upload, then delete compartments</li>
          <li>Use the trash icon to delete compartments (disabled if trees are present)</li>
        </ul>
      </div>
    </div>
  );
}
