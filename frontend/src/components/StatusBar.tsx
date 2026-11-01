import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { SystemStats } from "../api/types";
import { bytes } from "./ui";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";

export function StatusBar() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const health = useStudio((s) => s.health);
  const lastSaveAt = useStudio((s) => s.lastSaveAt);
  const project = useStudio((s) => s.project);

  useEffect(() => {
    let alive = true;
    const load = () => {
      api
        .stats()
        .then((s) => {
          if (alive) setStats(s);
        })
        .catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 12000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const active = stats?.active_jobs?.length || 0;

  return (
    <Localize>
    <footer className="flex h-[26px] shrink-0 items-center gap-4 border-t border-ink-700/80 bg-ink-950 px-3 text-[10.5px] text-ink-500">
      <span className={`inline-flex items-center gap-1.5 ${health ? "text-emerald-400" : "text-rose-400"}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${health ? "bg-emerald-400" : "bg-rose-400"}`} />
        {health ? "Engine online" : "Engine offline"}
      </span>
      <span className="font-mono">
        CPU {stats?.cpu.percent ?? 0}% · {stats?.cpu.count ?? health?.cpu_count ?? "–"} threads
      </span>
      <span className="font-mono">
        RAM {stats ? `${stats.memory.app_rss_mb} / ${stats.memory.total_mb} MB` : "–"}
      </span>
      <span className="font-mono">Data {stats ? bytes(stats.data.total_bytes) : "–"}</span>
      <span className="ml-auto inline-flex items-center gap-1.5">
        {active > 0 && (
          <span className="inline-flex items-center gap-1 text-[rgb(var(--accent))]">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[rgb(var(--accent))]" />
            {active} job{active > 1 ? "s" : ""} running
          </span>
        )}
        {project && <span className="max-w-[180px] truncate">{project.name}</span>}
        <span className="font-mono">{lastSaveAt ? `saved ${new Date(lastSaveAt).toLocaleTimeString()}` : "not saved yet"}</span>
        <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-ink-400">{health?.python ?? "py"}</span>
      </span>
    </footer>
    </Localize>
  );
}
