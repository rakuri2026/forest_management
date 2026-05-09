import React, { useState, useMemo } from 'react';
import api from '../services/api';

interface Species {
  scientific_name: string;
  local_name: string;
  role: string;
  availability_rank: number;
  economic_value: string;
  confirmed?: boolean;  // Grey (false/undefined) vs Colorful (true)
  manually_added?: boolean;
  growth_rate?: string;
  min_altitude_m?: number;
  max_altitude_m?: number;
  main_uses?: string;
  nitrogen_fixing?: boolean;
  rarity_status?: string;
  family?: string;
  forest_types?: string[];
}

interface SpeciesTableProps {
  species: Species[];
  calculationId: string;
  removedSpecies?: string[];
  onSpeciesToggle?: (speciesName: string, enabled: boolean) => void;
  onAddSpecies?: () => void;
  onSpeciesRemoved?: () => void;
  onSpeciesConfirmed?: () => void;  // Refresh after confirmation changes
  onExport?: (format: 'csv' | 'excel') => void;
  // External state sharing (for syncing with block species)
  optimisticConfirmations?: Map<string, boolean>;
  confirmingSpecies?: Set<string>;
  getConfirmedStatus?: (species: Species) => boolean;
  handleToggleSpeciesConfirmation?: (species: Species) => Promise<void>;
}

