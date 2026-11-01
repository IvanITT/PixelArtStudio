export type AssetKind =
  | "source"
  | "pixelart"
  | "sprite"
  | "spritesheet"
  | "tile"
  | "tileset"
  | "procedural"
  | "false3d"
  | "frame"
  | "animation"
  | "workspace"
  | "export"
  | string;

export interface Asset {
  id: string;
  project_id: string;
  name: string;
  kind: AssetKind;
  filename: string;
  thumb: string | null;
  width: number;
  height: number;
  size_bytes: number;
  sha256: string;
  tags: string[];
  favorite: boolean;
  meta: Record<string, any>;
  created_at: string;
  updated_at: string;
  url: string;
  thumb_url: string | null;
  download_url: string;
  src_url: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  category: string;
  favorite: boolean;
  state: Record<string, any>;
  settings: Record<string, any>;
  created_at: string;
  updated_at: string;
  asset_counts: Record<string, number>;
  asset_count: number;
  animation_count: number;
  thumbnail_url: string | null;
  size_bytes: number;
}

export interface Palette {
  id: string;
  name: string;
  colors: string[];
  builtin: boolean;
  project_id: string | null;
  note: string;
}

export interface Health {
  status: string;
  app: string;
  version: string;
  offline: boolean;
  time: string;
  platform: string;
  python: string;
  versions: Record<string, string>;
  cpu_count: number;
  memory: MemoryInfo;
  data_dir: string;
  frontend_built: boolean;
}

export interface MemoryInfo {
  total_mb: number;
  available_mb: number;
  used_mb: number;
  app_rss_mb: number;
  percent: number;
}

export interface Settings {
  max_upload_mb: number;
  max_image_pixels: number;
  preview_max_dim: number;
  max_output_dim: number;
  worker_threads: number;
  max_tiles: number;
  cache_limit_mb: number;
  autosave_seconds: number;
  accent: string;
  reduce_motion: boolean;
  max_sheet_dim: number;
  [key: string]: any;
}

export interface SystemStats {
  memory: MemoryInfo;
  cpu: { count: number; percent: number };
  data: { data_dir: string; projects: number; total_bytes: number; cache_bytes: number; tmp_bytes: number };
  projects: number;
  assets: number;
  active_jobs: JobRecord[];
  recent_jobs: JobRecord[];
  benchmark: Benchmark | null;
  workers: number;
  frontend_built: boolean;
}

export interface JobRecord {
  id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error" | "cancelled" | string;
  progress: number;
  message: string;
  error?: string | null;
  result?: any;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Benchmark {
  id?: number;
  name?: string;
  results?: any[];
  created_at?: string;
  [key: string]: any;
}

export interface ParamSpec {
  name: string;
  label: string;
  type: "int" | "float" | "bool" | "select" | "palette" | "color" | "text" | string;
  default: any;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  options?: string[];
}

export interface CatalogItem {
  id: string;
  name: string;
  group: string;
  group_label: string;
  params: ParamSpec[];
}

export interface PreviewResult {
  url: string;
  info: Record<string, any>;
  source_url: string;
  cached: boolean;
  asset_id: string;
}

export interface SpriteExtraction {
  sprites: Asset[];
  count: number;
  warnings: string[];
  cutout_url: string | null;
  group: string;
  background: [number, number, number] | null;
  saved: boolean;
  duplicates: number;
}

export interface TilePreview {
  index: number;
  source_x: number;
  source_y: number;
  row: number;
  col: number;
  url: string;
  duplicate_of: number | null;
  near_duplicate_of: number | null;
  empty: boolean;
}

export interface TileExtraction {
  tiles: TilePreview[];
  total: number;
  shown: number;
  duplicates: number;
  near_duplicates: number;
  tile_size: number;
  sheet_url: string;
  sheet: Record<string, any>;
  source_url: string;
  truncated: boolean;
}

export interface TerrainInfo {
  id: string;
  name: string;
  palette: string[];
  edge: number;
}

export interface Animation {
  id: string;
  project_id: string;
  name: string;
  fps: number;
  loop: boolean;
  frames: string[];
  meta: Record<string, any>;
  created_at: string;
  updated_at: string;
  frame_assets: Asset[];
  frame_count: number;
}

export interface Preset {
  id: string;
  name: string;
  description?: string;
  files?: string[];
  [key: string]: any;
}

export interface WorkspaceLayer {
  uid: string;
  asset_id: string;
  name: string;
  x: number;
  y: number;
  scale: number;
  rotation: number;
  opacity: number;
  visible: boolean;
  url: string;
  width: number;
  height: number;
}

export interface StyleProfile {
  palette_id: string | null;
  colors: string[];
  max_colors: number;
  pixel_scale: number;
  outline: "none" | "dark" | "light" | "custom" | string;
  outline_width: number;
  outline_color: string;
  brightness: number;
  contrast: number;
  saturation: number;
  shading_steps: number;
  dither: "none" | "bayer" | string;
}

export interface StyleRow {
  asset_id: string;
  name: string;
  kind: string;
  width: number;
  height: number;
  colors: number;
  palette_coverage: number | null;
  outline_ratio: number | null;
  pixel_scale: number;
  score: number;
  palette: string[];
  notes: string[];
  error?: string;
}

export interface StyleSummary {
  assets: number;
  score: number | null;
  mean_asset_score: number | null;
  palette_coverage: number | null;
  average_colors: number | null;
  pairwise_palette_overlap: number | null;
  consistent: boolean | null;
  recommendations: string[];
}

export interface StyleReport {
  profile: StyleProfile;
  rows: StyleRow[];
  aggregate: StyleSummary;
}

export interface StyledResult {
  source: Asset;
  asset?: Asset;
  url: string;
  info: {
    applied: string[];
    colors_before: number;
    colors_after: number;
    pixel_scale_before: number;
    pixel_scale_after: number;
    palette_coverage_before: number | null;
    palette_coverage_after: number | null;
    outline_pixels: number;
    score_before: number;
    score_after: number;
    width: number;
    height: number;
    [key: string]: any;
  };
}
