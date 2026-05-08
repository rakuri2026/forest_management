import React from 'react';
import { TreeNodeComponent } from './TreeNode';

interface CompartmentTreeNode {
  id: string;
  name: string;
  area_hectares: number;
  area_sqm: number;
  division_level: number;
  color: string | null;
  is_locked: boolean;
  child_count: number;
  is_compartment: boolean;
  compartment_code: string | null;
  children: CompartmentTreeNode[];
  tree_count?: number;
}

interface CompartmentTreeViewProps {
  tree: CompartmentTreeNode[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onRenameNode: (nodeId: string, newName: string) => void;
  onToggleLock: (nodeId: string) => void;
  onSubDivide: (nodeId: string) => void;
  onDeleteNode: (nodeId: string, nodeName: string) => void;
}

export function CompartmentTreeView({ 
  tree, 
  selectedNodeId,
  onSelectNode, 
  onRenameNode, 
  onToggleLock, 
  onSubDivide,
  onDeleteNode
}: CompartmentTreeViewProps) {
  
  const totalBlocks = tree.length;
  const totalCompartments = tree.reduce((sum, node) => sum + (node.child_count || 0), 0);
  
  return (
    <div className="compartment-tree h-full flex flex-col">
      {/* Header */}
      <div className="p-3 border-b bg-gray-50">
        <h3 className="text-sm font-semibold text-gray-900">Compartment Hierarchy</h3>
        <div className="flex gap-3 mt-1 text-xs text-gray-500">
          <span>{totalBlocks} blocks</span>
          <span>•</span>
          <span>{totalCompartments} compartments</span>
        </div>
      </div>
      
      {/* Tree Content */}
      <div className="flex-1 overflow-y-auto p-2">
        {tree.length === 0 ? (
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
            <p className="mt-2 text-sm">No blocks available</p>
            <p className="text-xs text-gray-400 mt-1">
              Create forest blocks first from the Map Creation tab
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {tree.map((node) => (
              <TreeNodeComponent 
                key={node.id}
                node={node}
                depth={0}
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
      
      {/* Info Footer */}
      <div className="p-3 border-t bg-blue-50 text-xs text-blue-800">
        <p className="font-medium mb-1">Information:</p>
        <ul className="space-y-0.5 list-disc list-inside">
          <li>Click compartment name to select on map</li>
          <li>Use ✏️ to rename, ➕ to sub-divide, 🗑️ to delete</li>
          <li><span className="text-green-600 font-medium">🔓 Unlocked</span> (can divide), <span className="text-red-600 font-medium">🔒 Locked</span></li>
        </ul>
      </div>
    </div>
  );
}
