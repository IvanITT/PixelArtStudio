import { useEffect, useMemo, useState } from "react";
import { api, errorText, mediaUrl } from "../api/client";
import type { TerrainInfo, TileExtraction } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { AssetPicker, DropZone } from "../components/AssetPicker";
import { ImageStage } from "../components/ImageStage";
import { Icon } from "../components/Icon";
import { Empty, Panel, Segmented, Slider, Spinner, Toggle } from "../components/ui";

type Mode = "extract" | "terrain" | "tools";

export function Tileset() {
  const projectId = useStudio((s) => s.projectId);
  const lastImported = useStudio((s) => s.lastImported);
  const assets = useStudio((s) => s.assets);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const ensureProject = useStudio((s) => s.ensureProject);
  const notify = useStudio((s) => s.notify);

  useEffect(() => {
    if (lastImported && lastImported.project_id === projectId) setSourceId(lastImported.id);
  }, [lastImported, projectId]);

  const [mode, setMode] = useState<Mode>("extract");
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [tileSize, setTileSize] = useState(16);
  const [margin, setMargin] = useState(0);
  const [spacing, setSpacing] = useState(0);
  const [offsetX, setOffsetX] = useState(0);
  const [offsetY, setOffsetY] = useState(0);
  const [removeEmpty, setRemoveEmpty] = useState(true);
  const [detectDups, setDetectDups] = useState(true);
  const [sort, setSort] = useState("grid");
  const [result, setResult] = useState<TileExtraction | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [columns, setColumns] = useState(8);
  const [spacingOut, setSpacingOut] = useState(0);
  const [paddingOut, setPaddingOut] = useState(0);
  const [recolorHue, setRecolorHue] = useState(0);
  const [recolorSat, setRecolorSat] = useState(100);
  const [recolorBri, setRecolorBri] = useState(100);
  const [variationKind, setVariationKind] = useState("");

  const [terrains, setTerrains] = useState<TerrainInfo[]>([]);
  const [terrainId, setTerrainId] = useState("grass");
  const [terrainSize, setTerrainSize] = useState(16);
  const [seed, setSeed] = useState(1337);
  const [variations, setVariations] = useState(1);
  const [terrainResult, setTerrainResult] = useState<{ preview_url: string; tiles: { mask: number; url: string }[]; asset: any } | null>(null);
  const [terrainBusy, setTerrainBusy] = useState(false);

  const [bandRatio, setBandRatio] = useState(12);
  const [seamlessResult, setSeamlessResult] = useState<{ url: string; before: number; after: number } | null>(null);
  const [recolorResult, setRecolorResult] = useState<string | null>(null);
  const [toolBusy, setToolBusy] = useState(false);

  useEffect(() => {
    api
      .tilesetTerrains()
      .then(setTerrains)
      .catch(() => undefined);
  }, []);

  const options = useMemo(
    () => ({
      tile_size: tileSize,
      margin,
      spacing,
      offset_x: offsetX,
      offset_y: offsetY,
      remove_empty: removeEmpty,
      detect_duplicates: detectDups,
      sort,
      max_tiles: 4096,
    }),
    [tileSize, margin, spacing, offsetX, offsetY, removeEmpty, detectDups, sort],
  );

  const upload = async (file: File) => {
    try {
      const project = await ensureProject();
      const asset = await api.uploadAsset(project, file, "source", file.name.replace(/\.[^.]+$/, ""));
      await refreshAssets();
      setSourceId(asset.id);
      notify("Tileset source imported", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const runExtract = async () => {
    if (!projectId || !sourceId) return;
    setBusy(true);
    try {
      const res = await api.extractTiles({ project_id: projectId, asset_id: sourceId, options });
      setResult(res);
      setSelected(new Set(res.tiles.map((t) => t.index)));
      notify(`${res.total} tiles${res.truncated ? " (preview truncated)" : ""} · ${res.duplicates} duplicates`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const saveTileset = async () => {
    if (!projectId || !sourceId) return;
    try {
      const body: Record<string, any> = {
        project_id: projectId,
        asset_id: sourceId,
        options,
        selected: Array.from(selected),
        columns,
        spacing: spacingOut,
        padding: paddingOut,
        name: `${assets.find((a) => a.id === sourceId)?.name || "Tiles"} tileset`,
      };
      if (recolorHue || recolorSat !== 100 || recolorBri !== 100) {
        body.recolor = { hue: recolorHue, saturation: recolorSat / 100, brightness: recolorBri / 100 };
      }
      if (variationKind) body.variation = variationKind;
      const res = await api.saveTileset(body);
      await refreshAssets();
      notify(`Saved ${res.asset.name}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const generateTerrain = async () => {
    if (!projectId) return;
    setTerrainBusy(true);
    try {
      const res = await api.terrain({
        project_id: projectId,
        terrain: terrainId,
        tile_size: terrainSize,
        seed,
        variations,
        name: `${terrainId} autotile ${terrainSize}px`,
      });
      setTerrainResult(res as any);
      await refreshAssets();
      notify(`Generated ${terrainId} autotile set with ${res.tiles.length} masks`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setTerrainBusy(false);
    }
  };

  const runSeamless = async () => {
    if (!projectId || !sourceId) return;
    setToolBusy(true);
    try {
      const res = await api.seamless({ project_id: projectId, asset_id: sourceId, band_ratio: bandRatio / 100, save: true });
      setSeamlessResult({ url: res.url, before: res.seam_error_before, after: res.seam_error_after });
      await refreshAssets();
      notify(`Seam error ${res.seam_error_before} → ${res.seam_error_after}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setToolBusy(false);
    }
  };

  const runRecolor = async () => {
    if (!projectId || !sourceId) return;
    setToolBusy(true);
    try {
      const res = await api.recolor({
        project_id: projectId,
        asset_id: sourceId,
        hue: recolorHue,
        saturation: recolorSat / 100,
        brightness: recolorBri / 100,
        save: true,
        name: `${assets.find((a) => a.id === sourceId)?.name || "Tile"} recolored`,
      });
      setRecolorResult(res.url);
      await refreshAssets();
      notify("Recolored variant saved", "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setToolBusy(false);
    }
  };

  const toggle = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <Localize>
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-ink-700/70 px-3 py-2">
        <Segmented
          value={mode}
          onChange={setMode}
          options={[
            { value: "extract", label: "Grid extract" },
            { value: "terrain", label: "Autotile terrain" },
            { value: "tools", label: "Seamless & recolor" },
          ]}
        />
        <span className="text-[10.5px] text-ink-500">
          {mode === "extract" ? "Cut uniform grids, detect duplicates, export a tileset" : mode === "terrain" ? "16-bit autotile masks from 31 procedural ramps" : "Edge blending and palette shifts"}
        </span>
      </div>

      {mode === "extract" && (
        <div className="grid min-h-0 flex-1 grid-cols-[288px_1fr_262px]">
          <div className="min-h-0 space-y-2 overflow-y-auto border-r border-ink-700/70 p-3">
            <AssetPicker assets={assets} value={sourceId} onChange={setSourceId} label="Tileset image" />
            <DropZone onFile={(f) => void upload(f)} compact />
            <Panel title="Grid" bodyClass="p-3 space-y-2.5">
              <Slider label="Tile size" value={tileSize} min={4} max={128} step={4} onChange={setTileSize} suffix=" px" />
              <Slider label="Margin" value={margin} min={0} max={64} onChange={setMargin} suffix=" px" />
              <Slider label="Spacing" value={spacing} min={0} max={64} onChange={setSpacing} suffix=" px" />
              <div className="grid grid-cols-2 gap-2">
                <Slider label="Offset X" value={offsetX} min={0} max={128} onChange={setOffsetX} />
                <Slider label="Offset Y" value={offsetY} min={0} max={128} onChange={setOffsetY} />
              </div>
              <Toggle label="Remove empty tiles" checked={removeEmpty} onChange={setRemoveEmpty} />
              <Toggle label="Detect duplicates" checked={detectDups} onChange={setDetectDups} />
              <Segmented
                size="sm"
                value={sort}
                onChange={setSort}
                options={[
                  { value: "grid", label: "Grid" },
                  { value: "hue", label: "Hue" },
                  { value: "brightness", label: "Luma" },
                ]}
              />
              <button className="btn-primary w-full" onClick={() => void runExtract()} disabled={busy || !sourceId}>
                <Icon name="grid" size={14} /> {busy ? "Slicing…" : "Extract tiles"}
              </button>
            </Panel>
          </div>

          <div className="min-h-0 overflow-y-auto p-3">
            {busy && <Spinner label="Slicing grid" />}
            {!result && !busy && (
              <Empty icon={<Icon name="tileset" size={24} />} title="No tiles yet" hint="Choose an image and grid, then extract. Every tile keeps its source coordinates and duplicate hash." />
            )}
            {result && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-[11px]">
                  <span className="font-medium text-ink-100">{result.total} tiles</span>
                  <span className="chip">{result.tile_size}px</span>
                  <span className="chip">{result.duplicates} exact dupes</span>
                  <span className="chip">{result.near_duplicates} near dupes</span>
                  {result.truncated && <span className="text-amber-400">preview truncated to {result.shown}</span>}
                  <div className="ml-auto flex gap-1">
                    <button className="btn-ghost !py-1" onClick={() => setSelected(new Set(result.tiles.map((t) => t.index)))}>
                      All
                    </button>
                    <button className="btn-ghost !py-1" onClick={() => setSelected(new Set())}>
                      None
                    </button>
                  </div>
                </div>
                <Panel title="Extracted sheet" bodyClass="p-2">
                  <div className="checker grid max-h-[240px] place-items-center overflow-auto rounded border border-ink-700">
                    <img src={mediaUrl(result.sheet_url)} alt="extracted tiles" className="max-h-[232px] object-contain pixelated" />
                  </div>
                </Panel>
                <div className="grid grid-cols-[repeat(auto-fill,minmax(64px,1fr))] gap-1.5">
                  {result.tiles.map((t) => {
                    const active = selected.has(t.index);
                    return (
                      <button
                        key={t.index}
                        type="button"
                        onClick={() => toggle(t.index)}
                        title={`#${t.index} · ${t.source_x},${t.source_y}${t.duplicate_of !== null ? ` · dup of #${t.duplicate_of}` : ""}`}
                        className={`relative overflow-hidden rounded border p-1 transition ${
                          active ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/10" : "border-ink-700 bg-ink-900 hover:border-ink-600"
                        }`}
                      >
                        <div className="checker grid h-[52px] place-items-center overflow-hidden rounded-sm">
                          <img src={mediaUrl(t.url)} alt={`tile ${t.index}`} className="max-h-[50px] max-w-full object-contain pixelated" loading="lazy" />
                        </div>
                        <span className="mt-0.5 block text-center font-mono text-[8.5px] text-ink-500">{t.index}</span>
                        {t.duplicate_of !== null && (
                          <span className="absolute right-0.5 top-0.5 rounded bg-amber-500/80 px-1 text-[7.5px] text-black">D</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="min-h-0 space-y-2 overflow-y-auto border-l border-ink-700/70 p-3">
            <Panel title="Export tileset" bodyClass="p-3 space-y-2.5">
              <div className="grid grid-cols-3 gap-1.5">
                <label className="space-y-0.5">
                  <span className="text-[10px] text-ink-400">Columns</span>
                  <input type="number" min={1} max={64} className="field !py-1" value={columns} onChange={(e) => setColumns(Number(e.target.value) || 1)} />
                </label>
                <label className="space-y-0.5">
                  <span className="text-[10px] text-ink-400">Gap</span>
                  <input type="number" min={0} max={32} className="field !py-1" value={spacingOut} onChange={(e) => setSpacingOut(Number(e.target.value) || 0)} />
                </label>
                <label className="space-y-0.5">
                  <span className="text-[10px] text-ink-400">Pad</span>
                  <input type="number" min={0} max={32} className="field !py-1" value={paddingOut} onChange={(e) => setPaddingOut(Number(e.target.value) || 0)} />
                </label>
              </div>
              <p className="text-[10px] text-ink-500">{selected.size} tiles selected</p>
              <button className="btn-primary w-full" onClick={() => void saveTileset()} disabled={selected.size === 0 || !sourceId}>
                <Icon name="save" size={13} /> Save tileset asset
              </button>
            </Panel>

            <Panel title="Recolor variant" bodyClass="p-3 space-y-2">
              <Slider label="Hue shift" value={recolorHue} min={-180} max={180} onChange={setRecolorHue} suffix="°" />
              <Slider label="Saturation" value={recolorSat} min={0} max={200} onChange={setRecolorSat} suffix="%" />
              <Slider label="Brightness" value={recolorBri} min={20} max={200} onChange={setRecolorBri} suffix="%" />
              <Segmented
                size="sm"
                value={variationKind}
                onChange={setVariationKind}
                options={[
                  { value: "", label: "None" },
                  { value: "flip_h", label: "Flip H" },
                  { value: "flip_v", label: "Flip V" },
                  { value: "rotate", label: "Rotate" },
                ]}
              />
            </Panel>
          </div>
        </div>
      )}

      {mode === "terrain" && (
        <div className="grid min-h-0 flex-1 grid-cols-[272px_1fr]">
          <div className="min-h-0 space-y-2 overflow-y-auto border-r border-ink-700/70 p-3">
            <Panel title="Terrain" bodyClass="p-2">
              <div className="grid grid-cols-2 gap-1">
                {terrains.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTerrainId(t.id)}
                    className={`rounded-md border p-1.5 text-left transition ${
                      terrainId === t.id ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/10" : "border-ink-700 bg-ink-900 hover:border-ink-600"
                    }`}
                  >
                    <span className="flex gap-0.5">
                      {t.palette.slice(0, 5).map((c, i) => (
                        <span key={i} className="h-3 w-3 rounded-sm border border-black/40" style={{ background: c }} />
                      ))}
                    </span>
                    <span className="mt-1 block text-[10.5px] text-ink-200">{t.name}</span>
                  </button>
                ))}
              </div>
            </Panel>
            <Panel title="Parameters" bodyClass="p-3 space-y-2.5">
              <Slider label="Tile size" value={terrainSize} min={8} max={64} step={8} onChange={setTerrainSize} suffix=" px" />
              <Slider label="Seed" value={seed} min={1} max={9999} onChange={setSeed} />
              <Slider label="Variations" value={variations} min={1} max={6} onChange={setVariations} />
              <button className="btn-primary w-full" onClick={() => void generateTerrain()} disabled={terrainBusy}>
                <Icon name="spark" size={14} /> {terrainBusy ? "Generating…" : "Generate autotiles"}
              </button>
              <p className="text-[10px] leading-relaxed text-ink-500">
                Produces 16 neighbour masks × variations with a deterministic seed, saved as a tileset asset with full autotile metadata.
              </p>
            </Panel>
          </div>
          <div className="min-h-0 overflow-y-auto p-3">
            {terrainBusy && <Spinner label="Painting terrain" />}
            {!terrainResult && !terrainBusy && (
              <Empty icon={<Icon name="tileset" size={24} />} title="Pick a terrain" hint="Generate a ready-to-use 16-mask autotile sheet for grass, stone, water and more." />
            )}
            {terrainResult && (
              <div className="space-y-3">
                <Panel title="Autotile preview" bodyClass="p-2">
                  <ImageStage src={terrainResult.preview_url} className="h-[260px]" />
                </Panel>
                <Panel title="Mask gallery (16)" bodyClass="p-2">
                  <div className="grid grid-cols-8 gap-1.5">
                    {terrainResult.tiles.map((t) => (
                      <div key={t.mask} className="rounded border border-ink-700 bg-ink-900 p-1 text-center">
                        <div className="checker grid h-12 place-items-center">
                          <img src={mediaUrl(t.url)} alt={`mask ${t.mask}`} className="max-h-12 w-full object-contain pixelated" />
                        </div>
                        <span className="font-mono text-[8.5px] text-ink-500">{t.mask.toString(2).padStart(4, "0")}</span>
                      </div>
                    ))}
                  </div>
                </Panel>
              </div>
            )}
          </div>
        </div>
      )}

      {mode === "tools" && (
        <div className="grid min-h-0 flex-1 grid-cols-[288px_1fr]">
          <div className="min-h-0 space-y-2 overflow-y-auto border-r border-ink-700/70 p-3">
            <AssetPicker assets={assets} value={sourceId} onChange={setSourceId} label="Tile or texture" />
            <Panel title="Seamless blend" bodyClass="p-3 space-y-2">
              <Slider label="Edge band" value={bandRatio} min={2} max={40} onChange={setBandRatio} suffix="%" />
              <button className="btn-primary w-full" onClick={() => void runSeamless()} disabled={toolBusy || !sourceId}>
                <Icon name="refresh" size={13} /> Make seamless
              </button>
              {seamlessResult && (
                <p className="font-mono text-[10px] text-ink-400">
                  error {seamlessResult.before.toFixed(2)} → {seamlessResult.after.toFixed(2)}
                </p>
              )}
            </Panel>
            <Panel title="Recolor" bodyClass="p-3 space-y-2">
              <Slider label="Hue" value={recolorHue} min={-180} max={180} onChange={setRecolorHue} suffix="°" />
              <Slider label="Saturation" value={recolorSat} min={0} max={200} onChange={setRecolorSat} suffix="%" />
              <Slider label="Brightness" value={recolorBri} min={20} max={200} onChange={setRecolorBri} suffix="%" />
              <button className="btn-ghost w-full" onClick={() => void runRecolor()} disabled={toolBusy || !sourceId}>
                <Icon name="spark" size={13} /> Recolor & save
              </button>
            </Panel>
          </div>
          <div className="min-h-0 overflow-y-auto p-3">
            {toolBusy && <Spinner label="Processing tile" />}
            {!seamlessResult && !recolorResult && !toolBusy && (
              <Empty icon={<Icon name="tileset" size={24} />} title="Tile finishing tools" hint="Blend opposing edges for seamless tiling or generate recolored variants of an existing tile." />
            )}
            <div className="grid gap-3 md:grid-cols-2">
              {seamlessResult && (
                <Panel title="Seamless result" bodyClass="p-2">
                  <ImageStage src={seamlessResult.url} className="h-[300px]" />
                </Panel>
              )}
              {recolorResult && (
                <Panel title="Recolor result" bodyClass="p-2">
                  <ImageStage src={recolorResult} className="h-[300px]" />
                </Panel>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
    </Localize>
  );
}
