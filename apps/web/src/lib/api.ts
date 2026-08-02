import type { components } from "@sahaayak/api-types";
import { z } from "zod";

export type TurnRequest = components["schemas"]["TurnRequest"];

const API_ROOT = import.meta.env.VITE_API_BASE_URL ?? "";

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

const matchSchema = z.object({
  benefit_id: z.string(),
  benefit_name: z.string(),
  domain: z.enum(["scheme", "scholarship", "job"]),
  verdict: z.string(),
  confidence: z.number(),
  reasons: z.array(z.string()).default([]),
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
export type TurnResponse = z.infer<typeof turnResponseSchema>;
export type MatchSummary = z.infer<typeof matchSchema>;
export type BenefitDetail = z.infer<typeof benefitDetailSchema>;
export type RetrievedSource = z.infer<typeof retrievedSourceSchema>;

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
