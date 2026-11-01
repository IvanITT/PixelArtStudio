import { useEffect, useMemo, useState } from "react";
import { api, errorText, mediaUrl } from "../api/client";
import type { CatalogItem, ParamSpec } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "../components/Icon";
import { Empty, Panel, Slider, Spinner, Toggle } from "../components/ui";

export function Procedural() {
  const projectId = useStudio((s) => s.projectId);
  const palettes = useStudio((s) => s.palettes);
  const refreshAssets = useStudio((s) => s.refreshAssets);
  const notify = useStudio((s) => s.notify);

  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [group, setGroup] = useState("all");
  const [generator, setGenerator] = useState<string>("tree");
  const [params, setParams] = useState<Record<string, any>>({});
  const [seed, setSeed] = useState(1337);
  const [count, setCount] = useState(4);
  const [save, setSave] = useState(true);
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<{ asset: any; info: Record<string, any>; url: string; seed: number }[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api
      .catalog()
      .then((c) => {
        setCatalog(c);
        const first = c.find((g) => g.id === "tree") || c[0];
        if (first) {
          setGenerator(first.id);
          setParams(Object.fromEntries(first.params.map((p) => [p.name, p.default])));
        }
      })
      .catch((err) => notify(errorText(err), "error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const groups = useMemo(() => {
    const map = new Map<string, string>();
    catalog.forEach((c) => map.set(c.group, c.group_label));
    return Array.from(map.entries());
  }, [catalog]);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return catalog.filter(
      (c) => (group === "all" || c.group === group) && (!q || c.name.toLowerCase().includes(q) || c.id.includes(q)),
    );
  }, [catalog, group, filter]);

  const active = catalog.find((c) => c.id === generator) || null;

  const choose = (item: CatalogItem) => {
    setGenerator(item.id);
    setParams(Object.fromEntries(item.params.map((p) => [p.name, p.default])));
    setItems([]);
  };

  const setParam = (name: string, value: any) => setParams((p) => ({ ...p, [name]: value }));

  const generate = async () => {
    if (!projectId) return;
    setBusy(true);
    try {
      const res = await api.generate({
        project_id: projectId,
        generator,
        params,
        seed,
        count,
        save,
        name: active ? `${active.name} ${seed}` : undefined,
      });
      setItems(res.items);
      if (save) await refreshAssets();
      notify(`Generated ${res.count} ${active?.name || "asset"} variant${res.count === 1 ? "" : "s"}`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const renderParam = (p: ParamSpec) => {
    const value = params[p.name] ?? p.default;
    if (p.type === "bool") {
      return <Toggle key={p.name} label={p.label} checked={Boolean(value)} onChange={(v) => setParam(p.name, v)} />;
    }
    if (p.type === "select") {
      return (
        <label key={p.name} className="block space-y-1">
          <span className="text-[11px] text-ink-300">{p.label}</span>
          <select className="field" value={String(value)} onChange={(e) => setParam(p.name, e.target.value)}>
            {(p.options || []).map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (p.type === "palette") {
      return (
        <label key={p.name} className="block space-y-1">
          <span className="text-[11px] text-ink-300">{p.label}</span>
          <select className="field" value={String(value || "")} onChange={(e) => setParam(p.name, e.target.value)}>
            <option value="">None (free colors)</option>
            {palettes.map((pal) => (
              <option key={pal.id} value={pal.id}>
                {pal.name}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (p.type === "color") {
      return (
        <label key={p.name} className="flex items-center justify-between text-[11px] text-ink-300">
          {p.label}
          <input type="color" value={String(value || "#ffffff")} onChange={(e) => setParam(p.name, e.target.value)} className="h-6 w-10" />
        </label>
      );
    }
    if ((p.type === "int" || p.type === "float") && p.min !== undefined && p.min !== null && p.max !== null && p.max !== undefined) {
      return (
        <Slider
          key={p.name}
          label={p.label}
          value={Number(value)}
          min={Number(p.min)}
          max={Number(p.max)}
          step={p.type === "float" ? p.step || 0.01 : p.step || 1}
          onChange={(v) => setParam(p.name, v)}
        />
      );
    }
    if (p.type === "int" || p.type === "float") {
      return (
        <label key={p.name} className="block space-y-1">
          <span className="text-[11px] text-ink-300">{p.label}</span>
          <input
            type="number"
            className="field"
            value={Number(value)}
            step={p.type === "float" ? 0.01 : 1}
            onChange={(e) => setParam(p.name, Number(e.target.value))}
          />
        </label>
      );
    }
    return (
      <label key={p.name} className="block space-y-1">
        <span className="text-[11px] text-ink-300">{p.label}</span>
        <input className="field" value={String(value ?? "")} onChange={(e) => setParam(p.name, e.target.value)} />
      </label>
    );
  };

  return (
    <Localize>
    <div className="grid h-full min-h-0 grid-cols-[248px_1fr_292px]">
      <div className="flex min-h-0 flex-col border-r border-ink-700/70">
        <div className="space-y-2 border-b border-ink-700/70 p-2.5">
          <input className="field !py-1" placeholder="Search generators…" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <select className="field !py-1" value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="all">All groups ({catalog.length})</option>
            {groups.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
          {visible.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => choose(c)}
              className={`mb-0.5 flex w-full items-center justify-between rounded px-2 py-1.5 text-left transition ${
                generator === c.id ? "bg-[rgb(var(--accent))]/15 text-[rgb(var(--accent))]" : "text-ink-300 hover:bg-ink-800 hover:text-ink-100"
              }`}
            >
              <span className="truncate text-[11.5px]">{c.name}</span>
              <span className="font-mono text-[9px] text-ink-600">{c.id}</span>
            </button>
          ))}
          {visible.length === 0 && <p className="p-3 text-center text-[11px] text-ink-500">No generators match.</p>}
        </div>
        <div className="border-t border-ink-700/70 p-2.5 text-[10px] text-ink-500">
          {catalog.length} deterministic generators · CPU only
        </div>
      </div>

      <div className="min-h-0 overflow-y-auto p-3">
        {busy && <Spinner label="Rendering variants" />}
        {!busy && items.length === 0 && (
          <Empty
            icon={<Icon name="procedural" size={24} />}
            title={active ? `Generate ${active.name.toLowerCase()}` : "Choose a generator"}
            hint="Pick a generator, adjust parameters, and produce a seeded family of game-ready assets."
          />
        )}
        {items.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-850 px-3 py-2">
              <div>
                <p className="text-[12px] font-medium text-ink-100">{active?.name}</p>
                <p className="text-[10px] text-ink-500">
                  seed {items[0]?.seed}–{items[items.length - 1]?.seed} · {items.length} variants · {save ? "saved to project" : "preview only"}
                </p>
              </div>
              <button className="btn-ghost !py-1" onClick={() => void generate()}>
                <Icon name="refresh" size={12} /> Reroll
              </button>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-2">
              {items.map((item) => (
                <div key={item.seed} className="overflow-hidden rounded-lg border border-ink-700 bg-ink-850">
                  <div className="checker grid h-[168px] place-items-center overflow-hidden">
                    <img src={mediaUrl(item.url)} alt={`variant ${item.seed}`} className="max-h-[160px] max-w-full object-contain pixelated" />
                  </div>
                  <div className="px-2 py-1.5">
                    <p className="truncate text-[10.5px] text-ink-200">{item.asset?.name || `${active?.name} ${item.seed}`}</p>
                    <p className="font-mono text-[9px] text-ink-500">
                      seed {item.seed} · {item.info?.width}×{item.info?.height}
                    </p>
                    <div className="mt-1 flex gap-1">
                      {item.asset && (
                        <a className="text-[9.5px] text-[rgb(var(--accent))] hover:underline" href={item.asset.download_url}>
                          Download
                        </a>
                      )}
                      <button
                        className="ml-auto text-[9.5px] text-ink-400 hover:text-ink-100"
                        onClick={() => {
                          navigator.clipboard?.writeText(String(item.seed));
                          notify(`Seed ${item.seed} copied`, "info");
                        }}
                      >
                        Copy seed
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 space-y-2 overflow-y-auto border-l border-ink-700/70 p-3">
        <Panel title={active ? active.name : "Generator"} subtitle={active ? `${active.group_label} · ${active.id}` : undefined} bodyClass="p-3 space-y-2.5">
          {active?.params.map(renderParam)}
          <div className="flex items-center gap-1.5 border-t border-ink-700/70 pt-2">
            <button className="btn-ghost !px-2 !py-1" onClick={() => setSeed(Math.floor(Math.random() * 9999) + 1)} title="Random seed">
              <Icon name="spark" size={13} />
            </button>
            <label className="flex flex-1 items-center gap-1.5 text-[10.5px] text-ink-400">
              Seed
              <input type="number" className="field !py-1" value={seed} onChange={(e) => setSeed(Number(e.target.value) || 1)} />
            </label>
          </div>
          <Slider label="Variants" value={count} min={1} max={12} onChange={setCount} />
          <Toggle label="Save to project" checked={save} onChange={setSave} hint="Creates procedural assets with metadata" />
          <button className="btn-primary w-full" onClick={() => void generate()} disabled={busy || !projectId}>
            <Icon name="spark" size={14} /> {busy ? "Generating…" : "Generate"}
          </button>
        </Panel>

        <Panel title="Seed family" bodyClass="p-3 space-y-1">
          <p className="text-[10px] leading-relaxed text-ink-500">
            Variants use consecutive seeds. The same seed and parameters always produce identical pixels on this machine.
          </p>
          {["tree", "rock", "potion", "sword"].map((g) => (
            <button key={g} className="chip w-full justify-between hover:text-ink-100" onClick={() => choose(catalog.find((c) => c.id === g) || (active as CatalogItem))}>
              <span>{catalog.find((c) => c.id === g)?.name || g}</span>
              <Icon name="chevron" size={10} />
            </button>
          ))}
        </Panel>
      </div>
    </div>
    </Localize>
  );
}
