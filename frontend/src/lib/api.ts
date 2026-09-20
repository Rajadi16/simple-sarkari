/**
 * JanVaani API client — all backend communication goes through here.
 *
 * Uses relative /api paths so the Vite proxy handles routing to FastAPI.
 * Never calls AWS services directly.
 */

import type {
  Circular,
  Translation,
  Review,
  Source,
  CrawlRun,
  Job,
  PaginatedResponse,
  CatalogueFilters,
  HealthResponse,
  IngestionJob,
} from "@/types";

// ─── Config ──────────────────────────────────────────────────────────────────

const BASE = "/api";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("reviewer_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...init?.headers,
    },
    ...init,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = Array.isArray(error.detail)
      ? error.detail.map((item: { msg?: string }) => item.msg || "Request was rejected").join("; ")
      : error.detail;
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── System ──────────────────────────────────────────────────────────────────

export const api = {
  health: () => request<HealthResponse>("/health"),
  ready: () => request<HealthResponse>("/health/ready"),

  // ─── Public catalogue ────────────────────────────────────────────────
  searchCirculars: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedResponse<Circular>>(`/circulars${qs}`);
  },
  getCircular: (id: string) =>
    request<Circular>(`/circulars/${id}`),
  getTranslation: (circularId: string, language: string) =>
    request<Translation>(`/circulars/${circularId}/translations/${language}`),
  getAudio: (circularId: string, language: string) =>
    request<{ url?: string; audio_available: boolean }>(`/circulars/${circularId}/audio/${language}`),
  getFilters: () =>
    request<CatalogueFilters>("/catalogue/filters"),
  subscribe: (email: string) =>
    request<{ status: "subscribed" | "already_subscribed" | "resubscribed" }>("/subscribers", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  // ─── Admin: Ingestion ────────────────────────────────────────────────
  ingestUrl: (url: string, sourceId: string) =>
    request<{ job_id: string; status: string }>("/admin/ingestions/url", {
      method: "POST",
      body: JSON.stringify({ url, source_id: sourceId }),
    }),
  ingestText: (data: { title: string; publisher: string; source_url: string; original_language: string; text: string; target_languages?: string[]; government_level?: string; state?: string; department?: string }) =>
    request<{ job_id: string; status: string }>("/admin/ingestions/text", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getIngestion: (id: string) =>
    request<IngestionJob>(`/admin/ingestions/${id}`),
  retryIngestion: (id: string) =>
    request<{ status: string }>(`/admin/ingestions/${id}/retry`, { method: "POST" }),

  // ─── Admin: Sources ──────────────────────────────────────────────────
  listSources: () =>
    request<Source[]>("/admin/sources"),
  getSource: (id: string) =>
    request<Source>(`/admin/sources/${id}`),
  createSource: (source: Partial<Source>) =>
    request<Source>("/admin/sources", { method: "POST", body: JSON.stringify(source) }),
  updateSource: (id: string, updates: Partial<Source>) =>
    request<Source>(`/admin/sources/${id}`, { method: "PATCH", body: JSON.stringify(updates) }),
  triggerCrawl: (sourceId: string, opts?: { max_pages?: number; max_documents?: number; backfill?: boolean }) =>
    request<{ run_id: string; status: string }>(`/admin/sources/${sourceId}/crawl`, {
      method: "POST",
      body: JSON.stringify(opts || {}),
    }),
  getCrawlRun: (runId: string) =>
    request<CrawlRun>(`/admin/crawl-runs/${runId}`),

  // ─── Admin: Jobs ─────────────────────────────────────────────────────
  listJobs: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedResponse<Job>>(`/admin/jobs/${qs ? qs : ""}`);
  },
  getJob: (id: string) =>
    request<Job>(`/admin/jobs/${id}`),
  retryJob: (id: string) =>
    request<Job>(`/admin/jobs/${id}/retry`, { method: "POST" }),
  cancelJob: (id: string) =>
    request<Job>(`/admin/jobs/${id}/cancel`, { method: "POST" }),

  // ─── Admin: Reviews ──────────────────────────────────────────────────
  listReviews: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedResponse<Review>>(`/admin/reviews/${qs ? qs : ""}`);
  },
  getReview: (id: string) =>
    request<Review>(`/admin/reviews/${id}`),
  saveReviewEdits: (id: string, edits: Partial<Review>) =>
    request<Review>(`/admin/reviews/${id}`, { method: "PATCH", body: JSON.stringify(edits) }),
  redraftReview: (id: string, feedback: string) =>
    request<Review>(`/admin/reviews/${id}/redraft`, { method: "POST", body: JSON.stringify({ feedback }) }),
  approveReview: (id: string) =>
    request<Review>(`/admin/reviews/${id}/approve`, { method: "POST" }),
  rejectReview: (id: string, reason: string) =>
    request<Review>(`/admin/reviews/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  flagReview: (id: string) =>
    request<Review>(`/admin/reviews/${id}/flag`, { method: "POST" }),

  // ─── Admin: Translations & Audio ─────────────────────────────────────
  requestTranslations: (circularId: string, languages: string[]) =>
    request<{ translation_ids: string[] }>(`/admin/circulars/${circularId}/translations`, {
      method: "POST",
      body: JSON.stringify({ languages }),
    }),
  getTranslationStatus: (circularId: string) =>
    request<Translation[]>(`/admin/circulars/${circularId}/translations`),
  requestAudio: (circularId: string, language: string) =>
    request<{ status: string }>(`/admin/circulars/${circularId}/audio/${language}`, { method: "POST" }),
  getAudioStatus: (circularId: string, language: string) =>
    request<{ status: string }>(`/admin/circulars/${circularId}/audio/${language}/status`),
};
