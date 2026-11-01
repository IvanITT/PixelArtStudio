import { useEffect, useMemo, useState } from "react";
import { api, errorText, mediaUrl } from "../api/client";
import type { StyleProfile, StyleReport, StyledResult } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "../components/Icon";
import { Empty, Field, Panel, ProgressBar, Segmented, Slider, Spinner, bytes } from "../components/ui";

const KIND_OPTIONS = [
  { value: "all", label: "All assets" },
  { value: "pixelart", label: "Pixel art" },
  { value: "sprite", label: "Sprites" },
  { value: "tileset", label: "Tilesets" },
  { value: "procedural", label: "Procedural" },
  { value: "false3d", label: "2.5D" },
  { value: "frame", label: "Frames" },
];

function scoreTone(score: number | null | undefined): string {
  if (score == null) return "text-ink-400";
  if (score >= 85) return "text-emerald-300";
  if (score >= 70) return "text-amber-300";
  return "text-rose-300";
}

function parseColors(text: string): string[] {
  return text
    .split(/[\s,;]+/)
    .map((c) => c.trim())
    .filter(Boolean)
    .map((c) => (c.startsWith("#") ? c : `#${c}`));
}

export function Style() {
  const projectId = useStudio((s) => s.projectId);
  const assets = useStudio((s) => s.assets);
  const palettes = useStudio((s) => s.palettes);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const refreshPalettes = useStudio((s) => s.refreshPalettes);
  const notify = useStudio((s) => s.notify);

  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [colorsText, setColorsText] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [report, setReport] = useState<StyleReport | null>(null);
  const [results, setResults] = useState<StyledResult[]>([]);
  const [busy, setBusy] = useState<"save" | "apply" | "preview" | "report" | null>(null);
  const [kind, setKind] = useState("all");
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  const projectAssets = useMemo(
    () => assets.filter((a) => a.kind !== "animation" && a.kind !== "export"),
    [assets],
  );
  const visible = useMemo(
    () => (kind === "all" ? projectAssets : projectAssets.filter((a) => a.kind === kind)),
    [projectAssets, kind],
  );

  useEffect(() => {
    if (!projectId) {
      setProfile(null);
      setReport(null);
      setResults([]);
      setSelected(new Set());
      return;
    }
    let alive = true;
    setBusy("report");
    api
      .styleProfile(projectId)
      .then(async ({ profile: loaded }) => {
        if (!alive) return;
        setProfile(loaded);
        setColorsText(loaded.colors.join(", "));
        const rep = await api.styleReport({ project_id: projectId, profile: loaded, limit: 60 });
        if (!alive) return;
        setReport(rep);
        setLoadedAt(new Date().toLocaleTimeString());
      })
      .catch((err) => notify(errorText(err), "error"))
      .finally(() => {
        if (alive) setBusy(null);
      });
    setSelected(new Set());
    setResults([]);
    return () => {
      alive = false;
    };
  }, [projectId, notify]);

  useEffect(() => {
    void refreshPalettes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const patch = (key: keyof StyleProfile, value: any) => setProfile((prev) => (prev ? { ...prev, [key]: value } : prev));

  const choosePalette = (id: string) => {
    if (!profile) return;
    if (!id) {
      setProfile({ ...profile, palette_id: null });
      return;
    }
    const palette = palettes.find((p) => p.id === id);
    if (!palette) return;
    setProfile({ ...profile, palette_id: id, colors: palette.colors });
    setColorsText(palette.colors.join(", "));
  };

  const editColors = (text: string) => {
    setColorsText(text);
    setProfile((prev) => (prev ? { ...prev, colors: parseColors(text), palette_id: null } : prev));
  };

  const saveProfile = async () => {
    if (!projectId || !profile) return;
    setBusy("save");
    try {
      const { profile: saved } = await api.updateStyle(projectId, profile);
      setProfile(saved);
      setColorsText(saved.colors.join(", "));
      notify("Style profile saved to the project", "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const analyse = async (selectionOnly = false, ids?: string[]) => {
    if (!projectId || !profile) return;
    setBusy("report");
    try {
      const rep = await api.styleReport({
        project_id: projectId,
        asset_ids: ids ?? (selectionOnly ? Array.from(selected) : []),
        profile,
        limit: 80,
      });
      setReport(rep);
      setLoadedAt(new Date().toLocaleTimeString());
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const runApply = async (save: boolean) => {
    if (!projectId || !profile) return;
    if (selected.size === 0) {
      notify("Select one or more target assets first", "error");
      return;
    }
    setBusy(save ? "apply" : "preview");
    try {
      const res = await api.applyStyle({
        project_id: projectId,
        asset_ids: Array.from(selected),
        profile,
        save,
        name_suffix: " styled",
      });
      setProfile(res.profile);
      setColorsText(res.profile.colors.join(", "));
      setResults(res.results);
      if (save) {
        await refreshAssets();
        notify(`${res.count} asset${res.count === 1 ? "" : "s"} styled and saved`, "success");
      } else {
        notify(`Preview generated for ${res.count} asset${res.count === 1 ? "" : "s"}`, "success");
      }
      const created = res.results.map((r) => r.asset?.id).filter((id): id is string => Boolean(id));
      if (created.length > 0) await analyse(false, created);
      else await analyse(true);
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectAll = () => setSelected(new Set(visible.map((a) => a.id)));
  const clearAll = () => setSelected(new Set());

  const totalColors = profile?.colors.length || 0;

  return (
    <Localize>
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-ink-700/70 px-3 py-2">
        <div className="min-w-[220px]">
          <h1 className="text-[13px] font-semibold text-ink-100">Asset style consistency</h1>
          <p className="text-[10.5px] text-ink-400">One profile — palette, colour budget, pixel scale, outline and shading — applied to every asset.</p>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <button className="btn-ghost !py-1" onClick={() => void analyse(false)} disabled={busy === "report" || !profile}>
            <Icon name="refresh" size={12} /> Analyse project
          </button>
          <button className="btn-ghost !py-1" onClick={() => void analyse(true)} disabled={busy === "report" || selected.size === 0}>
            <Icon name="fit" size={12} /> Analyse selection
          </button>
          <button className="btn-primary !py-1" onClick={() => void saveProfile()} disabled={busy === "save" || !profile}>
            <Icon name="save" size={12} /> {busy === "save" ? "Saving…" : "Save profile"}
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr_330px]">
        <div className="min-h-0 space-y-3 overflow-y-auto border-r border-ink-700/70 p-3">
          <Panel title="Style profile" subtitle="Stored inside this project">
            {!projectId ? (
              <div className="rounded-lg border border-dashed border-ink-700 bg-ink-900/50 p-4 text-center">
                <p className="text-[11.5px] font-medium text-ink-300">No active project</p>
                <p className="mt-1 text-[10px] leading-relaxed text-ink-500">Open a project to create a style profile and measure its assets.</p>
              </div>
            ) : !profile ? (
              <Spinner label="Loading profile…" />
            ) : (
              <div className="space-y-3">
                <Field label="Palette" hint={totalColors ? `${totalColors} colours` : "free colours"}>
                  <select className="field" value={profile.palette_id || ""} onChange={(e) => choosePalette(e.target.value)}>
                    <option value="">Custom / free colours</option>
                    {palettes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Palette colours" hint="hex · editable">
                  <textarea
                    className="field min-h-[64px] font-mono text-[10.5px]"
                    value={colorsText}
                    onChange={(e) => editColors(e.target.value)}
                    placeholder="#0f380f, #306230, #8bac0f…"
                  />
                </Field>
                {profile.colors.length > 0 && (
                  <div className="flex flex-wrap gap-1 rounded border border-ink-700 bg-ink-900 p-1.5">
                    {profile.colors.slice(0, 48).map((c, i) => (
                      <span key={`${c}-${i}`} className="h-4 w-4 rounded-[3px] border border-black/50" style={{ background: c }} title={c} />
                    ))}
                  </div>
                )}
                <Slider label="Colour budget (0 = off)" value={profile.max_colors} min={0} max={32} onChange={(v) => patch("max_colors", v)} />
                <Field label="Pixel scale">
                  <Segmented
                    value={String(profile.pixel_scale)}
                    onChange={(v) => patch("pixel_scale", Number(v))}
                    options={[
                      { value: "1", label: "1×" },
                      { value: "2", label: "2×" },
                      { value: "3", label: "3×" },
                      { value: "4", label: "4×" },
                    ]}
                  />
                </Field>
                <Field label="Outline">
                  <select className="field" value={profile.outline} onChange={(e) => patch("outline", e.target.value)}>
                    <option value="none">None</option>
                    <option value="dark">Dark outline</option>
                    <option value="light">Light outline</option>
                    <option value="custom">Custom colour</option>
                  </select>
                </Field>
                {profile.outline !== "none" && (
                  <div className="grid grid-cols-2 gap-2">
                    <Slider label="Width" value={profile.outline_width} min={1} max={4} onChange={(v) => patch("outline_width", v)} suffix=" px" />
                    {profile.outline === "custom" ? (
                      <Field label="Outline colour">
                        <input type="color" className="h-8 w-full" value={profile.outline_color} onChange={(e) => patch("outline_color", e.target.value)} />
                      </Field>
                    ) : (
                      <div className="self-end rounded border border-ink-700 bg-ink-900 px-2 py-1.5 text-[10px] text-ink-400">
                        {profile.outline === "dark" ? "#0b0b12" : "#f4ecd8"}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Shading & colour" subtitle="Applied before palette mapping">
            {profile && (
              <div className="space-y-3">
                <Slider label="Shading steps (0 = off)" value={profile.shading_steps} min={0} max={8} onChange={(v) => patch("shading_steps", v)} />
                <Field label="Dithering">
                  <select className="field" value={profile.dither} onChange={(e) => patch("dither", e.target.value)}>
                    <option value="none">None</option>
                    <option value="bayer">Ordered Bayer 8×8</option>
                  </select>
                </Field>
                <Slider label="Brightness" value={profile.brightness} min={40} max={160} onChange={(v) => patch("brightness", v)} suffix="%" />
                <Slider label="Contrast" value={profile.contrast} min={40} max={160} onChange={(v) => patch("contrast", v)} suffix="%" />
                <Slider label="Saturation" value={profile.saturation} min={0} max={180} onChange={(v) => patch("saturation", v)} suffix="%" />
              </div>
            )}
          </Panel>

          <div className="rounded-lg border border-ink-700 bg-ink-900/60 p-2.5 text-[10px] leading-relaxed text-ink-500">
            Applying the profile is deterministic: the same source, palette and settings always produce the same pixels. Profiles are
            saved locally with the project and travel inside exported <code className="rounded bg-ink-800 px-1">.pasproject.zip</code> files.
          </div>
        </div>

        <div className="flex min-h-0 flex-col">
          <div className="flex flex-wrap items-center gap-2 border-b border-ink-700/70 px-3 py-2">
            <select className="field !w-auto !py-1" value={kind} onChange={(e) => setKind(e.target.value)}>
              {KIND_OPTIONS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
            <span className="text-[10.5px] text-ink-500">
              {visible.length} shown · {selected.size} selected
            </span>
            <button className="btn-ghost !py-1 !text-[11px]" onClick={selectAll} disabled={visible.length === 0}>
              All
            </button>
            <button className="btn-ghost !py-1 !text-[11px]" onClick={clearAll} disabled={selected.size === 0}>
              Clear
            </button>
            <div className="ml-auto flex items-center gap-1.5">
              <button className="btn-ghost !py-1" onClick={() => void runApply(false)} disabled={selected.size === 0 || busy !== null}>
                <Icon name="eye" size={12} /> Preview
              </button>
              <button className="btn-primary !py-1" onClick={() => void runApply(true)} disabled={selected.size === 0 || busy !== null}>
                <Icon name="spark" size={12} /> {busy === "apply" ? "Applying…" : "Apply style"}
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {!projectId ? (
              <Empty icon={<Icon name="projects" size={24} />} title="No active project" hint="Create or open a project to give its assets a shared style." />
            ) : visible.length === 0 ? (
              <Empty icon={<Icon name="library" size={24} />} title="No compatible assets" hint="Generate or import assets, then return here to unify their style." />
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(118px,1fr))] gap-2">
                {visible.map((asset) => {
                  const active = selected.has(asset.id);
                  return (
                    <button
                      key={asset.id}
                      type="button"
                      onClick={() => toggle(asset.id)}
                      className={`group overflow-hidden rounded-lg border text-left transition ${
                        active ? "border-[rgb(var(--accent))] shadow-glow" : "border-ink-700 hover:border-ink-600"
                      }`}
                    >
                      <span className="checker relative grid h-[84px] place-items-center overflow-hidden">
                        <img src={mediaUrl(asset.thumb_url || asset.url)} alt={asset.name} className="max-h-[78px] max-w-full object-contain pixelated" loading="lazy" />
                        <span
                          className={`absolute right-1 top-1 grid h-4 w-4 place-items-center rounded border ${
                            active ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))] text-white" : "border-ink-600 bg-black/60 text-transparent"
                          }`}
                        >
                          <Icon name="check" size={10} />
                        </span>
                      </span>
                      <span className="block px-1.5 py-1">
                        <span className="block truncate text-[10px] text-ink-200">{asset.name}</span>
                        <span className="block font-mono text-[8.5px] text-ink-500">
                          {asset.kind} · {asset.width}×{asset.height}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            {results.length > 0 && (
              <div className="mt-4">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="label">Style results ({results.length})</h2>
                  <button className="text-[10px] text-ink-500 hover:text-ink-300" onClick={() => setResults([])}>
                    Clear results
                  </button>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {results.map((res) => (
                    <div key={res.source.id} className="flex gap-2 rounded-lg border border-ink-700 bg-ink-850 p-2">
                      <div className="checker grid h-[76px] w-[76px] shrink-0 place-items-center overflow-hidden rounded border border-ink-700">
                        <img src={mediaUrl(res.url)} alt={`${res.source.name} styled`} className="max-h-[72px] max-w-full object-contain pixelated" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[11px] text-ink-100">{res.asset?.name || `${res.source.name} preview`}</p>
                        <p className="font-mono text-[9px] text-ink-500">
                          {res.info.colors_before}→{res.info.colors_after} colours · {res.info.pixel_scale_before}→{res.info.pixel_scale_after}×
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <span className={`chip !py-0 !text-[9px] ${scoreTone(res.info.score_after)}`}>
                            {res.info.score_before} → {res.info.score_after}
                          </span>
                          {res.info.applied.slice(0, 4).map((a) => (
                            <span key={a} className="chip !py-0 !text-[9px]">
                              {a}
                            </span>
                          ))}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[9px]">
                          <a className="text-[rgb(var(--accent))] hover:underline" href={mediaUrl(res.url)} download>
                            Download
                          </a>
                          {res.asset && <span className="text-ink-500">{bytes(res.asset.size_bytes)}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="min-h-0 space-y-3 overflow-y-auto border-l border-ink-700/70 p-3">
          <Panel
            title="Consistency report"
            subtitle={loadedAt ? `Analysed at ${loadedAt}` : "Waiting for analysis"}
            actions={
              <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => void analyse(false)} disabled={busy === "report"}>
                <Icon name="refresh" size={11} />
              </button>
            }
          >
            {busy === "report" && !report ? (
              <Spinner label="Measuring palette coverage and outlines…" />
            ) : !report ? (
              <p className="text-[11px] text-ink-500">No report yet.</p>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <div className={`grid h-[74px] w-[74px] shrink-0 place-items-center rounded-full border-4 ${report.aggregate.consistent ? "border-emerald-500/60" : "border-amber-500/50"}`}>
                    <div className="text-center">
                      <p className={`font-mono text-[20px] leading-none ${scoreTone(report.aggregate.score)}`}>{report.aggregate.score ?? "—"}</p>
                      <p className="text-[8.5px] uppercase tracking-wider text-ink-500">score</p>
                    </div>
                  </div>
                  <div className="min-w-0 flex-1 space-y-1 text-[10px]">
                    <div className="flex justify-between">
                      <span className="text-ink-500">Mean asset</span>
                      <span className="font-mono text-ink-200">{report.aggregate.mean_asset_score ?? "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-500">Palette coverage</span>
                      <span className="font-mono text-ink-200">{report.aggregate.palette_coverage != null ? `${report.aggregate.palette_coverage}%` : "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-500">Palette overlap</span>
                      <span className="font-mono text-ink-200">
                        {report.aggregate.pairwise_palette_overlap != null ? `${report.aggregate.pairwise_palette_overlap}%` : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-500">Avg colours</span>
                      <span className="font-mono text-ink-200">{report.aggregate.average_colors ?? "—"}</span>
                    </div>
                  </div>
                </div>
                <ProgressBar value={report.aggregate.score ?? 0} />
                <ul className="space-y-1">
                  {report.aggregate.recommendations.map((r) => (
                    <li key={r} className="flex gap-1.5 text-[10px] leading-snug text-ink-400">
                      <Icon name="info" size={11} className="mt-[1px] shrink-0 text-ink-500" />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Panel>

          <Panel title="Per-asset detail" subtitle={`${report?.rows.length || 0} assets measured`} bodyClass="p-0">
            <div className="max-h-[calc(100vh-430px)] min-h-[180px] overflow-y-auto">
              {report && report.rows.length > 0 ? (
                <table className="w-full text-left text-[9.5px]">
                  <thead className="sticky top-0 bg-ink-850 text-ink-500">
                    <tr>
                      <th className="px-2 py-1 font-medium">Asset</th>
                      <th className="px-1 py-1 text-right font-medium">Score</th>
                      <th className="px-1 py-1 text-right font-medium">Col</th>
                      <th className="px-1 py-1 text-right font-medium">Cov</th>
                      <th className="px-1 py-1 text-right font-medium">Px</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.rows.map((row) => (
                      <tr key={row.asset_id} className="border-t border-ink-700/40" title={row.notes.join(" ")}>
                        <td className="max-w-[112px] truncate px-2 py-1 text-ink-300">{row.name}</td>
                        <td className={`px-1 py-1 text-right font-mono ${scoreTone(row.score)}`}>{row.score}</td>
                        <td className="px-1 py-1 text-right font-mono text-ink-400">{row.colors}</td>
                        <td className="px-1 py-1 text-right font-mono text-ink-400">
                          {row.palette_coverage != null ? `${Math.round(row.palette_coverage * 100)}` : "—"}
                        </td>
                        <td className="px-1 py-1 text-right font-mono text-ink-400">{row.pixel_scale}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="p-3 text-[10.5px] text-ink-500">No assets measured yet.</p>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
    </Localize>
  );
}
