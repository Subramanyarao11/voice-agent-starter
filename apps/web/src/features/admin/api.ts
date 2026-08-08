import { z } from "zod";

import { healthSchema, request } from "@/lib/api";

const adminMeSchema = z.object({
  actor_id: z.string(),
  role: z.string(),
  permissions: z.array(z.string()),
  auth_source: z.string(),
  mfa_verified: z.boolean(),
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

const notificationOverviewSchema = z.object({
  generated_at: z.string(),
  window_hours: z.number(),
  channels: z.array(
    z.object({
      channel: z.string(),
      configured: z.boolean(),
      policy_enabled: z.boolean(),
      circuit_state: z.string(),
      primary_provider: z.string(),
      fallback_provider: z.string(),
      sender_ready: z.boolean(),
      templates_total: z.number(),
      templates_approved: z.number(),
      template_ready: z.boolean(),
      accepted: z.number(),
      delivered: z.number(),
      failed: z.number(),
      suppressed: z.number(),
      awaiting_report: z.number(),
      stale_awaiting_report: z.number(),
      delivery_rate: z.number(),
      last_success_at: z.string().nullable(),
      last_failure_at: z.string().nullable(),
      last_report_at: z.string().nullable(),
      top_error_class: z.string(),
      cost_minor_units: z.number(),
      cost_currency: z.string(),
      verified_contacts: z.number(),
      opted_out_contacts: z.number(),
      note: z.string(),
    }),
  ),
  voice: z.object({
    configured: z.boolean(),
    policy_enabled: z.boolean(),
    calls: z.number(),
    answered: z.number(),
    ended: z.number(),
    average_duration_seconds: z.number(),
    note: z.string(),
  }),
  budget_daily_spent_minor_units: z.number(),
  budget_daily_limit_minor_units: z.number().nullable(),
  budget_monthly_spent_minor_units: z.number(),
  budget_monthly_limit_minor_units: z.number().nullable(),
  cost_currency: z.string(),
  cost_by_language: z.record(z.string(), z.number()),
  cost_by_provider: z.record(z.string(), z.number()),
  controls_note: z.string(),
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
  trace_id: z.string().nullable(),
  trace_url: z.string().nullable(),
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
  category: z.string(),
  description: z.string(),
  eligibility_initial: z.record(z.string(), z.unknown()),
  eligibility_renewal: z.record(z.string(), z.unknown()).nullable(),
  benefits_text: z.string(),
  documents_required: z.array(z.string()),
  application_process: z.string(),
  source_url: z.string(),
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
  localized_summary: z.record(z.string(), z.string()),
  job_metadata: z.record(z.string(), z.unknown()).default(() => ({})),
  content_revision: z.number(),
});

const reviewQueueSchema = z.object({
  items: z.array(reviewSchema),
  total: z.number(),
  status_counts: z.record(z.string(), z.number()),
  data_fresh_at: z.string().nullable(),
});

const benefitIssueReportSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  benefit_name: z.string(),
  category: z.string(),
  description: z.string(),
  locale: z.string(),
  status: z.string(),
  source_title: z.string(),
  source_document_url: z.string(),
  created_at: z.string(),
  resolved_at: z.string().nullable(),
  resolved_by: z.string().nullable(),
});

const ticketNoteSchema = z.object({
  id: z.string(),
  actor_id: z.string(),
  actor_role: z.string(),
  text: z.string(),
  created_at: z.string(),
});

const ticketSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  reason: z.string(),
  caller_context: z.record(z.string(), z.unknown()),
  transcript_excerpt: z.string(),
  status: z.string(),
  assigned_to: z.string().nullable(),
  claimed_at: z.string().nullable(),
  sla_due_at: z.string().nullable(),
  sla_breached: z.boolean(),
  department: z.string(),
  routing_location: z.string(),
  routing_source: z.string(),
  routing_directory_entry_id: z.string().nullable().optional(),
  routing_source_url: z.string().default(""),
  routing_verified_at: z.string().nullable().optional(),
  operator_notes: z.array(ticketNoteSchema),
  created_at: z.string(),
  updated_at: z.string().nullable(),
  resolved_at: z.string().nullable(),
  resolved_by: z.string().nullable(),
  resolution_code: z.string().nullable(),
  resolution_note: z.string(),
});

