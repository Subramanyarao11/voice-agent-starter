import { z } from "zod";

import { healthSchema, request } from "@/lib/api";

const adminMeSchema = z.object({
  actor_id: z.string(),
  role: z.string(),
  permissions: z.array(z.string()),
});

const providerStatusSchema = z.object({
  name: z.string(),
  configured: z.boolean(),
  health: z.string(),
  requests: z.number(),
  failures: z.number(),
  cache_hits: z.number().default(0),
  cache_misses: z.number().default(0),
  budget_usd: z.number().nullable().optional(),
  reserved_usd: z.number().nullable().optional(),
  observed_usd: z.number().nullable().optional(),
  remaining_usd: z.number().nullable().optional(),
  controls_available: z.boolean().default(false),
  note: z.string().default(""),
});

const overviewSchema = z.object({
  generated_at: z.string(),
  data_fresh_at: z.string().nullable(),
  partial_data: z.boolean(),
  window_hours: z.number(),
  health: healthSchema,
  traffic: z.object({
    requests: z.number(),
    errors: z.number(),
    error_rate: z.number(),
    p50_latency_ms: z.number(),
    p95_latency_ms: z.number(),
    active_sessions: z.number(),
    turns: z.number(),
    language_mix: z.record(z.string(), z.number()),
  }),
  quality: z.object({
    escalations: z.number(),
    open_escalations: z.number(),
    escalation_rate: z.number(),
    no_match_turns: z.number(),
    active_benefits: z.number(),
    verified_benefits: z.number(),
    machine_reviewed_benefits: z.number(),
    needs_review_benefits: z.number(),
    stale_benefits: z.number(),
    illustrative_benefits: z.number(),
    latest_import_at: z.string().nullable(),
  }),
  providers: z.array(providerStatusSchema),
  recent_errors: z.array(
    z.object({
      request_id: z.string().nullable(),
      route: z.string(),
      method: z.string(),
      status_code: z.number().nullable(),
      error_code: z.string().nullable(),
      duration_ms: z.number().nullable(),
      created_at: z.string(),
    }),
  ),
});

const conversationListSchema = z.object({
  items: z.array(
    z.object({
      session_key: z.string(),
      state_code: z.string(),
      language_code: z.string(),
      turn_count: z.number(),
      created_at: z.string(),
      last_contact_at: z.string(),
      last_intent: z.string().nullable(),
    }),
  ),
  total: z.number(),
  data_fresh_at: z.string().nullable(),
});

const telemetryEventSchema = z.object({
  id: z.string(),
  event_type: z.string(),
  request_id: z.string().nullable(),
  route: z.string(),
  method: z.string(),
  status_code: z.number().nullable(),
  duration_ms: z.number().nullable(),
  surface: z.string(),
  language_code: z.string().nullable(),
  state_code: z.string().nullable(),
  provider: z.string().nullable(),
  outcome: z.string(),
  error_code: z.string().nullable(),
  safe_metadata: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

const reviewSchema = z.object({
  id: z.string(),
  domain: z.string(),
  name: z.string(),
  state_code: z.string().nullable(),
  verification_status: z.string(),
  is_active: z.boolean(),
  source_title: z.string(),
  source_document_url: z.string(),
  source_excerpt: z.string().nullable(),
  automated_review: z.record(z.string(), z.unknown()),
  verified_by: z.string().nullable(),
  verified_at: z.string().nullable(),
  last_verified_date: z.string().nullable(),
  valid_from: z.string().nullable(),
  valid_until: z.string().nullable(),
});

const reviewQueueSchema = z.object({
  items: z.array(reviewSchema),
  total: z.number(),
  status_counts: z.record(z.string(), z.number()),
  data_fresh_at: z.string().nullable(),
});

const ticketSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  reason: z.string(),
  caller_context: z.record(z.string(), z.unknown()),
  transcript_excerpt: z.string(),
  status: z.string(),
  created_at: z.string(),
  resolved_at: z.string().nullable(),
});

const providerListSchema = z.object({
  generated_at: z.string(),
  providers: z.array(providerStatusSchema),
  controls_note: z.string(),
});

const languageReadinessSchema = z.object({
  code: z.string(),
  name: z.string(),
  native_name: z.string(),
  active: z.boolean(),
  prompt_ready: z.boolean(),
  interface_status: z.string(),
  data_status: z.string(),
  localized_benefits: z.number(),
  active_benefits: z.number(),
  stt_provider: z.string(),
  tts_provider: z.string(),
  voice_status: z.string(),
  rollout_status: z.string(),
});

