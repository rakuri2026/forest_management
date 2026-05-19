import { useState, useEffect } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, LineChart, Line,
} from 'recharts';
import { fieldInventoryApi } from '../services/api';
import { downloadBlob } from '../utils/download';

interface ManagementPlanTabProps {
  calculationId: string;
  fieldInventoryId?: string;
  forestName?: string;
}

interface GroupConfig {
  id: string;
  label: string;
  en: string;
  charts: string[];
}

const GROUPS: GroupConfig[] = [
  { id: 'structure',     label: 'वन संरचना',     en: 'Forest Structure',     charts: ['species', 'dbh', 'structure', 'growth'] },
  { id: 'block-analysis', label: 'ब्लक विश्लेषण', en: 'Block Analysis',       charts: ['blocks', 'harvest', 'carbon'] },
  { id: 'condition',     label: 'वन अवस्था',     en: 'Forest Condition',     charts: ['condition', 'productivity'] },
  { id: 'landcover',     label: 'भू-आवरण',       en: 'Land Cover & Type',    charts: ['landcover-pie', 'forest-type-pie', 'landcover-block'] },
  { id: 'health-loss',   label: 'हानि/लाभ',      en: 'Loss/Gain & Health',  charts: ['health-pie', 'canopy-pie', 'loss-gain'] },
  { id: 'terrain-soil',  label: 'भू-बनोट',       en: 'Terrain & Soil',       charts: ['slope-pie', 'soil'] },
];

const COLORS = ['#2e7d32', '#4caf50', '#a5d6a7', '#1565c0', '#42a5f5', '#795548', '#f9a825', '#c62828', '#78909c', '#8bc34a'];
const CONDITION_COLORS: Record<string, string> = { Good: '#2e7d32', Moderate: '#f9a825', Weak: '#c62828' };
const HEALTH_COLORS: Record<string, string> = { excellent: '#1b5e20', healthy: '#4caf50', moderate: '#f9a825', poor: '#ff9800', stressed: '#c62828' };
const CANOPY_COLORS: Record<string, string> = { high_forest: '#1b5e20', pole_trees: '#4caf50', bush_regenerated: '#a5d6a7', non_forest: '#d4d4d4' };
const SLOPE_COLORS: Record<string, string> = { flat: '#a5d6a7', gentle: '#4caf50', moderate: '#f9a825', steep: '#ff9800', very_steep: '#c62828' };

function getPercentColor(key: string, map: Record<string, string>): string {
  for (const [k, v] of Object.entries(map)) {
    if (key.toLowerCase().includes(k)) return v;
  }
  return '#78909c';
}

