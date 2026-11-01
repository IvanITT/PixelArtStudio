import { useEffect, useMemo, useState } from "react";
import { api, errorText, mediaUrl } from "../api/client";
import type { SpriteExtraction } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { AssetPicker, DropZone } from "../components/AssetPicker";
import { Icon } from "../components/Icon";
import { Empty, Panel, Segmented, Slider, Spinner, Toggle, bytes } from "../components/ui";

export function Sprites() {
  const projectId = useStudio((s) => s.projectId);
  const lastImported = useStudio((s) => s.lastImported);
  const assets = useStudio((s) => s.assets);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const ensureProject = useStudio((s) => s.ensureProject);
  const notify = useStudio((s) => s.notify);

  useEffect(() => {
    if (lastImported && lastImported.project_id === projectId) setSourceId(lastImported.id);
  }, [lastImported, projectId]);

  const [sourceId, setSourceId] = useState<string | null>(null);
  const [method, setMethod] = useState("auto_alpha");
  const [tolerance, setTolerance] = useState(28);
  const [mergeGap, setMergeGap] = useState(0);
  const [minArea, setMinArea] = useState(24);
  const [maxSprites, setMaxSprites] = useState(300);
  const [padding, setPadding] = useState(0);
  const [normalize, setNormalize] = useState(false);
  const [trim, setTrim] = useState(true);
  const [save, setSave] = useState(true);
  const [bgColor, setBgColor] = useState("#ffffff");
  const [targetColor, setTargetColor] = useState("#ff00ff");
  const [result, setResult] = useState<SpriteExtraction | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [packing, setPacking] = useState(false);
  const [packName, setPackName] = useState("Spritesheet");
  const [columns, setColumns] = useState(0);
  const [spacing, setSpacing] = useState(2);

  const spriteAssets = useMemo(() => assets.filter((a) => a.kind === "sprite"), [assets]);
  const selectedAssets = useMemo(
    () => (result?.sprites || []).filter((s) => selected.has(s.id)),
    [result, selected],
  );

  const options = useMemo(() => {
    const o: Record<string, any> = {
      method,
      tolerance,
      merge_gap: mergeGap,
      min_area: minArea,
      max_sprites: maxSprites,
      padding,
      normalize,
      normalize_size: 64,
      trim,
    };
    if (method === "bg_color") o.bg_color = bgColor;
    if (method === "color") {
      o.target_color = targetColor;
      o.color_mode = "keep";
    }
    return o;
  }, [method, tolerance, mergeGap, minArea, maxSprites, padding, normalize, trim, bgColor, targetColor]);

  const upload = async (file: File) => {
    try {
      const project = await ensureProject();
      const asset = await api.uploadAsset(project, file, "source", file.name.replace(/\.[^.]+$/, ""));
      await refreshAssets();
      setSourceId(asset.id);
      notify("Source imported", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const run = async () => {
    if (!projectId || !sourceId) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await api.extractSprites({ project_id: projectId, asset_id: sourceId, options, save, name_prefix: "sprite" });
      setResult(res);
      setSelected(new Set(res.sprites.map((s) => s.id)));
      if (save) await refreshAssets();
      notify(`Extracted ${res.count} sprite${res.count === 1 ? "" : "s"}${res.duplicates ? ` · ${res.duplicates} near-duplicates` : ""}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const pack = async () => {
    if (!projectId || selectedAssets.length === 0) return;
    setPacking(true);
    try {
      const ids = selectedAssets.map((s) => s.id).filter((id) => !id.startsWith("preview_"));
      if (ids.length === 0) {
        notify("Enable “Save sprites as assets” to pack a sheet", "error");
        setPacking(false);
        return;
      }
      const res = await api.packSprites({
        project_id: projectId,
        sprite_ids: ids,
        options: { columns, padding: 4, spacing, max_dim: 8192 },
        name: packName || "Spritesheet",
      });
      await refreshAssets();
      notify(`Packed ${res.asset.name} · ${res.sheet.size.w}×${res.sheet.size.h}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setPacking(false);
    }
  };

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <Localize>
    <div className="grid h-full min-h-0 grid-cols-[292px_1fr_272px]">
      <div className="min-h-0 space-y-2 overflow-y-auto border-r border-ink-700/70 p-3">
        <AssetPicker assets={assets} value={sourceId} onChange={setSourceId} label="Sprite sheet" />
        <DropZone onFile={(f) => void upload(f)} compact />

        <Panel title="Segmentation" bodyClass="p-3 space-y-2.5">
          <Segmented
            size="sm"
            value={method}
            onChange={setMethod}
            options={[
              { value: "auto_alpha", label: "Alpha" },
              { value: "bg_color", label: "BG color" },
              { value: "color", label: "Color" },
              { value: "threshold", label: "Threshold" },
            ]}
          />
          {method === "bg_color" && (
            <label className="flex items-center justify-between text-[11px] text-ink-300">
              Background
              <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="h-6 w-10" />
            </label>
          )}
          {method === "color" && (
            <label className="flex items-center justify-between text-[11px] text-ink-300">
              Target color
              <input type="color" value={targetColor} onChange={(e) => setTargetColor(e.target.value)} className="h-6 w-10" />
            </label>
          )}
          <Slider label="Tolerance" value={tolerance} min={1} max={180} onChange={setTolerance} />
          <Slider label="Merge gap" value={mergeGap} min={0} max={64} onChange={setMergeGap} suffix=" px" />
          <Slider label="Min area" value={minArea} min={1} max={5000} onChange={setMinArea} suffix=" px" />
          <Slider label="Max sprites" value={maxSprites} min={1} max={2000} step={10} onChange={setMaxSprites} />
          <Slider label="Padding" value={padding} min={0} max={64} onChange={setPadding} />
          <Toggle label="Trim transparent edges" checked={trim} onChange={setTrim} />
          <Toggle label="Normalize to 64×64" checked={normalize} onChange={setNormalize} />
          <Toggle label="Save sprites as assets" checked={save} onChange={setSave} hint="Required to pack into a sheet" />
          <button className="btn-primary w-full" onClick={() => void run()} disabled={busy || !sourceId}>
            <Icon name="spark" size={14} /> {busy ? "Extracting…" : "Extract sprites"}
          </button>
        </Panel>

        <Panel title="Pack sheet" bodyClass="p-3 space-y-2">
          <label className="block space-y-1">
            <span className="text-[11px] text-ink-300">Sheet name</span>
            <input className="field" value={packName} onChange={(e) => setPackName(e.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block space-y-1">
              <span className="text-[11px] text-ink-300">Columns</span>
              <input type="number" min={0} max={64} className="field" value={columns} onChange={(e) => setColumns(Number(e.target.value) || 0)} />
            </label>
            <label className="block space-y-1">
              <span className="text-[11px] text-ink-300">Spacing</span>
              <input type="number" min={0} max={64} className="field" value={spacing} onChange={(e) => setSpacing(Number(e.target.value) || 0)} />
            </label>
          </div>
          <p className="text-[10px] text-ink-500">{selectedAssets.length} selected · auto columns when 0</p>
          <button className="btn-ghost w-full" onClick={() => void pack()} disabled={packing || selectedAssets.length === 0}>
            <Icon name="download" size={14} /> {packing ? "Packing…" : "Pack selected"}
          </button>
        </Panel>
      </div>

      <div className="min-h-0 overflow-y-auto p-3">
        {busy && <Spinner label="Segmenting on CPU" />}
        {!result && !busy && (
          <Empty
            icon={<Icon name="sprites" size={24} />}
            title="No extraction yet"
            hint="Pick a sprite sheet, tune segmentation and run extraction. Sprites are cropped, hashed and saved as real assets."
          />
        )}
        {result && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2">
              <span className="text-[12px] font-medium text-ink-100">{result.count} sprites</span>
              <span className="chip">{result.duplicates} duplicates</span>
              {result.background && (
                <span className="chip">
                  bg rgb({result.background.join(",")})
                </span>
              )}
              {result.warnings.map((w) => (
                <span key={w} className="text-[10.5px] text-amber-400">
                  {w}
                </span>
              ))}
              <div className="ml-auto flex gap-1">
                <button className="btn-ghost !py-1" onClick={() => setSelected(new Set(result.sprites.map((s) => s.id)))}>
                  Select all
                </button>
                <button className="btn-ghost !py-1" onClick={() => setSelected(new Set())}>
                  Clear
                </button>
              </div>
            </div>

            {result.cutout_url && (
              <Panel title="Segmentation cutout" bodyClass="p-2">
                <div className="checker grid max-h-[180px] place-items-center overflow-hidden rounded border border-ink-700">
                  <img src={mediaUrl(result.cutout_url)} alt="cutout" className="max-h-[172px] object-contain pixelated" />
                </div>
              </Panel>
            )}

            <div className="grid grid-cols-[repeat(auto-fill,minmax(112px,1fr))] gap-2">
              {result.sprites.map((s) => {
                const active = selected.has(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggle(s.id)}
                    className={`group overflow-hidden rounded-lg border text-left transition ${
                      active ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/10" : "border-ink-700 bg-ink-850 hover:border-ink-600"
                    }`}
                  >
                    <div className="checker grid h-[92px] place-items-center overflow-hidden">
                      <img src={mediaUrl(s.thumb_url || s.url)} alt={s.name} className="max-h-[86px] max-w-full object-contain pixelated" loading="lazy" />
                    </div>
                    <div className="flex items-center justify-between px-2 py-1">
                      <span className="truncate text-[10px] text-ink-200">{s.name}</span>
                      <span className="font-mono text-[9px] text-ink-500">
                        {s.width}×{s.height}
                      </span>
                    </div>
                    <div className="flex items-center justify-between px-2 pb-1.5 text-[9px] text-ink-500">
                      <span>{s.meta?.area ? `${s.meta.area} px` : s.kind}</span>
                      <Icon name={active ? "check" : "plus"} size={10} className={active ? "text-[rgb(var(--accent))]" : ""} />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 space-y-2 overflow-y-auto border-l border-ink-700/70 p-3">
        <Panel title="Session" bodyClass="p-3 space-y-1 text-[11px]">
          <div className="flex justify-between">
            <span className="text-ink-500">Sprites saved</span>
            <span className="font-mono text-ink-200">{spriteAssets.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">Selection</span>
            <span className="font-mono text-ink-200">{selectedAssets.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">Saved mode</span>
            <span className="font-mono text-ink-200">{save ? "assets" : "preview"}</span>
          </div>
          {result?.group && (
            <div className="flex justify-between">
              <span className="text-ink-500">Group</span>
              <span className="font-mono text-[10px] text-ink-300">{result.group}</span>
            </div>
          )}
        </Panel>

        <Panel title="Selected sprite" bodyClass="p-3">
          {selectedAssets[0] ? (
            <div className="space-y-2">
              <div className="checker grid h-[140px] place-items-center overflow-hidden rounded border border-ink-700">
                <img src={mediaUrl(selectedAssets[0].thumb_url || selectedAssets[0].url)} alt="" className="max-h-[132px] object-contain pixelated" />
              </div>
              <p className="truncate text-[11px] text-ink-100">{selectedAssets[0].name}</p>
              <p className="text-[10px] text-ink-500">
                {selectedAssets[0].width}×{selectedAssets[0].height} · {bytes(selectedAssets[0].size_bytes)}
              </p>
              {selectedAssets[0].meta?.bbox && (
                <p className="font-mono text-[10px] text-ink-400">bbox {JSON.stringify(selectedAssets[0].meta.bbox)}</p>
              )}
            </div>
          ) : (
            <p className="text-[10.5px] text-ink-500">Select a sprite to inspect its crop.</p>
          )}
        </Panel>

        <Panel title="Alpha at a glance" bodyClass="p-3">
          <p className="text-[10px] leading-relaxed text-ink-500">
            Extraction runs connected-components on the computed mask. Merge gap groups nearby parts, min area discards noise, and
            every sprite is hashed for near-duplicate detection.
          </p>
        </Panel>
      </div>
    </div>
    </Localize>
  );
}
