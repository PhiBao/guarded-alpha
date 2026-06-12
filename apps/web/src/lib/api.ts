import type {
  AgentRun,
  AgentStatus,
  CompetitionReadiness,
  CompetitionStatus,
  RunCard
} from "../types";

export const POLL_MS = Number(import.meta.env.VITE_POLL_MS ?? 15000);

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

export function fetchLedger(limit = 20): Promise<AgentRun[]> {
  return request<AgentRun[]>(`/ledger?limit=${limit}`);
}

export function runCycle(): Promise<AgentRun> {
  return request<AgentRun>("/run-cycle", { method: "POST" });
}

export function runDryRun(): Promise<AgentRun> {
  return request<AgentRun>("/dry-run", { method: "POST" });
}

export function fetchCompetitionStatus(): Promise<CompetitionStatus> {
  return request<CompetitionStatus>("/registration/status");
}

export function fetchCompetitionReadiness(): Promise<CompetitionReadiness> {
  return request<CompetitionReadiness>("/readiness");
}

export function registerCompetition(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/competition/register", { method: "POST" });
}

export function fetchWalletStatus(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/wallet/status");
}

export function fetchRunCard(runId: string): Promise<RunCard> {
  return request<RunCard>(`/run-card/${runId}`);
}
