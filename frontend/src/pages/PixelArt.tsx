import { useEffect, useRef, useState } from "react";
import { api, errorText } from "../api/client";
import type { Palette, PreviewResult } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { AssetPicker, DropZone } from "../components/AssetPicker";
import { ImageStage } from "../components/ImageStage";
import { Icon } from "../components/Icon";
import { Panel, Segmented, Slider, Toggle, bytes, Empty, ProgressBar, Select } from "../components/ui";
import { Workspace } from "../components/Workspace";

interface PixelOptions {
  width: number;
  height: number;
  block_size: number;
  resize_method: string;
  quantizer: string;
  colors: number;
  dither: string;
  dither_strength: number;
  brightness: number;
  contrast: number;
  saturation: number;
  denoise: number;
  edge_preserve: number;
  edge_enhance: number;
  transparent: boolean;
  bg_color: string;
  bg_tolerance: number;
  palette_id: string;
  palette_colors: string[];
  pixel_grid: boolean;
}

const DEFAULTS: PixelOptions = {
  width: 128,
  height: 128,
  block_size: 1,
  resize_method: "lanczos",
  quantizer: "median_cut",
  colors: 16,
  dither: "none",
  dither_strength: 0.75,
  brightness: 1,
  contrast: 1,
  saturation: 1,
  denoise: 0,
  edge_preserve: 0,
  edge_enhance: 0,
  transparent: false,
  bg_color: "#000000",
  bg_tolerance: 24,
  palette_id: "",
  palette_colors: [],
  pixel_grid: false,
};

const PRESETS: Record<string, Partial<PixelOptions>> = {
  "16-bit RPG": { width: 128, height: 128, colors: 32, dither: "bayer", quantizer: "median_cut" },
  "Game Boy": { width: 160, height: 144, colors: 4, dither: "floyd", palette_id: "gameboy" },
  "PICO-8": { width: 128, height: 128, colors: 16, dither: "none", palette_id: "pico8" },
  "HD pixel art": { width: 256, height: 256, colors: 48, dither: "none", quantizer: "kmeans" },
  "Poster": { width: 192, height: 192, colors: 12, dither: "atkinson", quantizer: "adaptive" },
};

