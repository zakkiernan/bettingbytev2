import type { IngestionHealthResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      signal: controller.signal,
      ...opts,
    });
    if (!res.ok) {
      throw new Error(`API ${res.status} - ${path}`);
    }
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

export function fetchHealth(): Promise<IngestionHealthResponse> {
  return apiFetch("/health");
}

export * from "./nba-api";
