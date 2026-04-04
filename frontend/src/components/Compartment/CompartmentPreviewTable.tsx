import React from 'react';
import { CompartmentPreview, SplitValidation } from './types';

interface CompartmentPreviewTableProps {
  compartments: CompartmentPreview[];
  validation: SplitValidation;
  totalAreaSqM: number;
}

export function CompartmentPreviewTable({
  compartments,
  validation,
  totalAreaSqM,
}: CompartmentPreviewTableProps) {
  return (
    <div className="space-y-4">
      {/* Validation status */}
      <div
        className={`p-4 rounded-lg border ${
          validation.is_valid
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}
      >
        <div className="flex items-center gap-2">
          {validation.is_valid ? (
            <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          <span className={`font-medium ${
            validation.is_valid ? 'text-green-800' : 'text-red-800'
          }`}>
            {validation.is_valid ? 'Split configuration is valid' : 'Split has errors'}
          </span>
        </div>

        {/* Warnings */}
        {validation.warnings.length > 0 && (
          <div className="mt-2 ml-7 space-y-1">
            {validation.warnings.map((warning, idx) => (
              <p key={idx} className="text-sm text-yellow-700">
                ⚠️ {warning}
              </p>
            ))}
          </div>
        )}

        {/* Errors */}
        {validation.errors.length > 0 && (
          <div className="mt-2 ml-7 space-y-1">
            {validation.errors.map((error, idx) => (
              <p key={idx} className="text-sm text-red-700">
                ❌ {error}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Compartment table */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                #
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Name
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Area (m²)
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Area (ha)
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Deviation
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Perimeter (m)
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Trees
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {compartments.map((comp) => (
              <tr key={comp.index} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm text-gray-500">
                  {comp.index}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">
                  {comp.name}
                </td>
                <td className="px-4 py-3 text-sm text-gray-700 text-right">
                  {comp.area_sqm.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-700 text-right">
                  {comp.area_hectares.toFixed(4)}
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                      Math.abs(comp.area_deviation_percent) > 10
                        ? 'bg-red-100 text-red-800'
                        : Math.abs(comp.area_deviation_percent) > 5
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {comp.area_deviation_percent > 0 ? '+' : ''}
                    {comp.area_deviation_percent.toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-700 text-right">
                  {comp.perimeter_m ? comp.perimeter_m.toFixed(1) : '-'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-700 text-right">
                  {comp.tree_count}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-gray-50">
            <tr>
              <td colSpan={2} className="px-4 py-3 text-sm font-medium text-gray-900">
                Total ({compartments.length} compartments)
              </td>
              <td className="px-4 py-3 text-sm font-medium text-gray-900 text-right">
                {totalAreaSqM.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-sm font-medium text-gray-900 text-right">
                {(totalAreaSqM / 10000).toFixed(4)}
              </td>
              <td colSpan={3}></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Area summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">Target Area per Compartment</p>
          <p className="text-lg font-semibold text-gray-900">
            {(totalAreaSqM / compartments.length).toLocaleString()} m²
          </p>
          <p className="text-xs text-gray-500">
            {((totalAreaSqM / compartments.length) / 10000).toFixed(4)} ha
          </p>
        </div>
        <div className="p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">Min Compartment</p>
          <p className="text-lg font-semibold text-gray-900">
            {Math.min(...compartments.map((c) => c.area_sqm)).toLocaleString()} m²
          </p>
        </div>
        <div className="p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">Max Compartment</p>
          <p className="text-lg font-semibold text-gray-900">
            {Math.max(...compartments.map((c) => c.area_sqm)).toLocaleString()} m²
          </p>
        </div>
      </div>
    </div>
  );
}
