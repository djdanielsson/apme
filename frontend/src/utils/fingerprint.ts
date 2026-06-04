/**
 * Client-side fingerprint preview for violation suppression (ADR-055).
 *
 * Uses the Web Crypto API for SHA-256 hashing. This is a **preview-only**
 * approximation — the authoritative fingerprint is computed server-side
 * using normalized YAML (via `apme_engine.fingerprint.compute_fingerprint`).
 *
 * The Acknowledge flow sends `rule_id` + `original_yaml` to the server,
 * which computes and stores the canonical fingerprint. This client-side
 * function is retained for display/comparison purposes only.
 */

const LEGACY_PREFIX_RE = /^(native|opa|ansible|gitleaks):/;

export function canonicalizeRuleId(rawId: string): string {
  return rawId.trim().replace(LEGACY_PREFIX_RE, '');
}

export async function computeFingerprint(
  ruleId: string,
  originalYaml: string,
  mode: 'full' | 'rule_module' | 'rule_only' = 'full',
  moduleFqcn = '',
): Promise<string> {
  const canonicalId = canonicalizeRuleId(ruleId);

  let payload: string;
  if (mode === 'full') {
    payload = canonicalId + '\x00' + (originalYaml || '');
  } else if (mode === 'rule_module') {
    payload = canonicalId + '\x00' + moduleFqcn;
  } else {
    payload = canonicalId + '\x00';
  }

  const encoder = new TextEncoder();
  const data = encoder.encode(payload);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