const SpeciesTable: React.FC<SpeciesTableProps> = ({
  species,
  calculationId,
  removedSpecies = [],
  onSpeciesToggle,
  onAddSpecies,
  onSpeciesRemoved,
  onSpeciesConfirmed,
  onExport,
  optimisticConfirmations: externalOptimisticConfirmations,
  confirmingSpecies: externalConfirmingSpecies,
  getConfirmedStatus: externalGetConfirmedStatus,
  handleToggleSpeciesConfirmation: externalHandleToggle
}) => {
  const [expanded, setExpanded] = useState(false);
  const [enabledSpecies, setEnabledSpecies] = useState<Set<string>>(
    new Set(species.map(s => s.scientific_name))
  );
  const [sortBy, setSortBy] = useState<string>('role');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [filterRole, setFilterRole] = useState<string>('all');
  const [filterValue, setFilterValue] = useState<string>('all');
  const [showNFixersOnly, setShowNFixersOnly] = useState(false);
  const [showFilter, setShowFilter] = useState<'all' | 'confirmed' | 'unconfirmed'>('all');
  const [internalConfirmingSpecies, setInternalConfirmingSpecies] = useState<Set<string>>(new Set());
  const [showAllAssociates, setShowAllAssociates] = useState(false);
  const [internalOptimisticConfirmations, setInternalOptimisticConfirmations] = useState<Map<string, boolean>>(new Map());

  // Use external state if provided, otherwise use internal state
  const optimisticConfirmations = externalOptimisticConfirmations || internalOptimisticConfirmations;
  const confirmingSpecies = externalConfirmingSpecies || internalConfirmingSpecies;

  // Helper function to get actual confirmed status (combining prop + optimistic updates)
  const getConfirmedStatus = externalGetConfirmedStatus || ((species: Species): boolean => {
    const scientificName = species.scientific_name;
    if (optimisticConfirmations.has(scientificName)) {
      return optimisticConfirmations.get(scientificName)!;
    }
    return species.confirmed ?? false;
  });

  // Group species by role (excluding removed species from backend)
  const speciesByRole = useMemo(() => {
    const groups: { [key: string]: Species[] } = {
      'Dominant': [],
      'Co-dominant': [],
      'Associate': [],
      'Occasional': [],
      'Rare': []
    };

    species.forEach(s => {
      // Skip removed species (from backend)
      if (removedSpecies.includes(s.scientific_name)) {
        return;
      }

      // Apply confirmation filter
      const isConfirmed = s.confirmed ?? false;
      if (showFilter === 'confirmed' && !isConfirmed) return;
      if (showFilter === 'unconfirmed' && isConfirmed) return;

      const role = s.role || 'Associate';
      if (groups[role]) {
        groups[role].push(s);
      } else {
        groups['Associate'].push(s);
      }
    });

    return groups;
  }, [species, removedSpecies, showFilter]);

  // Get role badge color
  const getRoleBadge = (role: string) => {
    const colors: { [key: string]: string } = {
      'Dominant': 'bg-green-100 text-green-800 font-bold',
      'Co-dominant': 'bg-blue-100 text-blue-800 font-bold',
      'Associate': 'bg-gray-100 text-gray-700',
      'Occasional': 'bg-yellow-50 text-yellow-700',
      'Rare': 'bg-orange-100 text-orange-700'
    };
    return colors[role] || colors['Associate'];
  };

  // Get economic value badge color
  const getValueBadge = (value: string) => {
    const colors: { [key: string]: string } = {
      'Very High': 'bg-green-200 text-green-900',
      'High': 'bg-green-100 text-green-800',
      'Moderate': 'bg-yellow-100 text-yellow-800',
      'Medium': 'bg-yellow-100 text-yellow-800',
      'Low': 'bg-gray-100 text-gray-600'
    };
    return colors[value] || colors['Medium'];
  };

  // Toggle species checkbox
  const handleToggle = (scientificName: string) => {
    const newEnabled = new Set(enabledSpecies);
    if (newEnabled.has(scientificName)) {
      newEnabled.delete(scientificName);
    } else {
      newEnabled.add(scientificName);
    }
    setEnabledSpecies(newEnabled);

    if (onSpeciesToggle) {
      onSpeciesToggle(scientificName, newEnabled.has(scientificName));
    }
  };

  // Handle species confirmation (grey -> colorful) with optimistic updates
  const handleToggleConfirmation = async (scientificName: string, currentConfirmed: boolean) => {
    // Find the species object
    const speciesObj = species.find(s => s.scientific_name === scientificName);
    if (!speciesObj) return;

    // If external handler is provided, use it (for shared state with blocks)
    if (externalHandleToggle) {
      await externalHandleToggle(speciesObj);
      return;
    }

    // Otherwise use internal state management
    const newConfirmed = !currentConfirmed;

    // Optimistic update - change UI immediately
    setInternalOptimisticConfirmations(prev => {
      const newMap = new Map(prev);
      newMap.set(scientificName, newConfirmed);
      return newMap;
    });

    setInternalConfirmingSpecies(prev => new Set(prev).add(scientificName));

    try {
      await api.patch(
        `/api/forests/calculations/${calculationId}/species/${encodeURIComponent(scientificName)}/confirm`,
        { confirmed: newConfirmed }
      );

      // Success - optimistic update is correct, no need to refresh page
      // Data is already saved in backend
    } catch (err: any) {
      console.error('Error confirming species:', err);
      alert('Failed to update species: ' + (err.response?.data?.detail || err.message));

      // Revert optimistic update on error
      setInternalOptimisticConfirmations(prev => {
        const newMap = new Map(prev);
        newMap.delete(scientificName);
        return newMap;
      });
    } finally {
      setInternalConfirmingSpecies(prev => {
        const newSet = new Set(prev);
        newSet.delete(scientificName);
        return newSet;
      });
    }
  };

  const handleConfirmAll = async () => {
    if (!window.confirm('Confirm all species as present in the forest?')) return;

    try {
      await api.post(`/api/forests/calculations/${calculationId}/species/confirm-all`, {
        confirmed: true
      });

      if (onSpeciesConfirmed) {
        onSpeciesConfirmed();
      }
    } catch (err: any) {
      console.error('Error confirming all:', err);
      alert('Failed to confirm all species: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('Clear all confirmations? Species will return to grey/unconfirmed state.')) return;

    try {
      await api.post(`/api/forests/calculations/${calculationId}/species/confirm-all`, {
        confirmed: false
      });

      if (onSpeciesConfirmed) {
        onSpeciesConfirmed();
      }
    } catch (err: any) {
      console.error('Error clearing confirmations:', err);
      alert('Failed to clear confirmations: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Remove (hide) species from display - saves to backend
  const handleRemoveSpecies = async (scientificName: string, localName: string) => {
    if (!window.confirm(`Remove "${localName}" (${scientificName}) from species list?\n\nThis will be saved and the species will not appear in reports.`)) {
      return;
    }

    try {
      await api.delete(`/api/forests/calculations/${calculationId}/remove-species/${encodeURIComponent(scientificName)}`);

      // Notify parent to refresh calculation data
      if (onSpeciesRemoved) {
        onSpeciesRemoved();
      }
    } catch (err: any) {
      console.error('Error removing species:', err);
      alert('Failed to remove species: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Filter and sort species
  const filteredAndSortedSpecies = useMemo(() => {
    let filtered = species.filter(s => !removedSpecies.includes(s.scientific_name));

    // Apply role filter
    if (filterRole !== 'all') {
      filtered = filtered.filter(s => s.role === filterRole);
    }

    // Apply economic value filter
    if (filterValue !== 'all') {
      filtered = filtered.filter(s => s.economic_value === filterValue);
    }

    // Apply nitrogen-fixer filter
    if (showNFixersOnly) {
      filtered = filtered.filter(s => s.nitrogen_fixing === true);
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal, bVal;

      switch (sortBy) {
        case 'role':
          const roleOrder = ['Dominant', 'Co-dominant', 'Associate', 'Occasional', 'Rare'];
          aVal = roleOrder.indexOf(a.role || 'Associate');
          bVal = roleOrder.indexOf(b.role || 'Associate');
          break;
        case 'local_name':
          aVal = a.local_name || '';
          bVal = b.local_name || '';
          break;
        case 'economic_value':
          const valueOrder = ['Very High', 'High', 'Moderate', 'Medium', 'Low'];
          aVal = valueOrder.indexOf(a.economic_value || 'Medium');
          bVal = valueOrder.indexOf(b.economic_value || 'Medium');
          break;
        case 'altitude':
          aVal = a.min_altitude_m || 0;
          bVal = b.min_altitude_m || 0;
          break;
        default:
          return 0;
      }

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [species, sortBy, sortOrder, filterRole, filterValue, showNFixersOnly, removedSpecies]);

  // Format altitude range
  const formatAltitude = (min?: number, max?: number) => {
    if (!min && !max) return 'N/A';
    if (!max) return `${min}m+`;
    if (!min) return `up to ${max}m`;
    return `${min}-${max}m`;
  };

  // Truncate text
  const truncate = (text: string, maxLength: number) => {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  // Export to CSV
  const handleExportCSV = () => {
    const csvContent = [
      // Header
      ['Local Name', 'Scientific Name', 'Role', 'Economic Value', 'Altitude Range', 'Growth Rate', 'Main Uses', 'N-Fixing', 'Family', 'Rarity Status'].join(','),
      // Data rows
      ...species.map(s => [
        s.local_name,
        s.scientific_name,
        s.role,
        s.economic_value,
        formatAltitude(s.min_altitude_m, s.max_altitude_m),
        s.growth_rate || '',
        (s.main_uses || '').replace(/,/g, ';'),
        s.nitrogen_fixing ? 'Yes' : 'No',
        s.family || '',
        s.rarity_status || ''
      ].map(v => `"${v}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `species_list_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  return (
    <div className="space-y-4">
      {/* Card View - Top species */}
      <div>
        <h4 className="text-md font-semibold text-gray-900 mb-3">
          Potential Tree Species ({species.length} species)
        </h4>

        {/* Instruction Banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-900 mb-1">
                Species Confirmation Workflow
              </p>
              <p className="text-sm text-blue-700">
                <span className="font-semibold">Grey species</span> = Not yet confirmed (system-generated, needs field verification)<br />
                <span className="font-semibold">Colorful species</span> = Confirmed present in forest (ready for operational plan)<br />
                Click any species card to toggle confirmation status.
              </p>
            </div>
            <div className="ml-4 text-sm text-blue-900 font-semibold bg-blue-100 rounded px-3 py-2">
              {species.filter(s => !removedSpecies.includes(s.scientific_name) && getConfirmedStatus(s)).length} / {species.filter(s => !removedSpecies.includes(s.scientific_name)).length} confirmed
            </div>
          </div>
        </div>

        {/* Control Buttons */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          {/* Filter Buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowFilter('all')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                showFilter === 'all'
                  ? 'bg-gray-700 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Show All
            </button>
            <button
              onClick={() => setShowFilter('confirmed')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                showFilter === 'confirmed'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Confirmed Only
            </button>
            <button
              onClick={() => setShowFilter('unconfirmed')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                showFilter === 'unconfirmed'
                  ? 'bg-orange-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Unconfirmed Only
            </button>
          </div>

          {/* Bulk Action Buttons */}
          <div className="flex gap-2 ml-auto">
            <button
              onClick={handleConfirmAll}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded text-sm font-medium transition-colors"
            >
              Confirm All
            </button>
            <button
              onClick={handleClearAll}
              className="px-3 py-1.5 bg-gray-500 hover:bg-gray-600 text-white rounded text-sm font-medium transition-colors"
            >
              Clear All
            </button>
          </div>
        </div>

        {/* Dominant Species */}
        {speciesByRole['Dominant'].length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Dominant Species ({speciesByRole['Dominant'].length}):</p>
            <div className="flex flex-wrap gap-2">
              {speciesByRole['Dominant'].map((species, idx) => {
                const isConfirmed = getConfirmedStatus(species);
                const isConfirming = confirmingSpecies.has(species.scientific_name);
                return (
                  <div
                    key={idx}
                    onClick={(e) => {
                      // Don't trigger if clicking the X button
                      if ((e.target as HTMLElement).closest('button')) return;
                      handleToggleConfirmation(species.scientific_name, isConfirmed);
                    }}
                    className={`relative inline-flex items-center rounded-md px-3 py-2 pr-8 text-sm cursor-pointer transition-all ${
                      isConfirmed
                        ? 'bg-green-50 border-2 border-green-400 opacity-100 hover:bg-green-100'
                        : 'bg-gray-100 border-2 border-gray-300 border-dashed opacity-60 hover:opacity-80 hover:border-gray-400'
                    } ${isConfirming ? 'animate-pulse' : ''}`}
                    title={isConfirmed ? 'Click to unconfirm (make grey)' : 'Click to confirm (make colorful)'}
                  >
                    <span className={isConfirmed ? 'font-bold text-green-900' : 'font-semibold text-gray-600'}>
                      {species.local_name}
                    </span>
                    <span className={isConfirmed ? 'text-gray-500 ml-2 italic' : 'text-gray-400 ml-2 italic'}>
                      ({species.scientific_name})
                    </span>
                    {species.economic_value && (
                      <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${isConfirmed ? getValueBadge(species.economic_value) : 'bg-gray-200 text-gray-600'}`}>
                        {species.economic_value === 'Medium' ? 'Med Value' : species.economic_value}
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveSpecies(species.scientific_name, species.local_name);
                      }}
                      className="absolute top-1 right-1 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors z-10"
                      title="Remove species from list (saved)"
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Co-dominant Species */}
        {speciesByRole['Co-dominant'].length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Co-dominant Species ({speciesByRole['Co-dominant'].length}):</p>
            <div className="flex flex-wrap gap-2">
              {speciesByRole['Co-dominant'].map((species, idx) => {
                const isConfirmed = getConfirmedStatus(species);
                const isConfirming = confirmingSpecies.has(species.scientific_name);
                return (
                  <div
                    key={idx}
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest('button')) return;
                      handleToggleConfirmation(species.scientific_name, isConfirmed);
                    }}
                    className={`relative inline-flex items-center rounded-md px-3 py-2 pr-8 text-sm cursor-pointer transition-all ${
                      isConfirmed
                        ? 'bg-blue-50 border-2 border-blue-400 opacity-100 hover:bg-blue-100'
                        : 'bg-gray-100 border-2 border-gray-300 border-dashed opacity-60 hover:opacity-80 hover:border-gray-400'
                    } ${isConfirming ? 'animate-pulse' : ''}`}
                    title={isConfirmed ? 'Click to unconfirm (make grey)' : 'Click to confirm (make colorful)'}
                  >
                    <span className={isConfirmed ? 'font-bold text-blue-900' : 'font-semibold text-gray-600'}>
                      {species.local_name}
                    </span>
                    <span className={isConfirmed ? 'text-gray-500 ml-2 italic' : 'text-gray-400 ml-2 italic'}>
                      ({species.scientific_name})
                    </span>
                    {species.economic_value && (
                      <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${isConfirmed ? getValueBadge(species.economic_value) : 'bg-gray-200 text-gray-600'}`}>
                        {species.economic_value === 'Medium' ? 'Med Value' : species.economic_value}
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveSpecies(species.scientific_name, species.local_name);
                      }}
                      className="absolute top-1 right-1 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors z-10"
                      title="Remove species from list (saved)"
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Associate, Occasional, and Rare Species - expandable */}
        {(speciesByRole['Associate'].length > 0 || speciesByRole['Occasional'].length > 0 || speciesByRole['Rare'].length > 0) && (
          <div className="mb-3">
            <p className="text-sm font-medium text-gray-700 mb-2">
              Associate, Occasional & Rare Species ({speciesByRole['Associate'].length + speciesByRole['Occasional'].length + speciesByRole['Rare'].length} total):
            </p>
            <div className="flex flex-wrap gap-2">
              {/* Combine all Associate, Occasional, and Rare species */}
              {[...speciesByRole['Associate'], ...speciesByRole['Occasional'], ...speciesByRole['Rare']]
                .slice(0, showAllAssociates ? undefined : 8)
                .map((species, idx) => {
                  const isConfirmed = getConfirmedStatus(species);
                  const isConfirming = confirmingSpecies.has(species.scientific_name);
                  return (
                    <div
                      key={idx}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest('button')) return;
                        handleToggleConfirmation(species.scientific_name, isConfirmed);
                      }}
                      className={`relative inline-flex items-center rounded-md px-3 py-2 pr-8 text-sm cursor-pointer transition-all ${
                        isConfirmed
                          ? 'bg-gray-50 border-2 border-gray-400 opacity-100 hover:bg-gray-100'
                          : 'bg-gray-100 border-2 border-gray-300 border-dashed opacity-50 hover:opacity-70 hover:border-gray-400'
                      } ${isConfirming ? 'animate-pulse' : ''}`}
                      title={isConfirmed ? 'Click to unconfirm (make grey)' : 'Click to confirm (make colorful)'}
                    >
                      <span className={isConfirmed ? 'font-semibold text-gray-900' : 'font-medium text-gray-500'}>
                        {species.local_name}
                      </span>
                      <span className={isConfirmed ? 'text-gray-500 ml-2 italic' : 'text-gray-400 ml-2 italic'}>
                        ({species.scientific_name})
                      </span>
                      {species.economic_value && (
                        <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${isConfirmed ? getValueBadge(species.economic_value) : 'bg-gray-200 text-gray-600'}`}>
                          {species.economic_value === 'Medium' ? 'Med Value' : species.economic_value}
                        </span>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveSpecies(species.scientific_name, species.local_name);
                        }}
                        className="absolute top-1 right-1 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors z-10"
                        title="Remove species from list (saved)"
                      >
                        ×
                      </button>
                    </div>
                  );
                })}

              {/* Show More / Show Less button */}
              {(speciesByRole['Associate'].length + speciesByRole['Occasional'].length + speciesByRole['Rare'].length > 8) && (
                <button
                  onClick={() => setShowAllAssociates(!showAllAssociates)}
                  className="inline-flex items-center px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md transition-colors self-center"
                >
                  {showAllAssociates ? (
                    <>
                      <span>Show Less</span>
                      <svg className="ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                      </svg>
                    </>
                  ) : (
                    <>
                      <span>Show {speciesByRole['Associate'].length + speciesByRole['Occasional'].length + speciesByRole['Rare'].length - 8} More Species</span>
                      <svg className="ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Expandable Detailed Table */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full bg-gray-50 hover:bg-gray-100 px-4 py-3 text-left flex items-center justify-between transition-colors"
        >
          <span className="text-sm font-medium text-gray-700">
            {expanded ? '▼' : '▶'} Show All Species with Detailed Characteristics
          </span>
          <span className="text-xs text-gray-500">
            {filteredAndSortedSpecies.length} species
          </span>
        </button>

        {expanded && (
          <div className="bg-white">
            {/* Filters and Actions */}
            <div className="p-4 bg-gray-50 border-b border-gray-200 flex flex-wrap gap-3 items-center justify-between">
              <div className="flex flex-wrap gap-3 items-center">
                <select
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                  className="text-sm border border-gray-300 rounded px-3 py-1.5"
                >
                  <option value="all">All Roles</option>
                  <option value="Dominant">Dominant</option>
                  <option value="Co-dominant">Co-dominant</option>
                  <option value="Associate">Associate</option>
                  <option value="Occasional">Occasional</option>
                  <option value="Rare">Rare</option>
                </select>

                <select
                  value={filterValue}
                  onChange={(e) => setFilterValue(e.target.value)}
                  className="text-sm border border-gray-300 rounded px-3 py-1.5"
                >
                  <option value="all">All Values</option>
                  <option value="Very High">Very High</option>
                  <option value="High">High</option>
                  <option value="Moderate">Moderate</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>

                <label className="flex items-center text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={showNFixersOnly}
                    onChange={(e) => setShowNFixersOnly(e.target.checked)}
                    className="mr-2"
                  />
                  N-fixers only
                </label>
              </div>

              <div className="flex gap-2">
                {onAddSpecies && (
                  <button
                    onClick={onAddSpecies}
                    className="text-sm px-3 py-1.5 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                  >
                    + Add Species
                  </button>
                )}
                <button
                  onClick={handleExportCSV}
                  className="text-sm px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  📥 Export CSV
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-100">
                  <tr>
                    {onSpeciesToggle && (
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        ☑
                      </th>
                    )}
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-200"
                      onClick={() => {
                        if (sortBy === 'local_name') {
                          setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                        } else {
                          setSortBy('local_name');
                          setSortOrder('asc');
                        }
                      }}
                    >
                      Local Name {sortBy === 'local_name' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Scientific Name
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-200"
                      onClick={() => {
                        if (sortBy === 'role') {
                          setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                        } else {
                          setSortBy('role');
                          setSortOrder('asc');
                        }
                      }}
                    >
                      Role {sortBy === 'role' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-200"
                      onClick={() => {
                        if (sortBy === 'economic_value') {
                          setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                        } else {
                          setSortBy('economic_value');
                          setSortOrder('asc');
                        }
                      }}
                    >
                      Value {sortBy === 'economic_value' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-200"
                      onClick={() => {
                        if (sortBy === 'altitude') {
                          setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                        } else {
                          setSortBy('altitude');
                          setSortOrder('asc');
                        }
                      }}
                    >
                      Altitude {sortBy === 'altitude' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Growth
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Main Uses
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      N-Fix
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredAndSortedSpecies.map((species, idx) => (
                    <tr key={idx} className={`hover:bg-gray-50 ${!enabledSpecies.has(species.scientific_name) ? 'opacity-50' : ''}`}>
                      {onSpeciesToggle && (
                        <td className="px-3 py-3 whitespace-nowrap">
                          <input
                            type="checkbox"
                            checked={enabledSpecies.has(species.scientific_name)}
                            onChange={() => handleToggle(species.scientific_name)}
                            className="h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded"
                          />
                        </td>
                      )}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`font-semibold ${species.role === 'Dominant' || species.role === 'Co-dominant' ? 'text-green-900' : 'text-gray-900'}`}>
                          {species.local_name}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm italic text-gray-600">
                        {species.scientific_name}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs rounded ${getRoleBadge(species.role || 'Associate')}`}>
                          {species.role || 'Associate'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs rounded ${getValueBadge(species.economic_value || 'Medium')}`}>
                          {species.economic_value || 'Medium'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {formatAltitude(species.min_altitude_m, species.max_altitude_m)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {species.growth_rate || 'N/A'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 max-w-xs">
                        <span title={species.main_uses || ''}>
                          {truncate(species.main_uses || 'N/A', 50)}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-center">
                        {species.nitrogen_fixing ? (
                          <span className="text-green-600 font-bold" title="Nitrogen-fixing species">🌱</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span className={`${species.rarity_status?.includes('ENDANGERED') || species.rarity_status?.includes('RARE') ? 'text-orange-600 font-semibold' : 'text-gray-600'}`}>
                          {species.rarity_status || 'Common'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredAndSortedSpecies.length === 0 && (
              <div className="p-8 text-center text-gray-500">
                No species match the current filters.
              </div>
            )}

            {/* Note */}
            <div className="p-4 bg-yellow-50 border-t border-yellow-200">
              <p className="text-sm text-yellow-800">
                ⚠️ <strong>Note:</strong> Uncheck species not found in field survey. The forest type classification will be recalculated when species are modified.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SpeciesTable;
