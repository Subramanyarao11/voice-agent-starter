import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function labelForSlot(slot: string | null | undefined): string {
  return slot ? slot.replaceAll("_", " ") : "none";
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function newCallerId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `web_${crypto.randomUUID()}`;
  }
  return `web_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
}

export function audioDataUrl(audioBase64?: string | null, mimeType?: string | null) {
  return audioBase64 && mimeType ? `data:${mimeType};base64,${audioBase64}` : null;
}
