import { Link } from "react-router-dom";

const workspaces = [
  {
    eyebrow: "OPERATE",
    title: "Application Operations",
    description: "Track application readiness, environments, releases, and infrastructure from one control plane.",
    to: "/projects",
    action: "Open projects",
    status: "Active",
  },
  {
    eyebrow: "SHIP",
    title: "Deploy & Transfer",
    description: "Move applications and configuration between providers with guarded, auditable workflows.",
    to: "/deploy",
    action: "Open deployment hub",
    status: "Active",
  },
  {
    eyebrow: "DESIGN",
    title: "Specwright",
    description: "Turn product intent into implementation-ready specifications connected to delivery work.",
    to: "/quality",
    action: "Open quality workspace",
    status: "Active",
  },
] as const;

export default function StudioPage() {
  return (
    <div className="studio-page">
      <section className="studio-hero">
        <div>
          <p className="studio-kicker">AI SOFTWARE OPERATIONS</p>
          <h1>One place to understand, improve, and ship your software.</h1>
          <p className="studio-lead">
            A unified operating layer for product specifications, application readiness,
            secure configuration, billing, and deployment.
          </p>
          <div className="studio-actions">
            <Link className="btn btn-primary" to="/projects">View applications</Link>
            <Link className="btn btn-ghost" to="/deploy">Deployment center</Link>
            <Link className="btn btn-ghost" to="/guide">How to use the Studio</Link>
          </div>
        </div>
        <div className="studio-signal" aria-label="Studio foundation status">
          <span className="studio-signal-dot" />
          <div>
            <strong>Foundation online</strong>
            <p>Local workspace · production isolated</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="workspaces-heading">
        <div className="studio-section-heading">
          <div>
            <p className="studio-kicker">WORKSPACES</p>
            <h2 id="workspaces-heading">Your software lifecycle, connected</h2>
          </div>
          <Link className="muted" to="/workflows">Prepare for Production →</Link>
        </div>
        <div className="studio-grid">
          {workspaces.map((workspace) => (
            <article className="studio-workspace" key={workspace.title}>
              <div className="studio-card-topline">
                <span className="studio-card-index">{workspace.eyebrow}</span>
                <span className={`studio-status studio-status-${workspace.status.toLowerCase()}`}>
                  {workspace.status}
                </span>
              </div>
              <h3>{workspace.title}</h3>
              <p>{workspace.description}</p>
              <Link to={workspace.to}>{workspace.action} <span aria-hidden>→</span></Link>
            </article>
          ))}
        </div>
      </section>

      <section className="studio-principles" aria-label="Studio operating principles">
        <div><strong>Safe by default</strong><span>Secrets stay server-side and production actions stay explicit.</span></div>
        <div><strong>Evidence over guesswork</strong><span>Readiness, runs, and changes are visible and auditable.</span></div>
        <div><strong>Built to expand</strong><span>New operational tools join the Studio without replacing proven workflows.</span></div>
      </section>
    </div>
  );
}
