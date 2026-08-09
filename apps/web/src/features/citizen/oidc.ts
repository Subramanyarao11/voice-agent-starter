import { exchangeCitizenCode, logoutCitizen } from "@/lib/api";

const STORAGE_STATE = "sahaayak-citizen-oidc-state";
const STORAGE_VERIFIER = "sahaayak-citizen-oidc-verifier";

export function citizenOidcConfig() {
  const issuer = (import.meta.env.VITE_CITIZEN_OIDC_ISSUER ?? "").trim().replace(/\/$/, "");
  const clientId = (import.meta.env.VITE_CITIZEN_OIDC_CLIENT_ID ?? "").trim();
  const redirectUri =
    (import.meta.env.VITE_CITIZEN_OIDC_REDIRECT_URI ?? "").trim() ||
    `${window.location.origin}/account/callback`;
  return {
    issuer,
    clientId,
    redirectUri,
    scope: (import.meta.env.VITE_CITIZEN_OIDC_SCOPE ?? "openid profile email").trim(),
    bffEnabled: (import.meta.env.VITE_CITIZEN_OIDC_BFF_ENABLED ?? "false") === "true",
  };
}

export function isCitizenOidcConfigured(): boolean {
  const config = citizenOidcConfig();
  return Boolean(config.issuer && config.clientId && config.bffEnabled);
}

export async function beginCitizenOidcLogin(): Promise<void> {
  const config = citizenOidcConfig();
  if (!config.issuer || !config.clientId || !config.bffEnabled) {
    throw new Error("Citizen sign-in is not configured for this web deployment.");
  }
  const discoveryResponse = await fetch(`${config.issuer}/.well-known/openid-configuration`);
  if (!discoveryResponse.ok) throw new Error("Could not reach the citizen identity provider.");
  const discovery = (await discoveryResponse.json()) as { authorization_endpoint?: string };
  const authorizationEndpoint =
    discovery.authorization_endpoint ?? `${config.issuer}/protocol/openid-connect/auth`;
  const state = randomString(32);
  const verifier = randomString(64);
  const challenge = await sha256Base64Url(verifier);
  sessionStorage.setItem(STORAGE_STATE, state);
  sessionStorage.setItem(STORAGE_VERIFIER, verifier);

  const authorization = new URL(authorizationEndpoint);
  authorization.search = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    response_type: "code",
    scope: config.scope,
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  }).toString();
  window.location.assign(authorization.toString());
}

export async function completeCitizenOidcLogin(): Promise<void> {
  const config = citizenOidcConfig();
  const params = new URLSearchParams(window.location.search);
  const providerError = params.get("error_description") || params.get("error");
  if (providerError) throw new Error(providerError);
  const code = params.get("code");
  const state = params.get("state");
  const expectedState = sessionStorage.getItem(STORAGE_STATE);
  const verifier = sessionStorage.getItem(STORAGE_VERIFIER);
  sessionStorage.removeItem(STORAGE_STATE);
  sessionStorage.removeItem(STORAGE_VERIFIER);
  if (!code || !state || !expectedState || state !== expectedState || !verifier) {
    throw new Error("The citizen sign-in response could not be verified.");
  }
  await exchangeCitizenCode({ code, code_verifier: verifier, redirect_uri: config.redirectUri });
  window.history.replaceState({}, document.title, "/household");
}

export async function signOutCitizen(): Promise<void> {
  await logoutCitizen();
}

function randomString(length: number): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256Base64Url(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  const bytes = String.fromCharCode(...new Uint8Array(digest));
  return btoa(bytes).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}
