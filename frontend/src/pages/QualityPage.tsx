import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { qualityApi, type QualitySummary } from "../api/client";

const capabilities = [
  { value: "AST", label: "Code-aware analysis", detail: "Routes and models are read from source, not guessed." },
  { value: "0–100", label: "Specwright Score", detail: "Documentation, tests, freshness, and model coverage." },
  { value: "CI", label: "Drift protection", detail: "Detect stale OpenAPI artifacts before deployment." },
  { value: "AI", label: "Grounded assistance", detail: "Improve prose and tests while source remains truth." },
];

const checks = [
  ["API inventory", "Discover FastAPI and Django routes"],
  ["Specification sync", "Compare source routes with committed OpenAPI"],
  ["Test gaps", "Identify routes without meaningful coverage"],
  ["Model documentation", "Map data models and generate ER artifacts"],
  ["Change safety", "Surface breaking changes and migration notes"],
] as const;

export default function QualityPage() {
  const [data, setData] = useState<QualitySummary | null>(null);

  useEffect(() => {
    let active = true;
    qualityApi.summary().then((result) => { if (active) setData(result); }).catch(() => {
      if (active) setData({ connected: false, status: "unavailable", message: "Quality adapter is unavailable" });
    });
    return () => { active = false; };
  }, []);

  const metrics = data?.connected && data.summary ? [
    { value: String(data.summary.averageScore ?? "—"), label: "Average score", detail: `${data.summary.scoredProjects} of ${data.summary.totalProjects} projects scored.` },
    { value: `${data.summary.documentationCoverage ?? "—"}%`, label: "Documentation", detail: "Average documented route coverage." },
    { value: `${data.summary.testCoverage ?? "—"}%`, label: "Test coverage", detail: "Average API test coverage." },
    { value: String(data.summary.needsAttention), label: "Needs attention", detail: `${data.summary.driftedThisWeek} drifted this week.` },
  ] : capabilities;

  return (
    <div className="quality-page">
      <header className="page-header quality-header">
        <div>
          <p className="studio-kicker">SPECWRIGHT INTELLIGENCE</p>
          <h1>Quality & Specifications</h1>
          <p className="quality-intro">Understand whether each application is documented, tested, synchronized, and safe to ship.</p>
        </div>
        <Link className="btn btn-primary" to="/workflows">Prepare for Production</Link>
      </header>
      <div className={`quality-connection ${data?.connected ? "connected" : ""}`}>
        <span className="studio-signal-dot"/><strong>{data === null ? "Checking Specwright connection…" : data.connected ? "Live quality data connected" : "Quality adapter ready to connect"}</strong>
        {data?.message && <span>{data.message}</span>}
      </div>
      <div className="quality-metrics">
        {metrics.map((item) => <article key={item.label}><strong>{item.value}</strong><h2>{item.label}</h2><p>{item.detail}</p></article>)}
      </div>
      <div className="quality-layout">
        <section className="card quality-checks">
          <div className="quality-section-title"><div><p className="studio-kicker">SCAN PIPELINE</p><h2>What the Studio will verify</h2></div><span className="studio-status studio-status-next">Adapter next</span></div>
          <ol>{checks.map(([title, detail], index) => <li key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{title}</strong><p>{detail}</p></div></li>)}</ol>
        </section>
        <aside className="card integration-note">
          <p className="studio-kicker">SAFE INTEGRATION</p><h2>Bounded module, shared experience</h2>
          <p>Specwright’s scanner remains isolated while the Studio adopts its scores and artifacts through a stable adapter.</p>
          <ul><li>No production database migration</li><li>No webhook changes</li><li>No secret duplication</li><li>No legacy service shutdown</li></ul>
          <Link to="/projects">Choose an application →</Link>
        </aside>
      </div>
    </div>
  );
}
