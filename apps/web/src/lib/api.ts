import type { components } from "@sahaayak/api-types";
import { z } from "zod";

export type TurnRequest = components["schemas"]["TurnRequest"];

const API_ROOT = import.meta.env.VITE_API_BASE_URL ?? "";

export function voiceStreamUrl(): string {
  const base = API_ROOT || (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
  const url = new URL("/api/voice/stream", base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

const slotValueSchema = z.union([z.number(), z.string(), z.boolean()]);

export const languageSchema = z.object({
  code: z.string(),
  name: z.string(),
  native_name: z.string(),
  is_active: z.boolean(),
});

export const stateSchema = z.object({
  code: z.string(),
  name: z.string(),
  primary_language_code: z.string(),
  is_active: z.boolean(),
});

export const coverageSchema = z.object({
  by_domain: z.record(z.string(), z.number()),
  by_state: z.record(z.string(), z.number()),
  total: z.number(),
  verified_total: z.number(),
  illustrative_total: z.number(),
  last_data_update: z.string().nullable().optional(),
});

export const healthSchema = z.object({
  status: z.string(),
  environment: z.string(),
  database: z.string(),
  cache: z.string(),
  speech_to_text: z.boolean(),
  text_to_speech: z.boolean(),
  reasoning_model: z.boolean(),
  tracing: z.boolean(),
  languages: z.array(z.string()),
});

export const browserSessionSchema = z.object({
  session_id: z.string(),
  access_token: z.string(),
  language_code: z.string(),
  state_code: z.string(),
  expires_at: z.string(),
});

export const citizenMeSchema = z.object({
  id: z.string(),
  identity_provider: z.string(),
  preferred_language_code: z.string(),
  timezone: z.string(),
  status: z.string(),
  household_ids: z.array(z.string()),
  created_at: z.string(),
  last_login_at: z.string(),
});

export const householdSchema = z.object({
  id: z.string(),
  label: z.string(),
  state_code: z.string().nullable(),
  district: z.string(),
  pincode: z.string(),
  status: z.string(),
  revision: z.number(),
  matching_policy_version: z.string(),
  member_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const householdMemberSchema = z.object({
  id: z.string(),
  alias: z.string(),
  safe_ordinal: z.string(),
  relationship_category: z.string(),
  is_account_owner_subject: z.boolean(),
  age_class: z.string(),
  authority_status: z.string(),
  status: z.string(),
  revision: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const profileFactSchema = z.object({
  fact_key: z.string(),
  version: z.number(),
  scope: z.string(),
  data_type: z.string(),
  allowed_values: z.array(z.string()),
  allowed_purposes: z.array(z.string()),
  sensitivity: z.string(),
  inheritance_allowed: z.boolean(),
  reconfirmation_days: z.number().nullable(),
  question: z.record(z.string(), z.string()),
  help_text: z.record(z.string(), z.string()),
  matcher_slot: z.string().nullable(),
  state: z.enum(["missing", "current", "stale"]),
  masked_value: z.string(),
  value_source: z.string(),
  purposes: z.array(z.string()),
  confirmed_at: z.string().nullable(),
  reconfirm_after: z.string().nullable(),
  expires_at: z.string().nullable(),
  revision: z.number().nullable(),
});

export const radarCriterionEvidenceSchema = z.object({
  slot: z.string(),
  status: z.string(),
  requirement: z.string(),
  fact_key: z.string(),
  fact_state: z.string(),
  evidence_source: z.string(),
});

export const radarRecommendationSchema = z.object({
  id: z.string(),
  household_member_id: z.string(),
  member_ordinal: z.string(),
  benefit_id: z.string(),
  benefit_name: z.string(),
  domain: z.string(),
  verdict: z.string(),
  confidence: z.number(),
  state: z.string(),
  reason_codes: z.array(z.string()),
  criterion_evidence: z.array(radarCriterionEvidenceSchema),
  fact_use_evidence: z.array(z.record(z.string(), z.unknown())),
  source_title: z.string(),
  source_url: z.string(),
  source_last_verified_date: z.string().nullable(),
  valid_until: z.string().nullable(),
  benefit_revision: z.number(),
  matcher_rules_version: z.string(),
  computed_profile_version: z.string(),
  viewed_at: z.string().nullable(),
  snoozed_until: z.string().nullable(),
  dismissed_at: z.string().nullable(),
  updated_at: z.string(),
});

export const radarListSchema = z.object({
  household_id: z.string(),
  generated_at: z.string(),
  recommendations: z.array(radarRecommendationSchema),
  counts_by_state: z.record(z.string(), z.number()),
});

export const radarRefreshSchema = z.object({
  household_id: z.string(),
  generated_at: z.string(),
  profile_version: z.string(),
  recommendation_count: z.number(),
  counts_by_verdict: z.record(z.string(), z.number()),
  recommendations: z.array(radarRecommendationSchema),
});

const retrievedSourceSchema = z.object({
  source_id: z.string(),
  filename: z.string(),
  score: z.number(),
  excerpt: z.string(),
  source_url: z.string().default(""),
  attributes: z
    .record(z.string(), z.union([z.string(), z.number(), z.boolean()]))
    .default({}),
});

const criterionEvidenceSchema = z.object({
  slot: z.string(),
  status: z.enum(["pass", "fail", "unknown"]),
  requirement: z.string(),
  caller_value: z.string().nullable().optional(),
});

const matchSchema = z.object({
  benefit_id: z.string(),
  benefit_name: z.string(),
  domain: z.enum(["scheme", "scholarship", "job"]),
  verdict: z.string(),
  confidence: z.number(),
  reasons: z.array(z.string()).default([]),
  criteria: z.array(criterionEvidenceSchema).default([]),
  caveats: z.array(z.string()).default([]),
  verification_status: z.enum([
    "illustrative",
    "machine_structured",
    "machine_reviewed",
    "needs_review",
    "human_verified",
    "stale",
  ]),
  source_title: z.string().default(""),
  source_document_url: z.string().default(""),
  verified_at: z.string().nullable().optional(),
  last_verified_date: z.string().nullable().optional(),
  job_metadata: z.record(z.string(), z.unknown()).default(() => ({})),
});

export const benefitDetailSchema = z.object({
  id: z.string(),
  domain: z.enum(["scheme", "scholarship", "job"]),
  name: z.string(),
  state_code: z.string().nullable(),
  category: z.string(),
  description: z.string(),
  benefits_text: z.string(),
  documents_required: z.array(z.string()),
  application_process: z.string(),
  eligibility_initial: z.record(z.string(), z.unknown()),
  verification_status: z.enum([
    "illustrative",
    "machine_structured",
    "machine_reviewed",
    "needs_review",
    "human_verified",
    "stale",
  ]),
  source_title: z.string(),
  source_document_url: z.string(),
  source_excerpt: z.string().nullable(),
  verified_at: z.string().nullable(),
  last_verified_date: z.string().nullable(),
  valid_from: z.string().nullable(),
  valid_until: z.string().nullable(),
  job_metadata: z.record(z.string(), z.unknown()).default(() => ({})),
});

export const benefitIssueReportSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  category: z.string(),
  status: z.string(),
  created_at: z.string(),
});

export const savedBenefitSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  name: z.string(),
  domain: z.string(),
  state_code: z.string().nullable(),
  description: z.string(),
  source_title: z.string(),
  source_document_url: z.string(),
  verification_status: z.string(),
  saved_at: z.string(),
  job_metadata: z.record(z.string(), z.unknown()).default(() => ({})),
});

export const reminderSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  application_case_id: z.string().nullable().optional(),
  benefit_name: z.string(),
  due_at: z.string(),
  note: z.string(),
  timezone: z.string(),
  channel: z.string(),
  status: z.string(),
  created_at: z.string(),
  delivered_at: z.string().nullable(),
  // Masked only; the API never returns a destination.
  contact_display_suffix: z.string().default(""),
  delivery_status: z.string().default(""),
});

export const applicationTaskSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  benefit_name: z.string(),
  kind: z.string(),
  title: z.string(),
  description: z.string(),
  requirement_key: z.string().nullable(),
  position: z.number(),
  status: z.string(),
  due_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  source_revision: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const applicationStatusEventSchema = z.object({
  id: z.string(),
  status: z.string(),
  provenance: z.string(),
  actor_type: z.string(),
  occurred_at: z.string(),
  recorded_at: z.string(),
  source_url: z.string(),
  reason_code: z.string(),
  external_reference_masked: z.string(),
});

export const applicationCaseSchema = z.object({
  id: z.string(),
  benefit_id: z.string(),
  benefit_name: z.string(),
  benefit_domain: z.string(),
  benefit_state_code: z.string().nullable(),
  benefit_revision: z.number(),
  benefit_verification_status: z.string(),
  current_benefit_revision: z.number().nullable(),
  benefit_change_state: z.string(),
  benefit_change_items: z.array(z.string()),
  source_stale: z.boolean(),
  source_title: z.string(),
  source_document_url: z.string(),
  last_verified_date: z.string().nullable(),
  application_channel: z.string(),
  status: z.string(),
  status_provenance: z.string(),
  status_recorded_at: z.string(),
  status_source_url: z.string(),
  readiness_state: z.string(),
  readiness_blockers: z.array(z.string()),
  external_reference_masked: z.string(),
  submission_date: z.string().nullable(),
  revision: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
  closed_at: z.string().nullable(),
  tasks: z.array(applicationTaskSchema),
  status_events: z.array(applicationStatusEventSchema),
});

export const applicationPackPreviewSchema = z.object({
  html: z.string(),
  generated_at: z.string(),
  expires_at: z.string(),
  content_sha256: z.string(),
});

export const applicationFieldValueSchema = z.object({
  field_key: z.string(),
  definition_revision: z.number(),
  masked_value: z.string(),
  value_source: z.string(),
  confirmed_by_citizen_at: z.string(),
  expires_at: z.string().nullable(),
  revision: z.number(),
});

export const applicationFieldDefinitionSchema = z.object({
  field_key: z.string(),
  revision: z.number(),
  label: z.record(z.string(), z.string()),
  help_text: z.record(z.string(), z.string()),
  data_type: z.string(),
  validation: z.record(z.string(), z.unknown()),
  required: z.boolean(),
  sensitivity: z.string(),
  source_excerpt: z.string(),
  source_url: z.string(),
  profile_slot: z.string().nullable(),
  handoff_destinations: z.array(z.string()),
  value: applicationFieldValueSchema.nullable(),
});

export const applicationRequirementSchema = z.object({
  id: z.string(),
  requirement_key: z.string(),
  requirement_type: z.string(),
  title: z.string(),
  description: z.string(),
  required: z.boolean(),
  source_revision: z.number(),
  source_excerpt: z.string(),
  source_url: z.string(),
  status: z.string(),
  task_id: z.string().nullable(),
  expiry_date: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const applicationOutcomeSchema = z.object({
  id: z.string(),
  application_case_id: z.string(),
  outcome: z.string(),
  confirmed_at: z.string(),
  reason_code: z.string(),
  has_comment: z.boolean(),
  satisfaction_score: z.number().nullable(),
  consent_for_evaluation: z.boolean(),
  revision: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const contactPointSchema = z.object({
  id: z.string(),
  channel: z.string(),
  display_suffix: z.string(),
  locale: z.string(),
  verification_status: z.string(),
  consent_status: z.string(),
  consent_purpose: z.string(),
  verified_at: z.string().nullable(),
  created_at: z.string(),
});

export const channelStatusSchema = z.object({
  channel: z.string(),
  available: z.boolean(),
  gate: z.string(),
  // Always populated when unavailable, so a disabled control can explain itself.
  reason: z.string(),
  contact_point_id: z.string().nullable(),
  display_suffix: z.string().default(""),
});

export const turnResponseSchema = z.object({
  session_id: z.string(),
  transcript: z.string(),
  response_text: z.string(),
  grounded_answer: z.string().nullable().optional(),
  sources: z.array(retrievedSourceSchema).default([]),
  intent: z.enum([
    "find_scheme",
    "find_scholarship",
    "find_job",
    "ask_about_benefit",
    "ask_how_to_apply",
    "provide_info",
    "request_human",
    "greeting",
    "unknown",
  ]),
  slots: z.record(z.string(), slotValueSchema).default({}),
  pending_slot: z.string().nullable().optional(),
  matches: z.array(matchSchema).default([]),
  needs_escalation: z.boolean(),
  escalation_reason: z.string().nullable().optional(),
  audio_base64: z.string().nullable().optional(),
  audio_mime_type: z.string().nullable().optional(),
});

export type Language = z.infer<typeof languageSchema>;
export type State = z.infer<typeof stateSchema>;
export type Coverage = z.infer<typeof coverageSchema>;
export type Health = z.infer<typeof healthSchema>;
export type BrowserSession = z.infer<typeof browserSessionSchema>;
export type CitizenMe = z.infer<typeof citizenMeSchema>;
export type Household = z.infer<typeof householdSchema>;
export type HouseholdMember = z.infer<typeof householdMemberSchema>;
export type ProfileFact = z.infer<typeof profileFactSchema>;
export type RadarRecommendation = z.infer<typeof radarRecommendationSchema>;
export type RadarList = z.infer<typeof radarListSchema>;
export type RadarRefresh = z.infer<typeof radarRefreshSchema>;
export type TurnResponse = z.infer<typeof turnResponseSchema>;
export type MatchSummary = z.infer<typeof matchSchema>;
export type BenefitDetail = z.infer<typeof benefitDetailSchema>;
export type BenefitIssueReport = z.infer<typeof benefitIssueReportSchema>;
export type RetrievedSource = z.infer<typeof retrievedSourceSchema>;
export type SavedBenefit = z.infer<typeof savedBenefitSchema>;
export type Reminder = z.infer<typeof reminderSchema>;
export type ApplicationTask = z.infer<typeof applicationTaskSchema>;
export type ApplicationStatusEvent = z.infer<typeof applicationStatusEventSchema>;
export type ApplicationCase = z.infer<typeof applicationCaseSchema>;
export type ApplicationPackPreview = z.infer<typeof applicationPackPreviewSchema>;
export type ApplicationFieldDefinition = z.infer<typeof applicationFieldDefinitionSchema>;
export type ApplicationRequirement = z.infer<typeof applicationRequirementSchema>;
export type ApplicationOutcome = z.infer<typeof applicationOutcomeSchema>;
export type ContactPoint = z.infer<typeof contactPointSchema>;
export type ChannelStatus = z.infer<typeof channelStatusSchema>;

export type Catalog = {
  languages: Language[];
  states: State[];
  coverage: Coverage;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function detailFromBody(body: unknown): string | null {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return null;
  }

  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String(item.msg);
        }
        return String(item);
      })
      .join(", ");
  }
  return detail == null ? null : String(detail);
}

export async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      credentials: "include",
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("Could not reach the Sahaayak API.", 0);
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // The HTTP status remains useful when a proxy returns a non-JSON error.
    }
    throw new ApiError(
      detailFromBody(body) ?? `Request failed with status ${response.status}`,
      response.status,
    );
  }

  if (response.status === 204) return undefined as T;

  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new ApiError("The API returned an invalid response.", response.status);
  }
  return parsed.data;
}

