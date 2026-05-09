import { useState, useEffect, useCallback } from 'react';
import { reportApi } from '../../services/api';

interface ReportTabProps {
  calculationId: string;
  forestName?: string;
  onNavigateToTab?: (tabId: string) => void;
  calculationData?: any;
}

interface DataComponent {
  status: 'complete' | 'empty' | 'partial';
  details: Record<string, any>;
}

interface DataCompleteness {
  components: Record<string, DataComponent>;
  readiness_score: number;
  complete_count: number;
  total_count: number;
}

interface SectionInfo {
  section: string;
  title_ne: string;
  title_en: string;
  status: 'available' | 'missing_data' | 'manual_input';
  auto_generate: boolean;
  subsections?: {
    key: string;
    title_ne: string;
    title_en: string;
    status: 'available' | 'missing_data';
    auto_generate: boolean;
  }[];
}

interface Metadata {
  forest_name: string;
  group_name: string;
  district: string;
  palika: string;
  ward: string;
  province: string;
  division: string;
  sub_division: string;
  address: string;
  serial_number: string;
  cf_code: string;
  cf_national_code: string;
  fy_start: string;
  fy_end: string;
}

export function ReportTab({ calculationId, forestName = '', calculationData }: ReportTabProps) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [dataCompleteness, setDataCompleteness] = useState<DataCompleteness | null>(null);
  const [availableSections, setAvailableSections] = useState<SectionInfo[]>([]);
  const [selectedSections, setSelectedSections] = useState<string[]>([]);

  const resultData = calculationData?.result_data || {};

  const [metadata, setMetadata] = useState<Metadata>({
    forest_name: forestName,
    group_name: '',
    district: resultData.whole_district || '',
    palika: resultData.whole_municipality || '',
    ward: resultData.whole_ward || '',
    province: resultData.whole_province || '',
    division: '',
    sub_division: '',
    address: '',
    serial_number: '',
    cf_code: '',
    cf_national_code: '',
    fy_start: '',
    fy_end: '',
  });
  const [generating, setGenerating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [previewHtml, setPreviewHtml] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [includeImages, setIncludeImages] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  const loadDataCompleteness = useCallback(async () => {
    try {
      const data = await reportApi.checkDataCompleteness(calculationId);
      setDataCompleteness(data);
    } catch (err) {
      setError('Failed to load data completeness check');
    }
  }, [calculationId]);

  const loadAvailableSections = useCallback(async () => {
    try {
      const data = await reportApi.getAvailableSections(calculationId);
      setAvailableSections(data.sections || []);

      // Auto-select available sections
      const autoSelect = (data.sections || [])
        .filter((s: SectionInfo) => s.status === 'available' && s.auto_generate)
        .map((s: SectionInfo) => s.section);
      setSelectedSections(autoSelect);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load available sections';
      setError(msg);
      console.error('Error loading sections:', err);
    }
  }, [calculationId]);

  useEffect(() => {
    loadDataCompleteness();
    loadAvailableSections();
  }, [loadDataCompleteness, loadAvailableSections]);

  const handleGenerate = async () => {
    if (selectedSections.length === 0) {
      setError('Please select at least one section to generate');
      return;
    }

    setGenerating(true);
    setProgress(0);
    setStatusMessage('Starting report generation...');
    setError(null);

    try {
      const result = await reportApi.generateReport(
        calculationId,
        metadata,
        selectedSections,
        includeImages
      );

      setJobId(result.job_id);

      // Poll for status
      const pollInterval = setInterval(async () => {
        const status = await reportApi.getReportStatus(result.job_id);
        setProgress(status.progress);
        setStatusMessage(`Generating sections: ${status.sections_completed.length}/${status.sections_total}`);

        if (status.status === 'completed') {
          clearInterval(pollInterval);
          setGenerating(false);
          setStatusMessage('Report generated successfully!');
          setStep(4);

          // Load preview
          const preview = await reportApi.previewReport(result.job_id);
          setPreviewHtml(preview.html);
        } else if (status.status === 'failed') {
          clearInterval(pollInterval);
          setGenerating(false);
          setError(status.error || 'Report generation failed');
        }
      }, 2000);
    } catch (err: any) {
      setGenerating(false);
      setError(err.response?.data?.detail || 'Failed to start report generation');
    }
  };

  const handleDownload = async () => {
    if (!jobId) return;
    try {
      await reportApi.downloadReport(jobId);
    } catch (err: any) {
      const msg = err.message || 'Failed to download report';
      setError(msg);
      console.error('Download error:', err);
    }
  };

  const toggleSection = (section: string) => {
    setSelectedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section]
    );
  };

  const toggleSectionExpand = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'complete':
        return <span className="text-green-500">&#x2705;</span>;
      case 'partial':
        return <span className="text-yellow-500">&#x26A0;&#xFE0F;</span>;
      default:
        return <span className="text-red-500">&#x274C;</span>;
    }
  };

  const componentLabels: Record<string, string> = {
    analysis: 'Analysis (Raster)',
    species: 'Species',
    sampling: 'Sampling Design',
    inventory: 'Tree Inventory',
    households: 'Household Survey',
    committees: 'Forest Committee',
    biodiversity: 'Biodiversity',
    activities: 'Yearly Activities',
    user_group: 'User Group',
  };

  return (
    <div className="p-4 space-y-4 bg-gray-50 min-h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800">
          &#x1F4CB; Report Generation (प्रतिवेदन)
        </h2>
        <div className="flex gap-2">
          <button
            onClick={() => setStep(1)}
            className={`px-3 py-1.5 text-sm rounded ${step === 1 ? 'bg-green-600 text-white' : 'bg-gray-200'}`}
          >
            1. Check Data
          </button>
          <button
            onClick={() => setStep(2)}
            className={`px-3 py-1.5 text-sm rounded ${step === 2 ? 'bg-green-600 text-white' : 'bg-gray-200'}`}
          >
            2. Metadata
          </button>
          <button
            onClick={() => setStep(3)}
            className={`px-3 py-1.5 text-sm rounded ${step === 3 ? 'bg-green-600 text-white' : 'bg-gray-200'}`}
          >
            3. Generate
          </button>
          <button
            onClick={() => setStep(4)}
            className={`px-3 py-1.5 text-sm rounded ${step === 4 ? 'bg-green-600 text-white' : 'bg-gray-200'}`}
          >
            4. Preview
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-500 hover:text-red-700">&#x2716;</button>
        </div>
      )}

      {/* Step 1: Data Completeness Check */}
      {step === 1 && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-lg font-semibold mb-3">Data Completeness Check</h3>

            {dataCompleteness && (
              <>
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-600">
                      Data Readiness: {Math.round(dataCompleteness.readiness_score * 100)}%
                    </span>
                    <span className="text-sm text-gray-600">
                      {dataCompleteness.complete_count}/{dataCompleteness.total_count} components ready
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className="bg-green-600 h-2.5 rounded-full transition-all duration-500"
                      style={{ width: `${dataCompleteness.readiness_score * 100}%` }}
                    ></div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(dataCompleteness.components).map(([key, component]) => (
                    <div
                      key={key}
                      className="flex items-center gap-2 p-2 bg-gray-50 rounded text-sm"
                    >
                      {getStatusIcon(component.status)}
                      <span className="font-medium">{componentLabels[key] || key}</span>
                      <span className="text-gray-400">- {component.status}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => setStep(2)}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Next: Fill Metadata &#x2192;
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Metadata */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-lg font-semibold mb-3">Report Metadata</h3>
            <p className="text-sm text-gray-500 mb-4">
              Location data auto-filled from analysis. Fill in remaining details for the cover page.
            </p>

            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded">
              <p className="text-sm font-medium text-green-800">
                &#x2705; Location auto-filled from analysis data
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Auto-filled location (read-only) */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Forest Name &#x2A;</label>
                <input
                  type="text"
                  value={metadata.forest_name}
                  onChange={(e) => setMetadata({ ...metadata, forest_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">User Group Name &#x2A;</label>
                <input
                  type="text"
                  value={metadata.group_name}
                  onChange={(e) => setMetadata({ ...metadata, group_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="Enter user group name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Province <span className="text-xs text-green-600 font-normal">(auto-filled)</span>
                </label>
                <input
                  type="text"
                  value={metadata.province}
                  onChange={(e) => setMetadata({ ...metadata, province: e.target.value })}
                  className="w-full px-3 py-2 border border-green-300 bg-green-50 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  District <span className="text-xs text-green-600 font-normal">(auto-filled)</span>
                </label>
                <input
                  type="text"
                  value={metadata.district}
                  onChange={(e) => setMetadata({ ...metadata, district: e.target.value })}
                  className="w-full px-3 py-2 border border-green-300 bg-green-50 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Municipality <span className="text-xs text-green-600 font-normal">(auto-filled)</span>
                </label>
                <input
                  type="text"
                  value={metadata.palika}
                  onChange={(e) => setMetadata({ ...metadata, palika: e.target.value })}
                  className="w-full px-3 py-2 border border-green-300 bg-green-50 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ward <span className="text-xs text-green-600 font-normal">(auto-filled)</span>
                </label>
                <input
                  type="text"
                  value={metadata.ward}
                  onChange={(e) => setMetadata({ ...metadata, ward: e.target.value })}
                  className="w-full px-3 py-2 border border-green-300 bg-green-50 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Address (Tole)</label>
                <input
                  type="text"
                  value={metadata.address}
                  onChange={(e) => setMetadata({ ...metadata, address: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="Enter address"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">FY Start (e.g., 2083/84) &#x2A;</label>
                <input
                  type="text"
                  value={metadata.fy_start}
                  onChange={(e) => setMetadata({ ...metadata, fy_start: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="2083/84"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">FY End (e.g., 2093/94) &#x2A;</label>
                <input
                  type="text"
                  value={metadata.fy_end}
                  onChange={(e) => setMetadata({ ...metadata, fy_end: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="2093/94"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Serial Number</label>
                <input
                  type="text"
                  value={metadata.serial_number}
                  onChange={(e) => setMetadata({ ...metadata, serial_number: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">CF Code</label>
                <input
                  type="text"
                  value={metadata.cf_code}
                  onChange={(e) => setMetadata({ ...metadata, cf_code: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">CF National Database Code</label>
                <input
                  type="text"
                  value={metadata.cf_national_code}
                  onChange={(e) => setMetadata({ ...metadata, cf_national_code: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                  placeholder="Optional"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
            >
              &#x2190; Back
            </button>
            <button
              onClick={() => setStep(3)}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Next: Select Sections &#x2192;
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Section Selection & Generation */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-lg font-semibold mb-3">Select Report Sections</h3>
            <p className="text-sm text-gray-500 mb-4">
              {selectedSections.length} sections selected
            </p>

            <div className="space-y-2">
              {availableSections.map((section) => (
                <div key={section.section} className="border rounded overflow-hidden">
                  <div className="flex items-center gap-2 p-3 bg-gray-50">
                    <input
                      type="checkbox"
                      checked={selectedSections.includes(section.section)}
                      onChange={() => toggleSection(section.section)}
                      disabled={section.status === 'missing_data' && !section.auto_generate}
                      className="w-4 h-4"
                    />
                    <span className="font-medium text-sm">
                      {section.section}. {section.title_ne}
                    </span>
                    <span className="text-xs text-gray-400 ml-2">{section.title_en}</span>
                    {section.status === 'missing_data' && (
                      <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded ml-auto">
                        Missing Data
                      </span>
                    )}
                    {section.status === 'manual_input' && (
                      <span className="text-xs bg-yellow-100 text-yellow-600 px-2 py-0.5 rounded ml-auto">
                        Manual Input
                      </span>
                    )}
                  </div>

                  {section.subsections && (
                    <div className="pl-8 pr-3 py-2 bg-white">
                      <button
                        onClick={() => toggleSectionExpand(section.section)}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        {expandedSections[section.section] ? '&#x25BC;' : '&#x25B6;'} Toggle Subsections
                      </button>
                      {expandedSections[section.section] && (
                        <div className="mt-2 space-y-1">
                          {section.subsections.map((sub) => (
                            <div key={sub.key} className="flex items-center gap-2 text-sm py-1">
                              <span className="text-gray-500">({sub.key})</span>
                              <span>{sub.title_ne}</span>
                              {sub.status === 'missing_data' && (
                                <span className="text-xs bg-red-100 text-red-500 px-1 rounded">No Data</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeImages}
                onChange={(e) => setIncludeImages(e.target.checked)}
                className="w-4 h-4"
              />
              <label className="text-sm">Include maps and charts in report</label>
            </div>
          </div>

          {generating && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="text-lg font-semibold mb-2">Generating Report...</h3>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="bg-green-600 h-3 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-600 mt-2">{statusMessage}</p>
            </div>
          )}

          <div className="flex justify-between">
            <button
              onClick={() => setStep(2)}
              className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
            >
              &#x2190; Back
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating || selectedSections.length === 0}
              className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {generating ? 'Generating...' : 'Generate Selected Sections'}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Preview & Download */}
      {step === 4 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Report Preview</h3>
            <div className="flex gap-2">
              <button
                onClick={handleDownload}
                disabled={!jobId}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                &#x1F4E5; Download .docx
              </button>
            </div>
          </div>

          {previewHtml ? (
            <div className="bg-white rounded-lg shadow p-4">
              <div
                dangerouslySetInnerHTML={{ __html: previewHtml }}
                className="prose max-w-none"
              />
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              <p className="text-lg">No report generated yet.</p>
              <p className="text-sm mt-2">Go to Step 3 to generate the report first.</p>
              <button
                onClick={() => setStep(3)}
                className="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Go to Generation
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
