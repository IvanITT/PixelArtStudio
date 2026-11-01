import { create } from "zustand";
import { api, errorText } from "../api/client";
import type { Asset, Health, Palette, Project, Settings } from "../api/types";

const ACCENTS: Record<string, string> = {
  violet: "139 92 246",
  teal: "20 184 166",
  amber: "245 158 11",
  rose: "244 63 94",
  blue: "59 130 246",
  green: "34 197 94",
};

export function accentRgb(name: string): string {
  return ACCENTS[name] || ACCENTS.violet;
}

export type ToastKind = "info" | "success" | "error";

export type Language = "en" | "es";

const LANG_KEY = "pas.language";

function initialLanguage(): Language {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved === "en" || saved === "es") return saved;
    if (typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("es")) return "es";
  } catch {
    /* localStorage unavailable */
  }
  return "en";
}

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

interface StudioState {
  ready: boolean;
  booting: boolean;
  fatal: string | null;
  health: Health | null;
  settings: Settings | null;
  projects: Project[];
  projectId: string | null;
  project: Project | null;
  assets: Asset[];
  palettes: Palette[];
  assetsLoading: boolean;
  toasts: Toast[];
  lastSaveAt: string | null;
  lastImported: Asset | null;
  setLastImported: (asset: Asset | null) => void;
  language: Language;
  setLanguage: (language: Language) => void;
  bootstrap: () => Promise<void>;
  selectProject: (id: string | null) => Promise<void>;
  ensureProject: () => Promise<string>;
  refreshProjects: () => Promise<void>;
  refreshProject: () => Promise<void>;
  refreshAssets: () => Promise<void>;
  refreshPalettes: () => Promise<void>;
  updateSettings: (patch: Partial<Settings>) => Promise<void>;
  notify: (message: string, kind?: ToastKind) => void;
  dismiss: (id: number) => void;
  save: (note?: string, state?: Record<string, any>) => Promise<void>;
}

const PROJECT_KEY = "pas.currentProject";

export const useStudio = create<StudioState>((set, get) => ({
  ready: false,
  booting: true,
  fatal: null,
  health: null,
  settings: null,
  projects: [],
  projectId: null,
  project: null,
  assets: [],
  palettes: [],
  assetsLoading: false,
  toasts: [],
  lastSaveAt: null,
  lastImported: null,
  language: initialLanguage(),

  setLastImported: (asset) => set({ lastImported: asset }),

  setLanguage: (language) => {
    try {
      localStorage.setItem(LANG_KEY, language);
    } catch {
      /* non fatal */
    }
    document.documentElement.lang = language;
    set({ language });
  },

  notify: (message, kind = "info") => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    set((s) => ({ toasts: [...s.toasts.slice(-3), { id, message, kind }] }));
    window.setTimeout(() => get().dismiss(id), kind === "error" ? 7000 : 3600);
  },

  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  bootstrap: async () => {
    set({ booting: true, fatal: null });
    try {
      const [health, settings, projects] = await Promise.all([api.health(), api.settings(), api.projects()]);
      document.documentElement.style.setProperty("--accent", accentRgb(settings.accent));
      document.body.classList.toggle("reduce-motion", Boolean(settings.reduce_motion));
      set({ health, settings, projects, ready: true, booting: false });
      const saved = localStorage.getItem(PROJECT_KEY);
      const ids = new Set(projects.map((p) => p.id));
      const target = (saved && ids.has(saved) ? saved : projects[0]?.id) || null;
      if (target) await get().selectProject(target);
      else set({ projectId: null, project: null, assets: [] });
    } catch (err) {
      set({ booting: false, fatal: errorText(err), ready: false });
    }
  },

  selectProject: async (id) => {
    if (!id) {
      set({ projectId: null, project: null, assets: [], palettes: [] });
      localStorage.removeItem(PROJECT_KEY);
      return;
    }
    set({ projectId: id, assetsLoading: true });
    localStorage.setItem(PROJECT_KEY, id);
    try {
      const [project, assets] = await Promise.all([api.project(id), api.assets(id, { limit: 500 })]);
      const palettes = await api.palettes(id).catch(() => [] as Palette[]);
      set({ project, assets, palettes, assetsLoading: false });
    } catch (err) {
      set({ assetsLoading: false });
      get().notify(errorText(err), "error");
    }
  },

  /**
   * Returns the active project, creating and selecting one when the studio is
   * still empty. This makes "import an image" work on a first run instead of
   * silently doing nothing because there is no project yet.
   */
  ensureProject: async () => {
    const current = get().projectId;
    if (current && get().project) return current;

    let projects = get().projects;
    if (projects.length === 0) {
      projects = await api.projects();
      set({ projects });
    }
    if (projects.length > 0) {
      await get().selectProject(projects[0].id);
      return projects[0].id;
    }

    const name = get().language === "es" ? "Mi proyecto" : "My project";
    const created = await api.createProject({ name, description: "", category: "General" });
    set({ projects: [created, ...get().projects] });
    await get().selectProject(created.id);
    get().notify(
      get().language === "es" ? "Proyecto creado automáticamente para importar la imagen" : "Project created automatically for the import",
      "success",
    );
    return created.id;
  },

  refreshProjects: async () => {
    try {
      const projects = await api.projects();
      set({ projects });
    } catch (err) {
      get().notify(errorText(err), "error");
    }
  },

  refreshProject: async () => {
    const id = get().projectId;
    if (!id) return;
    try {
      const project = await api.project(id);
      set({ project });
    } catch {
      /* non fatal */
    }
  },

  refreshAssets: async () => {
    const id = get().projectId;
    if (!id) return;
    set({ assetsLoading: true });
    try {
      const assets = await api.assets(id, { limit: 500 });
      set({ assets, assetsLoading: false });
      void get().refreshProject();
    } catch (err) {
      set({ assetsLoading: false });
      get().notify(errorText(err), "error");
    }
  },

  refreshPalettes: async () => {
    try {
      const palettes = await api.palettes(get().projectId || undefined);
      set({ palettes });
    } catch {
      /* non fatal */
    }
  },

  updateSettings: async (patchValues) => {
    try {
      const settings = await api.updateSettings(patchValues);
      document.documentElement.style.setProperty("--accent", accentRgb(settings.accent));
      document.body.classList.toggle("reduce-motion", Boolean(settings.reduce_motion));
      set({ settings });
      get().notify("Settings saved", "success");
    } catch (err) {
      get().notify(errorText(err), "error");
    }
  },

  save: async (note = "manual", state) => {
    const id = get().projectId;
    if (!id) return;
    try {
      const res = await api.saveProject(id, note, state);
      set({ project: res.project, lastSaveAt: new Date().toISOString() });
      get().notify(note === "autosave" ? "Project autosaved" : "Project saved", "success");
      void get().refreshProjects();
    } catch (err) {
      get().notify(errorText(err), "error");
    }
  },
}));
