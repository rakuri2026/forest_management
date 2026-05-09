import React from 'react';

interface CompartmentDetailsPanelProps {
  node: any;
  onSubDivide: () => void;
  onDelete: (nodeId: string, nodeName: string) => void;
}

export function CompartmentDetailsPanel({ node, onSubDivide, onDelete }: CompartmentDetailsPanelProps) {
  if (!node) return null;
  
  const hasChildren = node.children && node.children.length > 0;
  const isLocked = node.is_locked;
  const isCompartment = node.is_compartment;
  
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center gap-2">
          <div 
            className="w-5 h-5 rounded border border-gray-300 flex-shrink-0"
            style={{ backgroundColor: node.color || '#6b7280' }}
          />
          <h3 className="text-lg font-semibold text-gray-900">{node.name}</h3>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {node.is_compartment ? 'Compartment' : 'Block'} (Level {node.division_level})
        </p>
      </div>
      
      {/* Details */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Area Information */}
        <div className="bg-gray-50 rounded-lg p-3">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Area Information</h4>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Hectares:</span>
              <span className="font-medium">{node.area_hectares.toFixed(2)} ha</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Square Meters:</span>
              <span className="font-medium">{Math.round(node.area_sqm).toLocaleString()} m²</span>
            </div>
          </div>
        </div>
        
        {/* Statistics */}
        <div className="bg-gray-50 rounded-lg p-3">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Statistics</h4>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Child Count:</span>
              <span className="font-medium">{node.child_count || 0}</span>
            </div>
            {node.tree_count !== undefined && (
              <div className="flex justify-between">
                <span className="text-gray-600">Trees:</span>
                <span className="font-medium">{node.tree_count}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-600">Status:</span>
              <span className={`font-medium ${isLocked ? 'text-red-600' : 'text-green-600'}`}>
                {isLocked ? '🔒 Locked' : '🔓 Unlocked'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Level:</span>
              <span className="font-medium">
                {node.division_level === 0 ? 'Block' : 
                 node.division_level === 1 ? 'Compartment' : 
                 `Sub-Compartment (${node.division_level})`}
              </span>
            </div>
          </div>
        </div>
        
        {/* Children Preview */}
        {hasChildren && (
          <div className="bg-blue-50 rounded-lg p-3">
            <h4 className="text-sm font-medium text-blue-900 mb-2">Children ({node.child_count})</h4>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {node.children.map((child: any, index: number) => (
                <div key={child.id} className="flex items-center gap-2 text-xs">
                  <div 
                    className="w-3 h-3 rounded flex-shrink-0"
                    style={{ backgroundColor: child.color || '#6b7280' }}
                  />
                  <span className="text-gray-700">{child.name}</span>
                  <span className="text-gray-500 ml-auto">
                    {child.area_hectares.toFixed(2)} ha
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Actions */}
        <div className="space-y-2">
          {isCompartment && !isLocked && (
            <button
              onClick={onSubDivide}
              className="w-full px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Sub-divide Compartment
            </button>
          )}

          {isCompartment && (
            <button
              onClick={() => onDelete(node.id, node.name)}
              className="w-full px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete Compartment
            </button>
          )}
          
          {isLocked && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span className="text-sm text-red-800">
                  This compartment is locked from further division
                </span>
              </div>
            </div>
          )}
          
          {!isCompartment && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">
                This is a top-level block. Use the Compartments tab to split it into compartments first.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
