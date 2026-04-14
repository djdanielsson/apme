/**
 * SSE hook for real-time project operation state (ADR-052).
 *
 * Connects to GET /api/v1/projects/{id}/operation/events and returns
 * the current OperationState.  On initial connect receives a full
 * snapshot, then applies delta events.  Automatically reconnects on
 * disconnect.  Returns null when no operation is active.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type ProjectOperationStatus =
  | "queued"
  | "cloning"
  | "scanning"
  | "awaiting_approval"
  | "applying"
  | "completed"
  | "submitting_pr"
  | "pr_submitted"
  | "failed"
  | "expired"
  | "cancelled";

const TERMINAL_STATUSES = new Set<ProjectOperationStatus>([
  "completed",
  "pr_submitted",
  "failed",
  "expired",
  "cancelled",
]);

export interface ProgressEntry {
  phase: string;
  message: string;
  timestamp: string;
  progress?: number | null;
  level?: number | null;
}

export interface Proposal {
  id: string;
  rule_id: string;
  file: string;
  tier: number;
  confidence: number;
  explanation?: string;
  diff_hunk?: string;
  status?: "proposed" | "declined";
  suggestion?: string;
  line_start?: number;
}

export interface OperationResultData {
  total_violations: number;
  fixable: number;
  ai_proposed: number;
  ai_declined: number;
  ai_accepted: number;
  manual_review: number;
  remediated_count: number;
  fixed_violations: Array<Record<string, unknown>>;
  patches: Array<{ file: string; diff: string }>;
}

export interface ProjectOperationState {
  operation_id: string;
  project_id: string;
  scan_id: string;
  status: ProjectOperationStatus;
  scan_type: "check" | "remediate";
  started_at: string;
  progress: ProgressEntry[];
  proposals?: Proposal[];
  result?: OperationResultData;
  pr_url?: string;
  error?: string;
  clone_commit?: string;
}

const BASE = "/api/v1";

/**
 * Poll for current operation state.  Returns the state snapshot, or null
 * if no operation exists (404).
 */
async function fetchState(
  projectId: string,
): Promise<ProjectOperationState | null> {
  try {
    const res = await fetch(`${BASE}/projects/${projectId}/operation`);
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return (await res.json()) as ProjectOperationState;
  } catch {
    return null;
  }
}

export function useProjectOperationState(projectId: string) {
  const [state, setState] = useState<ProjectOperationState | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const cleanup = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    setConnected(false);
  }, []);

  const connect = useCallback(() => {
    cleanup();

    const es = new EventSource(
      `${BASE}/projects/${projectId}/operation/events`,
    );
    esRef.current = es;

    es.addEventListener("snapshot", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as ProjectOperationState;
        setState(data);
        setConnected(true);
      } catch {
        /* ignore parse errors */
      }
    });

    es.addEventListener("status_changed", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as {
          status: string;
          previous: string;
          error?: string;
        };
        setState((prev) =>
          prev
            ? {
                ...prev,
                status: data.status as ProjectOperationStatus,
                ...(data.error ? { error: data.error } : {}),
              }
            : prev,
        );
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("progress", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const entry = JSON.parse(e.data) as ProgressEntry;
        setState((prev) =>
          prev ? { ...prev, progress: [...prev.progress, entry] } : prev,
        );
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("proposals", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as { proposals: Proposal[] };
        setState((prev) =>
          prev ? { ...prev, proposals: data.proposals } : prev,
        );
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("result", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const result = JSON.parse(e.data) as OperationResultData;
        setState((prev) => (prev ? { ...prev, result } : prev));
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("approval_ack", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as { applied_count: number };
        setState((prev) =>
          prev
            ? {
                ...prev,
                status: "applying" as ProjectOperationStatus,
                result: prev.result
                  ? { ...prev.result, ai_accepted: data.applied_count }
                  : prev.result,
              }
            : prev,
        );
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("pr_created", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as { pr_url: string };
        setState((prev) => (prev ? { ...prev, pr_url: data.pr_url } : prev));
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("error_event", (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as { error: string };
        setState((prev) => (prev ? { ...prev, error: data.error } : prev));
      } catch {
        /* ignore */
      }
    });

    es.onerror = () => {
      if (!mountedRef.current) return;
      es.close();
      esRef.current = null;
      setConnected(false);
      reconnectTimer.current = setTimeout(() => {
        if (mountedRef.current) connect();
      }, 3000);
    };
  }, [projectId, cleanup]);

  const poll = useCallback(async () => {
    const s = await fetchState(projectId);
    if (!mountedRef.current) return;
    if (!s) {
      setState(null);
      return;
    }
    setState(s);
    if (!TERMINAL_STATUSES.has(s.status)) {
      connect();
    }
  }, [projectId, connect]);

  useEffect(() => {
    mountedRef.current = true;
    poll();
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [poll, cleanup]);

  const refresh = useCallback(() => {
    poll();
  }, [poll]);

  const clear = useCallback(() => {
    cleanup();
    setState(null);
  }, [cleanup]);

  return { state, connected, refresh, clear };
}
