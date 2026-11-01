import { useEffect, useMemo, useState } from "react";
import { api, errorText } from "../api/client";
import type { Benchmark, JobRecord, Palette, Settings as SettingsShape, SystemStats } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "../components/Icon";
import { Field, Modal, Panel, ProgressBar, Section, Spinner, Stat, Toggle, bytes } from "../components/ui";

const ACCENTS = [
  { id: "violet", label: "Violet", hex: "#8b5cf6" },
  { id: "teal", label: "Teal", hex: "#14b8a6" },
  { id: "amber", label: "Amber", hex: "#f59e0b" },
  { id: "rose", label: "Rose", hex: "#f43f5e" },
  { id: "blue", label: "Blue", hex: "#3b82f6" },
  { id: "green", label: "Green", hex: "#22c55e" },
];

const LIMITS: { key: keyof SettingsShape; label: string; hint: string; min: number; max: number; step?: number }[] = [
  { key: "max_upload_mb", label: "Max upload size", hint: "MB per file", min: 1, max: 256 },
  { key: "max_image_pixels", label: "Max image pixels", hint: "width × height", min: 1_000_000, max: 200_000_000, step: 1_000_000 },
  { key: "preview_max_dim", label: "Preview max dimension", hint: "px", min: 256, max: 4096 },
  { key: "max_output_dim", label: "Output max dimension", hint: "px", min: 128, max: 8192 },
  { key: "max_tiles", label: "Max extracted tiles", hint: "per sheet", min: 64, max: 65536 },
  { key: "max_sheet_dim", label: "Max sheet dimension", hint: "px", min: 512, max: 16384 },
  { key: "cache_limit_mb", label: "Preview cache limit", hint: "MB", min: 64, max: 4096 },
  { key: "autosave_seconds", label: "Autosave interval", hint: "seconds · 0 disables", min: 0, max: 300 },
];

