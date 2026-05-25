import { useState, useCallback } from 'react';
import { operationalPlanApi } from '../../../services/api';

export interface LocationState {
  province: string | undefined;
  division: string | undefined;
  subDivision: string | undefined;
  municipality: string | undefined;
  ward: string | undefined;
}

export interface AdminLocationOptions {
  provinces: string[];
  divisions: string[];
  subDivisions: string[];
  municipalities: { name: string; type: string }[];
  wards: string[];
  physiographyZone: string;
  protectedAreaStatus: string;
}

export function useAdminLocation() {
  const [options, setOptions] = useState<AdminLocationOptions>({
    provinces: [],
    divisions: [],
    subDivisions: [],
    municipalities: [],
    wards: [],
    physiographyZone: '',
    protectedAreaStatus: '',
  });
  const [loading, setLoading] = useState(false);

  const loadProvinces = useCallback(async () => {
    try {
      const provinces = await operationalPlanApi.getProvinces();
      setOptions(prev => ({ ...prev, provinces }));
    } catch { /* ignore */ }
  }, []);

  const loadDivisions = useCallback(async (province?: string) => {
    if (!province) { setOptions(prev => ({ ...prev, divisions: [], subDivisions: [], municipalities: [], wards: [] })); return; }
    try {
      const divisions = await operationalPlanApi.getDivisions(province);
      setOptions(prev => ({ ...prev, divisions, subDivisions: [], municipalities: [], wards: [] }));
    } catch { /* ignore */ }
  }, []);

  const loadSubDivisions = useCallback(async (province?: string, division?: string) => {
    if (!province || !division) { setOptions(prev => ({ ...prev, subDivisions: [], municipalities: [], wards: [] })); return; }
    try {
      const subDivisions = await operationalPlanApi.getSubDivisions(province, division);
      setOptions(prev => ({ ...prev, subDivisions, municipalities: [], wards: [] }));
    } catch { /* ignore */ }
  }, []);

  const loadMunicipalities = useCallback(async (province?: string, division?: string, subDivision?: string) => {
    if (!province || !division || !subDivision) { setOptions(prev => ({ ...prev, municipalities: [], wards: [] })); return; }
    try {
      const municipalities = await operationalPlanApi.getMunicipalities(province, division, subDivision);
      setOptions(prev => ({ ...prev, municipalities, wards: [] }));
    } catch { /* ignore */ }
  }, []);

  const loadWards = useCallback(async (province?: string, division?: string, subDivision?: string, municipality?: string) => {
    if (!province || !division || !subDivision || !municipality) { setOptions(prev => ({ ...prev, wards: [] })); return; }
    try {
      const wards = await operationalPlanApi.getWards(province, division, subDivision, municipality);
      setOptions(prev => ({ ...prev, wards }));
    } catch { /* ignore */ }
  }, []);

  const loadPhysiography = useCallback(async (province?: string, division?: string, subDivision?: string, municipality?: string) => {
    if (!province || !division || !subDivision || !municipality) return;
    try {
      const result = await operationalPlanApi.getPhysiographyJurisdiction(province, division, subDivision, municipality);
      setOptions(prev => ({ ...prev, physiographyZone: result.physiography_zone, protectedAreaStatus: result.protected_area_status }));
    } catch { /* ignore */ }
  }, []);

  const cascadeOnProvinceChange = useCallback(async (province: string | undefined) => {
    setLoading(true);
    setOptions(prev => ({ ...prev, province: province, divisions: [], subDivisions: [], municipalities: [], wards: [], physiographyZone: '', protectedAreaStatus: '' }));
    if (province) await loadDivisions(province);
    setLoading(false);
  }, [loadDivisions]);

  const cascadeOnDivisionChange = useCallback(async (province: string | undefined, division: string | undefined) => {
    setLoading(true);
    setOptions(prev => ({ ...prev, division, subDivisions: [], municipalities: [], wards: [], physiographyZone: '', protectedAreaStatus: '' }));
    if (province && division) await loadSubDivisions(province, division);
    setLoading(false);
  }, [loadSubDivisions]);

  const cascadeOnSubDivisionChange = useCallback(async (province: string | undefined, division: string | undefined, subDivision: string | undefined) => {
    setLoading(true);
    setOptions(prev => ({ ...prev, subDivision, municipalities: [], wards: [], physiographyZone: '', protectedAreaStatus: '' }));
    if (province && division && subDivision) {
      await loadMunicipalities(province, division, subDivision);
    }
    setLoading(false);
  }, [loadMunicipalities]);

  const cascadeOnMunicipalityChange = useCallback(async (province: string | undefined, division: string | undefined, subDivision: string | undefined, municipality: string | undefined, fetchPhysiography: boolean = true) => {
    setLoading(true);
    setOptions(prev => ({ ...prev, municipality, wards: [] }));
    if (province && division && subDivision && municipality) {
      await loadWards(province, division, subDivision, municipality);
      if (fetchPhysiography) {
        await loadPhysiography(province, division, subDivision, municipality);
      }
    }
    setLoading(false);
  }, [loadWards, loadPhysiography]);

  const cascadeOnWardChange = useCallback((ward: string | undefined) => {
    setOptions(prev => ({ ...prev, ward }));
  }, []);

  return {
    options,
    loading,
    loadProvinces,
    cascadeOnProvinceChange,
    cascadeOnDivisionChange,
    cascadeOnSubDivisionChange,
    cascadeOnMunicipalityChange,
    cascadeOnWardChange,
    setOptions,
  };
}