const auditEventSchema = z.object({
  id: z.string(),
  actor_id: z.string(),
  actor_role: z.string(),
  action: z.string(),
  target_type: z.string(),
  target_id: z.string(),
  reason: z.string(),
  safe_before: z.record(z.string(), z.unknown()),
  safe_after: z.record(z.string(), z.unknown()),
  request_id: z.string().nullable(),
  created_at: z.string(),
});

const importRunSchema = z.object({
  id: z.string(),
  source_name: z.string(),
  state_code: z.string().nullable(),
  started_at: z.string(),
  completed_at: z.string().nullable(),
  model_name: z.string(),
  prompt_version: z.string(),
  input_count: z.number(),
  accepted_count: z.number(),
  failed_count: z.number(),
  review_sample_size: z.number(),
  manifest_json: z.record(z.string(), z.unknown()),
});

const systemSchema = z.object({
  environment: z.string(),
  process_started_at: z.string(),
  generated_at: z.string(),
  git_commit_sha: z.string(),
  migration_revision: z.string().nullable(),
  database_mode: z.string(),
  configuration: z.record(z.string(), z.boolean()),
  deployment_notes: z.array(z.string()),
});

export type AdminMe = z.infer<typeof adminMeSchema>;
export type AdminOverview = z.infer<typeof overviewSchema>;
export type ConversationList = z.infer<typeof conversationListSchema>;
export type TelemetryEvent = z.infer<typeof telemetryEventSchema>;
export type ReviewQueue = z.infer<typeof reviewQueueSchema>;
export type ReviewItem = z.infer<typeof reviewSchema>;
export type AdminTicket = z.infer<typeof ticketSchema>;
export type ProviderList = z.infer<typeof providerListSchema>;
export type LanguageReadiness = z.infer<typeof languageReadinessSchema>;
export type AuditEvent = z.infer<typeof auditEventSchema>;
export type ImportRun = z.infer<typeof importRunSchema>;
export type AdminSystem = z.infer<typeof systemSchema>;

function adminInit(token: string, init?: RequestInit): RequestInit {
  return {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  };
}

export function getAdminMe(token: string): Promise<AdminMe> {
  return request("/api/admin/me", adminMeSchema, adminInit(token));
}

export function getAdminOverview(token: string, hours = 24): Promise<AdminOverview> {
  return request(`/api/admin/overview?hours=${hours}`, overviewSchema, adminInit(token));
}

export function getAdminConversations(token: string): Promise<ConversationList> {
  return request("/api/admin/conversations?limit=100", conversationListSchema, adminInit(token));
}

export function getAdminTelemetry(token: string): Promise<TelemetryEvent[]> {
  return request("/api/admin/telemetry/events?limit=100", z.array(telemetryEventSchema), adminInit(token));
}

export function getAdminReviews(token: string, status = "needs_review"): Promise<ReviewQueue> {
  return request(
    `/api/admin/benefits/review?status=${encodeURIComponent(status)}&limit=100`,
    reviewQueueSchema,
    adminInit(token),
  );
}

export function reviewAdminBenefit(
  token: string,
  benefitId: string,
  payload: { verification_status: string; reason: string; activate?: boolean },
): Promise<ReviewItem> {
  return request(`/api/admin/benefits/${encodeURIComponent(benefitId)}/review`, reviewSchema, adminInit(token, {
    method: "POST",
    body: JSON.stringify(payload),
  }));
}

export function getAdminEscalations(token: string): Promise<AdminTicket[]> {
  return request("/api/escalations?status=open&limit=100", z.array(ticketSchema), adminInit(token));
}

export function resolveAdminEscalation(token: string, ticketId: string): Promise<AdminTicket> {
  return request(`/api/escalations/${encodeURIComponent(ticketId)}/resolve`, ticketSchema, adminInit(token, {method: "POST"}));
}

export function getAdminProviders(token: string): Promise<ProviderList> {
  return request("/api/admin/providers", providerListSchema, adminInit(token));
}

export function getAdminLanguages(token: string): Promise<LanguageReadiness[]> {
  return request("/api/admin/languages", z.array(languageReadinessSchema), adminInit(token));
}

export function getAdminAuditEvents(token: string): Promise<AuditEvent[]> {
  return request("/api/admin/audit-events?limit=100", z.array(auditEventSchema), adminInit(token));
}

export function getAdminImports(token: string): Promise<ImportRun[]> {
  return request("/api/admin/imports?limit=50", z.array(importRunSchema), adminInit(token));
}

export function getAdminSystem(token: string): Promise<AdminSystem> {
  return request("/api/admin/system", systemSchema, adminInit(token));
}
