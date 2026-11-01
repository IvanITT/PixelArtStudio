import type {
  Animation,
  Asset,
  CatalogItem,
  Health,
  JobRecord,
  Palette,
  Preset,
  PreviewResult,
  Project,
  Settings,
  SpriteExtraction,
  StyledResult,
  StyleProfile,
  StyleReport,
  SystemStats,
  TerrainInfo,
  TileExtraction,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError("Cannot reach the local server. Start it with start.bat.", 0);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") || "";
  if (!type.includes("application/json")) return (await res.text()) as unknown as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const patch = (body: unknown): RequestInit => ({
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => request<Health>("/health"),
  settings: () => request<Settings>("/settings"),
  updateSettings: (body: Partial<Settings>) => request<Settings>("/settings", patch(body)),
  stats: () => request<SystemStats>("/system/stats"),
  cleanup: () => request<{ removed: number; data: SystemStats["data"] }>("/system/cleanup", { method: "POST" }),
  benchmarks: (limit = 10) => request<any[]>("/benchmarks" + qs({ limit })),
  runBenchmarks: () => request<{ job_id: string }>("/benchmarks/run", { method: "POST" }),

  palettes: (projectId?: string) => request<Palette[]>("/palettes" + qs({ project_id: projectId })),
  createPalette: (body: { name: string; colors: string[]; project_id?: string | null; note?: string }) =>
    request<Palette>("/palettes", json(body)),
  deletePalette: (id: string) => request<{ deleted: boolean }>(`/palettes/${id}`, { method: "DELETE" }),

  projects: () => request<Project[]>("/projects"),
  project: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (body: { name: string; description?: string; category?: string }) =>
    request<Project>("/projects", json(body)),
  updateProject: (id: string, body: Record<string, any>) =>
    request<Project>(`/projects/${id}`, patch(body)),
  deleteProject: (id: string) => request<{ deleted: boolean }>(`/projects/${id}?confirm=true`, { method: "DELETE" }),
  duplicateProject: (id: string) => request<Project>(`/projects/${id}/duplicate`, { method: "POST" }),
  saveProject: (id: string, note = "manual", state?: Record<string, any>) =>
    request<{ saved: boolean; backup: any; project: Project }>(`/projects/${id}/save`, json({ note, state })),
  backups: (id: string) => request<any[]>(`/projects/${id}/backups`),
  restoreBackup: (id: string, backupId: string) =>
    request<{ restored: boolean }>(`/projects/${id}/backups/${backupId}/restore`, { method: "POST" }),
  exportProjectUrl: (id: string) => `${BASE}/projects/${id}/export`,
  importProject: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<Project>("/projects/import", { method: "POST", body: fd });
  },

  assets: (pid: string, params: { kind?: string; search?: string; favorite?: boolean; tag?: string; limit?: number } = {}) =>
    request<Asset[]>(`/projects/${pid}/assets` + qs({ kind: params.kind || "all", ...params })),
  asset: (id: string) => request<Asset>(`/assets/${id}`),
  updateAsset: (id: string, body: Record<string, any>) => request<Asset>(`/assets/${id}`, patch(body)),
  deleteAsset: (id: string) => request<{ deleted: boolean }>(`/assets/${id}`, { method: "DELETE" }),
  batchAssets: (ids: string[], action: string, value?: string | boolean | null) =>
    request<{ updated: number }>("/assets/batch", json({ ids, action, value })),
  uploadAsset: (pid: string, file: File, kind: "source" | "sprite" = "source", name = "") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", name);
    fd.append("kind", kind);
    return request<Asset>(`/projects/${pid}/assets/upload`, { method: "POST", body: fd });
  },

  pixelPreview: (body: { project_id: string; asset_id: string; options: Record<string, any> }) =>
    request<PreviewResult>("/pixelart/preview", json(body)),
  pixelPreviewJob: (body: { project_id: string; asset_id: string; options: Record<string, any> }) =>
    request<{ job_id: string }>("/pixelart/job", json(body)),
  pixelExport: (body: { project_id: string; asset_id: string; options: Record<string, any>; name?: string }) =>
    request<{ asset: Asset; info: Record<string, any> }>("/pixelart/export", json(body)),
  workspaceExport: (body: Record<string, any>) =>
    request<{ asset: Asset }>("/workspace/export", json(body)),

  extractSprites: (body: { project_id: string; asset_id: string; options: Record<string, any>; save?: boolean; name_prefix?: string }) =>
    request<SpriteExtraction>("/sprites/extract", json(body)),
  packSprites: (body: { project_id: string; sprite_ids: string[]; options: Record<string, any>; name?: string }) =>
    request<{ asset: Asset; sheet: Record<string, any>; url: string }>("/sprites/pack", json(body)),
  adjustSprite: (id: string, body: Record<string, any>) =>
    request<{ asset: Asset }>(`/sprites/${id}/adjust`, json(body)),

  tilesetTerrains: () => request<TerrainInfo[]>("/tileset/terrains"),
  extractTiles: (body: { project_id: string; asset_id: string; options: Record<string, any> }) =>
    request<TileExtraction>("/tileset/extract", json(body)),
  saveTileset: (body: Record<string, any>) =>
    request<{ asset: Asset; sheet: Record<string, any> }>("/tileset/save", json(body)),
  terrain: (body: Record<string, any>) =>
    request<{ asset: Asset; sheet: Record<string, any>; preview_url: string; tiles: { mask: number; url: string }[]; terrain: string }>(
      "/tileset/terrain",
      json(body),
    ),
  seamless: (body: Record<string, any>) =>
    request<{ url: string; seam_error_before: number; seam_error_after: number; asset: Asset | null }>("/tileset/seamless", json(body)),
  recolor: (body: Record<string, any>) => request<{ url: string; asset: Asset | null }>("/tileset/recolor", json(body)),

  catalog: () => request<CatalogItem[]>("/procedural/catalog"),
  generate: (body: { project_id: string; generator: string; params: Record<string, any>; seed: number; count: number; save?: boolean; name?: string }) =>
    request<{ generator: string; items: { asset: Asset | null; info: Record<string, any>; url: string; seed: number }[]; count: number }>(
      "/procedural/generate",
      json(body),
    ),

  false3dTemplates: () =>
    request<{ templates: { id: string; name: string; description: string; defaults: Record<string, any> }[]; disclaimer: string }>(
      "/false3d/templates",
    ),
  false3dPreview: (body: Record<string, any>) =>
    request<{ url: string; info: Record<string, any>; asset: Asset | null; source_url: string }>("/false3d/preview", json(body)),
  heightmap: (body: Record<string, any>) => request<{ url: string; asset: Asset | null }>("/false3d/heightmap", json(body)),

  animations: (pid: string) => request<Animation[]>(`/projects/${pid}/animations`),
  createAnimation: (pid: string, body: { name: string; fps?: number; loop?: boolean; frames?: string[] }) =>
    request<Animation>(`/projects/${pid}/animations`, json(body)),
  animation: (id: string) => request<Animation>(`/animations/${id}`),
  updateAnimation: (id: string, body: Record<string, any>) => request<Animation>(`/animations/${id}`, patch(body)),
  deleteAnimation: (id: string) => request<{ deleted: boolean }>(`/animations/${id}`, { method: "DELETE" }),
  addFrame: (id: string, assetId: string, index?: number) =>
    request<Animation>(`/animations/${id}/frames`, json({ asset_id: assetId, index })),
  deleteFrame: (id: string, index: number) =>
    request<Animation>(`/animations/${id}/frames/${index}`, { method: "DELETE" }),
  duplicateFrame: (id: string, from: number, to: number) =>
    request<Animation>(`/animations/${id}/duplicate-frame`, json({ from_index: from, to_index: to })),
  reorderFrames: (id: string, from: number, to: number) =>
    request<Animation>(`/animations/${id}/reorder`, json({ from_index: from, to_index: to })),
  applyTemplate: (id: string, body: { asset_id: string; template: string; frames?: number | null; replace?: boolean }) =>
    request<Animation>(`/animations/${id}/template`, json(body)),
  uploadFrame: (pid: string, aid: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ animation: Animation; frame: Asset }>(`/projects/${pid}/animations/${aid}/frames/upload`, {
      method: "POST",
      body: fd,
    });
  },
  exportAnimation: (id: string, body: Record<string, any>) =>
    request<{ asset: Asset; metadata?: Record<string, any>; format: string }>(`/animations/${id}/export`, json(body)),

  presets: () => request<{ presets: Preset[]; formats: string[] }>("/export/presets"),
  packageExport: (body: Record<string, any>) => request<{ job_id: string }>("/export/package", json(body)),
  exports: (pid: string) => request<{ filename: string; bytes: number; created_at: number; download_url: string }[]>(`/projects/${pid}/exports`),

  jobs: () => request<{ active: JobRecord[]; recent: JobRecord[] }>("/jobs"),
  job: (id: string) => request<JobRecord>(`/jobs/${id}`),
  cancelJob: (id: string) => request<{ cancelled: boolean }>(`/jobs/${id}/cancel`, { method: "POST" }),
  jobEventsUrl: (id: string) => `${BASE}/jobs/${id}/events`,

  styleProfile: (pid: string) => request<{ profile: StyleProfile; defaults: StyleProfile }>(`/style/${pid}`),
  updateStyle: (pid: string, profile: Partial<StyleProfile>) =>
    request<{ profile: StyleProfile }>(`/style/${pid}`, patch({ profile })),
  applyStyle: (body: { project_id: string; asset_ids: string[]; profile?: StyleProfile; save?: boolean; name_suffix?: string }) =>
    request<{ profile: StyleProfile; results: StyledResult[]; count: number; saved: boolean }>("/style/apply", json(body)),
  styleReport: (body: { project_id: string; asset_ids?: string[]; profile?: StyleProfile; limit?: number }) =>
    request<StyleReport>("/style/report", json(body)),
};

export function mediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (url.startsWith("http") || url.startsWith("data:") || url.startsWith("blob:")) return url;
  return url.startsWith("/") ? url : `/${url}`;
}

export function errorText(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return String(err);
}
