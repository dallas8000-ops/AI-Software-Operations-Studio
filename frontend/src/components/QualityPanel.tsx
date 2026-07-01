import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { qualityApi, type ProjectQualityHealth } from "../api/client";
import ScoreRing from "./ScoreRing";

export default function QualityPanel({ projectSlug }: { projectSlug: string }) {
  const [health, setHealth] = useState<ProjectQualityHealth | null>(null);

  useEffect(() => {
    let active = true;
    qualityApi.projectHealth(projectSlug).then((result) => { if (active) setHealth(result); }).catch(() => {
      if (active) setHealth({ linked: false, connected: false, status: "unavailable", message: "Quality data could not be loaded." });
    });
    return () => { active = false; };
  }, [projectSlug]);

  if (!health) return <section className="card quality-panel"><p className="muted">Loading quality intelligence…</p></section>;
  if (!health.linked) return <section className="card quality-panel quality-panel-empty"><div><p className="studio-kicker">SPECWRIGHT</p><h2>Connect quality intelligence</h2><p className="muted">Link this application to its Specwright project to see specifications, tests, and drift here.</p></div><Link className="btn btn-secondary" to={`/projects/${projectSlug}/settings`}>Link in settings</Link></section>;
  if (!health.connected) return <section className="card quality-panel quality-panel-empty"><div><p className="studio-kicker">SPECWRIGHT</p><h2>Quality project linked</h2><p className="muted">{health.message || "Start the configured Specwright service to load current quality data."}</p></div><span className="studio-status studio-status-next">Offline</span></section>;

  return (
    <section className="card quality-panel">
      <div className="quality-panel-heading"><div><p className="studio-kicker">SPECWRIGHT QUALITY</p><h2>Specifications & test health</h2><p className="muted">{health.summary || "Current source-backed quality assessment."}</p></div><ScoreRing score={health.score ?? null} size={72}/></div>
      <div className="quality-panel-metrics">
        <div><strong>{health.documentationCoverage ?? "—"}%</strong><span>Documentation</span></div>
        <div><strong>{health.testCoverage ?? "—"}%</strong><span>Tests</span></div>
        <div><strong>{health.routeCount ?? 0}</strong><span>Routes</span></div>
        <div><strong>{health.gaps?.tests ?? 0}</strong><span>Test gaps</span></div>
      </div>
      <div className={`quality-drift ${health.drift?.detected ? "has-drift" : ""}`}><strong>{health.drift?.detected ? "Specification drift detected" : "Specifications in sync"}</strong><span>{health.drift?.message || (health.drift?.detected ? `${health.drift.commitsBehind} commits behind` : "No source drift reported")}</span></div>
    </section>
  );
}
