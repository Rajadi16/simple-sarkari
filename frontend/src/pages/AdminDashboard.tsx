import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { CrawlRun, Source } from "@/types";

export default function AdminDashboard() {
  const [sources, setSources] = useState<Source[]>([]);
  const [runs, setRuns] = useState<CrawlRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.listSources(), api.listJobs({ limit: "8" })]).then(([sourceItems, jobs]) => {
      setSources(sourceItems);
      setRuns(jobs.items.filter((job) => job.job_type === "crawl").map((job) => ({ id: job.id, source_id: job.source_id || "unknown", status: job.status as CrawlRun["status"], pages_fetched: 0, documents_discovered: 0, documents_new: 0, documents_duplicate: 0, blocked_requests: 0, errors: [], started_at: job.created_at, completed_at: job.completed_at })));
    }).catch((err: Error) => setError(err.message)).finally(() => setLoading(false));
  }, []);

  return <div className="page-stack admin-page">
    <section className="admin-hero"><div><p className="eyebrow">Operations room</p><h1>Keep the public catalogue trustworthy.</h1><p className="lede">Monitor registered government sources, inspect crawl health, and move documents into review.</p></div><div className="admin-actions"><Link to="/admin/ingest" className="button primary">Start ingestion</Link><Link to="/admin/reviews" className="button secondary">Open review queue</Link></div></section>
    {error && <div className="state-box error-state">{error}</div>}
    {loading ? <div className="state-box">Loading operations data...</div> : <>
      <div className="metric-grid"><Metric label="Registered sources" value={sources.length} detail={`${sources.filter((source) => source.status === "active").length} active`} /><Metric label="Recent crawl runs" value={runs.length} detail="Latest jobs" /><Metric label="Crawler posture" value="Guarded" detail="Allowlisted + robots-aware" /></div>
      <section className="admin-section"><div className="section-heading"><div><p className="eyebrow">Source registry</p><h2>Approved government sources</h2></div><Link to="/admin/ingest" className="text-link">Use a source →</Link></div><div className="source-table">{sources.map((source) => <div className="source-row" key={source.source_id}><div><strong>{source.name}</strong><span>{source.base_domains[0]} · {source.government_level}</span></div><span className={`status-dot ${source.status}`}>{source.status}</span></div>)}{sources.length === 0 && <div className="state-box">No sources registered yet.</div>}</div></section>
      <section className="admin-section"><div className="section-heading"><div><p className="eyebrow">Activity</p><h2>Recent crawl jobs</h2></div></div><div className="source-table">{runs.map((run) => <div className="source-row" key={run.id}><div><strong>{sources.find((source) => source.source_id === run.source_id)?.name || run.source_id}</strong><span>{run.id}</span></div><span className={`status-dot ${run.status}`}>{run.status}</span></div>)}{runs.length === 0 && <div className="state-box">No crawl jobs yet. Start with an approved source.</div>}</div></section>
    </>}
  </div>;
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) { return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>; }
