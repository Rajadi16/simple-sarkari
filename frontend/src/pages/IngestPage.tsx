import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/lib/api";
import type { CrawlRun, IngestionJob, Source } from "@/types";

type JobState =
  | { kind: "crawl"; id: string; status: string }
  | { kind: "ingestion"; job: IngestionJob };

export default function IngestPage() {
  const [mode, setMode] = useState<"source" | "text">("source");
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [form, setForm] = useState({ title: "", publisher: "", sourceUrl: "", language: "en-IN", targets: ["hi-IN", "kn-IN"], text: "" });
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listSources().then((items) => {
      setSources(items);
      setSourceId(items.find((source) => source.status === "active")?.source_id || items[0]?.source_id || "");
    }).catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!job || job.kind !== "crawl" || ["completed", "failed"].includes(job.status)) return;
    const timer = window.setInterval(() => api.getCrawlRun(job.id).then((run: CrawlRun) => setJob({ kind: "crawl", id: run.id, status: run.status })).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (!job || job.kind !== "ingestion" || ["completed", "failed"].includes(job.job.status)) return;
    const timer = window.setInterval(() => api.getIngestion(job.job.job_id).then((next) => setJob({ kind: "ingestion", job: next })).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [job]);

  const selectedSource = sources.find((source) => source.source_id === sourceId);
  const update = (key: "title" | "publisher" | "sourceUrl" | "language" | "text", value: string) => setForm((current) => ({ ...current, [key]: value }));
  const toggleTarget = (language: string) => setForm((current) => ({ ...current, targets: current.targets.includes(language) ? current.targets.filter((value) => value !== language) : [...current.targets, language] }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (mode === "source") {
      if (!sourceId) { setError("Choose a government source first."); return; }
      api.triggerCrawl(sourceId).then((value) => setJob({ kind: "crawl", id: value.run_id, status: value.status })).catch((err: Error) => setError(err.message));
      return;
    }
    api.ingestText({ title: form.title, publisher: form.publisher, source_url: form.sourceUrl, original_language: form.language, text: form.text, target_languages: form.targets }).then((value) => setJob({ kind: "ingestion", job: { job_id: value.job_id, status: value.status } })).catch((err: Error) => setError(err.message));
  };

  return <div className="page-stack narrow-page">
    <div><p className="eyebrow">Admin intake</p><h1>Bring in an official document.</h1><p className="lede">Choose a registered government source to crawl, or use pasted text when a source blocks automated access.</p></div>
    <div className="mode-tabs"><button type="button" className={mode === "source" ? "active" : ""} onClick={() => setMode("source")}>Choose a source</button><button type="button" className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>Pasted official text</button></div>
    <form className="form-panel" onSubmit={submit}>
      {mode === "source" ? <>
        <label>Government source<select required value={sourceId} onChange={(event) => setSourceId(event.target.value)}><option value="">Select a registered source</option>{sources.map((source) => <option key={source.source_id} value={source.source_id} disabled={source.status !== "active"}>{source.name} {source.status !== "active" ? `(${source.status})` : ""}</option>)}</select></label>
        {selectedSource && <div className="source-preview"><strong>{selectedSource.name}</strong><span>{selectedSource.government_level}{selectedSource.state ? ` · ${selectedSource.state}` : ""}</span><span>Monitored domain: {selectedSource.base_domains[0]}</span><span>Seed: {selectedSource.seed_urls[0]}</span></div>}
        <p className="form-help">We use the source’s approved seed and crawl policy. If access is blocked, the run stops and reports that manual ingestion is required.</p>
      </> : <>
        <div className="two-col"><label>Title<input required value={form.title} onChange={(event) => update("title", event.target.value)} /></label><label>Publisher<input required value={form.publisher} onChange={(event) => update("publisher", event.target.value)} /></label></div>
        <label>Official source URL<input required type="url" value={form.sourceUrl} onChange={(event) => update("sourceUrl", event.target.value)} /></label>
        <div className="two-col"><label>Original language<select value={form.language} onChange={(event) => update("language", event.target.value)}><option value="en-IN">English (India)</option><option value="hi-IN">Hindi</option><option value="kn-IN">Kannada</option></select></label><fieldset className="language-options"><legend>Target languages</legend><label><input type="checkbox" checked={form.targets.includes("hi-IN")} onChange={() => toggleTarget("hi-IN")} /> Hindi <span className="language-note">Audio supported</span></label><label><input type="checkbox" checked={form.targets.includes("kn-IN")} onChange={() => toggleTarget("kn-IN")} /> Kannada <span className="language-note">Text only</span></label></fieldset></div>
        <label>Official text<textarea required value={form.text} onChange={(event) => update("text", event.target.value)} placeholder="Paste the source document text here..." /></label>
      </>}
      <button className="button primary" type="submit">{mode === "source" ? "Start source crawl" : "Submit pasted text"}</button>
    </form>
    {error && <div className="state-box error-state">{error}</div>}
    {job && <div className="job-status"><p className="eyebrow">Processing status</p><strong>{job.kind === "crawl" ? job.status : job.job.status}</strong><p>{job.kind === "crawl" ? `Source run ${job.id} is being monitored.` : job.job.error || (job.job.circular_id ? `Circular created: ${job.job.circular_id}` : `Job ${job.job.job_id} is being processed.`)}</p></div>}
  </div>;
}
