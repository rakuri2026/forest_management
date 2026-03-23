import React from 'react';
import { X } from 'lucide-react';

interface LegendItem {
  color: string;
  label: string;
  value?: string;
}

interface MapLegendProps {
  type: 'landcover' | 'biomass' | null;
  onClose?: () => void;
}

export function MapLegend({ type, onClose }: MapLegendProps) {
  if (!type) return null;

  const getLandCoverItems = (): LegendItem[] => [
    { color: '#006400', label: 'Tree cover' },
    { color: '#FFBB22', label: 'Shrubland' },
    { color: '#FFFF4C', label: 'Grassland' },
    { color: '#F096FF', label: 'Cropland' },
    { color: '#FA0000', label: 'Built-up' },
    { color: '#B4B4B4', label: 'Bare / sparse vegetation' },
    { color: '#F0F0F0', label: 'Snow and ice' },
    { color: '#0064C8', label: 'Permanent water bodies' },
    { color: '#0096A0', label: 'Herbaceous wetland' },
    { color: '#00CF75', label: 'Mangroves' },
    { color: '#FAE6A0', label: 'Moss and lichen' },
  ];

  const getBiomassItems = (): LegendItem[] => [
    { color: '#003300', label: 'Very High', value: '> 150 Mg/ha' },
    { color: '#006600', label: 'High', value: '100-150 Mg/ha' },
    { color: '#228B22', label: 'Medium-High', value: '75-100 Mg/ha' },
    { color: '#90EE90', label: 'Medium', value: '50-75 Mg/ha' },
    { color: '#ADFF2F', label: 'Medium-Low', value: '25-50 Mg/ha' },
    { color: '#FFFF00', label: 'Low', value: '10-25 Mg/ha' },
    { color: '#FFD700', label: 'Very Low', value: '< 10 Mg/ha' },
  ];

  const items = type === 'landcover' ? getLandCoverItems() : getBiomassItems();
  const title = type === 'landcover'
    ? 'Land Cover Classification'
    : 'Above-Ground Biomass';
  const source = type === 'landcover'
    ? 'ESA WorldCover 2020 (10m)'
    : 'ESA CCI AGB 2022 Nepal (100m)';

  return (
    <div className="absolute bottom-6 left-6 bg-white rounded-lg shadow-lg p-4 z-[1000] max-w-xs">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-semibold text-gray-800 text-sm">{title}</h4>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            title="Close legend"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Legend Items */}
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {items.map((item, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div
              className="w-5 h-5 rounded border border-gray-300 flex-shrink-0"
              style={{ backgroundColor: item.color }}
            />
            <div className="flex-1 min-w-0">
              <span className="text-xs text-gray-700">{item.label}</span>
              {item.value && (
                <span className="text-xs text-gray-500 ml-1">({item.value})</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Source */}
      <div className="mt-3 pt-3 border-t border-gray-200">
        <p className="text-xs text-gray-500">{source}</p>
      </div>
    </div>
  );
}
