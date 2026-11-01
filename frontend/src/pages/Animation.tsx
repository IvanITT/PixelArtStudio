import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorText, mediaUrl } from "../api/client";
import type { Animation } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { AssetPicker } from "../components/AssetPicker";
import { Icon } from "../components/Icon";
import { Empty, Panel, Segmented, Slider, Spinner, Toggle, bytes } from "../components/ui";

const TEMPLATES = [
  { id: "idle", label: "Idle" },
  { id: "walk", label: "Walk" },
  { id: "run", label: "Run" },
  { id: "jump", label: "Jump" },
  { id: "fall", label: "Fall" },
  { id: "attack", label: "Attack" },
  { id: "hurt", label: "Hurt" },
  { id: "death", label: "Death" },
];

export function AnimationStudio() {
  const projectId = useStudio((s) => s.projectId);
  const assets = useStudio((s) => s.assets);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const notify = useStudio((s) => s.notify);

  const [animations, setAnimations] = useState<Animation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [active, setActive] = useState<Animation | null>(null);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("New animation");
  const [newFrameId, setNewFrameId] = useState<string | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [tplAssetId, setTplAssetId] = useState<string | null>(null);
  const [tplName, setTplName] = useState("walk");
  const [tplFrames, setTplFrames] = useState(4);
  const [tplReplace, setTplReplace] = useState(false);
  const [exportFormat, setExportFormat] = useState("sheet");
  const [columns, setColumns] = useState(0);
  const [padding, setPadding] = useState(0);
  const [spacing, setSpacing] = useState(0);
  const [exportResult, setExportResult] = useState<{ url: string; name: string; format: string } | null>(null);
  const timer = useRef<number | null>(null);

  const loadList = async () => {
    if (!projectId) return;
    try {
      const list = await api.animations(projectId);
      setAnimations(list);
      setActiveId((cur) => cur || list[0]?.id || null);
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  useEffect(() => {
    void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (!activeId) {
      setActive(null);
      return;
    }
    api
      .animation(activeId)
      .then((a) => {
        setActive(a);
        setFrameIndex(0);
        setExportResult(null);
      })
      .catch((err) => notify(errorText(err), "error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current);
    if (playing && active && active.frame_count > 0) {
      timer.current = window.setInterval(() => {
        setFrameIndex((i) => (i + 1) % active.frame_count);
      }, Math.max(40, 1000 / Math.max(1, active.fps)));
    }
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [playing, active?.fps, active?.frame_count, active]);

  const applyUpdate = async (promise: Promise<Animation>) => {
    setBusy(true);
    try {
      const updated = await promise;
      setActive(updated);
      setFrameIndex((i) => Math.min(i, Math.max(0, updated.frame_count - 1)));
      await loadList();
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const create = async () => {
    if (!projectId) return;
    try {
      const anim = await api.createAnimation(projectId, { name: newName || "New animation", fps: 8, loop: true });
      setCreating(false);
      setNewName("New animation");
      await loadList();
      setActiveId(anim.id);
      notify("Animation created", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const remove = async () => {
    if (!active) return;
    if (!window.confirm(`Delete animation “${active.name}”? Frame assets stay in the library.`)) return;
    try {
      await api.deleteAnimation(active.id);
      setActive(null);
      setActiveId(null);
      await loadList();
      notify("Animation deleted", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const addFrame = async () => {
    if (!active || !newFrameId) return;
    await applyUpdate(api.addFrame(active.id, newFrameId));
    setNewFrameId(null);
  };

  const uploadFrame = async (file: File) => {
    if (!projectId || !active) return;
    try {
      const res = await api.uploadFrame(projectId, active.id, file);
      setActive(res.animation);
      await Promise.all([loadList(), refreshAssets()]);
      setFrameIndex(res.animation.frame_count - 1);
      notify("Frame uploaded", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const moveFrame = async (from: number, to: number) => {
    if (!active || to < 0 || to >= active.frame_count) return;
    await applyUpdate(api.reorderFrames(active.id, from, to));
    setFrameIndex(to);
  };

  const applyTemplate = async () => {
    if (!active || !tplAssetId) return;
    await applyUpdate(
      api.applyTemplate(active.id, { asset_id: tplAssetId, template: tplName, frames: tplFrames, replace: tplReplace }),
    );
    notify(`${tplName} template applied`, "success");
  };

  const exportAnim = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const res = await api.exportAnimation(active.id, {
        format: exportFormat,
        columns,
        padding,
        spacing,
        name: active.name,
        save_asset: true,
      });
      setExportResult({ url: res.asset.url, name: res.asset.name, format: res.format });
      await refreshAssets();
      notify(`Exported ${res.asset.name}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const currentFrame = active?.frame_assets?.[frameIndex] || null;
  const frameCount = active?.frame_count || 0;
  const imageAssets = useMemo(() => assets.filter((a) => a.kind !== "animation" && a.kind !== "export"), [assets]);

  return (
    <Localize>
    <div className="grid h-full min-h-0 grid-cols-[230px_1fr_290px]">
      <div className="flex min-h-0 flex-col border-r border-ink-700/70">
        <div className="flex items-center justify-between border-b border-ink-700/70 px-2.5 py-2">
          <span className="label">Animations ({animations.length})</span>
          <button className="text-ink-400 hover:text-ink-100" onClick={() => setCreating(true)} title="New animation">
            <Icon name="plus" size={14} />
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-1.5">
          {animations.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setActiveId(a.id)}
              className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition ${
                activeId === a.id ? "bg-[rgb(var(--accent))]/15 text-[rgb(var(--accent))]" : "text-ink-300 hover:bg-ink-800"
              }`}
            >
              <span className="checker grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded border border-ink-700">
                {a.frame_assets?.[0] && (
                  <img src={mediaUrl(a.frame_assets[0].thumb_url || a.frame_assets[0].url)} alt="" className="h-full w-full object-contain pixelated" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[11px]">{a.name}</span>
                <span className="block font-mono text-[9px] text-ink-500">
                  {a.frame_count}f · {a.fps}fps
                </span>
              </span>
            </button>
          ))}
          {animations.length === 0 && <p className="px-2 py-6 text-center text-[10.5px] text-ink-500">No animations yet.</p>}
        </div>
        {creating && (
          <div className="space-y-1.5 border-t border-ink-700/70 p-2.5">
            <input autoFocus className="field !py-1" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Animation name" />
            <div className="flex gap-1">
              <button className="btn-primary flex-1 !py-1" onClick={() => void create()}>
                Create
              </button>
              <button className="btn-ghost !py-1" onClick={() => setCreating(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex min-h-0 flex-col">
        {!active ? (
          <div className="p-4">
            <Empty icon={<Icon name="animation" size={24} />} title="No animation selected" hint="Create an animation, add frames from the library or generate a walk cycle from a single sprite." />
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 border-b border-ink-700/70 px-3 py-2">
              <input
                className="field !w-auto max-w-[220px] !py-1"
                value={active.name}
                onChange={(e) => setActive({ ...active, name: e.target.value })}
                onBlur={() => void applyUpdate(api.updateAnimation(active.id, { name: active.name }))}
              />
              <span className="chip">{frameCount} frames</span>
              <span className="chip">{active.fps} fps</span>
              <button className="btn-danger ml-auto !py-1" onClick={() => void remove()}>
                <Icon name="trash" size={12} /> Delete
              </button>
            </div>

            <div className="relative min-h-0 flex-1 overflow-hidden checker">
              {busy && <div className="absolute left-3 top-3 z-10"><Spinner label="Updating" /></div>}
              {currentFrame ? (
                <div className="grid h-full place-items-center p-4">
                  <img
                    src={mediaUrl(currentFrame.url)}
                    alt={currentFrame.name}
                    className="max-h-full max-w-full object-contain pixelated"
                    style={{ imageRendering: "pixelated" }}
                  />
                </div>
              ) : (
                <div className="grid h-full place-items-center text-[11.5px] text-ink-500">This animation has no frames.</div>
              )}
              <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-lg border border-ink-600 bg-ink-900/90 px-1.5 py-1 shadow-panel">
                <button className="p-1 text-ink-300 hover:text-ink-50" onClick={() => setFrameIndex((i) => Math.max(0, i - 1))}>
                  <Icon name="chevron" size={13} className="rotate-180" />
                </button>
                <button className="p-1 text-ink-100 hover:text-[rgb(var(--accent))]" onClick={() => setPlaying((p) => !p)}>
                  <Icon name={playing ? "pause" : "play"} size={14} />
                </button>
                <button className="p-1 text-ink-300 hover:text-ink-50" onClick={() => setFrameIndex((i) => Math.min(frameCount - 1, i + 1))}>
                  <Icon name="chevron" size={13} />
                </button>
                <span className="mx-1 font-mono text-[10px] text-ink-400">
                  {frameCount ? frameIndex + 1 : 0}/{frameCount}
                </span>
              </div>
            </div>

            <div className="shrink-0 border-t border-ink-700/70 p-2">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="label">Timeline</span>
                <span className="text-[9.5px] text-ink-500">Select a frame · reorder with arrows</span>
              </div>
              <div className="flex gap-1.5 overflow-x-auto pb-1">
                {active.frame_assets.map((f, i) => (
                  <div
                    key={`${f.id}-${i}`}
                    className={`group relative shrink-0 overflow-hidden rounded border ${
                      i === frameIndex ? "border-[rgb(var(--accent))]" : "border-ink-700"
                    }`}
                  >
                    <button type="button" onClick={() => setFrameIndex(i)} className="checker grid h-[62px] w-[62px] place-items-center">
                      <img src={mediaUrl(f.thumb_url || f.url)} alt={f.name} className="max-h-[60px] max-w-[60px] object-contain pixelated" />
                    </button>
                    <span className="absolute left-0 top-0 rounded-br bg-black/70 px-1 font-mono text-[8.5px] text-ink-200">{i + 1}</span>
                    <div className="absolute inset-x-0 bottom-0 hidden justify-between bg-black/70 group-hover:flex">
                      <button className="px-0.5 text-ink-300 hover:text-white" onClick={() => void moveFrame(i, i - 1)} title="Move left">
                        ‹
                      </button>
                      <button
                        className="px-0.5 text-ink-300 hover:text-white"
                        onClick={() => void applyUpdate(api.duplicateFrame(active.id, i, i + 1))}
                        title="Duplicate"
                      >
                        ⧉
                      </button>
                      <button
                        className="px-0.5 text-rose-300 hover:text-rose-100"
                        onClick={() => void applyUpdate(api.deleteFrame(active.id, i))}
                        title="Delete frame"
                      >
                        ×
                      </button>
                      <button className="px-0.5 text-ink-300 hover:text-white" onClick={() => void moveFrame(i, i + 1)} title="Move right">
                        ›
                      </button>
                    </div>
                  </div>
                ))}
                <label className="grid h-[62px] w-[62px] shrink-0 cursor-pointer place-items-center rounded border border-dashed border-ink-600 text-ink-500 hover:border-ink-500 hover:text-ink-200">
                  <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && void uploadFrame(e.target.files[0])} />
                  <Icon name="plus" size={16} />
                </label>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="min-h-0 space-y-2 overflow-y-auto border-l border-ink-700/70 p-3">
        {active && (
          <>
            <Panel title="Playback" bodyClass="p-3 space-y-2.5">
              <Slider label="FPS" value={active.fps} min={1} max={30} onChange={(v) => setActive({ ...active, fps: v })} />
              <button className="btn-ghost w-full !py-1" onClick={() => void applyUpdate(api.updateAnimation(active.id, { fps: active.fps }))}>
                Apply FPS
              </button>
              <Toggle
                label="Loop"
                checked={active.loop}
                onChange={(v) => {
                  setActive({ ...active, loop: v });
                  void applyUpdate(api.updateAnimation(active.id, { loop: v }));
                }}
              />
            </Panel>

            <Panel title="Add frame" bodyClass="p-3 space-y-2">
              <AssetPicker assets={imageAssets} value={newFrameId} onChange={setNewFrameId} label="Frame asset" />
              <button className="btn-ghost w-full" onClick={() => void addFrame()} disabled={!newFrameId || busy}>
                <Icon name="plus" size={13} /> Append frame
              </button>
            </Panel>

            <Panel title="Template from sprite" bodyClass="p-3 space-y-2">
              <AssetPicker assets={imageAssets} value={tplAssetId} onChange={setTplAssetId} label="Sprite" />
              <select className="field" value={tplName} onChange={(e) => setTplName(e.target.value)}>
                {TEMPLATES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
              <Slider label="Frames" value={tplFrames} min={2} max={16} onChange={setTplFrames} />
              <Toggle label="Replace existing frames" checked={tplReplace} onChange={setTplReplace} />
              <button className="btn-primary w-full" onClick={() => void applyTemplate()} disabled={!tplAssetId || busy}>
                <Icon name="spark" size={13} /> Generate frames
              </button>
            </Panel>

            <Panel title="Export" bodyClass="p-3 space-y-2">
              <Segmented
                size="sm"
                value={exportFormat}
                onChange={setExportFormat}
                options={[
                  { value: "sheet", label: "Sheet" },
                  { value: "gif", label: "GIF" },
                  { value: "webp", label: "WebP" },
                  { value: "json", label: "JSON" },
                ]}
              />
              {exportFormat === "sheet" && (
                <div className="grid grid-cols-3 gap-1.5">
                  <label className="space-y-0.5">
                    <span className="text-[10px] text-ink-400">Cols</span>
                    <input type="number" min={0} max={64} className="field !py-1" value={columns} onChange={(e) => setColumns(Number(e.target.value) || 0)} />
                  </label>
                  <label className="space-y-0.5">
                    <span className="text-[10px] text-ink-400">Gap</span>
                    <input type="number" min={0} max={32} className="field !py-1" value={spacing} onChange={(e) => setSpacing(Number(e.target.value) || 0)} />
                  </label>
                  <label className="space-y-0.5">
                    <span className="text-[10px] text-ink-400">Pad</span>
                    <input type="number" min={0} max={32} className="field !py-1" value={padding} onChange={(e) => setPadding(Number(e.target.value) || 0)} />
                  </label>
                </div>
              )}
              <button className="btn-primary w-full" onClick={() => void exportAnim()} disabled={busy || frameCount === 0}>
                <Icon name="download" size={13} /> Export {exportFormat.toUpperCase()}
              </button>
              {exportResult && (
                <div className="rounded border border-ink-700 bg-ink-900 p-2 text-[10px]">
                  <p className="truncate text-ink-200">{exportResult.name}</p>
                  <a href={exportResult.url} download className="mt-1 inline-block text-[rgb(var(--accent))] hover:underline">
                    Download {exportResult.format}
                  </a>
                </div>
              )}
            </Panel>

            <Panel title="Frame info" bodyClass="p-3 text-[10.5px] text-ink-400 space-y-1">
              {currentFrame ? (
                <>
                  <div className="flex justify-between">
                    <span>Name</span>
                    <span className="max-w-[150px] truncate text-ink-200">{currentFrame.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Size</span>
                    <span className="font-mono text-ink-200">
                      {currentFrame.width}×{currentFrame.height}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>File</span>
                    <span className="font-mono text-ink-200">{bytes(currentFrame.size_bytes)}</span>
                  </div>
                </>
              ) : (
                <p className="text-ink-500">No frame selected.</p>
              )}
            </Panel>
          </>
        )}
      </div>
    </div>
    </Localize>
  );
}
