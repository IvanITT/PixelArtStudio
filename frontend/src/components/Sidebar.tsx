import { NavLink } from "react-router-dom";
import { Icon } from "./Icon";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";

const NAV = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/pixelart", label: "Image → Pixel Art", icon: "pixel" },
  { to: "/sprites", label: "Sprite Extractor", icon: "sprites" },
  { to: "/tileset", label: "Tileset Generator", icon: "tileset" },
  { to: "/procedural", label: "Procedural", icon: "procedural" },
  { to: "/false3d", label: "False 3D", icon: "three_d" },
  { to: "/animation", label: "Animation", icon: "animation" },
  { to: "/library", label: "Asset Library", icon: "library" },
  { to: "/style", label: "Style Consistency", icon: "spark" },
  { to: "/projects", label: "Projects", icon: "projects" },
  { to: "/settings", label: "Settings", icon: "settings" },
];

export function Sidebar() {
  const project = useStudio((s) => s.project);
  const health = useStudio((s) => s.health);

  return (
    <Localize>
    <aside className="flex w-[212px] shrink-0 flex-col border-r border-ink-700/80 bg-ink-900">
      <div className="flex h-[52px] items-center gap-2 border-b border-ink-700/80 px-3.5">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-[rgb(var(--accent))] text-white shadow-glow">
          <Icon name="pixel" size={16} />
        </div>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-[12px] font-semibold tracking-wide">PIXEL STUDIO</p>
          <p className="truncate text-[9.5px] text-ink-500">Offline asset toolkit</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `group flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[12px] transition ${
                isActive
                  ? "bg-[rgb(var(--accent))]/15 text-[rgb(var(--accent))] ring-1 ring-inset ring-[rgb(var(--accent))]/25"
                  : "text-ink-300 hover:bg-ink-800 hover:text-ink-100"
              }`
            }
          >
            <Icon name={item.icon} size={15} />
            <span className="truncate">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="space-y-2 border-t border-ink-700/80 p-2.5">
        <div className="rounded-md border border-ink-700 bg-ink-850 px-2.5 py-2">
          <p className="label">Active project</p>
          <p className="mt-0.5 truncate text-[11.5px] text-ink-200">{project ? project.name : "No project"}</p>
          <p className="mt-0.5 text-[10px] text-ink-500">
            {project ? `${project.asset_count} assets · ${project.animation_count} anims` : "Create one to begin"}
          </p>
        </div>
        <div className="flex items-center justify-between px-1 text-[10px] text-ink-500">
          <span className="inline-flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${health ? "bg-emerald-400" : "bg-rose-400"}`} />
            {health ? "Local · offline" : "API offline"}
          </span>
          <span className="font-mono">v1.0</span>
        </div>
      </div>
    </aside>
    </Localize>
  );
}
