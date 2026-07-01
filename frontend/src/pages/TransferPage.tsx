import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  deployApi,
  projectsApi,
  qualityApi,
  transferApi,
  type MigrationStatus,
  type Project,
  type SyncApprovalPlan,
  type TransferProviderStatus,
} from "../api/client";
import SetupHubPanel from "../components/SetupHubPanel";

const RAILWAY_ENV_KEYS = [
  "RAILWAY_API_TOKEN",
  "RAILWAY_PROJECT_ID",
  "RAILWAY_SERVICE_ID",
] as const;

const STRIPE_ENV_KEYS = [
  "STRIPE_SECRET_KEY",
  "STRIPE_PUBLISHABLE_KEY",
  "STRIPE_WEBHOOK_SECRET",
] as const;

function missingKeys(keyNames: string[], expected: readonly string[]) {
  return expected.filter((key) => !keyNames.includes(key));
}

export default function TransferPage() {
  const [providers, setProviders] = useState<TransferProviderStatus[]>([]);
  const [moduleStatus, setModuleStatus] = useState<string>("loading");
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [auditValid, setAuditValid] = useState<boolean | null>(null);
  const [migration, setMigration] = useState<MigrationStatus | null>(null);
  const [syncPlans, setSyncPlans] = useState<Record<string, SyncApprovalPlan>>({});
  const [confirmations, setConfirmations] = useState<Record<string, string>>({});
  const [syncBusy, setSyncBusy] = useState<string>("");
  const [syncNotice, setSyncNotice] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [flagship, setFlagship] = useState<Project | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mod, prov, metricData, auditData, projects, migrationData] = await Promise.all([
          transferApi.moduleStatus(),
          transferApi.providerStatus(),
          transferApi.transferMetrics(),
          transferApi.transferAudit(),
          projectsApi.list(),
          qualityApi.migrationStatus(),
        ]);
        if (!cancelled) {
          setModuleStatus(mod.status);
          setProviders(prov.providers);
          setMetrics(metricData.summary as Record<string, unknown>);
          setAuditValid(Boolean(auditData.valid?.valid));
          setMigration(migrationData);
          setFlagship(
            projects.find((p) => p.slug === "stripe-installer") ||
              projects.find((p) => p.name.includes("Operations Studio")) ||
              projects.find((p) => p.name.includes("Automation Center")) ||
              projects[0] ||
              null
          );
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load transfer status");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function prepareSyncPacket(slug: string) {
    setSyncBusy(`plan:${slug}`);
    setSyncNotice("");
    setError(null);
    try {
      const plan = await deployApi.syncApprovalPlan(slug);
      setSyncPlans((current) => ({ ...current, [slug]: plan }));
      setConfirmations((current) => ({ ...current, [slug]: "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare sync packet");
    } finally {
      setSyncBusy("");
    }
  }

  async function applySyncPacket(slug: string) {
    const confirmation = confirmations[slug] || "";
    setSyncBusy(`apply:${slug}`);
    setSyncNotice("");
    setError(null);
    try {
      const result = await deployApi.applySyncApproval(slug, confirmation);
      setSyncPlans((current) => ({ ...current, [slug]: result.plan }));
      setSyncNotice(`${result.message} Pushed keys: ${result.pushed.join(", ") || "none"}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync was not applied");
    } finally {
      setSyncBusy("");
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Deployments &amp; transfer</h1>
        <p className="muted">
          Deployment &amp; transfer pipeline — shared projects and vault with Stripe setup.
        </p>
      </div>

      {error && (
        <section className="card card-error">
          <p>{error}</p>
        </section>
      )}

      {syncNotice && (
        <section className="card">
          <p className="text-success">{syncNotice}</p>
        </section>
      )}

      {flagship && (
        <>
          <SetupHubPanel projectSlug={flagship.slug} />
          <p className="muted page-footer-link">
            <Link to={`/projects/${flagship.slug}`}>Open project workspace</Link> to run the full setup pipeline (step 4).
          </p>
        </>
      )}

      {!flagship && !error && (
        <section className="card">
          <h2>Platform setup</h2>
          <p className="muted">
            Open your flagship project workspace to use Setup Hub (reset, Stripe scan, webhooks).{" "}
            <Link to="/">Go to projects</Link>
          </p>
        </section>
      )}

      <section className="card">
        <h2>Module status</h2>
        <p>
          <strong>api_transfer</strong>: {moduleStatus}
        </p>
        <p className="muted">
          Per-project deploy and Render→Railway migration: open a project workspace →{" "}
          <strong>API Transfer</strong> section.
        </p>
      </section>

      {metrics && (
        <section className="card">
          <h2>Transfer queue</h2>
          <ul className="provider-list">
            <li>
              <strong>Running</strong> {String(metrics.running ?? 0)}
            </li>
            <li>
              <strong>Queued</strong> {String(metrics.queued ?? 0)}
            </li>
            <li>
              <strong>Retryable</strong> {String(metrics.retryable ?? 0)}
            </li>
            <li>
              <strong>Dead letter</strong> {String(metrics.deadLetter ?? 0)}
            </li>
          </ul>
          <p className="muted">
            Process queued jobs with <code>npm run transfer:worker</code> in a second terminal.
          </p>
        </section>
      )}

      {auditValid !== null && (
        <section className="card">
          <h2>Audit chain</h2>
          <p>
            Tamper-evident log:{" "}
            <span className={`badge ${auditValid ? "badge-ok" : "badge-warn"}`}>
              {auditValid ? "Valid" : "Broken — investigate"}
            </span>
          </p>
        </section>
      )}

      <section className="card">
        <h2>Provider readiness</h2>
        {providers.length === 0 ? (
          <p className="muted">Loading providers…</p>
        ) : (
          <ul className="provider-list">
            {providers.map((p) => (
              <li key={p.provider}>
                <strong>{p.provider}</strong>
                <span className={`badge ${p.liveEnabled ? "badge-ok" : "badge-warn"}`}>
                  {p.status}
                </span>
                <span className="muted">{p.message}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="muted">
          Platform tokens: <code>private_env/railway.env</code>, <code>render.env</code>,{" "}
          <code>github.env</code> (local) or project vault keys.
        </p>
      </section>

      {migration && (
        <section className="card" aria-labelledby="sync-plan-heading">
          <div className="studio-section-heading">
            <div>
              <p className="studio-kicker">GUARDED SYNC PLAN</p>
              <h2 id="sync-plan-heading">Railway and Stripe environment delivery</h2>
            </div>
            <span className="muted">Names only · no values shown</span>
          </div>
          <p className="muted">
            This is the approval checklist before any server-side sync. The Studio can keep secret values encrypted,
            verify key names, and prepare Railway environment delivery per project. It does not push to Railway,
            create Stripe objects, or change webhooks from this screen.
          </p>
          <div className="sync-summary">
            <div>
              <strong>{migration.railwayReadyProjects}/{migration.projects}</strong>
              <span>Railway target ready</span>
            </div>
            <div>
              <strong>{migration.stripeReadyProjects}/{migration.projects}</strong>
              <span>Stripe key-pair ready</span>
            </div>
            <div>
              <strong>{migration.secrets}</strong>
              <span>encrypted records retained</span>
            </div>
          </div>
          <ul className="sync-plan-list">
            {migration.railwayProjects.map((project) => {
              const keyNames = project.keyNames ?? [];
              const missingRailway = missingKeys(keyNames, RAILWAY_ENV_KEYS);
              const missingStripe = missingKeys(keyNames, STRIPE_ENV_KEYS);
              const stripeCoreReady = keyNames.includes("STRIPE_SECRET_KEY") && keyNames.includes("STRIPE_PUBLISHABLE_KEY");
              const syncPlan = syncPlans[project.slug];
              const confirmation = confirmations[project.slug] || "";
              return (
                <li key={project.slug}>
                  <div>
                    <h3>{project.name}</h3>
                    <p className="muted">
                      Railway: {project.ready ? "target mapped" : `missing ${missingRailway.join(", ") || "target mapping"}`} · Stripe:{" "}
                      {stripeCoreReady ? "key pair present" : `missing ${missingStripe.filter((key) => key !== "STRIPE_WEBHOOK_SECRET").join(", ") || "key pair"}`}
                    </p>
                    <p className="key-name-row">
                      {keyNames.length
                        ? keyNames.map((key) => <code key={key}>{key}</code>)
                        : <span className="muted">No vault keys imported yet</span>}
                    </p>
                    {syncPlan && (
                      <div className="sync-confirm">
                        <p className="muted">
                          Sync packet prepared: {syncPlan.payload.count} env var name(s). Type{" "}
                          <code>{syncPlan.requiresConfirmation}</code> to enable apply.
                        </p>
                        {syncPlan.warnings.length > 0 && (
                          <ul>
                            {syncPlan.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                          </ul>
                        )}
                        <input
                          value={confirmation}
                          onChange={(event) =>
                            setConfirmations((current) => ({ ...current, [project.slug]: event.target.value }))
                          }
                          placeholder={syncPlan.requiresConfirmation}
                        />
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          disabled={
                            syncBusy === `apply:${project.slug}` ||
                            confirmation !== syncPlan.requiresConfirmation ||
                            !syncPlan.ready
                          }
                          onClick={() => applySyncPacket(project.slug)}
                        >
                          {syncBusy === `apply:${project.slug}` ? "Applying…" : "Apply Railway sync"}
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="sync-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={syncBusy === `plan:${project.slug}`}
                      onClick={() => prepareSyncPacket(project.slug)}
                    >
                      {syncBusy === `plan:${project.slug}` ? "Preparing…" : "Prepare sync packet"}
                    </button>
                    <Link to={`/projects/${project.slug}`}>Open project →</Link>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="muted">
            Stripe note: prefer restricted API keys (<code>rk_</code>) where possible and keep separate keys for test,
            staging, and production.
          </p>
        </section>
      )}

      <section className="card">
        <h2>What&apos;s merged vs planned</h2>
        <ul>
          <li>GitHub import, framework detect, Railway/Render/Fly deploy pipeline</li>
          <li>Render→Railway migration runs + worker (<code>npm run transfer:worker</code>)</li>
          <li>Deployment history, Railway env backup, platform setup audit</li>
          <li>Transfer UI on each project workspace</li>
          <li className="muted">Planned: discover/plan/apply, Terraform, console bootstrap, client prewire</li>
        </ul>
        <p>
          Production cutover (Railway, Stripe, domain): see <code>docs/CUTOVER.md</code>
        </p>
        <p>
          <Link to="/">Back to projects</Link>
        </p>
      </section>
    </div>
  );
}
