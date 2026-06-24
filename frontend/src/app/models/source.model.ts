export type SourceType = 'telegram' | 'x' | 'rss' | 'gov';

export interface Source {
  id: number;
  name: string;
  source_type: SourceType;
  source_type_display: string;
  identifier: string;
  is_active: boolean;
  last_synced_at: string | null;
  created_at: string;
}

export interface SourceInput {
  name: string;
  source_type: SourceType;
  identifier: string;
  is_active: boolean;
}
