export type Analysis = {
  analysis_id: string | null;
  source_sha256: string | null;
  impeller: ImpellerFeatures | null;
  filename: string;
  format: "STL" | "STEP";
  method: string;
  unit: "mm";
  unit_source: string;
  dimensions_mm: number[];
  bounds_mm: number[][];
  surface_area_mm2: number;
  volume_mm3: number | null;
  center_of_mass_mm: number[] | null;
  topology: Record<string, number>;
  surface_types: Record<string, number>;
  checks: Record<string, boolean | number | string>;
  warnings: string[];
  classification: string;
  preview: {
    positions: number[];
    indices: number[];
    triangle_count: number;
    note: string;
  } | null;
};

export function formatNumber(value: number | null) {
  return value === null ? "不可用" : new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value);
}

export type ImpellerFeatures = {
  status: "candidate" | "unresolved";
  axis: string;
  method: string;
  blade_count: number | null;
  outer_diameter_mm: number | null;
  axial_height_mm: number | null;
  sampled_material_arc_min_mm: number | null;
  sampled_gap_arc_min_mm: number | null;
  evidence_ratio: number;
  reasons: string[];
  limitations: string[];
  rings: {count: number; height_fraction: number; radius_mm: number; pitch_cv: number; occupancy: number; material_arc_mm: number | null; gap_arc_mm: number | null}[];
};

export type CuttingParameters = {
  rpm: number; feed_mm_min: number; ap_mm: number; ae_mm: number;
  achieved_vc_m_min: number; requested_vc_m_min: number; rpm_limited: boolean;
  basis: string; note: string;
};

export type ProcessPlan = {
  schema_version: string; rule_version: string; status: "blocked" | "review_required";
  title: string; executable_nc: false;
  tools: {id: string; kind: string; diameter_mm: number; flutes: number; assumed_flute_length_mm: number; source: string}[];
  steps: {order: number; operation: string; strategy: string; tool_id: string | null; parameters: CuttingParameters | null; status: string}[];
  constraints: {tool_diameter_cap_mm: number; basis: string};
  estimate: {ideal_roughing_minutes: number | null; ideal_roughing_cost: number | null; removed_volume_mm3: number; basis: string};
  warnings: string[]; blockers: string[]; required_review: string[]; disclaimer: string;
};
