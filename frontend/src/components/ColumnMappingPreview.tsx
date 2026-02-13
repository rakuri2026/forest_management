import { useState } from 'react';

interface ColumnMappingPreviewProps {
  previewData: {
    filename: string;
    total_rows: number;
    csv_columns: string[];
    sample_data: Record<string, any>[];
    mapping: Record<string, string>;
    confidence: Record<string, number>;
    unmapped_columns: string[];
    missing_required: string[];
    duplicates: Record<string, string[]>;
    needs_user_input: boolean;
    required_columns: string[];
    optional_columns: string[];
  };
  onConfirm: (mapping: Record<string, string>, savePreference: boolean) => void;
  onCancel: () => void;
}

export default function ColumnMappingPreview({
  previewData,
  onConfirm,
  onCancel,
}: ColumnMappingPreviewProps) {
  const [mapping, setMapping] = useState<Record<string, string>>(
    previewData.mapping
  );
  const [savePreference, setSavePreference] = useState(false);

  const allStandardColumns = [
    ...previewData.required_columns,
    ...previewData.optional_columns,
    '_ignore', // Option to ignore a column
  ];

  const handleColumnChange = (csvCol: string, stdCol: string) => {
    setMapping((prev) => ({ ...prev, [csvCol]: stdCol }));
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 90) return 'bg-green-500';
    if (confidence >= 70) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getConfidenceText = (confidence: number) => {
    if (confidence >= 90) return 'text-green-700';
    if (confidence >= 70) return 'text-yellow-700';
    return 'text-red-700';
  };

  // Check if mapping is valid
  const mappedValues = Object.values(mapping).filter((v) => v !== '_ignore');
  const missingRequired = previewData.required_columns.filter(
    (col) => !mappedValues.includes(col)
  );

  // Check for duplicates in current mapping
  const currentDuplicates: Record<string, string[]> = {};
  Object.entries(mapping).forEach(([csvCol, stdCol]) => {
    if (stdCol !== '_ignore') {
      if (!currentDuplicates[stdCol]) {
        currentDuplicates[stdCol] = [];
      }
      currentDuplicates[stdCol].push(csvCol);
    }
  });
  const hasDuplicates = Object.values(currentDuplicates).some(
    (cols) => cols.length > 1
  );

  const canConfirm = missingRequired.length === 0 && !hasDuplicates;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 rounded-t-lg">
          <h2 className="text-2xl font-bold text-gray-900">
            Column Mapping Confirmation
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            File: <span className="font-medium">{previewData.filename}</span> ({previewData.total_rows} rows)
          </p>
        </div>

        <div className="px-6 py-4 space-y-6">
          {/* Warnings */}
          {(missingRequired.length > 0 || hasDuplicates) && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start">
                <svg
                  className="h-5 w-5 text-red-600 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">
                    Mapping Issues Detected
                  </h3>
                  <div className="mt-2 text-sm text-red-700 space-y-1">
                    {missingRequired.length > 0 && (
                      <p>
                        Missing required columns:{' '}
                        <span className="font-semibold">
                          {missingRequired.join(', ')}
                        </span>
                      </p>
                    )}
                    {hasDuplicates && (
                      <div>
                        <p className="font-semibold">Duplicate mappings:</p>
                        <ul className="list-disc list-inside ml-2">
                          {Object.entries(currentDuplicates)
                            .filter(([_, cols]) => cols.length > 1)
                            .map(([stdCol, csvCols]) => (
                              <li key={stdCol}>
                                {stdCol} is mapped from: {csvCols.join(', ')}
                              </li>
                            ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sample Data Preview */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              Sample Data (first 5 rows)
            </h3>
            <div className="overflow-x-auto border rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {previewData.csv_columns.map((col) => (
                      <th
                        key={col}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {previewData.sample_data.slice(0, 5).map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      {previewData.csv_columns.map((col) => (
                        <td
                          key={col}
                          className="px-4 py-2 text-sm text-gray-900 whitespace-nowrap"
                        >
                          {row[col] !== null && row[col] !== undefined
                            ? String(row[col])
                            : '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Column Mapping Table */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              Column Mapping
            </h3>
            <div className="overflow-x-auto border rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                      Your Column
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                      Maps To
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                      Confidence
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {previewData.csv_columns.map((csvCol) => {
                    const stdCol = mapping[csvCol] || '';
                    const conf = previewData.confidence[csvCol] || 0;
                    const isRequired =
                      previewData.required_columns.includes(stdCol);

                    return (
                      <tr key={csvCol} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">
                          {csvCol}
                        </td>
                        <td className="px-4 py-3">
                          <select
                            value={stdCol}
                            onChange={(e) =>
                              handleColumnChange(csvCol, e.target.value)
                            }
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 text-sm"
                          >
                            <option value="">-- Select Column --</option>
                            <optgroup label="Required">
                              {previewData.required_columns.map((col) => (
                                <option key={col} value={col}>
                                  {col}
                                </option>
                              ))}
                            </optgroup>
                            <optgroup label="Optional">
                              {previewData.optional_columns.map((col) => (
                                <option key={col} value={col}>
                                  {col}
                                </option>
                              ))}
                            </optgroup>
                            <optgroup label="Other">
                              <option value="_ignore">Ignore Column</option>
                            </optgroup>
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          {conf > 0 && (
                            <div className="flex items-center gap-2">
                              <div className="w-24 bg-gray-200 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full ${getConfidenceColor(
                                    conf
                                  )}`}
                                  style={{ width: `${conf}%` }}
                                ></div>
                              </div>
                              <span className={`text-sm font-medium ${getConfidenceText(conf)}`}>
                                {conf}%
                              </span>
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isRequired && stdCol !== '_ignore' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                              Required
                            </span>
                          )}
                          {stdCol === '_ignore' && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                              Ignored
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Save Preference Checkbox */}
          <div className="flex items-center">
            <input
              id="save-preference"
              type="checkbox"
              checked={savePreference}
              onChange={(e) => setSavePreference(e.target.checked)}
              className="h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded"
            />
            <label
              htmlFor="save-preference"
              className="ml-2 block text-sm text-gray-700"
            >
              Remember this mapping for future uploads
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 px-6 py-4 border-t border-gray-200 rounded-b-lg flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(mapping, savePreference)}
            disabled={!canConfirm}
            className={`px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 ${
              canConfirm
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-gray-300 cursor-not-allowed'
            }`}
          >
            Confirm & Upload
          </button>
        </div>
      </div>
    </div>
  );
}
