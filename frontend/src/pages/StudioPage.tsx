import { Link } from "react-router-dom";

const workspaces = [
  {
    eyebrow: "INTELLIGENCE",
    title: "Operations Center",
    description: "See portfolio readiness, release recovery evidence, team connectivity, and recent changes.",
    to: "/operations",
    action: "Open operations center",
    status: "Active",
  },
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

const trustPoints = [
  { label: "Built for", value: "Technician workflows" },
  { label: "Current focus", value: "Secure diagnostics" },
  { label: "Future path", value: "Fleet monitoring" },
  { label: "Ready for", value: "Support evidence" },
] as const;

const planCards = [
  {
    name: "Starter",
    price: "$19",
    description: "For solo operators and small support teams.",
    features: ["1 workspace", "Core diagnostics", "Email support", "Monthly billing"],
    featured: false,
  },
  {
    name: "Professional",
    price: "$49",
    description: "For distributed teams with deeper review needs.",
    features: ["Unlimited checks", "Multi-environment review", "Priority support", "Audit trail"],
    featured: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For regulated or fleet-wide deployment programs.",
    features: ["Private deployment", "Custom retention", "Dedicated onboarding", "SLA coverage"],
    featured: false,
  },
] as const;

export default function StudioPage() {
  return (
    <div className="studio-page">
      <section className="studio-hero">
        <div className="studio-hero-copy">
          <p className="studio-kicker">AI SOFTWARE OPERATIONS</p>
          <h1>Built for technician workflows and future fleet monitoring.</h1>
          <p className="studio-lead">
            A calm, evidence-driven workspace for diagnostics, secure configuration review,
            deployment verification, and support-ready operations.
          </p>
          <div className="studio-actions">
            <Link className="btn btn-primary" to="/projects">View applications</Link>
            <Link className="btn btn-ghost" to="/billing">See pricing</Link>
            <Link className="btn btn-ghost" to="/guide">How it works</Link>
          </div>
          <div className="studio-badges" aria-label="Product proof points">
            <span>Privacy-aware</span>
            <span>Support-ready</span>
            <span>Evidence-first</span>
          </div>
        </div>
        <div className="studio-signal" aria-label="Product readiness status">
          <span className="studio-signal-dot" />
          <div>
            <strong>Current scope</strong>
            <p>Diagnostics workflows, secure config review, and production-ready evidence.</p>
          </div>
        </div>
      </section>

      <section className="studio-metrics" aria-label="Product summary">
        {trustPoints.map((point) => (
          <article key={point.label} className="studio-metric-card">
            <span>{point.label}</span>
            <strong>{point.value}</strong>
          </article>
        ))}
      </section>

      <section aria-labelledby="workspaces-heading">
        <div className="studio-section-heading">
          <div>
            <p className="studio-kicker">WORKSPACES</p>
            <h2 id="workspaces-heading">Operations built for confidence, not hype</h2>
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

      <section className="studio-trust-grid" aria-label="Trust and commercial details">
        <article className="studio-trust-panel">
          <p className="studio-kicker">WHY CUSTOMERS TRUST IT</p>
          <h2>Plain-language proof, not a speculative promise.</h2>
          <ul>
            <li>Clear plan limits, trial terms, renewal, and cancellation policy.</li>
            <li>Privacy expectations for scan data, retention, and AI processing.</li>
            <li>Support channels, compatibility matrix, and installer guidance.</li>
            <li>Deployment evidence that helps teams validate before rollout.</li>
          </ul>
        </article>

        <article className="studio-trust-panel studio-trust-panel-alt">
          <p className="studio-kicker">SUPPORT & POLICIES</p>
          <h2>Confidence is built in.</h2>
          <div className="studio-trust-list">
            <div><strong>Support</strong><span>Response windows and escalation path are documented.</span></div>
            <div><strong>Privacy</strong><span>Scan data handling, retention, and AI usage are clear.</span></div>
            <div><strong>Compatibility</strong><span>Windows OS and deployment matrix are published.</span></div>
            <div><strong>Trust</strong><span>Signed installer and release notes reduce friction for end users.</span></div>
          </div>
        </article>
      </section>

      <section className="studio-pricing" aria-labelledby="pricing-heading">
        <div className="studio-section-heading">
          <div>
            <p className="studio-kicker">PRICING</p>
            <h2 id="pricing-heading">Simple tiers for technical teams</h2>
          </div>
          <Link className="muted" to="/billing">Open billing →</Link>
        </div>
        <div className="studio-plan-grid">
          {planCards.map((plan) => (
            <article key={plan.name} className={`studio-plan ${plan.featured ? "studio-plan-featured" : ""}`}>
              <span className="studio-plan-label">{plan.name}</span>
              <strong>{plan.price}</strong>
              <p>{plan.description}</p>
              <ul>
                {plan.features.map((feature) => <li key={feature}>{feature}</li>)}
              </ul>
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
