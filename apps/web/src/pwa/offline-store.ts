import { openDB, type DBSchema } from "idb";

export const OFFLINE_DRAFT_MAX_LENGTH = 2_000;
export const OFFLINE_DRAFT_TTL_MS = 24 * 60 * 60 * 1_000;

export type OfflineDraft = {
  id: string;
  text: string;
  locale: string;
  createdAt: string;
  expiresAt: string;
  userApproved: true;
  submissionIdempotencyKey: string;
  schemaVersion: 1;
};

interface OfflineDatabase extends DBSchema {
  drafts: {
    key: string;
    value: OfflineDraft;
    indexes: { "by-expires-at": string };
  };
}

const databasePromise = openDB<OfflineDatabase>("sahaayak-offline-v1", 1, {
  upgrade(database) {
    const store = database.createObjectStore("drafts", { keyPath: "id" });
    store.createIndex("by-expires-at", "expiresAt");
  },
});

function randomId(prefix: string): string {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi.randomUUID === "function") {
    return `${prefix}_${cryptoApi.randomUUID()}`;
  }
  const bytes = new Uint8Array(16);
  cryptoApi.getRandomValues(bytes);
  return `${prefix}_${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

function normalizeDraftText(text: string): string {
  const normalized = text.replace(/\u0000/g, "").trim();
  if (!normalized || normalized.length > OFFLINE_DRAFT_MAX_LENGTH) {
    throw new Error(`Offline drafts must contain 1–${OFFLINE_DRAFT_MAX_LENGTH} characters.`);
  }
  return normalized;
}

export async function saveOfflineDraft(text: string, locale: string): Promise<OfflineDraft> {
  const now = Date.now();
  const draft: OfflineDraft = {
    id: randomId("draft"),
    text: normalizeDraftText(text),
    locale: locale || "en",
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + OFFLINE_DRAFT_TTL_MS).toISOString(),
    userApproved: true,
    submissionIdempotencyKey: randomId("turn"),
    schemaVersion: 1,
  };
  const database = await databasePromise;
  await database.put("drafts", draft);
  return draft;
}

export async function listOfflineDrafts(): Promise<OfflineDraft[]> {
  const database = await databasePromise;
  const drafts = await database.getAllFromIndex("drafts", "by-expires-at");
  const now = Date.now();
  const active = drafts.filter((draft) => Date.parse(draft.expiresAt) > now);
  await Promise.all(
    drafts
      .filter((draft) => Date.parse(draft.expiresAt) <= now)
      .map((draft) => database.delete("drafts", draft.id)),
  );
  return active;
}

export async function deleteOfflineDraft(id: string): Promise<void> {
  const database = await databasePromise;
  await database.delete("drafts", id);
}

export async function clearOfflineDrafts(): Promise<void> {
  const database = await databasePromise;
  await database.clear("drafts");
}
