import type { AgentRun, AgentStatus, CompetitionStatus } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...init?.headers
    }
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchStatus(): Promise<AgentStatus> {
  return request<AgentStatus>("/status");
}

export function runDryRun(): Promise<AgentRun> {
  return request<AgentRun>("/dry-run", { method: "POST" });
}

export function fetchCompetitionStatus(): Promise<CompetitionStatus> {
  return request<CompetitionStatus>("/competition/status");
}

export function registerCompetition(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/competition/register", { method: "POST" });
}
