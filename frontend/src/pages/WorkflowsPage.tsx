import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { projectsApi, qualityApi, type Project, type ProjectQualityHealth } from "../api/client";

type StageStatus = "ready" | "attention" | "approval" | "blocked";

export default function WorkflowsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [slug, setSlug] = useState("");
  const [quality, setQuality] = useState<ProjectQualityHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsApi.list().then((items) => { setProjects(items); if (items[0]) setSlug(items[0].slug); }).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!slug) { setQuality(null); return; }
    setQuality(null);
    qualityApi.projectHealth(slug).then(setQuality).catch(() => setQuality({ linked: false, connected: false, status: "unavailable" }));
  }, [slug]);

  const project = projects.find((item) => item.slug === slug);
  const stages = useMemo(() => {
    if (!project) return [];
    const analyzed = project.framework !== "unknown" || Boolean(project.last_scanned_at);
    const qualityReady = quality?.connected && (quality.score ?? 0) >= 75 && !quality.drift?.detected;
    const configured = Boolean(project.local_path && project.production_url);
    const verified = (project.latest_readiness_score ?? 0) >= 75;
    return [
      stage("UNDERSTAND", "Analyze repository", analyzed ? "Repository profile is available." : "Run the existing project scan to establish framework and dependency evidence.", analyzed ? "ready" : "attention"),
      stage("IMPROVE", "Close quality gaps", qualityReady ? `Specwright score ${quality?.score}; specifications are synchronized.` : quality?.linked ? "Review quality score, gaps, and drift before release." : "Link this project to Specwright in Project Settings.", qualityReady ? "ready" : "attention"),
      stage("CONFIGURE", "Prepare services", configured ? "Local source path and production URL are configured." : "Local source path or production URL is missing.", configured ? "ready" : "attention"),
      stage("VERIFY", "Run release gates", verified ? `Latest operational readiness score is ${project.latest_readiness_score}.` : "A readiness score of 75 or higher is required.", verified ? "ready" : "blocked"),
      stage("SHIP", "Deploy and observe", verified && qualityReady ? "Evidence is ready for human deployment approval." : "Complete quality and readiness gates before approval.", verified && qualityReady ? "approval" : "blocked"),
    ];
  }, [project, quality]);

  const readyCount = stages.filter((item) => item.status === "ready").length;

  return (
    <div className="workflow-page">
      <header className="page-header quality-header"><div><p className="studio-kicker">UNIFIED AUTOMATION</p><h1>Prepare for Production</h1><p className="quality-intro">A read-only evidence review before any production action is allowed.</p></div>{project && <Link className="btn btn-ghost" to={`/projects/${project.slug}`}>Open project</Link>}</header>
      <section className="workflow-selector card">
        <label>Application<select value={slug} onChange={(event) => setSlug(event.target.value)} disabled={loading}>{projects.length ? projects.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>) : <option value="">No projects available</option>}</select></label>
        {project && <div className="workflow-score"><strong>{readyCount}/4</strong><span>evidence gates ready</span></div>}
      </section>
      {!project ? <section className="card"><h2>No application selected</h2><p className="muted">Create a project before running a production preflight.</p><Link to="/projects">Open Projects →</Link></section> : <>
        <div className="workflow-notice"><span className="studio-signal-dot"/><div><strong>Read-only preflight</strong><p>This page reads existing evidence only. It does not scan, provision, modify Stripe, or deploy.</p></div></div>
        <ol className="workflow-timeline">{stages.map((item, index) => <li key={item.title}><div className="workflow-number">{index + 1}</div><article><div className="workflow-stage-head"><span>{item.group}</span><span className={`workflow-result workflow-result-${item.status}`}>{label(item.status)}</span></div><h2>{item.title}</h2><p>{item.detail}</p>{item.status !== "ready" && item.group !== "SHIP" && <Link to={item.group === "IMPROVE" ? `/projects/${slug}/settings` : `/projects/${slug}`}>Resolve in project →</Link>}</article></li>)}</ol>
        <section className="workflow-gate"><div><p className="studio-kicker">HUMAN CONTROL</p><h2>{stages.at(-1)?.status === "approval" ? "Evidence ready for approval." : "Production remains blocked."}</h2></div><p>Paid, destructive, and production actions always require explicit approval. This preflight never performs them.</p></section>
      </>}
    </div>
  );
}

function stage(group: string, title: string, detail: string, status: StageStatus) { return { group, title, detail, status }; }
function label(status: StageStatus) { return { ready: "Ready", attention: "Needs attention", approval: "Approval required", blocked: "Blocked" }[status]; }
