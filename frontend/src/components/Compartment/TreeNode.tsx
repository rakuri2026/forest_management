import React, { useState } from 'react';

interface TreeNodeProps {
  node: any;
  depth: number;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onRenameNode: (nodeId: string, newName: string) => void;
  onToggleLock: (nodeId: string) => void;
  onSubDivide: (nodeId: string) => void;
  onDeleteNode: (nodeId: string, nodeName: string) => void;
}

export function TreeNodeComponent({ 
  node, 
  depth, 
  selectedNodeId,
  onSelectNode, 
  onRenameNode, 
  onToggleLock, 
  onSubDivide,
  onDeleteNode
}: TreeNodeProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(node.name);
  const [isExpanded, setIsExpanded] = useState(true);
  
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = selectedNodeId === node.id;
  
  const handleSaveEdit = () => {
    if (editName.trim() && editName.trim() !== node.name) {
      onRenameNode(node.id, editName.trim());
      setIsEditing(false);
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSaveEdit();
    if (e.key === 'Escape') {
      setIsEditing(false);
      setEditName(node.name);
    }
  };
  
  return (
    <div className={`tree-node ${isSelected ? 'bg-green-50 border-l-4 border-green-500' : ''}`} 
         style={{ marginLeft: `${depth * 20}px` }}>
      
      {/* Expand/Collapse toggle for parents */}
      <div className="flex items-start gap-1 p-2 hover:bg-gray-50 rounded cursor-pointer">
        <div className="flex items-center gap-1 flex-1">
          {hasChildren && (
            <button 
              onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}
              className="w-5 h-5 flex items-center justify-center text-gray-500 hover:text-gray-700"
            >
              {isExpanded ? '▼' : '▶'}
            </button>
          )}
          
          {/* Color indicator */}
          <div 
            className="w-4 h-4 rounded flex-shrink-0 border border-gray-300"
            style={{ backgroundColor: node.color || '#6b7280' }}
            title="Compartment color"
          />
          
          {/* Selection & Name */}
          {isEditing ? (
            <div className="flex-1 flex gap-1">
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1 px-2 py-0.5 text-sm border border-green-400 rounded focus:outline-none focus:ring-1 focus:ring-green-500"
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
              <button 
                onClick={(e) => { e.stopPropagation(); handleSaveEdit(); }}
                className="px-2 py-0.5 text-xs bg-green-600 text-white rounded hover:bg-green-700"
              >
                ✓
              </button>
              <button 
                onClick={(e) => { e.stopPropagation(); setIsEditing(false); setEditName(node.name); }}
                className="px-2 py-0.5 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                ✗
              </button>
            </div>
          ) : (
            <div className="flex-1">
              <span 
                onClick={() => onSelectNode(node.id)}
                className={`font-medium text-sm cursor-pointer hover:text-green-600 ${
                  isSelected ? 'text-green-700 font-bold' : 'text-gray-900'
                }`}
              >
                {node.name}
              </span>
              
              {/* Area display */}
              <div className="text-xs text-gray-500">
                {node.area_hectares.toFixed(2)} ha ({Math.round(node.area_sqm).toLocaleString()} m²)
              </div>
              
              {/* Child count badge */}
              {node.child_count > 0 && (
                <span className="inline-block mt-1 px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded">
                  {node.child_count} compartment{node.child_count > 1 ? 's' : ''}
                </span>
              )}
            </div>
          )}
        </div>
        
        {/* Actions (only show when not editing) */}
        {!isEditing && (
          <div className="flex items-center gap-1 ml-2">
            {/* Rename button - only for compartments/sub-compartments */}
            {node.is_compartment && (
              <button 
                onClick={(e) => { e.stopPropagation(); setIsEditing(true); setEditName(node.name); }}
                className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded"
                title="Rename compartment"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            )}
            
            {/* Sub-divide button (only for compartments that aren't locked) */}
            {!node.is_locked && node.is_compartment && (
              <button 
                onClick={(e) => { e.stopPropagation(); onSubDivide(node.id); }}
                className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                title="Sub-divide"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
            )}
            
            {/* Lock toggle button */}
            <button 
              onClick={(e) => { e.stopPropagation(); onToggleLock(node.id); }}
              className={`p-1 rounded ${
                node.is_locked 
                  ? 'text-red-600 hover:bg-red-50' 
                  : 'text-green-600 hover:bg-green-50'
              }`}
              title={node.is_locked ? 'Unlock' : 'Lock'}
            >
              {node.is_locked ? (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                </svg>
              )}
            </button>

            {/* Delete button - only for compartments */}
            {node.is_compartment && (
              <button 
                onClick={(e) => { e.stopPropagation(); onDeleteNode(node.id, node.name); }}
                className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                title="Delete compartment"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            )}
          </div>
        )}
      </div>
      
      {/* Children (recursive) */}
      {isExpanded && hasChildren && (
        <div className="children">
          {node.children.map((child: any) => (
            <TreeNodeComponent 
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
              onRenameNode={onRenameNode}
              onToggleLock={onToggleLock}
              onSubDivide={onSubDivide}
              onDeleteNode={onDeleteNode}
            />
          ))}
        </div>
      )}
    </div>
  );
}
