/**
 * Client-side fingerprint computation for violation suppression (ADR-055).
 *
 * Uses the Web Crypto API for SHA-256 hashing. The fingerprint formula is:
 *   SHA-256(canonicalize(rule_id) + "\x00" + original_yaml)
 *
 * Both client and server hash the raw `original_yaml` (no normalization).
 * This keeps fingerprints deterministic and consistent across browser and gateway.
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