export function ManagementPlanTab({ calculationId, fieldInventoryId: propFiId, forestName = 'Forest' }: ManagementPlanTabProps) {
  const [activeGroup, setActiveGroup] = useState('structure');
  const [mgmtData, setMgmtData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aahGood, setAahGood] = useState(75);
  const [aahModerate, setAahModerate] = useState(60);
  const [aahWeak, setAahWeak] = useState(40);
  const [fieldInventoryId, setFieldInventoryId] = useState<string | undefined>(propFiId);

  useEffect(() => {
    if (propFiId) { setFieldInventoryId(propFiId); return; }
    (async () => {
      try {
        const fi = await fieldInventoryApi.getByCalculation(calculationId);
        if (fi?.id) setFieldInventoryId(fi.id);
      } catch { /* no field inventory */ }
    })();
  }, [calculationId, propFiId]);

  useEffect(() => {
    if (!fieldInventoryId) return;
    fetchData();
  }, [fieldInventoryId, calculationId, aahGood, aahModerate, aahWeak]);

  const fetchData = async () => {
    if (!fieldInventoryId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fieldInventoryApi.getManagementPlanData(fieldInventoryId, calculationId, aahGood, aahModerate, aahWeak);
      setMgmtData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const [showPlanDialog, setShowPlanDialog] = useState(false);
  const [includeMaps, setIncludeMaps] = useState(true);
  const [includeCharts, setIncludeCharts] = useState(true);
  const [generating, setGenerating] = useState(false);

  const handleExportDocx = async () => {
    if (!fieldInventoryId) return;
    try {
      const blob = await fieldInventoryApi.exportManagementPlanDocx(fieldInventoryId, calculationId, aahGood, aahModerate, aahWeak);
      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      downloadBlob(blob, `${forestName.replace(/\s/g, '_')}_ManagementPlan_${dateStr}.docx`);
    } catch (err: any) {
      setError('DOCX export failed: ' + err.message);
    }
  };

  const handleExport10yrPlan = async () => {
    if (!fieldInventoryId) return;
    setGenerating(true);
    setError(null);
    try {
      const blob = await fieldInventoryApi.export10yrPlanDocx(
        fieldInventoryId, calculationId, aahGood, aahModerate, aahWeak, includeMaps, includeCharts
      );
      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      downloadBlob(blob, `${forestName.replace(/\s/g, '_')}_10Yr_ManagementPlan_${dateStr}.docx`);
      setShowPlanDialog(false);
    } catch (err: any) {
      setError('10-Year Plan export failed: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleExportDfo = async () => {
    if (!fieldInventoryId) return;
    try {
      const blob = await fieldInventoryApi.exportDfoSummary(fieldInventoryId, calculationId, aahGood, aahModerate, aahWeak);
      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      downloadBlob(blob, `${forestName.replace(/\s/g, '_')}_FieldInventory_DFOSummary_${dateStr}.xlsx`);
    } catch (err: any) {
      setError('Excel export failed: ' + err.message);
    }
  };

  const renderChart = (chartId: string) => {
    if (!mgmtData) return null;
    switch (chartId) {
      case 'species':        return <SpeciesChart data={mgmtData.species_composition} />;
      case 'blocks':         return <BlockChart data={mgmtData.block_comparison} />;
      case 'harvest':        return <HarvestChart data={mgmtData.annual_harvest_plan} />;
      case 'condition':      return <ConditionChart data={mgmtData.forest_condition_summary} />;
      case 'dbh':            return <DbhClassChart data={mgmtData.dbh_class_volume} />;
      case 'carbon':         return <CarbonChart data={mgmtData.carbon_per_block} />;
      case 'growth':         return <GrowthChart data={mgmtData.growth_rate_classification} />;
      case 'structure':      return <StructureChart data={mgmtData.stand_structure} />;
      case 'productivity':   return <ProductivityChart data={mgmtData.productivity_classification} />;
      case 'landcover-pie':  return <PercentPieChart title="भू-आवरण वितरण — Land Cover Distribution" data={mgmtData.raster_analysis?.landcover_percentages} />;
      case 'forest-type-pie':return <PercentPieChart title="वन प्रकार वितरण — Forest Type Distribution" data={mgmtData.raster_analysis?.forest_type_percentages} />;
      case 'health-pie':     return <PercentPieChart title="वन स्वास्थ्य वितरण — Forest Health Distribution" data={mgmtData.raster_analysis?.forest_health_percentages} colorMap={HEALTH_COLORS} />;
      case 'canopy-pie':     return <PercentPieChart title="वन छाना वितरण — Canopy Cover Distribution" data={mgmtData.raster_analysis?.canopy_percentages} colorMap={CANOPY_COLORS} />;
      case 'slope-pie':      return <PercentPieChart title="भिरालो वर्ग वितरण — Slope Class Distribution" data={mgmtData.raster_analysis?.slope_percentages} colorMap={SLOPE_COLORS} />;
      case 'loss-gain':      return <LossGainChart data={mgmtData.raster_analysis} />;
      case 'landcover-block':return <BlockRasterChart title="ब्लक अनुसार भू-आवरण — Land Cover by Block" data={mgmtData.blocks_raster} dataKey="landcover_percentages" />;
      case 'soil':           return <SoilChart data={mgmtData.raster_analysis} />;
      default: return null;
    }
  };

  const renderGroup = () => {
    const group = GROUPS.find(g => g.id === activeGroup);
    if (!group || !mgmtData) return null;
    const charts = group.charts.map(id => ({ id, el: renderChart(id) })).filter(c => c.el !== null);
    if (!charts.length) return <div className="text-center py-12 text-gray-400">No data available for this group</div>;
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {charts.map(c => (
          <div key={c.id} className="bg-white rounded-lg border p-3">{c.el}</div>
        ))}
      </div>
    );
  };

  if (!fieldInventoryId) {
    return (
      <div className="p-6 text-center text-gray-500">
        Please upload and process field inventory data first to access management plan graphics.
      </div>
    );
  }

  return (
    <>
    <div className="p-4 space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-green-800">व्यवस्थापन योजना ग्राफिक्स</h2>
        <div className="flex gap-2 items-center">
          <div className="flex items-center gap-1 text-xs">
            <span className="text-gray-600">AAH:</span>
            <input type="number" className="w-12 border rounded px-1 py-0.5 text-xs" value={aahGood}
              onChange={e => setAahGood(Number(e.target.value))} title="Good %" />
            <input type="number" className="w-12 border rounded px-1 py-0.5 text-xs" value={aahModerate}
              onChange={e => setAahModerate(Number(e.target.value))} title="Moderate %" />
            <input type="number" className="w-12 border rounded px-1 py-0.5 text-xs" value={aahWeak}
              onChange={e => setAahWeak(Number(e.target.value))} title="Weak %" />
          </div>
          <button onClick={() => setShowPlanDialog(true)}
            className="px-3 py-1.5 bg-amber-700 text-white rounded text-xs hover:bg-amber-800 font-bold">१० वर्षे योजना DOCX</button>
          <button onClick={handleExportDocx}
            className="px-3 py-1.5 bg-green-700 text-white rounded text-xs hover:bg-green-800">DOCX डाउनलोड</button>
          <button onClick={handleExportDfo}
            className="px-3 py-1.5 bg-blue-800 text-white rounded text-xs hover:bg-blue-900">Excel डाउनलोड</button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b pb-2">
        {GROUPS.map(group => (
          <button key={group.id} onClick={() => setActiveGroup(group.id)}
            className={`px-3 py-1.5 rounded-t text-xs font-medium transition-colors ${activeGroup === group.id ? 'bg-green-700 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}>
            {group.label}
          </button>
        ))}
      </div>

      {error && <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>}
      {loading && <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-700" /></div>}
      {!loading && mgmtData && renderGroup()}
    </div>

      {/* 10-Year Plan Dialog */}
      {showPlanDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold text-green-800 mb-4">१० वर्षे व्यवस्थापन योजना उत्पन्न गर्नुहोस्</h3>
            <p className="text-xs text-gray-500 mb-4">Generate 10-Year Management Plan</p>

            <div className="space-y-3">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={includeMaps}
                  onChange={e => setIncludeMaps(e.target.checked)} />
                <span className="text-sm">नक्साहरू समावेश गर्नुहोस् (Include Maps)</span>
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={includeCharts}
                  onChange={e => setIncludeCharts(e.target.checked)} />
                <span className="text-sm">चार्टहरू समावेश गर्नुहोस् (Include Charts)</span>
              </label>
              <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                <p className="font-semibold mb-1">योजनामा समावेश:</p>
                <ul className="list-disc pl-4 space-y-0.5">
                  <li>१२ अध्याय (परिचयदेखि अनुगमन सम्म)</li>
                  <li>प्रत्येक अध्यायमा नक्सा, चार्ट र तालिका</li>
                  <li>ब्लक अनुसार १० वर्षे कार्य तालिका</li>
                  <li>सिफारिसको आधार सहित</li>
                </ul>
              </div>
            </div>

            <div className="flex gap-2 mt-6 justify-end">
              <button onClick={() => setShowPlanDialog(false)} disabled={generating}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300">रद्द गर्नुहोस्</button>
              <button onClick={handleExport10yrPlan} disabled={generating}
                className="px-4 py-2 bg-amber-700 text-white rounded text-sm hover:bg-amber-800 flex items-center gap-2">
                {generating && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />}
                {generating ? 'उत्पन्न गर्दै...' : 'उत्पन्न गर्नुहोस्'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Helper: Generic Percentage Pie Chart ───

function PercentPieChart({ title, data, colorMap }: { title: string; data?: Record<string, number>; colorMap?: Record<string, string> }) {
  if (!data || !Object.keys(data).length) return <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Raster data not available. Run Analysis first.</div>;
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const pieData = entries.map(([name, value]) => ({ name, value }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">{title}</h3>
      <div className="h-56">
        <ResponsiveContainer><PieChart>
          <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75}
            label={({ name, value }) => `${name.replace(/_/g, ' ')} ${value.toFixed(1)}%`} labelLine={true}>
            {pieData.map((e, i) => (<Cell key={i} fill={colorMap ? getPercentColor(e.name, colorMap) : COLORS[i % COLORS.length]} />))}
          </Pie>
          <Tooltip />
        </PieChart></ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Helper: Block-wise Raster Stacked Bar ───

function BlockRasterChart({ title, data, dataKey }: { title: string; data?: any[]; dataKey: string }) {
  if (!data || !data.length) return <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Block raster data not available</div>;
  const allKeys = new Set<string>();
  data.forEach((b: any) => { const p = b[dataKey]; if (p) Object.keys(p).forEach(k => allKeys.add(k)); });
  const keys = Array.from(allKeys);
  if (!keys.length) return <div className="flex items-center justify-center h-48 text-gray-400 text-sm">No block raster data</div>;
  const chartData = data.map((b: any) => {
    const row: any = { name: b.block_name };
    const p = b[dataKey] || {};
    keys.forEach(k => { row[k] = p[k] || 0; });
    return row;
  });
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">{title}</h3>
      <div className="h-56">
        <ResponsiveContainer><BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" /><Tooltip /><Legend />
          {keys.map((k, i) => <Bar key={k} dataKey={k} stackId="a" fill={COLORS[i % COLORS.length]} />)}
        </BarChart></ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Helper: Empty State ───

function EmptyState() {
  return <div className="flex items-center justify-center h-48 text-gray-400">No data available for this section</div>;
}

// ══════════════════════════════════════════════════════════════
// GROUP 1: वन संरचना — Forest Structure Charts
// ══════════════════════════════════════════════════════════════

function SpeciesChart({ data }: { data: any }) {
  const species = data?.forest_wide || [];
  if (!species.length) return <EmptyState />;
  const pieData = species.map((s: any) => ({ name: s.local_name || s.scientific_name, value: s.volume_pct || 0 }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">प्रजाती संरचना — Species Composition</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <div className="h-60">
          <ResponsiveContainer><PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75}
              label={({ name, value }) => `${name.slice(0, 12)} ${value}%`} labelLine={true}>
              {pieData.map((_: any, i: number) => (<Cell key={i} fill={COLORS[i % COLORS.length]} />))}
            </Pie>
            <Tooltip />
          </PieChart></ResponsiveContainer>
        </div>
        <div className="overflow-auto max-h-60">
          <table className="w-full text-xs border-collapse">
            <thead><tr className="bg-green-700 text-white">
              <th className="p-1 text-left">Species</th><th className="p-1 text-right">m³/ha</th><th className="p-1 text-right">%</th>
            </tr></thead>
            <tbody>
              {species.map((s: any, i: number) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                  <td className="p-1">{s.local_name || s.scientific_name}</td>
                  <td className="p-1 text-right">{s.total_volume_m3_per_ha}</td>
                  <td className="p-1 text-right">{s.volume_pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function DbhClassChart({ data }: { data: any }) {
  const blocks = data?.blocks || [];
  if (!blocks.length) return <EmptyState />;
  const dbhLabels = ['10-20', '20-30', '30-40', '40-50', '50-60', '60+'];
  const chartData = blocks.map((b: any) => {
    const row: any = { name: b.block };
    b.classes?.forEach((c: any) => { row[c.dbh_class] = c.total_m3ha; });
    return row;
  });
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">DBH वर्ग आयतन — DBH Class Volume</h3>
      <div className="h-56">
        <ResponsiveContainer><BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis label={{ value: 'm³/ha', angle: -90, position: 'insideLeft' }} />
          <Tooltip /><Legend />
          {dbhLabels.map((l, i) => <Bar key={l} dataKey={l} stackId="a" fill={COLORS[i % COLORS.length]} />)}
        </BarChart></ResponsiveContainer>
      </div>
    </div>
  );
}

function StructureChart({ data }: { data: any }) {
  const blocks = data?.blocks || [];
  if (!blocks.length) return <EmptyState />;
  const dbhLabels = ['10-20', '20-30', '30-40', '40-50', '50-60', '60+'];
  const chartData = dbhLabels.map((l, i) => {
    const row: any = { name: l };
    blocks.forEach((b: any) => {
      const cls = b.classes?.[i] || {};
      row[b.block + ' Actual'] = cls.actual_nha || 0;
    });
    const firstCls = blocks[0].classes?.[i] || {};
    row.Ideal = firstCls.ideal_nha || 0;
    return row;
  });
  const lines: { dataKey: string; color: string; dash?: string }[] = [];
  blocks.forEach((b: any, idx: number) => {
    lines.push({ dataKey: b.block + ' Actual', color: COLORS[idx % COLORS.length] });
  });
  lines.push({ dataKey: 'Ideal', color: '#c62828', dash: '5 5' });
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">रुख संरचना — Stand Structure (All Blocks)</h3>
      <div className="h-56">
        <ResponsiveContainer><LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" label={{ value: 'DBH (cm)', position: 'bottom' }} />
          <YAxis label={{ value: 'N/ha', angle: -90, position: 'insideLeft' }} />
          <Tooltip /><Legend />
          {lines.map((l, i) => (
            <Line key={l.dataKey} type="monotone" dataKey={l.dataKey} stroke={l.color} strokeWidth={l.dash ? 2 : 1.5}
              strokeDasharray={l.dash} dot={{ r: l.dash ? 3 : 2 }} />
          ))}
        </LineChart></ResponsiveContainer>
      </div>
      {data.assessment && <div className="mt-1 p-1.5 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">{data.assessment}</div>}
    </div>
  );
}

function GrowthChart({ data }: { data: any }) {
  const classes = data?.classes || [];
  if (!classes.length) return <EmptyState />;
  const pieData = classes.map((c: any) => ({ name: c.rate, value: c.volume_pct }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">वृद्धि दर — Growth Rate</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <div className="h-48">
          <ResponsiveContainer><PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={60}
              label={({ name, value }) => `${name} ${value}%`}>
              {pieData.map((_: any, i: number) => (<Cell key={i} fill={COLORS[i]} />))}
            </Pie>
            <Tooltip />
          </PieChart></ResponsiveContainer>
        </div>
        <div className="overflow-auto max-h-48">
          <table className="w-full text-xs border-collapse">
            <thead><tr className="bg-green-700 text-white">
              <th className="p-1 text-left">Rate</th><th className="p-1 text-right">Sp.</th><th className="p-1 text-right">m³/ha</th><th className="p-1 text-right">%</th>
            </tr></thead>
            <tbody>
              {classes.map((c: any, i: number) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                  <td className="p-1">{c.rate}</td><td className="p-1 text-right">{c.species_count}</td>
                  <td className="p-1 text-right">{c.volume_m3_per_ha}</td><td className="p-1 text-right">{c.volume_pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// GROUP 2: ब्लक विश्लेषण — Block Analysis Charts
// ══════════════════════════════════════════════════════════════

function BlockChart({ data }: { data: any }) {
  const blocks = data?.ranked || [];
  if (!blocks.length) return <EmptyState />;
  const chartData = blocks.map((b: any) => ({
    name: b.name, 'Growing Stock': b.growing_stock_m3ha, 'AAH Timber': b.aah_timber_m3yr,
    fill: CONDITION_COLORS[b.condition] || '#78909c',
  }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">ब्लक तुलना — Block Comparison</h3>
      <div className="h-56">
        <ResponsiveContainer><BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={80} />
          <Tooltip /><Legend />
          <Bar dataKey="Growing Stock" fill={COLORS[0]} />
          <Bar dataKey="AAH Timber" fill={COLORS[3]} />
        </BarChart></ResponsiveContainer>
      </div>
    </div>
  );
}

function HarvestChart({ data }: { data: any }) {
  const blocks = data?.blocks || [];
  if (!blocks.length) return <EmptyState />;
  const chartData = blocks.map((b: any) => ({ name: b.name, 'AAH Timber': b.aah_timber_m3yr, 'AAH Fuelwood': b.aah_fuelwood_m3yr }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">वार्षिक फसल — Annual Harvest Plan</h3>
      <div className="h-48">
        <ResponsiveContainer><BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis label={{ value: 'm³/yr', angle: -90, position: 'insideLeft' }} />
          <Tooltip /><Legend />
          <Bar dataKey="AAH Timber" fill={COLORS[0]} />
          <Bar dataKey="AAH Fuelwood" fill={COLORS[6]} />
        </BarChart></ResponsiveContainer>
      </div>
    </div>
  );
}

function CarbonChart({ data }: { data: any }) {
  const blocks = data?.blocks || [];
  if (!blocks.length) return <EmptyState />;
  const chartData = blocks.map((b: any) => ({ name: b.block, AGB: b.agb_tha, BGB: b.bgb_tha }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">कार्बन भण्डार — Carbon Stock</h3>
      <div className="h-48">
        <ResponsiveContainer><BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis label={{ value: 't/ha', angle: -90, position: 'insideLeft' }} />
          <Tooltip /><Legend />
          <Bar dataKey="AGB" fill={COLORS[0]} />
          <Bar dataKey="BGB" fill={COLORS[4]} />
        </BarChart></ResponsiveContainer>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// GROUP 3: वन अवस्था — Forest Condition Charts
// ══════════════════════════════════════════════════════════════

function ConditionChart({ data }: { data: any }) {
  const byCond = data?.by_condition || [];
  const regen = data?.regeneration || [];
  if (!byCond.length && !regen.length) return <EmptyState />;
  const pieData = byCond.map((c: any) => ({ name: c.condition, value: c.area_ha, fill: CONDITION_COLORS[c.condition] || '#78909c' }));
  const regenData = regen.map((r: any) => ({ name: r.block, Seedling: r.seedling_nha, Sapling: r.sapling_nha }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">वन स्थिति — Forest Condition</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <div className="h-48">
          <h4 className="text-xs font-semibold text-center">Condition by Area</h4>
          <ResponsiveContainer><PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={60}
              label={({ name, value }) => `${name} (${value} ha)`}>
              {pieData.map((_: any, i: number) => (<Cell key={i} fill={pieData[i].fill} />))}
            </Pie>
            <Tooltip />
          </PieChart></ResponsiveContainer>
        </div>
        <div className="h-48">
          <h4 className="text-xs font-semibold text-center">Regeneration by Block</h4>
          <ResponsiveContainer><BarChart data={regenData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" /><Tooltip /><Legend />
            <Bar dataKey="Seedling" fill={COLORS[0]} />
            <Bar dataKey="Sapling" fill={COLORS[2]} />
          </BarChart></ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function ProductivityChart({ data }: { data: any }) {
  const classes = data?.classes || [];
  if (!classes.length) return <EmptyState />;
  const chartData = classes.map((c: any) => ({
    name: c.class, Area: c.area_ha,
    fill: c.class === 'High' ? COLORS[0] : c.class === 'Medium' ? COLORS[6] : COLORS[7],
  }));
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">उत्पादकता — Productivity</h3>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <div className="h-40">
          <ResponsiveContainer><BarChart data={chartData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" label={{ value: 'Area (ha)', position: 'bottom' }} />
            <YAxis type="category" dataKey="name" width={60} />
            <Tooltip />
            <Bar dataKey="Area" fill={COLORS[0]}>
              {chartData.map((_: any, i: number) => (<Cell key={i} fill={chartData[i].fill} />))}
            </Bar>
          </BarChart></ResponsiveContainer>
        </div>
        <div className="overflow-auto max-h-40">
          <table className="w-full text-xs border-collapse">
            <thead><tr className="bg-green-700 text-white">
              <th className="p-1 text-left">Class</th><th className="p-1 text-right">Area</th><th className="p-1 text-left">Recommendation</th>
            </tr></thead>
            <tbody>
              {classes.map((c: any, i: number) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                  <td className="p-1 font-medium">{c.class}</td><td className="p-1 text-right">{c.area_ha}</td>
                  <td className="p-1 text-xs">{c.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// GROUP 5: हानि/लाभ — Loss/Gain & Health Charts
// ══════════════════════════════════════════════════════════════

function LossGainChart({ data }: { data: any }) {
  const lossHa = data?.forest_loss_hectares;
  const gainHa = data?.forest_gain_hectares;
  const fireHa = data?.fire_loss_hectares;
  const lossByYear = data?.forest_loss_by_year;
  if (lossHa === undefined && gainHa === undefined && !lossByYear) return <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Loss/Gain data not available</div>;
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">वन हानि/लाभ — Forest Loss & Gain</h3>
      {(lossHa !== undefined || gainHa !== undefined) && (
        <div className="h-32">
          <ResponsiveContainer><BarChart data={[
            { name: 'Loss', ha: lossHa || 0 }, { name: 'Gain', ha: gainHa || 0 },
            ...(fireHa !== undefined ? [{ name: 'Fire Loss', ha: fireHa || 0 }] : []),
          ]}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis label={{ value: 'ha', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Bar dataKey="ha" fill={COLORS[0]}>
              {[lossHa || 0, gainHa || 0, fireHa || 0].map((v, i) => (
                <Cell key={i} fill={i === 1 ? '#2e7d32' : '#c62828'} />
              ))}
            </Bar>
          </BarChart></ResponsiveContainer>
        </div>
      )}
      {lossByYear && Object.keys(lossByYear).length > 0 && (
        <div className="h-40 mt-2">
          <h4 className="text-xs font-semibold text-center mb-1">Loss by Year</h4>
          <ResponsiveContainer><BarChart data={Object.entries(lossByYear).map(([y, h]) => ({ year: y, ha: h }))}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="ha" fill="#c62828" />
          </BarChart></ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// GROUP 6: भू-बनोट — Terrain & Soil Charts
// ══════════════════════════════════════════════════════════════

function SoilChart({ data }: { data: any }) {
  if (!data || (!data.soil_texture && !data.fertility_class && !data.carbon_stock_t_ha)) return <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Soil data not available</div>;
  return (
    <div>
      <h3 className="text-sm font-semibold text-center mb-2">माटो विश्लेषण — Soil Analysis</h3>
      <div className="space-y-2">
        {data.soil_texture && (
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
            <span className="text-xs font-medium">Texture:</span>
            <span className="text-xs">{data.soil_texture.replace(/_/g, ' ')}</span>
          </div>
        )}
        {data.fertility_class && (
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
            <span className="text-xs font-medium">Fertility:</span>
            <span className={`text-xs font-semibold ${data.fertility_class === 'Low' || data.fertility_class === 'Very Low' ? 'text-red-600' : 'text-green-700'}`}>
              {data.fertility_class} {data.fertility_score !== undefined ? `(${data.fertility_score}/100)` : ''}
            </span>
          </div>
        )}
        {data.carbon_stock_t_ha !== undefined && (
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
            <span className="text-xs font-medium">Soil Organic Carbon:</span>
            <span className="text-xs">{data.carbon_stock_t_ha} t/ha</span>
          </div>
        )}
        {data.compaction_status && (
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
            <span className="text-xs font-medium">Compaction:</span>
            <span className="text-xs">{data.compaction_status.replace(/_/g, ' ')}</span>
          </div>
        )}
        {data.soil_properties?.ph_h2o !== undefined && (
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded">
            <span className="text-xs font-medium">pH:</span>
            <span className="text-xs">{data.soil_properties.ph_h2o}</span>
          </div>
        )}
      </div>
    </div>
  );
}
