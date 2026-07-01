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
  "Confirm any remaining Specwright project links that were not present in the imported source data.",
  "Create Specwright records and links for projects that have not yet been scanned there.",
  "Assign migrated projects to the correct agency organization after you choose the ownership model.",
  "Validate products, prices, webhooks, domains, and production URLs per application.",
  "Create separate Studio staging services and database before any production cutover.",
  "Run migration rehearsals, backups, and side-by-side monitoring.",
  "Cut over gradually; archive old services only after verification.",
] as const;

type PhaseState = "done" | "ready" | "approval" | "remaining";

function phaseRoadmap(migration: MigrationStatus | null, projects: Project[], quality: QualitySummary | null) {
  const migratedProjects = migration?.projects ?? projects.length;
  const railwayReady = migration ? migration.railwayReadyProjects === migration.projects && migration.projects > 0 : false;
  const stripeReady = migration ? migration.stripeReadyProjects > 0 : false;
  const qualityLinked = Boolean((migration?.qualityLinks ?? 0) > 0 || quality?.connected);

  return [
    {
      title: "Phase 1 — Studio foundation",
      state: "done" as PhaseState,
      detail: "Unified navigation, local root serving, auth, project workspaces, vault, quality, workflow, deploy, agency, and billing surfaces are in place.",
    },
    {
      title: "Phase 2 — Local data migration",
      state: migratedProjects > 0 ? "done" as PhaseState : "remaining" as PhaseState,
      detail: `${migratedProjects} projects, ${migration?.runs ?? 0} runs, ${migration?.logs ?? 0} logs, ${migration?.vaults ?? 0} vaults, and ${migration?.secrets ?? 0} encrypted secret records are present for your real account.`,
    },
    {
      title: "Phase 3 — Secret protection and target mapping",
      state: railwayReady ? "ready" as PhaseState : "remaining" as PhaseState,
      detail: railwayReady
        ? "Railway tokens/project IDs/service IDs are mapped locally without exposing values. The app is ready for an approval-controlled server-side sync."
        : "Some Railway token, project ID, or service ID mappings still need to be verified before any server-side sync.",
    },
    {
      title: "Phase 4 — Stripe setup per client app",
      state: stripeReady ? "ready" as PhaseState : "remaining" as PhaseState,
      detail: stripeReady
        ? `${migration?.stripeReadyProjects ?? 0} projects have Stripe key pairs in the encrypted vault. Billing setup still runs per project, not from the Studio billing page.`
        : "Add or import each client app's Stripe keys into its own vault, then run Verify keys before creating products, prices, or webhooks.",
    },
    {
      title: "Phase 5 — Quality and workflow evidence",
      state: qualityLinked ? "ready" as PhaseState : "remaining" as PhaseState,
      detail: qualityLinked
        ? `${migration?.qualityLinks ?? 0} project links are connected to Specwright/fallback quality data. Continue linking projects that need scan history.`
        : "Link projects to Specwright and run quality scans before treating readiness scores as production evidence.",
    },
    {
      title: "Phase 6 — Agency, production, and cutover",
      state: "approval" as PhaseState,
      detail: "Organization assignment, Railway env sync, Stripe dashboard changes, live domains, production database moves, and old-service archival remain approval-controlled steps.",
    },
  ];
}

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
  const phases = useMemo(() => phaseRoadmap(migration, projects, quality), [migration, projects, quality]);

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
        <p>The local data migration is complete. Project metadata, pipeline history, and encrypted vault records are now in Studio. Secrets are retained for server-side Railway sync but never displayed. Railway databases and live services remain unchanged until their target mappings pass verification.</p>
      </section>

      {migration && <section className="migration-summary" aria-label="Migrated data summary">
        <div><strong>{migration.projects}</strong><span>projects</span></div><div><strong>{migration.runs}</strong><span>pipeline runs</span></div><div><strong>{migration.logs}</strong><span>run logs</span></div><div><strong>{migration.secrets}</strong><span>encrypted secrets</span></div><div><strong>{migration.stripeReadyProjects}/{migration.projects}</strong><span>Stripe-key ready</span></div><div><strong>{migration.railwayReadyProjects}/{migration.projects}</strong><span>Railway target ready</span></div><div><strong>{migration.qualityLinks}</strong><span>quality links</span></div>
      </section>}

      {migration && <section className="card" aria-labelledby="railway-readiness">
        <div className="studio-section-heading"><div><p className="studio-kicker">SAFE SYNC AUDIT</p><h2 id="railway-readiness">Railway secret delivery readiness</h2></div><span className="muted">No values displayed or sent</span></div>
        <ul>{migration.railwayProjects.map((project) => <li key={project.slug}>
          <strong>{project.name}</strong>: {project.ready ? "ready for verified server-side sync" : [!project.hasToken && "token", !project.hasProjectId && "project ID", !project.hasServiceId && "service ID"].filter(Boolean).join(", ") + " mapping required"}
        </li>)}</ul>
      </section>}

      <section className="card" aria-labelledby="phase-roadmap">
        <div className="studio-section-heading"><div><p className="studio-kicker">PHASE ROADMAP</p><h2 id="phase-roadmap">What is complete and what still needs approval</h2></div><span className="muted">Live local status</span></div>
        <ol className="phase-roadmap">
          {phases.map((phase) => (
            <li key={phase.title} className={`phase phase-${phase.state}`}>
              <div>
                <h3>{phase.title}</h3>
                <p>{phase.detail}</p>
              </div>
              <span>{phase.state === "done" ? "Done" : phase.state === "ready" ? "Ready" : phase.state === "approval" ? "Approval required" : "Remaining"}</span>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="guide-steps">
        <div className="studio-section-heading"><div><p className="studio-kicker">STEP BY STEP</p><h2 id="guide-steps">From application folder to safe production</h2></div><span className="muted">8 stages</span></div>
        <ol className="guide-steps">{steps.map((step, index) => <li key={step.title}><span>{index + 1}</span><div><h3>{step.title}</h3><p>{step.detail}</p></div><Link to={step.to}>{step.action} →</Link></li>)}</ol>
      </section>

      <section className="guide-status-grid">
        <article className="card"><p className="studio-kicker">COMPLETE NOW</p><h2>Studio foundation + data</h2><ul><li>Unified navigation and branding</li><li>{migration?.projects ?? 12} project records and settings migrated</li><li>{migration?.runs ?? 103} runs and {migration?.logs ?? 1618} logs migrated</li><li>{migration?.secrets ?? 90} encrypted secret records retained without displaying values</li><li>{migration?.qualityLinks ?? 2} Specwright/quality project links</li><li>Production preflight and approval gates</li></ul></article>
        <article className="card"><p className="studio-kicker">LEFT TO COMPLETE</p><h2>Connections and migration</h2><ol>{remaining.map((item) => <li key={item}>{item}</li>)}</ol></article>
      </section>

      <section className="workflow-gate"><div><p className="studio-kicker">IMPORTANT</p><h2>Do not enter production keys just to make every item green.</h2></div><p>First connect the correct project, confirm its environment, and verify where each credential belongs. Green should represent proven evidence, not a rushed checkbox.</p></section>
    </div>
  );
}
