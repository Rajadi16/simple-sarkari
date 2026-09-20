import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { CatalogueFilters, Circular, PaginatedResponse } from "@/types";

export default function HomePage() {
  const [filters, setFilters] = useState<CatalogueFilters | null>(null);
  const [result, setResult] = useState<PaginatedResponse<Circular> | null>(null);
  const [params, setParams] = useState({ q: "", language: "", government_level: "", state: "", department: "", source_id: "", page: "1" });
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getFilters().then(setFilters).catch(() => setFilters({ sources: [], departments: [], states: [], document_types: [], languages: ["en-IN", "hi-IN", "kn-IN"] }));
  }, []);
  useEffect(() => {
    setLoading(true); setError("");
    const query = Object.fromEntries(Object.entries(params).filter(([, value]) => value));
    api.searchCirculars(query).then(setResult).catch((err: Error) => setError(err.message)).finally(() => setLoading(false));
  }, [params]);
  const update = (key: keyof typeof params, value: string) => setParams((current) => ({ ...current, [key]: value, page: "1" }));
  const clearFilters = () => { setQuery(""); setParams({ q: "", language: "", government_level: "", state: "", department: "", source_id: "", page: "1" }); };
  const activeFilters = Object.entries(params).filter(([key, value]) => value && key !== "page");

  return <div className="page-stack">
    <section className="feed-hero"><div className="hero-copy"><div className="hero-kicker"><span className="live-dot" /> Citizen briefing desk <span>·</span> Updated from official sources</div><h1>Government decisions, made easier to act on.</h1><p className="lede">Find the circular that matters to you, understand it in plain language, and always trace it back to the original government source.</p><div className="hero-proof"><span><strong>Plain language</strong><small>Built for citizens</small></span><span><strong>Traceable</strong><small>Source excerpts included</small></span><span><strong>Multilingual</strong><small>Hindi · Kannada · English</small></span></div></div><div className="hero-index" aria-hidden="true"><span>01</span><i /><small>Explore<br />the public record</small></div></section>
    <form className="search-panel" aria-label="Search and filter circulars" onSubmit={(event) => { event.preventDefault(); update("q", query); }}><label className="search-field"><span>Search circulars</span><div className="search-control"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try scholarships, tax, agriculture..." /><button className="button primary" type="submit">Search</button></div></label><div className="filter-grid">
      <label>Language<select value={params.language} onChange={(event) => update("language", event.target.value)}><option value="">All languages</option>{filters?.languages.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Government level<select value={params.government_level} onChange={(event) => update("government_level", event.target.value)}><option value="">All levels</option><option value="central">Central</option><option value="state">State</option></select></label>
      <label>State<select value={params.state} onChange={(event) => update("state", event.target.value)}><option value="">All states</option>{filters?.states.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Department<select value={params.department} onChange={(event) => update("department", event.target.value)}><option value="">All departments</option>{filters?.departments.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>Source<select value={params.source_id} onChange={(event) => update("source_id", event.target.value)}><option value="">All sources</option>{filters?.sources.map((source) => <option key={source.source_id} value={source.source_id}>{source.name}</option>)}</select></label>
    </div>{activeFilters.length > 0 && <div className="filter-summary"><div className="filter-chips">{activeFilters.map(([key, value]) => <button type="button" className="filter-chip" key={key} onClick={() => update(key as keyof typeof params, "")}>{key === "government_level" ? value === "central" ? "Central" : "State" : value} ×</button>)}</div><button type="button" className="clear-button" onClick={clearFilters}>Clear all</button></div>}</form>
    <div className="section-heading"><div><p className="eyebrow">Published circulars</p><h2>{result?.total ?? "Latest"} documents</h2></div>{result && <span className="muted">Page {result.page} of {Math.max(1, Math.ceil(result.total / result.limit))}</span>}</div>
    {loading && <div className="card-grid" aria-label="Loading circulars"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>}
    {!loading && error && <div className="state-box error-state">{error}<button className="button secondary" onClick={() => setParams({ ...params })}>Try again</button></div>}
    {!loading && !error && result?.items.length === 0 && <div className="state-box">No published circulars match those filters.</div>}
    <div className="card-grid">{result?.items.map((circular) => <CircularCard key={circular.id} circular={circular} />)}</div>
    {result && result.total > result.limit && <div className="pagination"><button className="button secondary" disabled={result.page <= 1} onClick={() => setParams((current) => ({ ...current, page: String(result.page - 1) }))}>← Previous</button><span className="muted">Showing {((result.page - 1) * result.limit) + 1}–{Math.min(result.page * result.limit, result.total)}</span><button className="button secondary" disabled={result.page * result.limit >= result.total} onClick={() => setParams((current) => ({ ...current, page: String(result.page + 1) }))}>Next →</button></div>}
  </div>;
}

function SkeletonCard() { return <div className="skeleton-card" aria-hidden="true"><span /><span /><span /><span /></div>; }

function CircularCard({ circular }: { circular: Circular }) {
  return <article className="circular-card"><div className="card-meta"><span>{circular.government_level ?? "Government"}</span><span>{circular.published_date ?? "Date unavailable"}</span></div><h3><Link to={`/circular/${circular.id}`}>{circular.simplified_title || circular.title || "Untitled circular"}</Link></h3><p>{circular.summary || "A published government document is available to read."}</p><div className="card-footer"><span>{circular.source_name || circular.department || "Official source"}</span><span className="card-signals">{circular.translation_languages.length > 0 && <span className="audio-pill">Translation</span>}{circular.audio_available && <span className="audio-pill">Audio</span>}</span></div><div className="card-actions"><Link to={`/circular/${circular.id}`} className="text-link">Read circular</Link>{circular.official_document_url && <a href={circular.official_document_url} target="_blank" rel="noreferrer" className="text-link">Official source ↗</a>}</div></article>;
}
