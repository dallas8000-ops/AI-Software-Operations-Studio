import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { operationsApi, type OperationsReport } from "../api/client";
import ScoreRing from "../components/ScoreRing";

export default function OperationsPage() {
  const [report, setReport] = useState<OperationsReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setReport(await operationsApi.report());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operations report failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="page operations-page">
      <div className="page-header">
        <div>
          <p className="studio-kicker">VERSION 2 CONTROL CENTER</p>
          <h1>Operations intelligence</h1>
          <p className="muted">Portfolio readiness, releases, recovery evidence, teams, and changes in one view.</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh report"}
        </button>
      </div>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {loading && !report && <section className="card"><p className="muted">Building operations report…</p></section>}

      {report && (
        <>
          <section className="operations-metrics" aria-label="Portfolio metrics">
            <article><strong>{report.summary.projects}</strong><span>Active projects</span></article>
            <article><strong>{report.summary.averageReadiness ?? "—"}</strong><span>Average readiness</span></article>
            <article><strong>{report.summary.deployments24h}</strong><span>Runs in 24 hours</span></article>
            <article className={report.summary.failed24h ? "metric-warn" : ""}>
              <strong>{report.summary.failed24h}</strong><span>Failures in 24 hours</span>
            </article>
            <article><strong>{report.summary.organizations}</strong><span>Organizations</span></article>
            <article><strong>{report.summary.githubConnectedOrganizations}</strong><span>GitHub connected</span></article>
          </section>

          <section className="card">
            <div className="card-header-row">
              <div><h2>Portfolio readiness</h2><p className="muted">Live account-wide delivery posture.</p></div>
              <span className="badge badge-ok">{report.summary.readyProjects} ready</span>
            </div>
            <ul className="operations-project-list">
              {report.projects.filter((project) => !project.archived).map((project) => (
                <li key={project.slug}>
                  <ScoreRing score={project.readinessScore} size={44} />
                  <div>
                    <Link to={`/projects/${project.slug}`}><strong>{project.name}</strong></Link>
                    <span className="muted">{project.organization || "Personal workspace"}</span>
                  </div>
                  <span className={`run-pill run-${project.lastRunStatus || "idle"}`}>
                    {project.lastRunStatus || "No runs"}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <div className="operations-columns">
            <section className="card">
              <h2>Release recovery</h2>
              {report.recoveryCandidates.length === 0 ? (
                <p className="text-success">No failed releases in the last 24 hours.</p>
              ) : (
                <ul className="audit-list">
                  {report.recoveryCandidates.map((item) => (
                    <li key={item.failedRunId}>
                      <Link to={`/projects/${item.projectSlug}`}><strong>{item.project}</strong></Link>
                      <span className="muted">{item.error || "Pipeline failed"}</span>
                      <span className={`badge ${item.recoveryAvailable ? "badge-ok" : "badge-warn"}`}>
                        {item.recoveryAvailable ? "Previous release available" : "Manual recovery required"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card">
              <h2>Recent changes</h2>
              {report.recentActivity.length === 0 ? <p className="muted">No audit activity yet.</p> : (
                <ul className="audit-list">
                  {report.recentActivity.slice(0, 10).map((item, index) => (
                    <li key={`${item.projectSlug}-${item.createdAt}-${index}`}>
                      <Link to={`/projects/${item.projectSlug}`}><strong>{item.project}</strong></Link>
                      <span>{item.action.replaceAll(".", " ")}</span>
                      <span className="muted">{new Date(item.createdAt).toLocaleString()}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
          <p className="muted">Generated {new Date(report.generatedAt).toLocaleString()} · Secret values are never included.</p>
        </>
      )}
    </div>
  );
}
