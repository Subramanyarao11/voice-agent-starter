const STORAGE_STATE = "sahaayak-admin-oidc-state";
const STORAGE_VERIFIER = "sahaayak-admin-oidc-verifier";

export type AdminOidcTokens = {
  accessToken: string;
  idToken: string;
  expiresAt: number;
};

export function adminOidcConfig() {
  const issuer = (import.meta.env.VITE_ADMIN_OIDC_ISSUER ?? "").trim().replace(/\/$/, "");
  const clientId = (import.meta.env.VITE_ADMIN_OIDC_CLIENT_ID ?? "").trim();
  const redirectUri =
    (import.meta.env.VITE_ADMIN_OIDC_REDIRECT_URI ?? "").trim() ||
    `${window.location.origin}/admin/callback`;
  return {
    issuer,
    clientId,
    redirectUri,
    scope: (import.meta.env.VITE_ADMIN_OIDC_SCOPE ?? "openid profile email").trim(),
  };
}

export function isAdminOidcConfigured(): boolean {
  const config = adminOidcConfig();
  return Boolean(config.issuer && config.clientId);
}

export async function beginAdminOidcLogin(): Promise<void> {
  const config = adminOidcConfig();
  if (!config.issuer || !config.clientId) {
    throw new Error("Admin OIDC is not configured for this web deployment.");
  }
  const state = randomString(32);
  const verifier = randomString(64);
  const challenge = await sha256Base64Url(verifier);
  sessionStorage.setItem(STORAGE_STATE, state);
  sessionStorage.setItem(STORAGE_VERIFIER, verifier);

  const authorization = new URL(`${config.issuer}/protocol/openid-connect/auth`);
  authorization.search = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    response_type: "code",
    scope: config.scope,
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
    // Force the password form. A stale Keycloak SSO cookie otherwise can land
    // on the "Invalid username or password" error page with no login UI.
    prompt: "login",
  }).toString();
  window.location.assign(authorization.toString());
}

export async function completeAdminOidcLogin(): Promise<AdminOidcTokens> {
  const config = adminOidcConfig();
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
    throw new Error("The admin sign-in response could not be verified.");
  }

  const response = await fetch(`${config.issuer}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code,
      redirect_uri: config.redirectUri,
      code_verifier: verifier,
    }),
  });
  if (!response.ok) throw new Error("The identity provider rejected the admin sign-in.");
  const payload = (await response.json()) as {
    access_token?: string;
    id_token?: string;
    expires_in?: number;
  };
  if (!payload.access_token) throw new Error("The identity provider returned no access token.");
  window.history.replaceState({}, document.title, "/admin");
  return {
    accessToken: payload.access_token,
    idToken: payload.id_token ?? "",
    expiresAt: Date.now() + Math.max(30, payload.expires_in ?? 300) * 1000,
  };
}

export function beginAdminOidcLogout(idToken: string): void {
  const config = adminOidcConfig();
  if (!config.issuer) return;
  const logout = new URL(`${config.issuer}/protocol/openid-connect/logout`);
  logout.search = new URLSearchParams({
    client_id: config.clientId,
    post_logout_redirect_uri: window.location.origin + "/admin",
    ...(idToken ? { id_token_hint: idToken } : {}),
  }).toString();
  window.location.assign(logout.toString());
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
