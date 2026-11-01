import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "./Icon";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/pixelart": "Image → Pixel Art",
  "/sprites": "Sprite Extractor",
  "/tileset": "Tileset Generator",
  "/procedural": "Procedural Generator",
  "/false3d": "False 3D Lab",
  "/animation": "Animation Studio",
  "/library": "Asset Library",
  "/style": "Style Consistency",
  "/projects": "Project Manager",
  "/settings": "Settings",
};

export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const projects = useStudio((s) => s.projects);
  const projectId = useStudio((s) => s.projectId);
  const selectProject = useStudio((s) => s.selectProject);
  const ensureProject = useStudio((s) => s.ensureProject);
  const setLastImported = useStudio((s) => s.setLastImported);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const refreshProject = useStudio((s) => s.refreshProject);
  const save = useStudio((s) => s.save);
  const notify = useStudio((s) => s.notify);
  const settings = useStudio((s) => s.settings);
  const language = useStudio((s) => s.language);
  const setLanguage = useStudio((s) => s.setLanguage);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState("");

  const title = TITLES[location.pathname] || "Pixel Studio";

  useEffect(() => {
    const onImport = () => fileRef.current?.click();
    window.addEventListener("pas:import", onImport);
    return () => window.removeEventListener("pas:import", onImport);
  }, []);

  const upload = async (file?: File | null) => {
    if (!file) return;
    setUploading(true);
    try {
      const project = await ensureProject();
      const asset = await api.uploadAsset(project, file, "source", file.name.replace(/\.[^.]+$/, ""));
      await Promise.all([refreshAssets(), refreshProject()]);
      setLastImported(asset);
      notify(`Imported ${asset.name} (${asset.width}×${asset.height})`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const search = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) navigate(`/library?q=${encodeURIComponent(query.trim())}`);
  };

  return (
    <Localize>
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-ink-700/80 bg-ink-900/80 px-4 backdrop-blur">
      <div className="flex min-w-[170px] items-center gap-2">
        <h1 className="truncate text-[13px] font-semibold text-ink-100">{title}</h1>
        {settings && (
          <span className="chip" title="Threads assigned to background jobs">
            {settings.worker_threads} thr
          </span>
        )}
      </div>

      <form onSubmit={search} className="relative max-w-[260px] flex-1">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search assets…"
          className="field !py-1 pl-8 text-[11.5px]"
        />
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-500">
          <Icon name="zoomIn" size={13} />
        </span>
      </form>

      <div className="ml-auto flex items-center gap-2">
        <div className="flex items-center rounded-md border border-ink-700 bg-ink-900 p-0.5" role="group" aria-label="Interface language">
          <button
            type="button"
            onClick={() => setLanguage("es")}
            title="Español"
            className={`rounded px-1.5 py-[3px] text-[10.5px] font-medium transition ${
              language === "es" ? "bg-[rgb(var(--accent))] text-white" : "text-ink-400 hover:text-ink-100"
            }`}
          >
            ES
          </button>
          <button
            type="button"
            onClick={() => setLanguage("en")}
            title="English"
            className={`rounded px-1.5 py-[3px] text-[10.5px] font-medium transition ${
              language === "en" ? "bg-[rgb(var(--accent))] text-white" : "text-ink-400 hover:text-ink-100"
            }`}
          >
            EN
          </button>
        </div>

        <select
          className="field !w-auto max-w-[190px] !py-1 text-[11.5px]"
          value={projectId || ""}
          onChange={(e) => {
            void selectProject(e.target.value || null);
            void refreshProject();
          }}
          title="Active project"
        >
          {projects.length === 0 && <option value="">No projects</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/bmp,image/gif"
          className="hidden"
          onChange={(e) => void upload(e.target.files?.[0])}
        />
        <button
          type="button"
          className="btn-ghost"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
          title="Import a source image (Ctrl+U)"
        >
          <Icon name="upload" size={14} />
          {uploading ? "Importing…" : "Import"}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={!projectId}
          onClick={() => void save("manual")}
          title="Save project (Ctrl+S)"
        >
          <Icon name="save" size={14} />
          Save
        </button>
      </div>
    </header>
    </Localize>
  );
}
