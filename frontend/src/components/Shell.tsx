import { useEffect } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { StatusBar } from "./StatusBar";
import { Toasts } from "./Toasts";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "./Icon";

export function Shell() {
  const fatal = useStudio((s) => s.fatal);
  const booting = useStudio((s) => s.booting);
  const bootstrap = useStudio((s) => s.bootstrap);
  const save = useStudio((s) => s.save);
  const autosaveSeconds = useStudio((s) => s.settings?.autosave_seconds ?? 0);
  const projectId = useStudio((s) => s.projectId);
  const navigate = useNavigate();

  useEffect(() => {
    if (!projectId || !autosaveSeconds || autosaveSeconds <= 0) return;
    const timer = window.setInterval(() => void save("autosave"), autosaveSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [projectId, autosaveSeconds, save]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const key = e.key.toLowerCase();
      if (key === "s") {
        e.preventDefault();
        void save("manual");
      } else if (key === "u") {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent("pas:import"));
      } else if (key === "k") {
        e.preventDefault();
        navigate("/library");
      } else if (key === "z" || key === "y") {
        const target = document.activeElement;
        if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
        window.dispatchEvent(new CustomEvent(`pas:${key === "z" && e.shiftKey ? "redo" : key}`));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save, navigate]);

  if (booting) {
    return (
      <Localize>
      <div className="grid h-full place-items-center bg-ink-950">
        <div className="flex flex-col items-center gap-4">
          <div className="grid h-12 w-12 animate-pulse place-items-center rounded-xl bg-[rgb(var(--accent))] text-white">
            <Icon name="pixel" size={26} />
          </div>
          <p className="text-[12px] text-ink-400">Starting local engine…</p>
          <div className="h-1 w-40 overflow-hidden rounded bg-ink-800">
            <div className="h-full w-1/2 animate-shimmer bg-[linear-gradient(90deg,transparent,rgb(var(--accent)),transparent)] bg-[length:200%_100%]" />
          </div>
        </div>
      </div>
      </Localize>
    );
  }

  if (fatal) {
    return (
      <Localize>
      <div className="grid h-full place-items-center bg-ink-950 p-8">
        <div className="panel max-w-lg p-6">
          <div className="mb-3 flex items-center gap-2 text-rose-400">
            <Icon name="info" size={18} />
            <h1 className="text-[14px] font-semibold">Engine unavailable</h1>
          </div>
          <p className="text-[12px] leading-relaxed text-ink-300">{fatal}</p>
          <p className="mt-3 text-[11.5px] leading-relaxed text-ink-500">
            This app runs fully offline on your machine. Start the backend with <code className="rounded bg-ink-800 px-1">start.bat</code>{" "}
            (or <code className="rounded bg-ink-800 px-1">run_dev.bat</code> while developing) and retry.
          </p>
          <button type="button" className="btn-primary mt-4" onClick={() => void bootstrap()}>
            <Icon name="refresh" size={14} /> Retry connection
          </button>
        </div>
      </div>
      </Localize>
    );
  }

  return (
    <Localize>
    <div className="flex h-full min-w-[1024px] flex-col bg-ink-950">
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="min-h-0 flex-1 overflow-hidden">
            <Outlet />
          </main>
        </div>
      </div>
      <StatusBar />
      <Toasts />
    </div>
    </Localize>
  );
}
