import React, { useState, useEffect } from 'react';
import { AvailableBlock, SplitDirection, SplitPreviewResponse, SplitConfig } from './types';
import { compartmentApi } from '../../services/api';
import { SplitMethodSelector } from './SplitMethodSelector';
import { DirectionSelector } from './DirectionSelector';
import { CompartmentPreviewTable } from './CompartmentPreviewTable';
import { SplitPreviewMap } from './SplitPreviewMap';

interface SplitConfigurationPanelProps {
  block: AvailableBlock;
  onExecuteSplit: (config: SplitConfig) => Promise<void>;
  onPreviewSplit: (config: SplitConfig) => Promise<SplitPreviewResponse | null>;
  loading?: boolean;
}

export function SplitConfigurationPanel({
  block,
  onExecuteSplit,
  onPreviewSplit,
  loading = false,
}: SplitConfigurationPanelProps) {
  const [method, setMethod] = useState<'parallel' | 'grid' | 'custom'>('parallel');
  const [directions, setDirections] = useState<SplitDirection[]>([]);
  const [directionAngle, setDirectionAngle] = useState<number | null>(null);
  const [numCompartments, setNumCompartments] = useState(8);
  const [gridRows, setGridRows] = useState(4);
  const [gridColumns, setGridColumns] = useState(2);
  const [namingPattern, setNamingPattern] = useState('{block_name}-C{index}');
  const [reassignTrees, setReassignTrees] = useState(true);
  const [notes, setNotes] = useState('');

  const [previewData, setPreviewData] = useState<SplitPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDirections();
  }, []);

  useEffect(() => {
    if (block.has_compartments) {
      setPreviewData(null);
    }
  }, [block.id, block.has_compartments]);

  const loadDirections = async () => {
    try {
      const dirs = await compartmentApi.getSplitDirections();
      setDirections(dirs);
    } catch (err) {
      console.error('Failed to load directions:', err);
      setDirections([
        { name: 'North-South', angle: 0, description: 'Vertical strips' },
        { name: 'East-West', angle: 90, description: 'Horizontal strips' },
        { name: 'Optimal', angle: null, description: 'Auto-detect' },
      ]);
    }
  };

  const handlePreview = async () => {
    setPreviewData(null);
    setError(null);
    setPreviewLoading(true);

    try {
      const config: SplitConfig = {
        method,
        parameters: {
          direction_angle: method === 'parallel' ? directionAngle ?? undefined : undefined,
          num_compartments: method === 'parallel' ? numCompartments : undefined,
          rows: method === 'grid' ? gridRows : undefined,
          columns: method === 'grid' ? gridColumns : undefined,
          min_area_sqm: 1000,
          max_deviation_percent: 10,
        },
      };

      const preview = await onPreviewSplit(config);
      setPreviewData(preview);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Preview failed');
      setPreviewData(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!previewData) return;

    if (!confirm(`Are you sure you want to split "${block.name}" into ${previewData.compartments.length} compartments?`)) {
      return;
    }

    try {
      setError(null);
      setExecuting(true);

      const config: SplitConfig = {
        method,
        parameters: {
          direction_angle: method === 'parallel' ? directionAngle ?? undefined : undefined,
          num_compartments: method === 'parallel' ? numCompartments : undefined,
          rows: method === 'grid' ? gridRows : undefined,
          columns: method === 'grid' ? gridColumns : undefined,
          min_area_sqm: 1000,
          max_deviation_percent: 10,
        },
        naming_pattern: namingPattern,
        reassign_trees: reassignTrees,
        notes: notes || undefined,
      };

      await onExecuteSplit(config);
      setPreviewData(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Split execution failed');
    } finally {
      setExecuting(false);
    }
  };

  const handleClearPreview = () => {
    setPreviewData(null);
  };

  if (block.has_compartments) {
    return (
      <div className="space-y-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="font-medium text-blue-900">
              This block already has compartments
            </span>
          </div>
          <p className="text-sm text-blue-700 mt-1 ml-7">
            Block "{block.name}" has been split into {block.compartment_count} compartments.
            To split it differently, first delete the existing compartments.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Configuration */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-6">
        <h3 className="text-lg font-semibold text-gray-900">
          Configure Split: {block.name}
        </h3>
        <p className="text-sm text-gray-500">
          Block area: {block.area_hectares.toFixed(2)} ha ({block.area_sqm.toLocaleString()} m²)
        </p>

        {/* Method Selection */}
        <SplitMethodSelector method={method} onMethodChange={setMethod} />

        {/* Method-specific options */}
        {method === 'parallel' && (
          <div className="space-y-4 border-t pt-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Compartments
              </label>
              <input
                type="number"
                value={numCompartments}
                onChange={(e) => setNumCompartments(Math.max(2, parseInt(e.target.value) || 2))}
                min={2}
                max={20}
                className="w-32 px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="mt-1 text-xs text-gray-500">
                Target area per compartment: {(block.area_sqm / numCompartments).toLocaleString()} m²
              </p>
            </div>

            <DirectionSelector
              directions={directions}
              selectedAngle={directionAngle}
              onAngleChange={setDirectionAngle}
            />
          </div>
        )}

        {method === 'grid' && (
          <div className="space-y-4 border-t pt-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Rows
                </label>
                <input
                  type="number"
                  value={gridRows}
                  onChange={(e) => setGridRows(Math.max(1, parseInt(e.target.value) || 1))}
                  min={1}
                  max={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Columns
                </label>
                <input
                  type="number"
                  value={gridColumns}
                  onChange={(e) => setGridColumns(Math.max(1, parseInt(e.target.value) || 1))}
                  min={1}
                  max={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>
            <p className="text-xs text-gray-500">
              Total compartments: {gridRows * gridColumns} 
              • Target area per compartment: {(block.area_sqm / (gridRows * gridColumns)).toLocaleString()} m²
            </p>
          </div>
        )}

        {/* Naming pattern */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Naming Pattern
          </label>
          <input
            type="text"
            value={namingPattern}
            onChange={(e) => setNamingPattern(e.target.value)}
            placeholder="{block_name}-C{index}"
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
          />
          <p className="mt-1 text-xs text-gray-500">
            Use {"{block_name}"} for the original block name and {"{index}"} for compartment number
          </p>
        </div>

        {/* Tree reassignment */}
        {block.tree_count > 0 && (
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="reassignTrees"
              checked={reassignTrees}
              onChange={(e) => setReassignTrees(e.target.checked)}
              className="w-4 h-4 text-green-600 border-gray-300 rounded"
            />
            <label htmlFor="reassignTrees" className="text-sm text-gray-700">
              Automatically assign {block.tree_count} existing trees to compartments by GPS location
            </label>
          </div>
        )}

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            placeholder="Add notes about this split operation..."
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={handlePreview}
            disabled={previewLoading || loading}
            className="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {previewLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                Generating Preview...
              </>
            ) : (
              'Preview Split'
            )}
          </button>
        </div>
      </div>

      {/* Preview results */}
      {previewData && (
        <div className="space-y-4">
          {/* Preview map */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <SplitPreviewMap
              block={block}
              compartments={previewData.compartments}
            />
          </div>

          {/* Preview table */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              Compartment Preview ({previewData.compartments.length} compartments)
            </h4>
            <CompartmentPreviewTable
              compartments={previewData.compartments}
              validation={previewData.validation}
              totalAreaSqM={previewData.total_area_sqm}
            />
          </div>

          {/* Execute/Cancel buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleClearPreview}
              className="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={executing || !previewData.validation.is_valid}
              className="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {executing ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Creating Compartments...
                </>
              ) : (
                `Create ${previewData.compartments.length} Compartments`
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
