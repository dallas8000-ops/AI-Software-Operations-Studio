import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { projectsApi, qualityApi, vaultApi, type MigrationStatus, type Project, type QualitySummary } from "../api/client";

const steps = [
  { title: "Add your applications", detail: "Register each real application folder or Git repository. The Studio never discovers every folder automatically.", action: "Open Projects", to: "/projects" },
  { title: "Confirm project settings", detail: "Set the real local path, Git URL, production URL, organization, and active environment for each application.", action: "Choose a project", to: "/projects" },
  { title: "Connect Specwright", detail: "Start or configure the Specwright API, then link each Studio project to its matching Specwright project ID.", action: "Open Quality", to: "/quality" },
  { title: "Set up the secure vault", detail: "Open a project, unlock its vault, and add required keys such as Stripe and Railway credentials. Secret values are never displayed again.", action: "Open Projects", to: "/projects" },
  { title: "Verify Stripe safely", detail: "Use Verify keys before provisioning anything. Then review products, prices, webhook URL, and billing configuration for that specific application.", action: "Review billing", to: "/billing" },
  { title: "Run readiness checks", detail: "Run repository scanning, diagnostics, CI gates, and readiness. Fix warnings before any production operation.", action: "Open workflow", to: "/workflows" },
  { title: "Prepare for Production", detail: "Review the evidence gates. Analyze and verify automatically; paid, destructive, and production actions remain approval-controlled.", action: "Run preflight", to: "/workflows" },
  { title: "Stage before cutover", detail: "Deploy the Studio to new staging services and a separate database. Keep current Railway services, URLs, databases, and Stripe webhooks active until validation passes.", action: "Deployment center", to: "/deploy" },
] as const;

const remaining = [
  "Connect a running Specwright API to SPECWRIGHT_API_URL.",
  "Create Specwright records and links for projects that have not yet been scanned there.",
  "Migrate organizations, memberships, and subscription ownership after account identity review.",
  "Validate products, prices, webhooks, domains, and production URLs per application.",
  "Create separate Studio staging services and database before any production cutover.",
  "Run migration rehearsals, backups, and side-by-side monitoring.",
  "Cut over gradually; archive old services only after verification.",
] as const;

export default function GuidePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [quality, setQuality] = useState<QualitySummary | null>(null);
  const [stripeReady, setStripeReady] = useState(0);
  const [migration, setMigration] = useState<MigrationStatus | null>(null);

  useEffect(() => {
    projectsApi.list().then(async (items) => {
      setProjects(items);
      const vaults = await Promise.all(items.map((project) => vaultApi.keys(project.slug).catch(() => null)));
      setStripeReady(vaults.filter((vault) => vault?.keys.includes("STRIPE_SECRET_KEY") && vault.keys.includes("STRIPE_PUBLISHABLE_KEY")).length);
    }).catch(() => setProjects([]));
    qualityApi.summary().then(setQuality).catch(() => setQuality({ connected: false, status: "unavailable" }));
    qualityApi.migrationStatus().then(setMigration).catch(() => setMigration(null));
  }, []);

  const configured = useMemo(() => projects.filter((p) => p.local_path && p.production_url).length, [projects]);

  return (
    <div className="guide-page">
      <header className="guide-hero">
        <div><p className="studio-kicker">START HERE</p><h1>How to use Operations Studio</h1><p>Follow this sequence for each application. Green means evidence is currently passing—not that every external system or production record has been migrated.</p></div>
        <div className="guide-snapshot">
          <div><strong>{projects.length}</strong><span>local projects</span></div>
          <div><strong>{configured}</strong><span>paths + URLs set</span></div>
          <div><strong>{stripeReady}/{projects.length}</strong><span>Stripe vault ready</span></div>
          <div><strong>{quality?.connected ? "Live" : "Offline"}</strong><span>Specwright</span></div>
        </div>
      </header>

      <section className="guide-callout">
        <strong>Why data appears missing</strong>
        <p>The safe migration is underway. Project metadata, pipeline history, and encrypted vault records are now in Studio. Stripe customers and products remain in Stripe, while Railway databases and live services remain in place until staged cutover.</p>
      </section>

      {migration && <section className="migration-summary" aria-label="Migrated data summary">
        <div><strong>{migration.projects}</strong><span>projects</span></div><div><strong>{migration.runs}</strong><span>pipeline runs</span></div><div><strong>{migration.logs}</strong><span>run logs</span></div><div><strong>{migration.secrets}</strong><span>encrypted secrets</span></div><div><strong>{migration.stripeReadyProjects}/{migration.projects}</strong><span>Stripe-key ready</span></div><div><strong>{migration.qualityLinks}</strong><span>quality links</span></div>
      </section>}

      <section aria-labelledby="guide-steps">
        <div className="studio-section-heading"><div><p className="studio-kicker">STEP BY STEP</p><h2 id="guide-steps">From application folder to safe production</h2></div><span className="muted">8 stages</span></div>
        <ol className="guide-steps">{steps.map((step, index) => <li key={step.title}><span>{index + 1}</span><div><h3>{step.title}</h3><p>{step.detail}</p></div><Link to={step.to}>{step.action} →</Link></li>)}</ol>
      </section>

      <section className="guide-status-grid">
        <article className="card"><p className="studio-kicker">COMPLETE NOW</p><h2>Studio foundation + data</h2><ul><li>Unified navigation and branding</li><li>12 project records and settings migrated</li><li>103 runs and 1,618 logs migrated</li><li>88 encrypted secrets migrated and readable</li><li>DBOps and Elite Specwright links</li><li>Production preflight and approval gates</li></ul></article>
        <article className="card"><p className="studio-kicker">LEFT TO COMPLETE</p><h2>Connections and migration</h2><ol>{remaining.map((item) => <li key={item}>{item}</li>)}</ol></article>
      </section>

      <section className="workflow-gate"><div><p className="studio-kicker">IMPORTANT</p><h2>Do not enter production keys just to make every item green.</h2></div><p>First connect the correct project, confirm its environment, and verify where each credential belongs. Green should represent proven evidence, not a rushed checkbox.</p></section>
    </div>
  );
}
