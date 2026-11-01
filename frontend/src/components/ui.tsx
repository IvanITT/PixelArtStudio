import type { ReactNode } from "react";
import { useEffect } from "react";

export function Panel({
  title,
  actions,
  children,
  className = "",
  bodyClass = "p-3",
  subtitle,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
  subtitle?: ReactNode;
}) {
  return (
    <section className={`panel flex min-h-0 flex-col ${className}`}>
      {(title || actions) && (
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-ink-700/70 px-3 py-2">
          <div className="min-w-0">
            {title && <h2 className="truncate text-[12.5px] font-semibold text-ink-100">{title}</h2>}
            {subtitle && <p className="truncate text-[10.5px] text-ink-400">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={`min-h-0 ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="label">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium text-ink-300">{label}</span>
        {hint && <span className="font-mono text-[10px] text-ink-500">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

export function Slider({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  suffix = "",
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  suffix?: string;
}) {
  return (
    <Field label={label} hint={`${value}${suffix}`}>
      <input
        type="range"
        className="w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Field>
  );
}

export function Select({
  label,
  value,
  options,
  onChange,
}: {
  label?: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  const control = (
    <select className="field" value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
  return label ? <Field label={label}>{control}</Field> : control;
}

export function Toggle({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between gap-3 rounded-md px-0.5 py-1 text-left"
    >
      <span>
        <span className="block text-[11.5px] text-ink-200">{label}</span>
        {hint && <span className="block text-[10px] text-ink-500">{hint}</span>}
      </span>
      <span
        className={`relative h-[18px] w-[32px] shrink-0 rounded-full border transition ${
          checked
            ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/85"
            : "border-ink-600 bg-ink-800"
        }`}
      >
        <span
          className={`absolute top-[2px] h-[12px] w-[12px] rounded-full bg-white transition-all ${
            checked ? "left-[16px]" : "left-[2px]"
          }`}
        />
      </span>
    </button>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  size = "md",
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex rounded-md border border-ink-700 bg-ink-900 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`rounded px-2 transition ${
            size === "sm" ? "py-[3px] text-[10.5px]" : "py-1 text-[11.5px]"
          } ${
            value === o.value
              ? "bg-ink-700 text-ink-50 shadow-sm"
              : "text-ink-400 hover:text-ink-200"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-ink-400">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink-600 border-t-[rgb(var(--accent))]" />
      {label}
    </div>
  );
}

export function Empty({ icon, title, hint, action }: { icon?: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-ink-700 bg-ink-900/40 p-6 text-center">
      {icon && <div className="text-ink-500">{icon}</div>}
      <p className="text-[12.5px] font-medium text-ink-200">{title}</p>
      {hint && <p className="max-w-[380px] text-[11px] leading-relaxed text-ink-400">{hint}</p>}
      {action}
    </div>
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-6 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        className={`panel max-h-[86vh] w-full overflow-hidden shadow-panel animate-fade-in ${wide ? "max-w-4xl" : "max-w-lg"}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
          <h2 className="text-[13px] font-semibold">{title}</h2>
          <button type="button" className="text-ink-400 hover:text-ink-100" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="max-h-[62vh] overflow-y-auto p-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-ink-700 px-4 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg border border-ink-700/80 bg-ink-800/60 px-3 py-2">
      <p className="label">{label}</p>
      <p className="mt-0.5 font-mono text-[15px] text-ink-100">{value}</p>
      {hint && <p className="text-[10px] text-ink-500">{hint}</p>}
    </div>
  );
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
      <div
        className="h-full rounded-full bg-[rgb(var(--accent))] transition-all"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

export function bytes(n: number | undefined | null): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
