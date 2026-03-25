/**
 * Common types for scan/fix operations shared by both the Playground
 * (useSessionStream) and Project (useProjectOperation) hooks.
 */

export type OperationStatus =
  | "idle"
  | "connecting"
  | "preparing"
  | "scanning"
  | "tier1_done"
  | "awaiting_approval"
  | "applying"
  | "complete"
  | "disconnected"
  | "error";

export interface OperationProgress {
  phase: string;
  message: string;
  timestamp: number;
}

export interface OperationProposal {
  id: string;
  rule_id: string;
  file: string;
  tier: number;
  confidence: number;
  explanation?: string;
  diff_hunk?: string;
}

export interface OperationResult {
  total_violations: number;
  auto_fixable: number;
  ai_candidate: number;
  manual_review: number;
  fixed_count?: number;
}

export interface OperationState {
  status: OperationStatus;
  progress: OperationProgress[];
  proposals: OperationProposal[];
  result: OperationResult | null;
  error: string | null;
  approve: (ids: string[]) => void;
  cancel: () => void;
  reset: () => void;
}
