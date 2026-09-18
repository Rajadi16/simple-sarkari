/**
 * TanStack Query hooks for JanVaani API.
 *
 * Each hook wraps an API call with caching, loading states, and error handling.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ─── Public ──────────────────────────────────────────────────────────────────

export function useCirculars(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["circulars", params],
    queryFn: () => api.searchCirculars(params),
  });
}

export function useCircular(id: string) {
  return useQuery({
    queryKey: ["circular", id],
    queryFn: () => api.getCircular(id),
    enabled: !!id,
  });
}

export function useTranslation(circularId: string, language: string) {
  return useQuery({
    queryKey: ["translation", circularId, language],
    queryFn: () => api.getTranslation(circularId, language),
    enabled: !!circularId && !!language,
  });
}

export function useCatalogueFilters() {
  return useQuery({
    queryKey: ["catalogue-filters"],
    queryFn: () => api.getFilters(),
    staleTime: 60_000,
  });
}

// ─── Admin: Sources ──────────────────────────────────────────────────────────

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: () => api.listSources(),
  });
}

export function useTriggerCrawl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, opts }: { sourceId: string; opts?: Record<string, unknown> }) =>
      api.triggerCrawl(sourceId, opts as never),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

// ─── Admin: Reviews ──────────────────────────────────────────────────────────

export function useReviews(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["reviews", params],
    queryFn: () => api.listReviews(params),
  });
}

export function useReview(id: string) {
  return useQuery({
    queryKey: ["review", id],
    queryFn: () => api.getReview(id),
    enabled: !!id,
  });
}

export function useApproveReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.approveReview(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}

export function useRejectReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.rejectReview(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}

// ─── Admin: Jobs ─────────────────────────────────────────────────────────────

export function useJobs(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => api.listJobs(params),
  });
}

// ─── Admin: Ingestion ────────────────────────────────────────────────────────

export function useIngestUrl() {
  return useMutation({
    mutationFn: ({ url, sourceId }: { url: string; sourceId: string }) => api.ingestUrl(url, sourceId),
  });
}

export function useIngestText() {
  return useMutation({
    mutationFn: (data: Parameters<typeof api.ingestText>[0]) => api.ingestText(data),
  });
}
