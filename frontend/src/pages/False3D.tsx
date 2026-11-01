import { useEffect, useState } from "react";
import { api, errorText, mediaUrl } from "../api/client";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { AssetPicker, DropZone } from "../components/AssetPicker";
import { ImageStage } from "../components/ImageStage";
import { Icon } from "../components/Icon";
import { Empty, Panel, Segmented, Slider, Spinner, Toggle } from "../components/ui";

interface Template {
  id: string;
  name: string;
  description: string;
  defaults: Record<string, any>;
}

export function False3D() {
  const projectId = useStudio((s) => s.projectId);
  const lastImported = useStudio((s) => s.lastImported);
  const assets = useStudio((s) => s.assets);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const ensureProject = useStudio((s) => s.ensureProject);
  const notify = useStudio((s) => s.notify);

  useEffect(() => {
    if (lastImported && lastImported.project_id === projectId) setSourceId(lastImported.id);
  }, [lastImported, projectId]);

  const [templates, setTemplates] = useState<Template[]>([]);
  const [disclaimer, setDisclaimer] = useState("");
  const [templateId, setTemplateId] = useState("iso_object");
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [projection, setProjection] = useState("isometric");
  const [extrude, setExtrude] = useState(28);
  const [relief, setRelief] = useState(25);
  const [floors, setFloors] = useState(1);
  const [perspective, setPerspective] = useState(0);
  const [angle, setAngle] = useState(45);
  const [scale, setScale] = useState(100);
  const [shadow, setShadow] = useState(true);
  const [shadowDx, setShadowDx] = useState(6);
  const [shadowDy, setShadowDy] = useState(8);
  const [shadowBlur, setShadowBlur] = useState(5);
  const [shadowOpacity, setShadowOpacity] = useState(45);
  const [backdrop, setBackdrop] = useState("none");
  const [result, setResult] = useState<{ url: string; info: Record<string, any> } | null>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"studio" | "heightmap">("studio");
  const [blur, setBlur] = useState(2);
  const [invert, setInvert] = useState(false);
  const [heightUrl, setHeightUrl] = useState<string | null>(null);

  useEffect(() => {
    api
      .false3dTemplates()
      .then((res) => {
        setTemplates(res.templates);
        setDisclaimer(res.disclaimer);
        const first = res.templates[0];
        if (first) applyTemplate(first);
      })
      .catch((err) => notify(errorText(err), "error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyTemplate = (t: Template) => {
    setTemplateId(t.id);
    const d = t.defaults || {};
    setProjection(String(d.projection || "isometric"));
    setExtrude(Math.round(Number(d.extrude ?? 0.28) * 100));
    setRelief(Math.round(Number(d.relief ?? 0.25) * 100));
    setFloors(Number(d.floors ?? 1));
    setPerspective(Math.round(Number(d.perspective ?? 0) * 100));
    setShadow(Boolean(d.shadow ?? true));
    setBackdrop(String(d.backdrop || "none"));
  };

  const options = () => ({
    template: templateId,
    projection,
    extrude: extrude / 100,
    relief: relief / 100,
    floors,
    perspective: perspective / 100,
    angle,
    scale: scale / 100,
    shadow,
    shadow_dx: shadowDx,
    shadow_dy: shadowDy,
    shadow_blur: shadowBlur,
    shadow_opacity: shadowOpacity / 100,
    backdrop,
  });

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

  const preview = async () => {
    if (!projectId || !sourceId) return;
    setBusy(true);
    try {
      const res = await api.false3dPreview({ project_id: projectId, asset_id: sourceId, options: options(), save: false });
      setResult({ url: res.url, info: res.info });
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const saveResult = async () => {
    if (!projectId || !sourceId) return;
    try {
      const res = await api.false3dPreview({ project_id: projectId, asset_id: sourceId, options: options(), save: true, name: `${assets.find((a) => a.id === sourceId)?.name || "Prop"} 2.5D` });
      if (res.asset) {
        await refreshAssets();
        notify(`Saved ${res.asset.name}`, "success");
      }
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const makeHeight = async () => {
    if (!projectId || !sourceId) return;
    setBusy(true);
    try {
      const res = await api.heightmap({ project_id: projectId, asset_id: sourceId, blur, invert, save: true, name: `${assets.find((a) => a.id === sourceId)?.name || "Image"} heightmap` });
      setHeightUrl(res.url);
      await refreshAssets();
      notify("Heightmap saved", "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Localize>
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-ink-700/70 px-3 py-2">
        <Segmented
          value={mode}
          onChange={setMode}
          options={[
            { value: "studio", label: "2.5D projection" },
            { value: "heightmap", label: "Heightmap" },
          ]}
        />
        <span className="text-[10.5px] text-ink-500">{disclaimer || "2.5D simulation — not true geometry reconstruction."}</span>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[268px_1fr_276px]">
        <div className="min-h-0 space-y-2 overflow-y-auto border-r border-ink-700/70 p-3">
          <AssetPicker assets={assets} value={sourceId} onChange={setSourceId} label="Flat art" />
          <DropZone onFile={(f) => void upload(f)} compact />

          <Panel title="Templates" bodyClass="p-2 space-y-1">
            {templates.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => applyTemplate(t)}
                className={`w-full rounded-md border p-2 text-left transition ${
                  templateId === t.id ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/10" : "border-ink-700 bg-ink-900 hover:border-ink-600"
                }`}
              >
                <span className="block text-[11px] text-ink-100">{t.name}</span>
                <span className="mt-0.5 block text-[9.5px] leading-snug text-ink-500">{t.description}</span>
              </button>
            ))}
          </Panel>
        </div>

        <div className="min-h-0 overflow-y-auto p-3">
          {busy && <Spinner label="Projecting" />}
          {mode === "studio" && !result && !busy && (
            <Empty icon={<Icon name="three_d" size={24} />} title="Fake 3D studio" hint="Turn flat sprites into isometric, top-down or side-view props with extrusion, relief lighting and shadows." />
          )}
          {mode === "studio" && result && (
            <div className="space-y-3">
              <ImageStage src={result.url} className="h-[calc(100%-120px)] min-h-[360px]" />
              <div className="flex flex-wrap gap-2 text-[10.5px] text-ink-400">
                {Object.entries(result.info || {})
                  .filter(([k]) => ["projection", "width", "height", "duration_ms", "floors", "extrude"].includes(k))
                  .map(([k, v]) => (
                    <span key={k} className="chip">
                      {k}: <span className="font-mono text-ink-200">{String(v)}</span>
                    </span>
                  ))}
              </div>
            </div>
          )}
          {mode === "heightmap" && (
            <div className="space-y-3">
              {heightUrl ? (
                <ImageStage src={heightUrl} className="h-[440px]" />
              ) : (
                <Empty icon={<Icon name="three_d" size={24} />} title="Generate a heightmap" hint="Luminance-driven depth map with controllable blur and inversion." />
              )}
            </div>
          )}
        </div>

        <div className="min-h-0 space-y-2 overflow-y-auto border-l border-ink-700/70 p-3">
          {mode === "studio" ? (
            <>
              <Panel title="Projection" bodyClass="p-3 space-y-2.5">
                <Segmented
                  size="sm"
                  value={projection}
                  onChange={setProjection}
                  options={[
                    { value: "isometric", label: "Iso" },
                    { value: "topdown", label: "Top" },
                    { value: "side", label: "Side" },
                    { value: "orthographic", label: "Shear" },
                  ]}
                />
                <Slider label="Extrusion" value={extrude} min={2} max={100} onChange={setExtrude} suffix="%" />
                <Slider label="Relief light" value={relief} min={0} max={150} onChange={setRelief} suffix="%" />
                <Slider label="Floors" value={floors} min={1} max={4} onChange={setFloors} />
                <Slider label="Perspective" value={perspective} min={-100} max={100} onChange={setPerspective} suffix="%" />
                <Slider label="Projection angle" value={angle} min={-60} max={60} onChange={setAngle} suffix="°" />
                <Slider label="Scale" value={scale} min={20} max={200} onChange={setScale} suffix="%" />
              </Panel>
              <Panel title="Shadow & ground" bodyClass="p-3 space-y-2">
                <Toggle label="Cast shadow" checked={shadow} onChange={setShadow} />
                {shadow && (
                  <>
                    <Slider label="Offset X" value={shadowDx} min={-30} max={30} onChange={setShadowDx} />
                    <Slider label="Offset Y" value={shadowDy} min={-30} max={30} onChange={setShadowDy} />
                    <Slider label="Blur" value={shadowBlur} min={1} max={20} onChange={setShadowBlur} />
                    <Slider label="Opacity" value={shadowOpacity} min={0} max={100} onChange={setShadowOpacity} suffix="%" />
                  </>
                )}
                <Segmented
                  size="sm"
                  value={backdrop}
                  onChange={setBackdrop}
                  options={[
                    { value: "none", label: "None" },
                    { value: "grid", label: "Grid" },
                  ]}
                />
              </Panel>
              <div className="flex gap-1.5">
                <button className="btn-primary flex-1" onClick={() => void preview()} disabled={!sourceId || busy}>
                  <Icon name="play" size={13} /> Preview
                </button>
                <button className="btn-ghost flex-1" onClick={() => void saveResult()} disabled={!sourceId || busy}>
                  <Icon name="save" size={13} /> Save
                </button>
              </div>
            </>
          ) : (
            <Panel title="Heightmap" bodyClass="p-3 space-y-2.5">
              <Slider label="Blur" value={blur} min={0} max={24} step={0.5} onChange={setBlur} suffix=" px" />
              <Toggle label="Invert depth" checked={invert} onChange={setInvert} />
              <button className="btn-primary w-full" onClick={() => void makeHeight()} disabled={!sourceId || busy}>
                <Icon name="three_d" size={13} /> Generate & save
              </button>
              <p className="text-[10px] leading-relaxed text-ink-500">
                Heightmaps are derived from luminance and blurred with OpenCV. Useful as a displacement or normal-map source in your
                engine of choice.
              </p>
            </Panel>
          )}
          {result && mode === "studio" && (
            <Panel title="Last projection" bodyClass="p-3">
              <a href={mediaUrl(result.url)} download="false3d.png" className="btn-ghost w-full">
                <Icon name="download" size={13} /> Download preview
              </a>
            </Panel>
          )}
        </div>
      </div>
    </div>
    </Localize>
  );
}
