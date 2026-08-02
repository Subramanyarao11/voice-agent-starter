import type { components } from "@sahaayak/api-types";

export type Language = components["schemas"]["LanguageOut"];
export type State = components["schemas"]["StateOut"];
export type Coverage = components["schemas"]["CoverageOut"];
export type Health = components["schemas"]["HealthReport"];
export type TurnRequest = components["schemas"]["TurnRequest"];
export type TurnResponse = components["schemas"]["TurnResponse"];

const API_ROOT = import.meta.env.VITE_API_BASE_URL ?? "";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // The status still gives the caller a useful error when the API did not
      // return JSON (for example, a reverse proxy error page).
    }
    throw new ApiError(
      detailFromBody(body) ?? `Request failed with status ${response.status}`,
      response.status,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export function getLanguages(): Promise<Language[]> {
  return request<Language[]>("/api/languages");
}

export function getStates(): Promise<State[]> {
  return request<State[]>("/api/states");
}

export function getCoverage(): Promise<Coverage> {
  return request<Coverage>("/api/coverage");
}

export function sendTextTurn(payload: TurnRequest): Promise<TurnResponse> {
  return request<TurnResponse>("/api/turns", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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
    caller_id: string;
    language_code: string;
    state_code: string;
    speak: boolean;
  },
): Promise<TurnResponse> {
  const form = new FormData();
  form.append("audio", audio, `sahaayak-turn.${extensionForMimeType(audio.type)}`);
  form.append("caller_id", fields.caller_id);
  form.append("language_code", fields.language_code);
  form.append("state_code", fields.state_code);
  form.append("speak", String(fields.speak));
  return request<TurnResponse>("/api/voice/turns", {
    method: "POST",
    body: form,
  });
}

export function resetSession(callerId: string): Promise<void> {
  return request<void>(`/api/sessions/${encodeURIComponent(callerId)}`, {
    method: "DELETE",
  });
}
