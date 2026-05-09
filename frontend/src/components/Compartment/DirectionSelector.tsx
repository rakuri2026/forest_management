import React from 'react';
import { SplitDirection } from './types';

interface DirectionSelectorProps {
  directions: SplitDirection[];
  selectedAngle: number | null;
  onAngleChange: (angle: number | null) => void;
  disabled?: boolean;
}

export function DirectionSelector({
  directions,
  selectedAngle,
  onAngleChange,
  disabled = false,
}: DirectionSelectorProps) {
  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value === 'auto') {
      onAngleChange(null);
    } else {
      onAngleChange(parseFloat(value));
    }
  };

  const selectedDirection = directions.find(
    (d) => d.angle === selectedAngle
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <label className="text-sm font-medium text-gray-700">
          Split Direction
        </label>
        {selectedDirection && (
          <span className="text-sm text-green-600 font-medium">
            {selectedDirection.name}
          </span>
        )}
      </div>

      {/* Direction presets */}
      <div className="grid grid-cols-5 gap-2">
        {directions.map((dir) => (
          <button
            key={dir.name}
            onClick={() => onAngleChange(dir.angle)}
            disabled={disabled}
            className={`p-2 text-xs font-medium rounded border transition-all ${
              selectedAngle === dir.angle
                ? 'border-green-500 bg-green-100 text-green-800'
                : 'border-gray-200 hover:border-green-300 text-gray-700'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            title={dir.description}
          >
            {dir.angle !== null ? `${dir.angle}°` : 'Auto'}
          </button>
        ))}
      </div>

      {/* Custom angle slider */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <input
            type="range"
            min="0"
            max="180"
            step="15"
            value={selectedAngle !== null ? selectedAngle : 0}
            onChange={handleSliderChange}
            disabled={disabled || selectedAngle === null}
            className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-600 disabled:opacity-50"
          />
          <input
            type="number"
            min="0"
            max="360"
            value={selectedAngle ?? ''}
            onChange={(e) => {
              const value = e.target.value;
              if (value === '') {
                onAngleChange(null);
              } else {
                const num = parseInt(value);
                if (!isNaN(num) && num >= 0 && num <= 360) {
                  onAngleChange(num);
                }
              }
            }}
            disabled={disabled || selectedAngle === null}
            className="w-20 px-2 py-1 text-sm border border-gray-300 rounded text-center disabled:opacity-50"
            placeholder="0-360"
          />
        </div>
        <p className="text-xs text-gray-500 text-center">
          {selectedAngle !== null
            ? `${selectedAngle}° - ${getDirectionDescription(selectedAngle)}`
            : 'Auto-detect optimal direction based on block shape'}
        </p>
      </div>
    </div>
  );
}

function getDirectionDescription(angle: number): string {
  if (angle >= 337.5 || angle < 22.5) return 'North-South (vertical strips)';
  if (angle >= 22.5 && angle < 67.5) return 'Northeast-Southwest';
  if (angle >= 67.5 && angle < 112.5) return 'East-West (horizontal strips)';
  if (angle >= 112.5 && angle < 157.5) return 'Northwest-Southeast';
  if (angle >= 157.5 && angle < 202.5) return 'North-South (vertical strips)';
  if (angle >= 202.5 && angle < 247.5) return 'Northeast-Southwest';
  if (angle >= 247.5 && angle < 292.5) return 'East-West (horizontal strips)';
  if (angle >= 292.5 && angle < 337.5) return 'Northwest-Southeast';
  return '';
}
