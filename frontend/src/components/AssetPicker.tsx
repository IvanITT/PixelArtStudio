import { useMemo, useRef, useState } from "react";
import type { Asset } from "../api/types";
import { mediaUrl } from "../api/client";
import { Localize } from "../i18n";
import { Icon } from "./Icon";

export function DropZone({
  onFile,
  hint = "PNG, JPEG, WebP, BMP or GIF · processed locally",
  compact,
}: {
  onFile: (file: File) => void;
  hint?: string;
  compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <Localize>
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      onClick={() => input.current?.click()}
      className={`group flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed text-center transition ${
        over
          ? "border-[rgb(var(--accent))] bg-[rgb(var(--accent))]/10"
          : "border-ink-600 bg-ink-900/60 hover:border-ink-500 hover:bg-ink-800/60"
      } ${compact ? "px-3 py-4" : "px-6 py-8"}`}
    >
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/bmp,image/gif"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      <Icon name="upload" size={compact ? 16 : 22} className="text-ink-400 group-hover:text-ink-200" />
      <p className="text-[11.5px] font-medium text-ink-200">Drop an image or click to browse</p>
      <p className="text-[10px] text-ink-500">{hint}</p>
    </div>
    </Localize>
  );
}

export function AssetPicker({
  assets,
  value,
  onChange,
  kinds,
  label = "Source image",
}: {
  assets: Asset[];
  value: string | null;
  onChange: (id: string) => void;
  kinds?: string[];
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const filtered = useMemo(() => {
    const pool = kinds ? assets.filter((a) => kinds.includes(a.kind)) : assets;
    const q = filter.trim().toLowerCase();
    return q ? pool.filter((a) => a.name.toLowerCase().includes(q) || a.kind.includes(q)) : pool;
  }, [assets, kinds, filter]);
  const selected = assets.find((a) => a.id === value) || null;

  return (
    <Localize>
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-md border border-ink-700 bg-ink-900 px-2 py-1.5 text-left transition hover:border-ink-600"
      >
        <span className="checker grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded border border-ink-700">
          {selected && <img src={mediaUrl(selected.thumb_url || selected.url)} alt="" className="h-full w-full object-contain pixelated" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[11.5px] text-ink-100">{selected ? selected.name : `Choose ${label.toLowerCase()}…`}</span>
          <span className="block truncate text-[10px] text-ink-500">
            {selected ? `${selected.kind} · ${selected.width}×${selected.height}` : `${filtered.length} available`}
          </span>
        </span>
        <Icon name="chevron" size={13} className={`text-ink-500 transition ${open ? "rotate-90" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-ink-600 bg-ink-850 shadow-panel">
          <div className="border-b border-ink-700 p-1.5">
            <input
              autoFocus
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter assets…"
              className="field !py-1 text-[11px]"
            />
          </div>
          <div className="max-h-[240px] overflow-y-auto p-1.5">
            {filtered.length === 0 && <p className="px-2 py-4 text-center text-[11px] text-ink-500">No compatible assets yet.</p>}
            {filtered.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => {
                  onChange(a.id);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 rounded px-1.5 py-1 text-left transition hover:bg-ink-750 ${
                  a.id === value ? "bg-[rgb(var(--accent))]/15" : ""
                }`}
              >
                <span className="checker grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded border border-ink-700">
                  <img src={mediaUrl(a.thumb_url || a.url)} alt="" className="h-full w-full object-contain pixelated" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] text-ink-100">{a.name}</span>
                  <span className="block text-[9.5px] text-ink-500">
                    {a.kind} · {a.width}×{a.height}
                  </span>
                </span>
                {a.id === value && <Icon name="check" size={12} className="text-[rgb(var(--accent))]" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
    </Localize>
  );
}
