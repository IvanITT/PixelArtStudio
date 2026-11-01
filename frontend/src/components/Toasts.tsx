import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "./Icon";

export function Toasts() {
  const toasts = useStudio((s) => s.toasts);
  const dismiss = useStudio((s) => s.dismiss);
  return (
    <Localize>
    <div className="pointer-events-none fixed bottom-8 right-4 z-[60] flex w-[320px] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2 text-[11.5px] shadow-panel animate-fade-in ${
            t.kind === "error"
              ? "border-rose-800/80 bg-rose-950/90 text-rose-100"
              : t.kind === "success"
                ? "border-emerald-800/80 bg-emerald-950/90 text-emerald-100"
                : "border-ink-600 bg-ink-800/95 text-ink-100"
          }`}
        >
          <Icon name={t.kind === "error" ? "info" : "check"} size={14} className="mt-0.5 shrink-0" />
          <span className="flex-1 leading-snug">{t.message}</span>
          <button type="button" onClick={() => dismiss(t.id)} className="text-current/60 hover:text-current">
            <Icon name="close" size={12} />
          </button>
        </div>
      ))}
    </div>
    </Localize>
  );
}