export function PixelArt() {
  const projectId = useStudio((s) => s.projectId);
  const lastImported = useStudio((s) => s.lastImported);
  const assets = useStudio((s) => s.assets);
  const palettes = useStudio((s) => s.palettes);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const ensureProject = useStudio((s) => s.ensureProject);
  const notify = useStudio((s) => s.notify);

  useEffect(() => {
    if (lastImported && lastImported.project_id === projectId) setSourceId(lastImported.id);
  }, [lastImported, projectId]);

  const [tab, setTab] = useState<"convert" | "workspace">("convert");
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [options, setOptions] = useState<PixelOptions>(DEFAULTS);
  const [lockRatio, setLockRatio] = useState(true);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState("");
  const [viewMode, setViewMode] = useState<"result" | "source">("source");
  const [customPalette, setCustomPalette] = useState("");
  const [exporting, setExporting] = useState(false);
  const [dirty, setDirty] = useState(true);
  const pollRef = useRef<number | null>(null);
  const sizedSource = useRef<string | null>(null);

  const source = assets.find((a) => a.id === sourceId) || null;

  useEffect(() => {
    if (lastImported && lastImported.project_id === projectId) setSourceId(lastImported.id);
  }, [lastImported, projectId]);

  // Switching projects must not keep a source from the previous project.
  useEffect(() => {
    setSourceId(null);
    setPreview(null);
    setViewMode("source");
    setDirty(true);
    if (pollRef.current) window.clearTimeout(pollRef.current);
    setProcessing(false);
    setProgress(0);
    setPhase("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    const first = assets.find((a) => a.kind === "source") || assets[0];
    if (!sourceId && first) setSourceId(first.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assets]);

  useEffect(() => {
    setPreview(null);
    setViewMode("source");
    setDirty(true);
    setProgress(0);
    setPhase("");
    if (pollRef.current) window.clearTimeout(pollRef.current);
    setProcessing(false);
  }, [sourceId]);

  // Start with a sensible output size that preserves the source aspect ratio.
  useEffect(() => {
    if (!source || sizedSource.current === source.id) return;
    sizedSource.current = source.id;
    const scale = 128 / Math.max(source.width, source.height);
    setOptions((o) => ({
      ...o,
      width: Math.max(16, Math.round(source.width * scale)),
      height: Math.max(16, Math.round(source.height * scale)),
    }));
    setDirty(true);
  }, [source]);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, []);

  const info = preview?.info || {};
  const usedPalette: string[] = info.palette || [];

  const set = <K extends keyof PixelOptions>(key: K, value: PixelOptions[K]) => {
    setOptions((o) => ({ ...o, [key]: value }));
    setDirty(true);
  };

  const setSize = (key: "width" | "height", value: number) => {
    setOptions((o) => {
      if (!lockRatio || !source) return { ...o, [key]: value };
      const ratio = source.width / source.height;
      if (key === "width") return { ...o, width: value, height: Math.max(8, Math.round(value / ratio)) };
      return { ...o, height: value, width: Math.max(8, Math.round(value * ratio)) };
    });
    setDirty(true);
  };

  const applyPreset = (name: string) => {
    const preset = PRESETS[name];
    if (!preset) return;
    setOptions((o) => ({ ...o, ...preset }));
    setDirty(true);
    notify(`Preset “${name}” applied`, "info");
  };

  const upload = async (file: File) => {
    try {
      const project = await ensureProject();
      const asset = await api.uploadAsset(project, file, "source", file.name.replace(/\.[^.]+$/, ""));
      await refreshAssets();
      setSourceId(asset.id);
      notify(`Imported ${asset.name}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const buildOptions = () => {
    const custom = customPalette
      .split(/[,\s]+/)
      .map((c) => c.trim())
      .filter((c) => /^#?[0-9a-f]{3,8}$/i.test(c))
      .map((c) => (c.startsWith("#") ? c : `#${c}`));
    const payload: Record<string, any> = { ...options };
    payload.palette_colors = custom.length >= 2 ? custom : [];
    return payload;
  };

  const processImage = async () => {
    if (!projectId || !sourceId) {
      notify("Select or import a source image first", "error");
      return;
    }
    if (processing) return;
    if (pollRef.current) window.clearTimeout(pollRef.current);
    setProcessing(true);
    setProgress(0);
    setPhase("Queued");
    setViewMode("source");
    try {
      const { job_id } = await api.pixelPreviewJob({
        project_id: projectId,
        asset_id: sourceId,
        options: buildOptions(),
      });

      const poll = async () => {
        try {
          const job = await api.job(job_id);
          setProgress(job.progress);
          setPhase(job.message || "");
          if (job.status === "done") {
            const result = job.result as PreviewResult | null | undefined;
            if (result && result.url) {
              setPreview(result);
              setViewMode("result");
              setDirty(false);
              setProgress(100);
              notify("Pixel art generated", "success");
            } else {
              notify("Processing finished without a preview", "error");
            }
            setProcessing(false);
            return;
          }
          if (job.status === "error" || job.status === "cancelled") {
            setProcessing(false);
            notify(job.error || "Processing failed", "error");
            return;
          }
          pollRef.current = window.setTimeout(poll, 160);
        } catch (err) {
          setProcessing(false);
          notify(errorText(err), "error");
        }
      };

      pollRef.current = window.setTimeout(poll, 120);
    } catch (err) {
      setProcessing(false);
      notify(errorText(err), "error");
    }
  };

  const exportArt = async () => {
    if (!projectId || !sourceId) return;
    setExporting(true);
    try {
      const payload: Record<string, any> = { ...options };
      const custom = customPalette
        .split(/[,\s]+/)
        .map((c) => c.trim())
        .filter((c) => /^#?[0-9a-f]{3,8}$/i.test(c))
        .map((c) => (c.startsWith("#") ? c : `#${c}`));
      payload.palette_colors = custom.length >= 2 ? custom : [];
      const res = await api.pixelExport({
        project_id: projectId,
        asset_id: sourceId,
        options: payload,
        name: `${source?.name || "Image"} pixel art`,
      });
      await refreshAssets();
      notify(`Saved ${res.asset.name} · ${res.info.colors_used} colors`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setExporting(false);
    }
  };

  const showingResult = Boolean(preview && viewMode === "result");
  const stageUrl = showingResult ? preview!.url : source?.url || "";

  if (tab === "workspace") {
    return (
      <Localize>
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex items-center gap-2 border-b border-ink-700/70 px-3 py-2">
          <Segmented
            value={tab}
            onChange={(v) => setTab(v)}
            options={[
              { value: "convert", label: "Convert" },
              { value: "workspace", label: "Workspace" },
            ]}
          />
          <span className="text-[10.5px] text-ink-500">Layer composition with undo/redo and pixel export</span>
        </div>
        <Workspace />
      </div>
      </Localize>
    );
  }

  return (
    <Localize>
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-ink-700/70 px-3 py-2">
        <Segmented
          value={tab}
          onChange={(v) => setTab(v)}
          options={[
            { value: "convert", label: "Convert" },
            { value: "workspace", label: "Workspace" },
          ]}
        />
        <span className="text-[10.5px] text-ink-500">
          {processing
            ? `Processing ${progress}%${phase ? ` · ${phase}` : ""}`
            : dirty
              ? "Changes not processed yet"
              : preview
                ? "Result ready"
                : "Ready to process"}
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          {preview && (
            <Segmented
              size="sm"
              value={viewMode}
              onChange={setViewMode}
              options={[
                { value: "result", label: "Result" },
                { value: "source", label: "Source" },
              ]}
            />
          )}
          <button
            type="button"
            className="btn-primary"
            onClick={() => void processImage()}
            disabled={!sourceId || processing}
            title="Process the selected image on the CPU"
          >
            <Icon name="spark" size={14} />
            {processing ? `Processing ${progress}%` : "Process"}
          </button>
        </div>
      </div>
      {processing && (
        <div className="flex items-center gap-2 border-b border-ink-700/70 bg-ink-900/60 px-3 py-1.5">
          <div className="flex-1">
            <ProgressBar value={progress} />
          </div>
          <span className="w-[42px] text-right font-mono text-[10.5px] text-ink-300">{progress}%</span>
          <span className="min-w-[110px] text-[10.5px] text-ink-500">{phase || "Processing…"}</span>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr_268px]">
        <div className="min-h-0 overflow-y-auto border-r border-ink-700/70 p-3 space-y-3">
          <div className="space-y-1.5">
            <AssetPicker assets={assets} value={sourceId} onChange={setSourceId} label="Source image" />
            <DropZone onFile={(f) => void upload(f)} compact hint="Import into this project" />
          </div>

          <div className="space-y-1.5">
            <p className="label">Presets</p>
            <div className="flex flex-wrap gap-1">
              {Object.keys(PRESETS).map((p) => (
                <button key={p} type="button" className="chip hover:border-[rgb(var(--accent))] hover:text-ink-100" onClick={() => applyPreset(p)}>
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <label className="block space-y-1">
              <span className="text-[11px] text-ink-300">Width</span>
              <input type="number" className="field" min={8} max={1024} value={options.width} onChange={(e) => setSize("width", Number(e.target.value) || 8)} />
            </label>
            <label className="block space-y-1">
              <span className="text-[11px] text-ink-300">Height</span>
              <input type="number" className="field" min={8} max={1024} value={options.height} onChange={(e) => setSize("height", Number(e.target.value) || 8)} />
            </label>
          </div>
          <Toggle label="Lock source aspect ratio" checked={lockRatio} onChange={setLockRatio} />
          <Slider label="Block size" value={options.block_size} min={1} max={16} onChange={(v) => set("block_size", v)} suffix=" px" />

          <Select
            label="Resize method"
            value={options.resize_method}
            onChange={(v) => set("resize_method", v)}
            options={[
              { value: "lanczos", label: "Lanczos (sharp)" },
              { value: "bicubic", label: "Bicubic" },
              { value: "bilinear", label: "Bilinear" },
              { value: "nearest", label: "Nearest (hard edges)" },
            ]}
          />

          <Select
            label="Quantizer"
            value={options.quantizer}
            onChange={(v) => set("quantizer", v)}
            options={[
              { value: "median_cut", label: "Median cut" },
              { value: "octree", label: "Octree" },
              { value: "kmeans", label: "K-Means (seeded)" },
              { value: "adaptive", label: "Adaptive" },
            ]}
          />
          <Slider label="Colors" value={options.colors} min={2} max={256} onChange={(v) => set("colors", v)} />

          <Select
            label="Palette lock"
            value={options.palette_id}
            onChange={(v) => set("palette_id", v)}
            options={[
              { value: "", label: "Free (quantizer palette)" },
              ...palettes.map((p: Palette) => ({ value: p.id, label: `${p.name} · ${p.colors.length}` })),
            ]}
          />
          <label className="block space-y-1">
            <span className="text-[11px] text-ink-300">Custom palette (hex, comma separated)</span>
            <input
              className="field font-mono !text-[11px]"
              placeholder="#0f380f, #306230, #8bac0f"
              value={customPalette}
              onChange={(e) => setCustomPalette(e.target.value)}
            />
          </label>

          <Select
            label="Dithering"
            value={options.dither}
            onChange={(v) => set("dither", v)}
            options={[
              { value: "none", label: "None" },
              { value: "floyd", label: "Floyd–Steinberg" },
              { value: "atkinson", label: "Atkinson" },
              { value: "jjn", label: "Jarvis–Judice–Ninke" },
              { value: "bayer", label: "Ordered Bayer 8×8" },
            ]}
          />
          {options.dither !== "none" && (
            <Slider label="Dither strength" value={Math.round(options.dither_strength * 100)} min={5} max={100} onChange={(v) => set("dither_strength", v / 100)} suffix="%" />
          )}

          <div className="space-y-2 border-t border-ink-700/70 pt-2">
            <p className="label">Adjustments</p>
            <Slider label="Brightness" value={Math.round(options.brightness * 100)} min={20} max={200} onChange={(v) => set("brightness", v / 100)} suffix="%" />
            <Slider label="Contrast" value={Math.round(options.contrast * 100)} min={20} max={200} onChange={(v) => set("contrast", v / 100)} suffix="%" />
            <Slider label="Saturation" value={Math.round(options.saturation * 100)} min={0} max={200} onChange={(v) => set("saturation", v / 100)} suffix="%" />
            <Slider label="Denoise" value={options.denoise} min={0} max={3} onChange={(v) => set("denoise", v)} />
            <Slider label="Edge preserve" value={options.edge_preserve} min={0} max={100} onChange={(v) => set("edge_preserve", v)} />
            <Slider label="Edge enhance" value={options.edge_enhance} min={0} max={100} onChange={(v) => set("edge_enhance", v)} />
          </div>

          <div className="space-y-2 border-t border-ink-700/70 pt-2">
            <Toggle label="Transparent background" checked={options.transparent} onChange={(v) => set("transparent", v)} hint="Uses the selected color or auto corner color" />
            {options.transparent && (
              <>
                <label className="flex items-center justify-between gap-2 text-[11px] text-ink-300">
                  Background color
                  <input type="color" value={options.bg_color} onChange={(e) => set("bg_color", e.target.value)} className="h-6 w-10" />
                </label>
                <Slider label="Tolerance" value={options.bg_tolerance} min={0} max={200} onChange={(v) => set("bg_tolerance", v)} />
              </>
            )}
            <Toggle label="Pixel grid alignment" checked={options.pixel_grid} onChange={(v) => set("pixel_grid", v)} hint="Snap output to block multiples" />
          </div>
        </div>

        <div className="min-h-0 p-3">
          {source ? (
            <div className="relative h-full">
              <ImageStage src={stageUrl} gridSize={1} alt="Pixel art preview" onReady={() => undefined} className="h-full" />
              <span className="pointer-events-none absolute left-3 top-3 z-10 rounded-md border border-ink-600 bg-ink-900/90 px-2 py-0.5 text-[10px] uppercase tracking-wide text-ink-300">
                {showingResult ? "Result" : "Source"}
              </span>
              {processing && (
                <div className="pointer-events-none absolute inset-0 z-20 grid place-items-center bg-black/30">
                  <div className="panel w-[240px] px-4 py-3">
                    <div className="mb-1.5 flex items-center justify-between text-[11px]">
                      <span className="text-ink-200">Processing…</span>
                      <span className="font-mono text-ink-300">{progress}%</span>
                    </div>
                    <ProgressBar value={progress} />
                    <p className="mt-1 truncate text-[10px] text-ink-500">{phase || "Working on the CPU"}</p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <Empty icon={<Icon name="pixel" size={24} />} title="Select or import a source image" hint="Import an image from the top bar or drop one in the left panel." />
          )}
        </div>

        <div className="min-h-0 space-y-3 overflow-y-auto border-l border-ink-700/70 p-3">
          <Panel title="Output" bodyClass="p-3">
            {processing && (
              <div className="mb-2 space-y-1 rounded border border-ink-700 bg-ink-900 p-2">
                <div className="flex items-center justify-between text-[10.5px]">
                  <span className="text-ink-300">{phase || "Processing…"}</span>
                  <span className="font-mono text-ink-400">{progress}%</span>
                </div>
                <ProgressBar value={progress} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded bg-ink-800/70 p-2">
                <p className="text-ink-500">Size</p>
                <p className="font-mono text-ink-100">{info.width ?? "–"}×{info.height ?? "–"}</p>
              </div>
              <div className="rounded bg-ink-800/70 p-2">
                <p className="text-ink-500">Colors</p>
                <p className="font-mono text-ink-100">{info.colors_used ?? "–"}</p>
              </div>
              <div className="rounded bg-ink-800/70 p-2">
                <p className="text-ink-500">Work grid</p>
                <p className="font-mono text-ink-100">{info.work_width ?? "–"}×{info.work_height ?? "–"}</p>
              </div>
              <div className="rounded bg-ink-800/70 p-2">
                <p className="text-ink-500">Time</p>
                <p className="font-mono text-ink-100">{info.duration_ms ? `${Math.round(info.duration_ms)} ms` : "–"}</p>
              </div>
            </div>
            <button type="button" className="btn-primary mt-2 w-full" onClick={() => void exportArt()} disabled={!preview || exporting || processing}>
              <Icon name="save" size={14} /> {exporting ? "Saving…" : "Save as asset"}
            </button>
            {!preview && !processing && (
              <p className="mt-2 text-[10.5px] leading-relaxed text-ink-500">Choose the options and press Process to generate the preview.</p>
            )}
            {preview && (
              <a className="btn-ghost mt-1.5 w-full" href={preview.url} download="pixel-art.png">
                <Icon name="download" size={14} /> Download PNG
              </a>
            )}
          </Panel>

          <Panel title={`Palette (${usedPalette.length})`} bodyClass="p-3">
            {usedPalette.length === 0 ? (
              <p className="text-[11px] text-ink-500">Palette appears after the first preview.</p>
            ) : (
              <div className="grid grid-cols-8 gap-1">
                {usedPalette.map((c) => (
                  <span key={c} title={c} className="aspect-square rounded border border-black/40" style={{ background: c }} />
                ))}
              </div>
            )}
            <p className="mt-2 text-[10px] leading-relaxed text-ink-500">
              Quantizer: {String(info.quantizer ?? "–")} · dither: {String(info.dither ?? "–")}
            </p>
          </Panel>

          <Panel title="Source" bodyClass="p-3">
            {source ? (
              <div className="space-y-1 text-[11px]">
                <p className="truncate text-ink-100">{source.name}</p>
                <p className="text-ink-500">
                  {source.width}×{source.height} · {bytes(source.size_bytes)}
                </p>
                {source.src_url && (
                  <a className="text-[10.5px] text-[rgb(var(--accent))] hover:underline" href={source.src_url} target="_blank" rel="noreferrer">
                    Original file
                  </a>
                )}
              </div>
            ) : (
              <p className="text-[11px] text-ink-500">No source selected.</p>
            )}
          </Panel>
        </div>
      </div>
      {preview?.cached && <span className="sr-only">cached preview</span>}
    </div>
    </Localize>
  );
}
