export const CACHE_SCHEMA_VERSION = "v1";
export const PUBLIC_CACHE_MARKER = "public-reviewed-v1";

export const CACHE_NAMES = {
  shell: `sahaayak-shell-${CACHE_SCHEMA_VERSION}`,
  publicCatalog: `sahaayak-public-catalog-${CACHE_SCHEMA_VERSION}`,
  publicContent: `sahaayak-public-content-${CACHE_SCHEMA_VERSION}`,
  fonts: `sahaayak-fonts-${CACHE_SCHEMA_VERSION}`,
} as const;

const PRIVATE_PATH_PREFIXES = [
  "/admin",
  "/assistant",
  "/applications",
  "/household",
  "/account",
  "/settings",
  "/api/sessions",
  "/api/citizen",
  "/api/households",
  "/api/assistant",
  "/api/admin",
  "/api/voice",
  "/api/turns",
  "/api/rag",
];

export function isPrivatePath(pathname: string): boolean {
  return PRIVATE_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function isPublicApiPath(pathname: string): boolean {
  return pathname === "/api/public" || pathname.startsWith("/api/public/");
}

export function isSafeNavigationPath(pathname: string): boolean {
  if (isPrivatePath(pathname) || pathname.startsWith("/api/")) return false;
  return pathname === "/" || pathname === "/offline" || pathname.startsWith("/benefits/");
}

export function isPublicReviewedResponse(response: Response): boolean {
  return (
    response.ok &&
    response.headers.get("X-Sahaayak-Cache-Class") === PUBLIC_CACHE_MARKER &&
    response.headers.get("Content-Type")?.toLowerCase().includes("application/json") === true
  );
}

export function isSensitiveApiPath(pathname: string): boolean {
  return pathname.startsWith("/api/") && !isPublicApiPath(pathname);
}
