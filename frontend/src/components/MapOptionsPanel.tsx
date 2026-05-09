import React from 'react';
import {
  MapOptions,
  DEFAULT_MAP_OPTIONS,
  MAP_TYPE_INFO,
} from '../constants/analysisPresets';

interface MapOptionsPanelProps {
  options: MapOptions;
  onChange: (options: MapOptions) => void;
  disabled?: boolean;
}

const MapOptionsPanel: React.FC<MapOptionsPanelProps> = ({
  options,
  onChange,
  disabled = false,
}) => {
  const handleOptionChange = (key: keyof MapOptions, value: boolean) => {
    const updatedOptions = { ...options, [key]: value };
    onChange(updatedOptions);
  };

  const handleSelectAll = () => {
    const allSelected: MapOptions = {
      generate_boundary_map: true,
      generate_topographic_map: true,
      generate_slope_map: true,
      generate_aspect_map: true,
      generate_forest_type_map: true,
      generate_canopy_height_map: true,
      generate_landcover_change_map: true,
      generate_soil_map: true,
      generate_forest_health_map: true,
    };
    onChange(allSelected);
  };

  const handleDeselectAll = () => {
    onChange(DEFAULT_MAP_OPTIONS);
  };

  const handleSelectImplemented = () => {
    const implementedOnly: MapOptions = {
      generate_boundary_map: true,
      generate_topographic_map: false,
      generate_slope_map: true,
      generate_aspect_map: true,
      generate_forest_type_map: false,
      generate_canopy_height_map: false,
      generate_landcover_change_map: true,
      generate_soil_map: false,
      generate_forest_health_map: false,
    };
    onChange(implementedOnly);
  };

  const selectedCount = Object.values(options).filter(Boolean).length;
  const implementedCount = Object.entries(MAP_TYPE_INFO).filter(([_, info]) => info.implemented).length;

  return (
    <div className="border rounded-lg p-6 bg-white">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Map Generation Options</h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSelectImplemented}
            disabled={disabled}
            className="text-sm px-3 py-1 border border-green-300 text-green-700 rounded hover:bg-green-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Select Available ({implementedCount})
          </button>
          <button
            type="button"
            onClick={handleSelectAll}
            disabled={disabled}
            className="text-sm px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Select All
          </button>
          <button
            type="button"
            onClick={handleDeselectAll}
            disabled={disabled}
            className="text-sm px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Deselect All
          </button>
        </div>
      </div>

      {/* Info Box */}
      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="text-sm text-blue-800">
          <strong>Map Format:</strong> A5 PNG (1748×2480 pixels at 300 DPI)
          <br />
          <strong>Features:</strong> Professional styling, title, legend, scale bar, north arrow
          <br />
          <strong>Generation:</strong> Maps are generated on-demand and not stored permanently
        </div>
      </div>

      {/* Map Options Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {(Object.entries(MAP_TYPE_INFO) as [keyof MapOptions, typeof MAP_TYPE_INFO[keyof MapOptions]][]).map(([key, info]) => {
          const isChecked = options[key];
          const isImplemented = info.implemented;

          return (
            <label
              key={key}
              className={`flex items-start p-3 border rounded-lg cursor-pointer transition-all ${
                isChecked
                  ? 'border-green-500 bg-green-50 ring-2 ring-green-200'
                  : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
              } ${
                !isImplemented ? 'opacity-60' : ''
              } ${
                disabled ? 'cursor-not-allowed opacity-50' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={(e) => handleOptionChange(key, e.target.checked)}
                disabled={disabled}
                className="w-4 h-4 mt-0.5 text-green-600 rounded focus:ring-green-500 disabled:opacity-50"
              />
              <div className="ml-3 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{info.label}</span>
                  {!isImplemented && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                      Coming Soon
                    </span>
                  )}
                  {isImplemented && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                      Available
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-600 mt-1">{info.description}</p>
                {!isImplemented && (
                  <p className="text-xs text-yellow-600 mt-1 italic">
                    This map type will be available in a future update
                  </p>
                )}
              </div>
            </label>
          );
        })}
      </div>

      {/* Summary */}
      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex items-center justify-between text-xs text-blue-800">
          <div>
            <strong>Selected:</strong> {selectedCount} / {Object.keys(options).length} maps
          </div>
          <div>
            <strong>Estimated Time:</strong> ~{selectedCount * 5} seconds (5s per map)
          </div>
        </div>
      </div>

      {/* Warning for not implemented maps */}
      {Object.entries(options).some(([key, value]) => value && !MAP_TYPE_INFO[key as keyof MapOptions].implemented) && (
        <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-yellow-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div className="ml-2 text-sm text-yellow-800">
              <strong>Note:</strong> Some selected maps are not yet implemented and will not be generated.
              Only available maps will be created.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MapOptionsPanel;
