import React, { useState, useEffect } from 'react';
import api from '../services/api';

interface BiodiversitySpecies {
  id: string;
  category: string;
  sub_category: string | null;
  nepali_name: string;
  english_name: string;
  scientific_name: string;
  primary_use: string | null;
  secondary_uses: string | null;
  iucn_status: string | null;
  cites_appendix: string | null;
  distribution: string | null;
  notes: string | null;
  is_invasive: boolean;
  is_protected: boolean;
}

interface SelectedSpecies {
  id: string;
  species_id: string;
  calculation_id: string;
  presence_status: string;
  recorded_at: string;
  species: BiodiversitySpecies;
}

interface BiodiversityTabProps {
  calculationId: string;
}

const BiodiversityTab: React.FC<BiodiversityTabProps> = ({ calculationId }) => {
  const [activeCategory, setActiveCategory] = useState<'vegetation' | 'animal'>('vegetation');
  const [availableSpecies, setAvailableSpecies] = useState<BiodiversitySpecies[]>([]);
  const [selectedSpecies, setSelectedSpecies] = useState<SelectedSpecies[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSubCategory, setFilterSubCategory] = useState<string>('');
  const [filterIUCN, setFilterIUCN] = useState<string>('');
  const [filterInvasive, setFilterInvasive] = useState<boolean | null>(null);
  const [categories, setCategories] = useState<any>({});
  const [saving, setSaving] = useState(false);

  // Load categories
  useEffect(() => {
    loadCategories();
  }, []);

  // Load available species when filters change
  useEffect(() => {
    loadAvailableSpecies();
  }, [activeCategory, filterSubCategory, searchTerm, filterIUCN, filterInvasive]);

  // Load selected species
  useEffect(() => {
    loadSelectedSpecies();
  }, [calculationId]);

  const loadCategories = async () => {
    try {
      const response = await api.get('/api/biodiversity/categories');
      setCategories(response.data);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const loadAvailableSpecies = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('category', activeCategory);
      params.append('page_size', '500');

      if (filterSubCategory) params.append('sub_category', filterSubCategory);
      if (searchTerm) params.append('search', searchTerm);
      if (filterIUCN) params.append('iucn_status', filterIUCN);
      if (filterInvasive !== null) params.append('is_invasive', filterInvasive.toString());

      const response = await api.get(`/api/biodiversity/species?${params.toString()}`);
      setAvailableSpecies(response.data.items);
    } catch (error) {
      console.error('Error loading species:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSelectedSpecies = async () => {
    try {
      const response = await api.get(`/api/biodiversity/calculations/${calculationId}/species`);
      setSelectedSpecies(response.data.species);
    } catch (error) {
      console.error('Error loading selected species:', error);
    }
  };

  const handleAddSpecies = async (speciesId: string) => {
    setSaving(true);
    try {
      await api.post(`/api/biodiversity/calculations/${calculationId}/species/bulk`, {
        species_ids: [speciesId],
        presence_status: 'present'
      });
      await loadSelectedSpecies();
    } catch (error: any) {
      console.error('Error adding species:', error);
      if (error.response?.status === 400) {
        alert('Species already added');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveSpecies = async (speciesId: string) => {
    if (!confirm('Remove this species from inventory?')) return;

    setSaving(true);
    try {
      await api.delete(`/api/biodiversity/calculations/${calculationId}/species/${speciesId}`);
      await loadSelectedSpecies();
    } catch (error) {
      console.error('Error removing species:', error);
    } finally {
      setSaving(false);
    }
  };

  const getIUCNBadgeColor = (status: string | null) => {
    if (!status) return 'bg-gray-100 text-gray-600';
    switch (status) {
      case 'CR': return 'bg-red-600 text-white';
      case 'EN': return 'bg-orange-500 text-white';
      case 'VU': return 'bg-yellow-500 text-white';
      case 'NT': return 'bg-yellow-300 text-gray-800';
      case 'LC': return 'bg-green-100 text-green-700';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  const isSpeciesSelected = (speciesId: string) => {
    return selectedSpecies.some(s => s.species.id === speciesId);
  };

  const selectedInCategory = selectedSpecies.filter(s => s.species.category === activeCategory);
  const subCategories = categories[activeCategory]?.sub_categories || {};

  return (
    <div className="space-y-4">
      {/* Category Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex space-x-4">
          <button
            onClick={() => setActiveCategory('vegetation')}
            className={`px-6 py-3 border-b-2 font-medium text-sm ${
              activeCategory === 'vegetation'
                ? 'border-green-500 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            🌳 Vegetation ({selectedSpecies.filter(s => s.species.category === 'vegetation').length})
          </button>
          <button
            onClick={() => setActiveCategory('animal')}
            className={`px-6 py-3 border-b-2 font-medium text-sm ${
              activeCategory === 'animal'
                ? 'border-green-500 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            🦌 Animals ({selectedSpecies.filter(s => s.species.category === 'animal').length})
          </button>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-2 gap-4">
        {/* Left Panel: Available Species */}
        <div className="border rounded-lg p-4 bg-white">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-semibold text-lg">Available Species</h3>
            <span className="text-sm text-gray-500">{availableSpecies.length} species</span>
          </div>

          {/* Search */}
          <div className="mb-4">
            <input
              type="text"
              placeholder="Search species..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-green-500"
            />
          </div>

          {/* Filters */}
          <div className="space-y-2 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Sub-category</label>
              <select
                value={filterSubCategory}
                onChange={(e) => setFilterSubCategory(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-green-500"
              >
                <option value="">All</option>
                {Object.keys(subCategories).map(subCat => (
                  <option key={subCat} value={subCat}>
                    {subCat} ({subCategories[subCat]})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IUCN Status</label>
              <select
                value={filterIUCN}
                onChange={(e) => setFilterIUCN(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-green-500"
              >
                <option value="">All</option>
                <option value="CR">Critically Endangered</option>
                <option value="EN">Endangered</option>
                <option value="VU">Vulnerable</option>
                <option value="NT">Near Threatened</option>
                <option value="LC">Least Concern</option>
              </select>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                checked={filterInvasive === true}
                onChange={(e) => setFilterInvasive(e.target.checked ? true : null)}
                className="mr-2"
              />
              <label className="text-sm text-gray-700">Show invasive species only</label>
            </div>
          </div>

          {/* Species List */}
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading species...</div>
            ) : availableSpecies.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No species found</div>
            ) : (
              availableSpecies.map(species => (
                <div
                  key={species.id}
                  className={`border rounded-lg p-3 ${
                    isSpeciesSelected(species.id)
                      ? 'bg-green-50 border-green-300'
                      : 'hover:bg-gray-50 cursor-pointer'
                  }`}
                  onClick={() => !isSpeciesSelected(species.id) && handleAddSpecies(species.id)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900">{species.nepali_name}</div>
                      <div className="text-sm text-gray-600">{species.english_name}</div>
                      <div className="text-xs italic text-gray-500">{species.scientific_name}</div>
                    </div>
                    {isSpeciesSelected(species.id) && (
                      <span className="text-green-600 text-sm">✓ Selected</span>
                    )}
                  </div>

                  <div className="flex gap-2 mt-2 flex-wrap">
                    {species.iucn_status && (
                      <span className={`text-xs px-2 py-1 rounded ${getIUCNBadgeColor(species.iucn_status)}`}>
                        {species.iucn_status}
                      </span>
                    )}
                    {species.is_invasive && (
                      <span className="text-xs px-2 py-1 rounded bg-red-100 text-red-700">
                        ⚠️ Invasive
                      </span>
                    )}
                    {species.cites_appendix && species.cites_appendix !== 'Not listed' && (
                      <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">
                        CITES
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Panel: Selected Species */}
        <div className="border rounded-lg p-4 bg-white">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-semibold text-lg">Selected Species</h3>
            <span className="text-sm text-gray-500">{selectedInCategory.length} selected</span>
          </div>

          {selectedInCategory.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No species selected yet. Click on species from the left panel to add them.
            </div>
          ) : (
            <div className="space-y-2 max-h-[700px] overflow-y-auto">
              {selectedInCategory.map(item => (
                <div key={item.id} className="border rounded-lg p-3 bg-gray-50">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900">{item.species.nepali_name}</div>
                      <div className="text-sm text-gray-600">{item.species.english_name}</div>
                      <div className="text-xs italic text-gray-500">{item.species.scientific_name}</div>
                    </div>
                    <button
                      onClick={() => handleRemoveSpecies(item.species.id)}
                      disabled={saving}
                      className="text-red-600 hover:text-red-800 text-sm"
                    >
                      Remove
                    </button>
                  </div>

                  <div className="flex gap-2 mt-2 flex-wrap">
                    {item.species.iucn_status && (
                      <span className={`text-xs px-2 py-1 rounded ${getIUCNBadgeColor(item.species.iucn_status)}`}>
                        {item.species.iucn_status}
                      </span>
                    )}
                    {item.species.is_invasive && (
                      <span className="text-xs px-2 py-1 rounded bg-red-100 text-red-700">
                        ⚠️ Invasive
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold mb-2">Biodiversity Summary</h4>
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-600">Total Species</div>
            <div className="text-2xl font-bold text-blue-600">{selectedSpecies.length}</div>
          </div>
          <div>
            <div className="text-gray-600">Vegetation</div>
            <div className="text-2xl font-bold text-green-600">
              {selectedSpecies.filter(s => s.species.category === 'vegetation').length}
            </div>
          </div>
          <div>
            <div className="text-gray-600">Animals</div>
            <div className="text-2xl font-bold text-orange-600">
              {selectedSpecies.filter(s => s.species.category === 'animal').length}
            </div>
          </div>
          <div>
            <div className="text-gray-600">Protected</div>
            <div className="text-2xl font-bold text-red-600">
              {selectedSpecies.filter(s =>
                s.species.is_protected ||
                ['CR', 'EN', 'VU'].includes(s.species.iucn_status || '')
              ).length}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BiodiversityTab;
