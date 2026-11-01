import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Konva from "konva";
import { api, errorText, mediaUrl } from "../api/client";
import type { WorkspaceLayer } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { AssetPicker } from "./AssetPicker";
import { Icon } from "./Icon";
import { Empty, Panel, Slider, Toggle, bytes } from "./ui";

const uid = () => Math.random().toString(36).slice(2, 9);

export function Workspace() {
  const projectId = useStudio((s) => s.projectId);
  const assets = useStudio((s) => s.assets);
  const project = useStudio((s) => s.project);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const notify = useStudio((s) => s.notify);

  const [layers, setLayers] = useState<WorkspaceLayer[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [past, setPast] = useState<WorkspaceLayer[][]>([]);
  const [future, setFuture] = useState<WorkspaceLayer[][]>([]);
  const [canvas, setCanvas] = useState({ width: 512, height: 512 });
  const [zoom, setZoom] = useState(1);
  const [grid, setGrid] = useState(true);
  const [addId, setAddId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [images, setImages] = useState<Record<string, HTMLImageElement>>({});
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  // Restore persisted layout for this project once.
  useEffect(() => {
    const ws = project?.state?.workspace;
    if (ws && Array.isArray(ws.layers) && ws.layers.length && layers.length === 0) {
      const restored: WorkspaceLayer[] = ws.layers
        .map((l: any) => {
          const asset = assets.find((a) => a.id === l.asset_id);
          if (!asset) return null;
          return {
            uid: uid(),
            asset_id: asset.id,
            name: asset.name,
            url: asset.url,
            width: asset.width,
            height: asset.height,
            x: Number(l.x) || 0,
            y: Number(l.y) || 0,
            scale: Number(l.scale) || 1,
            rotation: Number(l.rotation) || 0,
            opacity: Number(l.opacity ?? 1),
            visible: l.visible !== false,
          } as WorkspaceLayer;
        })
        .filter(Boolean) as WorkspaceLayer[];
      if (restored.length) setLayers(restored);
      if (ws.width) setCanvas({ width: ws.width, height: ws.height });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, assets.length]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // Load images for every layer.
  useEffect(() => {
    let alive = true;
    const missing = layers.filter((l) => !images[l.asset_id]);
    if (missing.length === 0) return;
    missing.forEach((l) => {
      const img = new window.Image();
      img.onload = () => {
        if (alive) setImages((m) => ({ ...m, [l.asset_id]: img }));
      };
      img.src = mediaUrl(l.url) + (l.url.includes("?") ? "&" : "?") + "v=" + l.asset_id;
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layers]);

  const view = useMemo(() => {
    if (!size.w || !size.h) return 1;
    return Math.min((size.w - 48) / canvas.width, (size.h - 48) / canvas.height) * zoom;
  }, [size, canvas, zoom]);

  const commit = useCallback(
    (next: WorkspaceLayer[]) => {
      setPast((p) => [...p.slice(-30), layers]);
      setFuture([]);
      setLayers(next);
    },
    [layers],
  );

  const update = (id: string, patch: Partial<WorkspaceLayer>, history = true) => {
    const next = layers.map((l) => (l.uid === id ? { ...l, ...patch } : l));
    if (history) commit(next);
    else setLayers(next);
  };

  const undo = useCallback(() => {
    setPast((p) => {
      if (!p.length) return p;
      const prev = p[p.length - 1];
      setFuture((f) => [...f, layers]);
      setLayers(prev);
      return p.slice(0, -1);
    });
  }, [layers]);

  const redo = useCallback(() => {
    setFuture((f) => {
      if (!f.length) return f;
      const next = f[f.length - 1];
      setPast((p) => [...p, layers]);
      setLayers(next);
      return f.slice(0, -1);
    });
  }, [layers]);

  useEffect(() => {
    const onUndo = () => undo();
    const onRedo = () => redo();
    window.addEventListener("pas:z", onUndo);
    window.addEventListener("pas:redo", onRedo);
    window.addEventListener("pas:y", onRedo);
    return () => {
      window.removeEventListener("pas:z", onUndo);
      window.removeEventListener("pas:redo", onRedo);
      window.removeEventListener("pas:y", onRedo);
    };
  }, [undo, redo]);

  // Render with Konva.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !size.w || !size.h) return;
    const stage = new Konva.Stage({ container, width: size.w, height: size.h });
    const layer = new Konva.Layer();
    stage.add(layer);
    const offsetX = (size.w - canvas.width * view) / 2;
    const offsetY = (size.h - canvas.height * view) / 2;
    const group = new Konva.Group({ x: offsetX, y: offsetY, scaleX: view, scaleY: view });
    layer.add(group);

    group.add(
      new Konva.Rect({
        x: 0,
        y: 0,
        width: canvas.width,
        height: canvas.height,
        fill: showSource ? "#000000" : "#1b2230",
        stroke: "#334155",
        strokeWidth: 1 / view,
        listening: false,
      }),
    );

    for (const l of layers) {
      const img = images[l.asset_id];
      if (!img || !l.visible) continue;
      const node = new Konva.Image({
        image: img,
        x: l.x,
        y: l.y,
        width: l.width * l.scale,
        height: l.height * l.scale,
        rotation: l.rotation,
        opacity: l.opacity,
        draggable: true,
        imageSmoothingEnabled: false,
        name: l.uid,
      });
      node.on("dragstart", () => {
        setSelected(l.uid);
      });
      node.on("dragend", () => {
        update(l.uid, { x: Math.round(node.x()), y: Math.round(node.y()) });
      });
      node.on("mousedown touchstart", () => setSelected(l.uid));
      group.add(node);
    }

    if (grid) {
      const stroke = "rgba(148,163,184,0.14)";
      const step = 16;
      for (let x = step; x < canvas.width; x += step) {
        group.add(new Konva.Line({ points: [x, 0, x, canvas.height], stroke, strokeWidth: 1 / view, listening: false }));
      }
      for (let y = step; y < canvas.height; y += step) {
        group.add(new Konva.Line({ points: [0, y, canvas.width, y], stroke, strokeWidth: 1 / view, listening: false }));
      }
    }

    // Selection outline.
    const sel = layers.find((l) => l.uid === selected);
    if (sel) {
      group.add(
        new Konva.Rect({
          x: sel.x,
          y: sel.y,
          width: sel.width * sel.scale,
          height: sel.height * sel.scale,
          stroke: "#8b5cf6",
          strokeWidth: 1.5 / view,
          dash: [6 / view, 4 / view],
          listening: false,
        }),
      );
    }

    layer.draw();
    return () => {
      stage.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layers, images, size, canvas, view, grid, selected, showSource]);

  const selectedLayer = layers.find((l) => l.uid === selected) || null;

  const addLayer = () => {
    if (!addId) return;
    const asset = assets.find((a) => a.id === addId);
    if (!asset) return;
    const next: WorkspaceLayer = {
      uid: uid(),
      asset_id: asset.id,
      name: asset.name,
      url: asset.url,
      width: asset.width,
      height: asset.height,
      x: Math.round((canvas.width - asset.width) / 2),
      y: Math.round((canvas.height - asset.height) / 2),
      scale: 1,
      rotation: 0,
      opacity: 1,
      visible: true,
    };
    commit([...layers, next]);
    setSelected(next.uid);
    setAddId(null);
  };

  const move = (dir: -1 | 1) => {
    if (!selectedLayer) return;
    const i = layers.findIndex((l) => l.uid === selectedLayer.uid);
    const j = i + dir;
    if (j < 0 || j >= layers.length) return;
    const next = [...layers];
    [next[i], next[j]] = [next[j], next[i]];
    commit(next);
  };

  const remove = () => {
    if (!selectedLayer) return;
    commit(layers.filter((l) => l.uid !== selectedLayer.uid));
    setSelected(null);
  };

  const duplicate = () => {
    if (!selectedLayer) return;
    const copy = { ...selectedLayer, uid: uid(), x: selectedLayer.x + 8, y: selectedLayer.y + 8 };
    commit([...layers, copy]);
    setSelected(copy.uid);
  };

  const saveLayout = async () => {
    if (!projectId) return;
    try {
      await api.updateProject(projectId, {
        state: {
          ...(project?.state || {}),
          workspace: {
            width: canvas.width,
            height: canvas.height,
            layers: layers.map((l) => ({
              asset_id: l.asset_id,
              x: l.x,
              y: l.y,
              scale: l.scale,
              rotation: l.rotation,
              opacity: l.opacity,
              visible: l.visible,
            })),
          },
        },
      });
      notify("Workspace layout saved to project", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const exportComposite = async () => {
    if (!projectId) return;
    if (layers.length === 0) {
      notify("Add at least one layer first", "error");
      return;
    }
    setExporting(true);
    try {
      const res = await api.workspaceExport({
        project_id: projectId,
        width: canvas.width,
        height: canvas.height,
        background: "transparent",
        name: `Workspace ${new Date().toLocaleTimeString()}`,
        layers: layers.map((l) => ({
          asset_id: l.asset_id,
          x: l.x,
          y: l.y,
          scale: l.scale,
          rotation: l.rotation,
          opacity: l.opacity,
          visible: l.visible,
        })),
      });
      await refreshAssets();
      notify(`Composite saved (${res.asset.width}×${res.asset.height})`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setExporting(false);
    }
  };

  return (
    <Localize>
    <div className="grid min-h-0 flex-1 grid-cols-[250px_1fr_272px]">
      <div className="min-h-0 space-y-2 overflow-y-auto border-r border-ink-700/70 p-3">
        <Panel title="Layers" actions={<span className="font-mono text-[10px] text-ink-500">{layers.length}</span>} bodyClass="p-2">
          <div className="space-y-1">
            {layers.length === 0 && <p className="px-1 py-3 text-center text-[10.5px] text-ink-500">No layers yet.</p>}
            {[...layers].reverse().map((l) => (
              <div
                key={l.uid}
                onClick={() => setSelected(l.uid)}
                className={`group flex cursor-pointer items-center gap-2 rounded-md border px-1.5 py-1 transition ${
                  selected === l.uid ? "border-[rgb(var(--accent))]/60 bg-[rgb(var(--accent))]/10" : "border-transparent hover:bg-ink-800"
                }`}
              >
                <button
                  type="button"
                  className="text-ink-500 hover:text-ink-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    update(l.uid, { visible: !l.visible });
                  }}
                  title="Toggle visibility"
                >
                  <Icon name={l.visible ? "eye" : "eyeOff"} size={13} />
                </button>
                <span className="checker grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded border border-ink-700">
                  <img src={mediaUrl(l.url)} alt="" className="h-full w-full object-contain pixelated" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[10.5px] text-ink-200">{l.name}</span>
                  <span className="block font-mono text-[9px] text-ink-500">
                    {l.x},{l.y} · {Math.round(l.scale * 100)}%
                  </span>
                </span>
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-1">
            <button className="btn-ghost flex-1 !px-1 !py-1" onClick={undo} disabled={!past.length} title="Undo (Ctrl+Z)">
              <Icon name="refresh" size={12} className="-scale-x-100" /> Undo
            </button>
            <button className="btn-ghost flex-1 !px-1 !py-1" onClick={redo} disabled={!future.length} title="Redo (Ctrl+Y)">
              <Icon name="refresh" size={12} /> Redo
            </button>
          </div>
        </Panel>

        <Panel title="Add layer" bodyClass="p-2 space-y-2">
          <AssetPicker assets={assets} value={addId} onChange={setAddId} label="Asset" />
          <button className="btn-primary w-full !py-1" onClick={addLayer} disabled={!addId}>
            <Icon name="plus" size={13} /> Add to canvas
          </button>
        </Panel>

        <Panel title="Canvas" bodyClass="p-2 space-y-2">
          <div className="grid grid-cols-2 gap-1.5">
            <label className="space-y-0.5">
              <span className="text-[10px] text-ink-400">Width</span>
              <input
                type="number"
                min={8}
                max={4096}
                className="field !py-1"
                value={canvas.width}
                onChange={(e) => setCanvas((c) => ({ ...c, width: Math.max(8, Math.min(4096, Number(e.target.value) || 8)) }))}
              />
            </label>
            <label className="space-y-0.5">
              <span className="text-[10px] text-ink-400">Height</span>
              <input
                type="number"
                min={8}
                max={4096}
                className="field !py-1"
                value={canvas.height}
                onChange={(e) => setCanvas((c) => ({ ...c, height: Math.max(8, Math.min(4096, Number(e.target.value) || 8)) }))}
              />
            </label>
          </div>
          <Toggle label="Canvas grid" checked={grid} onChange={setGrid} />
          <Toggle label="Source backdrop" checked={showSource} onChange={setShowSource} hint="Opaque black behind layers" />
          <div className="flex gap-1">
            <button className="btn-ghost flex-1 !px-1 !py-1" onClick={() => void saveLayout()}>
              <Icon name="save" size={12} /> Save layout
            </button>
            <button className="btn-primary flex-1 !px-1 !py-1" onClick={() => void exportComposite()} disabled={exporting}>
              <Icon name="download" size={12} /> Export
            </button>
          </div>
        </Panel>
      </div>

      <div className="relative min-h-0 overflow-hidden checker">
        <div ref={containerRef} className="absolute inset-0" />
        {layers.length === 0 && (
          <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center">
            <Empty icon={<Icon name="layers" size={24} />} title="Composite workspace" hint="Add assets from the left panel, drag them on canvas and export a single PNG." />
          </div>
        )}
        <div className="absolute bottom-2 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1 rounded-lg border border-ink-600 bg-ink-900/90 px-1.5 py-0.5 shadow-panel">
          <button className="p-1 text-ink-300 hover:text-ink-50" onClick={() => setZoom((z) => Math.max(0.25, z * 0.87))}>
            <Icon name="zoomOut" size={13} />
          </button>
          <span className="w-[48px] text-center font-mono text-[10px] text-ink-300">{Math.round(view * 100)}%</span>
          <button className="p-1 text-ink-300 hover:text-ink-50" onClick={() => setZoom((z) => Math.min(4, z * 1.15))}>
            <Icon name="zoomIn" size={13} />
          </button>
          <button className="p-1 text-ink-300 hover:text-ink-50" onClick={() => setZoom(1)} title="Fit">
            <Icon name="fit" size={13} />
          </button>
          <span className="mx-1 h-3.5 w-px bg-ink-700" />
          <span className="font-mono text-[10px] text-ink-500">
            {canvas.width}×{canvas.height}
          </span>
        </div>
      </div>

      <div className="min-h-0 space-y-2 overflow-y-auto border-l border-ink-700/70 p-3">
        <Panel title="Transform" bodyClass="p-3 space-y-2.5">
          {selectedLayer ? (
            <>
              <p className="truncate text-[11px] text-ink-200">{selectedLayer.name}</p>
              <div className="grid grid-cols-2 gap-1.5">
                <label className="space-y-0.5">
                  <span className="text-[10px] text-ink-400">X</span>
                  <input type="number" className="field !py-1" value={Math.round(selectedLayer.x)} onChange={(e) => update(selectedLayer.uid, { x: Number(e.target.value) || 0 })} />
                </label>
                <label className="space-y-0.5">
                  <span className="text-[10px] text-ink-400">Y</span>
                  <input type="number" className="field !py-1" value={Math.round(selectedLayer.y)} onChange={(e) => update(selectedLayer.uid, { y: Number(e.target.value) || 0 })} />
                </label>
              </div>
              <Slider label="Scale" value={Math.round(selectedLayer.scale * 100)} min={10} max={400} onChange={(v) => update(selectedLayer.uid, { scale: v / 100 })} suffix="%" />
              <Slider label="Rotation" value={Math.round(selectedLayer.rotation)} min={-180} max={180} onChange={(v) => update(selectedLayer.uid, { rotation: v })} suffix="°" />
              <Slider label="Opacity" value={Math.round(selectedLayer.opacity * 100)} min={0} max={100} onChange={(v) => update(selectedLayer.uid, { opacity: v / 100 })} suffix="%" />
              <div className="flex gap-1">
                <button className="btn-ghost flex-1 !px-1 !py-1" onClick={() => move(1)} title="Move up">
                  ↑ Up
                </button>
                <button className="btn-ghost flex-1 !px-1 !py-1" onClick={() => move(-1)} title="Move down">
                  ↓ Down
                </button>
              </div>
              <div className="flex gap-1">
                <button className="btn-ghost flex-1 !px-1 !py-1" onClick={duplicate}>
                  <Icon name="copy" size={12} /> Duplicate
                </button>
                <button className="btn-danger flex-1 !px-1 !py-1" onClick={remove}>
                  <Icon name="trash" size={12} /> Delete
                </button>
              </div>
            </>
          ) : (
            <p className="text-[11px] leading-relaxed text-ink-500">Select a layer on the canvas or in the list to edit its transform.</p>
          )}
        </Panel>

        <Panel title="History" bodyClass="p-3 space-y-1.5">
          <div className="flex justify-between text-[10.5px] text-ink-400">
            <span>Undo steps</span>
            <span className="font-mono">{past.length}</span>
          </div>
          <div className="flex justify-between text-[10.5px] text-ink-400">
            <span>Redo steps</span>
            <span className="font-mono">{future.length}</span>
          </div>
          <p className="text-[10px] leading-relaxed text-ink-500">
            Ctrl+Z undo · Ctrl+Y redo. Layout is stored in the project state.
          </p>
        </Panel>

        {selectedLayer && (
          <Panel title="Layer info" bodyClass="p-3 text-[10.5px] text-ink-400 space-y-1">
            <div className="flex justify-between">
              <span>Source</span>
              <span className="font-mono text-ink-200">
                {selectedLayer.width}×{selectedLayer.height}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Rendered</span>
              <span className="font-mono text-ink-200">
                {Math.round(selectedLayer.width * selectedLayer.scale)}×{Math.round(selectedLayer.height * selectedLayer.scale)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Visible</span>
              <span className="font-mono text-ink-200">{selectedLayer.visible ? "yes" : "no"}</span>
            </div>
            <p className="pt-1 text-ink-500">{bytes(selectedLayer.width * selectedLayer.height * 4)} in memory</p>
          </Panel>
        )}
      </div>
    </div>
    </Localize>
  );
}
