import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, errorText, mediaUrl } from "../api/client";
import type { Asset, Preset } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "../components/Icon";
import { Empty, Modal, ProgressBar, Segmented, Spinner, bytes } from "../components/ui";

const KINDS = [
  { value: "all", label: "All" },
  { value: "source", label: "Sources" },
  { value: "pixelart", label: "Pixel art" },
  { value: "sprite", label: "Sprites" },
  { value: "spritesheet", label: "Sheets" },
  { value: "tileset", label: "Tilesets" },
  { value: "procedural", label: "Procedural" },
  { value: "false3d", label: "2.5D" },
  { value: "frame", label: "Frames" },
  { value: "animation", label: "Animations" },
  { value: "workspace", label: "Workspace" },
];

export function Library() {
  const projectId = useStudio((s) => s.projectId);
  const assets = useStudio((s) => s.assets);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const notify = useStudio((s) => s.notify);
  const [params] = useSearchParams();

  const [kind, setKind] = useState("all");
  const [search, setSearch] = useState(params.get("q") || "");
  const [favorite, setFavorite] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<Asset | null>(null);
  const [renaming, setRenaming] = useState("");
  const [tags, setTags] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [formats, setFormats] = useState<string[]>([]);
  const [preset, setPreset] = useState("generic");
  const [format, setFormat] = useState("png");
  const [packName, setPackName] = useState("");
  const [job, setJob] = useState<{ status: string; progress: number; message: string; result?: any; error?: string } | null>(null);
  const [exporting, setExporting] = useState(false);
  const [zoom, setZoom] = useState<"sm" | "md" | "lg">("md");

  useEffect(() => {
    api
      .presets()
      .then((res) => {
        setPresets(res.presets);
        setFormats(res.formats);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setSearch(params.get("q") || "");
  }, [params]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return assets.filter((a) => {
      if (kind !== "all" && a.kind !== kind) return false;
      if (favorite && !a.favorite) return false;
      if (!q) return true;
      return a.name.toLowerCase().includes(q) || a.tags.join(" ").toLowerCase().includes(q) || a.kind.includes(q);
    });
  }, [assets, kind, favorite, search]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const openDetail = (asset: Asset) => {
    setDetail(asset);
    setRenaming(asset.name);
    setTags(asset.tags.join(", "));
  };

  const saveDetail = async () => {
    if (!detail) return;
    try {
      const updated = await api.updateAsset(detail.id, { name: renaming, tags });
      setDetail(updated);
      await refreshAssets();
      notify("Asset updated", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const remove = async () => {
    if (!detail) return;
    if (!window.confirm(`Delete “${detail.name}”? This cannot be undone.`)) return;
    try {
      await api.deleteAsset(detail.id);
      setDetail(null);
      await refreshAssets();
      notify("Asset deleted", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const batch = async (action: string, value?: string | boolean) => {
    if (selected.size === 0) return;
    try {
      const res = await api.batchAssets(Array.from(selected), action, value);
      await refreshAssets();
      notify(`${res.updated} assets updated`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const packSprites = async () => {
    const ids = assets.filter((a) => selected.has(a.id) && a.kind === "sprite").map((a) => a.id);
    if (ids.length < 1) {
      notify("Select one or more sprites first", "error");
      return;
    }
    try {
      const res = await api.packSprites({ project_id: projectId!, sprite_ids: ids, options: { padding: 2, spacing: 2, max_dim: 8192 }, name: "Library sheet" });
      await refreshAssets();
      notify(`Packed ${res.asset.name}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const runExport = async () => {
    if (!projectId || selected.size === 0) return;
    setExporting(true);
    setJob(null);
    try {
      const { job_id } = await api.packageExport({
        project_id: projectId,
        asset_ids: Array.from(selected),
        preset,
        format,
        name: packName || undefined,
      });
      const poll = window.setInterval(async () => {
        try {
          const j = await api.job(job_id);
          setJob({ status: j.status, progress: j.progress, message: j.message, result: j.result, error: j.error || undefined });
          if (["done", "error", "cancelled"].includes(j.status)) {
            window.clearInterval(poll);
            setExporting(false);
            if (j.status === "done") notify("ZIP package ready", "success");
            else notify(j.error || "Export failed", "error");
          }
        } catch {
          window.clearInterval(poll);
          setExporting(false);
        }
      }, 500);
    } catch (err) {
      setExporting(false);
      notify(errorText(err), "error");
    }
  };

  const sizeClass = zoom === "sm" ? "minmax(92px,1fr)" : zoom === "md" ? "minmax(128px,1fr)" : "minmax(184px,1fr)";

  return (
    <Localize>
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-ink-700/70 px-3 py-2">
        <input className="field !w-[180px] !py-1" placeholder="Filter by name or tag…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="field !w-auto !py-1" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setFavorite((f) => !f)}
          className={`btn ${favorite ? "border-amber-600/60 bg-amber-500/10 text-amber-300" : "btn-ghost"} !py-1`}
        >
          <Icon name="star" size={12} /> Favorites
        </button>
        <span className="text-[10.5px] text-ink-500">{visible.length} shown</span>
        <div className="ml-auto flex items-center gap-1.5">
          <Segmented
            size="sm"
            value={zoom}
            onChange={setZoom}
            options={[
              { value: "sm", label: "S" },
              { value: "md", label: "M" },
              { value: "lg", label: "L" },
            ]}
          />
          {selected.size > 0 && (
            <>
              <button className="btn-ghost !py-1" onClick={() => void batch("favorite", true)}>
                <Icon name="star" size={12} /> Favorite
              </button>
              <button className="btn-ghost !py-1" onClick={() => void packSprites()}>
                <Icon name="sprites" size={12} /> Pack
              </button>
              <button className="btn-primary !py-1" onClick={() => setExportOpen(true)}>
                <Icon name="download" size={12} /> Export {selected.size}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {visible.length === 0 ? (
          <Empty icon={<Icon name="library" size={24} />} title="Nothing here yet" hint="Run any module to generate assets, or import a source image from the top bar." />
        ) : (
          <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(auto-fill, ${sizeClass})` }}>
            {visible.map((a) => {
              const active = selected.has(a.id);
              return (
                <div
                  key={a.id}
                  className={`group relative overflow-hidden rounded-lg border bg-ink-850 transition ${
                    active ? "border-[rgb(var(--accent))] shadow-glow" : "border-ink-700 hover:border-ink-600"
                  }`}
                >
                  <button type="button" onClick={() => toggle(a.id)} className="checker grid h-[124px] w-full place-items-center overflow-hidden">
                    <img src={mediaUrl(a.thumb_url || a.url)} alt={a.name} className="max-h-[116px] max-w-full object-contain pixelated" loading="lazy" />
                  </button>
                  <span className="absolute left-1.5 top-1.5 rounded bg-black/65 px-1.5 py-0.5 text-[8.5px] uppercase tracking-wide text-ink-300">
                    {a.kind}
                  </span>
                  {a.favorite && <Icon name="star" size={12} className="absolute left-1.5 bottom-[52px] text-amber-400" />}
                  <button
                    type="button"
                    className={`absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded border ${
                      active ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))] text-white" : "border-ink-600 bg-black/60 text-transparent hover:text-ink-300"
                    }`}
                    onClick={() => toggle(a.id)}
                  >
                    <Icon name="check" size={11} />
                  </button>
                  <div className="px-2 py-1.5">
                    <button type="button" className="block w-full truncate text-left text-[10.5px] text-ink-200 hover:text-ink-50" onClick={() => openDetail(a)}>
                      {a.name}
                    </button>
                    <p className="font-mono text-[9px] text-ink-500">
                      {a.width}×{a.height} · {bytes(a.size_bytes)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <Modal
        open={Boolean(detail)}
        title={detail?.name || "Asset"}
        onClose={() => setDetail(null)}
        wide
        footer={
          detail && (
            <>
              <a className="btn-ghost" href={detail.download_url}>
                <Icon name="download" size={13} /> Download
              </a>
              <button className="btn-danger" onClick={() => void remove()}>
                <Icon name="trash" size={13} /> Delete
              </button>
              <button className="btn-primary" onClick={() => void saveDetail()}>
                <Icon name="save" size={13} /> Save changes
              </button>
            </>
          )
        }
      >
        {detail && (
          <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
            <div>
              <div className="checker grid h-[260px] place-items-center overflow-hidden rounded-lg border border-ink-700">
                <img src={mediaUrl(detail.url)} alt={detail.name} className="max-h-[252px] max-w-full object-contain pixelated" />
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {detail.tags.map((t) => (
                  <span key={t} className="chip">
                    {t}
                  </span>
                ))}
                {detail.tags.length === 0 && <span className="text-[10.5px] text-ink-500">No tags</span>}
              </div>
            </div>
            <div className="space-y-3">
              <label className="block space-y-1">
                <span className="label">Name</span>
                <input className="field" value={renaming} onChange={(e) => setRenaming(e.target.value)} />
              </label>
              <label className="block space-y-1">
                <span className="label">Tags (comma separated)</span>
                <input className="field" value={tags} onChange={(e) => setTags(e.target.value)} />
              </label>
              <dl className="grid grid-cols-2 gap-2 text-[10.5px]">
                {[
                  ["Kind", detail.kind],
                  ["Size", `${detail.width}×${detail.height}`],
                  ["File", bytes(detail.size_bytes)],
                  ["Created", new Date(detail.created_at).toLocaleString()],
                  ["SHA-256", detail.sha256?.slice(0, 16)],
                  ["Favorite", detail.favorite ? "yes" : "no"],
                ].map(([k, v]) => (
                  <div key={k} className="rounded bg-ink-800/70 p-1.5">
                    <dt className="text-ink-500">{k}</dt>
                    <dd className="truncate font-mono text-ink-200">{v}</dd>
                  </div>
                ))}
              </dl>
              <details className="rounded border border-ink-700 bg-ink-900 p-2 text-[10px]">
                <summary className="cursor-pointer text-ink-300">Metadata JSON</summary>
                <pre className="mt-1 max-h-[160px] overflow-auto font-mono text-[9.5px] text-ink-400">{JSON.stringify(detail.meta, null, 2)}</pre>
              </details>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={exportOpen}
        title={`Export ${selected.size} assets`}
        onClose={() => setExportOpen(false)}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setExportOpen(false)}>
              Close
            </button>
            <button className="btn-primary" onClick={() => void runExport()} disabled={exporting || selected.size === 0}>
              <Icon name="download" size={13} /> Build ZIP
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1">
              <span className="label">Preset</span>
              <select className="field" value={preset} onChange={(e) => setPreset(e.target.value)}>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="label">Format</span>
              <select className="field" value={format} onChange={(e) => setFormat(e.target.value)}>
                {formats.map((f) => (
                  <option key={f} value={f}>
                    {f.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="block space-y-1">
            <span className="label">Package name</span>
            <input className="field" placeholder="Auto from project name" value={packName} onChange={(e) => setPackName(e.target.value)} />
          </label>
          <p className="text-[10.5px] leading-relaxed text-ink-500">
            The ZIP includes converted images, sprite/tileset metadata and engine-specific manifests. Naming follows the selected
            preset so files drop straight into Godot, Unity or RPG Maker projects.
          </p>
          {(exporting || job) && (
            <div className="space-y-1 rounded border border-ink-700 bg-ink-900 p-2.5">
              <div className="flex items-center justify-between text-[10.5px]">
                <span className="text-ink-300">
                  {job?.message || (exporting ? "Starting export…" : "")}
                </span>
                <span className="font-mono text-ink-500">{job?.progress ?? 0}%</span>
              </div>
              <ProgressBar value={job?.progress ?? 0} />
              {job?.error && <p className="text-[10.5px] text-rose-400">{job.error}</p>}
              {job?.result?.download_url && (
                <a className="btn-ghost mt-1 w-full" href={job.result.download_url}>
                  <Icon name="download" size={13} /> Download {job.result.filename || "package.zip"}
                </a>
              )}
            </div>
          )}
          {exporting && <Spinner label="Building package in background" />}
        </div>
      </Modal>
    </div>
    </Localize>
  );
}