const directoryEntrySchema = z.object({
  id: z.string(),
  entry_key: z.string(),
  state_code: z.string(),
  district_code: z.string(),
  district_name: z.string(),
  service_domain: z.string(),
  pincode: z.string(),
  pincode_prefix: z.string(),
  department_code: z.string(),
  department_name: z.string(),
  help_centre_name: z.string(),
  address: z.string(),
  phone: z.string(),
  email: z.string(),
  website_url: z.string(),
  source_name: z.string(),
  source_url: z.string(),
  source_record_id: z.string(),
  source_last_verified: z.string().nullable(),
  approval_status: z.string(),
  is_active: z.boolean(),
  stale: z.boolean(),
  priority: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

const directoryListSchema = z.object({
  generated_at: z.string(),
  stale_after_days: z.number(),
  entries: z.array(directoryEntrySchema),
  total: z.number(),
  status_counts: z.record(z.string(), z.number()),
});

const providerPolicySchema = z.object({
  id: z.string(),
  provider: z.string(),
  scope: z.string(),
  enabled: z.boolean(),
  primary_provider: z.string(),
  fallback_provider: z.string().nullable(),
  circuit_state: z.string(),
  daily_budget_usd: z.number().nullable(),
  monthly_budget_usd: z.number().nullable(),
  override_expires_at: z.string().nullable(),
  revision: z.number(),
  config: z.record(z.string(), z.unknown()),
  updated_by: z.string(),
  updated_at: z.string(),
});

const providerListSchema = z.object({
  generated_at: z.string(),
  providers: z.array(providerStatusSchema),
  policies: z.array(providerPolicySchema),
  controls_note: z.string(),
});

const languageReadinessSchema = z.object({
  code: z.string(),
  name: z.string(),
  native_name: z.string(),
  active: z.boolean(),
  prompt_ready: z.boolean(),
  interface_status: z.string(),
  interface_review_status: z.string(),
  data_status: z.string(),
  localized_benefits: z.number(),
  active_benefits: z.number(),
  stt_provider: z.string(),
  tts_provider: z.string(),
  voice_status: z.string(),
  voice_review_status: z.string(),
  native_speaker_status: z.string(),
  prompt_status: z.string(),
  content_status: z.string(),
  understanding_status: z.string(),
  accessibility_status: z.string(),
  evidence_url: z.string(),
  review_notes: z.string(),
  reviewed_by: z.string().nullable(),
  reviewed_at: z.string().nullable(),
  activated_at: z.string().nullable(),
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

const evaluationRunSchema = z.object({
  id: z.string(),
  suite_name: z.string(),
  suite_version: z.string(),
  passed: z.boolean(),
  case_count: z.number(),
  passed_count: z.number(),
  failed_count: z.number(),
  language_counts: z.record(z.string(), z.number()),
  report_json: z.record(z.string(), z.unknown()),
  started_at: z.string(),
  completed_at: z.string().nullable(),
});

const freshnessSchema = z.object({
  generated_at: z.string(),
  stale_after_days: z.number(),
  data_fresh_at: z.string().nullable(),
  sources: z.array(
    z.object({
      dataset: z.string(),
      total_rows: z.number(),
      active_rows: z.number(),
      human_verified_rows: z.number(),
      machine_structured_rows: z.number(),
      stale_rows: z.number(),
      expired_rows: z.number(),
      missing_source_rows: z.number(),
      oldest_verified_date: z.string().nullable(),
      latest_verified_date: z.string().nullable(),
      latest_import_at: z.string().nullable(),
      status: z.string(),
    }),
  ),
  alerts: z.array(
    z.object({
      id: z.string(),
      alert_key: z.string(),
      benefit_id: z.string().nullable(),
      dataset: z.string(),
      alert_type: z.string(),
      severity: z.string(),
      status: z.string(),
      message: z.string(),
      first_seen_at: z.string(),
      last_seen_at: z.string(),
      resolved_at: z.string().nullable(),
      resolved_by: z.string().nullable(),
      safe_metadata: z.record(z.string(), z.unknown()),
    }),
  ),
  alert_counts: z.record(z.string(), z.number()),
});

const benefitVersionSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  version: z.number(),
  action: z.string(),
  actor_id: z.string(),
  actor_role: z.string(),
  reason: z.string(),
  snapshot: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

const benefitVersionListSchema = z.object({
  benefit_id: z.string(),
  current_revision: z.number(),
  versions: z.array(benefitVersionSchema),
});

const featureFlagSchema = z.object({
  id: z.string(),
  key: z.string(),
  description: z.string(),
  enabled: z.boolean(),
  rollout_percentage: z.number(),
  target_languages: z.array(z.string()),
  target_states: z.array(z.string()),
  config: z.record(z.string(), z.unknown()),
  revision: z.number(),
  updated_by: z.string(),
  updated_at: z.string(),
});

const featureFlagListSchema = z.object({
  generated_at: z.string(),
  flags: z.array(featureFlagSchema),
  revisions: z.array(
    z.object({
      id: z.string(),
      flag_id: z.string(),
      revision: z.number(),
      action: z.string(),
      actor_id: z.string(),
      actor_role: z.string(),
      reason: z.string(),
      before: z.record(z.string(), z.unknown()),
      after: z.record(z.string(), z.unknown()),
      created_at: z.string(),
    }),
  ),
});

const systemSchema = z.object({
  environment: z.string(),
  process_started_at: z.string(),
  generated_at: z.string(),
  git_commit_sha: z.string(),
  migration_revision: z.string().nullable(),
  deployment_id: z.string().nullable().optional(),
  database_mode: z.string(),
  configuration: z.record(z.string(), z.boolean()),
  deployment_notes: z.array(z.string()),
});

const deploymentSchema = z.object({
  id: z.string(),
  release_key: z.string(),
  environment: z.string(),
  app_version: z.string(),
  git_commit_sha: z.string(),
  image_digest: z.string(),
  migration_revision: z.string().nullable(),
  data_revision: z.string(),
  prompt_version: z.string(),
  model_versions: z.record(z.string(), z.unknown()),
  active_flags: z.record(z.string(), z.unknown()),
  configuration: z.record(z.string(), z.unknown()),
  deployed_at: z.string(),
});

const deploymentComparisonSchema = z.object({
  generated_at: z.string(),
  current: deploymentSchema.nullable(),
  previous: deploymentSchema.nullable(),
  history: z.array(deploymentSchema),
  changes: z.array(
    z.object({
      field: z.string(),
      previous: z.unknown(),
      current: z.unknown(),
    }),
  ),
  note: z.string(),
});

const providerFailureSimulationSchema = z.object({
  scenario: z.string(),
  provider: z.string(),
  policy_provider: z.string().nullable(),
  flag_key: z.string(),
  flag_enabled: z.boolean(),
  policy_enabled: z.boolean(),
  circuit_state: z.string(),
  configured: z.boolean(),
  current_posture: z.string(),
  expected_path: z.array(z.string()),
  user_facing_fallback: z.string(),
  operator_action: z.string(),
});

const providerFailureSimulationListSchema = z.object({
  generated_at: z.string(),
  language_code: z.string(),
  state_code: z.string(),
  simulations: z.array(providerFailureSimulationSchema),
  note: z.string(),
});

export type AdminMe = z.infer<typeof adminMeSchema>;
export type AdminOverview = z.infer<typeof overviewSchema>;
export type ConversationList = z.infer<typeof conversationListSchema>;
export type TelemetryEvent = z.infer<typeof telemetryEventSchema>;
export type ReviewQueue = z.infer<typeof reviewQueueSchema>;
export type BenefitIssueReport = z.infer<typeof benefitIssueReportSchema>;
export type ReviewItem = z.infer<typeof reviewSchema>;
export type AdminTicket = z.infer<typeof ticketSchema>;
export type AdminDirectoryEntry = z.infer<typeof directoryEntrySchema>;
export type AdminDirectory = z.infer<typeof directoryListSchema>;
export type ProviderList = z.infer<typeof providerListSchema>;
export type LanguageReadiness = z.infer<typeof languageReadinessSchema>;
export type AuditEvent = z.infer<typeof auditEventSchema>;
export type ImportRun = z.infer<typeof importRunSchema>;
export type AdminSystem = z.infer<typeof systemSchema>;
export type DeploymentComparison = z.infer<typeof deploymentComparisonSchema>;
export type ProviderFailureSimulationList = z.infer<typeof providerFailureSimulationListSchema>;
export type ProviderPolicy = ProviderList["policies"][number];
export type AdminNotifications = z.infer<typeof notificationOverviewSchema>;
export type AdminFreshness = z.infer<typeof freshnessSchema>;
export type FreshnessAlert = AdminFreshness["alerts"][number];
export type BenefitVersion = z.infer<typeof benefitVersionSchema>;
export type BenefitVersionList = z.infer<typeof benefitVersionListSchema>;
export type AdminEvaluation = z.infer<typeof evaluationRunSchema>;
export type FeatureFlag = z.infer<typeof featureFlagSchema>;
export type FeatureFlagList = z.infer<typeof featureFlagListSchema>;

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

export function getAdminBenefitReports(token: string, status = "open"): Promise<BenefitIssueReport[]> {
  return request(
    `/api/admin/benefit-reports?status=${encodeURIComponent(status)}&limit=100`,
    z.array(benefitIssueReportSchema),
    adminInit(token),
  );
}

export function updateAdminBenefitReport(
  token: string,
  reportId: string,
  payload: { status: "acknowledged" | "resolved" | "dismissed"; reason: string },
): Promise<BenefitIssueReport> {
  return request(
    `/api/admin/benefit-reports/${encodeURIComponent(reportId)}`,
    benefitIssueReportSchema,
    adminInit(token, { method: "POST", body: JSON.stringify(payload) }),
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

export type BenefitEditPayload = {
  expected_revision?: number;
  domain: string;
  name: string;
  state_code: string | null;
  category: string;
  description: string;
  eligibility_initial: Record<string, unknown>;
  eligibility_renewal: Record<string, unknown> | null;
  benefits_text: string;
  documents_required: string[];
  application_process: string;
  source_url: string;
  source_title: string;
  source_document_url: string;
  source_excerpt: string | null;
  valid_from: string | null;
  valid_until: string | null;
  localized_summary: Record<string, string>;
  job_metadata: Record<string, unknown> | null;
  reason: string;
};

export function updateAdminBenefit(
  token: string,
  benefitId: string,
  payload: BenefitEditPayload,
): Promise<ReviewItem> {
  return request(
    `/api/admin/benefits/${encodeURIComponent(benefitId)}`,
    reviewSchema,
    adminInit(token, {method: "PUT", body: JSON.stringify(payload)}),
  );
}

export function getAdminBenefitVersions(token: string, benefitId: string): Promise<BenefitVersionList> {
  return request(
    `/api/admin/benefits/${encodeURIComponent(benefitId)}/versions`,
    benefitVersionListSchema,
    adminInit(token),
  );
}

export function rollbackAdminBenefit(
  token: string,
  benefitId: string,
  payload: { version: number; reason: string },
): Promise<ReviewItem> {
  return request(
    `/api/admin/benefits/${encodeURIComponent(benefitId)}/rollback`,
    reviewSchema,
    adminInit(token, {method: "POST", body: JSON.stringify(payload)}),
  );
}

export function updateFreshnessAlert(
  token: string,
  alertId: string,
  payload: { status: "acknowledged" | "resolved"; reason: string },
): Promise<FreshnessAlert> {
  return request(
    `/api/admin/freshness/alerts/${encodeURIComponent(alertId)}`,
    freshnessSchema.shape.alerts.element,
    adminInit(token, {method: "POST", body: JSON.stringify(payload)}),
  );
}

export function getAdminEscalations(token: string): Promise<AdminTicket[]> {
  return request("/api/escalations?status=active&limit=100", z.array(ticketSchema), adminInit(token));
}

export function claimAdminEscalation(token: string, ticketId: string): Promise<AdminTicket> {
  return request(
    `/api/escalations/${encodeURIComponent(ticketId)}/claim`,
    ticketSchema,
    adminInit(token, {method: "POST"}),
  );
}

export function addAdminEscalationNote(token: string, ticketId: string, text: string): Promise<AdminTicket> {
  return request(
    `/api/escalations/${encodeURIComponent(ticketId)}/notes`,
    ticketSchema,
    adminInit(token, {method: "POST", body: JSON.stringify({text})}),
  );
}

export function routeAdminEscalation(
  token: string,
  ticketId: string,
  payload: { department: string; routing_location: string },
): Promise<AdminTicket> {
  return request(
    `/api/escalations/${encodeURIComponent(ticketId)}/route`,
    ticketSchema,
    adminInit(token, {method: "POST", body: JSON.stringify(payload)}),
  );
}

export function resolveAdminEscalation(
  token: string,
  ticketId: string,
  payload: { resolution_code: string; note: string },
): Promise<AdminTicket> {
  return request(
    `/api/escalations/${encodeURIComponent(ticketId)}/resolve`,
    ticketSchema,
    adminInit(token, {method: "POST", body: JSON.stringify(payload)}),
  );
}

export function getAdminDirectory(token: string): Promise<AdminDirectory> {
  return request("/api/admin/departments?status=all&limit=500", directoryListSchema, adminInit(token));
}

export function approveAdminDirectoryEntry(token: string, entryId: string, reason: string): Promise<AdminDirectoryEntry> {
  return request(
    `/api/admin/departments/${encodeURIComponent(entryId)}/approve`,
    directoryEntrySchema,
    adminInit(token, {method: "POST", body: JSON.stringify({reason})}),
  );
}

export function deactivateAdminDirectoryEntry(token: string, entryId: string, reason: string): Promise<AdminDirectoryEntry> {
  return request(
    `/api/admin/departments/${encodeURIComponent(entryId)}/deactivate`,
    directoryEntrySchema,
    adminInit(token, {method: "POST", body: JSON.stringify({reason})}),
  );
}

export function getAdminProviders(token: string): Promise<ProviderList> {
  return request("/api/admin/providers", providerListSchema, adminInit(token));
}

export function getAdminProviderFailureSimulations(
  token: string,
  languageCode = "en",
  stateCode = "KA",
): Promise<ProviderFailureSimulationList> {
  const query = new URLSearchParams({language_code: languageCode, state_code: stateCode});
  return request(
    `/api/admin/providers/simulations?${query.toString()}`,
    providerFailureSimulationListSchema,
    adminInit(token),
  );
}

export function getAdminNotifications(token: string, hours = 24): Promise<AdminNotifications> {
  return request(
    `/api/admin/notifications?hours=${hours}`,
    notificationOverviewSchema,
    adminInit(token),
  );
}

export function getAdminFreshness(token: string, staleDays = 90): Promise<AdminFreshness> {
  return request(
    `/api/admin/freshness?stale_days=${staleDays}`,
    freshnessSchema,
    adminInit(token),
  );
}

export function getAdminEvaluations(token: string): Promise<AdminEvaluation[]> {
  return request(
    "/api/admin/evaluations?limit=20",
    z.array(evaluationRunSchema),
    adminInit(token),
  );
}

export function getAdminFeatureFlags(token: string): Promise<FeatureFlagList> {
  return request("/api/admin/feature-flags", featureFlagListSchema, adminInit(token));
}

export type FeatureFlagUpdate = {
  enabled: boolean;
  rollout_percentage: number;
  target_languages: string[];
  target_states: string[];
  reason: string;
};

export function updateAdminFeatureFlag(
  token: string,
  key: string,
  payload: FeatureFlagUpdate,
): Promise<FeatureFlag> {
  return request(
    `/api/admin/feature-flags/${encodeURIComponent(key)}`,
    featureFlagSchema,
    adminInit(token, {method: "PUT", body: JSON.stringify(payload)}),
  );
}

export function rollbackAdminFeatureFlag(
  token: string,
  key: string,
  reason: string,
): Promise<FeatureFlag> {
  return request(
    `/api/admin/feature-flags/${encodeURIComponent(key)}/rollback`,
    featureFlagSchema,
    adminInit(token, {method: "POST", body: JSON.stringify({reason})}),
  );
}

export type ProviderPolicyUpdate = {
  enabled: boolean;
  primary_provider: string;
  fallback_provider: string | null;
  circuit_state: "closed" | "open" | "half_open";
  daily_budget_usd?: number | null;
  monthly_budget_usd?: number | null;
  override_expires_at: string | null;
  reason: string;
};

export function updateAdminProviderPolicy(
  token: string,
  provider: string,
  scope: string,
  payload: ProviderPolicyUpdate,
): Promise<ProviderPolicy> {
  return request(
    `/api/admin/provider-policies/${encodeURIComponent(provider)}/${encodeURIComponent(scope)}`,
    providerPolicySchema,
    adminInit(token, {method: "PUT", body: JSON.stringify(payload)}),
  );
}

export function rollbackAdminProviderPolicy(
  token: string,
  provider: string,
  scope: string,
  reason: string,
): Promise<ProviderPolicy> {
  return request(
    `/api/admin/provider-policies/${encodeURIComponent(provider)}/${encodeURIComponent(scope)}/rollback`,
    providerPolicySchema,
    adminInit(token, {method: "POST", body: JSON.stringify({reason})}),
  );
}

export function getAdminLanguages(token: string): Promise<LanguageReadiness[]> {
  return request("/api/admin/languages", z.array(languageReadinessSchema), adminInit(token));
}

export type LanguageReviewUpdate = {
  native_speaker_status: "pending" | "approved" | "rejected";
  interface_status: "pending" | "approved" | "rejected";
  prompt_status: "pending" | "approved" | "rejected";
  content_status: "pending" | "approved" | "rejected";
  understanding_status: "pending" | "approved" | "rejected";
  voice_status: "pending" | "approved" | "rejected";
  accessibility_status: "pending" | "approved" | "rejected";
  evidence_url: string;
  review_notes: string;
  attestation: boolean;
  activate: boolean;
};

export function updateAdminLanguageReview(
  token: string,
  code: string,
  payload: LanguageReviewUpdate,
): Promise<LanguageReadiness> {
  return request(
    `/api/admin/languages/${encodeURIComponent(code)}/review`,
    languageReadinessSchema,
    adminInit(token, {method: "PUT", body: JSON.stringify(payload)}),
  );
}

export function getAdminAuditEvents(token: string): Promise<AuditEvent[]> {
  return request("/api/admin/audit-events?limit=100", z.array(auditEventSchema), adminInit(token));
}

export async function downloadAdminAuditEvents(
  token: string,
  format: "csv" | "json" = "csv",
): Promise<Blob> {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  const url = new URL(
    `/api/admin/audit-events/export?format=${format}`,
    base || window.location.origin,
  );
  const response = await fetch(url, adminInit(token));
  if (!response.ok) throw new Error(`Audit export failed (${response.status})`);
  return response.blob();
}

export function getAdminImports(token: string): Promise<ImportRun[]> {
  return request("/api/admin/imports?limit=50", z.array(importRunSchema), adminInit(token));
}

export function getAdminSystem(token: string): Promise<AdminSystem> {
  return request("/api/admin/system", systemSchema, adminInit(token));
}

export function getAdminDeploymentComparison(token: string): Promise<DeploymentComparison> {
  return request(
    "/api/admin/system/deployments/compare?limit=20",
    deploymentComparisonSchema,
    adminInit(token),
  );
}
