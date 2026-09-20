/**
 * Circular detail page — shows original, simplified, translated text + audio.
 */

import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Circular, Translation } from "@/types";

export default function CircularPage() {
  const { id } = useParams<{ id: string }>();

  const [circular, setCircular] = useState<Circular | null>(null);
  const [language, setLanguage] = useState("en-IN");
  const [translation, setTranslation] = useState<Translation | null>(null);
  const [translationLoading, setTranslationLoading] = useState(false);
  const [translationError, setTranslationError] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { if (id) api.getCircular(id).then((value) => { setCircular(value); setLanguage(value.language || value.translation_languages[0] || "en-IN"); }).catch((err: Error) => setError(err.message)); }, [id]);
  useEffect(() => {
    if (!id || !circular) return;
    const isOriginalLanguage = language === circular.language;
    setTranslationError("");
    setTranslationLoading(!isOriginalLanguage);
    if (isOriginalLanguage) setTranslation(null);
    else api.getTranslation(id, language).then(setTranslation).catch((err: Error) => { setTranslation(null); setTranslationError(err.message); }).finally(() => setTranslationLoading(false));
    api.getAudio(id, language).then((value) => setAudioUrl(value.url || "")).catch(() => setAudioUrl(""));
  }, [id, language, circular]);

  if (error) return <div className="state-box error-state">{error}</div>;
  if (!circular) return <div className="state-box">Loading circular...</div>;
  const isOriginal = language === circular.language;
  const body = isOriginal ? circular.simplified_text : translation?.translated_text;
  return (
    <div className="page-stack reader-page">
      <div className="reader-header"><div><p className="eyebrow">{circular.source_name || "Government circular"}</p><h1>{circular.simplified_title || circular.title}</h1><p className="lede">{circular.summary}</p></div><a className="button secondary" href={circular.official_document_url || circular.source_url || "#"} target="_blank" rel="noreferrer">Open official source</a></div>
      <div className="trust-banner"><strong>AI-assisted and human-reviewed</strong><span>Original government source controls if there is any conflict.</span></div>
      {(circular.required_action || circular.key_points?.length) ? <section className="action-panel"><div><p className="eyebrow">What this means for you</p><h2>{circular.required_action || "Key points from this circular"}</h2></div>{circular.key_points?.length ? <ul>{circular.key_points.map((point) => <li key={point}>{point}</li>)}</ul> : null}</section> : null}
      <div className="reader-grid"><main className="reader-main">
        <div className="language-tabs">{[circular.language, ...circular.translation_languages].filter((value, index, list): value is string => Boolean(value) && list.indexOf(value) === index).map((value) => <button className={language === value ? "active" : ""} key={value} onClick={() => setLanguage(value)}>{languageLabel(value)}</button>)}</div>
        <div className="audio-row">{audioUrl ? <audio controls src={audioUrl} /> : <span className="muted">{language === "kn-IN" ? "Audio is not available for Kannada. The translation remains available as text." : `Audio is not available for ${languageLabel(language)}.`}</span>}</div>
        <article className="reading-surface"><p className="eyebrow">{isOriginal ? "Simplified explanation" : `Translation: ${language}`}</p><h2>{isOriginal ? circular.simplified_title : translation?.translated_title || circular.simplified_title}</h2>{translationLoading ? <div className="reading-copy">Loading this translation...</div> : translationError ? <div className="reading-copy error-state">{translationError}</div> : <div className="reading-copy">{body || "This version is not available yet."}</div>}</article>
        <details className="original-panel"><summary>Read original government text</summary><div className="reading-copy">{circular.original_text || "Original text is unavailable."}</div></details>
        {circular.source_excerpts?.length ? <section className="source-excerpts"><p className="eyebrow">Traceable facts</p><h3>Source excerpts</h3>{circular.source_excerpts.map((excerpt) => <blockquote key={excerpt}>{excerpt}</blockquote>)}</section> : null}
      </main><aside className="reader-aside"><InfoBlock title="Important dates" values={circular.important_dates.map(formatFact)} /><InfoBlock title="Amounts" values={circular.amounts.map(formatFact)} /><InfoBlock title="Who is affected" values={circular.who_is_affected ? [circular.who_is_affected] : []} /><InfoBlock title="Document details" values={[circular.department, circular.published_date && `Published ${circular.published_date}`, circular.retrieved_at && `Retrieved ${formatDate(circular.retrieved_at)}`, circular.review_date && `Reviewed ${formatDate(circular.review_date)}`].filter(Boolean) as string[]} />{circular.attachments?.length ? <section className="info-block"><h3>Original attachments</h3>{circular.attachments.map((attachment) => <a className="attachment-link" href={attachment.url} target="_blank" rel="noreferrer" key={attachment.url}>{attachment.title || attachment.type} ↗</a>)}</section> : null}</aside></div>
    </div>
  );
}

function formatFact(item: Record<string, unknown>) { return String(item.description || item.date || item.amount || Object.values(item)[0] || ""); }
function languageLabel(value: string) { return ({ "en-IN": "English", "hi-IN": "Hindi", "kn-IN": "Kannada" }[value] || value); }
function formatDate(value: string) { return new Date(value).toLocaleDateString("en-IN", { dateStyle: "medium" }); }
function InfoBlock({ title, values }: { title: string; values: string[] }) { return <section className="info-block"><h3>{title}</h3>{values.length ? values.map((value) => <p key={value}>{value}</p>) : <p className="muted">Not specified</p>}</section>; }
