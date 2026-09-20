/**
 * JanVaani — shared TypeScript types matching the backend Pydantic models.
 */

// ─── Source ──────────────────────────────────────────────────────────────────

export interface Source {
  source_id: string;
  name: string;
  base_domains: string[];
  seed_urls: string[];
  adapter: string;
  government_level: "central" | "state";
  state: string | null;
  allowed_document_types: string[];
  allowed_path_patterns: string[];
  crawl_policy: {
    max_pages_per_run: number;
    request_delay_seconds: number;
    max_documents_per_run: number;
    respect_robots: boolean;
    stop_on_403: boolean;
    stop_on_429: boolean;
  };
  status: "active" | "paused" | "disabled" | string;
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
  source_id: string | null;
  source_name: string | null;
  source_url: string | null;
  official_document_url: string | null;
  title: string | null;
  document_number: string | null;
  department: string | null;
  document_type: string | null;
  government_level: "central" | "state" | string | null;
  state: string | null;
  language: string | null;
  original_text: string;
  simplified_title: string | null;
  simplified_text: string | null;
  summary: string | null;
  who_is_affected: string | null;
  required_action: string | null;
  key_points?: string[];
  action_items?: string[];
  important_dates: Record<string, unknown>[];
  amounts: Record<string, unknown>[];
  eligibility: string[];
  warnings: string[];
  keywords: string[];
  effective_from: string | null;
  effective_until: string | null;
  published_date: string | null;
  last_updated?: string | null;
  retrieved_at?: string | null;
  review_date?: string | null;
  source_excerpts?: string[];
  processing_status?: string;
  published: boolean;
  translation_languages: string[];
  audio_available?: boolean;
  attachments?: Attachment[];
}

export interface Attachment {
  url: string;
  type: string;
  title: string | null;
  file_size_bytes: number | null;
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
  circular?: ReviewCircular;
  translation?: Translation | null;
}

export interface ReviewCircular {
  id: string;
  source?: { source_name?: string | null; official_document_url?: string | null };
  identity?: { title_original?: string | null };
  classification?: { department?: string | null; language?: string | null };
  dates?: { published_date?: string | null };
  content?: { original_text?: string | null; clean_text?: string | null; sections?: ContentSection[] };
  simplification?: { important_dates?: Record<string, unknown>[]; warnings?: string[]; source_excerpts?: string[] };
}

export interface ContentSection {
  heading: string | null;
  text: string;
  page_start?: number | null;
  page_end?: number | null;
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
  sources: { source_id: string; name: string }[];
  departments: string[];
  states: string[];
  document_types: string[];
  languages: string[];
}

export interface IngestionJob {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  circular_id?: string | null;
  processing_status?: string | null;
  error?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface HealthResponse {
  status: string;
  database: string;
  storage: string;
}
