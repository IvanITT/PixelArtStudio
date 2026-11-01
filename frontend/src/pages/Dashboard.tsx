import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText, mediaUrl } from "../api/client";
import type { SystemStats } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "../components/Icon";
import { Empty, Panel, ProgressBar, Stat, bytes } from "../components/ui";

const MODULES = [
  { to: "/pixelart", label: "Pixel Art Converter", icon: "pixel", desc: "Resize, quantize, dither and palette-lock images." },
  { to: "/sprites", label: "Sprite Extractor", icon: "sprites", desc: "Segment sheets into cropped sprites and pack them back." },
  { to: "/tileset", label: "Tileset Generator", icon: "tileset", desc: "Grid extraction, autotiles, seamless and recolor." },
  { to: "/procedural", label: "Procedural Assets", icon: "procedural", desc: "31 deterministic generators with palettes." },
  { to: "/false3d", label: "False 3D Lab", icon: "three_d", desc: "2.5D isometric, top-down and side projections." },
  { to: "/animation", label: "Animation Studio", icon: "animation", desc: "Templates, timeline, sheets, GIF and WebP." },
  { to: "/style", label: "Style Consistency", icon: "spark", desc: "Shared palettes, outlines and pixel scale across assets." },
];

export function Dashboard() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const project = useStudio((s) => s.project);
  const projects = useStudio((s) => s.projects);
  const assets = useStudio((s) => s.assets);
  const health = useStudio((s) => s.health);
  const notify = useStudio((s) => s.notify);
  const [benchmarking, setBenchmarking] = useState(false);

  const load = () => api.stats().then(setStats).catch(() => undefined);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(t);
  }, []);

  const runBenchmark = async () => {
    setBenchmarking(true);
    try {
      const { job_id } = await api.runBenchmarks();
      notify("Benchmark queued. Results appear when the job finishes.", "info");
      const poll = window.setInterval(async () => {
        try {
          const job = await api.job(job_id);
          if (["done", "error", "cancelled"].includes(job.status)) {
            window.clearInterval(poll);
            setBenchmarking(false);
            if (job.status === "done") notify("Benchmark finished", "success");
            else notify(job.error || "Benchmark failed", "error");
            void load();
          }
        } catch {
          window.clearInterval(poll);
          setBenchmarking(false);
        }
      }, 900);
    } catch (err) {
      setBenchmarking(false);
      notify(errorText(err), "error");
    }
  };

  const recent = assets.slice(0, 8);
  const counts = project?.asset_counts || {};

  return (
    <Localize>
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-[18px] font-semibold text-ink-50">Studio overview</h1>
          <p className="text-[11.5px] text-ink-400">
            {project ? `Working on “${project.name}”` : "Create a project to start producing assets"} · fully offline, CPU-only
          </p>
        </div>
        <Link to="/projects" className="btn-ghost">
          <Icon name="folder" size={14} /> Projects
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Projects" value={stats?.projects ?? projects.length} hint="local folders" />
        <Stat label="Assets" value={stats?.assets ?? 0} hint={bytes(stats?.data.total_bytes)} />
        <Stat
          label="Memory"
          value={`${stats?.memory.app_rss_mb ?? 0} MB`}
          hint={stats ? `${stats.memory.percent}% system used` : "engine"}
        />
        <Stat
          label="CPU"
          value={`${stats?.cpu.percent ?? 0}%`}
          hint={`${stats?.cpu.count ?? health?.cpu_count ?? 0} threads · ${stats?.workers ?? 4} workers`}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Panel title="Quick actions" subtitle="Every module writes real assets into the active project" bodyClass="p-3">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {MODULES.map((m) => (
                <Link
                  key={m.to}
                  to={m.to}
                  className="card-hover group flex items-start gap-2.5 rounded-lg border border-ink-700 bg-ink-800/50 p-2.5"
                >
                  <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md bg-ink-750 text-[rgb(var(--accent))] group-hover:bg-[rgb(var(--accent))]/15">
                    <Icon name={m.icon} size={15} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[11.5px] font-medium text-ink-100">{m.label}</span>
                    <span className="mt-0.5 block text-[10.5px] leading-snug text-ink-400">{m.desc}</span>
                  </span>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel
            title="Recent assets"
            subtitle={`${assets.length} in this project`}
            actions={
              <Link to="/library" className="text-[11px] text-[rgb(var(--accent))] hover:underline">
                Open library
              </Link>
            }
            bodyClass="p-3"
          >
            {recent.length === 0 ? (
              <Empty
                icon={<Icon name="library" size={22} />}
                title="No assets yet"
                hint="Import a source image from the top bar, then run it through any module."
              />
            ) : (
              <div className="grid grid-cols-4 gap-2 md:grid-cols-6 xl:grid-cols-8">
                {recent.map((a) => (
                  <div key={a.id} className="group overflow-hidden rounded-md border border-ink-700 bg-ink-900">
                    <div className="checker grid h-[64px] place-items-center overflow-hidden">
                      <img
                        src={mediaUrl(a.thumb_url || a.url)}
                        alt={a.name}
                        className="max-h-full max-w-full object-contain pixelated transition group-hover:scale-105"
                        loading="lazy"
                      />
                    </div>
                    <div className="px-1.5 py-1">
                      <p className="truncate text-[10px] text-ink-200">{a.name}</p>
                      <p className="truncate text-[9px] text-ink-500">{a.kind}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Project composition" bodyClass="p-3">
            {project ? (
              <div className="space-y-2.5">
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(counts).length === 0 && <span className="text-[11px] text-ink-500">No assets yet.</span>}
                  {Object.entries(counts).map(([kind, n]) => (
                    <span key={kind} className="chip">
                      {kind} <span className="font-mono text-ink-100">{n}</span>
                    </span>
                  ))}
                </div>
                <dl className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded-md bg-ink-800/60 p-2">
                    <dt className="text-ink-500">Animations</dt>
                    <dd className="font-mono text-ink-100">{project.animation_count}</dd>
                  </div>
                  <div className="rounded-md bg-ink-800/60 p-2">
                    <dt className="text-ink-500">Folder size</dt>
                    <dd className="font-mono text-ink-100">{bytes(project.size_bytes)}</dd>
                  </div>
                </dl>
                <p className="text-[10.5px] text-ink-500">
                  Updated {new Date(project.updated_at).toLocaleString()}
                </p>
              </div>
            ) : (
              <p className="text-[11px] text-ink-400">No active project. Create one in Projects.</p>
            )}
          </Panel>

          <Panel title="Engine" bodyClass="p-3">
            {health ? (
              <div className="space-y-2 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-ink-500">Platform</span>
                  <span className="max-w-[190px] truncate text-right text-ink-200">{health.platform}</span>
                </div>
                {Object.entries(health.versions).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-ink-500">{k}</span>
                    <span className="font-mono text-ink-200">{v}</span>
                  </div>
                ))}
                <div className="flex justify-between">
                  <span className="text-ink-500">Data folder</span>
                  <span className="max-w-[190px] truncate text-right font-mono text-[10px] text-ink-300">{health.data_dir}</span>
                </div>
                <div className="flex items-center gap-1.5 pt-1 text-emerald-400">
                  <Icon name="check" size={12} /> Offline mode active
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-ink-500">Waiting for engine…</p>
            )}
          </Panel>

          <Panel
            title="Benchmark"
            actions={
              <button type="button" className="btn-ghost !px-2 !py-1" onClick={() => void runBenchmark()} disabled={benchmarking}>
                <Icon name="play" size={12} /> {benchmarking ? "Running" : "Run"}
              </button>
            }
            bodyClass="p-3"
          >
            {stats?.benchmark ? (
              <div className="space-y-1.5">
                <p className="text-[10.5px] text-ink-500">
                  Last run {stats.benchmark.created_at ? new Date(stats.benchmark.created_at).toLocaleString() : ""}
                </p>
                <div className="space-y-1">
                  {(stats.benchmark.results || []).slice(0, 5).map((r: any) => (
                    <div key={r.name || r.id}>
                      <div className="flex justify-between text-[10.5px]">
                        <span className="text-ink-300">{r.name}</span>
                        <span className="font-mono text-ink-400">{Math.round(r.ms ?? r.duration_ms ?? 0)} ms</span>
                      </div>
                      <ProgressBar value={Math.min(100, (r.ms ?? r.duration_ms ?? 0) / 20)} />
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-[10.5px] leading-relaxed text-ink-500">
                Run the deterministic benchmark suite to measure this machine across all processing modules.
              </p>
            )}
          </Panel>
        </div>
      </div>
    </div>
    </Localize>
  );
}
