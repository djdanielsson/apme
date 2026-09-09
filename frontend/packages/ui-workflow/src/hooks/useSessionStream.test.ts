import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSessionStream } from "./useSessionStream";

const STORAGE_KEY = "apme_active_session";

/** Minimal WebSocket stand-in capturing instances and sent frames. */
class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readyState = MockWebSocket.OPEN;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  send = vi.fn();
  close = vi.fn((_code?: number) => {
    this.readyState = MockWebSocket.CLOSED;
  });

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
}

function lastSocket(): MockWebSocket {
  const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
  if (!ws) throw new Error("expected a WebSocket to have been created");
  return ws;
}

function sendMsg(ws: MockWebSocket, msg: unknown): void {
  act(() => {
    ws.onmessage?.({ data: JSON.stringify(msg) });
  });
}

async function startSessionWithSocket() {
  const { result, unmount } = renderHook(() => useSessionStream());
  await act(async () => {
    await result.current.startSession([], {});
  });
  const ws = lastSocket();
  act(() => {
    ws.onopen?.(new Event("open"));
  });
  return { result, unmount, ws };
}

function validTier1() {
  return {
    type: "tier1_complete",
    idempotency_ok: true,
    patches: [],
    format_diffs: [],
    report: null,
  };
}

function proposalBase() {
  return {
    id: "p1",
    file: "site.yml",
    rule_id: "R1",
    before_text: "before",
    after_text: "after",
    diff_hunk: "@@",
    confidence: 0.9,
    explanation: "fix",
    tier: 2,
  };
}

describe("useSessionStream hardening", () => {
  beforeEach(() => {
    sessionStorage.clear();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("accepts proposals omitting line_start and normalizes to 0", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      sendMsg(lastSocket(), {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });
      sendMsg(lastSocket(), validTier1());
      sendMsg(lastSocket(), {
        type: "proposals",
        proposals: [{ ...proposalBase(), line_end: 5 }],
      });

      expect(result.current.error).toBeNull();
      expect(result.current.status).toBe("awaiting_approval");
      expect(result.current.proposals).toHaveLength(1);
      expect(result.current.proposals[0]?.line_start).toBe(0);
      expect(result.current.proposals[0]?.line_end).toBe(5);
    } finally {
      unmount();
    }
  });

  it("accepts proposals omitting line_end and both line fields", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      sendMsg(lastSocket(), {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });
      sendMsg(lastSocket(), validTier1());
      sendMsg(lastSocket(), {
        type: "proposals",
        proposals: [
          { ...proposalBase(), line_start: 3 },
          { ...proposalBase(), id: "p2" },
        ],
      });

      expect(result.current.error).toBeNull();
      expect(result.current.proposals).toHaveLength(2);
      expect(result.current.proposals[0]?.line_end).toBe(0);
      expect(result.current.proposals[1]?.line_start).toBe(0);
      expect(result.current.proposals[1]?.line_end).toBe(0);
    } finally {
      unmount();
    }
  });

  it("malformed proposals preserves the persisted session and reconnect affordance", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      const ws = lastSocket();
      sendMsg(ws, {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });
      sendMsg(ws, validTier1());
      expect(result.current.status).toBe("tier1_done");

      sendMsg(ws, { type: "proposals", proposals: [{ id: 123 }] });

      expect(result.current.error).toBe("Received malformed proposals from server");
      // Server session is alive: resume material must survive.
      expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull();
      expect(ws.close).not.toHaveBeenCalled();
      // tier1_done is reconnectable → reconnect affordance per phase logic.
      expect(result.current.canReconnect).toBe(true);
      expect(result.current.status).toBe("disconnected");
    } finally {
      unmount();
    }
  });

  it("malformed tier1_complete preserves the persisted session without tearing down", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      const ws = lastSocket();
      sendMsg(ws, {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });

      sendMsg(ws, {
        type: "tier1_complete",
        idempotency_ok: "yes",
        patches: [],
        format_diffs: [],
        report: null,
      });

      expect(result.current.error).toBe(
        "Received malformed tier1 result from server",
      );
      expect(result.current.tier1).toBeNull();
      expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull();
      expect(ws.close).not.toHaveBeenCalled();
      // "checking" is not reconnectable → error without reconnect.
      expect(result.current.canReconnect).toBe(false);
      expect(result.current.status).toBe("error");
    } finally {
      unmount();
    }
  });

  it("malformed terminal result still tears down the session", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      const ws = lastSocket();
      sendMsg(ws, {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });
      sendMsg(ws, validTier1());
      sendMsg(ws, {
        type: "proposals",
        proposals: [{ ...proposalBase(), line_start: 1, line_end: 2 }],
      });
      expect(result.current.status).toBe("awaiting_approval");

      sendMsg(ws, {
        type: "result",
        scan_id: 123,
        patches: [],
        report: null,
        remaining_violations: [],
      });

      expect(result.current.error).toBe("Received malformed result from server");
      expect(result.current.status).toBe("error");
      expect(result.current.canReconnect).toBe(false);
      expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
      expect(ws.close).toHaveBeenCalledWith(1000);
    } finally {
      unmount();
    }
  });

  it("rejects an array report on tier1_complete", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      const ws = lastSocket();
      sendMsg(ws, {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });
      sendMsg(ws, {
        type: "tier1_complete",
        idempotency_ok: true,
        patches: [],
        format_diffs: [],
        report: [],
      });

      expect(result.current.tier1).toBeNull();
      expect(result.current.error).toBe(
        "Received malformed tier1 result from server",
      );
      // Non-terminal: resume material survives.
      expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull();
      expect(ws.close).not.toHaveBeenCalled();
    } finally {
      unmount();
    }
  });

  it("rejects an array report on terminal result with teardown", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      const ws = lastSocket();
      sendMsg(ws, {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });
      sendMsg(ws, {
        type: "result",
        scan_id: "scan-1",
        patches: [],
        report: [],
        remaining_violations: [],
      });

      expect(result.current.result).toBeNull();
      expect(result.current.error).toBe("Received malformed result from server");
      expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
      expect(ws.close).toHaveBeenCalledWith(1000);
    } finally {
      unmount();
    }
  });

  it("treats session_created with empty ids as malformed without persisting", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      const ws = lastSocket();
      sendMsg(ws, { type: "session_created", session_id: "", scan_id: "scan-1" });

      expect(result.current.error).toBe("Received malformed session from server");
      expect(result.current.sessionId).toBeNull();
      expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();

      sendMsg(ws, { type: "session_created", session_id: "sess-1", scan_id: "" });

      expect(result.current.sessionId).toBeNull();
      expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    } finally {
      unmount();
    }
  });

  it("persists valid session_created ids", async () => {
    const { result, unmount } = await startSessionWithSocket();
    try {
      sendMsg(lastSocket(), {
        type: "session_created",
        session_id: "sess-1",
        scan_id: "scan-1",
      });

      expect(result.current.sessionId).toBe("sess-1");
      expect(result.current.scanId).toBe("scan-1");
      const raw = sessionStorage.getItem(STORAGE_KEY);
      expect(raw).not.toBeNull();
      expect(JSON.parse(raw as string)).toMatchObject({
        sessionId: "sess-1",
        scanId: "scan-1",
      });
    } finally {
      unmount();
    }
  });
});
