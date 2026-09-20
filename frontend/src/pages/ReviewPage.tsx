import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Review } from "@/types";

const statuses = ["draft", "in_review", "changes_requested"];

export default function ReviewPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selected, setSelected] = useState<Review | null>(null);
  const [status, setStatus] = useState("draft");
  const [draft, setDraft] = useState({ title: "", text: "", notes: "", feedback: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [translationLanguage, setTranslationLanguage] = useState("");

  const loadReviews = (nextStatus = status) => {
    setLoading(true);
    setError("");
    api.listReviews({ status: nextStatus }).then((value) => setReviews(value.items)).catch((err: Error) => setError(err.message)).finally(() => setLoading(false));
  };

  useEffect(() => { loadReviews(); }, [status]);

  const openReview = (id: string) => {
    setNotice("");
    api.getReview(id).then((value) => {
      setSelected(value);
      setTranslationLanguage(value.language);
      setDraft({ title: value.simplified_title || "", text: value.simplified_text || value.translation_text || "", notes: value.reviewer_notes || "", feedback: "" });
    }).catch((err: Error) => setError(err.message));
  };

  const save = () => {
    if (!selected) return;
    setSaving(true);
    setError("");
    api.saveReviewEdits(selected.id, { simplified_title: draft.title, simplified_text: draft.text, reviewer_notes: draft.notes }).then((value) => { setSelected(value); setNotice("Draft saved. It remains in the review queue until approved."); }).catch((err: Error) => setError(err.message)).finally(() => setSaving(false));
  };

  const action = (type: "approve" | "reject" | "redraft") => {
    if (!selected) return;
    const confirmation = type === "approve" ? "Approve this draft and allow it to move toward publication?" : type === "reject" ? "Reject this review? You will need to provide a reason in the notes." : "Request an AI redraft using the feedback below?";
    if (!window.confirm(confirmation)) return;
    setSaving(true);
    setError("");
    const request = type === "approve" ? api.approveReview(selected.id) : type === "reject" ? api.rejectReview(selected.id, draft.notes || "Rejected during review") : api.redraftReview(selected.id, draft.feedback || "Please review the facts and simplify the draft further.");
    request.then((value) => { setSelected(value); setReviews((items) => items.filter((item) => item.id !== selected.id)); setNotice(type === "approve" ? "Approved. Publication will follow the backend approval rules." : type === "reject" ? "Review rejected." : "Redraft requested."); }).catch((err: Error) => setError(err.message)).finally(() => setSaving(false));
  };

  const circular = selected?.circular;
  const originalText = circular?.content?.original_text || circular?.content?.clean_text || "Original text unavailable.";
  const sourceExcerpts = circular?.simplification?.source_excerpts || [];
  const importantDates = circular?.simplification?.important_dates || [];
  const warnings = circular?.simplification?.warnings || [];

  return <div className="review-layout">
    <aside className="review-queue"><p className="eyebrow">Editorial desk</p><h1>Review workspace</h1><p className="muted">Compare every draft with the official source before publication.</p><label className="queue-filter">Queue status<select value={status} onChange={(event) => { setStatus(event.target.value); setSelected(null); }}><option value="all">All open reviews</option>{statuses.map((value) => <option key={value} value={value}>{value.replace("_", " ")}</option>)}</select></label>{error && <p className="inline-error" role="alert">{error}</p>}<div className="queue-list">{loading ? <p className="muted">Loading review queue...</p> : reviews.map((review) => <button key={review.id} className={selected?.id === review.id ? "queue-item active" : "queue-item"} onClick={() => openReview(review.id)}><strong>{review.simplified_title || "Untitled draft"}</strong><span>{review.language} · {review.status.replace("_", " ")}</span></button>)}{!loading && reviews.length === 0 && <p className="muted">No reviews in this queue.</p>}</div></aside>
    {selected ? <main className="workspace"><div className="workspace-heading"><div><p className="eyebrow">{circular?.source?.source_name || "Source document"}</p><h2>{circular?.identity?.title_original || "Review draft"}</h2></div><span className={`status-dot ${selected.status}`}>{selected.status.replace("_", " ")}</span></div>{notice && <div className="notice-box">{notice}</div>}<div className="review-toolbar"><label>Translation selector<select value={translationLanguage} onChange={(event) => setTranslationLanguage(event.target.value)}><option value={selected.language}>{selected.language} draft</option>{selected.translation && selected.translation.language !== selected.language && <option value={selected.translation.language}>{selected.translation.language} translation</option>}</select></label><span className="muted">Editing the selected review revision</span></div><div className="compare-grid"><section className="source-column"><h3>Original government document</h3><div className="document-pane">{originalText}</div>{sourceExcerpts.length > 0 && <><h3>Source excerpts</h3><div className="excerpt-list">{sourceExcerpts.map((excerpt) => <blockquote key={excerpt}>{excerpt}</blockquote>)}</div></>}</section><section className="draft-column"><h3>AI-generated draft</h3><label>Draft title<input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label><label>Draft text<textarea value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} /></label><h3>Important facts</h3><div className="fact-strip">{importantDates.length ? importantDates.map((item) => <span key={JSON.stringify(item)}>{String(item.description || item.date || item.amount || "Fact")}</span>) : <span className="muted">No extracted dates yet</span>}</div>{warnings.length > 0 && <div className="warning-box"><strong>Warnings</strong>{warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}<label>Reviewer notes<textarea className="notes-area" value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} placeholder="Record corrections or the reason for rejection..." /></label><label>Redraft feedback<textarea className="feedback-area" value={draft.feedback} onChange={(event) => setDraft({ ...draft, feedback: event.target.value })} placeholder="Optional guidance for the next AI draft" /></label><div className="workspace-actions"><button className="button secondary" disabled={saving} onClick={save}>{saving ? "Saving..." : "Save edits"}</button><button className="button danger" disabled={saving} onClick={() => action("reject")}>Reject</button><button className="button secondary" disabled={saving} onClick={() => action("redraft")}>Request redraft</button><button className="button primary" disabled={saving} onClick={() => action("approve")}>Approve and publish</button></div></section></div></main> : <div className="state-box">Select a review from the queue to begin.</div>}
  </div>;
}
