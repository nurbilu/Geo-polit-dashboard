export type Region =
  | 'judea_samaria'
  | 'golan_heights'
  | 'north'
  | 'south'
  | 'central'
  | 'unknown';

export type Country =
  | 'israel'
  | 'lebanon'
  | 'syria'
  | 'jordan'
  | 'egypt'
  | 'iraq'
  | 'arabian_peninsula'
  | 'gulf_states'
  | 'iran'
  | 'turkey'
  | 'mediterranean'
  | 'unknown';

export interface Alert {
  id: number;
  source: number;
  source_name: string;
  source_type: string;
  external_id: string;
  title: string;
  content: string;
  url: string;
  image: string | null;
  image_url: string | null;
  has_image: boolean;
  status: string;
  status_display: string;
  is_threat: boolean | null;
  country: Country;
  country_display: string;
  region: Region;
  region_display: string;
  threat_severity: number | null;
  visual_summary: string;
  summary_hebrew: string;
  analysis: Record<string, unknown>;
  parent_alert: number | null;
  cluster_count: number;
  is_primary: boolean;
  published_at: string;
  analyzed_at: string | null;
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface RegionBucket {
  region: Region;
  count: number;
  avg_severity: number | null;
}

export interface DashboardSummary {
  window_hours: number;
  total_alerts: number;
  threat_alerts: number;
  pending_analysis: number;
  critical_alerts: number;
  by_region: RegionBucket[];
}

export interface AlertFilters {
  region?: Region | '';
  is_threat?: boolean | '';
  min_severity?: number | '';
  has_image?: boolean;
}
