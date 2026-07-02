import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { projectsApi, type Project } from "../api/client";
import { filterVisibleProjects, PLATFORM_PROJECT, PORTFOLIO_DEMOS } from "../config/portfolio";
import ScoreRing from "../components/ScoreRing";
import WelcomeWizard from "../components/WelcomeWizard";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [portfolioProjects, setPortfolioProjects] = useState<Record<string, Project>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [creating, setCreating] = useState(false);
  const [projectAction, setProjectAction] = useState("");
  const [query, setQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState("active");
  const [wizardDismissed, setWizardDismissed] = useState(
    () => localStorage.getItem("wizard-dismissed") === "true"
  );

  const visibleProjects = useMemo(() => filterVisibleProjects(projects), [projects]);
  const activeProjects = useMemo(() => visibleProjects.filter((project) => !project.archived_at), [visibleProjects]);
  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return visibleProjects.filter((project) => {
      const matchesQuery = !needle || [project.name, project.slug, project.framework, project.language]
        .some((value) => value.toLowerCase().includes(needle));
      if (!matchesQuery) return false;
      if (projectFilter === "archived") return Boolean(project.archived_at);
      if (project.archived_at) return false;
      if (projectFilter === "running") return project.last_run_status === "running";
      if (projectFilter === "ready") return (project.latest_readiness_score ?? 0) >= 90;
      if (projectFilter === "attention") return (project.latest_readiness_score ?? 0) < 90;
      return true;
    });
  }, [visibleProjects, query, projectFilter]);

  const stats = useMemo(() => {
    const scores = activeProjects
      .map((p) => p.latest_readiness_score)
      .filter((s): s is number => typeof s === "number");
    const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
    const running = activeProjects.filter((p) => p.last_run_status === "running").length;
    return { avg, running, total: activeProjects.length + 1 };
  }, [activeProjects]);

  function loadPortfolioProjects(listed: Project[]) {
    const projectsBySlug = new Map(listed.map((project) => [project.slug, project]));
    const mapped: Record<string, Project> = {};
    for (const demo of PORTFOLIO_DEMOS) {
      const project = projectsBySlug.get(demo.slug);
      if (project) mapped[demo.slug] = project;
    }
    setPortfolioProjects(mapped);
  }

  async function load() {
    setLoading(true);
    try {
      const listed = await projectsApi.list(true, true);
      setProjects(listed);
      loadPortfolioProjects(listed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!localPath.trim()) {
      setError("Set the local path to your real app folder before creating a project.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      await projectsApi.create({
        name,
        local_path: localPath.trim(),
        git_url: gitUrl || undefined,
      });
      setName("");
      setLocalPath("");
      setGitUrl("");
      localStorage.setItem("wizard-dismissed", "true");
      setWizardDismissed(true);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  function handleWizardComplete() {
    localStorage.setItem("wizard-dismissed", "true");
    setWizardDismissed(true);
  }

  async function setArchived(project: Project, archived: boolean) {
    setProjectAction(project.slug);
    setError("");
    try {
      if (archived) await projectsApi.archive(project.slug);
      else await projectsApi.restore(project.slug);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Project update failed");
    } finally {
      setProjectAction("");
    }
  }

  return (
    <>
      {!loading && projects.length === 0 && !wizardDismissed && (
        <WelcomeWizard onComplete={handleWizardComplete} />
      )}
      <div className="page">
      <div className="page-header">
        <div>
          <h1>Projects</h1>
          <p className="muted">
            Stripe setup runs in each app&apos;s own folder — open that folder in your editor to write code.
          </p>
        </div>
        {!loading && stats.total > 0 && (
          <div className="stats-row">
            <span>{stats.total} projects</span>
            {stats.avg !== null && <span>Avg readiness {stats.avg}</span>}
            {stats.running > 0 && <span>{stats.running} running</span>}
          </div>
        )}
      </div>

      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <section className="card">
        <h2>Portfolio demos (Railway storefronts)</h2>
        <p className="muted">
          Stripe-exempt portfolio apps — not listed under billing projects. Open SilverFox here to push Railway env
          vars and run full deploy setup (not the Operations Studio hub).
        </p>
        <ul className="project-grid">
          {PORTFOLIO_DEMOS.map((demo) => {
            const existing = portfolioProjects[demo.slug];
            return (
              <li key={demo.slug}>
                <div className="project-card">
                  {existing ? (
                    <Link to={`/projects/${demo.slug}`} className="project-card-link">
                      <div className="project-card-top">
                        <strong>{demo.name}</strong>
                        <ScoreRing score={existing.latest_readiness_score ?? null} size={48} />
                      </div>
                      <div className="project-card-meta">
                        <span className="pill">portfolio</span>
                        <span className="muted">{demo.note}</span>
                      </div>
                    </Link>
                  ) : (
                    <div className="project-card-link">
                      <div className="project-card-top">
                        <strong>{demo.name}</strong>
                      </div>
                      <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
                        Not registered yet — create below with slug <code>{demo.slug}</code>
                        {demo.localPath ? (
                          <>
                            {" "}
                            and path <code>{demo.localPath}</code>
                          </>
                        ) : null}
                      </p>
                    </div>
                  )}
                  {existing && (
                    <Link to={`/projects/${demo.slug}/settings`} className="project-card-settings">
                      Edit settings
                    </Link>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="card">
        <h2>New project</h2>
        <form className="settings-form" onSubmit={onCreate}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Local path
            <input
              value={localPath}
              onChange={(e) => setLocalPath(e.target.value)}
              placeholder="C:\Software Projects\YourApp"
              required
            />
          </label>
          <p className="muted" style={{ marginTop: "-0.5rem" }}>
            Your app&apos;s real folder on disk. Setup and Stripe files are written here — not inside this hub repo.
          </p>
          <label>
            Git URL (optional)
            <input
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              placeholder="https://github.com/org/repo"
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={creating}>
            {creating ? "Creating…" : "Create project"}
          </button>
        </form>
      </section>

      <section className="card">
        <div className="card-header-row">
          <div>
            <h2>Your projects</h2>
            <p className="muted">Search, triage, and safely archive workspaces without deleting their history.</p>
          </div>
          <div className="project-toolbar">
            <input
              aria-label="Search projects"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search projects"
            />
            <select
              aria-label="Filter projects"
              value={projectFilter}
              onChange={(event) => setProjectFilter(event.target.value)}
            >
              <option value="active">Active</option>
              <option value="ready">Ready (90+)</option>
              <option value="attention">Needs attention</option>
              <option value="running">Running</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : (
          <ul className="project-grid">
            <li>
              <div className="project-card">
                <a href={PLATFORM_PROJECT.productionUrl} className="project-card-link">
                  <div className="project-card-top">
                    <strong>{PLATFORM_PROJECT.name}</strong>
                    <ScoreRing score={PLATFORM_PROJECT.readinessScore} size={48} />
                  </div>
                  <div className="project-card-meta">
                    <span className="pill">platform</span>
                    <span className="run-pill run-completed">live</span>
                  </div>
                  <p className="muted" style={{ margin: "0.6rem 0 0", fontSize: "0.85rem" }}>
                    {PLATFORM_PROJECT.note}
                  </p>
                </a>
                <a
                  href={PLATFORM_PROJECT.repositoryUrl}
                  className="project-card-settings"
                  target="_blank"
                  rel="noreferrer"
                >
                  View GitHub repository
                </a>
              </div>
            </li>
            {filteredProjects.map((p) => (
              <li key={p.id}>
                <div className="project-card">
                  <Link to={`/projects/${p.slug}`} className="project-card-link">
                    <div className="project-card-top">
                      <strong>{p.name}</strong>
                      <ScoreRing score={p.latest_readiness_score ?? null} size={48} />
                    </div>
                    <div className="project-card-meta">
                      <span className="pill">{p.framework}</span>
                      <span className="muted">{p.language}</span>
                      {p.last_run_status && (
                        <span className={`run-pill run-${p.last_run_status}`}>{p.last_run_status}</span>
                      )}
                    </div>
                  </Link>
                  <Link to={`/projects/${p.slug}/settings`} className="project-card-settings">
                    Edit settings
                  </Link>
                  <button
                    type="button"
                    className="project-card-settings project-archive-action"
                    disabled={projectAction === p.slug}
                    onClick={() => setArchived(p, !p.archived_at)}
                  >
                    {projectAction === p.slug ? "Saving…" : p.archived_at ? "Restore" : "Archive"}
                  </button>
                </div>
              </li>
            ))}
            {filteredProjects.length === 0 && (
              <li className="empty-state">
                <p className="empty-state-title">No matching projects</p>
                <p className="muted">Try a different search or project status.</p>
              </li>
            )}
          </ul>
        )}
      </section>
    </div>
    </>
  );
}