export function getHealth(): Promise<Health> {
  return request("/health", healthSchema);
}

export function createBrowserSession(payload: {
  language_code?: string;
  state_code?: string;
}): Promise<BrowserSession> {
  return request("/api/browser-sessions", browserSessionSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exchangeCitizenCode(payload: {
  code: string;
  code_verifier: string;
  redirect_uri: string;
}): Promise<{ authenticated: boolean; expires_at: string }> {
  return request("/api/citizen/auth/exchange", z.object({ authenticated: z.boolean(), expires_at: z.string() }), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logoutCitizen(): Promise<void> {
  return request("/api/citizen/auth/logout", z.undefined(), { method: "POST" });
}

export function getCitizenMe(): Promise<CitizenMe> {
  return request("/api/citizen/me", citizenMeSchema);
}

export function getHouseholds(): Promise<Household[]> {
  return request("/api/households", z.array(householdSchema));
}

export function createHousehold(payload: {
  label: string;
  state_code?: string;
  district?: string;
  pincode?: string;
  include_self: boolean;
  consent_persistence: boolean;
  consent_personalization: boolean;
}): Promise<Household> {
  return request("/api/households", householdSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getHouseholdMembers(householdId: string): Promise<HouseholdMember[]> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/members`,
    z.array(householdMemberSchema),
  );
}

export function addHouseholdMember(
  householdId: string,
  payload: {
    alias: string;
    relationship_category: string;
    age_class: string;
    authority_confirmed: boolean;
    consent_member_management: boolean;
  },
): Promise<HouseholdMember> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/members`,
    householdMemberSchema,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function getHouseholdFacts(householdId: string): Promise<ProfileFact[]> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/facts`,
    z.array(profileFactSchema),
  );
}

export function getMemberFacts(householdId: string, memberId: string): Promise<ProfileFact[]> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/members/${encodeURIComponent(memberId)}/facts`,
    z.array(profileFactSchema),
  );
}

export function writeMemberFact(
  householdId: string,
  memberId: string,
  factKey: string,
  payload: { value: string; purposes: string[]; confirm_purpose: boolean; expected_revision?: number },
): Promise<ProfileFact> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/members/${encodeURIComponent(memberId)}/facts/${encodeURIComponent(factKey)}`,
    profileFactSchema,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function refreshHouseholdRadar(
  householdId: string,
  payload: { member_id?: string; domains?: string[]; limit_per_member?: number } = {},
): Promise<RadarRefresh> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/radar/refresh`,
    radarRefreshSchema,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function getHouseholdRadar(
  householdId: string,
  memberId?: string,
): Promise<RadarList> {
  const query = memberId ? `?member_id=${encodeURIComponent(memberId)}` : "";
  return request(
    `/api/households/${encodeURIComponent(householdId)}/radar${query}`,
    radarListSchema,
  );
}

export function updateHouseholdRadar(
  householdId: string,
  recommendationId: string,
  payload: { action: "view" | "snooze" | "dismiss"; snooze_until?: string; reason_code?: string },
): Promise<RadarRecommendation> {
  return request(
    `/api/households/${encodeURIComponent(householdId)}/radar/${encodeURIComponent(recommendationId)}`,
    radarRecommendationSchema,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function getCatalog(): Promise<Catalog> {
  const [languages, states, coverage] = await Promise.all([
    request("/api/languages", z.array(languageSchema)),
    request("/api/states", z.array(stateSchema)),
    request("/api/coverage", coverageSchema),
  ]);
  return { languages, states, coverage };
}

export function sendTextTurn(payload: TurnRequest, accessToken: string): Promise<TurnResponse> {
  return request("/api/turns", turnResponseSchema, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function getBenefit(benefitId: string): Promise<BenefitDetail> {
  return request(`/api/benefits/${encodeURIComponent(benefitId)}`, benefitDetailSchema);
}

export function reportBenefitIssue(
  benefitId: string,
  payload: { category: string; description: string },
  accessToken: string,
): Promise<BenefitIssueReport> {
  return request(
    `/api/benefits/${encodeURIComponent(benefitId)}/reports`,
    benefitIssueReportSchema,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function getSavedBenefits(sessionId: string, accessToken: string): Promise<SavedBenefit[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/saved-benefits`,
    z.array(savedBenefitSchema),
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function saveBenefit(
  sessionId: string,
  benefitId: string,
  accessToken: string,
): Promise<SavedBenefit> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/saved-benefits`,
    savedBenefitSchema,
    {
      method: "POST",
      body: JSON.stringify({ benefit_id: benefitId }),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function removeSavedBenefit(
  sessionId: string,
  benefitId: string,
  accessToken: string,
): Promise<void> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/saved-benefits/${encodeURIComponent(benefitId)}`,
    z.undefined(),
    { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function getReminders(sessionId: string, accessToken: string): Promise<Reminder[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/reminders`,
    z.array(reminderSchema),
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function createReminder(
  sessionId: string,
  payload: { benefit_id: string; due_at: string; note?: string; channel?: string },
  accessToken: string,
): Promise<Reminder> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/reminders`,
    reminderSchema,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function cancelReminder(
  sessionId: string,
  reminderId: string,
  accessToken: string,
): Promise<void> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/reminders/${encodeURIComponent(reminderId)}`,
    z.undefined(),
    { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function getApplicationTasks(
  sessionId: string,
  accessToken: string,
): Promise<ApplicationTask[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/tasks`,
    z.array(applicationTaskSchema),
    {headers: {Authorization: `Bearer ${accessToken}`}},
  );
}

export function updateApplicationTask(
  sessionId: string,
  taskId: string,
  status: "pending" | "completed" | "skipped",
  accessToken: string,
): Promise<ApplicationTask> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/tasks/${encodeURIComponent(taskId)}`,
    applicationTaskSchema,
    {
      method: "POST",
      body: JSON.stringify({status}),
      headers: {Authorization: `Bearer ${accessToken}`},
    },
  );
}

export function getApplications(sessionId: string, accessToken: string): Promise<ApplicationCase[]> {
  return request(
    "/api/sessions/" + encodeURIComponent(sessionId) + "/applications",
    z.array(applicationCaseSchema),
    { headers: { Authorization: "Bearer " + accessToken } },
  );
}

export function getApplication(
  sessionId: string,
  applicationId: string,
  accessToken: string,
): Promise<ApplicationCase> {
  return request(
    "/api/sessions/" + encodeURIComponent(sessionId) + "/applications/" + encodeURIComponent(applicationId),
    applicationCaseSchema,
    { headers: { Authorization: "Bearer " + accessToken } },
  );
}

export function createApplication(
  sessionId: string,
  payload: { benefit_id: string; application_channel?: string },
  accessToken: string,
): Promise<ApplicationCase> {
  return request(
    "/api/sessions/" + encodeURIComponent(sessionId) + "/applications",
    applicationCaseSchema,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: "Bearer " + accessToken },
    },
  );
}

export function recordApplicationStatus(
  sessionId: string,
  applicationId: string,
  payload: {
    status: string;
    occurred_at?: string;
    submission_date?: string;
    external_reference?: string;
    reason_code?: string;
  },
  accessToken: string,
): Promise<ApplicationCase> {
  return request(
    "/api/sessions/" +
      encodeURIComponent(sessionId) +
      "/applications/" +
      encodeURIComponent(applicationId) +
      "/status-events",
    applicationCaseSchema,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: "Bearer " + accessToken },
    },
  );
}

export function getApplicationFields(
  sessionId: string,
  applicationId: string,
  accessToken: string,
): Promise<ApplicationFieldDefinition[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/applications/${encodeURIComponent(applicationId)}/fields`,
    z.array(applicationFieldDefinitionSchema),
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function updateApplicationField(
  sessionId: string,
  applicationId: string,
  fieldKey: string,
  payload: { value: string; expected_revision?: number },
  accessToken: string,
): Promise<ApplicationFieldDefinition[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/applications/${encodeURIComponent(applicationId)}/fields/${encodeURIComponent(fieldKey)}`,
    z.array(applicationFieldDefinitionSchema),
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function getApplicationRequirements(
  sessionId: string,
  applicationId: string,
  accessToken: string,
): Promise<ApplicationRequirement[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/applications/${encodeURIComponent(applicationId)}/requirements`,
    z.array(applicationRequirementSchema),
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function updateApplicationRequirement(
  sessionId: string,
  applicationId: string,
  requirementKey: string,
  payload: {
    status: "missing" | "ready" | "not_applicable" | "submitted" | "needs_update";
    reason?: string;
    expected_case_revision?: number;
  },
  accessToken: string,
): Promise<ApplicationRequirement[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/applications/${encodeURIComponent(applicationId)}/requirements/${encodeURIComponent(requirementKey)}/status`,
    z.array(applicationRequirementSchema),
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function getApplicationOutcome(
  sessionId: string,
  applicationId: string,
  accessToken: string,
): Promise<ApplicationOutcome> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/applications/${encodeURIComponent(applicationId)}/outcome`,
    applicationOutcomeSchema,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function recordApplicationOutcome(
  sessionId: string,
  applicationId: string,
  payload: {
    outcome: "received" | "not_received" | "partially_received" | "unknown";
    reason_code?: string;
    free_text?: string;
    satisfaction_score?: number;
    consent_for_evaluation?: boolean;
    expected_case_revision?: number;
  },
  accessToken: string,
): Promise<ApplicationOutcome> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/applications/${encodeURIComponent(applicationId)}/outcome`,
    applicationOutcomeSchema,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function previewApplicationPack(
  sessionId: string,
  applicationId: string,
  accessToken: string,
): Promise<ApplicationPackPreview> {
  return request(
    "/api/sessions/" +
      encodeURIComponent(sessionId) +
      "/applications/" +
      encodeURIComponent(applicationId) +
      "/packs/preview",
    applicationPackPreviewSchema,
    {
      method: "POST",
      headers: { Authorization: "Bearer " + accessToken },
    },
  );
}

export function getContactPoints(
  sessionId: string,
  accessToken: string,
): Promise<ContactPoint[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/contact-points`,
    z.array(contactPointSchema),
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function addContactPoint(
  sessionId: string,
  payload: { channel: string; destination: string; locale: string; consent: boolean },
  accessToken: string,
): Promise<ContactPoint> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/contact-points`,
    contactPointSchema,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function verifyContactPoint(
  sessionId: string,
  contactId: string,
  code: string,
  accessToken: string,
): Promise<ContactPoint> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/contact-points/${encodeURIComponent(contactId)}/verify`,
    contactPointSchema,
    {
      method: "POST",
      body: JSON.stringify({ code }),
      headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
}

export function revokeContactPoint(
  sessionId: string,
  contactId: string,
  accessToken: string,
): Promise<void> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/contact-points/${encodeURIComponent(contactId)}`,
    z.undefined(),
    { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

export function getNotificationChannels(
  sessionId: string,
  accessToken: string,
): Promise<ChannelStatus[]> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/notification-channels`,
    z.array(channelStatusSchema),
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
}

function extensionForMimeType(mimeType: string): string {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

export function sendVoiceTurn(
  audio: Blob,
  fields: {
    language_code: string;
    state_code: string;
    speak: boolean;
  },
  accessToken: string,
): Promise<TurnResponse> {
  const form = new FormData();
  form.append("audio", audio, `sahaayak-turn.${extensionForMimeType(audio.type)}`);
  form.append("language_code", fields.language_code);
  form.append("state_code", fields.state_code);
  form.append("speak", String(fields.speak));
  return request("/api/voice/turns", turnResponseSchema, {
    method: "POST",
    body: form,
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function resetSession(sessionId: string, accessToken: string): Promise<void> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}`, z.undefined(), {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return "Could not reach the API. Start it with `make api`, then reload this page.";
    }
    if (error.status === 503) {
      return "Voice is not configured on the API yet. Text chat is still available.";
    }
    if (error.status === 401) {
      return "Your guest session has expired. Starting a fresh session is required.";
    }
    if (error.status === 429) {
      return "You are sending requests too quickly. Please wait a moment and try again.";
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}
