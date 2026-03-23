import { describe, it, expect } from "vitest";
import { bareRuleId, getRuleDescription, RULE_DESCRIPTIONS } from "../data/ruleDescriptions";

describe("bareRuleId", () => {
  it("strips validator prefix", () => {
    expect(bareRuleId("native:L042")).toBe("L042");
    expect(bareRuleId("opa:L003")).toBe("L003");
  });

  it("returns the original if no prefix", () => {
    expect(bareRuleId("L042")).toBe("L042");
    expect(bareRuleId("SEC001")).toBe("SEC001");
  });

  it("handles edge cases", () => {
    expect(bareRuleId(":L042")).toBe(":L042");
    expect(bareRuleId("a:")).toBe("a:");
    expect(bareRuleId("")).toBe("");
  });
});

describe("getRuleDescription", () => {
  it("returns description for a known rule", () => {
    expect(getRuleDescription("L003")).toBe("Each play should have a name.");
  });

  it("resolves prefixed rule IDs via bareRuleId", () => {
    const desc = RULE_DESCRIPTIONS["L003"];
    expect(desc).toBeDefined();
    expect(getRuleDescription("native:L003")).toBe(desc);
  });

  it("returns empty string for unknown rules", () => {
    expect(getRuleDescription("ZZZZ999")).toBe("");
    expect(getRuleDescription("native:ZZZZ999")).toBe("");
  });
});

describe("RULE_DESCRIPTIONS", () => {
  it("contains expected rule IDs", () => {
    expect(RULE_DESCRIPTIONS).toHaveProperty("L002");
    expect(RULE_DESCRIPTIONS).toHaveProperty("L005");
    expect(RULE_DESCRIPTIONS).toHaveProperty("L003");
  });

  it("values are non-empty strings", () => {
    for (const [key, value] of Object.entries(RULE_DESCRIPTIONS)) {
      expect(typeof value).toBe("string");
      expect(value.length, `${key} should have a non-empty description`).toBeGreaterThan(0);
    }
  });
});