function fmtWhen(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

function statusTone(status: string): string {
  if (status === "done") return "text-emerald-300 border-emerald-800/70 bg-emerald-950/40";
  if (status === "error") return "text-rose-300 border-rose-900/70 bg-rose-950/40";
  if (status === "cancelled") return "text-ink-400 border-ink-600 bg-ink-800";
  if (status === "running") return "text-amber-300 border-amber-800/70 bg-amber-950/40";
  return "text-sky-300 border-sky-900/70 bg-sky-950/30";
}

export function Settings() {
  const stored = useStudio((s) => s.settings);
  const health = useStudio((s) => s.health);
  const palettes = useStudio((s) => s.palettes);
  const refreshPalettes = useStudio((s) => s.refreshPalettes);
  const updateSettings = useStudio((s) => s.updateSettings);
  const notify = useStudio((s) => s.notify);
  const projectId = useStudio((s) => s.projectId);

  const [form, setForm] = useState<SettingsShape | null>(stored);
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [jobs, setJobs] = useState<{ active: JobRecord[]; recent: JobRecord[] }>({ active: [], recent: [] });
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [runningBench, setRunningBench] = useState<string | null>(null);
  const [benchProgress, setBenchProgress] = useState(0);
  const [paletteModal, setPaletteModal] = useState(false);
  const [paletteName, setPaletteName] = useState("");
  const [paletteColors, setPaletteColors] = useState("#1a1a2e, #16213e, #0f3460, #e94560");
  const [paletteShared, setPaletteShared] = useState(false);
  const [cleaning, setCleaning] = useState(false);

  useEffect(() => {
    if (stored) setForm((prev) => prev ?? stored);
  }, [stored]);

  const loadAux = () => {
    void api.stats().then(setStats).catch(() => undefined);
    void api.jobs().then(setJobs).catch(() => undefined);
    void api.benchmarks(5).then(setBenchmarks).catch(() => undefined);
  };

  useEffect(() => {
    loadAux();
    const t = window.setInterval(loadAux, 12000);
    return () => window.clearInterval(t);
  }, []);

  const dirty = useMemo(() => {
    if (!form || !stored) return false;
    return (Object.keys(form) as (keyof SettingsShape)[]).some((k) => form[k] !== stored[k]);
  }, [form, stored]);

  const patch = (key: keyof SettingsShape, value: any) => setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const save = async () => {
    if (!form) return;
    setSaving(true);
    try {
      await updateSettings({
        max_upload_mb: Number(form.max_upload_mb),
        max_image_pixels: Number(form.max_image_pixels),
        preview_max_dim: Number(form.preview_max_dim),
        max_output_dim: Number(form.max_output_dim),
        worker_threads: Number(form.worker_threads),
        max_tiles: Number(form.max_tiles),
        max_sheet_dim: Number(form.max_sheet_dim),
        cache_limit_mb: Number(form.cache_limit_mb),
        autosave_seconds: Number(form.autosave_seconds),
        accent: form.accent,
        reduce_motion: form.reduce_motion,
      });
      setForm(useStudio.getState().settings);
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setSaving(false);
    }
  };

  const cleanup = async () => {
    setCleaning(true);
    try {
      const res = await api.cleanup();
      notify(`Removed ${res.removed} temporary file${res.removed === 1 ? "" : "s"}`, "success");
      loadAux();
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setCleaning(false);
    }
  };

  const runBenchmark = async () => {
    try {
      const { job_id } = await api.runBenchmarks();
      setRunningBench(job_id);
      setBenchProgress(0);
      notify("Benchmark started in the background", "info");
      const poll = window.setInterval(async () => {
        try {
          const job = await api.job(job_id);
          setBenchProgress(job.progress);
          if (["done", "error", "cancelled"].includes(job.status)) {
            window.clearInterval(poll);
            setRunningBench(null);
            if (job.status === "done") {
              notify("Benchmark finished — results saved", "success");
              void api.benchmarks(5).then(setBenchmarks);
            } else notify(job.error || `Benchmark ${job.status}`, "error");
            loadAux();
          }
        } catch {
          window.clearInterval(poll);
          setRunningBench(null);
        }
      }, 800);
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const createPalette = async () => {
    const colors = paletteColors
      .split(/[\s,;]+/)
      .map((c) => c.trim())
      .filter(Boolean)
      .map((c) => (c.startsWith("#") ? c : `#${c}`));
    if (!paletteName.trim() || colors.length === 0) {
      notify("Palette needs a name and at least one colour", "error");
      return;
    }
    try {
      await api.createPalette({ name: paletteName.trim(), colors, project_id: paletteShared ? projectId : null });
      await refreshPalettes();
      setPaletteModal(false);
      setPaletteName("");
      notify("Palette saved", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const removePalette = async (palette: Palette) => {
    if (!window.confirm(`Delete palette “${palette.name}”?`)) return;
    try {
      await api.deletePalette(palette.id);
      await refreshPalettes();
      notify("Palette deleted", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const cancelJob = async (job: JobRecord) => {
    try {
      await api.cancelJob(job.id);
      notify("Job cancelled", "success");
      loadAux();
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const latest = benchmarks[0];

  return (
    <Localize>
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-[17px] font-semibold text-ink-50">Settings</h1>
          <p className="text-[11px] text-ink-400">Local engine limits, appearance, palettes and maintenance. Stored in SQLite on this machine.</p>
        </div>
        <div className="flex items-center gap-1.5">
          <a className="btn-ghost" href="/api/docs" target="_blank" rel="noreferrer">
            <Icon name="info" size={13} /> API docs
          </a>
          <button className="btn-primary" onClick={() => void save()} disabled={!form || saving || !dirty}>
            <Icon name="save" size={13} /> {saving ? "Saving…" : dirty ? "Save settings" : "Saved"}
          </button>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Engine limits" subtitle="Applied to uploads, previews and every generator" className="xl:col-span-2">
          {form ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {LIMITS.map((item) => (
                <Field key={String(item.key)} label={item.label} hint={item.hint}>
                  <input
                    type="number"
                    className="field"
                    min={item.min}
                    max={item.max}
                    step={item.step || 1}
                    value={Number(form[item.key] ?? 0)}
                    onChange={(e) => patch(item.key, Number(e.target.value))}
                  />
                </Field>
              ))}
              <Field label="Background worker threads" hint={`1–12 · CPU has ${health?.cpu_count ?? "?"} logical cores`}>
                <input
                  type="number"
                  className="field"
                  min={1}
                  max={12}
                  value={Number(form.worker_threads ?? 4)}
                  onChange={(e) => patch("worker_threads", Number(e.target.value))}
                />
              </Field>
              <div className="hidden sm:block" />
              <div className="sm:col-span-2">
                <Section title="Appearance">
                  <div className="flex flex-wrap gap-1.5">
                    {ACCENTS.map((accent) => (
                      <button
                        key={accent.id}
                        type="button"
                        onClick={() => patch("accent", accent.id)}
                        className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] transition ${
                          form.accent === accent.id ? "border-ink-500 bg-ink-750 text-ink-100" : "border-ink-700 text-ink-400 hover:border-ink-600"
                        }`}
                      >
                        <span className="h-3 w-3 rounded-full" style={{ background: accent.hex }} />
                        {accent.label}
                        {form.accent === accent.id && <Icon name="check" size={11} />}
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 max-w-[320px]">
                    <Toggle
                      label="Reduce motion"
                      hint="Disables shimmer and long transitions"
                      checked={Boolean(form.reduce_motion)}
                      onChange={(v) => patch("reduce_motion", v)}
                    />
                  </div>
                </Section>
              </div>
            </div>
          ) : (
            <Spinner label="Loading settings…" />
          )}
        </Panel>

        <div className="space-y-3">
          <Panel title="System" subtitle="Live CPU-only workload" actions={<button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={loadAux}><Icon name="refresh" size={12} /></button>}>
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Memory used" value={stats ? `${stats.memory.percent.toFixed(0)}%` : "—"} hint={stats ? `${stats.memory.used_mb} / ${stats.memory.total_mb} MB` : undefined} />
              <Stat label="App process" value={stats ? `${stats.memory.app_rss_mb} MB` : "—"} hint="RSS" />
              <Stat label="CPU load" value={stats ? `${stats.cpu.percent.toFixed(0)}%` : "—"} hint={`${stats?.cpu.count ?? health?.cpu_count ?? "?"} threads`} />
              <Stat label="Workers" value={stats?.workers ?? form?.worker_threads ?? "—"} hint="job pool" />
              <Stat label="Projects" value={stats?.projects ?? "—"} />
              <Stat label="Assets" value={stats?.assets ?? "—"} />
            </div>
            <div className="mt-2 space-y-1">
              <div className="flex justify-between text-[10.5px] text-ink-400">
                <span>Library memory pressure</span>
                <span className="font-mono">{stats ? `${stats.memory.used_mb} MB` : "—"}</span>
              </div>
              <ProgressBar value={stats?.memory.percent ?? 0} />
            </div>
            <dl className="mt-2 space-y-0.5 font-mono text-[9.5px] text-ink-500">
              <div className="flex justify-between gap-2">
                <dt>data</dt>
                <dd className="truncate" title={stats?.data?.data_dir}>{stats?.data?.data_dir || health?.data_dir || "—"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>disk</dt>
                <dd>{bytes(stats?.data?.total_bytes)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>cache / tmp</dt>
                <dd>
                  {bytes(stats?.data?.cache_bytes)} / {bytes(stats?.data?.tmp_bytes)}
                </dd>
              </div>
            </dl>
          </Panel>

          <Panel title="Diagnostics" subtitle={health ? `${health.app} v${health.version}` : undefined}>
            <dl className="space-y-1 text-[10.5px]">
              {[
                ["Offline", health?.offline ? "yes · no remote calls" : "unknown"],
                ["Python", health?.python || "—"],
                ["Platform", health?.platform || "—"],
                ["Frontend build", stats?.frontend_built ?? health?.frontend_built ? "served" : "dev server"],
                ...Object.entries(health?.versions || {}).map(([k, v]) => [k, v]),
              ].map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-2 rounded bg-ink-800/60 px-2 py-1">
                  <dt className="text-ink-500">{k}</dt>
                  <dd className="truncate font-mono text-ink-200" title={String(v)}>
                    {String(v)}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-2 flex gap-1.5">
              <a className="btn-ghost flex-1 !py-1 !text-[11px]" href="/api/docs" target="_blank" rel="noreferrer">
                <Icon name="info" size={12} /> Swagger
              </a>
              <a className="btn-ghost flex-1 !py-1 !text-[11px]" href="/api/openapi.json" target="_blank" rel="noreferrer">
                OpenAPI JSON
              </a>
            </div>
          </Panel>
        </div>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Panel
          title="Palettes"
          subtitle="Built-in and project palettes used by pixel art, procedural and animation"
          actions={
            <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => setPaletteModal(true)}>
              <Icon name="plus" size={12} /> New
            </button>
          }
          bodyClass="p-0"
        >
          <ul className="max-h-[290px] divide-y divide-ink-700/60 overflow-y-auto">
            {palettes.map((palette) => (
              <li key={palette.id} className="flex items-center gap-2 px-3 py-2">
                <div className="flex min-w-0 flex-1 flex-wrap gap-0.5">
                  {palette.colors.slice(0, 16).map((c, i) => (
                    <span key={`${palette.id}-${i}`} className="h-4 w-3 rounded-[2px] border border-black/40" style={{ background: c }} title={c} />
                  ))}
                </div>
                <div className="min-w-0 max-w-[140px] text-right">
                  <p className="truncate text-[11px] text-ink-200">{palette.name}</p>
                  <p className="text-[9px] text-ink-500">
                    {palette.colors.length} colours{palette.builtin ? " · built-in" : ""}
                  </p>
                </div>
                {!palette.builtin && (
                  <button className="text-ink-500 hover:text-rose-300" onClick={() => void removePalette(palette)} title="Delete palette">
                    <Icon name="trash" size={12} />
                  </button>
                )}
              </li>
            ))}
            {palettes.length === 0 && <li className="p-3 text-[11px] text-ink-500">No palettes loaded.</li>}
          </ul>
        </Panel>

        <Panel
          title="Jobs"
          subtitle={`${jobs.active.length} active · last ${jobs.recent.length} events`}
          actions={<button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={loadAux}><Icon name="refresh" size={12} /></button>}
          bodyClass="p-0"
        >
          <div className="max-h-[290px] overflow-y-auto">
            {jobs.active.length > 0 && (
              <div className="border-b border-ink-700/60 p-2.5">
                {jobs.active.map((job) => (
                  <div key={job.id} className="mb-2 last:mb-0">
                    <div className="flex items-center justify-between gap-2 text-[10.5px]">
                      <span className="truncate text-ink-300">
                        {job.kind} · {job.message}
                      </span>
                      <button className="text-ink-500 hover:text-rose-300" onClick={() => void cancelJob(job)}>
                        <Icon name="close" size={11} />
                      </button>
                    </div>
                    <ProgressBar value={job.progress} />
                  </div>
                ))}
              </div>
            )}
            <ul className="divide-y divide-ink-700/60">
              {jobs.recent.map((job) => (
                <li key={job.id} className="flex items-center gap-2 px-3 py-1.5">
                  <span className={`rounded border px-1 py-0.5 text-[8.5px] uppercase tracking-wide ${statusTone(job.status)}`}>{job.status}</span>
                  <span className="min-w-0 flex-1 truncate text-[10.5px] text-ink-300">{job.kind}</span>
                  <span className="font-mono text-[9px] text-ink-500">{fmtWhen(job.created_at)}</span>
                </li>
              ))}
              {jobs.recent.length === 0 && <li className="p-3 text-[11px] text-ink-500">No background jobs yet.</li>}
            </ul>
          </div>
        </Panel>

        <Panel
          title="Benchmarks"
          subtitle="Deterministic CPU measurement across all modules"
          actions={
            <button className="btn-primary !px-2 !py-1 !text-[11px]" onClick={() => void runBenchmark()} disabled={Boolean(runningBench)}>
              <Icon name="play" size={11} /> Run
            </button>
          }
          bodyClass="p-0"
        >
          {runningBench && (
            <div className="border-b border-ink-700/60 p-3">
              <div className="mb-1 flex justify-between text-[10.5px] text-ink-400">
                <span>Running…</span>
                <span className="font-mono">{benchProgress}%</span>
              </div>
              <ProgressBar value={benchProgress} />
            </div>
          )}
          {latest ? (
            <div className="max-h-[220px] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-ink-700/60 px-3 py-1.5 text-[10px] text-ink-500">
                <span>{latest.created_at ? new Date(latest.created_at).toLocaleString() : "latest"}</span>
                <span className="font-mono">
                  {latest.modules_ok}/{latest.modules} ok · {latest.total_ms} ms
                </span>
              </div>
              <table className="w-full text-left text-[10px]">
                <thead className="text-ink-500">
                  <tr>
                    <th className="px-3 py-1 font-medium">Module</th>
                    <th className="px-2 py-1 text-right font-medium">ms</th>
                    <th className="px-3 py-1 text-right font-medium">peak MB</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-ink-300">
                  {(latest.results || []).map((row: any) => (
                    <tr key={row.module} className="border-t border-ink-700/40">
                      <td className={`px-3 py-0.5 ${row.error ? "text-rose-300" : ""}`} title={row.error || undefined}>
                        {row.module}
                      </td>
                      <td className="px-2 py-0.5 text-right">{row.ms}</td>
                      <td className="px-3 py-0.5 text-right">{row.peak_mb}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="p-3 text-[11px] text-ink-500">No benchmark recorded yet. Run one to capture timings for this machine.</p>
          )}
          <div className="border-t border-ink-700/60 p-2.5">
            <button className="btn-ghost w-full !py-1 !text-[11px]" onClick={() => void cleanup()} disabled={cleaning}>
              <Icon name="trash" size={12} /> {cleaning ? "Cleaning…" : "Clean temporary files & preview cache"}
            </button>
          </div>
        </Panel>
      </div>

      {benchmarks.length > 1 && (
        <Panel title="Benchmark history" className="mt-3" bodyClass="p-0">
          <table className="w-full text-left text-[10.5px]">
            <thead className="text-ink-500">
              <tr>
                <th className="px-3 py-1.5 font-medium">When</th>
                <th className="px-3 py-1.5 font-medium">Fixture</th>
                <th className="px-3 py-1.5 text-right font-medium">Modules</th>
                <th className="px-3 py-1.5 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-300">
              {benchmarks.map((b, i) => (
                <tr key={b.id || i} className="border-t border-ink-700/40">
                  <td className="px-3 py-1">{b.created_at ? new Date(b.created_at).toLocaleString() : "—"}</td>
                  <td className="px-3 py-1 text-ink-500">{b.source ? `${b.source.width}×${b.source.height} · ${b.source.fixture}` : "—"}</td>
                  <td className="px-3 py-1 text-right">
                    {b.modules_ok}/{b.modules}
                  </td>
                  <td className="px-3 py-1 text-right">{b.total_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <Modal
        open={paletteModal}
        title="New palette"
        onClose={() => setPaletteModal(false)}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setPaletteModal(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={() => void createPalette()}>
              <Icon name="plus" size={13} /> Create palette
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="Name">
            <input className="field" autoFocus value={paletteName} onChange={(e) => setPaletteName(e.target.value)} placeholder="e.g. Moonlit ruins" />
          </Field>
          <Field label="Colours" hint="hex, comma separated · max 256">
            <textarea className="field min-h-[80px] font-mono text-[11px]" value={paletteColors} onChange={(e) => setPaletteColors(e.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-1">
            {paletteColors
              .split(/[\s,;]+/)
              .filter(Boolean)
              .slice(0, 64)
              .map((c, i) => (
                <span
                  key={`${c}-${i}`}
                  className="h-5 w-5 rounded border border-black/50"
                  style={{ background: c.startsWith("#") ? c : `#${c}` }}
                  title={c}
                />
              ))}
          </div>
          <Toggle
            label="Limit to active project"
            hint="Project palettes appear in that project only; otherwise the palette is available everywhere"
            checked={paletteShared}
            onChange={setPaletteShared}
          />
        </div>
      </Modal>
    </div>
    </Localize>
  );
}
