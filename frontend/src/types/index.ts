/**
 * JanVaani — shared TypeScript types matching the backend Pydantic models.
 */

// ─── Source ──────────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  name: string;
  base_domains: string[];
  seed_urls: string[];
  adapter: string;
  government_level: "central" | "state";
  state: string | null;
  allowed_content_types: string[];
  enabled: boolean;
  crawl_interval_minutes: number;
  request_delay_seconds: number;
  max_pages_per_run: number;
  max_documents_per_run: number;
  created_at: string;
  updated_at: string;
}

export interface CrawlRun {
  id: string;
  source_id: string;
  status: "pending" | "running" | "completed" | "failed";
  pages_fetched: number;
  documents_discovered: number;
  documents_new: number;
  documents_duplicate: number;
  blocked_requests: number;
  errors: Record<string, unknown>[];
  started_at: string;
  completed_at: string | null;
}

// ─── Circular ────────────────────────────────────────────────────────────────

export interface Circular {
  id: string;
  source_id: string;
  source_url: string;
  title: string;
  subject: string | null;
  department: string | null;
  document_type: string | null;
  government_level: string;
  state: string | null;
  original_language: string;
  original_text: string | null;
  simplified_title: string | null;
  simplified_text: string | null;
  summary: string | null;
  who_is_affected: string | null;
  required_action: string | null;
  important_dates: Record<string, unknown>[];
  amounts: Record<string, unknown>[];
  eligibility: string[];
  warnings: string[];
  keywords: string[];
  processing_status: string;
  published: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Translation ─────────────────────────────────────────────────────────────

export interface Translation {
  id: string;
  circular_id: string;
  language: string;
  revision: number;
  translated_title: string | null;
  translated_text: string | null;
  translated_summary: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ─── Review ──────────────────────────────────────────────────────────────────

export interface Review {
  id: string;
  circular_id: string;
  translation_id: string;
  language: string;
  status: "draft" | "in_review" | "changes_requested" | "approved" | "rejected" | "published";
  simplified_title: string | null;
  simplified_text: string | null;
  translation_text: string | null;
  reviewer_notes: string | null;
  risk_tags: string[];
  assigned_to: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Job ─────────────────────────────────────────────────────────────────────

export interface Job {
  id: string;
  job_type: "crawl" | "extraction" | "translation" | "audio";
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  document_id: string | null;
  source_id: string | null;
  language: string | null;
  attempts: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

// ─── Audio ───────────────────────────────────────────────────────────────────

export interface AudioAsset {
  id: string;
  circular_id: string;
  language: string;
  status: "pending" | "generating" | "ready" | "failed";
  s3_key: string | null;
}

// ─── API Responses ───────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface CatalogueFilters {
  sources: string[];
  departments: string[];
  states: string[];
  document_types: string[];
  languages: string[];
}

export interface HealthResponse {
  status: string;
  database: string;
  storage: string;
}
