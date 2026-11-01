import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText, mediaUrl } from "../api/client";
import type { Project } from "../api/types";
import { useStudio } from "../store/studio";
import { Localize } from "../i18n";
import { Icon } from "../components/Icon";
import { Empty, Field, Modal, Panel, Spinner, bytes } from "../components/ui";

interface Backup {
  id: string;
  project_id: string;
  filename: string;
  note: string;
  created_at: string;
}

const CATEGORIES = ["General", "Platformer", "RPG", "Top-down", "Isometric", "UI", "Prototype"];

function fmtDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function Projects() {
  const projects = useStudio((s) => s.projects);
  const projectId = useStudio((s) => s.projectId);
  const refreshProjects = useStudio((s) => s.refreshProjects);
  const selectProject = useStudio((s) => s.selectProject);
  const notify = useStudio((s) => s.notify);
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [editing, setEditing] = useState<Project | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [formCategory, setFormCategory] = useState("General");
  const [busy, setBusy] = useState<string | null>(null);
  const [backupFor, setBackupFor] = useState<Project | null>(null);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loadingBackups, setLoadingBackups] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const categories = useMemo(() => {
    const set = new Set<string>(CATEGORIES);
    projects.forEach((p) => p.category && set.add(p.category));
    return Array.from(set).sort();
  }, [projects]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return projects.filter((p) => {
      if (category !== "all" && p.category !== category) return false;
      if (!q) return true;
      return p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q) || p.category.toLowerCase().includes(q);
    });
  }, [projects, search, category]);

  useEffect(() => {
    if (!backupFor) return;
    setLoadingBackups(true);
    api
      .backups(backupFor.id)
      .then(setBackups)
      .catch((err) => notify(errorText(err), "error"))
      .finally(() => setLoadingBackups(false));
  }, [backupFor, notify]);

  const openProject = async (project: Project) => {
    await selectProject(project.id);
    navigate("/");
  };

  const openCreate = () => {
    setEditing(null);
    setName("");
    setDescription("");
    setFormCategory("General");
    setCreating(true);
  };

  const openEdit = (project: Project) => {
    setEditing(project);
    setName(project.name);
    setDescription(project.description);
    setFormCategory(project.category);
    setCreating(true);
  };

  const submitForm = async () => {
    if (!name.trim()) {
      notify("Project name is required", "error");
      return;
    }
    setBusy("form");
    try {
      if (editing) {
        await api.updateProject(editing.id, { name: name.trim(), description, category: formCategory });
        await refreshProjects();
        notify("Project updated", "success");
      } else {
        const project = await api.createProject({ name: name.trim(), description, category: formCategory });
        await refreshProjects();
        await selectProject(project.id);
        notify(`Created “${project.name}”`, "success");
      }
      setCreating(false);
      setEditing(null);
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const duplicate = async (project: Project) => {
    setBusy(project.id);
    try {
      const copy = await api.duplicateProject(project.id);
      await refreshProjects();
      notify(`Duplicated as “${copy.name}”`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (project: Project) => {
    if (!window.confirm(`Delete “${project.name}” and every asset, frame and export inside it?\n\nThis cannot be undone.`)) return;
    setBusy(project.id);
    try {
      await api.deleteProject(project.id);
      await refreshProjects();
      if (project.id === projectId) {
        const remaining = useStudio.getState().projects;
        await selectProject(remaining[0]?.id || null);
      }
      notify("Project deleted", "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const toggleFavorite = async (project: Project) => {
    try {
      await api.updateProject(project.id, { favorite: !project.favorite });
      await refreshProjects();
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const saveVersion = async (project: Project) => {
    setBusy(project.id);
    try {
      const res = await api.saveProject(project.id, "manual");
      await refreshProjects();
      if (backupFor?.id === project.id) {
        const list = await api.backups(project.id);
        setBackups(list);
      }
      notify(res.backup ? "Version snapshot saved" : "Project saved", "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
    }
  };

  const restore = async (backup: Backup) => {
    if (!backupFor) return;
    if (!window.confirm(`Restore the snapshot from ${fmtDate(backup.created_at)}?\n\nCurrent state will be replaced; a fresh snapshot of it is taken first.`)) return;
    try {
      await api.saveProject(backupFor.id, "pre-restore");
      await api.restoreBackup(backupFor.id, backup.id);
      await refreshProjects();
      if (backupFor.id === projectId) await selectProject(backupFor.id);
      const list = await api.backups(backupFor.id);
      setBackups(list);
      notify("Snapshot restored", "success");
    } catch (err) {
      notify(errorText(err), "error");
    }
  };

  const importProject = async (file?: File | null) => {
    if (!file) return;
    setBusy("import");
    try {
      const project = await api.importProject(file);
      await refreshProjects();
      await selectProject(project.id);
      notify(`Imported “${project.name}”`, "success");
    } catch (err) {
      notify(errorText(err), "error");
    } finally {
      setBusy(null);
      if (importRef.current) importRef.current.value = "";
    }
  };

  return (
    <Localize>
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-ink-700/70 px-3 py-2">
        <input className="field !w-[200px] !py-1" placeholder="Search projects…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="field !w-auto !py-1" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <span className="text-[10.5px] text-ink-500">
          {visible.length} of {projects.length} projects
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <input
            ref={importRef}
            type="file"
            accept=".zip,.pasproject.zip,application/zip"
            className="hidden"
            onChange={(e) => void importProject(e.target.files?.[0])}
          />
          <button className="btn-ghost !py-1" onClick={() => importRef.current?.click()} disabled={busy === "import"}>
            <Icon name="upload" size={13} /> Import .zip
          </button>
          <button className="btn-primary !py-1" onClick={openCreate}>
            <Icon name="plus" size={13} /> New project
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {visible.length === 0 ? (
          <Empty
            icon={<Icon name="projects" size={24} />}
            title={projects.length === 0 ? "No projects yet" : "No projects match the filter"}
            hint="Projects keep their own assets, palette locks, layer state, animations and version snapshots. Create one to start producing sprites."
            action={
              <button className="btn-primary mt-1" onClick={openCreate}>
                <Icon name="plus" size={13} /> Create project
              </button>
            }
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visible.map((project) => {
              const active = project.id === projectId;
              return (
                <article
                  key={project.id}
                  className={`flex flex-col overflow-hidden rounded-xl border bg-ink-850 transition ${
                    active ? "border-[rgb(var(--accent))] shadow-glow" : "border-ink-700 hover:border-ink-600"
                  }`}
                >
                  <div className="checker relative h-[132px] overflow-hidden">
                    {project.thumbnail_url ? (
                      <img src={mediaUrl(project.thumbnail_url)} alt="" className="h-full w-full object-cover pixelated opacity-90" />
                    ) : (
                      <div className="grid h-full place-items-center text-ink-600">
                        <Icon name="projects" size={30} />
                      </div>
                    )}
                    <span className="absolute left-2 top-2 rounded bg-black/70 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-ink-300">
                      {project.category || "General"}
                    </span>
                    {active && (
                      <span className="absolute right-2 top-2 rounded bg-[rgb(var(--accent))] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-white">
                        Active
                      </span>
                    )}
                    {busy === project.id && (
                      <span className="absolute inset-0 grid place-items-center bg-black/55">
                        <Spinner />
                      </span>
                    )}
                  </div>

                  <div className="flex items-start gap-2 px-3 pt-2">
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-[12.5px] font-semibold text-ink-100" title={project.name}>
                        {project.name}
                      </h3>
                      <p className="line-clamp-2 min-h-[26px] text-[10.5px] leading-[1.35] text-ink-400">{project.description || "No description"}</p>
                    </div>
                    <button
                      type="button"
                      className={`mt-0.5 ${project.favorite ? "text-amber-400" : "text-ink-500 hover:text-ink-300"}`}
                      onClick={() => void toggleFavorite(project)}
                      title={project.favorite ? "Remove from favorites" : "Mark as favorite"}
                    >
                      <Icon name="star" size={14} />
                    </button>
                  </div>

                  <div className="grid grid-cols-3 gap-1 px-3 py-2 text-center">
                    <div className="rounded bg-ink-800/70 py-1">
                      <p className="font-mono text-[12px] text-ink-100">{project.asset_count}</p>
                      <p className="text-[9px] uppercase tracking-wide text-ink-500">assets</p>
                    </div>
                    <div className="rounded bg-ink-800/70 py-1">
                      <p className="font-mono text-[12px] text-ink-100">{project.animation_count}</p>
                      <p className="text-[9px] uppercase tracking-wide text-ink-500">anims</p>
                    </div>
                    <div className="rounded bg-ink-800/70 py-1">
                      <p className="font-mono text-[12px] text-ink-100">{bytes(project.size_bytes)}</p>
                      <p className="text-[9px] uppercase tracking-wide text-ink-500">on disk</p>
                    </div>
                  </div>

                  <p className="px-3 pb-1.5 font-mono text-[9.5px] text-ink-500">Updated {fmtDate(project.updated_at)}</p>

                  <div className="mt-auto flex flex-wrap items-center gap-1 border-t border-ink-700/70 px-2 py-1.5">
                    <button className="btn-primary !px-2 !py-1 !text-[11px]" onClick={() => void openProject(project)}>
                      <Icon name="folder" size={12} /> Open
                    </button>
                    <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => openEdit(project)} title="Rename / describe">
                      <Icon name="settings" size={12} />
                    </button>
                    <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => void duplicate(project)} title="Duplicate project">
                      <Icon name="copy" size={12} />
                    </button>
                    <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => void saveVersion(project)} title="Save snapshot">
                      <Icon name="save" size={12} />
                    </button>
                    <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => setBackupFor(project)} title="Version history">
                      <Icon name="refresh" size={12} />
                    </button>
                    <a className="btn-ghost !px-2 !py-1 !text-[11px]" href={api.exportProjectUrl(project.id)} title="Export project ZIP">
                      <Icon name="download" size={12} />
                    </a>
                    <button className="btn-danger ml-auto !px-2 !py-1 !text-[11px]" onClick={() => void remove(project)} title="Delete project">
                      <Icon name="trash" size={12} />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <Modal
        open={creating}
        title={editing ? `Edit “${editing.name}”` : "New project"}
        onClose={() => setCreating(false)}
        footer={
          <>
            <button className="btn-ghost" onClick={() => setCreating(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={() => void submitForm()} disabled={busy === "form" || !name.trim()}>
              <Icon name={editing ? "save" : "plus"} size={13} /> {editing ? "Save" : "Create project"}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="Name" hint={`${name.length}/100`}>
            <input className="field" maxLength={100} autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Moonlit Ruins" />
          </Field>
          <Field label="Category">
            <select className="field" value={formCategory} onChange={(e) => setFormCategory(e.target.value)}>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Description" hint={`${description.length}/300`}>
            <textarea
              className="field min-h-[80px] resize-y"
              maxLength={300}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Palette rules, camera angle, engine target…"
            />
          </Field>
          {!editing && (
            <p className="text-[10.5px] leading-relaxed text-ink-500">
              The project gets its own folder under the local data directory, an empty workspace state and its own palette locks and
              version snapshots. Nothing leaves this machine.
            </p>
          )}
        </div>
      </Modal>

      <Modal
        open={Boolean(backupFor)}
        title={`Version history — ${backupFor?.name || ""}`}
        onClose={() => setBackupFor(null)}
        wide
        footer={
          <>
            <button className="btn-ghost" onClick={() => setBackupFor(null)}>
              Close
            </button>
            <button
              className="btn-primary"
              disabled={!backupFor}
              onClick={() => {
                if (backupFor) void saveVersion(backupFor);
              }}
            >
              <Icon name="save" size={13} /> Snapshot now
            </button>
          </>
        }
      >
        <Panel title="Snapshots" subtitle="Autosaves keep the newest 15 per project" bodyClass="p-0">
          {loadingBackups ? (
            <div className="p-3">
              <Spinner label="Loading snapshots…" />
            </div>
          ) : backups.length === 0 ? (
            <p className="p-3 text-[11px] text-ink-500">No snapshots yet. Save the project (Ctrl+S) to create one.</p>
          ) : (
            <ul className="max-h-[46vh] divide-y divide-ink-700/70 overflow-y-auto">
              {backups.map((b) => (
                <li key={b.id} className="flex items-center gap-3 px-3 py-2">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded bg-ink-800 text-ink-400">
                    <Icon name="save" size={13} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[11.5px] text-ink-200">{fmtDate(b.created_at)}</p>
                    <p className="truncate font-mono text-[9.5px] text-ink-500">
                      {b.note} · {b.filename}
                    </p>
                  </div>
                  <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => void restore(b)}>
                    <Icon name="refresh" size={12} /> Restore
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </Modal>
    </div>
    </Localize>
  );
}
